# Ishaan's Tasks — Developer C (Persistence, Medicine Tracking)

## Your Ownership

| File | Status |
|------|--------|
| `tracking/models.py` | **Yours — PR #1, Day 1, blocks everyone** |
| `tracking/__init__.py` | Yours |
| `tracking/persistence.py` | Yours |
| `tracking/tracker_ui.py` | Yours |
| `tests/test_persistence.py` | Yours |

You do **not** edit `app.py`, `chatbot/`, or `crop_detection/`. If you need a field added to how sessions are used in the UI, raise it with Ankit.

---

## Critical: Day 1 PR

**Your first and most important task is to commit the skeleton `tracking/models.py`.**

Ankit needs `CropSession` to start writing `chatbot/state.py`. Suhaan needs `CropSession` to understand the data structure their Groq code will populate. Neither can start until this is merged.

The skeleton needs only:
1. The `MedicineEntry` dataclass (all fields)
2. The `CropSession` dataclass (all fields)

No persistence logic, no Streamlit code. Just the dataclasses. This file is already written — review it at `tracking/models.py` and confirm the schema is correct before Ankit and Suhaan start work.

**Coordinate before committing** — once the field names are agreed on, they must not change without a coordinated PR because Ankit imports `CropSession` and Suhaan's handlers reference its fields.

---

## Data Models (already written — review and confirm)

### `MedicineEntry` fields

| Field | Type | Purpose |
|-------|------|---------|
| `entry_id` | `str` | UUID primary key |
| `session_id` | `str` | FK to the parent `CropSession` |
| `week_number` | `int` | 1-based treatment week |
| `date_applied` | `date` | When treatment was applied |
| `medicine_id` | `str` | References `medications.json` — use `"manual"` for user-entered entries |
| `medicine_name` | `str` | Denormalized display name |
| `dosage_applied` | `str` | Actual dose used (free text) |
| `application_method` | `str` | e.g. "Foliar Spray" |
| `symptom_severity` | `int` | 1–5 severity scale |
| `notes` | `str` | Farmer observations |
| `is_improving` | `bool \| None` | None = too early; True/False = farmer assessment |

### `CropSession` fields

| Field | Type | Purpose |
|-------|------|---------|
| `session_id` | `str` | UUID primary key |
| `display_name` | `str` | User-editable label, e.g. "Corn Field A" |
| `crop_name` | `str \| None` | Set after first analysis |
| `disease_name` | `str \| None` | Set after first analysis |
| `created_at` | `datetime` | Creation timestamp |
| `chat_history` | `list[dict]` | In-memory only — NOT persisted to SQLite |
| `chat_summary` | `str \| None` | Rolling summary — IS persisted to SQLite |
| `analysis_result` | `Any \| None` | Last YOLO result — in-memory only |
| `clarification_state` | `dict \| None` | Tracks JSON parse failure count |
| `medicine_entries` | `list[MedicineEntry]` | Loaded from SQLite on startup |

---

## SQLite Layer (`tracking/persistence.py`) — already written

Review the implementation at `tracking/persistence.py`. Key functions:

```python
init_db() -> None              # creates tables if absent
save_session(session) -> None  # upsert — safe to call multiple times
load_sessions() -> list[CropSession]  # loads all sessions + their medicine entries
delete_session(session_id) -> None    # CASCADE deletes medicine_log rows too
save_medicine_entry(entry) -> None    # upsert
load_medicine_entries(session_id) -> list[MedicineEntry]
delete_medicine_entry(entry_id) -> None
set_db_path(path) -> None      # used in tests to point at a temp DB
```

### SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS crop_sessions (
    session_id   TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    crop_name    TEXT,
    disease_name TEXT,
    created_at   TEXT NOT NULL,
    chat_summary TEXT          -- rolling summary; NULL until first summarization
);

CREATE TABLE IF NOT EXISTS medicine_log (
    entry_id           TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES crop_sessions(session_id) ON DELETE CASCADE,
    week_number        INTEGER NOT NULL,
    date_applied       TEXT NOT NULL,     -- ISO date string
    medicine_id        TEXT NOT NULL,
    medicine_name      TEXT NOT NULL,
    dosage_applied     TEXT,
    application_method TEXT,
    symptom_severity   INTEGER CHECK(symptom_severity BETWEEN 1 AND 5),
    notes              TEXT,
    is_improving       INTEGER            -- NULL / 0 / 1
);
```

The database file is `tracking.db` in the project root.

---

## Medicine Tracking UI (`tracking/tracker_ui.py`) — already written

Review the implementation. Key function:

```python
render_tracking_panel(session_id: str, disease_name: str | None) -> None
```

Called by Ankit from `app.py` inside a `st.expander`. This function:
1. Calls `persistence.load_medicine_entries(session_id)` for current data
2. Renders an "Add This Week's Treatment" form
3. On save, calls `persistence.save_medicine_entry(entry)`
4. Renders the full treatment log as a `st.dataframe`
5. Renders a `st.bar_chart` showing symptom severity by week

### Medicine ID and medications.json

The `medicine_id` field links to the `id` field in `data/medications.json`. For entries the farmer types manually (not from Groq's treatment plan), use `medicine_id = "manual"`. The `medicine_name` field is always the human-readable name.

---

## Tests (`tests/test_persistence.py`) — already written

The test file uses `pytest`'s `tmp_path` fixture to create an isolated temporary database for each test. The `set_db_path()` function in persistence.py is the escape hatch that makes this possible.

Run tests:
```bash
python -m pytest tests/test_persistence.py -v
```

---

## What to Extend (if needed)

If Ankit asks for a new field in `CropSession` or `MedicineEntry`:
1. Add the field to the dataclass in `tracking/models.py`
2. Add the column to the SQLite schema in `persistence.py` (`CREATE TABLE` statement)
3. Update `save_session()` or `save_medicine_entry()` INSERT/UPDATE statements
4. Update `load_sessions()` or `load_medicine_entries()` to read the new column
5. Add a test in `test_persistence.py`
6. Notify Ankit and Suhaan so they can update any code that constructs `CropSession` or `MedicineEntry` objects

---

## Verification Checklist (your responsibility)

- [ ] `python -m pytest tests/test_persistence.py -v` — all tests pass
- [ ] `tracking/models.py` schema agreed with Ankit and Suhaan on Day 1
- [ ] Creating a session writes to `tracking.db`
- [ ] Adding a medicine entry writes to `tracking.db`
- [ ] Closing and reopening the browser shows previously saved sessions and entries
- [ ] Deleting a session removes it AND its medicine entries from SQLite
- [ ] The medicine tracker form saves entries and they appear in the table immediately after `st.rerun()`
- [ ] The severity sparkline appears after two or more weeks of entries
- [ ] `set_db_path(None)` restores the default path after each test (see fixture in test file)
