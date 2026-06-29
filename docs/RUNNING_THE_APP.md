# Running the Flutter App + FastAPI Backend

This replaces the Streamlit UI with a Flutter app talking to a FastAPI backend.
All detection/chatbot/tracking logic is reused unchanged; only the UI layer is new.

```
Flutter app  ──REST + SSE + WebSocket──▶  FastAPI (server.py)  ──▶  YOLOv5 + Groq + SQLite
```

## 1. Start the backend (one command)

```bash
# from the repo root
pip install -r requirements.txt -r requirements-api.txt   # first time only
export GROQ_API_KEY=your_key_here        # Windows PowerShell: $env:GROQ_API_KEY="..."
python server.py
```

That boots uvicorn on `http://0.0.0.0:8000`, preloads the three YOLOv5 models,
and serves:

- Interactive API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Useful env vars: `API_PORT` (default 8000), `API_HOST`, `PRELOAD_MODELS=0`
(skip model warm-up for a faster start), `API_RELOAD=1` (auto-reload in dev).

> A `.env` file in the repo root is loaded automatically — copy `.env.example`
> to `.env` and put `GROQ_API_KEY` there instead of exporting it.

## 2. Run the Flutter app

```bash
cd flutter_app
flutter pub get        # first time only
flutter run            # pick a device when prompted
```

The app auto-targets the backend on the same machine:

| Target | Backend URL it uses |
|---|---|
| Windows / macOS / Linux desktop | `http://127.0.0.1:8000` |
| Web (Chrome) | `http://localhost:8000` |
| Android emulator | `http://10.0.2.2:8000` |

### Physical phone (same Wi-Fi as the backend)

Pass your computer's LAN IP:

```bash
flutter run --dart-define=API_HOST=192.168.1.50 --dart-define=API_PORT=8000
```

(Find it with `ipconfig` on Windows / `ifconfig` on macOS/Linux. The backend
already binds `0.0.0.0`, so it accepts LAN connections.)

## 3. Use it

1. Create a session (a crop/field).
2. Choose **Upload photo**, **Live camera**, or **Describe symptoms**.
3. After analysis you get the annotated image, crop/disease confidence, an
   auto-generated medicine plan, a streamed plain-language summary, and a
   week-by-week treatment tracker with a severity chart.

## Notes & gotchas

- **GROQ_API_KEY is required** for the medicine plan, treatment summary, and
  chat. Detection (YOLOv5) works without it; the chat parts return a clear
  "key not set" message.
- **Models**: `models/crop_detector.pt`, `corn_disease.pt`, `grape_disease.pt`
  must be present. First load pulls the YOLOv5 runtime from Torch Hub (needs
  internet once) unless a local `yolov5/` clone is present.
- **Cross-platform checkpoints**: the `.pt` files were trained on Linux/Python
  3.13. `crop_detection/_compat.py` shims `pathlib` so they load on Windows and
  older Python too (no action needed).
- **Android cleartext**: the app talks HTTP to the local backend; the Android
  manifest enables `usesCleartextTraffic` for development. Use HTTPS in prod.
- **Windows desktop build** requires Developer Mode (for plugin symlinks):
  `start ms-settings:developers`. Android/web builds do not.

## Tests

```bash
# Backend (no models / no API calls)
python -m pytest tests/ -v

# Flutter widget tests
cd flutter_app && flutter test

# Flutter <-> backend integration (needs server.py running)
flutter test --dart-define=RUN_INTEGRATION=true \
  --dart-define=API_HOST=127.0.0.1 --dart-define=API_PORT=8000 \
  test/api_integration_test.dart
```

## Why FastAPI + Flutter (architecture rationale)

- **FastAPI**: async ASGI, models preloaded warm in the lifespan (low inference
  latency), token-by-token **SSE** streaming (low perceived latency), Pydantic
  validation, auto OpenAPI docs, and horizontal scaling via uvicorn/gunicorn
  workers. The API is stateless apart from an in-memory session store that can
  move to Redis; the SQLite→PostgreSQL path is already documented.
- **Flutter**: one codebase → Android/iOS/web/desktop, compiled-native
  performance, with **Riverpod** for compile-safe, testable, scalable state.
