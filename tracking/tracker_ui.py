"""Streamlit medicine tracking table and sparkline component.

This is the only file in the tracking/ package that imports Streamlit.
All other tracking modules are pure Python.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pandas as pd

from tracking.models import MedicineEntry
from tracking import persistence


def render_tracking_panel(session_id: str, disease_name: str | None) -> None:
    """Render the medicine log table and week-over-week severity chart."""
    import streamlit as st

    st.subheader("Medicine & Progress Tracker")
    st.caption(
        "Log each week's treatment here. All entries are saved automatically "
        "and persist between browser sessions."
    )

    entries = persistence.load_medicine_entries(session_id)

    _render_add_entry_form(session_id, disease_name, entries)
    st.divider()

    if not entries:
        st.info("No treatment entries yet. Add your first entry above.")
        return

    _render_table(session_id, entries)
    st.divider()
    _render_sparkline(entries)


def _render_add_entry_form(
    session_id: str,
    disease_name: str | None,
    existing_entries: list[MedicineEntry],
) -> None:
    import streamlit as st

    next_week = max((e.week_number for e in existing_entries), default=0) + 1

    with st.expander("Add This Week's Treatment", expanded=not existing_entries):
        col1, col2 = st.columns(2)
        with col1:
            week_num = st.number_input(
                "Week #", min_value=1, value=next_week, step=1, key=f"week_{session_id}"
            )
            medicine_name = st.text_input(
                "Medicine / Treatment Name",
                key=f"med_name_{session_id}",
                help="Use the name recommended in the treatment plan.",
            )
            dosage = st.text_input(
                "Dosage Applied",
                placeholder="e.g. 10 ml/L",
                key=f"dosage_{session_id}",
            )
        with col2:
            date_applied = st.date_input(
                "Date Applied", value=date.today(), key=f"date_{session_id}"
            )
            method = st.selectbox(
                "Application Method",
                ["Foliar Spray", "Soil Drench", "Seed Treatment", "Other"],
                key=f"method_{session_id}",
            )
            severity = st.slider(
                "Symptom Severity (1 = trace, 5 = severe)",
                min_value=1,
                max_value=5,
                value=3,
                key=f"severity_{session_id}",
            )

        improving_map = {"Too early to tell": None, "Yes": True, "No": False}
        improving_label = st.radio(
            "Is the crop improving?",
            list(improving_map.keys()),
            horizontal=True,
            key=f"improving_{session_id}",
        )
        notes = st.text_area("Notes", key=f"notes_{session_id}", height=80)

        if st.button("Save Entry", type="primary", key=f"save_{session_id}"):
            if not medicine_name.strip():
                st.warning("Please enter a medicine or treatment name.")
            else:
                entry = MedicineEntry(
                    entry_id=str(uuid4()),
                    session_id=session_id,
                    week_number=int(week_num),
                    date_applied=date_applied,
                    medicine_id="manual",
                    medicine_name=medicine_name.strip(),
                    dosage_applied=dosage.strip(),
                    application_method=method,
                    symptom_severity=severity,
                    notes=notes.strip(),
                    is_improving=improving_map[improving_label],
                )
                persistence.save_medicine_entry(entry)
                st.success("Entry saved.")
                st.rerun()


def _render_table(session_id: str, entries: list[MedicineEntry]) -> None:
    """Render an editable treatment log table with inline edit and delete support."""
    import streamlit as st

    st.markdown("**Treatment Log**")
    st.caption(
        "Edit cells directly in the table below. "
        "Use the **Delete selected entries** section to remove rows."
    )

    # Build display dataframe (entry_id kept as index for reconciliation)
    rows = []
    for e in entries:
        improving_display = (
            "Yes" if e.is_improving is True
            else "No" if e.is_improving is False
            else "Too early"
        )
        rows.append({
            "entry_id": e.entry_id,
            "Week": e.week_number,
            "Date": e.date_applied.isoformat(),
            "Medicine": e.medicine_name,
            "Dosage": e.dosage_applied,
            "Method": e.application_method,
            "Severity (1–5)": e.symptom_severity,
            "Improving?": improving_display,
            "Notes": e.notes,
        })

    original_df = pd.DataFrame(rows)
    editor_key = f"med_editor_{session_id}"

    edited_df = st.data_editor(
        original_df.drop(columns=["entry_id"]),
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Week": st.column_config.NumberColumn("Week #", min_value=1, step=1),
            "Date": st.column_config.TextColumn("Date (YYYY-MM-DD)"),
            "Method": st.column_config.SelectboxColumn(
                "Method",
                options=["Foliar Spray", "Soil Drench", "Seed Treatment", "Other"],
            ),
            "Severity (1–5)": st.column_config.NumberColumn(
                "Severity (1–5)", min_value=1, max_value=5, step=1
            ),
            "Improving?": st.column_config.SelectboxColumn(
                "Improving?",
                options=["Yes", "No", "Too early"],
            ),
        },
        key=editor_key,
    )

    if st.button("Save edits", type="primary", key=f"save_edits_{session_id}"):
        _apply_edits(original_df, edited_df, entries)
        st.success("Changes saved.")
        st.rerun()

    # -- Delete section -------------------------------------------------------
    st.markdown("**Delete entries**")
    entry_labels = [
        f"Week {e.week_number} — {e.medicine_name} ({e.date_applied.isoformat()})"
        for e in entries
    ]
    entry_id_by_label = {
        label: e.entry_id for label, e in zip(entry_labels, entries)
    }
    selected_labels = st.multiselect(
        "Select entries to delete",
        options=entry_labels,
        key=f"del_select_{session_id}",
    )
    if selected_labels and st.button(
        f"Delete {len(selected_labels)} selected",
        type="secondary",
        key=f"del_confirm_{session_id}",
    ):
        for label in selected_labels:
            persistence.delete_medicine_entry(entry_id_by_label[label])
        st.success(f"Deleted {len(selected_labels)} entr{'y' if len(selected_labels) == 1 else 'ies'}.")
        st.rerun()


def _apply_edits(
    original_df: pd.DataFrame,
    edited_df: pd.DataFrame,
    entries: list[MedicineEntry],
) -> None:
    """Persist any rows the user changed in the data_editor."""
    improving_map = {"Yes": True, "No": False, "Too early": None}

    for i, (orig_row, edit_row) in enumerate(
        zip(original_df.drop(columns=["entry_id"]).itertuples(index=False),
            edited_df.itertuples(index=False))
    ):
        if orig_row == edit_row:
            continue  # no change for this row

        entry = entries[i]
        try:
            parsed_date = date.fromisoformat(str(edit_row._asdict().get("Date", entry.date_applied.isoformat())))
        except ValueError:
            parsed_date = entry.date_applied

        row_dict = edit_row._asdict()
        updated = MedicineEntry(
            entry_id=entry.entry_id,
            session_id=entry.session_id,
            week_number=int(row_dict.get("Week", entry.week_number)),
            date_applied=parsed_date,
            medicine_id=entry.medicine_id,
            medicine_name=str(row_dict.get("Medicine", entry.medicine_name)),
            dosage_applied=str(row_dict.get("Dosage", entry.dosage_applied)),
            application_method=str(row_dict.get("Method", entry.application_method)),
            symptom_severity=int(row_dict.get("Severity (1–5)", entry.symptom_severity)),
            notes=str(row_dict.get("Notes", entry.notes)),
            is_improving=improving_map.get(
                str(row_dict.get("Improving?", "Too early")), None
            ),
        )
        persistence.save_medicine_entry(updated)


def _render_sparkline(entries: list[MedicineEntry]) -> None:
    import streamlit as st

    st.markdown("**Symptom Severity — Week over Week**")

    weekly: dict[int, int] = {}
    for e in entries:
        if e.week_number not in weekly or e.symptom_severity > weekly[e.week_number]:
            weekly[e.week_number] = e.symptom_severity

    if len(weekly) < 2:
        st.caption("At least two weeks of data needed to show a trend.")
        return

    chart_df = pd.DataFrame(
        {"Week": list(weekly.keys()), "Severity": list(weekly.values())}
    ).set_index("Week")

    st.bar_chart(chart_df, color="#e05c5c", use_container_width=True)
    st.caption(
        "Lower severity over time indicates the treatment is working. "
        "Severity scale: 1 = trace symptoms, 5 = severe infection."
    )
