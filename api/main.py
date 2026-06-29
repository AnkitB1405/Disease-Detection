"""FastAPI application factory: lifespan model preload, CORS, router mounts.

Imported by uvicorn as `api.main:app` (see server.py).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import runtime
from api.routers import analyze, camera, chat, medicines, media, sessions

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load persisted sessions and warm the YOLOv5 models so the first /analyze
    # request is fast (the equivalent of @st.cache_resource in the old app).
    runtime.STORE.ensure_loaded()
    runtime.warmup()
    LOGGER.info("API ready.")
    yield


app = FastAPI(
    title="Crop Disease Detection API",
    description="REST + SSE + WebSocket backend for the Flutter crop-disease app.",
    version="1.0.0",
    lifespan=lifespan,
)

# Flutter clients run from arbitrary origins (mobile, web, desktop); allow all.
# Tighten this for a production web deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (sessions, analyze, chat, medicines, media, camera):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "sessions_loaded": runtime.STORE._loaded,  # noqa: SLF001 - simple status
        "groq_key_set": bool(__import__("os").getenv("GROQ_API_KEY")),
    }
