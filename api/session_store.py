"""In-memory CropSession store — the API-layer replacement for st.session_state.

The Streamlit app kept CropSession objects (with their live chat_history and
last AnalysisResult) in st.session_state, and persisted only metadata + medicine
entries + the rolling summary to SQLite. This store reproduces that contract for
a long-lived server process: full chat history lives in RAM; SQLite remains the
source of truth for session metadata and the medicine log.

Per-session UI "mode" (CLARIFYING / ACTIVE_TREATMENT / ...) is tracked here too,
replacing the single global st.session_state.chat_mode.
"""

from __future__ import annotations

import threading
from datetime import datetime
from uuid import uuid4

from tracking import persistence
from tracking.models import CropSession

# Mirrors chatbot.state.ChatMode values; default for a fresh session.
DEFAULT_MODE = "ONBOARDING"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, CropSession] = {}
        self._modes: dict[str, str] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def ensure_loaded(self) -> None:
        """Load persisted sessions from SQLite once (like init_session_state)."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            persistence.init_db()
            for session in persistence.load_sessions():
                self._sessions[session.session_id] = session
            self._loaded = True

    def list(self) -> list[CropSession]:
        self.ensure_loaded()
        return sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )

    def get(self, session_id: str) -> CropSession | None:
        self.ensure_loaded()
        return self._sessions.get(session_id)

    def create(self, display_name: str) -> CropSession:
        self.ensure_loaded()
        session = CropSession(
            session_id=str(uuid4()),
            display_name=display_name.strip() or "Untitled Session",
            crop_name=None,
            disease_name=None,
            created_at=datetime.now(),
        )
        persistence.init_db()
        persistence.save_session(session)
        with self._lock:
            self._sessions[session.session_id] = session
            self._modes[session.session_id] = DEFAULT_MODE
        return session

    def delete(self, session_id: str) -> None:
        self.ensure_loaded()
        persistence.delete_session(session_id)
        with self._lock:
            self._sessions.pop(session_id, None)
            self._modes.pop(session_id, None)

    def get_mode(self, session_id: str) -> str:
        return self._modes.get(session_id, DEFAULT_MODE)

    def set_mode(self, session_id: str, mode: str) -> None:
        with self._lock:
            self._modes[session_id] = mode
