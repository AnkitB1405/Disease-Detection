"""Single-command entry point for the Crop Disease Detection backend.

Run exactly like the old Streamlit launcher:

    python server.py

This boots a FastAPI app (via uvicorn) that exposes the same detection,
chatbot, and medicine-tracking features the Streamlit prototype provided —
but over REST + Server-Sent Events + WebSocket, for the Flutter client to
consume. The heavy ML packages (crop_detection/, chatbot/, tracking/) are
reused unchanged; only the Streamlit UI is replaced.

Environment (all optional, sensible defaults):
    API_HOST          bind address          (default 0.0.0.0)
    API_PORT          port                  (default 8000)
    API_RELOAD        "1" to auto-reload     (default 0)
    PRELOAD_MODELS    "0" to skip warm-up    (default 1)
    GROQ_API_KEY      required for chat/treatment generation
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ.

    Mirrors app.py: zero-dependency, real shell exports always win.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_dotenv()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - guidance path
        raise SystemExit(
            "uvicorn is not installed. Run:\n"
            "    pip install -r requirements.txt -r requirements-api.txt"
        ) from exc

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "0") == "1"

    print(f"Starting Crop Disease Detection API on http://{host}:{port}")
    print(f"Interactive API docs: http://{host}:{port}/docs")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
