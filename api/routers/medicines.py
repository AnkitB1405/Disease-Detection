"""Medicine tracker CRUD — mirrors tracking/tracker_ui.py persistence calls."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from api.converters import to_medicine_out
from api.deps import get_session_or_404
from api.schemas import MedicineIn, MedicineOut
from tracking import persistence
from tracking.models import CropSession, MedicineEntry

router = APIRouter(prefix="/api/sessions", tags=["medicines"])

_VALID_METHODS = {"Foliar Spray", "Soil Drench", "Seed Treatment", "Other"}


def _build_entry(session_id: str, entry_id: str, body: MedicineIn) -> MedicineEntry:
    method = body.application_method if body.application_method in _VALID_METHODS else "Other"
    return MedicineEntry(
        entry_id=entry_id,
        session_id=session_id,
        week_number=body.week_number,
        date_applied=body.date_applied,
        medicine_id="manual",
        medicine_name=body.medicine_name.strip(),
        dosage_applied=body.dosage_applied.strip(),
        application_method=method,
        symptom_severity=body.symptom_severity,
        notes=body.notes.strip(),
        is_improving=body.is_improving,
    )


@router.get("/{session_id}/medicines", response_model=list[MedicineOut])
def list_medicines(session: CropSession = Depends(get_session_or_404)) -> list[MedicineOut]:
    entries = persistence.load_medicine_entries(session.session_id)
    return [to_medicine_out(e) for e in entries]


@router.post("/{session_id}/medicines", response_model=MedicineOut, status_code=201)
def add_medicine(
    body: MedicineIn,
    session: CropSession = Depends(get_session_or_404),
) -> MedicineOut:
    entry = _build_entry(session.session_id, str(uuid4()), body)
    persistence.save_medicine_entry(entry)
    return to_medicine_out(entry)


@router.put("/{session_id}/medicines/{entry_id}", response_model=MedicineOut)
def update_medicine(
    entry_id: str,
    body: MedicineIn,
    session: CropSession = Depends(get_session_or_404),
) -> MedicineOut:
    existing = {e.entry_id for e in persistence.load_medicine_entries(session.session_id)}
    if entry_id not in existing:
        raise HTTPException(status_code=404, detail="Medicine entry not found")
    entry = _build_entry(session.session_id, entry_id, body)
    persistence.save_medicine_entry(entry)
    return to_medicine_out(entry)


@router.delete("/{session_id}/medicines/{entry_id}", status_code=204)
def delete_medicine(
    entry_id: str,
    session: CropSession = Depends(get_session_or_404),
) -> None:
    persistence.delete_medicine_entry(entry_id)
