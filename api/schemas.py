"""Pydantic request/response models for the API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
class SessionCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)


class SessionOut(BaseModel):
    session_id: str
    display_name: str
    crop_name: str | None
    disease_name: str | None
    created_at: datetime
    has_analysis: bool = False


class ChatMessage(BaseModel):
    role: str            # "user" | "assistant"
    content: str


class SessionDetail(SessionOut):
    mode: str
    chat_history: list[ChatMessage]


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
class DetectionScore(BaseModel):
    class_name: str
    confidence: float


class AnalysisOut(BaseModel):
    crop_name: str
    crop_confidence: float
    crop_was_assumed: bool
    disease_name: str
    disease_confidence: float
    disease_was_fallback: bool
    recommendation: str | None
    inconclusive: bool
    annotated_url: str
    scores: list[DetectionScore]
    medicine_table_md: str
    medicines: list["MedicineOut"]


# --------------------------------------------------------------------------- #
# Medicine tracker
# --------------------------------------------------------------------------- #
class MedicineIn(BaseModel):
    week_number: int = Field(ge=1)
    date_applied: date
    medicine_name: str = Field(min_length=1)
    dosage_applied: str = ""
    application_method: str = "Other"
    symptom_severity: int = Field(ge=1, le=5, default=3)
    notes: str = ""
    is_improving: bool | None = None


class MedicineOut(BaseModel):
    entry_id: str
    session_id: str
    week_number: int
    date_applied: date
    medicine_id: str
    medicine_name: str
    dosage_applied: str
    application_method: str
    symptom_severity: int
    notes: str
    is_improving: bool | None


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class MessageIn(BaseModel):
    text: str = Field(min_length=1)


AnalysisOut.model_rebuild()
