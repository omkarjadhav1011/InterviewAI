<div align="center">
  <h1>AI Interview Prep System</h1>
  <p><strong>An AI-powered mock interview platform that parses your resume, asks personalized voice-driven questions, and grades your answers across confidence, technical depth, and communication.</strong></p>

  ![Python](https://img.shields.io/badge/python-3.10%2B-blue)
  ![Flask](https://img.shields.io/badge/flask-2.x-black)
  ![MongoDB](https://img.shields.io/badge/database-MongoDB-green)
  ![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange)
  ![License](https://img.shields.io/badge/license-MIT-blue)

  [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Configuration](#-configuration) • [API Reference](#-api-reference) • [DOCS.md](./DOCS.md)
</div>

---

## Overview

The AI Interview Prep System turns a candidate's PDF resume into a personalized, voice-first mock interview. It extracts skills, generates beginner-friendly questions tailored to seniority and role using Google Gemini, streams the candidate's spoken answer in real time via AssemblyAI, evaluates each answer on three independent dimensions, and stores a complete interview run for later review.

It is built as a Flask web application with vanilla JS on the frontend and degrades gracefully whenever any external AI service is unavailable.

---

## Features

- **Resume parsing** — PDF text extraction (PyMuPDF) with section-weighted skill scoring across 80+ skills and a rich alias map.
- **Adaptive question generation** — Gemini 2.5 Flash produces 5 question types (concept, practical, problem-solving, behavioural, curiosity) personalized to the candidate's profile; the next question is regenerated mid-interview based on what the candidate just said.
- **Real-time voice transcription** — Browser streams PCM16 audio over WebSocket to AssemblyAI v3 Universal-Streaming using a short-lived token from the server.
- **Hybrid answer capture** — Voice transcript and typed text are merged with deduplication so candidates can speak, type, or both.
- **Three-dimension scoring** — Each answer is scored 0–100 on confidence, technical correctness, and communication, then mapped to an overall 1–10 score.
- **Full-interview evaluation** — A second Gemini call produces a strict per-question review, skill summary, hire recommendation, and improvement plan stored in MongoDB.
- **Graceful fallbacks** — Every AI service has a heuristic fallback (skill-based question templates, deterministic answer scoring) so missing API keys never crash the app.
- **Persistent results** — Profile, sessions, and interview runs are stored in MongoDB and surfaced via a JSON API.

---

## Architecture

```
                  ┌─────────────────────┐
                  │   Browser (JS/HTML) │
                  │   interview.js      │
                  │   resume.js         │
                  └──────────┬──────────┘
                             │  HTTPS / WS
            ┌────────────────┼────────────────┐
            │                │                │
   ┌────────▼──────┐  ┌──────▼──────┐  ┌──────▼─────────┐
   │  Flask App    │  │  AssemblyAI │  │   VAPI (TTS/   │
   │  (run.py /    │  │  WebSocket  │  │   batch STT)   │
   │   wsgi.py)    │  │  Streaming  │  └────────────────┘
   └────────┬──────┘  └─────────────┘
            │
   ┌────────┴─────────────────────────────────┐
   │                                          │
┌──▼────────────┐  ┌────────────┐  ┌──────────▼────────┐
│ Resume Parser │  │   Gemini   │  │     MongoDB       │
│ (PyMuPDF +    │  │  2.5 Flash │  │ users / resumes / │
│ skill scorer) │  │  (genai)   │  │ interview_runs    │
└───────────────┘  └────────────┘  └───────────────────┘
```

Request flow during an interview:

```
upload PDF ─► parse skills ─► Gemini generates 5 questions ─► session
   │
   ▼
for each question:
   • TTS reads question (VAPI or browser fallback)
   • mic stream → AssemblyAI WS → transcript
   • POST /api/evaluate {question, answer, typed_answer}
   • Gemini scores answer  ◄── on the last question, full eval runs
                                and the run is persisted
```

---

## Tech Stack

| Layer        | Technology                              | Purpose                                    |
|--------------|-----------------------------------------|--------------------------------------------|
| Backend      | Flask 2.x, Flask-Login, Gunicorn        | App framework, auth, prod WSGI server      |
| Database     | MongoDB (PyMongo)                       | Users, resumes, interview runs             |
| AI           | Google Gemini 2.5 Flash (with fallbacks)| Question generation, answer evaluation     |
| Realtime STT | AssemblyAI v3 Universal-Streaming       | Live voice → text over WebSocket           |
| Batch STT/TTS| VAPI                                    | File-based transcription, voice synthesis  |
| Resume       | PyMuPDF (fitz)                          | PDF text extraction                        |
| Auth         | bcrypt                                  | Password hashing                           |
| Frontend     | Vanilla JS, Jinja2, Tailwind, Chart.js  | UI, charts, forms                          |

---

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB (local install **or** MongoDB Atlas connection string)
- API keys (all optional — the app falls back gracefully):
  - `GEMINI_API_KEY` — Google AI Studio
  - `ASSEMBLYAI_API_KEY` — AssemblyAI
  - `VAPI_API_KEY` — VAPI

### Installation

```bash
# Clone
git clone <your-repo-url>
cd project

# Create and activate venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Or on macOS / Linux
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# edit .env and fill in your keys
```

### Running Locally

```bash
# Development server (port 5000)
python run.py

# Production
gunicorn wsgi:app
```

Open http://localhost:5000, register an account, upload a PDF resume, and start the mock interview.

---

## Configuration

All settings are read from environment variables (loaded via `python-dotenv`).

| Variable              | Required | Default                                           | Description                                                                  |
|-----------------------|----------|---------------------------------------------------|------------------------------------------------------------------------------|
| `MONGO_URI`           | ✅       | `mongodb://localhost:27017/interview_app`         | MongoDB connection string. DB name is parsed from the path.                  |
| `SECRET_KEY`          | prod     | random in dev                                     | Flask session secret. **Required** when `FLASK_ENV=production`.              |
| `GEMINI_API_KEY`      | ❌       | —                                                 | Google Generative AI key. Without it, heuristic fallback is used.            |
| `GEMINI_MODEL_NAME`   | ❌       | `models/gemini-2.5-flash`                         | Override default Gemini model. Falls back through a candidate list.          |
| `ASSEMBLYAI_API_KEY`  | ❌       | —                                                 | Enables real-time voice transcription.                                       |
| `VAPI_API_KEY`        | ❌       | —                                                 | Enables batch STT and (with `VAPI_VOICE_ID`) TTS.                            |
| `VAPI_VOICE_ID`       | ❌       | —                                                 | Voice ID for TTS. Leave blank to use the browser's built-in `SpeechSynthesis`.|
| `VAPI_VOICE_PROVIDER` | ❌       | `11labs`                                          | TTS provider used by VAPI.                                                   |
| `FLASK_ENV`           | ❌       | —                                                 | Set to `production` to enforce `SECRET_KEY` and disable debug.               |
| `FLASK_DEBUG`         | ❌       | `false`                                           | When `true`, `python run.py` runs Flask with debug=True.                     |

Internal tuning (in `config.py`, edit if needed):

| Constant                  | Default | Effect                                       |
|---------------------------|---------|----------------------------------------------|
| `MAX_CONTENT_LENGTH`      | 16 MB   | Hard cap on any upload                       |
| `MAX_RESUME_SIZE_BYTES`   | 5 MB    | Soft cap enforced inside the resume route    |
| `MAX_RESUME_PAGES`        | 10      | Cap on PDF pages parsed                      |
| `GEMINI_TIMEOUT`          | 15 s    | Per-call timeout for Gemini                  |
| `ASSEMBLYAI_TOKEN_TTL`    | 55 s    | TTL reported back to clients on the token API|

---

## Project Structure

```
project/
├── app/
│   ├── __init__.py            # create_app(): blueprints, error handlers, login loader
│   ├── extensions.py          # Shared MongoDB client (init_db / get_db)
│   ├── routes/
│   │   ├── auth.py            # /register /login /logout /profile /settings
│   │   ├── resume.py          # / (home) /upload — PDF parse + question gen
│   │   ├── interview.py       # /interview /api/get_question /api/evaluate /api/tts
│   │   ├── transcription.py   # /start_transcription /api/transcription/token
│   │   ├── results_api.py     # /api/results /api/interview/start /api/interview/complete
│   │   └── profile_api.py     # /api/resume/profile /api/interview/history
│   ├── services/
│   │   ├── gemini_service.py  # Question gen, eval, full-interview eval, fallbacks
│   │   ├── resume_parser.py   # PDF text extraction + skill scoring
│   │   ├── transcription_service.py  # AssemblyAI v3 token mint
│   │   └── vapi_service.py    # VAPI batch STT/TTS
│   ├── utils/
│   │   ├── gemini_runtime.py  # Timeout-wrapped Gemini call + JSON parser
│   │   ├── responses.py       # ok() / err() JSON helpers
│   │   └── secrets_filter.py  # Logging filter that redacts secrets
│   ├── templates/             # Jinja2 templates (base + per-page)
│   └── static/                # CSS, JS, uploads
├── tools/                     # Ad-hoc smoke-test scripts (no pytest)
├── config.py                  # BaseConfig / Development / Production / Testing
├── run.py                     # Dev entry point
├── wsgi.py                    # Gunicorn entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## API Reference

> All `/api/*` endpoints require an authenticated session (Flask-Login). Errors use `{"status": "error", "error": "..."}` shape.

### Auth

| Method | Path        | Notes                                          |
|--------|-------------|------------------------------------------------|
| POST   | `/register` | Form: `username`, `email`, `password` (≥ 8 ch) |
| POST   | `/login`    | Form: `email`, `password`                      |
| GET    | `/logout`   | Logout and redirect                            |

### Resume & Interview

| Method | Path                                | Description                                                                 |
|--------|-------------------------------------|-----------------------------------------------------------------------------|
| GET    | `/`                                 | Home — recent interview cards                                               |
| POST   | `/upload`                           | Upload PDF resume → `{skills, questions, name, summary, ...}`               |
| GET    | `/interview`                        | Interview UI                                                                 |
| GET    | `/get_questions?question=N`         | Returns the Nth question, total, progress, and `isLastQuestion`             |
| GET    | `/api/get_question`                 | Generates a fresh batch of 7 questions from the candidate profile           |
| POST   | `/api/tts`                          | `{text}` → `{audio_url, fallback}` (`fallback=true` ⇒ use browser TTS)     |
| POST   | `/api/stt`                          | multipart `audio` file → `{transcript}`                                      |
| POST   | `/api/evaluate`                     | `{question, answer, typed_answer, questionNumber}` → per-dimension scores  |
| GET    | `/results`                          | HTML results page                                                            |

### Realtime Transcription

| Method | Path                              | Description                                                  |
|--------|-----------------------------------|--------------------------------------------------------------|
| POST   | `/start_transcription`            | Returns `{ws_url}` for AssemblyAI v3 streaming WebSocket     |
| GET    | `/api/transcription/token`        | Returns `{token, ws_url, expires_in}`                        |
| POST   | `/stop_transcription`             | Returns the accumulated transcript and clears it             |
| POST   | `/update_transcript`              | `{text}` — append a chunk to the session transcript          |

### JSON Surfaces

| Method | Path                              | Description                                              |
|--------|-----------------------------------|----------------------------------------------------------|
| GET    | `/api/results`                    | Latest interview run, flattened                          |
| POST   | `/api/interview/start`            | Returns the session-stashed questions                    |
| POST   | `/api/interview/complete`         | Confirms the most recent run was persisted               |
| GET    | `/api/resume/profile`             | Latest parsed resume profile for the user                |
| GET    | `/api/interview/history`          | Last 5 interview runs (overall score + recommendation)   |
| GET    | `/api/resume/questions/status`    | `ready` / `not_started` plus session questions           |

### Health

| Method | Path     | Description                          |
|--------|----------|--------------------------------------|
| GET    | `/health`| `{status, db}` — pings MongoDB       |

---

## Score Computation

Per-question:
- Gemini returns `confidence`, `technical`, `communication` (each 0–100).
- The route maps these to an `overall_score` on a 1–10 scale.
  - average ≥ 75 → floor at 8.0
  - average 45–74 → floor at 5.0
  - ≤ 2 words → 2.0; empty → 1.0

Final aggregate (`compute_final_scores`):
- Weighted 0–100: `technical*0.5 + confidence*0.25 + communication*0.25`
- ≥ 80 → `strong_yes`, ≥ 65 → `yes`, ≥ 45 → `maybe`, else `no`.

---

## Testing

There is **no pytest suite**. The `tools/` directory has ad-hoc smoke-test scripts:

```bash
python tools/test_transcription.py          # TTS→STT round-trip (70% word-match threshold)
python tools/test_transcription_service.py  # AssemblyAI token mint
python tools/test_transcription_config.py   # Sanity-check env vars
python tools/simulate_upload.py             # End-to-end resume parse + question gen
```

---

## Deployment

### Gunicorn (single host)

```bash
pip install -r requirements.txt
export FLASK_ENV=production
export SECRET_KEY=<long-random-string>
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

### Docker (illustrative — no Dockerfile is currently checked in)

> 📝 Assumption: a Dockerfile would copy the source, install `requirements.txt`, and run `gunicorn wsgi:app` on port 8000. Add one to ship.

### MongoDB

Use a managed Atlas cluster or self-host. The first request creates indexes on `users.email` (unique), `resumes.user_email` (unique), and `interview_runs(user_email, created_at)`.

---

## Security Notes

- Passwords are hashed with bcrypt; never stored in plaintext.
- Sessions are signed with `SECRET_KEY` — required in production.
- `RedactSecretsFilter` (in `app/utils/secrets_filter.py`) redacts API keys from log output.
- Resume uploads are limited to PDF, ≤ 5 MB, ≤ 10 pages, with a 16 MB Flask-level hard cap.
- All AI service calls have explicit timeouts to avoid request stalling.

---

## Contributing

1. Fork the repo
2. `git checkout -b feat/your-change`
3. Commit with conventional-commit style (the repo already follows `feat:` / `refactor:` / `fix:` prefixes)
4. Open a PR

---

## License

MIT — see `LICENSE` if present, or treat as MIT by default.

---

## Acknowledgements

- Google Gemini for question generation and evaluation
- AssemblyAI for v3 Universal-Streaming
- VAPI for batch speech services
- PyMuPDF for fast, robust PDF parsing
- Flask + the wider Python ecosystem
