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
    import streamlit as st

    st.markdown("**Treatment Log**")

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

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["entry_id"])
    st.dataframe(display_df, use_container_width=True, hide_index=True)


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
