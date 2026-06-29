"""Live camera preview over WebSocket — the API analogue of the WebRTC
VideoProcessor in the Streamlit app.

The Flutter client streams JPEG frames (throttled to a few fps). For each
frame the backend runs ONLY the crop detector on a grayscale copy and returns
the highest-confidence Corn box (or a "searching" sentinel), exactly like the
old every-Nth-frame preview. Capturing for full analysis reuses POST /analyze.

Box coordinates are returned in source-image pixels alongside the frame
width/height so the client can scale the overlay to its preview widget.
"""

from __future__ import annotations

import io
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from api.runtime import MANAGER
from crop_detection.disease_logic import select_crop
from crop_detection.predictor import create_grayscale_copy, run_inference

LOGGER = logging.getLogger("api.camera")
router = APIRouter(tags=["camera"])

_SEARCHING = {"box": None, "label": "Searching for leaf...", "confidence": 0.0}


def _detect_crop_box(frame_bytes: bytes) -> dict:
    """Run the crop detector on one frame; return a JSON-able preview result."""
    try:
        with Image.open(io.BytesIO(frame_bytes)) as raw:
            image = raw.convert("RGB")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return dict(_SEARCHING)

    detections = run_inference(MANAGER.crop_model(), create_grayscale_copy(image))
    crop = select_crop(detections)
    base = {"width": image.width, "height": image.height}
    if crop.selected_detection is not None:
        x1, y1, x2, y2 = crop.selected_detection.box
        return {
            "box": [x1, y1, x2, y2],
            "label": crop.name,
            "confidence": crop.confidence,
            **base,
        }
    return {**_SEARCHING, **base}


@router.websocket("/ws/sessions/{session_id}/camera")
async def camera_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    last_result: dict = dict(_SEARCHING)
    try:
        while True:
            frame = await websocket.receive_bytes()
            try:
                last_result = await run_in_threadpool(_detect_crop_box, frame)
            except Exception as exc:  # noqa: BLE001 - keep the stream alive
                LOGGER.warning("Camera inference failed: %s", exc)
                # Reuse the previous box rather than dropping the connection.
            await websocket.send_json(last_result)
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        LOGGER.exception("Camera WebSocket error")
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
