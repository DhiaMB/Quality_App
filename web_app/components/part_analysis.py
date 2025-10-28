import streamlit as st
import pandas as pd
from io import BytesIO

def part_leaderboard(summary_df, top_n=15):
    """Display top parts leaderboard"""
    st.markdown("## 🏆 Top Parts Leaderboard")
    
    if summary_df.empty:
        st.info("No part-level summary available")
        return
    
    display = summary_df[['part_number', 'total_defects', 'SCRAP', 'REPAIRED', 'scrap_rate_percent', 'top_reasons']].head(top_n)
    display = display.rename(columns={'SCRAP': 'scrap_count', 'REPAIRED': 'repaired_count'})
    
    st.dataframe(display, use_container_width=True)
    
    # Download button
    csv = display.to_csv(index=False)
    st.download_button("📥 Download Top Parts CSV", csv, file_name="top_parts.csv")

def part_detail_with_excel(df):
    """Display part detail analysis with Excel export"""
    st.markdown("## 📊 Part Detail Analysis")
    
    if df.empty:
        st.info("No data available for part analysis")
        return

    part_number = st.selectbox("Select Part Number", df["part_number"].unique())
    p_df = df[df["part_number"] == part_number]
    
    if p_df.empty:
        st.warning("No records found for this part.")
        return

    # Display part summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", len(p_df))
    with col2:
        st.metric("Scrap Count", (p_df["disposition_norm"] == "SCRAP").sum())
    with col3:
        st.metric("Repaired Count", (p_df["disposition_norm"] == "REPAIRED").sum())
    with col4:
        scrap_rate = (p_df["disposition_norm"] == "SCRAP").sum() / len(p_df) * 100
        st.metric("Scrap Rate", f"{scrap_rate:.1f}%")

    # Excel export
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        p_df.sort_values("date", ascending=False).to_excel(writer, sheet_name="records", index=False)
        
        summary = pd.DataFrame({
            "metric": ["total_records", "scrap_count", "repaired_count", "scrap_rate_percent"],
            "value": [len(p_df), (p_df["disposition_norm"] == "SCRAP").sum(), 
                     (p_df["disposition_norm"] == "REPAIRED").sum(), scrap_rate],
        })
        summary.to_excel(writer, sheet_name="summary", index=False)
    
    buffer.seek(0)

    st.download_button(
        label=f"📥 Download {part_number} Report",
        data=buffer,
        file_name=f"{part_number}_quality_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )