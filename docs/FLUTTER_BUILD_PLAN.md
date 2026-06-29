# Flutter App + FastAPI Backend — Build Plan & Spec

> Branch: `flutter`. Goal: replace the Streamlit UI with a Flutter app talking to a
> FastAPI backend, preserving **exact current behavior** but with a polished app UI.
> A single command (`python server.py`) boots the backend, just like `python app.py` does today.

## Locked decisions (confirmed with user 2026-06-29)

| Decision | Choice | Why |
|---|---|---|
| Backend framework | **FastAPI** (uvicorn) | Async ASGI, warm-preloaded models, SSE streaming, Pydantic validation, auto OpenAPI, horizontal scaling, already pre-planned in `MULTI_USER_UPGRADE.md` Phase 3 |
| Frontend | **Flutter** | One codebase → Android/iOS/web/desktop, native performance |
| State management | **Riverpod** | Compile-safe, testable, decoupled from widget tree, scales |
| LLM streaming transport | **SSE** (`text/event-stream`) | One-way token streaming, native to FastAPI `StreamingResponse` + Flutter |
| Live camera | **Real-time preview via WebSocket** | Stream frames to backend, run crop YOLO every Nth frame, return box — replicates current WebRTC green-box. Plus capture→`/analyze`. |
| Execution | Sequential, single thread (I build it) | Full codebase context already loaded; tight backend↔frontend contract |
| DB | Keep **SQLite** (`tracking.db`) | Unchanged; Postgres path documented for later |

## Scalability defense (viva answer)
- FastAPI: non-blocking I/O, `uvicorn`/`gunicorn` worker scaling, stateless HTTP (session store can move to Redis), OpenAPI contract.
- Models preloaded once in FastAPI **lifespan** and kept warm in RAM (= `@st.cache_resource` today) → low inference latency.
- LLM responses **streamed token-by-token over SSE** → low *perceived* latency.
- Flutter compiled-native + Riverpod for scalable, testable client state.
- Persistence layer isolated → SQLite→Postgres swap needs no business-logic change.

## Reuse map (DO NOT rewrite these — pure, no Streamlit)
- `crop_detection/predictor.py`, `disease_logic.py`, `solutions.py`, `feedback.py`
- `chatbot/groq_client.py`, `prompts.py`, `clarification.py`, `summarizer.py`
- `tracking/models.py`, `tracking/persistence.py`
- `data/medications.json`

## Must reimplement WITHOUT Streamlit (currently import `streamlit`)
- `chatbot/state.py` → server-side `api/session_store.py` (in-memory CropSession store, = `st.session_state`)
- `chatbot/handlers.py` → `api/services.py` (orchestration: analysis, medication lookup, 2-phase Groq, clarify/followup)
- `tracking/tracker_ui.py` → not needed (Flutter renders the tracker)
- `app.py` → replaced by `server.py` + `api/`

## Backend file structure
```
server.py                  # python server.py → loads .env, uvicorn api.main:app, preloads models
api/
  __init__.py
  main.py                  # FastAPI app, lifespan (ModelManager preload), CORS, router mounts
  schemas.py               # Pydantic models (SessionOut, AnalysisOut, MedicineIn/Out, MessageIn, etc.)
  session_store.py         # in-memory {session_id: CropSession}; mirrors chatbot/state.py
  services.py              # orchestration ported from chatbot/handlers.py (no streamlit)
  image_utils.py           # load_uploaded_image() ported from app.py (Pillow validation)
  routers/
    __init__.py
    sessions.py            # CRUD
    analyze.py             # POST image → analysis; SSE summary
    chat.py                # text messages + SSE replies
    medicines.py           # tracker CRUD
    camera.py              # WebSocket live-preview frame loop
    media.py               # serve outputs/*.jpg
```

