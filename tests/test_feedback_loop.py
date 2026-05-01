"""
tests/test_feedback_loop.py
───────────────────────────
Unit tests for the voice confirmation / feedback-loop logic in agent.py.

These tests completely bypass the LiveKit base class by instantiating
DefaultAgent without calling super().__init__() and patching `session`
at the class level.

Run with:
    cd "/Users/ved/Documents/Epics_Dicated Note Printer/Voice_Assistant"
    source venv/bin/activate
    python -m pytest tests/test_feedback_loop.py -v
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import DefaultAgent, AgentState

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.anyio   # use anyio (already installed) for async tests


def make_session_mock() -> MagicMock:
    sess = MagicMock()
    sess.generate_reply = AsyncMock()
    sess.clear_user_turn = MagicMock()
    return sess


def make_agent(session_mock=None) -> DefaultAgent:
    """
    Build a testable DefaultAgent:
      - Skips LiveKit super().__init__ entirely via object.__new__.
      - Creates a thin dynamic subclass that overrides the read-only
        `session` property with a mock, avoiding any livekit internals.
    """
    if session_mock is None:
        session_mock = make_session_mock()

    _mock = session_mock
    AgentUnderTest = type(
        "AgentUnderTest",
        (DefaultAgent,),
        {"session": property(lambda self: _mock)},
    )

    agent = object.__new__(AgentUnderTest)

    # Manually replicate DefaultAgent.__init__ instance attributes
    from braille_translator import BrailleGrade
    agent._state = AgentState.IDLE
    agent._current_grade = BrailleGrade.GRADE_1
    agent._last_conversion = None
    agent._last_conversion_id = None
    agent._history = []
    agent._accumulated_text = ""
    agent._pending_confirmation = None
    agent._pending_stt_confidence = 1.0
    agent._session_id = None
    agent._session_events = []

    return agent  # type: ignore[return-value]


def make_message(text: str, confidence: float = 1.0) -> MagicMock:
    msg = MagicMock()
    msg.content = text
    msg.confidence = confidence
    return msg


# ──────────────────────────────────────────────────────────────────────────────
# State routing
# ──────────────────────────────────────────────────────────────────────────────

class TestStateRouting:

    async def test_idle_wake_word_activates(self):
        agent = make_agent()
        agent._state = AgentState.IDLE
        await agent.on_user_turn_completed(None, make_message("hi sparky"))
        assert agent._state == AgentState.LISTENING

    async def test_idle_no_wake_word_stays_idle(self):
        agent = make_agent()
        agent._state = AgentState.IDLE
        await agent.on_user_turn_completed(None, make_message("hello world"))
        assert agent._state == AgentState.IDLE

    async def test_listening_speech_enters_accumulating(self):
        agent = make_agent()
        agent._state = AgentState.LISTENING
        await agent.on_user_turn_completed(None, make_message("the quick brown fox"))
        assert agent._state == AgentState.ACCUMULATING
        assert agent._accumulated_text == "the quick brown fox"

    async def test_listening_speech_triggers_continue_prompt(self):
        agent = make_agent()
        agent._state = AgentState.LISTENING
        await agent.on_user_turn_completed(None, make_message("hello world"))
        agent.session.generate_reply.assert_awaited_once()
        instructions = agent.session.generate_reply.call_args[1]["instructions"]
        assert "Is that all" in instructions

    async def test_stop_command_returns_to_idle(self):
        agent = make_agent()
        agent._state = AgentState.LISTENING
        await agent.on_user_turn_completed(None, make_message("stop"))
        assert agent._state == AgentState.IDLE

    async def test_empty_transcript_ignored(self):
        agent = make_agent()
        agent._state = AgentState.LISTENING
        await agent.on_user_turn_completed(None, make_message(""))
        assert agent._state == AgentState.LISTENING


# ──────────────────────────────────────────────────────────────────────────────
# Confirmation handler
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleConfirmation:

    async def test_yes_calls_pipeline(self):
        agent = make_agent()
        agent._pending_confirmation = "hello world"
        agent._run_pipeline = AsyncMock()

        await agent._handle_confirmation("yes")

        agent._run_pipeline.assert_awaited_once()
        assert agent._pending_confirmation is None
        assert agent._state == AgentState.LISTENING

    async def test_correct_also_confirms(self):
        agent = make_agent()
        agent._pending_confirmation = "the fox"
        agent._run_pipeline = AsyncMock()
        await agent._handle_confirmation("that's correct")
        agent._run_pipeline.assert_awaited_once()

    async def test_yeah_also_confirms(self):
        agent = make_agent()
        agent._pending_confirmation = "hello"
        agent._run_pipeline = AsyncMock()
        await agent._handle_confirmation("yeah")
        agent._run_pipeline.assert_awaited_once()

    async def test_no_enters_correcting(self):
        agent = make_agent()
        agent._pending_confirmation = "hello world"

        await agent._handle_confirmation("no")

        assert agent._state == AgentState.CORRECTING
        agent.session.generate_reply.assert_awaited_once()
        instr = agent.session.generate_reply.call_args[1]["instructions"]
        assert "wrong" in instr.lower()

    async def test_wrong_also_rejects(self):
        agent = make_agent()
        agent._pending_confirmation = "the fox"
        await agent._handle_confirmation("that's wrong")
        assert agent._state == AgentState.CORRECTING

    async def test_unclear_response_stays_confirming(self):
        agent = make_agent()
        agent._state = AgentState.CONFIRMING
        agent._pending_confirmation = "hello world"
        await agent._handle_confirmation("umm maybe")
        assert agent._state == AgentState.CONFIRMING

    async def test_yes_with_no_pending_does_not_crash(self):
        agent = make_agent()
        agent._pending_confirmation = None
        agent._run_pipeline = AsyncMock()
        await agent._handle_confirmation("yes")
        agent._run_pipeline.assert_not_awaited()


# ──────────────────────────────────────────────────────────────────────────────
# Correction handler
# ──────────────────────────────────────────────────────────────────────────────

class TestHandleCorrection:

    async def test_correction_updates_pending_and_enters_confirming(self):
        agent = make_agent()
        agent._pending_confirmation = "the quick brown fox"
        corrected = "the quick brown dog"

        with patch.object(agent, "_apply_correction_via_llm", AsyncMock(return_value=corrected)):
            await agent._handle_correction("change fox to dog")

        assert agent._pending_confirmation == corrected
        assert agent._state == AgentState.CONFIRMING

    async def test_correction_triggers_repeat_prompt(self):
        agent = make_agent()
        agent._pending_confirmation = "hello world"
        corrected = "hello earth"

        with patch.object(agent, "_apply_correction_via_llm", AsyncMock(return_value=corrected)):
            await agent._handle_correction("world should be earth")

        agent.session.generate_reply.assert_awaited_once()
        instr = agent.session.generate_reply.call_args[1]["instructions"]
        assert corrected in instr

    async def test_correction_llm_failure_keeps_original(self):
        agent = make_agent()
        agent._pending_confirmation = "original text"

        with patch.object(
            agent,
            "_apply_correction_via_llm",
            AsyncMock(return_value="original text"),
        ):
            await agent._handle_correction("something went wrong")

        assert agent._pending_confirmation == "original text"
        assert agent._state == AgentState.CONFIRMING


# ──────────────────────────────────────────────────────────────────────────────
# Full loop integration
# ──────────────────────────────────────────────────────────────────────────────

class TestFullLoop:

    async def test_full_loop_yes(self):
        """Speak → done → confirm → Braille emitted."""
        agent = make_agent()
        agent._state = AgentState.LISTENING
        agent._run_pipeline = AsyncMock()

        await agent.on_user_turn_completed(None, make_message("the quick brown fox"))
        assert agent._state == AgentState.ACCUMULATING

        await agent.on_user_turn_completed(None, make_message("yes")) # equivalent to DONE
        assert agent._state == AgentState.CONFIRMING

        await agent.on_user_turn_completed(None, make_message("yes")) # confirm
        agent._run_pipeline.assert_awaited_once_with(
            raw_text="the quick brown fox", stt_confidence=1.0
        )
        assert agent._state == AgentState.LISTENING

    async def test_full_loop_no_then_yes(self):
        """Speak → done → reject → correct → confirm → Braille emitted."""
        agent = make_agent()
        agent._state = AgentState.LISTENING
        agent._run_pipeline = AsyncMock()

        await agent.on_user_turn_completed(None, make_message("the quick brown fox"))
        await agent.on_user_turn_completed(None, make_message("that's all"))
        assert agent._state == AgentState.CONFIRMING

        await agent.on_user_turn_completed(None, make_message("no"))
        assert agent._state == AgentState.CORRECTING

        corrected = "the quick brown dog"
        with patch.object(agent, "_apply_correction_via_llm", AsyncMock(return_value=corrected)):
            await agent.on_user_turn_completed(None, make_message("fox should be dog"))

        assert agent._state == AgentState.CONFIRMING
        assert agent._pending_confirmation == corrected

        await agent.on_user_turn_completed(None, make_message("yes"))
        agent._run_pipeline.assert_awaited_once_with(
            raw_text=corrected, stt_confidence=1.0
        )
        assert agent._state == AgentState.LISTENING

    async def test_multiple_correction_rounds(self):
        """Reject twice before confirming — loop works correctly."""
        agent = make_agent()
        agent._state = AgentState.LISTENING
        agent._run_pipeline = AsyncMock()

        await agent.on_user_turn_completed(None, make_message("hello world"))
        await agent.on_user_turn_completed(None, make_message("done"))

        # Round 1 rejection
        await agent.on_user_turn_completed(None, make_message("no"))
        with patch.object(agent, "_apply_correction_via_llm", AsyncMock(return_value="hello earth")):
            await agent.on_user_turn_completed(None, make_message("world should be earth"))
        assert agent._pending_confirmation == "hello earth"

        # Round 2 rejection
        await agent.on_user_turn_completed(None, make_message("no"))
        with patch.object(agent, "_apply_correction_via_llm", AsyncMock(return_value="hello moon")):
            await agent.on_user_turn_completed(None, make_message("earth should be moon"))
        assert agent._pending_confirmation == "hello moon"

        # Final confirm
        await agent.on_user_turn_completed(None, make_message("yes"))
        agent._run_pipeline.assert_awaited_once_with(
            raw_text="hello moon", stt_confidence=1.0
        )
