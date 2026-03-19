import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    inference,
    room_io,
)
from livekit.agents.llm import function_tool
from livekit.plugins import (
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from braille_translator import BrailleGrade, BrailleTranslator, TranslationResult
from db.client import BrailleDBClient, DEFAULT_USER_ID
from normalizer import Normalizer

logger = logging.getLogger("agent-Sage-210")

load_dotenv(".env.local")


# ──────────────────────────────────────────────────────────────────────────────
# Agent state
# ──────────────────────────────────────────────────────────────────────────────

class AgentState(str, Enum):
    IDLE = "idle"               # Waiting for wake-word "hi sparky"
    LISTENING = "listening"     # Actively capturing speech
    PROCESSING = "processing"   # Running STT → Normalizer → Translator
    CONFIRMING = "confirming"   # Low-confidence; asking user to confirm


@dataclass
class ConversionRecord:
    """Holds the result of one complete speech → Braille conversion."""
    raw_text: str
    normalized_text: str
    braille_output: str
    stt_confidence: float
    translate_confidence: float
    grade: BrailleGrade
    metadata: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# Shared pipeline components (initialised once per process)
# ──────────────────────────────────────────────────────────────────────────────

_normalizer = Normalizer()
_translator = BrailleTranslator(default_grade=BrailleGrade.GRADE_1)
_db = BrailleDBClient()

# STT confidence threshold — below this we ask the user to confirm.
STT_CONFIDENCE_THRESHOLD = 0.70

# Wake-word detection: any of these phrases activate the agent.
WAKE_PHRASES = frozenset(["hi sparky", "hey sparky", "okay sparky", "sparky"])


def _check_wake_word(text: str) -> bool:
    """Return True if *text* contains a recognised wake phrase."""
    lower = text.strip().lower()
    return any(phrase in lower for phrase in WAKE_PHRASES)


def _strip_wake_word(text: str) -> str:
    """Remove the wake phrase from the transcript so it is not translated."""
    for phrase in WAKE_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────────────────────────

class DefaultAgent(Agent):
    """
    Sparky — voice-activated Braille transcription agent.

    Pipeline:
        STT transcript → wake-word gate → normalizer → liblouis translator
        → voice reply + data channel emission (Phase 3: → Supabase storage)
    """

    def __init__(self) -> None:
        super().__init__(
            instructions="""You are Sparky, a voice-activated Braille transcription system.
Your ONLY purpose is to convert spoken words into Braille output and display the
Braille translation on screen.

──────────────────────────────────────────────────────
STARTUP
──────────────────────────────────────────────────────
When activated, say exactly: "Start speaking to translate."
Do NOT introduce yourself. Do not hold a conversation.

──────────────────────────────────────────────────────
WAKE WORD & RECORDING
──────────────────────────────────────────────────────
Listen ONLY for the wake phrase "hi sparky". Do NOT record or process speech
until the wake phrase is detected. After activation:
  • Record the user's speech until voice activity ends.
  • If no speech is detected within 10 seconds, say: "Please begin speaking."
  • Process the speech through the Braille pipeline immediately.

──────────────────────────────────────────────────────
SPEECH-TO-BRAILLE PIPELINE
──────────────────────────────────────────────────────
1. Transcribe audio using the STT engine.
2. Normalize the transcript (remove fillers, expand spoken punctuation).
3. Translate the normalized text to Braille using liblouis (Grade 1 default).
4. Display the Braille output on screen and emit it to the client.
5. If STT confidence < 0.70, ask: "Did you mean [transcript]? Please say yes or no."

──────────────────────────────────────────────────────
VOICE COMMANDS (respond to these after wake word)
──────────────────────────────────────────────────────
  • "save"                  → call save_conversion tool
  • "export" / "export as"  → call export_conversion tool
  • "show last conversion"  → call get_history tool
  • "stop" / "go to sleep"  → return to idle mode

──────────────────────────────────────────────────────
OUTPUT RULES
──────────────────────────────────────────────────────
• Speak in plain text only. No JSON, markdown, lists, or code.
• Do NOT introduce yourself. Do NOT explain internal processes.
• After successful translation: say "Translated to Braille." only.
• If translation fails: say "Translation failed. Please try again."
• Do NOT store, display, or speak anything before the wake phrase.
""",
        )

        # Session-local state
        self._state: AgentState = AgentState.IDLE
        self._current_grade: BrailleGrade = BrailleGrade.GRADE_1
        self._last_conversion: Optional[ConversionRecord] = None
        self._last_conversion_id: Optional[str] = None   # DB row UUID
        self._history: list[ConversionRecord] = []
        self._pending_confirmation: Optional[str] = None
        self._session_id: Optional[str] = None           # Supabase session UUID
        self._session_events: list[dict] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def on_enter(self) -> None:
        """Called when the agent joins a room."""
        logger.info(
            "Sparky agent entered. Translator available: %s",
            _translator.is_available(),
        )
        # Bootstrap the default user and open a DB session
        try:
            await _db.upsert_user(
                user_id=DEFAULT_USER_ID,
                display_name="Sparky User",
                prefs={"braille_grade": 1, "language": "en"},
            )
            room_name = getattr(self.session, "room", None)
            room_name = getattr(room_name, "name", None)
            self._session_id = await _db.create_session(
                user_id=DEFAULT_USER_ID,
                livekit_room=room_name,
            )
            logger.info("[DB] Session opened: %s", self._session_id)
        except Exception as exc:
            logger.warning("[DB] Could not open session: %s", exc)

        await self.session.generate_reply(
            instructions='Say exactly: "Start speaking to translate."',
            allow_interruptions=False,
        )

    async def on_leave(self) -> None:
        """Called when the agent leaves the room — close the DB session."""
        if self._session_id:
            try:
                await _db.end_session(
                    session_id=self._session_id,
                    events=self._session_events,
                )
                logger.info("[DB] Session closed: %s", self._session_id)
            except Exception as exc:
                logger.warning("[DB] Could not close session: %s", exc)

    # ── Core transcript handler ────────────────────────────────────────────────

    async def on_user_speech_committed(self, message) -> None:
        """
        Called every time the STT engine commits a final transcript.

        This is the entry point for the entire pipeline:
          STT → wake-word gate → normalizer → translator → emit + store
        """
        transcript: str = getattr(message, "content", str(message)).strip()
        if not transcript:
            return

        logger.info("[STT] Committed transcript: %r", transcript)

        # ── Wake-word gate ──────────────────────────────────────────────────
        if self._state == AgentState.IDLE:
            if _check_wake_word(transcript):
                self._state = AgentState.LISTENING
                logger.info("Wake-word detected. Switching to LISTENING.")
                return  # The agent instructions will handle the verbal response.
            else:
                # Not active — silently ignore.
                return

        # ── Confirmation response ───────────────────────────────────────────
        if self._state == AgentState.CONFIRMING:
            await self._handle_confirmation(transcript)
            return

        # ── Voice command routing ───────────────────────────────────────────
        lower = transcript.lower()
        if any(cmd in lower for cmd in ["stop", "go to sleep", "sleep"]):
            self._state = AgentState.IDLE
            logger.info("Stop command received. Returning to IDLE.")
            return

        if "save" in lower:
            await self._run_save()
            return

        if "export" in lower:
            await self._run_export(lower)
            return

        if "show" in lower and "conversion" in lower or "history" in lower:
            await self._run_history()
            return

        if "grade two" in lower or "contracted braille" in lower:
            self._current_grade = BrailleGrade.GRADE_2
            logger.info("Switched to Grade 2 Braille.")
            return

        if "grade one" in lower or "uncontracted braille" in lower:
            self._current_grade = BrailleGrade.GRADE_1
            logger.info("Switched to Grade 1 Braille.")
            return

        # ── Run Braille pipeline ────────────────────────────────────────────
        clean_transcript = _strip_wake_word(transcript)
        if not clean_transcript:
            return

        # Optionally get STT confidence from the message metadata
        stt_confidence: float = getattr(message, "confidence", 1.0) or 1.0

        # Low-confidence STT → ask for voice confirmation
        if stt_confidence < STT_CONFIDENCE_THRESHOLD:
            self._state = AgentState.CONFIRMING
            self._pending_confirmation = clean_transcript
            logger.info(
                "STT confidence %.2f below threshold. Requesting confirmation.",
                stt_confidence,
            )
            return  # Agent instructions will prompt user to confirm

        await self._run_pipeline(
            raw_text=clean_transcript,
            stt_confidence=stt_confidence,
        )

    # ── Pipeline ───────────────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        raw_text: str,
        stt_confidence: float = 1.0,
    ) -> None:
        """Execute normalizer → translator and emit result."""
        self._state = AgentState.PROCESSING

        # 1. Normalise
        norm_result = _normalizer.normalize(raw_text)
        logger.info(
            "[Normalizer] '%s' → '%s' (changes: %s)",
            raw_text,
            norm_result.normalized,
            norm_result.changes,
        )

        if not norm_result.normalized:
            self._state = AgentState.LISTENING
            return

        # 2. Translate
        tr_result: TranslationResult = _translator.translate(
            norm_result.normalized,
            grade=self._current_grade,
        )
        logger.info(
            "[Translator] '%s' → '%s' (confidence: %.2f, fallback: %s)",
            norm_result.normalized,
            tr_result.braille,
            tr_result.confidence,
            tr_result.used_fallback,
        )

        # 3. Store in session history
        record = ConversionRecord(
            raw_text=raw_text,
            normalized_text=norm_result.normalized,
            braille_output=tr_result.braille,
            stt_confidence=stt_confidence,
            translate_confidence=tr_result.confidence,
            grade=self._current_grade,
            metadata={
                "normalizer_changes": norm_result.changes,
                "used_fallback": tr_result.used_fallback,
            },
        )
        self._last_conversion = record
        self._history.append(record)

        # 4. Emit braille to room data channel so frontend receives it
        await self._emit_braille(tr_result.braille)

        logger.info("[Pipeline] Complete. Braille emitted.")
        self._state = AgentState.LISTENING

    async def _emit_braille(self, braille: str) -> None:
        """
        Publish the Braille string on the LiveKit room data channel.
        The frontend listens for this to render the output.
        """
        try:
            payload = braille.encode("utf-8")
            await self.session.room.local_participant.publish_data(
                payload,
                topic="braille_output",
                reliable=True,
            )
        except Exception as exc:
            logger.warning("Failed to emit braille over data channel: %s", exc)

    # ── Confirmation handler ───────────────────────────────────────────────────

    async def _handle_confirmation(self, response: str) -> None:
        lower = response.lower().strip()
        if any(word in lower for word in ["yes", "correct", "right", "confirm"]):
            if self._pending_confirmation:
                await self._run_pipeline(
                    raw_text=self._pending_confirmation,
                    stt_confidence=1.0,  # User confirmed, treat as high confidence
                )
            self._pending_confirmation = None
            self._state = AgentState.LISTENING
        elif any(word in lower for word in ["no", "wrong", "incorrect", "cancel"]):
            self._pending_confirmation = None
            self._state = AgentState.LISTENING
            logger.info("User rejected low-confidence transcript.")
        # Otherwise stay in CONFIRMING and wait for a clearer response.

    # ── Tool helpers (stubs — wired to Supabase in Phase 2/3) ─────────────────

    async def _run_save(self) -> None:
        """Persist the last conversion to Supabase."""
        if not self._last_conversion:
            logger.info("[Save] No conversion to save.")
            return
        rec = self._last_conversion
        try:
            row_id = await _db.save_conversion(
                raw_text=rec.raw_text,
                normalized_text=rec.normalized_text,
                braille_output=rec.braille_output,
                stt_confidence=rec.stt_confidence,
                translate_confidence=rec.translate_confidence,
                braille_grade=1 if rec.grade == BrailleGrade.GRADE_1 else 2,
                session_id=self._session_id,
                user_id=DEFAULT_USER_ID,
                confirmed=True,
                metadata=rec.metadata,
            )
            self._last_conversion_id = row_id
            self._session_events.append({
                "type": "save",
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": {"conversion_id": row_id},
            })
            logger.info("[Save] Conversion saved to DB: %s", row_id)
        except Exception as exc:
            logger.error("[Save] DB write failed: %s", exc)

    async def _run_export(self, transcript: str) -> None:
        """Export last conversion to a .brl or .txt file."""
        if not self._last_conversion:
            logger.info("[Export] No conversion to export.")
            return
        rec = self._last_conversion
        fmt = "txt" if "txt" in transcript else "brl"

        # Write to local exports/ folder
        export_dir = os.path.join(os.path.dirname(__file__), "exports")
        os.makedirs(export_dir, exist_ok=True)

        filename = f"conversion_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{fmt}"
        filepath = os.path.join(export_dir, filename)

        content = rec.braille_output if fmt == "brl" else rec.raw_text
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("[Export] Written to %s", filepath)

        # Update DB if we have a saved row ID
        if self._last_conversion_id:
            try:
                await _db.mark_exported(
                    conversion_id=self._last_conversion_id,
                    export_format=fmt,
                    export_path=filepath,
                )
            except Exception as exc:
                logger.warning("[Export] DB update failed: %s", exc)

    async def _run_history(self) -> None:
        """Retrieve and log the last 5 conversions from Supabase."""
        try:
            rows = await _db.get_recent_conversions(
                user_id=DEFAULT_USER_ID,
                limit=5,
            )
            if not rows:
                logger.info("[History] No conversions found in DB.")
                return
            last = rows[0]
            logger.info(
                "[History] Last conversion → Raw: %r | Braille: %s",
                last.get("raw_text"),
                last.get("braille_output"),
            )
        except Exception as exc:
            logger.error("[History] DB read failed: %s", exc)


# ──────────────────────────────────────────────────────────────────────────────
# Server setup
# ──────────────────────────────────────────────────────────────────────────────

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="Sage-210")
async def entrypoint(ctx: JobContext) -> None:
    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            language="en",
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=DefaultAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)