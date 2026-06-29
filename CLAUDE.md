# Disease Detection — Claude Code Guide

## Project overview

A single-user Streamlit application that validates a crop image, uses a
Corn-first YOLOv5 routing pipeline to select a crop-specific disease model,
annotates and saves the result, uses a controlled medication database plus Groq
to generate a treatment explanation, and stores sessions and treatment progress
in SQLite.

Crops supported: **Corn** and **Grape**.
Diseases detected: Corn (Healthy, Gray Leaf Spot, Blight, Rust) and Grape
(Healthy, Black Rot, Blight).

---

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set the Groq API key (or copy .env.example to .env and fill it in)
export GROQ_API_KEY=your_key_here  # Windows PowerShell: $env:GROQ_API_KEY="..."

# 4. Place model weights (see Models section below)

# 5. Run the app
streamlit run app.py
# or
python app.py
```

---

## Environment variables

| Variable | Required | Where used |
|---|---|---|
| `GROQ_API_KEY` | Yes | `chatbot/groq_client.py` — all LLM calls |
| `YOLOV5_REPO` | No | `crop_detection/predictor.py` — local YOLOv5 repo path |

`app.py` loads `.env` automatically before any module reads these keys.

---

## Models

Three YOLOv5 `.pt` weight files are required at:

```text
models/crop_detector.pt    # detects Corn vs. not-Corn
models/corn_disease.pt     # detects corn diseases (healthy/gray_leaf/blight/rust)
models/grape_disease.pt    # detects grape diseases (Healthy/Black Rot/Blight)
```

YOLOv5 loading order:
1. Path from `YOLOV5_REPO` env var.
2. `./yolov5/` inside the project.
3. `../yolov5/` (parent directory).
4. Torch Hub remote fallback (requires internet on first load).

---

## Running tests

```bash
python -m pytest tests/ -v
```

Tests do **not** load real YOLO models or make real Groq API calls — they use
monkeypatching and temporary SQLite databases.

---

## Architecture

```text
app.py                    ← Streamlit UI, state machine, orchestration
crop_detection/           ← YOLO loading, inference, crop routing, annotation
chatbot/                  ← Groq calls, conversation state, prompts, summarization
tracking/                 ← SQLite persistence, medicine log, tracker UI
data/medications.json     ← Approved treatment context supplied to Groq
tests/                    ← Unit tests (no model loading, no API calls)
```

### State machine modes (app.py)

| Mode | What the user sees |
|---|---|
| `ONBOARDING` | Landing page with 3 options |
| `AWAITING_UPLOAD` | File uploader + Analyse button |
| `AWAITING_CAPTURE` | WebRTC camera preview + Capture button |
| `CLARIFYING` | Chat loop collecting symptom info (no image needed) |
| `ACTIVE_TREATMENT` | Follow-up chat + medicine tracker panel |
| `PAST_SESSIONS` | Session browser |
| `MEDICINE_TABLE` | Focused tracker view |

### Image analysis pipeline

```
load_uploaded_image()           ← Pillow validation + EXIF + RGB conversion
  → create_grayscale_copy()     ← grayscale RGB copy for crop model only
  → run_inference(crop_model)   ← conf threshold 0.25
  → select_crop()               ← Corn-first: "not Corn" = assume Grape
  → run_inference(disease_model)← conf threshold 0.10, uses ORIGINAL colour image
  → select_disease()            ← Corn: highest conf; Grape: must exceed 0.40
  → _draw_detection()           ← crop box green, disease box red
  → AnalysisResult              ← returned to app.py
  → handlers.handle_image_analysis()
      → phase 1: groq_client.complete() → medicine JSON → saved to SQLite
      → phase 2: groq_client.stream()   → condition summary streamed to UI
