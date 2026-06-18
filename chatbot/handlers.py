"""Message routing, inconclusiveness checks, and Groq call orchestration.

Three public entry points:
  handle_image_analysis(result, user_message, session) -> str | Iterator[str]
  handle_camera_analysis(result, user_message, session) -> str | Iterator[str]
  handle_text_message(user_text, session) -> ClarificationResult | Iterator[str]

All Groq calls happen here in the main Streamlit thread.
The VideoProcessor never calls into this module.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from chatbot import groq_client, clarification, summarizer
from chatbot.prompts import (
    TREATMENT_SYSTEM_PROMPT,
    ANALYSIS_USER_MESSAGE_TEMPLATE,
    TEXT_PATH_USER_MESSAGE_TEMPLATE,
    INCONCLUSIVE_RESPONSE,
    NO_MEDICATION_DATA_RESPONSE,
)
from chatbot.clarification import ClarificationResult
from chatbot.state import append_message, set_chat_mode, update_session_crop_disease
from crop_detection.disease_logic import Detection
from tracking.models import CropSession

_MEDICATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "medications.json"
_INCONCLUSIVENESS_TOP_CONF_THRESHOLD = 0.50
_INCONCLUSIVENESS_GAP_THRESHOLD = 0.15
_DETECTION_DISPLAY_THRESHOLD = 0.15   # only show detections above this in Groq prompt


# ---------------------------------------------------------------------------
# Inconclusiveness check
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
    """Return a formatted medication block for the Groq prompt.

    Falls back to NO_MEDICATION_DATA_RESPONSE string if no entry found.
    """
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


def _load_medications_raw(crop_name: str, disease_canonical: str) -> list[dict]:
    """Return the raw list of medication dicts for a crop+disease, or [].

    Unlike _load_medication_block (which formats a string for the Groq prompt),
    this returns the structured entries so other code (e.g. the medicine
    tracker auto-fill) can match trade names and read dosage_rate directly.
    """
    if not _MEDICATIONS_PATH.is_file():
        return []
    try:
        with open(_MEDICATIONS_PATH, encoding="utf-8") as f:
            db = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    crop_key = crop_name.lower()
    diseases = db.get("diseases", {}).get(crop_key, {})
    entry = diseases.get(disease_canonical)
    if not entry:
        return []
    return entry.get("medications", [])


def find_mentioned_medications(
    crop_name: str,
    disease_canonical: str,
    response_text: str,
) -> list[dict]:
    """Return medication dicts (from medications.json) whose trade_name appears
    in the LLM's treatment-plan response text.

    Used to auto-fill the medicine tracker right after a treatment plan streams
    in — matches against only the medications already known for this crop and
    disease, so unrelated trade names elsewhere in the file can't false-match.
    """
    meds = _load_medications_raw(crop_name, disease_canonical)
    if not meds:
        return []

    lower_text = response_text.lower()
    matched = []
    for med in meds:
        trade_name = med.get("trade_name", "")
        if not trade_name:
            continue
        # Use the part before any parenthetical, e.g. "Mancozeb (various brands)" -> "Mancozeb"
        primary_name = trade_name.split("(")[0].strip().lower()
        if primary_name and primary_name in lower_text:
            matched.append(med)
    return matched


# ---------------------------------------------------------------------------
# Image analysis handlers (upload and camera share the same core)
# ---------------------------------------------------------------------------

def _handle_analysis_common(
    result,  # AnalysisResult
    user_message: str,
    session: CropSession,
) -> str | Iterator[str]:
    """Shared logic for both upload and camera-capture paths."""
    if is_inconclusive(result.all_disease_detections):
        append_message(session, "assistant", INCONCLUSIVE_RESPONSE)
        return INCONCLUSIVE_RESPONSE

    crop_assumption_note = (
        "\n(Grape was assumed — no Corn detection found)"
        if result.crop_was_assumed else ""
    )
    fallback_note = (
        "\n(Healthy fallback applied — no qualifying disease detected)"
        if result.disease_was_fallback else ""
    )

    # disease_name here is the display name; we need the canonical name for the DB lookup.
    # We reverse-map via the internal name stored in result.
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
        user_message=user_message or "Please explain the results and provide a treatment plan.",
    )

    display_text = (
        f"Analyzed image — detected **{result.crop_name}** "
        f"with **{result.disease_name}** "
        f"({result.disease_confidence:.0%} confidence)."
    )
    if user_message:
        display_text += f"\n\n{user_message}"

    append_message(session, "user", user_msg_content, display_content=display_text)
    update_session_crop_disease(session, result.crop_name, result.disease_name)
    set_chat_mode("ACTIVE_TREATMENT")

    messages = summarizer.messages_for_groq(session)
    response_iter = groq_client.stream(messages, TREATMENT_SYSTEM_PROMPT)
    return response_iter


def handle_image_analysis(result, user_message: str, session: CropSession):
    return _handle_analysis_common(result, user_message, session)


def handle_camera_analysis(result, user_message: str, session: CropSession):
    return _handle_analysis_common(result, user_message, session)


# ---------------------------------------------------------------------------
# Text clarification path
# ---------------------------------------------------------------------------

def handle_text_message(
    user_text: str,
    session: CropSession,
) -> ClarificationResult | Iterator[str]:
    """Process one turn in the clarification loop or ongoing treatment chat.

    In CLARIFYING mode:  returns a ClarificationResult.
    In ACTIVE_TREATMENT: returns a streaming Groq response.
    """
    import streamlit as st

    mode = st.session_state.get("chat_mode", "CLARIFYING")

    if mode == "ACTIVE_TREATMENT":
        return _handle_followup(user_text, session)

    # CLARIFYING mode
    append_message(session, "user", user_text)

    failures = session.clarification_state.get("consecutive_failures", 0) if session.clarification_state else 0
    result = clarification.process_turn(
        messages=[{"role": m["role"], "content": m["content"]} for m in session.chat_history],
        consecutive_failures=failures,
    )

    if result.question is None and not result.resolved:
        failures += 1
    else:
        failures = 0

    session.clarification_state = {"consecutive_failures": failures}

    if result.resolved:
        # Transition to treatment
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
        display_text = (
            f"Based on what you've described — **{result.crop_type or 'Unknown crop'}**, "
            f"{result.symptoms_summary or 'symptoms as described'} — here's a treatment plan."
        )
        append_message(session, "user", treatment_content, display_content=display_text)
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
    """Map display disease name back to the key used in medications.json."""
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
    """Best-effort disease key lookup from free-text symptom summary.

    This is used only for the text path where no YOLO data exists.
    The medication block will be empty if no match is found, and the LLM
    is instructed to say so rather than guessing.
    """
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
    return ""  # empty → no medication data → LLM defers to extension professional