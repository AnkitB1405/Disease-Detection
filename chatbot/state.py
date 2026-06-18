"""Session state schema and initializer for the chatbot UI.

This module defines every key written to st.session_state and provides
init_session_state() which is called once at the top of streamlit_main().
No business logic lives here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from tracking.models import CropSession
from tracking import persistence

ChatMode = Literal[
    "ONBOARDING",       # landing page with 5 navigation options
    "AWAITING_UPLOAD",  # file uploader is rendered
    "AWAITING_CAPTURE", # WebRTC streamer is rendered
    "CLARIFYING",       # text clarification loop is active
    "ACTIVE_TREATMENT", # confirmed detection, ongoing treatment chat
    "PAST_SESSIONS",    # full list of all sessions
    "MEDICINE_TABLE",   # focused medicine tracking panel
]


def init_session_state() -> None:
    """Populate st.session_state with all keys used by the app.

    Safe to call on every rerun — only sets keys that do not yet exist.
    Loads persisted sessions and medicine entries from SQLite on first call.
    """
    import streamlit as st

    if "sessions_loaded" not in st.session_state:
        persisted = persistence.load_sessions()
        existing: dict[str, CropSession] = {s.session_id: s for s in persisted}
        st.session_state.crop_sessions = existing
        st.session_state.sessions_loaded = True

    if "crop_sessions" not in st.session_state:
        st.session_state.crop_sessions = {}

    if "active_crop_session_id" not in st.session_state:
        st.session_state.active_crop_session_id = None

    if "chat_mode" not in st.session_state:
        st.session_state.chat_mode = "ONBOARDING"

    # WebRTC frame sharing — unchanged from original app
    if "latest_frame" not in st.session_state:
        st.session_state.latest_frame = None
    if "captured_frame" not in st.session_state:
        st.session_state.captured_frame = None
    if "latest_detection" not in st.session_state:
        st.session_state.latest_detection = None

    if "groq_thinking" not in st.session_state:
        st.session_state.groq_thinking = False

    if "show_medicine_panel" not in st.session_state:
        st.session_state.show_medicine_panel = False


def active_session() -> CropSession | None:
    """Return the currently active CropSession, or None if none selected."""
    import streamlit as st

    sid = st.session_state.get("active_crop_session_id")
    if sid is None:
        return None
    return st.session_state.crop_sessions.get(sid)


def create_new_session(display_name: str) -> CropSession:
    """Create a session, persist its metadata, and make it active."""
    import streamlit as st

    session = CropSession(
        session_id=str(uuid4()),
        display_name=display_name,
        crop_name=None,
        disease_name=None,
        created_at=datetime.now(),
    )
    st.session_state.crop_sessions[session.session_id] = session
    st.session_state.active_crop_session_id = session.session_id
    st.session_state.chat_mode = "ONBOARDING"
    persistence.init_db()
    persistence.save_session(session)
    return session


def append_message(session: CropSession, role: str, content: str) -> None:
    """Append one message to the session's in-memory chat history."""
    session.chat_history.append({"role": role, "content": content})


def set_chat_mode(mode: ChatMode) -> None:
    import streamlit as st
    st.session_state.chat_mode = mode


def update_session_crop_disease(
    session: CropSession,
    crop_name: str,
    disease_name: str,
) -> None:
    """Persist crop/disease after a confirmed detection or clarification."""
    session.crop_name = crop_name
    session.disease_name = disease_name
    persistence.save_session(session)