## API contract (REST + SSE + WS)
- `GET  /health`
- `POST /api/sessions` {display_name} → SessionOut
- `GET  /api/sessions` → [SessionOut]
- `GET  /api/sessions/{id}` → SessionDetail (history, crop, disease, analysis, medicines)
- `DELETE /api/sessions/{id}`
- `POST /api/sessions/{id}/analyze` (multipart image, note?) → AnalysisOut {crop, crop_conf, disease, disease_conf, assumed, fallback, scores[], annotated_url, inconclusive, medicine_table_md, medicines[]}
- `GET  /api/sessions/{id}/analyze/summary` (SSE) → streamed condition summary (phase-2 Groq)
- `POST /api/sessions/{id}/messages` {text} → starts clarify/followup; returns SSE url or streams
- `GET  /api/sessions/{id}/messages/stream?text=...` (SSE) → streamed reply
- `GET  /api/sessions/{id}/medicines` → [MedicineOut]
- `POST /api/sessions/{id}/medicines` (MedicineIn) → MedicineOut
- `PUT  /api/medicines/{entry_id}` (MedicineIn) → MedicineOut
- `DELETE /api/medicines/{entry_id}`
- `WS   /ws/sessions/{id}/camera` → client sends JPEG frames; server runs crop YOLO every Nth frame, returns {box, label, conf}
- `GET  /media/outputs/{filename}` → annotated JPEG

Thresholds/behavior preserved exactly: crop 0.25, disease 0.10, grape 0.40, inconclusive 0.50/0.15 gap, display 0.15/0.05. Two Groq calls after analysis (phase1 medicine JSON → SQLite, phase2 streamed summary). Corn-first routing; "not Corn" = assume Grape. Healthy fallback at 0% conf.

## Flutter app structure
```
flutter_app/
  pubspec.yaml             # riverpod, dio, fl_chart, image_picker, camera, web_socket_channel, flutter_client_sse
  lib/
    main.dart
    core/   config.dart (baseUrl), api_client.dart (dio), sse_client.dart, theme.dart
    models/ session.dart, analysis.dart, medicine.dart, message.dart
    providers/ sessions_provider.dart, chat_provider.dart, analysis_provider.dart, medicines_provider.dart
    screens/ onboarding, upload, camera, clarify, treatment, sessions, tracker
    widgets/ chat_bubble, detection_card, medicine_table, severity_chart, option_card
```
Mirror the 7 modes: ONBOARDING, AWAITING_UPLOAD, AWAITING_CAPTURE, CLARIFYING, ACTIVE_TREATMENT, PAST_SESSIONS, MEDICINE_TABLE.
Use the **ui-ux plugin** for the design/polish pass.

## Build order (progress tracker) — COMPLETE
- [x] 0. Branch `flutter` created
- [x] 1. Backend deps + `server.py` + `api/main.py` lifespan model preload
- [x] 2. `api/image_utils.py`, `api/session_store.py`
- [x] 3. `api/services.py` (port handlers.py orchestration, no streamlit)
- [x] 4. Routers: sessions, analyze (+SSE summary), media
- [x] 5. Routers: chat (SSE), medicines
- [x] 6. Router: camera WebSocket live preview
- [x] 7. Smoke-test backend — verified analyze (Corn→Gray Leaf Spot on a real
       image), annotated-image serving, SSE (graceful no-key degradation),
       session + medicine CRUD
- [x] 8. Flutter scaffold + pubspec + core (api/sse/config/theme)
- [x] 9. Flutter models + providers (Riverpod)
- [x] 10. Flutter screens (onboarding→tracker) + widgets
- [x] 11. ui-ux pass (Material 3 green theme, cards, metrics, chat, chart)
- [x] 12. End-to-end verify — `flutter build web` compiles, `flutter analyze`
        clean, widget test + live ApiClient↔backend integration test pass.
        Run steps in `docs/RUNNING_THE_APP.md`.

## Cross-platform fixes applied (checkpoints trained on Linux/Python 3.13)
- `crop_detection/_compat.py` — shims `pathlib.PosixPath`→`WindowsPath` and
  registers a `pathlib._local` module so the `.pt` files unpickle on Windows /
  Python ≤3.12. Imported + invoked at the top of `predictor.py`.
- `flutter_app/lib/core/config.dart` — desktop default host is `127.0.0.1`
  (not `localhost`, which resolves to IPv6 `::1` on Windows and misses the
  IPv4 uvicorn server). Android→`10.0.2.2`, web→`localhost`.
- Android manifest — `usesCleartextTraffic=true` + CAMERA/INTERNET permissions
  so the app can reach the local `http://` backend and use the camera.
```
