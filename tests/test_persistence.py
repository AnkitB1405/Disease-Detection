"""Tests for tracking/persistence.py — uses tmp_path, no production DB touched."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from tracking import persistence
from tracking.models import CropSession, MedicineEntry


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    """Point the persistence module at a temporary database for each test."""
    persistence.set_db_path(tmp_path / "test.db")
    persistence.init_db()
    yield
    persistence.set_db_path(None)  # type: ignore[arg-type]


def _make_session(name: str = "Test Field") -> CropSession:
    return CropSession(
        session_id=str(__import__("uuid").uuid4()),
        display_name=name,
        crop_name="Corn",
        disease_name="rust",
        created_at=datetime.now(),
    )


def _make_entry(session_id: str, week: int = 1) -> MedicineEntry:
    return MedicineEntry(
        entry_id=str(__import__("uuid").uuid4()),
        session_id=session_id,
        week_number=week,
        date_applied=date.today(),
        medicine_id="corn_rust_001",
        medicine_name="Headline",
        dosage_applied="10 fl oz/acre",
        application_method="Foliar Spray",
        symptom_severity=3,
        notes="First application",
        is_improving=None,
    )


def test_save_and_load_session():
    session = _make_session("Corn Field A")
    persistence.save_session(session)

    loaded = persistence.load_sessions()
    assert len(loaded) == 1
    assert loaded[0].display_name == "Corn Field A"
    assert loaded[0].crop_name == "Corn"


def test_update_session_display_name():
    session = _make_session("Original Name")
    persistence.save_session(session)

    session.display_name = "Updated Name"
    persistence.save_session(session)

    loaded = persistence.load_sessions()
    assert len(loaded) == 1
    assert loaded[0].display_name == "Updated Name"


def test_save_and_load_medicine_entry():
    session = _make_session()
    persistence.save_session(session)

    entry = _make_entry(session.session_id, week=1)
    persistence.save_medicine_entry(entry)

    entries = persistence.load_medicine_entries(session.session_id)
    assert len(entries) == 1
    assert entries[0].medicine_name == "Headline"
    assert entries[0].week_number == 1
    assert entries[0].is_improving is None


def test_medicine_entry_is_improving_true():
    session = _make_session()
    persistence.save_session(session)

    entry = _make_entry(session.session_id)
    entry = MedicineEntry(
        **{**entry.__dict__, "is_improving": True}
    )
    persistence.save_medicine_entry(entry)

    loaded = persistence.load_medicine_entries(session.session_id)
    assert loaded[0].is_improving is True


def test_medicine_entry_is_improving_false():
    session = _make_session()
    persistence.save_session(session)

    entry = _make_entry(session.session_id)
    entry = MedicineEntry(**{**entry.__dict__, "is_improving": False})
    persistence.save_medicine_entry(entry)

    loaded = persistence.load_medicine_entries(session.session_id)
    assert loaded[0].is_improving is False


def test_delete_session_cascades_medicine_entries():
    session = _make_session()
    persistence.save_session(session)
    persistence.save_medicine_entry(_make_entry(session.session_id, 1))
    persistence.save_medicine_entry(_make_entry(session.session_id, 2))

    persistence.delete_session(session.session_id)

    sessions = persistence.load_sessions()
    assert sessions == []

    entries = persistence.load_medicine_entries(session.session_id)
    assert entries == []


def test_multiple_sessions_isolated():
    s1 = _make_session("Field A")
    s2 = _make_session("Field B")
    persistence.save_session(s1)
    persistence.save_session(s2)
    persistence.save_medicine_entry(_make_entry(s1.session_id, 1))

    entries_s1 = persistence.load_medicine_entries(s1.session_id)
    entries_s2 = persistence.load_medicine_entries(s2.session_id)

    assert len(entries_s1) == 1
    assert len(entries_s2) == 0


def test_chat_summary_persisted():
    session = _make_session()
    session.chat_summary = "Farmer applied fungicide in week 1. Improvement noted."
    persistence.save_session(session)

    loaded = persistence.load_sessions()
    assert loaded[0].chat_summary == "Farmer applied fungicide in week 1. Improvement noted."
