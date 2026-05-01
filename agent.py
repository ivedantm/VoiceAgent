import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
)
from livekit.plugins import (
    noise_cancellation,
    silero,
)
from openai import AsyncOpenAI

from braille_translator import BrailleGrade, BrailleTranslator, TranslationResult
from db.client import BrailleDBClient, DEFAULT_USER_ID
from normalizer import Normalizer

logger = logging.getLogger("agent-Sage-210")

load_dotenv(".env.local")

# Debug file logger — captures output from forked child processes
_debug_fh = logging.FileHandler("/tmp/sparky_debug.log", mode="w")
_debug_fh.setLevel(logging.DEBUG)
_debug_fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_debug_fh)
logger.setLevel(logging.DEBUG)


# ──────────────────────────────────────────────────────────────────────────────
# Agent state
# ──────────────────────────────────────────────────────────────────────────────

class AgentState(str, Enum):
    IDLE = "idle"          # Waiting for wake-word "hi sparky"
    LISTENING = "listening"     # Ready to capture; may have accumulated text
    ACCUMULATING = "accumulating"  # Got speech; asked "is that all?"; waiting
    PROCESSING = "processing"    # Running normalizer / translator
    CONFIRMING = "confirming"    # Agent repeated full text; waiting for yes/no
    CORRECTING = "correcting"    # Agent asked what's wrong; waiting for fix


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
_openai = AsyncOpenAI()   # uses OPENAI_API_KEY from .env.local

# Wake-word detection: any of these phrases activate the agent.
WAKE_PHRASES = frozenset(["hi sparky", "hey sparky", "okay sparky", "sparky"])


def _check_wake_word(text: str) -> bool:
    """Return True if *text* contains a recognised wake phrase."""
    lower = text.strip().lower()
    return any(phrase in lower for phrase in WAKE_PHRASES)


def _strip_wake_word(text: str) -> str:
    """Remove the wake phrase from the transcript so it is not translated."""
    for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text.strip(" .,?!")


# ──────────────────────────────────────────────────────────────────────────────
# Agent
# ──────────────────────────────────────────────────────────────────────────────

