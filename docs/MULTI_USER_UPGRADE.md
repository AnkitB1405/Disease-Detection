# Multi-User Upgrade Guide

This document describes the exact steps required to upgrade the single-user prototype to a multi-user production system. The codebase is architected to make this migration clean — no business logic needs to change, only the persistence layer, session isolation, and the UI entry point.

---

## Phase 1 — Session Isolation Without Authentication (Quick Win)

This phase adds per-browser isolation using a UUID stored in the URL. Users on the same server cannot see each other's data. No login required.

### Step 1 — Add `user_token` to SQLite

Run this migration SQL once on the production `tracking.db`:

```sql
ALTER TABLE crop_sessions ADD COLUMN user_token TEXT;
ALTER TABLE medicine_log ADD COLUMN user_token TEXT;

-- Back-fill existing single-user data with a placeholder token
UPDATE crop_sessions SET user_token = 'legacy-single-user' WHERE user_token IS NULL;
UPDATE medicine_log   SET user_token = 'legacy-single-user' WHERE user_token IS NULL;
```

### Step 2 — Update `tracking/persistence.py`

1. In `load_sessions()`, add a `WHERE user_token = ?` filter and pass the token as a parameter.
2. In `save_session()` and `save_medicine_entry()`, include `user_token` in the INSERT/UPDATE.
3. Add a `get_or_create_user_token() -> str` function that reads from `st.query_params` and generates a new UUID if none exists.

```python
# In app.py — call this before init_session_state()
import streamlit as st
from tracking.persistence import get_or_create_user_token

if "user_token" not in st.session_state:
    st.session_state.user_token = get_or_create_user_token()
```

4. Pass `st.session_state.user_token` to every persistence call.

### Step 3 — Persist token in the URL

```python
def get_or_create_user_token() -> str:
    params = st.query_params
    token = params.get("uid")
    if not token:
        token = str(uuid4())
        st.query_params["uid"] = token
    return token
```

Users bookmark their URL (e.g. `http://yourapp/?uid=abc123`) to return to their data. This is not secure authentication — see Phase 2 for real auth.

### Files changed in Phase 1:
- `tracking/persistence.py` — add `user_token` parameter to all queries
- `app.py` — call `get_or_create_user_token()` before `init_session_state()`
- `tracking/models.py` — no changes needed (token is a persistence concern, not a model concern)

---

## Phase 2 — Real Authentication

When the app is deployed publicly with actual farmers, add proper authentication. Two options depending on complexity:

### Option A — Streamlit Authenticator (simpler, stays on Streamlit)

Install: `pip install streamlit-authenticator`

1. Create a `config.yaml` with hashed passwords.
2. Wrap `streamlit_main()` with the authenticator login screen.
3. Use the authenticated `username` as the `user_token` instead of the URL UUID.
4. See the [streamlit-authenticator documentation](https://github.com/mkhorasani/Streamlit-Authenticator) for setup.

### Option B — FastAPI + JWT (proper, required for React migration)

See Phase 3 (React + FastAPI migration). When you build the FastAPI backend, add:

1. `POST /auth/register` and `POST /auth/login` endpoints returning JWT tokens.
2. All data endpoints require `Authorization: Bearer <token>` header.
3. The `user_id` from the JWT is used as the isolation key in SQLite (or Postgres).

---

## Phase 3 — React + FastAPI Migration

The codebase is intentionally structured so that `crop_detection/`, `chatbot/`, and `tracking/` packages have **zero Streamlit imports**. The migration is therefore additive — add a new `api.py`, build the React frontend, and retire `app.py` last.

### Step 1 — Add `api.py` (FastAPI backend)

```bash
pip install fastapi uvicorn python-multipart
```

Create `api.py` with routes that call the same packages:

```python
from fastapi import FastAPI, UploadFile, Depends
from fastapi.responses import StreamingResponse
from crop_detection.predictor import analyze_image, ModelManager
from chatbot.handlers import handle_image_analysis, handle_text_message
from chatbot.state import CropSession   # use as a Pydantic model or dataclass
from tracking.persistence import load_sessions, save_medicine_entry

app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parent

@app.get("/sessions")
def get_sessions(user_id: str):
    return load_sessions(user_token=user_id)

@app.post("/sessions/{session_id}/analyze")
async def analyze(session_id: str, file: UploadFile, user_message: str = ""):
    image = load_image_from_upload(file)
    manager = ModelManager.from_project_root(PROJECT_ROOT)
    result = analyze_image(image, manager)
    # Return detection data; Groq streaming handled via separate /chat endpoint
    return result_to_dict(result)

@app.post("/sessions/{session_id}/chat")
def chat(session_id: str, message: str, user_id: str):
    session = load_session(session_id, user_id)
    response_iter = handle_text_message(message, session)
    return StreamingResponse(response_iter, media_type="text/event-stream")
```

### Step 2 — Build the React frontend

Recommended stack:
- **Next.js 14+** with App Router for routing and SSR
- **TanStack Query** for API calls and caching
- **shadcn/ui** for components (chat bubbles, tables, forms)
- **Vercel AI SDK** for streaming text responses from the FastAPI SSE endpoint

React component tree:
```
App
├── Sidebar
│   ├── SessionList (GET /sessions)
│   └── NewSessionForm
└── Main
    ├── ChatWindow
    │   ├── MessageList
    │   └── ChatInput
    ├── InputModeSelector (Upload / Camera / Describe)
    ├── AnalysisResult (shown after YOLO runs)
    └── MedicineTracker
        ├── TreatmentTable
        └── SeverityChart
```

### Step 3 — Run both in parallel during migration

Use a reverse proxy (nginx or Caddy) to serve:
- `/api/*` → FastAPI (port 8000)
- `/*` → React (port 3000)

Keep `app.py` running for the existing users during the transition. Once the React frontend reaches feature parity, redirect all traffic and decommission `app.py`.

### Step 4 — Replace SQLite with PostgreSQL

SQLite is suitable for a single server. For multi-region or high-concurrency:

```bash
pip install asyncpg sqlalchemy[asyncio] alembic
```

1. Write Alembic migrations for the two tables.
2. Replace `sqlite3.connect()` in `persistence.py` with `asyncpg` or SQLAlchemy async engine.
3. Wrap persistence functions with `async/await`.
4. FastAPI route handlers become `async def`.

No model or business logic changes needed.

---

## Summary: What Changes in Each Phase

| Phase | Files Changed | Risk |
|-------|--------------|------|
| 1 — URL token isolation | `persistence.py`, `app.py` | Low — additive only |
| 2A — Streamlit Authenticator | `app.py`, new `config.yaml` | Low |
| 2B — FastAPI JWT | New `api.py`, new `auth/` module | Medium |
| 3A — FastAPI backend | New `api.py` | Medium — parallel, no removals |
| 3B — React frontend | New `frontend/` directory | High — frontend rewrite |
| 3C — PostgreSQL | `persistence.py` | Medium — swap storage layer |

**The `crop_detection/`, `chatbot/`, and `tracking/` packages change in none of these phases** — they are pure Python and work equally well called from Streamlit, FastAPI, or a test.

---

## Search Tags for Single-User Removal

All single-user assumptions in the current code are marked with this comment:

```python
# SINGLE_USER
```

Run `grep -r "SINGLE_USER" .` to find every touch point before starting Phase 1.
