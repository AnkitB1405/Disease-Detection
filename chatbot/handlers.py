"""Message routing, inconclusiveness checks, and Groq call orchestration.

Public entry points:
  handle_image_analysis(result, user_message, session)  -> AnalysisResponse
  handle_camera_analysis(result, user_message, session) -> AnalysisResponse
  handle_text_message(user_text, session)               -> ClarificationResult | Iterator[str]

An AnalysisResponse carries:
  - is_unreliable         : bool — detection confidences were too close
  - auto_medicine_entries : list[MedicineEntry] saved to the DB automatically
  - medicine_table_markdown: str — pre-formatted markdown table for the chat
  - summary_stream        : Iterator[str] — lazy Phase-2 Groq stream

Phase 1 (blocking)  : JSON medicine plan  → parsed → saved → chat history entry added
Phase 2 (streaming) : Crop condition summary → streamed by the caller via st.write_stream
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import NamedTuple
from uuid import uuid4

from chatbot import groq_client, clarification, summarizer
from chatbot.prompts import (
    TREATMENT_SYSTEM_PROMPT,
    MEDICINE_JSON_SYSTEM_PROMPT,
    CROP_CONDITION_SUMMARY_SYSTEM_PROMPT,
    ANALYSIS_USER_MESSAGE_TEMPLATE,
    TEXT_PATH_USER_MESSAGE_TEMPLATE,
    NO_MEDICATION_DATA_RESPONSE,
    INCONCLUSIVE_WARNING,
)
from chatbot.clarification import ClarificationResult
from chatbot.state import append_message, set_chat_mode, update_session_crop_disease
from crop_detection.disease_logic import Detection
from tracking import persistence
from tracking.models import CropSession, MedicineEntry

LOGGER = logging.getLogger(__name__)

_MEDICATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "medications.json"
_INCONCLUSIVENESS_TOP_CONF_THRESHOLD = 0.50
_INCONCLUSIVENESS_GAP_THRESHOLD = 0.15
_DETECTION_DISPLAY_THRESHOLD = 0.15


# ---------------------------------------------------------------------------
# Return type for image / camera analysis
# ---------------------------------------------------------------------------

class AnalysisResponse(NamedTuple):
    is_unreliable: bool
    auto_medicine_entries: list          # list[MedicineEntry]
    medicine_table_markdown: str         # pre-formatted markdown; empty if no medicines
    summary_stream: Iterator[str]        # lazy Phase-2 Groq stream


# ---------------------------------------------------------------------------
# Inconclusiveness check (now a WARNING flag, not a hard blocker)
# ---------------------------------------------------------------------------

def is_inconclusive(all_detections: tuple[Detection, ...]) -> bool:
    """Return True when the model cannot reliably identify a single disease.

    Rules:
    - No detections at all → inconclusive
    - Top confidence < 50% AND gap between top-1 and top-2 < 15pp → inconclusive
    """
    filtered = [d for d in all_detections if d.confidence > 0.10]
    if not filtered:
        return True
    top = sorted(filtered, key=lambda d: d.confidence, reverse=True)
    if top[0].confidence < _INCONCLUSIVENESS_TOP_CONF_THRESHOLD:
        if len(top) < 2 or (top[0].confidence - top[1].confidence) < _INCONCLUSIVENESS_GAP_THRESHOLD:
            return True
    return False


# ---------------------------------------------------------------------------
# Medication database lookup
# ---------------------------------------------------------------------------

def _load_medication_block(crop_name: str, disease_canonical: str) -> str:
    if not _MEDICATIONS_PATH.is_file():
        return NO_MEDICATION_DATA_RESPONSE

    try:
        with open(_MEDICATIONS_PATH, encoding="utf-8") as f:
            db = json.load(f)
    except (json.JSONDecodeError, OSError):
        return NO_MEDICATION_DATA_RESPONSE

    crop_key = crop_name.lower()
    diseases = db.get("diseases", {}).get(crop_key, {})
    entry = diseases.get(disease_canonical)
    if not entry:
        return NO_MEDICATION_DATA_RESPONSE

    lines: list[str] = []
    lines.append(f"Disease: {entry.get('display_name', disease_canonical)}")
    lines.append(f"Description: {entry.get('description', 'N/A')}")

    controls = entry.get("cultural_controls", [])
    if controls:
        lines.append("\nCultural controls:")
        for c in controls:
            lines.append(f"  - {c}")

    meds = entry.get("medications", [])
    if meds:
        lines.append("\nApproved medications:")
        for med in meds:
            lines.append(f"\n  {med.get('trade_name', 'Unknown')} ({med.get('active_ingredient', '')})")
            lines.append(f"    Class: {med.get('class', 'N/A')}")
            lines.append(f"    Application: {med.get('application_method', 'N/A')}")
            lines.append(f"    Dosage rate: {med.get('dosage_rate', 'N/A')}")
            lines.append(f"    Water volume: {med.get('water_volume', 'N/A')}")
            lines.append(f"    Timing: {med.get('timing', 'N/A')}")
            lines.append(f"    Reapplication interval: {med.get('reapplication_interval_days', 'N/A')} days")
            lines.append(f"    Pre-harvest interval: {med.get('preharvest_interval_days', 'N/A')} days")
            lines.append(f"    Max applications/season: {med.get('max_applications_per_season', 'N/A')}")
            if med.get("severity_threshold"):
                lines.append(f"    When to treat: {med['severity_threshold']}")
            if med.get("notes"):
                lines.append(f"    Notes: {med['notes']}")
            lines.append(f"    Source: {med.get('research_source', 'N/A')}")
    else:
        lines.append("\nNo specific medications are listed. Rely on cultural controls above.")

    return "\n".join(lines)


def _format_all_detections(all_detections: tuple[Detection, ...]) -> str:
    visible = [d for d in all_detections if d.confidence > _DETECTION_DISPLAY_THRESHOLD]
    if not visible:
        return "  (no detections above 15% confidence threshold)"
    lines = []
    for d in sorted(visible, key=lambda x: x.confidence, reverse=True):
        lines.append(f"  - {d.class_name}: {d.confidence:.1%}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase-1: Parse JSON medicine plan and persist entries
# ---------------------------------------------------------------------------

_VALID_METHODS = {"Foliar Spray", "Soil Drench", "Seed Treatment", "Other"}


def _parse_and_save_medicines(
    json_raw: str,
    session_id: str,
) -> tuple[list[MedicineEntry], str]:
    """Parse the JSON medicine plan from Phase-1 LLM call.

    Returns (saved_entries, markdown_table_string).
    On any parse error returns ([], "").
    """
    try:
        data = json.loads(json_raw.strip())
        medicines = data.get("medicines", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        LOGGER.warning("Phase-1 LLM returned non-JSON: %.200s", json_raw)
        return [], ""

    if not medicines:
        return [], ""

    entries: list[MedicineEntry] = []
    today = date.today()

    for med in medicines:
        name = str(med.get("name", "")).strip()
        if not name:
            continue
        method_raw = str(med.get("method", "Other")).strip()
        method = method_raw if method_raw in _VALID_METHODS else "Other"
        entry = MedicineEntry(
            entry_id=str(uuid4()),
            session_id=session_id,
            week_number=int(med.get("week_start", 1)),
            date_applied=today,
            medicine_id="auto_llm",
            medicine_name=name,
            dosage_applied=str(med.get("dosage", "")).strip(),
            application_method=method,
            symptom_severity=3,
            notes=str(med.get("notes", "")).strip(),
            is_improving=None,
        )
        persistence.save_medicine_entry(entry)
        entries.append(entry)

    if not entries:
        return [], ""

    # Build a readable markdown table for the chat message
    lines = [
        "**Treatment Plan Auto-Generated**",
        "",
        "The following medicines have been added to your treatment table automatically. "
        "You can edit or delete them in the Medicine Table.",
        "",
        "| Medicine | Dosage | Method | Duration | Notes |",
        "|----------|--------|--------|----------|-------|",
    ]
    for med in medicines:
        name = str(med.get("name", "—"))
        dosage = str(med.get("dosage", "—"))
        method = str(med.get("method", "—"))
        duration = f"{med.get('duration_weeks', '?')} wks"
        notes = str(med.get("notes", ""))
        # Escape pipe characters to avoid breaking the markdown table
        def _esc(s: str) -> str:
            return s.replace("|", "\\|")
        lines.append(f"| {_esc(name)} | {_esc(dosage)} | {_esc(method)} | {_esc(duration)} | {_esc(notes)} |")

    return entries, "\n".join(lines)


# ---------------------------------------------------------------------------
# Image analysis handlers (upload and camera share the same core)
# ---------------------------------------------------------------------------

def _handle_analysis_common(
    result,          # AnalysisResult
    user_message: str,
    session: CropSession,
) -> AnalysisResponse:
    """Two-phase LLM flow for both upload and camera paths.

    Phase 1 (blocking): JSON medicine plan → parsed → saved to DB → appended to history.
    Phase 2 (lazy):     Crop condition summary stream returned to caller.
    Inconclusive detections raise a warning flag but do NOT block analysis.
    """
    unreliable = is_inconclusive(result.all_disease_detections)

    # Persist the raw AnalysisResult on the session for the detection card
    session.analysis_result = result

    crop_assumption_note = (
        "\n(Grape was assumed — no Corn detection found)"
        if result.crop_was_assumed else ""
    )
    fallback_note = (
        "\n(Healthy fallback applied — no qualifying disease detected)"
        if result.disease_was_fallback else ""
    )
    unreliable_note = (
        "\n\nIMPORTANT: Detection confidence is LOW — the top two scores are very close. "
        "Treat this result as tentative and advise the farmer to seek confirmation."
        if unreliable else ""
    )

    medication_block = _load_medication_block(
        result.crop_name,
        _canonical_disease_key(result.crop_name, result.disease_name),
    )

    user_msg_content = ANALYSIS_USER_MESSAGE_TEMPLATE.format(
        crop_name=result.crop_name,
        crop_confidence=result.crop_confidence,
        crop_assumption_note=crop_assumption_note,
        disease_name=result.disease_name,
        disease_confidence=result.disease_confidence,
        fallback_note=fallback_note,
        all_detections_block=_format_all_detections(result.all_disease_detections),
        medication_block=medication_block,
        user_message=(user_message or "Please explain the results and provide a treatment plan.")
                     + unreliable_note,
    )

    # Store as "user" so the LLM sees the correct conversation role,
    # but display_role="assistant" so the UI shows the assistant icon —
    # this message is system-assembled, not typed by the farmer.
    session.chat_history.append({
        "role": "user",
        "display_role": "assistant",
        "content": user_msg_content,
    })
    update_session_crop_disease(session, result.crop_name, result.disease_name)
    set_chat_mode("ACTIVE_TREATMENT")

    # ------------------------------------------------------------------
    # Phase 1: JSON medicine plan (blocking)
    # ------------------------------------------------------------------
    auto_entries: list[MedicineEntry] = []
    medicine_table_md = ""
    try:
        messages_p1 = summarizer.messages_for_groq(session)
        json_raw = groq_client.complete(messages_p1, MEDICINE_JSON_SYSTEM_PROMPT)
        auto_entries, medicine_table_md = _parse_and_save_medicines(
            json_raw, session.session_id
        )
    except Exception:
        LOGGER.exception("Phase-1 medicine JSON call failed")

    if medicine_table_md:
        append_message(session, "assistant", medicine_table_md)

    # ------------------------------------------------------------------
    # Phase 2: Summary stream (lazy — Groq connection opens when iterated)
    # ------------------------------------------------------------------
    messages_p2 = summarizer.messages_for_groq(session)
    summary_iter = groq_client.stream(messages_p2, CROP_CONDITION_SUMMARY_SYSTEM_PROMPT)

    return AnalysisResponse(
        is_unreliable=unreliable,
        auto_medicine_entries=auto_entries,
        medicine_table_markdown=medicine_table_md,
        summary_stream=summary_iter,
    )


def handle_image_analysis(result, user_message: str, session: CropSession) -> AnalysisResponse:
    return _handle_analysis_common(result, user_message, session)


def handle_camera_analysis(result, user_message: str, session: CropSession) -> AnalysisResponse:
    return _handle_analysis_common(result, user_message, session)


# ---------------------------------------------------------------------------
# Text clarification path
# ---------------------------------------------------------------------------

def handle_text_message(
    user_text: str,
    session: CropSession,
) -> ClarificationResult | Iterator[str]:
    """Process one turn in the clarification loop or ongoing treatment chat."""
    import streamlit as st

    mode = st.session_state.get("chat_mode", "CLARIFYING")

    if mode == "ACTIVE_TREATMENT":
        return _handle_followup(user_text, session)

    append_message(session, "user", user_text)

    failures = (
        session.clarification_state.get("consecutive_failures", 0)
        if session.clarification_state else 0
    )
    result = clarification.process_turn(
        messages=list(session.chat_history),
        consecutive_failures=failures,
    )

    if result.question is None and not result.resolved:
        failures += 1
    else:
        failures = 0

    session.clarification_state = {"consecutive_failures": failures}

    if result.resolved:
        med_block = _load_medication_block(
            result.crop_type or "",
            _canonical_disease_from_symptoms(result.symptoms_summary or ""),
        )
        treatment_content = TEXT_PATH_USER_MESSAGE_TEMPLATE.format(
            crop_type=result.crop_type or "Unknown",
            symptoms_summary=result.symptoms_summary or "",
            medication_block=med_block,
            user_message="Please provide a treatment plan based on the above.",
        )
        append_message(session, "user", treatment_content)
        update_session_crop_disease(
            session,
            result.crop_type or "Unknown",
            "Text-described (unconfirmed)",
        )
        set_chat_mode("ACTIVE_TREATMENT")
        messages = summarizer.messages_for_groq(session)
        return groq_client.stream(messages, TREATMENT_SYSTEM_PROMPT)

    question = result.question or clarification._FALLBACK_QUESTION
    append_message(session, "assistant", question)
    return result


def _handle_followup(user_text: str, session: CropSession) -> Iterator[str]:
    """Handle a follow-up message during the ACTIVE_TREATMENT phase."""
    append_message(session, "user", user_text)
    messages = summarizer.messages_for_groq(session)
    return groq_client.stream(messages, TREATMENT_SYSTEM_PROMPT)


# ---------------------------------------------------------------------------
# Disease name helpers
# ---------------------------------------------------------------------------

def _canonical_disease_key(crop_name: str, display_name: str) -> str:
    _corn_map = {
        "Healthy": "healthy",
        "Gray Leaf Spot": "gray_leaf",
        "Blight": "blight",
        "Rust": "rust",
    }
    _grape_map = {
        "Healthy Grape Vine": "Healthy Grape Vine",
        "Black Rot Grape Vine": "Black Rot Grape Vine",
        "Blight Grape Vine": "Blight Grape Vine",
    }
    if crop_name == "Corn":
        return _corn_map.get(display_name, display_name)
    return _grape_map.get(display_name, display_name)


def _canonical_disease_from_symptoms(symptoms_summary: str) -> str:
    lower = symptoms_summary.lower()
    if "rust" in lower:
        return "rust"
    if "gray leaf" in lower or "grey leaf" in lower:
        return "gray_leaf"
    if "blight" in lower and "grape" not in lower:
        return "blight"
    if "black rot" in lower:
        return "Black Rot Grape Vine"
    if "blight" in lower and "grape" in lower:
        return "Blight Grape Vine"
    return ""
