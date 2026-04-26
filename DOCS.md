# AI Interview Prep System — Technical Documentation

Companion to [`README.md`](./README.md). The README is the marketing-shaped surface; this document is the engineering reference.

## Table of Contents

1. [Introduction & Goals](#1-introduction--goals)
2. [System Architecture](#2-system-architecture)
3. [Codebase Walkthrough](#3-codebase-walkthrough)
4. [Data Models & Schema](#4-data-models--schema)
5. [API Reference (full)](#5-api-reference-full)
6. [Environment & Configuration](#6-environment--configuration)
7. [Development Workflow](#7-development-workflow)
8. [Testing Strategy](#8-testing-strategy)
9. [Deployment & Infrastructure](#9-deployment--infrastructure)
10. [Error Handling & Logging](#10-error-handling--logging)
11. [Security Considerations](#11-security-considerations)
12. [Performance Notes](#12-performance-notes)
13. [Known Limitations & Future Work](#13-known-limitations--future-work)
14. [Glossary](#14-glossary)
15. [Changelog](#15-changelog)

---

## 1. Introduction & Goals

### Problem
Interview prep tools tend to be either generic flashcard systems or expensive human services. Candidates need a low-friction way to practice answering personalized questions out loud and receive structured, actionable feedback — without depending on a human reviewer.

### Solution
A Flask web app that:
1. Parses a candidate's PDF resume to extract a structured profile (skills, titles, years, education).
2. Generates beginner-friendly, personalized questions via Gemini.
3. Captures spoken answers in real time via AssemblyAI WebSocket streaming.
4. Scores each answer along three independent axes and a strict full-interview review.
5. Persists the run for review and longitudinal trend tracking.

### Design Decisions

| Decision | Rationale |
|---|---|
| **Session-first state** | Most interview state (`interview_questions`, `skills`, `interview_results`) lives in the Flask session and is only persisted to MongoDB when the run completes. Keeps reads cheap and avoids partial-state DB churn. |
| **Graceful degradation per service** | Any of Gemini, VAPI, or AssemblyAI may be unconfigured — the app degrades to heuristic fallbacks (skill-template questions, deterministic scorer, browser TTS, typed-only answers) rather than crashing. |
| **Two transcription paths** | VAPI handles batch file → text; AssemblyAI handles real-time streaming. The browser drives the streaming socket directly using a short-lived server-minted token (no audio passes through Flask). |
| **Adaptive next question** | After each answer is evaluated, the next pre-generated question is rewritten by Gemini to follow up on what the candidate just said. Pre-generation is the safety net; adaptation is the upgrade. |
| **Three-dimension scoring** | Confidence, technical, communication are scored independently to give targeted feedback rather than one opaque overall number. |
| **Bcrypt + Flask-Login** | Standard, audited primitives; nothing custom built. |

### Out of Scope (Explicit Non-Goals)
- Real-time multi-party interviews (no WebRTC).
- Video/visual analysis.
- Recruiter-side dashboards or job-posting workflows.
- A pytest test suite (currently only ad-hoc smoke tests in `tools/`).

---

## 2. System Architecture

### Component Diagram

```
                        ┌────────────────────────┐
                        │      Browser (UI)      │
                        │  Jinja2 + vanilla JS   │
                        │  static/js/interview.js│
                        └──────────┬─────────────┘
                                   │
                       ┌───────────┼─────────────────────────┐
                       │           │                         │
                  HTTP/HTTPS    WebSocket              HTTP (TTS audio URL)
                       │           │                         │
                       ▼           ▼                         ▼
            ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐
            │   Flask App      │  │   AssemblyAI     │  │    VAPI     │
            │ (run.py/wsgi.py) │  │ v3 Streaming WS  │  │ (batch STT/ │
            └─────────┬────────┘  └──────────────────┘  │   TTS)      │
                      │                                  └─────────────┘
       ┌──────────────┼──────────────┬──────────────────────┐
       │              │              │                      │
       ▼              ▼              ▼                      ▼
┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌─────────────────────┐
│ resume_    │ │  gemini_   │ │ transcription│ │      MongoDB        │
│ parser     │ │  service   │ │   _service   │ │ users / resumes /   │
│ (PyMuPDF)  │ │ (genai +   │ │ (token mint) │ │ interview_runs      │
│            │ │ fallbacks) │ │              │ │                     │
└────────────┘ └────────────┘ └──────────────┘ └─────────────────────┘
```

### Data Flow — End-to-End Interview

1. **Login** → `routes/auth.py` issues a Flask-Login session.
2. **Upload PDF** → `POST /upload` (`routes/resume.py`)
   - PyMuPDF extracts text (`extract_text_from_pdf_bytes`, capped to 10 pages, 5 MB, 20 s).
   - `extract_structured_profile` builds the candidate profile (Gemini-assisted, deterministic fallback).
   - `parse_resume_to_skills_from_text` scores skills by section weight (Skills 3×, Experience/Projects 1.5×, full text 1×) plus context-pattern bonuses.
   - Profile + skills stored on the user, in the `resumes` collection (upsert), and in the session.
   - 5 questions are generated and stashed in `session['interview_questions']`.
3. **Interview UI** → `GET /interview` renders `interview.html`.
4. **Per question:**
   - Client calls `GET /get_questions?question=N` and `POST /api/tts` for the audio.
   - Client opens the AssemblyAI WebSocket using the URL/token from `POST /start_transcription` and streams 16-bit PCM mono frames at 16 kHz.
   - On submit, client calls `POST /api/evaluate` with the voice transcript and any typed input.
   - `combine_answers` merges the two strings (substring dedupe, overlap dedupe, else concatenation prefixed by the typed text).
   - Gemini evaluates → 3-dim scores → `_compute_overall_score` maps to 1–10.
   - If not the last question, `regenerate_next_question` rewrites slot N+1 to follow up on the candidate's last answer.
5. **Last question:** the route runs `evaluate_full_interview` and `compute_final_scores`, then writes a single `interview_runs` document and clears the session results.
6. **Results** → `GET /results` (`routes/interview.py`) reads the latest run from MongoDB and renders `result.html`.

### External Dependencies

| Dependency | Purpose | Why chosen |
|---|---|---|
| Google Gemini 2.5 Flash | Question gen + answer eval | Cost-efficient, separate free-tier quota; cascades through 2.5 → 2.0 candidates |
| AssemblyAI v3 Universal-Streaming | Real-time STT | Stable PCM16 streaming, simple token mint, low latency |
| VAPI | Batch STT + TTS | One vendor for both directions; TTS is optional (browser fallback exists) |
| MongoDB | Document store | Schemaless run docs map cleanly to per-question + summary blobs |
| PyMuPDF (`fitz`) | PDF text extraction | Pure-C implementation, fast, robust on real-world resumes |

---

## 3. Codebase Walkthrough

### Top-level Layout

```
project/
├── app/                  ← Flask application package
├── tools/                ← Ad-hoc smoke-test scripts
├── config.py             ← Configuration classes
├── run.py                ← `python run.py` dev entry
├── wsgi.py               ← `gunicorn wsgi:app` entry
├── requirements.txt
└── .env.example
```

### `app/__init__.py` — Application Factory

`create_app()` is the single entry point. It:
- Loads `.env` via `python-dotenv`.
- Configures root logger and attaches `RedactSecretsFilter`.
- Validates `SECRET_KEY` (random in dev, **required** in production).
- Imports `BaseConfig`, sets `UPLOAD_FOLDER` and `MAX_CONTENT_LENGTH=16 MB`.
- Calls `init_db(app)` to create the shared `MongoClient`.
- Initializes Flask-Login with `login_view='auth.login'`.
- Logs warnings for missing `GEMINI_API_KEY` / `VAPI_API_KEY` / `ASSEMBLYAI_API_KEY`.
- Registers six blueprints: `auth`, `resume`, `interview`, `transcription`, `results_api`, `profile_api`.
- Defines a `/health` route that pings MongoDB.
- Installs JSON-aware error handlers for 400/404/405/413/500 (HTML or JSON, decided by `_is_api(req)`).
- Wires the Flask-Login `user_loader` to read users by ObjectId.

### `app/extensions.py` — DB Singleton

A module-level `_client` and `_db`. `init_db(app)`:
- Reads `MONGO_URI` (default `mongodb://localhost:27017/interview_app`).
- Parses the database name from the URI path; falls back to `interview_app`.
- Creates indexes on `users.email`, `resumes.user_email`, and `interview_runs(user_email, created_at)`.

### `app/routes/`

| File | Routes | Highlights |
|---|---|---|
| `auth.py` | `/register`, `/login`, `/logout`, `/profile`, `/settings` | bcrypt hash; basic email regex; aggregates avg/best score on `/profile`. |
| `resume.py` | `/`, `/upload` | PDF-only, `MAX_RESUME_SIZE_BYTES`, `MAX_RESUME_PAGES`. Stores both legacy `users.skills` and a richer `resumes` doc. Emits `interview_seed`. |
| `interview.py` | `/interview`, `/get_questions`, `/api/get_question`, `/api/tts`, `/api/stt`, `/api/evaluate`, `/results` | Hosts `combine_answers`, `_compute_overall_score`, last-question persistence, and adaptive `regenerate_next_question` call. |
| `transcription.py` | `/start_transcription`, `/api/transcription/token`, `/stop_transcription`, `/update_transcript` | Mints AssemblyAI tokens, accumulates transcript text in `session['live_transcript']`. |
| `results_api.py` | `/api/results`, `/api/interview/start`, `/api/interview/complete` | Read-shaped JSON for the latest run; back-compat for older docs without `final_scores`. |
| `profile_api.py` | `/api/resume/profile`, `/api/interview/history`, `/api/resume/questions/status` | Read-only candidate-side surfaces. |

### `app/services/`

#### `gemini_service.py`

Public functions:
- `generate_questions(skills, count, profile, previous_qa, session_seed)` — main question generator; returns plain strings.
- `regenerate_next_question(profile, skills, previous_qa, next_index, total_questions, fallback_question)` — adaptive rewrite mid-interview.
- `evaluate_answer(question, answer, skills)` — single-call 3-dim evaluation.
- `evaluate_full_interview(skills, questions, answers)` — batch end-of-run evaluation with strict scoring.
- `compute_final_scores(per_question_results, full_evaluation)` — pure-Python aggregator producing the `final_scores` block.

Internals:
- `_MODEL_CANDIDATES` cascade: 2.5-flash → 2.5-flash-lite → 2.0-flash → 2.0-flash-lite. `_get_model()` probes each with a 4-token call until one responds.
- `_model_blacklist` permanently drops models that 403/404; transient errors clear the cache for the next request.
- `_QUESTION_TEMPLATES_BY_TYPE` powers the deterministic fallback generator; `_QUESTION_TYPE_ORDER` defines the slot arc (concept → practical → problem-solving → behavioural → curiosity).
- `_normalize_profile` coerces a noisy profile dict into a canonical shape (lists of strings, int years, derived seniority).
- All Gemini calls run through `call_gemini_with_timeout` and `parse_json_response` from `utils/gemini_runtime.py`.

#### `resume_parser.py`

- `extract_text_from_pdf_bytes(file_bytes, max_pages, timeout_seconds)` — runs PyMuPDF on a thread with a wall-clock timeout.
- `parse_resume_to_skills_from_text(text)` — section-weighted scoring across `SKILLS_DB` (80+ entries) plus `SKILL_ALIASES` for variants (e.g. `k8s → kubernetes`, `nodejs → node`).
- `extract_structured_profile(text)` — Gemini-backed structured extraction for name, summary, years, titles, education; falls through to a deterministic scorer.
- Ambiguous tokens like `c`, `r`, `go` are suppressed unless they appear inside a named section.

#### `transcription_service.py`

`get_ws_url()` POSTs to `https://streaming.assemblyai.com/v3/token?expires_in_seconds=600` with the API key and returns `{ws_url}` shaped as `wss://streaming.assemblyai.com/v3/ws?sample_rate=16000&token=...&encoding=pcm_s16le&format_turns=true`.

#### `vapi_service.py`

- `stt_transcribe(audio_file)` — POSTs WAV bytes to `https://api.vapi.ai/speech-to-text`; returns transcript or `None`.
- `tts_synthesize(text)` — POSTs JSON to `https://api.vapi.ai/speech/generate`; returns the audio URL or `None`. Skips silently when `VAPI_VOICE_ID` is unset so the browser falls back to `SpeechSynthesisUtterance`.

### `app/utils/`

- `gemini_runtime.py` — `call_gemini_with_timeout(model, prompt, timeout)` (thread-based wall-clock cap) and `parse_json_response(raw)` (markdown-fence stripper + permissive JSON loader).
- `responses.py` — `ok(**kwargs)` and `err(message, code)` helpers.
- `secrets_filter.py` — `RedactSecretsFilter` for the root logger; redacts API keys from log records.

### `app/static/js/`

- `interview.js` — main client; drives Q&A, opens the AssemblyAI WS, streams PCM frames via `AudioWorklet`, runs the Whisper fallback when the WS is unavailable, and orchestrates TTS playback.
- `transcription.js` — standalone streaming module reused by `interview.js`.
- `whisper_transcription.js` — offline Whisper inference, lazy-loaded.
- `resume.js` — upload form, progress bar, skill chip rendering.
- `main.js` — `fetchJSON()` helper, nav highlight, animations.

### `app/templates/`

- `base.html` — Tailwind, Chart.js, Font Awesome, navbar.
- `home.html`, `upload.html`, `interview.html`, `result.html`, `profile.html`, `settings.html`, `login.html`, `register.html` — per-page templates inheriting from `base.html`.

---

## 4. Data Models & Schema

### `users`

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | Primary key |
| `username` | string | ≤ 80 chars |
| `email` | string | unique index, lowercased |
| `password` | bytes | bcrypt hash (`bcrypt.hashpw`) |
| `skills` | string[] | Latest extracted skills (legacy field) |
| `results` | array | Legacy embedded results (kept for back-compat) |
| `created_at` | datetime | Optional; surfaced as "Member since" on `/profile` |

**Indexes:** `{email: 1}` unique.

### `resumes`

| Field | Type | Notes |
|---|---|---|
| `user_email` | string | Unique index — one document per user |
| `filename` | string | Original (secure) filename of the upload |
| `parsed_at` | datetime (UTC) | Set on each successful upload |
| `skills` | string[] | Canonical skill list |
| `name` | string \| null | Extracted candidate name |
| `summary` | string | Short summary (≤ ~400 chars used in prompts) |
| `experience_years` | int \| null | Inferred years of experience |
| `job_titles` | string[] | Up to 5 used in prompt block |
| `education` | string[] | Up to 3 used in prompt block |

**Indexes:** `{user_email: 1}` unique.

### `interview_runs`

| Field | Type | Notes |
|---|---|---|
| `user_email` | string | Owner |
| `created_at` | datetime (UTC) | `datetime.utcnow()` at end of interview |
| `skills` | string[] | Snapshot used for the run |
| `questions` | string[] | Final question list (post adaptive regen) |
| `results` | array<PerQuestionResult> | One entry per question |
| `full_evaluation` | object | Output of `evaluate_full_interview` |
| `final_scores` | object | Output of `compute_final_scores` |
| `completed` | bool | Always `true` for runs written by the route |
| `summary.total_questions` | int | Count of `results` |
| `duration_seconds` | int \| absent | Set when client provides it |

`PerQuestionResult` shape:
```json
{
  "question": "...",
  "answer": "<combined>",
  "transcript": "<voice>",
  "typed": "<typed>",
  "final": "<combined>",
  "result": {
    "confidence": 0-100,
    "technical": 0-100,
    "communication": 0-100,
    "summary": "...",
    "feedback": "...",
    "strengths": ["..."],
    "areas_to_improve": ["..."],
    "key_strength": "...",
    "key_gap": "...",
    "overall_score": 1.0-10.0
  },
  "overall_score": 1.0-10.0,
  "questionNumber": 0
}
```

`final_scores` shape:
```json
{
  "overall_score": 1.0-10.0,
  "confidence_avg": 0-100,
  "technical_avg": 0-100,
  "communication_avg": 0-100,
  "hire_recommendation": "strong_yes|yes|maybe|no",
  "overall_feedback": "...",
  "strengths": ["..."],
  "areas_for_improvement": ["..."],
  "capped_questions": [<int>]
}
```

`full_evaluation` shape:
```json
{
  "questions_review": [{"skill", "original_question", "issues", "improved_question", "difficulty"}],
  "answer_evaluation": [{"question", "answer_summary", "issues", "score": 0-100, "justification"}],
  "skill_summary": [{"skill", "average_score", "strength": "Strong|Medium|Weak", "insight"}],
  "overall_evaluation": {"final_score": 0-100, "verdict": "Strong Hire|Hire|Weak Hire|Reject", "summary": "..."}
}
```

**Indexes:** `{user_email: 1, created_at: -1}`.

---

## 5. API Reference (full)

> All `/api/*` routes require `@login_required`. Responses use `{"status": "ok"|"error", ...}`. Status codes follow Flask defaults (400/401/403/404/405/413/500/503).

### `POST /register`
Form: `username`, `email`, `password` (≥ 8 chars). Sets a flash message and redirects to `/login`.

### `POST /login`
Form: `email`, `password`. On success, redirects to `/`.

### `GET /logout`
Logs the user out; redirects to `/login`.

### `GET /` (home)
HTML — renders `home.html` with the user's most recent 20 runs, mapping `final_scores.hire_recommendation` to a verdict label.

### `POST /upload`
Multipart: `resume` (PDF). Returns:
```json
{
  "status": "ok",
  "skills": ["..."],
  "questions": ["..."],
  "next": "/interview",
  "name": "...",
  "summary": "...",
  "experience_years": 3,
  "job_titles": ["..."]
}
```
Errors: `400` (no file / not PDF / extraction failed), `413` (>5 MB), `500` (read error).

### `GET /interview`
HTML — interview UI.

### `GET /get_questions?question=N`
Returns the Nth question from the session and progress metadata. If the session is empty but the user has skills, generates 5 questions on the fly and stashes them.

```json
{
  "status": "ok",
  "currentQuestion": "string|null",
  "questionNumber": 0,
  "totalQuestions": 5,
  "progress": {"current": 1, "total": 5, "completed": 0.0},
  "skills": ["..."],
  "isLastQuestion": false
}
```

### `GET /api/get_question`
Generates a fresh batch of 7 questions from the candidate profile (does not stash them). Returns `{status, questions}`.

### `POST /api/tts`
JSON: `{"text": "..."}`. Returns `{"status": "ok", "audio_url": "https://..."|null, "fallback": true|false}`. When `fallback=true`, the client should use the browser's `SpeechSynthesisUtterance`.

### `POST /api/stt`
Multipart: `audio`. Returns `{"status": "ok", "transcript": "..."}` or `503` if VAPI fails.

### `POST /api/evaluate`
JSON:
```json
{
  "question": "...",
  "answer": "<voice transcript>",
  "typed_answer": "<typed input>",
  "questionNumber": 0
}
```
Returns:
```json
{
  "status": "ok",
  "result": { "confidence": 80, "technical": 70, "communication": 75, "summary": "...", "feedback": "...", "strengths": [...], "areas_to_improve": [...], "key_strength": "...", "key_gap": "...", "overall_score": 8.0 },
  "questionNumber": 0,
  "is_last_question": false,
  "combined_answer": "..."
}
```
On the last question, also returns `redirect: "/results"`. On Gemini timeout, returns `503`.

### `POST /start_transcription`
Returns `{"status": "started", "ws_url": "wss://..."}` or `503` on token-mint failure. Resets `session['live_transcript']`.

### `GET /api/transcription/token`
Returns `{"status": "ok", "token": "...", "ws_url": "wss://...", "expires_in": 55}`. Use this if the client wants to construct its own URL.

### `POST /stop_transcription`
Returns `{"status": "stopped", "transcript": "..."}` and clears the session transcript.

### `POST /update_transcript`
JSON: `{"text": "..."}`. Appends `text + " "` to `session['live_transcript']`. 400 if `text` is non-string or > 10,000 chars.

### `GET /results`
HTML — renders `result.html` from the latest `interview_runs` doc.

### `GET /api/results`
Flat read-shape of the latest run. Reconstructs aggregates for older docs that predate `final_scores`. 404 if no runs exist.

### `POST /api/interview/start`
Returns `{"status": "ok", "questions": [...], "session_id": "..."}`.

### `POST /api/interview/complete`
`{"status": "ok", "run_id": "..."}` if the latest run is `completed`, else `409`.

### `GET /api/resume/profile`
Returns the latest parsed resume (`skills`, `name`, `summary`, `experience_years`, `job_titles`, `education`, `filename`, `parsed_at`). 404 if none.

### `GET /api/interview/history`
Returns up to 5 recent runs (`run_id`, `created_at`, `overall_score`, `skills`, `hire_recommendation`).

### `GET /api/resume/questions/status`
Returns `{"status": "ok", "status": "ready"|"not_started", "questions": [...]}`.

### `GET /health`
`{"status": "ok"|"degraded", "db": true|false}` — 200 or 503.

---

## 6. Environment & Configuration

Loaded by `python-dotenv` at module import time.

| Variable | Required | Type | Default | Effect |
|---|---|---|---|---|
| `MONGO_URI` | ✅ | string | `mongodb://localhost:27017/interview_app` | Mongo connection. DB name parsed from path. |
| `SECRET_KEY` | prod only | string | random in dev | Flask session signer. Required when `FLASK_ENV=production`. |
| `FLASK_ENV` | ❌ | `development\|production` | — | Toggles debug logging and SECRET_KEY enforcement. |
| `FLASK_DEBUG` | ❌ | `true\|false` | `false` | Sets Flask's debug flag in `run.py`. |
| `GEMINI_API_KEY` | ❌ | string | — | Enables Gemini paths. Without it, fallbacks run. |
| `GEMINI_MODEL_NAME` | ❌ | string | `models/gemini-2.5-flash` | First model to try. Cascade fallback follows. |
| `ASSEMBLYAI_API_KEY` | ❌ | string | — | Enables real-time STT. Token mint fails 503 without it. |
| `VAPI_API_KEY` | ❌ | string | — | Enables batch STT and (with voice id) TTS. |
| `VAPI_VOICE_ID` | ❌ | string | — | Empty ⇒ skip TTS call, use browser `SpeechSynthesis`. |
| `VAPI_VOICE_PROVIDER` | ❌ | string | `11labs` | Provider passed to VAPI TTS payload. |

`config.py` constants (compiled into `BaseConfig` and surfaced via `current_app.config`):

```python
MAX_CONTENT_LENGTH       = 16 * 1024 * 1024  # Flask hard cap
REQUEST_TIMEOUT          = 10                # outbound HTTP
GEMINI_TIMEOUT           = 15                # per generate_content
MAX_RESUME_SIZE_BYTES    = 5 * 1024 * 1024
MAX_RESUME_PAGES         = 10
PDF_EXTRACTION_TIMEOUT   = 20
ASSEMBLYAI_TOKEN_TTL     = 55
```

Selection between `DevelopmentConfig` / `ProductionConfig` / `TestingConfig` is *implicit* — `create_app()` always loads `BaseConfig` and reads `FLASK_ENV` only for the `SECRET_KEY` requirement. The named subclasses exist for callers that opt in.

---

## 7. Development Workflow

### Local setup (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env  # then edit
python run.py
```

### Local setup (macOS / Linux)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit
python run.py
```

### Branching & Commits

The repo uses conventional-commit prefixes already: `feat`, `refactor`, `fix`, `docs`, `chore`. Recent log:

```
feat(resume): enhance home route to display latest interview results
feat(interview): enhance question generation with candidate profile and adaptive follow-up
feat(env): add VAPI voice configuration options
refactor(interview): restructure code for state management and improve UI feedback
feat(vapi): enhance TTS and STT services with improved error handling and fallback logic
```

Suggested branch shape: `feat/<short-name>`, `fix/<short-name>`. PRs should land on `main`.

### Code Style

- Python: follow PEP 8 informally; lots of type hints in `gemini_service.py` and `resume_parser.py`.
- Frontend: vanilla JS, ES2017+. No build step.
- No linters or formatters are configured at the repo root — adopt `ruff` / `black` if introducing CI.

---

## 8. Testing Strategy

The project has **no pytest suite**. Smoke testing is via scripts in `tools/`:

| Script | Purpose |
|---|---|
| `tools/test_transcription.py` | TTS → STT round-trip; passes if ≥ 70 % of the original words round-trip back |
| `tools/test_transcription_service.py` | Token mint + WS URL formatting |
| `tools/test_transcription_config.py` | Validates env vars are readable |
| `tools/simulate_upload.py` | End-to-end: parse resume → generate questions via Gemini |

Run from the repo root with the venv active:

```bash
python tools/test_transcription.py
```

`requirements-test.txt` exists for future pytest adoption but is not currently consumed by CI.

> 📝 Assumption: any new tests should live under `tests/` with `pytest` and be run via `pytest -q`. The codebase is structured to allow this (no global state outside `app/extensions.py`).

---

## 9. Deployment & Infrastructure

### Environments

| Environment | Trigger | Notes |
|---|---|---|
| Development | `python run.py` (or `FLASK_DEBUG=true python run.py`) | Random `SECRET_KEY` if unset |
| Production | `gunicorn wsgi:app` with `FLASK_ENV=production` | `SECRET_KEY` **must** be set |
| Testing | `TestingConfig` opt-in | Used by future pytest setup |

### Production checklist

1. `MONGO_URI` points at a managed cluster (Atlas).
2. `SECRET_KEY` is a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).
3. All API keys (`GEMINI_API_KEY`, `ASSEMBLYAI_API_KEY`, `VAPI_API_KEY`) provisioned with the correct quotas.
4. Reverse proxy (nginx / Caddy) terminates TLS and forwards to gunicorn.
5. `app/static/uploads/` is **writable** by the gunicorn process.

### Sample gunicorn invocation

```bash
gunicorn -w 4 -k gthread --threads 2 -b 0.0.0.0:8000 \
  --access-logfile - --error-logfile - wsgi:app
```

### Rollback

Because runs are append-only documents, rollback is just redeploying the previous build — no migrations to reverse.

### Monitoring

- `/health` — pings MongoDB; returns `200`/`503`.
- App logs use Python's `logging` module at INFO/DEBUG; redirect to your preferred aggregator.
- AI service errors are logged with `logger.exception` so stack traces are captured.

---

## 10. Error Handling & Logging

### HTTP errors

`app/__init__.py` installs handlers for 400/404/405/413/500. The `_is_api(req)` helper switches between JSON and HTML rendering based on `request.path.startswith('/api/')` or `request.is_json`.

### AI service failures

Every Gemini-backed route catches `TimeoutError` and `ValueError` (JSON parse) explicitly:
- Log with `logger.exception`.
- Reset the cached model (`_reset_model_for_retry`) unless the error is permanent (`PermissionDenied`, `NotFound`, `Unauthenticated`, or `403/404` in the message).
- Fall back to the deterministic generator/scorer.

### Logging configuration

- Root logger configured at INFO (or DEBUG when `FLASK_ENV=development`).
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.
- `RedactSecretsFilter` is attached to the root logger so even third-party libraries' logs are scrubbed of API keys.

---

## 11. Security Considerations

- **Authentication**: bcrypt password hashing (`bcrypt.hashpw` with default cost factor); `Flask-Login` sessions signed with `SECRET_KEY`.
- **Authorization**: every protected route uses `@login_required`. There are no role-based access checks — each user only sees their own runs (filtered by `user_email`).
- **Input validation**: email regex, password length, file size, file extension/MIME, page count, transcript length.
- **Upload sandbox**: PDFs are stored in `app/static/uploads/` with `secure_filename`. Only PDFs are accepted at the route level.
- **Secrets management**: env vars, never logged in plaintext (`RedactSecretsFilter`).
- **Outbound calls**: all third-party HTTP calls use explicit timeouts (10–15 s).
- **Known risks**:
  - Resumes saved on disk have no auto-cleanup — consider adding a TTL job.
  - `app/static/uploads/` is served by Flask's static handler; if exposed publicly, filenames are predictable from the original PDF name. Consider hashing.
  - The Flask session cookie is the auth token — set `SESSION_COOKIE_SECURE=True` and `SESSION_COOKIE_HTTPONLY=True` behind TLS in production.

---

## 12. Performance Notes

- **Gemini probe**: `_get_model()` runs a 4-token call to verify reachability. This adds latency on cold start but avoids handing back a model that 429s on first real call.
- **Threaded timeouts**: PDF extraction and Gemini calls run on a worker thread with a wall-clock cap so a stuck call cannot hold a request handler.
- **Session size**: `interview_results` is capped to `max(total_questions, 10)` entries to avoid unbounded growth in the cookie.
- **Indexes**: All hot read paths (`/profile`, `/api/results`, `/api/interview/history`) hit `interview_runs` by `(user_email, created_at desc)` — index already in place.
- **Question regeneration** runs synchronously between turns. Each call adds ~1–3 s. To remove from the critical path, move it to a background thread and let the next-question fetch poll.

---

## 13. Known Limitations & Future Work

- No automated test suite (only ad-hoc scripts).
- No Dockerfile / docker-compose checked in.
- No background worker — all AI calls are inline.
- No rate limiting on the public-facing endpoints.
- Whisper fallback is loaded on demand but downloads the model in the browser; first-use latency is noticeable.
- `VAPI_VOICE_ID` defaults to empty — every install needs to be explicit about whether to use VAPI TTS or the browser fallback.
- Settings page is a stub; `auth.settings_general` is a no-op.
- Profile page recomputes aggregates on each request; cache or precompute for high-traffic deployments.

---

## 14. Glossary

| Term | Meaning |
|---|---|
| **Run** | A complete interview session. One document in `interview_runs`. |
| **Slot** | One of the 5 fixed question types (concept / practical / problem-solving / behavioural / curiosity). |
| **Profile** | Normalized dict of `{skills, job_titles, education, experience_years, seniority, summary, name}` derived from the resume. |
| **Combined answer** | The deduplicated merge of voice transcript and typed input fed to Gemini for evaluation. |
| **Final scores** | The aggregate block stored on `interview_runs.final_scores`. |
| **Verdict** | `Strong Hire \| Hire \| Weak Hire \| Reject` (Gemini wording) or `strong_yes \| yes \| maybe \| no` (`final_scores.hire_recommendation`). |

---

## 15. Changelog

This project does not maintain a separate `CHANGELOG.md`; recent history is in git. Highlights from the most recent commits on `dev`:

- `feat(resume)`: home route now displays latest interview results and user feedback.
- `feat(interview)`: question generation accepts the full candidate profile; adaptive follow-up question per turn.
- `feat(env)`: VAPI voice configuration options added to `.env.example`.
- `refactor(interview)`: state management restructured for clearer UI feedback.
- `feat(vapi)`: improved error handling and fallback for TTS/STT.

For the full history: `git log --oneline`.
