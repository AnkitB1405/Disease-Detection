"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException

from api.runtime import STORE
from tracking.models import CropSession


def get_session_or_404(session_id: str) -> CropSession:
    session = STORE.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
