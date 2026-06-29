"""Image/camera analysis: Phase-1 detection + medicine plan, Phase-2 SSE summary."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.converters import to_medicine_out
from api.deps import get_session_or_404
from api.image_utils import InvalidImageError, load_image_from_bytes
from api.runtime import MANAGER, STORE
from api.schemas import AnalysisOut, DetectionScore
from api.services import analyze_phase1, summary_tokens
from api.sse import SSE_HEADERS, format_sse
from crop_detection.predictor import ModelLoadError, analyze_image
from tracking.models import CropSession

LOGGER = logging.getLogger("api.analyze")
router = APIRouter(prefix="/api/sessions", tags=["analysis"])

# Display threshold for the scores shown on the detection card (matches app.py).
_DISPLAY_THRESHOLD = 0.05


@router.post("/{session_id}/analyze", response_model=AnalysisOut)
def analyze(
    session: CropSession = Depends(get_session_or_404),
    file: UploadFile = File(...),
    note: str = Form(""),
) -> AnalysisOut:
    raw = file.file.read()
    try:
        image = load_image_from_bytes(raw, file.filename or "upload.jpg")
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = analyze_image(image, MANAGER)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unexpected analysis error")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc

    unreliable, entries, table_md = analyze_phase1(session, result, note, STORE)

    scores = [
        DetectionScore(class_name=d.class_name, confidence=d.confidence)
        for d in sorted(
            result.all_disease_detections, key=lambda x: x.confidence, reverse=True
        )
        if d.confidence > _DISPLAY_THRESHOLD
    ]

    return AnalysisOut(
        crop_name=result.crop_name,
        crop_confidence=result.crop_confidence,
        crop_was_assumed=result.crop_was_assumed,
        disease_name=result.disease_name,
        disease_confidence=result.disease_confidence,
        disease_was_fallback=result.disease_was_fallback,
        recommendation=result.recommendation,
        inconclusive=unreliable,
        annotated_url=f"/media/outputs/{result.output_path.name}",
        scores=scores,
        medicine_table_md=table_md,
        medicines=[to_medicine_out(e) for e in entries],
    )


@router.get("/{session_id}/analyze/summary")
def analyze_summary(session: CropSession = Depends(get_session_or_404)) -> StreamingResponse:
    """Phase-2: stream the plain-language condition summary as SSE."""

    def gen():
        try:
            for token in summary_tokens(session):
                yield format_sse({"type": "token", "content": token})
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Summary stream failed")
            yield format_sse({"type": "error", "content": str(exc)})
        yield format_sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
