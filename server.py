"""
server.py
─────────
FastAPI backend for the Sparky Braille Voice Agent frontend.

Provides REST endpoints that wrap the existing Supabase client
and generate LiveKit participant tokens for the frontend.

Run:
    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from braille_translator import BrailleGrade, BrailleTranslator
from db.client import BrailleDBClient, DEFAULT_USER_ID
from normalizer import Normalizer

load_dotenv(".env.local")

logger = logging.getLogger("server")

# ──────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sparky Braille Agent API",
    version="1.0.0",
    description="Backend API for the Sparky Braille Voice Agent frontend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared instances ──────────────────────────────────────────
_db: Optional[BrailleDBClient] = None
_translator = BrailleTranslator(default_grade=BrailleGrade.GRADE_1)
_normalizer = Normalizer()


def _get_db() -> BrailleDBClient:
    global _db
    if _db is None:
        _db = BrailleDBClient()
    return _db


# ──────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    grade: int = 1  # 1 or 2


class TranslateResponse(BaseModel):
    original: str
    normalized: str
    braille: str
    confidence: float
    grade: int
    used_fallback: bool
    normalizer_changes: list[str]


class PrefsUpdate(BaseModel):
    braille_grade: Optional[int] = None
    language: Optional[str] = None
    strip_fillers: Optional[bool] = None


# ──────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "translator_available": _translator.is_available(),
    }


@app.get("/api/token")
async def get_token(room: str = Query(default=None)):
    """Generate a LiveKit participant token and dispatch the Sage-210 agent."""
    try:
        from livekit.api import AccessToken, VideoGrants, LiveKitAPI
        from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

        api_key = os.environ.get("LIVEKIT_API_KEY", "")
        api_secret = os.environ.get("LIVEKIT_API_SECRET", "")
        livekit_url = os.environ.get("LIVEKIT_URL", "")

        if not api_key or not api_secret:
            raise HTTPException(500, "LiveKit API credentials not configured")

        room_name = room or f"sparky-{uuid.uuid4().hex[:8]}"
        user_identity = f"user-{uuid.uuid4().hex[:6]}"

        # Generate participant token
        token = (
            AccessToken(api_key, api_secret)
            .with_identity(user_identity)
            .with_name("Sparky User")
            .with_grants(VideoGrants(
                room_join=True,
                room=room_name,
            ))
        )

        jwt_token = token.to_jwt()

        # Dispatch the Sage-210 agent to this room
        try:
            lk_api = LiveKitAPI(
                url=livekit_url,
                api_key=api_key,
                api_secret=api_secret,
            )
            await lk_api.agent_dispatch.create_dispatch(
                CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name="Sage-210",
                )
            )
            await lk_api.aclose()
            logger.info("Dispatched Sage-210 agent to room: %s", room_name)
        except Exception as dispatch_err:
            logger.warning("Agent dispatch failed (agent may not be running): %s", dispatch_err)

        return {
            "token": jwt_token,
            "room": room_name,
            "livekit_url": livekit_url,
        }
    except ImportError:
        raise HTTPException(500, "livekit-api package not installed")
    except Exception as exc:
        logger.error("Token generation failed: %s", exc)
        raise HTTPException(500, str(exc))


@app.get("/api/conversions")
async def get_conversions(limit: int = Query(default=20, le=100)):
    """Fetch recent conversions."""
    try:
        db = _get_db()
        rows = await db.get_recent_conversions(
            user_id=DEFAULT_USER_ID,
            limit=limit,
        )
        return {"conversions": rows, "total": len(rows)}
    except Exception as exc:
        logger.error("Failed to fetch conversions: %s", exc)
        raise HTTPException(500, str(exc))


@app.get("/api/conversions/{conversion_id}")
async def get_conversion(conversion_id: str):
    """Fetch a single conversion by ID."""
    try:
        db = _get_db()

        import asyncio

        def _select():
            result = (
                db._client.table("conversions")
                .select("*")
                .eq("id", conversion_id)
                .maybe_single()
                .execute()
            )
            return result.data

        row = await asyncio.to_thread(_select)
        if not row:
            raise HTTPException(404, "Conversion not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch conversion: %s", exc)
        raise HTTPException(500, str(exc))


@app.get("/api/sessions")
async def get_sessions(limit: int = Query(default=10, le=50)):
    """Fetch recent sessions."""
    try:
        db = _get_db()

        import asyncio

        def _select():
            result = (
                db._client.table("sessions")
                .select("*")
                .eq("user_id", DEFAULT_USER_ID)
                .order("session_start", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data

        rows = await asyncio.to_thread(_select)
        return {"sessions": rows, "total": len(rows)}
    except Exception as exc:
        logger.error("Failed to fetch sessions: %s", exc)
        raise HTTPException(500, str(exc))


@app.get("/api/stats")
async def get_stats():
    """Dashboard statistics."""
    try:
        db = _get_db()

        import asyncio

        def _fetch():
            # Total conversions
            conv_result = (
                db._client.table("conversions")
                .select("id, stt_confidence, translate_confidence, braille_grade, created_at", count="exact")
                .eq("user_id", DEFAULT_USER_ID)
                .execute()
            )

            # Total sessions
            sess_result = (
                db._client.table("sessions")
                .select("id", count="exact")
                .eq("user_id", DEFAULT_USER_ID)
                .execute()
            )

            conversions = conv_result.data or []
            total_conversions = len(conversions)
            total_sessions = len(sess_result.data or [])

            avg_stt = 0.0
            avg_translate = 0.0
            grade_1_count = 0
            grade_2_count = 0

            if conversions:
                avg_stt = sum(c.get("stt_confidence", 0) for c in conversions) / total_conversions
                avg_translate = sum(c.get("translate_confidence", 0) for c in conversions) / total_conversions
                grade_1_count = sum(1 for c in conversions if c.get("braille_grade") == 1)
                grade_2_count = sum(1 for c in conversions if c.get("braille_grade") == 2)

            return {
                "total_conversions": total_conversions,
                "total_sessions": total_sessions,
                "avg_stt_confidence": round(avg_stt, 3),
                "avg_translate_confidence": round(avg_translate, 3),
                "grade_1_count": grade_1_count,
                "grade_2_count": grade_2_count,
                "translator_available": _translator.is_available(),
            }

        stats = await asyncio.to_thread(_fetch)
        return stats
    except Exception as exc:
        logger.error("Failed to fetch stats: %s", exc)
        raise HTTPException(500, str(exc))


@app.get("/api/user/prefs")
async def get_prefs():
    """Get user preferences."""
    try:
        db = _get_db()
        prefs = await db.get_user_prefs(DEFAULT_USER_ID)
        return {"prefs": prefs}
    except Exception as exc:
        logger.error("Failed to fetch prefs: %s", exc)
        raise HTTPException(500, str(exc))


@app.put("/api/user/prefs")
async def update_prefs(body: PrefsUpdate):
    """Update user preferences."""
    try:
        db = _get_db()
        current = await db.get_user_prefs(DEFAULT_USER_ID)

        if body.braille_grade is not None:
            current["braille_grade"] = body.braille_grade
        if body.language is not None:
            current["language"] = body.language
        if body.strip_fillers is not None:
            current["strip_fillers"] = body.strip_fillers

        await db.upsert_user(
            user_id=DEFAULT_USER_ID,
            prefs=current,
        )
        return {"prefs": current}
    except Exception as exc:
        logger.error("Failed to update prefs: %s", exc)
        raise HTTPException(500, str(exc))


@app.post("/api/translate", response_model=TranslateResponse)
async def translate(body: TranslateRequest):
    """Direct text → Braille translation (non-voice, for demo/testing)."""
    if not body.text.strip():
        raise HTTPException(400, "Text cannot be empty")

    grade = BrailleGrade.GRADE_1 if body.grade == 1 else BrailleGrade.GRADE_2

    # Normalize
    norm = _normalizer.normalize(body.text)

    # Translate
    result = _translator.translate(norm.normalized, grade=grade)

    return TranslateResponse(
        original=body.text,
        normalized=norm.normalized,
        braille=result.braille,
        confidence=result.confidence,
        grade=body.grade,
        used_fallback=result.used_fallback,
        normalizer_changes=norm.changes,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
