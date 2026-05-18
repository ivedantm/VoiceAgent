# Braille Voice Agent

> **Sparky** — a wake-word activated, real-time voice agent that listens to natural speech and converts it into accurate Braille for blind and low-vision users.

Sparky is a full-stack voice → Braille pipeline built on [LiveKit](https://livekit.io/), [liblouis](https://liblouis.io/), and [Supabase](https://supabase.com/). Speak naturally, confirm what you said with your voice, and watch the agent emit Unified English Braille (UEB) to a frontend display, an export file, or a connected embosser.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [How It Works](#how-it-works)
  - [Conversation State Machine](#conversation-state-machine)
  - [Translation Pipeline](#translation-pipeline)
  - [Voice Commands](#voice-commands)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Clone the repo](#1-clone-the-repo)
  - [2. Install system dependencies](#2-install-system-dependencies)
  - [3. Python backend / agent](#3-python-backend--agent)
  - [4. Frontend (React + Vite)](#4-frontend-react--vite)
  - [5. Supabase database](#5-supabase-database)
  - [6. Environment variables](#6-environment-variables)
- [Running the Stack](#running-the-stack)
- [Testing](#testing)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Features

- **Wake-word activation** — say `"Hi Sparky"` (or `"Hey Sparky"`, `"Okay Sparky"`, `"Sparky"`) to wake the agent. Say `"stop"` or `"go to sleep"` to send it back to idle.
- **Real-time speech-to-text** via [AssemblyAI Universal-Streaming](https://www.assemblyai.com/) through LiveKit's `inference.STT` plugin.
- **Natural conversational confirmation loop** — the agent repeats what it heard and waits for `yes`/`no`. If you say "no", it asks what was wrong, uses GPT-4o-mini to apply the correction, and re-confirms.
- **Speech accumulation** — keep talking across multiple utterances; Sparky asks "Is that all, or would you like to continue speaking?" before locking the text in.
- **High-quality Braille translation** using [liblouis](https://liblouis.io/) with full UEB (Unified English Braille) tables:
  - **Grade 1** (uncontracted) — default
  - **Grade 2** (contracted) — toggle via voice or UI
- **Text normalization layer** — strips filler words (`um`, `like`, `you know`), expands spoken punctuation (`"comma"` → `,`), expands contractions, and collapses whitespace before liblouis sees the text.
- **Round-trip confidence scoring** — back-translates the Braille and compares to the input for a quality signal.
- **Voice export commands** — say `"save"`, `"export"`, or `"export as txt"` to write `.brl`/`.txt` files and persist them to Supabase.
- **Persistent history** in Supabase with sessions, conversions, exports, and per-user preferences.
- **REST API** (FastAPI) exposing token minting, conversion history, sessions, stats, prefs, and direct translation for non-voice clients.
- **React + Vite frontend** with live waveform, agent-state indicator, scrolling transcript, Braille display, history dashboard, and grade toggle.
- **Graceful liblouis fallback** — if liblouis isn't installed, a built-in ASCII-Braille map keeps the pipeline running for development.
- **Cross-process debug logging** to `/tmp/sparky_debug.log` (essential when LiveKit forks worker processes).

---

## Architecture

```
                        ┌───────────────────────────┐
                        │  Browser (React + Vite)   │
                        │  pages: Dashboard, Live,  │
                        │  History, Settings        │
                        └────────────┬──────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │  HTTP /api/*       │  WebRTC (LiveKit)  │
                ▼                    │                    ▼
       ┌─────────────────┐           │           ┌────────────────────┐
       │  FastAPI server │           │           │  LiveKit Cloud /   │
       │   (server.py)   │           │           │  self-hosted SFU   │
       │  - /api/token   │           │           └─────────┬──────────┘
       │  - /api/translate│          │                     │
       │  - /api/conversions │       │                     │
       │  - /api/stats   │           │                     │
       └────────┬────────┘           │                     │
                │                    │                     │
                ▼                    │                     ▼
       ┌─────────────────┐           │           ┌────────────────────┐
       │   Supabase      │           │           │   Sparky Agent     │
       │   Postgres      │◄──────────┼───────────┤   (agent.py)       │
       │   users         │           │           │  AssemblyAI STT    │
       │   sessions      │           │           │  GPT-4.1-mini LLM  │
       │   conversions   │           │           │  Cartesia Sonic-3  │
       │   assets        │           │           │  Silero VAD        │
       └─────────────────┘           │           │  liblouis (UEB)    │
                                     │           └─────────┬──────────┘
                                     │                     │
                                     │                     │
                                     └─────────────────────┘
                          braille_output topic (RTC data channel)
```

The agent is a long-running Python process registered with the LiveKit Agents framework. When the frontend requests a token, the FastAPI server dispatches the agent (`agent_name="Sage-210"`) into the same room. Audio flows over WebRTC, STT/LLM/TTS are run by LiveKit's inference plugins, and the final Braille string is published on a `braille_output` data channel back to the browser.

---

## Repository Layout

```
.
├── agent.py                # Sparky LiveKit agent (state machine, pipeline glue, voice commands)
├── server.py               # FastAPI backend — tokens, REST API, direct translation
├── braille_translator.py   # liblouis wrapper + ASCII-Braille fallback
├── normalizer.py           # STT text normalizer (fillers, punctuation, contractions)
├── requirements.txt        # Python dependencies
├── db/
│   ├── client.py           # Async Supabase client (users/sessions/conversions/assets)
│   └── schema.sql          # Postgres schema — paste into Supabase SQL Editor
├── frontend/
│   ├── src/
│   │   ├── App.jsx         # React Router setup
│   │   ├── api/client.js   # Fetch wrapper for the FastAPI backend
│   │   ├── pages/          # Dashboard, LiveSession, History, Settings
│   │   └── components/     # AgentStatus, BrailleDisplay, WaveformViz, Sidebar, …
│   ├── package.json        # Vite + React 19 + LiveKit components
│   └── vite.config.js
└── tests/
    ├── test_translator.py     # liblouis + fallback unit tests
    ├── test_pipeline.py       # End-to-end pipeline → Supabase integration test
    └── test_feedback_loop.py  # Confirmation/correction FSM tests
```

---

## How It Works

### Conversation State Machine

The agent is a 6-state FSM driven by the STT `on_user_turn_completed` callback:

| State           | What it's doing                                                          | Exits on                                       |
| --------------- | ------------------------------------------------------------------------ | ---------------------------------------------- |
| `IDLE`          | Waiting silently for the wake phrase                                     | Wake word detected → `LISTENING`               |
| `LISTENING`     | Active; ready to capture speech and recognize voice commands             | Speech captured → `ACCUMULATING`               |
| `ACCUMULATING`  | Buffered some speech; asked "Is that all, or continue?"                  | `yes`/`done` → `CONFIRMING`; `no` → `LISTENING`|
| `CONFIRMING`    | Repeated full text back; waiting for `yes`/`no`                          | `yes` → run pipeline → `LISTENING`; `no` → `CORRECTING` |
| `CORRECTING`    | Asked "What was wrong?"; waiting for natural-language correction         | Correction applied via LLM → `CONFIRMING`      |
| `PROCESSING`    | Running normalizer + liblouis + emit                                     | Done → `LISTENING`                             |

A global `"stop"` / `"go to sleep"` always returns to `IDLE` from any state.

### Translation Pipeline

```
STT transcript
    │
    ▼
strip wake word
    │
    ▼
Normalizer.normalize()
    ├─ Unicode NFC
    ├─ Length guard (5000 char cap)
    ├─ Expand spoken punctuation ("comma" → ",")
    ├─ Expand contractions ("don't" → "do not")  — Grade 1 only
    ├─ Strip filler words (um, uh, like, you know, …)
    └─ Collapse whitespace
    │
    ▼
BrailleTranslator.translate()
    ├─ louis.translateString(["unicode.dis", "en-ueb-g{1|2}.ctb"], text)
    ├─ louis.backTranslateString(...) → confidence score
    └─ Fallback to ASCII-Braille map if liblouis import fails
    │
    ▼
Persist ConversionRecord
    │
    ├─ Append to in-memory history
    ├─ Publish to room data channel (topic="braille_output")
    └─ (on "save") write to Supabase conversions table
```

### Voice Commands

While in `LISTENING`, Sparky recognises the following commands (substring match, case-insensitive):

| You say                                     | Sparky does                                                |
| ------------------------------------------- | ---------------------------------------------------------- |
| `"hi sparky"` / `"hey sparky"` / `"sparky"` | Wake from `IDLE`                                           |
| `"stop"` / `"go to sleep"` / `"sleep"`      | Return to `IDLE` from any state                            |
| `"save"`                                    | Persist the last conversion to Supabase                    |
| `"export"` / `"export as brl"` / `"export as txt"` | Write `.brl` or `.txt` file under `./exports/` and mark exported in DB |
| `"show conversion"` / `"history"`           | Fetch and log the last 5 conversions from Supabase         |
| `"grade two"` / `"contracted braille"`      | Switch to UEB Grade 2 for subsequent translations          |
| `"grade one"` / `"uncontracted braille"`    | Switch back to UEB Grade 1                                 |
| `"yes"` / `"no"` (in `CONFIRMING`)          | Accept or reject the read-back                             |
| `"done"` / `"continue"` (in `ACCUMULATING`) | Finish accumulating, or keep talking                       |

---

## Prerequisites

- **macOS or Linux** (Windows works for Python with WSL; native Windows untested)
- **Python 3.11+**
- **Node.js 20+** and **npm**
- **liblouis** ≥ 3.26 (system library, see installation below)
- A **LiveKit Cloud** project (free tier works) or a self-hosted LiveKit server
- A **Supabase** project (free tier works)
- An **OpenAI API key** (for the correction LLM and the GPT-4.1-mini chat model used by LiveKit inference)
- An **AssemblyAI API key** (used by LiveKit's `inference.STT` plugin)
- A **Cartesia API key** (used by LiveKit's `inference.TTS` plugin)

> The three model-provider keys are configured at the **LiveKit Cloud → Inference** dashboard, not in this app's `.env` file. LiveKit proxies the calls. If you self-host, you'll need to set them as environment variables that the LiveKit server can see.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/Braille-Voice-Agent.git
cd Braille-Voice-Agent
```

### 2. Install system dependencies

**macOS (Homebrew):**

```bash
brew install liblouis node python@3.11
```

**Ubuntu / Debian:**

```bash
sudo apt-get update
sudo apt-get install -y liblouis-dev liblouis-bin python3.11 python3.11-venv nodejs npm
```

Verify liblouis is installed:

```bash
lou_translate --version
```

### 3. Python backend / agent

```bash
python3.11 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

The `louis` PyPI package binds against your system liblouis — if you upgrade liblouis later, re-run `pip install --force-reinstall louis`.

### 4. Frontend (React + Vite)

```bash
cd frontend
npm install
cd ..
```

### 5. Supabase database

1. Create a new Supabase project at <https://supabase.com/>.
2. From the project dashboard, open **SQL Editor**.
3. Paste the entire contents of `db/schema.sql` and click **Run**.
4. Copy your project URL and the **`service_role`** key from **Settings → API**.
   - The service role bypasses Row Level Security — only use it on the backend, never expose it to the frontend.

### 6. Environment variables

Copy `.env.example` to `.env.local` and fill in the values:

```bash
cp .env.example .env.local
```

`.env.local` (loaded by `agent.py`, `server.py`, and `db/client.py` via `python-dotenv`):

```dotenv
# ── LiveKit ─────────────────────────────────────────────
LIVEKIT_URL=wss://<your-project>.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxx
LIVEKIT_API_SECRET=secretxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── OpenAI (used by the correction-LLM in agent.py) ─────
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Supabase ────────────────────────────────────────────
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...

# Optional — stable UUID for the MVP single-user mode.
# Defaults to 00000000-0000-0000-0000-000000000001 if not set.
SUPABASE_DEFAULT_USER_ID=00000000-0000-0000-0000-000000000001
```

---

## Running the Stack

Open **three terminals** (or use `tmux` / a multiplexer):

### Terminal 1 — LiveKit agent

```bash
source venv/bin/activate
python agent.py dev
```

The `dev` subcommand (from `livekit.agents.cli`) starts the agent worker, connects to LiveKit, and waits for dispatches.

### Terminal 2 — FastAPI backend

```bash
source venv/bin/activate
uvicorn server:app --reload --port 8000
```

Health check: <http://localhost:8000/api/health>

### Terminal 3 — React frontend

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173>, click **Connect** on the Live Session page, allow microphone access, and say **"Hi Sparky"**.

---

## Testing

The test suite is split into three files:

```bash
source venv/bin/activate

# Unit tests for the liblouis wrapper (no external services needed)
python -m pytest tests/test_translator.py -v

# Conversation state-machine + confirmation/correction loop (mocked)
python -m pytest tests/test_feedback_loop.py -v

# Full pipeline → live Supabase round-trip (requires .env.local + schema applied)
python -m pytest tests/test_pipeline.py -v
```

Run everything:

```bash
python -m pytest tests/ -v
```

---

## API Reference

The FastAPI server (`server.py`) exposes the following endpoints. All return JSON.

| Method | Path                            | Purpose                                                                  |
| ------ | ------------------------------- | ------------------------------------------------------------------------ |
| `GET`  | `/api/health`                   | Liveness + translator availability check                                 |
| `GET`  | `/api/token?room=<name>`        | Mint a LiveKit participant token and dispatch the `Sage-210` agent       |
| `POST` | `/api/translate`                | Direct (non-voice) text → Braille translation. Body: `{text, grade}`     |
| `GET`  | `/api/conversions?limit=N`      | Last N conversions for the default user                                  |
| `GET`  | `/api/conversions/{id}`         | Fetch a single conversion by UUID                                        |
| `GET`  | `/api/sessions?limit=N`         | Last N sessions (newest first)                                           |
| `GET`  | `/api/stats`                    | Dashboard counters: totals, average confidence, Grade 1 vs 2 split       |
| `GET`  | `/api/user/prefs`               | Read user preferences JSON                                               |
| `PUT`  | `/api/user/prefs`               | Update preferences. Body: `{braille_grade?, language?, strip_fillers?}`  |

CORS is open to `http://localhost:5173` and `http://localhost:3000` out of the box — edit `server.py` for production deployments.

---

## Database Schema

The full schema lives in [`db/schema.sql`](./db/schema.sql) and creates four tables plus one helper view:

| Table              | Description                                                            |
| ------------------ | ---------------------------------------------------------------------- |
| `users`            | Per-user prefs (`braille_grade`, `language`, `strip_fillers`, …)       |
| `sessions`         | One row per wake-word → stop. `events JSONB` logs state transitions.   |
| `conversions`      | One row per speech-to-Braille event. Includes raw/normalized/Braille, confidence, grade, export flags. |
| `assets`           | Optional audio recordings (consent-gated)                              |
| `recent_conversions` (view) | `conversions` ordered newest-first, lightweight columns       |

Row Level Security is enabled on all tables. The agent connects with the `service_role` key, which bypasses RLS. When you wire real auth later, add `auth.uid() = user_id` policies.

---

## Troubleshooting

| Symptom                                                                 | Fix                                                                                                                                                                |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `WARNING: Using ASCII-Braille fallback (liblouis not installed)`        | Install the system library (`brew install liblouis` or `apt install liblouis-dev`) and re-run `pip install --force-reinstall louis`.                               |
| `LiveKit API credentials not configured` from `/api/token`              | Make sure `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` are set in `.env.local` (loaded by `server.py` on startup).                                   |
| Agent connects to the room but never responds                           | Confirm `python agent.py dev` is running in another terminal and that the LiveKit project is the same one in both `.env.local` and the agent's environment.        |
| Microphone permission denied in the browser                             | Use `http://localhost:5173` (not `127.0.0.1`) or run behind HTTPS; Chrome blocks `getUserMedia` on insecure origins for non-localhost hosts.                       |
| `TTS crashes when reading Braille`                                      | Already handled — the agent never sends raw Braille strings to TTS, only short status messages like "Translation complete." The Braille goes over the data channel.|
| `EnvironmentError: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set` | The DB client expects both in `.env.local`. They are read at import time.                                                                                          |
| `gh: command not found` when pushing                                    | Install the GitHub CLI (`brew install gh`) or push manually with `git push -u origin main`.                                                                        |
| Debug logs missing from main stdout                                     | The agent forks workers; full logs are duplicated to `/tmp/sparky_debug.log`. `tail -f /tmp/sparky_debug.log` for the unified view.                                |

---

## Roadmap

- [x] Wake-word activation and FSM
- [x] STT → normalizer → liblouis → Braille pipeline
- [x] Confirmation / correction loop with GPT-assisted edits
- [x] Supabase persistence (sessions, conversions, exports)
- [x] FastAPI REST backend
- [x] React frontend with live waveform and transcript
- [ ] Real Supabase Auth (replace the hard-coded `DEFAULT_USER_ID`)
- [ ] WebSocket streaming of progressive Braille (per-word) to the frontend
- [ ] Direct USB / Bluetooth printing to popular Braille embossers
- [ ] Audio recording uploads to Supabase Storage (consent-gated)
- [ ] Multilingual UEB tables (es, fr, de, …)
- [ ] On-device, offline STT option (Whisper.cpp)

---

## Contributing

Issues and pull requests are welcome. Please:

1. Open an issue describing the change before working on a large feature.
2. Run `pytest tests/` and ensure all tests pass.
3. Match the existing code style — no `black`/`prettier` configured yet; just keep it readable.

---

## License

To be determined. Until a license is added, all rights are reserved by the authors. If you want to use this in your own project, please open an issue.

---

## Acknowledgements

- [**LiveKit**](https://livekit.io/) — real-time WebRTC infra and the Agents SDK
- [**liblouis**](https://liblouis.io/) — the world's most complete open-source Braille translation library
- [**AssemblyAI**](https://www.assemblyai.com/) — streaming STT
- [**Cartesia**](https://cartesia.ai/) — Sonic-3 TTS voices
- [**OpenAI**](https://openai.com/) — GPT-4.1-mini & GPT-4o-mini
- [**Supabase**](https://supabase.com/) — Postgres + storage
- The **Unified English Braille** standard maintained by [ICEB](http://www.iceb.org/ueb.html)
