"""
tests/test_pipeline.py
──────────────────────
Integration test: text → normalize → translate → save to Supabase.

Requires:
  - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set in .env.local
  - Schema already applied to Supabase (run db/schema.sql first)
  - venv active: source venv/bin/activate

Run:
    python -m pytest tests/test_pipeline.py -v
"""

import asyncio
import sys
import os
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from normalizer import Normalizer
from braille_translator import BrailleTranslator, BrailleGrade
from db.client import BrailleDBClient, DEFAULT_USER_ID


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def run(coro):
    """Run a coroutine synchronously — compatible with Python 3.10+."""
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def db():
    """Create one DB client for all tests in this module."""
    return BrailleDBClient()


@pytest.fixture(scope="module")
def pipeline():
    return Normalizer(), BrailleTranslator()


# ──────────────────────────────────────────────
# User bootstrap test
# ──────────────────────────────────────────────

class TestUserSetup:
    def test_upsert_default_user(self, db):
        """Ensure the default MVP user exists in the DB."""
        uid = run(db.upsert_user(
            user_id=DEFAULT_USER_ID,
            display_name="Sparky Test User",
            prefs={"braille_grade": 1, "language": "en"},
        ))
        assert uid == DEFAULT_USER_ID

    def test_get_user_prefs(self, db):
        prefs = run(db.get_user_prefs(user_id=DEFAULT_USER_ID))
        assert isinstance(prefs, dict)


# ──────────────────────────────────────────────
# Session tests
# ──────────────────────────────────────────────

class TestSessions:
    def test_create_and_end_session(self, db):
        session_id = run(db.create_session(
            user_id=DEFAULT_USER_ID,
            livekit_room="test-room",
        ))
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID format

        # Append an event
        run(db.append_session_event(
            session_id=session_id,
            event_type="wake_word_detected",
            payload={"phrase": "hi sparky"},
        ))

        # End the session
        run(db.end_session(
            session_id=session_id,
            events=[{"type": "session_ended", "ts": "2026-01-01T00:00:00Z", "payload": {}}],
        ))


# ──────────────────────────────────────────────
# Full pipeline round-trip tests
# ──────────────────────────────────────────────

class TestFullPipeline:
    """
    Run the text → normalize → translate → save → retrieve cycle
    against the real Supabase DB.
    """

    TEST_PHRASES = [
        "The quick brown fox jumps over the lazy dog period",
        "Hello, my name is Sparky exclamation mark",
        "1 2 3 test",
        "umm uh like I can't believe it",
    ]

    def test_pipeline_save_and_retrieve(self, db, pipeline):
        normalizer, translator = pipeline

        saved_ids = []
        for phrase in self.TEST_PHRASES:
            # Normalize
            norm = normalizer.normalize(phrase)
            # Translate
            tr = translator.translate(norm.normalized)
            # Save
            row_id = run(db.save_conversion(
                raw_text=phrase,
                normalized_text=norm.normalized,
                braille_output=tr.braille,
                stt_confidence=0.95,
                translate_confidence=tr.confidence,
                braille_grade=1,
                confirmed=True,
                metadata={
                    "normalizer_changes": norm.changes,
                    "used_fallback": tr.used_fallback,
                    "test": True,
                },
            ))
            assert isinstance(row_id, str)
            assert len(row_id) == 36
            saved_ids.append(row_id)

        assert len(saved_ids) == len(self.TEST_PHRASES)

    def test_get_recent_conversions(self, db):
        rows = run(db.get_recent_conversions(user_id=DEFAULT_USER_ID, limit=5))
        assert isinstance(rows, list)
        # Should have at least the rows we just inserted
        assert len(rows) >= 1
        # Each row should have these fields
        for row in rows:
            assert "braille_output" in row
            assert "raw_text" in row
            assert "created_at" in row

    def test_save_with_grade2(self, db, pipeline):
        normalizer, _ = pipeline
        translator_g2 = BrailleTranslator(default_grade=BrailleGrade.GRADE_2)
        norm = normalizer.normalize("hello world")
        tr = translator_g2.translate(norm.normalized)
        row_id = run(db.save_conversion(
            raw_text="hello world",
            normalized_text=norm.normalized,
            braille_output=tr.braille,
            braille_grade=2,
            metadata={"test": True},
        ))
        assert len(row_id) == 36

    def test_mark_exported(self, db, pipeline):
        normalizer, translator = pipeline
        norm = normalizer.normalize("export test")
        tr = translator.translate(norm.normalized)
        row_id = run(db.save_conversion(
            raw_text="export test",
            normalized_text=norm.normalized,
            braille_output=tr.braille,
            metadata={"test": True},
        ))
        # Should not raise
        run(db.mark_exported(
            conversion_id=row_id,
            export_format="brl",
            export_path=f"exports/{row_id}.brl",
        ))
