"""Serve generated annotated images from outputs/."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.runtime import MANAGER

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/outputs/{filename}")
def get_output(filename: str) -> FileResponse:
    # Only ever serve a basename from the outputs dir (no path traversal).
    safe_name = Path(filename).name
    path = MANAGER.outputs_dir / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path, media_type="image/jpeg")