class DefaultAgent(Agent):
    """
    Sparky — voice-activated Braille transcription agent.

    Pipeline:
        STT transcript → wake-word gate → normalizer → liblouis translator
        → voice confirmation loop → (on confirm) emit Braille + Supabase storage
    """

    def __init__(self, room=None) -> None:
        super().__init__(
            instructions="""You are Sparky. You are controlled by a Python application.
Your ONLY job is to execute the EXACT strings passed to you via 'Say exactly:', 'Ask exactly:', or 'Repeat' system instructions.

CRITICAL RULES:
1. NEVER generate your own responses or try to answer the user's speech directly. 
2. If the user speaks, you MUST REMAIN COMPLETELY SILENT (return an empty string). The Python script handles all tracking and will explicitly invoke you when a response is needed.
3. You do NOT perform Braille translation yourself. The Python application handles all translation and will explicitly provide the final string for you to output.
4. If you have nothing explicit to say via an instruction, DO NOT SPEAK.
""",
        )

        # Session-local state
        self._state: AgentState = AgentState.IDLE
        self._current_grade: BrailleGrade = BrailleGrade.GRADE_1
        self._last_conversion: Optional[ConversionRecord] = None
        self._last_conversion_id: Optional[str] = None   # DB row UUID
        self.room = room
        self._history: list[ConversionRecord] = []

        # Speech accumulation (builds up across multiple turns before confirmation)
        self._accumulated_text: str = ""         # grows as user keeps speaking

        # Feedback-loop state
        # text waiting for yes/no
        self._pending_confirmation: Optional[str] = None
        self._pending_stt_confidence: float = 1.0

        # Supabase session UUID
        self._session_id: Optional[str] = None
        self._session_events: list[dict] = []

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def on_enter(self) -> None:
        """Called when the agent joins a room."""
        logger.info(
            "Sparky agent entered. Translator available: %s",
            _translator.is_available(),
        )
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

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """
        Called every time the STT engine commits a final transcript.

        State routing:
          IDLE        → check wake word
          LISTENING   → accumulate speech, ask "is that all?"
          ACCUMULATING → done/continue gate
          CONFIRMING  → yes/no verification
          CORRECTING  → apply correction, re-enter CONFIRMING
        """
        try:
            raw_content = getattr(new_message, "content", "")
            if isinstance(raw_content, list):
                parts = []
                for c in raw_content:
                    if isinstance(c, str):
                        parts.append(c)
                    elif hasattr(c, "text"):
                        parts.append(str(getattr(c, "text", "")))
                transcript = " ".join(parts).strip()
            else:
                transcript = str(raw_content).strip()
            
            if not transcript:
                return

            # Suppress LiveKit's automatic LLM generation to prevent TTS crashes
            self.session.clear_user_turn()

            print(f"[SPARKY] Transcript: {transcript!r} | State: {self._state}", flush=True)
            logger.info("[STT] Committed transcript: %r (state=%s)",
                        transcript, self._state)

            # ── Wake-word gate ──────────────────────────────────────────────────
            if self._state == AgentState.IDLE:
                if _check_wake_word(transcript):
                    self._state = AgentState.LISTENING
                    print("[SPARKY] Wake-word detected! → LISTENING", flush=True)
                    logger.info("Wake-word detected. Switching to LISTENING.")
                    await self.session.generate_reply(
                        instructions='Say exactly: "Start speaking to translate."',
                        allow_interruptions=False,
                    )
                else:
                    logger.debug(
                        "[IDLE] Ignoring speech (no wake word): %r", transcript)
                return
        except Exception as exc:
            print(f"[SPARKY ERROR] on_user_turn_completed crashed: {exc}", flush=True)
            logger.error("[FATAL] on_user_turn_completed error: %s", exc, exc_info=True)
            raise

        # ── Global stop — works from ANY active state ───────────────────────
        _lower_global = transcript.lower().strip()
        if any(cmd in _lower_global for cmd in ["stop", "go to sleep", "sleep"]):
            prev_state = self._state
            self._state = AgentState.IDLE
            self._accumulated_text = ""
            self._pending_confirmation = None
            logger.info(
                "Stop command received from state=%s. Returning to IDLE.", prev_state)
            await self.session.generate_reply(
                instructions='Say exactly: "Okay, going to sleep. Say hi Sparky to wake me up."',
                allow_interruptions=False,
            )
            return

        # ── Done/continue gate ──────────────────────────────────────────────
        if self._state == AgentState.ACCUMULATING:
            await self._handle_accumulation_check(transcript)
            return

        # ── Confirmation response ───────────────────────────────────────────
        if self._state == AgentState.CONFIRMING:
            await self._handle_confirmation(transcript)
            return

        # ── Correction response ─────────────────────────────────────────────
        if self._state == AgentState.CORRECTING:
            await self._handle_correction(transcript)
            return

        # ── Voice commands (LISTENING state only) ───────────────────────────
        lower = transcript.lower()

        if "save" in lower:
            await self._run_save()
            return

        if "export" in lower:
            await self._run_export(lower)
            return

        if ("show" in lower and "conversion" in lower) or "history" in lower:
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

        # ── Accumulate speech and ask if the user is done ───────────────────
        clean_transcript = _strip_wake_word(transcript)
        if not clean_transcript:
            return

        # Append to any previously accumulated text
        if self._accumulated_text:
            self._accumulated_text += " " + clean_transcript
        else:
            self._accumulated_text = clean_transcript

        self._state = AgentState.ACCUMULATING
        logger.info("[Accumulate] Buffer now: %r", self._accumulated_text)

        # Brief pause so the question doesn't fire on top of the user's last word
        await asyncio.sleep(1.2)

        # Guard: if stop was called during the sleep, don't ask "is that all?"
        if self._state != AgentState.ACCUMULATING:
            return

        await self.session.generate_reply(
            instructions='Say exactly: "Is that all, or would you like to continue speaking?"',
            allow_interruptions=True,
        )

    # ── Accumulation check handler ─────────────────────────────────────────────

    async def _handle_accumulation_check(self, response: str) -> None:
        """
        Handle the 'is that all?' gate.

        done/yes  → lock accumulated text as pending_confirmation → CONFIRMING
        no/more   → say 'go ahead' → LISTENING (buffer kept, user appends)
        unclear   → re-prompt
        """
        lower = response.lower().strip()

        done_words = ["yes", "done", "finished", "that's all", "that is all",
                      "yeah", "yep", "correct", "i'm done", "im done", "that's it", "thats it"]
        more_words = ["no", "continue", "not yet", "not done", "nope",
                      "keep going", "more", "i'm not done", "im not done", "continuing"]

        if any(word in lower for word in done_words):
            full_text = self._accumulated_text
            self._accumulated_text = ""
            self._pending_confirmation = full_text
            self._pending_stt_confidence = 1.0
            self._state = AgentState.CONFIRMING
            logger.info("[Accumulate] User done. Full text: %r", full_text)

            await self.session.generate_reply(
                instructions=(
                    f'Say exactly: "{full_text}. Is this correct? Please say yes or no."'
                ),
                allow_interruptions=True,
            )

        elif any(word in lower for word in more_words):
            self._state = AgentState.LISTENING
            logger.info("[Accumulate] User wants to continue speaking.")

            await self.session.generate_reply(
                instructions='Say: "Go ahead, continue speaking."',
                allow_interruptions=True,
            )

        else:
            # Unclear — stay in ACCUMULATING and re-prompt
            logger.info(
                "[Accumulate] Unclear response %r — re-prompting.", response)
            await self.session.generate_reply(
                instructions=(
                    'Say exactly: "I didn\'t catch that. Is that all, '
                    'or would you like to continue speaking?"'
                ),
                allow_interruptions=True,
            )

    # ── Confirmation handler ───────────────────────────────────────────────────

    async def _handle_confirmation(self, response: str) -> None:
        """
        Process a yes/no confirmation response.

        yes → run Braille pipeline → LISTENING
        no  → ask what's wrong  → CORRECTING
        """
        lower = response.lower().strip()

        if any(word in lower for word in ["yes", "correct", "right", "confirm", "yep", "yeah"]):
            logger.info("[Confirm] User confirmed. Running pipeline.")
            pending = self._pending_confirmation
            confidence = self._pending_stt_confidence
            self._pending_confirmation = None
            self._pending_stt_confidence = 1.0
            self._state = AgentState.LISTENING

            if pending:
                await self._run_pipeline(raw_text=pending, stt_confidence=confidence)

        elif any(word in lower for word in ["no", "wrong", "incorrect", "not right", "nope", "nah"]):
            logger.info("[Confirm] User rejected. Entering CORRECTING.")
            self._state = AgentState.CORRECTING

            await self.session.generate_reply(
                instructions='Ask: "What part is wrong? Please describe the correction."',
                allow_interruptions=True,
            )

        else:
            # Unclear response — stay in CONFIRMING and prompt again
            logger.info(
                "[Confirm] Unclear response %r — re-prompting.", response)
            await self.session.generate_reply(
                instructions='Say: "Sorry, I didn\'t catch that. Please say yes or no."',
                allow_interruptions=True,
            )

    # ── Correction handler ─────────────────────────────────────────────────────

    async def _handle_correction(self, correction_description: str) -> None:
        """
        Apply the user's described correction to the pending transcript via LLM,
        then re-enter CONFIRMING with the updated text.
        """
        original = self._pending_confirmation or ""
        logger.info(
            "[Correct] Applying correction. Original: %r | Description: %r",
            original, correction_description,
        )

        corrected = await self._apply_correction_via_llm(original, correction_description)
        logger.info("[Correct] Corrected text: %r", corrected)

        self._pending_confirmation = corrected
        self._state = AgentState.CONFIRMING

        await self.session.generate_reply(
            instructions=(
                f'Repeat these words verbatim: "{corrected}" '
                f'— then ask: "Is this correct? Please say yes or no."'
            ),
            allow_interruptions=True,
        )

    async def _apply_correction_via_llm(
        self,
        original: str,
        correction_description: str,
    ) -> str:
        """
        Send the original transcript + correction description to GPT and return
        only the corrected text string. Falls back to the original on error.
        """
        try:
            response = await _openai.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a text correction assistant. "
                            "The user will give you an original transcript and a description of what needs to be fixed. "
                            "Apply the correction and return ONLY the corrected transcript text. "
                            "No explanation, no punctuation outside the text, no quotes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Original transcript: {original}\n"
                            f"Correction needed: {correction_description}\n\n"
                            "Return ONLY the corrected transcript."
                        ),
                    },
                ],
            )
            corrected = response.choices[0].message.content
            return corrected.strip() if corrected else original
        except Exception as exc:
            logger.error(
                "[Correct] LLM correction failed: %s — keeping original.", exc)
            return original

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
            # Only reset if stop wasn't called while we were normalizing
            if self._state == AgentState.PROCESSING:
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

        # Bail out early if stop was called while translating
        if self._state != AgentState.PROCESSING:
            logger.info(
                "[Pipeline] Aborted — state changed to %s during translate.", self._state)
            return

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

        # Bail out if stop was called while emitting
        if self._state != AgentState.PROCESSING:
            logger.info(
                "[Pipeline] Aborted — state changed to %s during emit.", self._state)
            return

        # 5. Notify user the translation is complete.
        #    We DO NOT send the braille string to TTS, because it will crash the TTS engine.
        display_text = f"Translated to Braille: {tr_result.braille}"
        logger.info("[Pipeline] Complete. %s", display_text)
        await self.session.generate_reply(
            instructions='Say exactly: "Translation complete. Sending to your printer."',
            allow_interruptions=False,
        )

        # Only return to LISTENING if stop wasn't issued while the pipeline ran.
        # If state is already IDLE (stop was called mid-pipeline), leave it alone.
        if self._state == AgentState.PROCESSING:
            self._accumulated_text = ""
            self._state = AgentState.LISTENING
        else:
            logger.info(
                "[Pipeline] Stop was issued mid-run — staying in state=%s.", self._state)

    async def _emit_braille(self, braille: str) -> None:
        """
        Publish the Braille string on the LiveKit room data channel.
        The frontend listens for this to render the output.
        """
        try:
            payload = braille.encode("utf-8")
            if self.room:
                await self.room.local_participant.publish_data(
                    payload,
                    topic="braille_output",
                    reliable=True,
                )
        except Exception as exc:
            logger.warning("Failed to emit braille over data channel: %s", exc)

    # ── Tool helpers ───────────────────────────────────────────────────────────

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

        export_dir = os.path.join(os.path.dirname(__file__), "exports")
        os.makedirs(export_dir, exist_ok=True)

        filename = f"conversion_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.{fmt}"
        filepath = os.path.join(export_dir, filename)

        content = rec.braille_output if fmt == "brl" else rec.raw_text
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("[Export] Written to %s", filepath)

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
        stt=inference.STT(
            model="assemblyai/universal-streaming", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(
            model="cartesia/sonic-3",
            voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            language="en",
        ),
        turn_detection=None,           # VAD-only turn detection (matches playground behavior)
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=False,    # our handler controls every reply explicitly
        min_endpointing_delay=0.5,      # commit turn 0.5s after user stops speaking
        max_endpointing_delay=1.5,      # hard commit at 1.5s
    )

    await session.start(
        agent=DefaultAgent(room=ctx.room),
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
