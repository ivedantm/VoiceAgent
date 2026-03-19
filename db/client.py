"""
db/client.py
────────────
Async Supabase client for the Braille Voice Agent.

Wraps supabase-py to provide clean, typed helpers for the three
operations the agent needs:

  • save_conversion()       — insert a new conversions row
  • get_recent_conversions() — fetch last N conversions for a user
  • create_session()        — start a session row
  • end_session()           — mark a session as ended
  • upsert_user()           — create or update a user row

All public methods are async (use asyncio.to_thread internally,
since supabase-py is synchronous under the hood).

Configuration:
  SUPABASE_URL              — from .env.local
  SUPABASE_SERVICE_ROLE_KEY — from .env.local
  SUPABASE_DEFAULT_USER_ID  — hardcoded UUID for MVP (no auth yet)
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(".env.local")

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Config — read from environment
# ──────────────────────────────────────────────

SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# For MVP: a single default user UUID. In Phase 4 this is replaced
# by real auth. You can set this in .env.local as SUPABASE_DEFAULT_USER_ID.
DEFAULT_USER_ID: str = os.environ.get(
    "SUPABASE_DEFAULT_USER_ID",
    "00000000-0000-0000-0000-000000000001",   # Stable placeholder UUID
)


# ──────────────────────────────────────────────
# Typed data classes matching the DB schema
# ──────────────────────────────────────────────

@dataclass
class ConversionRow:
    """Mirrors the `conversions` table columns."""
    user_id: str
    raw_text: str
    normalized_text: str
    braille_output: str
    braille_grade: int = 1
    stt_confidence: float = 1.0
    translate_confidence: float = 1.0
    session_id: Optional[str] = None
    confirmed: bool = True
    metadata: dict = field(default_factory=dict)
    start_time: Optional[str] = None   # ISO-8601 string
    end_time: Optional[str] = None


@dataclass
class SessionRow:
    """Mirrors the `sessions` table columns."""
    user_id: str
    livekit_room: Optional[str] = None
    events: list = field(default_factory=list)


# ──────────────────────────────────────────────
# Client class
# ──────────────────────────────────────────────

class BrailleDBClient:
    """
    Async wrapper around the Supabase Python client.

    Usage:
        db = BrailleDBClient()

        # Save a conversion
        row_id = await db.save_conversion(
            user_id=...,
            raw_text="The quick brown fox",
            normalized_text="The quick brown fox",
            braille_output="⠠⠞⠓⠑...",
            stt_confidence=0.95,
            translate_confidence=1.0,
        )

        # Get history
        rows = await db.get_recent_conversions(user_id=..., limit=5)
    """

    def __init__(self) -> None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env.local"
            )
        self._client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("BrailleDBClient initialised for project: %s", SUPABASE_URL)

    # ── Conversions ────────────────────────────────────────────────────────────

    async def save_conversion(
        self,
        raw_text: str,
        normalized_text: str,
        braille_output: str,
        stt_confidence: float = 1.0,
        translate_confidence: float = 1.0,
        braille_grade: int = 1,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        confirmed: bool = True,
        metadata: Optional[dict] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> str:
        """
        Insert a row into the `conversions` table.

        Returns the new row's UUID as a string.
        """
        row = {
            "user_id":              user_id or DEFAULT_USER_ID,
            "raw_text":             raw_text,
            "normalized_text":      normalized_text,
            "braille_output":       braille_output,
            "braille_grade":        braille_grade,
            "stt_confidence":       round(stt_confidence, 4),
            "translate_confidence": round(translate_confidence, 4),
            "session_id":           session_id,
            "confirmed":            confirmed,
            "metadata":             metadata or {},
            "start_time":           start_time.isoformat() if start_time else None,
            "end_time":             end_time.isoformat() if end_time else None,
        }

        def _insert() -> str:
            result = (
                self._client.table("conversions")
                .insert(row)
                .execute()
            )
            return result.data[0]["id"]

        row_id: str = await asyncio.to_thread(_insert)
        logger.info("[DB] Saved conversion %s", row_id)
        return row_id

    async def get_recent_conversions(
        self,
        user_id: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Fetch the *limit* most-recent conversions for a user,
        ordered newest first.

        Returns a list of dicts matching the `recent_conversions` view.
        """
        uid = user_id or DEFAULT_USER_ID

        def _select() -> list[dict]:
            result = (
                self._client.table("recent_conversions")
                .select("*")
                .eq("user_id", uid)
                .limit(limit)
                .execute()
            )
            return result.data

        rows: list[dict] = await asyncio.to_thread(_select)
        logger.info("[DB] Fetched %d recent conversions for user %s", len(rows), uid)
        return rows

    async def mark_exported(
        self,
        conversion_id: str,
        export_format: str,
        export_path: str,
    ) -> None:
        """Update a conversion row to record that it was exported."""

        def _update() -> None:
            self._client.table("conversions").update(
                {
                    "exported":      True,
                    "export_format": export_format,
                    "export_path":   export_path,
                }
            ).eq("id", conversion_id).execute()

        await asyncio.to_thread(_update)
        logger.info("[DB] Marked conversion %s as exported (%s)", conversion_id, export_format)

    # ── Sessions ───────────────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: Optional[str] = None,
        livekit_room: Optional[str] = None,
    ) -> str:
        """
        Insert a new session row (called when the agent activates).

        Returns the new session UUID as a string.
        """
        row = {
            "user_id":      user_id or DEFAULT_USER_ID,
            "livekit_room": livekit_room,
            "events":       [],
        }

        def _insert() -> str:
            result = (
                self._client.table("sessions")
                .insert(row)
                .execute()
            )
            return result.data[0]["id"]

        session_id: str = await asyncio.to_thread(_insert)
        logger.info("[DB] Created session %s", session_id)
        return session_id

    async def end_session(
        self,
        session_id: str,
        events: Optional[list] = None,
    ) -> None:
        """
        Mark a session as ended and write final events log.
        """
        update: dict[str, Any] = {
            "session_end": datetime.now(timezone.utc).isoformat(),
        }
        if events is not None:
            update["events"] = events

        def _update() -> None:
            self._client.table("sessions").update(update).eq("id", session_id).execute()

        await asyncio.to_thread(_update)
        logger.info("[DB] Ended session %s", session_id)

    async def append_session_event(
        self,
        session_id: str,
        event_type: str,
        payload: Optional[dict] = None,
    ) -> None:
        """
        Append a single event object to the session's events[] JSON array.
        Uses Postgres jsonb concatenation via RPC.
        """
        event = {
            "type":    event_type,
            "ts":      datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }

        def _append() -> None:
            # Fetch current events, append, and update — simple and reliable.
            result = (
                self._client.table("sessions")
                .select("events")
                .eq("id", session_id)
                .single()
                .execute()
            )
            current: list = result.data.get("events") or []
            current.append(event)
            self._client.table("sessions").update(
                {"events": current}
            ).eq("id", session_id).execute()

        await asyncio.to_thread(_append)

    # ── Users ──────────────────────────────────────────────────────────────────

    async def upsert_user(
        self,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        prefs: Optional[dict] = None,
    ) -> str:
        """
        Create or update a user row.

        Returns the user UUID.
        """
        uid = user_id or DEFAULT_USER_ID
        row: dict[str, Any] = {"id": uid}
        if email:
            row["email"] = email
        if display_name:
            row["display_name"] = display_name
        if prefs:
            row["prefs"] = prefs

        def _upsert() -> str:
            result = (
                self._client.table("users")
                .upsert(row, on_conflict="id")
                .execute()
            )
            return result.data[0]["id"]

        uid_returned: str = await asyncio.to_thread(_upsert)
        logger.info("[DB] Upserted user %s", uid_returned)
        return uid_returned

    async def get_user_prefs(self, user_id: Optional[str] = None) -> dict:
        """
        Fetch the preferences JSON for a user.

        Returns an empty dict if the user doesn't exist yet.
        """
        uid = user_id or DEFAULT_USER_ID

        def _select() -> dict:
            result = (
                self._client.table("users")
                .select("prefs")
                .eq("id", uid)
                .maybe_single()
                .execute()
            )
            return (result.data or {}).get("prefs", {})

        prefs: dict = await asyncio.to_thread(_select)
        return prefs


# ──────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────

_db_client: Optional[BrailleDBClient] = None


def get_db() -> BrailleDBClient:
    """
    Return a module-level singleton BrailleDBClient.
    Lazy-initialised on first call.
    """
    global _db_client
    if _db_client is None:
        _db_client = BrailleDBClient()
    return _db_client
