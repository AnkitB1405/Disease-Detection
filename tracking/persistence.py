"""SQLite read/write layer for crop sessions and medicine log.

Single-user build — one tracking.db in the project root.
# SINGLE_USER: when adding multi-user support, add user_token column to both
# tables and filter all queries by it. See docs/MULTI_USER_UPGRADE.md.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from tracking.models import CropSession, MedicineEntry

_DB_PATH: Path | None = None


def _db_path() -> Path:
    if _DB_PATH is not None:
        return _DB_PATH
    return Path(__file__).resolve().parent.parent / "tracking.db"


def set_db_path(path: Path) -> None:
    """Override default DB location (used in tests)."""
    global _DB_PATH
    _DB_PATH = path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS crop_sessions (
                session_id   TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                crop_name    TEXT,
                disease_name TEXT,
                created_at   TEXT NOT NULL,
                chat_summary TEXT
            );

            CREATE TABLE IF NOT EXISTS medicine_log (
                entry_id           TEXT PRIMARY KEY,
                session_id         TEXT NOT NULL
                                       REFERENCES crop_sessions(session_id)
                                       ON DELETE CASCADE,
                week_number        INTEGER NOT NULL,
                date_applied       TEXT NOT NULL,
                medicine_id        TEXT NOT NULL,
                medicine_name      TEXT NOT NULL,
                dosage_applied     TEXT,
                application_method TEXT,
                symptom_severity   INTEGER CHECK(symptom_severity BETWEEN 1 AND 5),
                notes              TEXT,
                is_improving       INTEGER
            );
        """)


def save_session(session: CropSession) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO crop_sessions
                (session_id, display_name, crop_name, disease_name, created_at, chat_summary)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                display_name = excluded.display_name,
                crop_name    = excluded.crop_name,
                disease_name = excluded.disease_name,
                chat_summary = excluded.chat_summary
            """,
            (
                session.session_id,
                session.display_name,
                session.crop_name,
                session.disease_name,
                session.created_at.isoformat(),
                session.chat_summary,
            ),
        )


def load_sessions() -> list[CropSession]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM crop_sessions ORDER BY created_at DESC"
        ).fetchall()

    sessions = []
    for row in rows:
        entries = load_medicine_entries(row["session_id"])
        sessions.append(
            CropSession(
                session_id=row["session_id"],
                display_name=row["display_name"],
                crop_name=row["crop_name"],
                disease_name=row["disease_name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                chat_history=[],   # chat history is in-memory only
                chat_summary=row["chat_summary"],
                medicine_entries=entries,
            )
        )
    return sessions


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM crop_sessions WHERE session_id = ?", (session_id,)
        )


def save_medicine_entry(entry: MedicineEntry) -> None:
    init_db()
    is_improving_int: int | None = None
    if entry.is_improving is not None:
        is_improving_int = 1 if entry.is_improving else 0

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO medicine_log
                (entry_id, session_id, week_number, date_applied,
                 medicine_id, medicine_name, dosage_applied,
                 application_method, symptom_severity, notes, is_improving)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                week_number        = excluded.week_number,
                date_applied       = excluded.date_applied,
                medicine_id        = excluded.medicine_id,
                medicine_name      = excluded.medicine_name,
                dosage_applied     = excluded.dosage_applied,
                application_method = excluded.application_method,
                symptom_severity   = excluded.symptom_severity,
                notes              = excluded.notes,
                is_improving       = excluded.is_improving
            """,
            (
                entry.entry_id,
                entry.session_id,
                entry.week_number,
                entry.date_applied.isoformat(),
                entry.medicine_id,
                entry.medicine_name,
                entry.dosage_applied,
                entry.application_method,
                entry.symptom_severity,
                entry.notes,
                is_improving_int,
            ),
        )


def load_medicine_entries(session_id: str) -> list[MedicineEntry]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM medicine_log WHERE session_id = ? ORDER BY week_number, date_applied",
            (session_id,),
        ).fetchall()

    entries = []
    for row in rows:
        is_improving: bool | None = None
        if row["is_improving"] is not None:
            is_improving = bool(row["is_improving"])
        entries.append(
            MedicineEntry(
                entry_id=row["entry_id"],
                session_id=row["session_id"],
                week_number=row["week_number"],
                date_applied=date.fromisoformat(row["date_applied"]),
                medicine_id=row["medicine_id"],
                medicine_name=row["medicine_name"],
                dosage_applied=row["dosage_applied"] or "",
                application_method=row["application_method"] or "",
                symptom_severity=row["symptom_severity"],
                notes=row["notes"] or "",
                is_improving=is_improving,
            )
        )
    return entries


def delete_medicine_entry(entry_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            "DELETE FROM medicine_log WHERE entry_id = ?", (entry_id,)
        )


def new_entry_id() -> str:
    return str(uuid4())
