"""Orchestration layer — the Streamlit-free port of chatbot/handlers.py.

The pure, deterministic helpers (inconclusiveness, medication lookup, JSON
medicine parsing, disease-key mapping) are imported directly from
chatbot.handlers so behavior stays byte-for-byte identical and there is a single
source of truth. Only the parts that touched st.session_state / st.write_stream
are reimplemented here against the in-memory SessionStore and as plain
generators the routers expose over SSE.

Flow parity with the Streamlit app:
  /analyze            -> analyze_phase1()  (blocking: medicine JSON -> SQLite)
  /analyze/summary    -> summary_tokens()  (Phase-2 streamed condition summary)
  /messages (SSE)     -> message_events()  (clarification loop OR followup chat)
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from chatbot import groq_client, clarification, summarizer
from chatbot.handlers import (
    is_inconclusive,
    _load_medication_block,
    _format_all_detections,
    _parse_and_save_medicines,
    _canonical_disease_key,
    _canonical_disease_from_symptoms,
)
from chatbot.prompts import (
    TREATMENT_SYSTEM_PROMPT,
    MEDICINE_JSON_SYSTEM_PROMPT,
    CROP_CONDITION_SUMMARY_SYSTEM_PROMPT,
    ANALYSIS_USER_MESSAGE_TEMPLATE,
    TEXT_PATH_USER_MESSAGE_TEMPLATE,
)
from tracking import persistence
from tracking.models import CropSession, MedicineEntry
from api.session_store import SessionStore

LOGGER = logging.getLogger("api.services")


# --------------------------------------------------------------------------- #
# Small session helpers (replace chatbot.state.* without Streamlit)
# --------------------------------------------------------------------------- #
def _update_crop_disease(session: CropSession, crop_name: str, disease_name: str) -> None:
    session.crop_name = crop_name
    session.disease_name = disease_name
    persistence.save_session(session)


def visible_history(session: CropSession) -> list[dict]:
    """Client-facing chat history: drop system + system-assembled context dumps."""
    out: list[dict] = []
    for m in session.chat_history:
        if m.get("hidden") or m["role"] == "system":
            continue
        out.append({"role": m.get("display_role", m["role"]), "content": m["content"]})
    return out


# --------------------------------------------------------------------------- #
# Image / camera analysis — Phase 1 (blocking)
# --------------------------------------------------------------------------- #
def analyze_phase1(
    session: CropSession,
    result,                 # crop_detection.predictor.AnalysisResult
    user_message: str,
    store: SessionStore,
) -> tuple[bool, list[MedicineEntry], str]:
    """Mirror handlers._handle_analysis_common up to the end of Phase 1.

    Returns (is_unreliable, saved_medicine_entries, medicine_table_markdown).
    Mutates session: stores AnalysisResult, appends the (hidden) LLM context
    message and the visible medicine table, sets mode to ACTIVE_TREATMENT.
    """
    unreliable = is_inconclusive(result.all_disease_detections)
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

    # role "user" so Groq treats it as input; hidden so the farmer never sees the
    # raw context dump. This is the conversation anchor (summarizer pins index 0).
    session.chat_history.append({
        "role": "user",
        "display_role": "assistant",
        "content": user_msg_content,
        "hidden": True,
    })
    _update_crop_disease(session, result.crop_name, result.disease_name)
    store.set_mode(session.session_id, "ACTIVE_TREATMENT")

    # Phase 1: structured medicine JSON -> parsed -> saved to SQLite (blocking).
    auto_entries: list[MedicineEntry] = []
    medicine_table_md = ""
    try:
        messages_p1 = summarizer.messages_for_groq(session)
        json_raw = groq_client.complete(messages_p1, MEDICINE_JSON_SYSTEM_PROMPT)
        auto_entries, medicine_table_md = _parse_and_save_medicines(
            json_raw, session.session_id
        )
    except Exception:  # noqa: BLE001 - parity with handlers (never crash analysis)
        LOGGER.exception("Phase-1 medicine JSON call failed")

    if medicine_table_md:
        session.chat_history.append({"role": "assistant", "content": medicine_table_md})

    return unreliable, auto_entries, medicine_table_md


# --------------------------------------------------------------------------- #
# Image / camera analysis — Phase 2 (streamed condition summary)
# --------------------------------------------------------------------------- #
def summary_tokens(session: CropSession) -> Iterator[str]:
    """Stream the Phase-2 condition summary, appending the full text on close."""
    messages = summarizer.messages_for_groq(session)
    chunks: list[str] = []
    for token in groq_client.stream(messages, CROP_CONDITION_SUMMARY_SYSTEM_PROMPT):
        chunks.append(token)
        yield token
    full = "".join(chunks).strip()
    if full:
        session.chat_history.append({"role": "assistant", "content": full})


# --------------------------------------------------------------------------- #
# Text chat — clarification loop and follow-up treatment chat
# --------------------------------------------------------------------------- #
def _stream_treatment(session: CropSession, system_prompt: str) -> Iterator[dict]:
    messages = summarizer.messages_for_groq(session)
    chunks: list[str] = []
    for token in groq_client.stream(messages, system_prompt):
        chunks.append(token)
        yield {"type": "token", "content": token}
    full = "".join(chunks).strip()
    if full:
        session.chat_history.append({"role": "assistant", "content": full})


def message_events(
    session: CropSession,
    user_text: str,
    store: SessionStore,
) -> Iterator[dict]:
    """Port of handlers.handle_text_message as an event generator.

    Yields {"type": "question"|"token", "content": str}. The router appends a
    final {"type": "done"} sentinel.
    """
    mode = store.get_mode(session.session_id)

    if mode == "ACTIVE_TREATMENT":
        session.chat_history.append({"role": "user", "content": user_text})
        yield from _stream_treatment(session, TREATMENT_SYSTEM_PROMPT)
        return

    # Clarification loop
    session.chat_history.append({"role": "user", "content": user_text})
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
        # Hidden context dump (LLM sees it; farmer does not).
        session.chat_history.append({
            "role": "user", "content": treatment_content, "hidden": True,
        })
        _update_crop_disease(
            session, result.crop_type or "Unknown", "Text-described (unconfirmed)"
        )
        store.set_mode(session.session_id, "ACTIVE_TREATMENT")
        yield from _stream_treatment(session, TREATMENT_SYSTEM_PROMPT)
        return

    question = result.question or clarification._FALLBACK_QUESTION
    session.chat_history.append({"role": "assistant", "content": question})
    yield {"type": "question", "content": question}