```

### Confidence thresholds (complete list)

| Value | Where | Purpose |
|---|---|---|
| `0.25` | `predictor.py` | Crop model minimum output confidence |
| `0.10` | `predictor.py` | Disease model minimum output confidence |
| `0.40` | `disease_logic.py` | Grape disease acceptance threshold |
| `0.50` / `0.15 gap` | `handlers.py` | Flag result as inconclusive |
| `0.15` | `handlers.py` | Minimum score sent to Groq as context |
| `0.05` | `app.py` | Minimum score displayed in UI |

---

## Developer ownership

Three developers built this. File-level ownership matters when raising PRs:

| Developer | Files owned |
|---|---|
| **Ankit** | `app.py`, `chatbot/state.py`, `chatbot/handlers.py` |
| **Suhaan** | `crop_detection/predictor.py`, `chatbot/groq_client.py`, `chatbot/prompts.py`, `chatbot/clarification.py`, `chatbot/summarizer.py`, `data/medications.json` |
| **Ishaan** | `tracking/models.py`, `tracking/persistence.py`, `tracking/tracker_ui.py`, `tests/test_persistence.py` |

---

## Key files reference

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI, file upload validation, state machine, camera WebRTC |
| `crop_detection/predictor.py` | YOLOv5 loading, inference, annotation, `AnalysisResult` |
| `crop_detection/disease_logic.py` | Pure deterministic routing: `select_crop()`, `select_disease()` |
| `crop_detection/solutions.py` | Static disease-to-recommendation mapping |
| `crop_detection/feedback.py` | Live-learning: saves user corrections + background fine-tunes affected model |
| `chatbot/state.py` | Streamlit session-state keys, session CRUD |
| `chatbot/handlers.py` | Business orchestration between detection, Groq, medication DB, persistence |
| `chatbot/groq_client.py` | Groq SDK wrapper: `complete()`, `stream()`, `summarize()` |
| `chatbot/prompts.py` | All prompt text (no logic) |
| `chatbot/clarification.py` | No-image symptom collection loop + JSON parsing |
| `chatbot/summarizer.py` | Rolling chat compression at 91 750 chars |
| `tracking/models.py` | `CropSession` and `MedicineEntry` dataclasses |
| `tracking/persistence.py` | SQLite CRUD for sessions and medicine log |
| `tracking/tracker_ui.py` | Editable medicine table, add-entry form, severity chart |
| `data/medications.json` | Approved treatments (corn: rust/gray_leaf/blight; grape: Black Rot/Blight) |

---

## SQLite schema (`tracking.db`)

```sql
crop_sessions (session_id PK, display_name, crop_name, disease_name, created_at, chat_summary)
medicine_log  (entry_id PK, session_id FK CASCADE, week_number, date_applied,
               medicine_id, medicine_name, dosage_applied, application_method,
               symptom_severity 1–5, notes, is_improving NULL/0/1)
```

`set_db_path()` in `persistence.py` redirects tests to a temp file.

---

## Groq LLM models

| Purpose | Model |
|---|---|
| Medicine JSON + clarification | `llama-3.3-70b-versatile` (blocking, temp 0.2) |
| Condition summary stream | `llama-3.3-70b-versatile` (streaming, temp 0.3) |
| Chat summarization | `llama-3.1-8b-instant` (blocking) |
| Clarification loop | `llama3-70b-8192` (hardcoded in `clarification.py`) |

---

## Live-learning feedback (`crop_detection/feedback.py`)

`FeedbackManager` is **not called from app.py yet** (it exists as infrastructure).
When integrated, the flow is:

1. User confirms or corrects crop/disease after analysis.
2. `FeedbackManager.save()` writes the image + YOLO labels to `feedback/`.
3. `FeedbackManager.maybe_trigger_retrain()` fine-tunes the affected `.pt` in a
   background thread (5 epochs, frozen backbone, replay buffer of 50 past samples).
4. On success, `consume_cache_clear_pending()` signals the UI to clear
   `@st.cache_resource` and reload the hot-swapped weights.

Requires a local `yolov5/` repo with `train.py` (won't retrain via Torch Hub).

---

## What persists across restarts

| Data | Location | Survives restart? |
|---|---|---|
| Models (cached in RAM) | `@st.cache_resource` | No |
| Full chat history | `CropSession` in RAM | No |
| Session metadata + crop/disease | SQLite | Yes |
| Rolling chat summary | SQLite | Yes |
| Medicine log | SQLite | Yes |
| Annotated output images | `outputs/*.jpg` | Yes |

---

## Known limitations and gotchas

- **"Not Corn" = assume Grape.** The crop model has no "unknown" class. Any
  non-corn leaf is silently routed through the Grape disease model.
- **Healthy can be a fallback**, not a positive detection (confidence shown as 0%).
- **`handle_camera_analysis()` is defined but never called.** Both upload and
  camera paths go through `handle_image_analysis()`.
- **`INCONCLUSIVE_RESPONSE` and `SUMMARIZE_PROMPT_TEMPLATE`** in `prompts.py`
  are defined but unused in the current flow.
- **`unsafe_allow_html=True`** in session cards interpolates user-controlled
  `display_name` directly — HTML-escape before production.
- **Single-user only.** All sessions in `tracking.db` are visible to everyone on
  the same deployment. No authentication exists.
- **Start Over** clears chat/result in memory but does not reset `crop_name`,
  `disease_name`, or medicine entries in SQLite.

---

## Adding a new crop or disease

1. Train a new YOLOv5 model and place weights in `models/`.
2. Add crop aliases to `CROP_ALIASES` in `disease_logic.py`.
3. Add disease aliases and display names to the relevant `*_DISEASE_ALIASES` and
   `DISPLAY_DISEASE_NAMES` dicts in `disease_logic.py`.
4. Add medication entries to `data/medications.json` under the new disease key.
5. Update `ModelManager.disease_model()` in `predictor.py` to route the new crop.
6. Add static recommendations to `solutions.py` if desired.
7. Add unit tests in `tests/test_disease_logic.py`.
