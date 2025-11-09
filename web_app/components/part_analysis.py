import streamlit as st
import pandas as pd
from io import BytesIO
from utils.sql import load_part_records

def part_leaderboard(summary_df, top_n=15):
    """Display top parts leaderboard"""
    st.markdown("## 🏆 Top Parts Leaderboard")
    if summary_df is None or summary_df.empty:
        st.info("No part-level summary available")
        return

    display = summary_df.copy()
    if 'SCRAP' in display.columns:
        display = display.rename(columns={'SCRAP': 'scrap_count'})
    if 'REPAIRED' in display.columns:
        display = display.rename(columns={'REPAIRED': 'repaired_count'})

    show_cols = [c for c in ['part_number', 'total_defects', 'scrap_count', 'repaired_count', 'scrap_rate_percent', 'top_reasons'] if c in display.columns]
    display = display[show_cols].head(top_n)
    st.dataframe(display, use_container_width=True)

    csv = display.to_csv(index=False)
    st.download_button("📥 Download Top Parts CSV", csv, file_name="top_parts.csv")

def part_detail_with_excel(engine=None, df=None):
    """
    Show per-part detail and allow Excel export.
    - If df (raw) is provided and is a DataFrame, use it.
    - Otherwise fetch records for the selected part on-demand via engine (DB or DataFrame).
    """
    st.markdown("## 📊 Part Detail Analysis")

    # Determine part choices
    part_choices = []
    if isinstance(df, pd.DataFrame) and not df.empty:
        part_choices = df['part_number'].unique().tolist()
    elif engine is not None:
        try:
            # If engine is a DataFrame, compute top parts in-memory
            if isinstance(engine, pd.DataFrame):
                top_parts = engine.groupby('part_number').size().reset_index(name='cnt').sort_values('cnt', ascending=False).head(200)
            else:
                top_parts_q = """
                    SELECT part_number, COUNT(*) as cnt
                    FROM quality.clean_quality_data
                    GROUP BY part_number
                    ORDER BY cnt DESC
                    LIMIT 200
                """
                top_parts = pd.read_sql(top_parts_q, con=engine)
            if top_parts is None or top_parts.empty:
                part_choices = []
            else:
                part_choices = top_parts['part_number'].tolist()
        except Exception as e:
            st.warning(f"Could not load part list: {e}")
            part_choices = []
    else:
        st.info("No data source available to list parts.")
        return

    if not part_choices:
        st.info("No parts available.")
        return

    part_number = st.selectbox("Select Part Number", part_choices)
    if not part_number:
        return

    # Fetch detailed records (prefer df if available)
    if isinstance(df, pd.DataFrame) and not df.empty:
        p_df = df[df['part_number'] == part_number].copy()
    else:
        try:
            p_df = load_part_records(engine, part_number, limit=10000)
        except Exception as e:
            st.error(f"Error loading records for {part_number}: {e}")
            return

    if p_df is None or (isinstance(p_df, pd.DataFrame) and p_df.empty):
        st.warning("No records found for this part.")
        return

    # Display part summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", f"{len(p_df):,}")
    with col2:
        # safe disposition detection
        if 'disposition_norm' in p_df.columns:
            scrap_count = int((p_df['disposition_norm'] == "SCRAP").sum())
            repaired_count = int((p_df['disposition_norm'] == "REPAIRED").sum())
        elif 'disposition' in p_df.columns:
            scrap_count = int((p_df['disposition'] == "Scrap").sum())
            repaired_count = int((p_df['disposition'] == "Repaired").sum())
        else:
            scrap_count = 0
            repaired_count = 0
        st.metric("Scrap Count", f"{scrap_count:,}")
    with col3:
        st.metric("Repaired Count", f"{repaired_count:,}")
    with col4:
        scrap_rate = (scrap_count / len(p_df) * 100) if len(p_df) > 0 else 0.0
        st.metric("Scrap Rate", f"{scrap_rate:.1f}%")

    # Excel export
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        if 'date' in p_df.columns:
            try:
                p_df['date'] = pd.to_datetime(p_df['date'], errors='coerce')
                p_df.sort_values("date", ascending=False).to_excel(writer, sheet_name="records", index=False)
            except Exception:
                p_df.to_excel(writer, sheet_name="records", index=False)
        else:
            p_df.to_excel(writer, sheet_name="records", index=False)

        summary = pd.DataFrame({
            "metric": ["total_records", "scrap_count", "repaired_count", "scrap_rate_percent"],
            "value": [len(p_df), scrap_count, repaired_count, scrap_rate],
        })
        summary.to_excel(writer, sheet_name="summary", index=False)

    buffer.seek(0)
    st.download_button(
        label=f"📥 Download {part_number} Report",
        data=buffer,
        file_name=f"{part_number}_quality_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )