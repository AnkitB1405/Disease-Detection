"""Shared backend runtime: env loading, warm model manager, session store.

These singletons replace Streamlit's @st.cache_resource (for the ModelManager)
and st.session_state (for the in-memory CropSession store). They live for the
lifetime of the server process and are safe to share across requests because
the heavy endpoints run in a threadpool (sync route handlers).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from crop_detection.predictor import ModelManager
from api.session_store import SessionStore

LOGGER = logging.getLogger("api.runtime")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load .env into os.environ (idempotent; real env always wins)."""
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


# Load .env as early as possible — uvicorn may import api.main without server.py.
load_dotenv()

# The ModelManager only resolves paths on construction; the actual YOLOv5
# checkpoints are loaded lazily (and cached) on first inference.
MANAGER: ModelManager = ModelManager.from_project_root(PROJECT_ROOT)

# In-memory CropSession store (replaces st.session_state.crop_sessions).
STORE: SessionStore = SessionStore()


def warmup() -> None:
    """Best-effort: load the three YOLOv5 models so the first /analyze is fast.

    Missing weights or an absent YOLOv5 repo must NOT crash startup — the
    Streamlit app behaved the same way (it showed a message on Analyze). We log
    and continue; the model then loads on the first real request.
    """
    if os.getenv("PRELOAD_MODELS", "1") != "1":
        LOGGER.info("PRELOAD_MODELS=0 — skipping model warm-up.")
        return
    for label, loader in (
        ("crop_detector", lambda: MANAGER.crop_model()),
        ("corn_disease", lambda: MANAGER.disease_model("Corn")),
        ("grape_disease", lambda: MANAGER.disease_model("Grape")),
    ):
        try:
            loader()
            LOGGER.info("Warmed up model: %s", label)
        except Exception as exc:  # noqa: BLE001 - intentional best-effort
            LOGGER.warning("Could not warm up %s: %s", label, exc)
