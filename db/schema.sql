-- ============================================================
-- Braille Voice Agent — Supabase Schema
-- ============================================================
-- HOW TO APPLY:
--   1. Open your Supabase project dashboard
--   2. Go to SQL Editor (left sidebar)
--   3. Paste this entire file and click "Run"
-- ============================================================


-- ── Enable UUID generation ───────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ============================================================
-- TABLE: users
-- Stores per-user preferences. Linked to Supabase Auth UIDs.
-- For the MVP we use a simple hardcoded user_id from .env;
-- replace with real auth later.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE,                          -- optional; null for anonymous users
    display_name    TEXT,
    prefs           JSONB NOT NULL DEFAULT '{}'::JSONB,   -- e.g. {"braille_grade": 1, "language": "en"}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.users IS
    'Voice agent users. Linked to Supabase Auth or created anonymously for MVP.';

COMMENT ON COLUMN public.users.prefs IS
    'JSON preferences: braille_grade (1|2), language ("en"), strip_fillers (bool), etc.';


-- ── Auto-update updated_at ───────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON public.users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- ============================================================
-- TABLE: sessions
-- One row per agent session (from wake-word to "stop").
-- ============================================================
CREATE TABLE IF NOT EXISTS public.sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    livekit_room    TEXT,                                 -- LiveKit room name for correlation
    session_start   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_end     TIMESTAMPTZ,                          -- NULL while session is active
    events          JSONB NOT NULL DEFAULT '[]'::JSONB,   -- array of {type, ts, payload} events
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id   ON public.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_start     ON public.sessions(session_start DESC);

COMMENT ON TABLE public.sessions IS
    'One row per agent activation (wake-word → stop/timeout). events logs voice commands, state transitions, etc.';


-- ============================================================
-- TABLE: conversions
-- One row per speech → Braille translation event.
-- ============================================================
CREATE TABLE IF NOT EXISTS public.conversions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    session_id           UUID REFERENCES public.sessions(id) ON DELETE SET NULL,

    -- Pipeline input / output
    raw_text             TEXT NOT NULL,                   -- original STT transcript
    normalized_text      TEXT NOT NULL,                   -- after normalizer.py
    braille_output       TEXT NOT NULL,                   -- liblouis Braille unicode
    braille_grade        SMALLINT NOT NULL DEFAULT 1      -- 1 = uncontracted, 2 = contracted
                             CHECK (braille_grade IN (1, 2)),

    -- Confidence scores (0.0 – 1.0)
    stt_confidence       REAL NOT NULL DEFAULT 1.0
                             CHECK (stt_confidence BETWEEN 0.0 AND 1.0),
    translate_confidence REAL NOT NULL DEFAULT 1.0
                             CHECK (translate_confidence BETWEEN 0.0 AND 1.0),

    -- Pipeline timing & debug metadata
    metadata             JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- e.g. {"normalizer_changes": [...], "used_fallback": false,
    --        "pipeline_ms": {"stt": 320, "normalize": 2, "translate": 5}}

    -- User-facing status
    confirmed            BOOLEAN NOT NULL DEFAULT TRUE,   -- False if user rejected confirmation
    exported             BOOLEAN NOT NULL DEFAULT FALSE,
    export_format        TEXT,                            -- "brl" | "txt" | null
    export_path          TEXT,                            -- Supabase Storage path when exported

    start_time           TIMESTAMPTZ,                     -- when audio started for this utterance
    end_time             TIMESTAMPTZ,                     -- when translation completed
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversions_user_id    ON public.conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_session_id ON public.conversions(session_id);
CREATE INDEX IF NOT EXISTS idx_conversions_created_at ON public.conversions(created_at DESC);

COMMENT ON TABLE public.conversions IS
    'One row per speech → Braille conversion. Includes raw/normalized text, Braille output, and confidence scores.';

COMMENT ON COLUMN public.conversions.metadata IS
    'JSON pipeline metadata: normalizer_changes, used_fallback, per-stage timing in ms.';


-- ============================================================
-- TABLE: assets (optional — audio recordings with consent)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    conversion_id   UUID REFERENCES public.conversions(id) ON DELETE SET NULL,
    storage_path    TEXT NOT NULL,                        -- Supabase Storage object path
    mime_type       TEXT NOT NULL DEFAULT 'audio/webm',
    size_bytes      BIGINT,
    consent         BOOLEAN NOT NULL DEFAULT FALSE,       -- must be TRUE before storing audio
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assets_user_id       ON public.assets(user_id);
CREATE INDEX IF NOT EXISTS idx_assets_conversion_id ON public.assets(conversion_id);

COMMENT ON TABLE public.assets IS
    'Audio recordings — only stored when consent = TRUE. Linked to a specific conversion.';


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Agent uses the service_role key (bypasses RLS).
-- Enable RLS anyway — good practice; protects against future
-- accidental client-side access.
-- ============================================================
ALTER TABLE public.users       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assets      ENABLE ROW LEVEL SECURITY;

-- service_role bypasses these policies automatically.
-- Add user-facing policies here when auth is wired up:
-- CREATE POLICY "users can read own row" ON public.users
--     FOR SELECT USING (auth.uid() = id);


-- ============================================================
-- HELPER VIEW: recent_conversions
-- Convenient view for the "show last conversion" voice command.
-- ============================================================
CREATE OR REPLACE VIEW public.recent_conversions AS
    SELECT
        c.id,
        c.user_id,
        c.session_id,
        c.raw_text,
        c.normalized_text,
        c.braille_output,
        c.braille_grade,
        c.stt_confidence,
        c.translate_confidence,
        c.confirmed,
        c.exported,
        c.created_at
    FROM public.conversions c
    ORDER BY c.created_at DESC;

COMMENT ON VIEW public.recent_conversions IS
    'Convenience view: conversions ordered by newest first, without heavy metadata columns.';
