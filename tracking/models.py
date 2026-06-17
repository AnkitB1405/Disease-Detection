"""Data models for crop sessions and medicine tracking. No Streamlit imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class MedicineEntry:
    entry_id: str
    session_id: str
    week_number: int
    date_applied: date
    medicine_id: str        # references medications.json medication id
    medicine_name: str      # denormalized for display
    dosage_applied: str     # actual dose used by farmer
    application_method: str
    symptom_severity: int   # 1 (trace) to 5 (severe)
    notes: str
    is_improving: bool | None  # None = too early to tell


@dataclass
class CropSession:
    session_id: str
    display_name: str           # user-editable label, e.g. "Corn Field A"
    crop_name: str | None
    disease_name: str | None
    created_at: datetime
    chat_history: list[dict] = field(default_factory=list)
    # {"role": "user"|"assistant"|"system", "content": str}
    # First user message is always the YOLO analysis — never compressed.
    chat_summary: str | None = None   # rolling summary of compressed messages
    analysis_result: Any | None = None  # AnalysisResult; typed Any to avoid circular import
    clarification_state: dict | None = None
    medicine_entries: list[MedicineEntry] = field(default_factory=list)
