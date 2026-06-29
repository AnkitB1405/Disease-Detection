"""Dataclass -> Pydantic conversion helpers."""

from __future__ import annotations

from api.schemas import MedicineOut, SessionOut
from tracking.models import CropSession, MedicineEntry


def to_medicine_out(entry: MedicineEntry) -> MedicineOut:
    return MedicineOut(**vars(entry))


def to_session_out(session: CropSession) -> SessionOut:
    return SessionOut(
        session_id=session.session_id,
        display_name=session.display_name,
        crop_name=session.crop_name,
        disease_name=session.disease_name,
        created_at=session.created_at,
        has_analysis=session.analysis_result is not None,
    )
