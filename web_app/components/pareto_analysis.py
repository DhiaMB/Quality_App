# Fixed: re-add defect_pareto() entrypoint so pages import works.
# This file defines small local helpers, export_full_pareto_pptx and the dashboard entrypoint defect_pareto.
import io
import zipfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Attempt to import the pretty PPTX generator (external helper)
try:
    from web_app.components.pptx_template import create_pretty_pptx
    HAS_PRETTY_PPTX = True
except Exception:
    create_pretty_pptx = None
    HAS_PRETTY_PPTX = False

# Reuse impl helpers where present
try:
    from web_app.components.pareto_analysis_impl import (
        render_chronic_issues as _render_chronic_issues_impl,
        get_top_operators_section as _get_top_operators_section_impl,
        render_operator_trends as _render_operator_trends_impl,
        render_performance_trends as _render_performance_trends_impl,
        render_advanced_analysis as _render_advanced_analysis_impl,
        create_modern_pareto_chart as _create_modern_pareto_chart_impl
    )
except Exception:
    _render_chronic_issues_impl = None
    _get_top_operators_section_impl = None
    _render_operator_trends_impl = None
    _render_performance_trends_impl = None
    _render_advanced_analysis_impl = None
    _create_modern_pareto_chart_impl = None

# ---------------------- small local helpers (prevent circular imports) ----------------------
def _make_png_bytes(fig, width=1200, height=600):
    """Return PNG bytes of a plotly figure if possible (prefers kaleido)."""
    try:
        return fig.to_image(format="png", width=width, height=height)
    except Exception:
        try:
            buf = io.BytesIO()
            fig.write_image(buf, format="png", width=width, height=height)
            return buf.getvalue()
        except Exception:
            return None

def _make_zip_bundle(files_dict):
    out = io.BytesIO()
    with zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files_dict.items():
            if content is None:
                continue
            zf.writestr(name, content)
    return out.getvalue()

# ---------------------- core helpers ----------------------
def run_query(query, engine):
    if not hasattr(engine, "connect"):
        st.error(f"❌ Invalid engine passed to run_query (got {type(engine)})")
        return pd.DataFrame()
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()

def load_data_from_db(engine):
    try:
        with engine.connect() as conn:
            pass
    except Exception as e:
        st.error(f"❌ Database engine test failed: {e}")
        return pd.DataFrame()

    query = """
        SELECT *
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '90 days'
    """
    df = run_query(query, engine)
    if df.empty:
        return df

    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['date_only'] = df['date'].dt.date
    if 'id' not in df.columns:
        df['id'] = range(1, len(df) + 1)
    return df

# ---------------------- export to PPTX ----------------------
def export_full_pareto_pptx(engine, top_n=15, logo_path: str | None = None, brand_color: str = "#2C3E50", accent_color: str = "#FF9900"):
    """
    Build a full PPTX using create_pretty_pptx when available, including operator section.
    Returns bytes or None.
    """
    df = load_data_from_db(engine)
    if df is None or df.empty:
        st.warning("No data to export")
        return None

    # 1) Pareto
    series = df['code_description'].dropna().astype(str)
    try:
        if _create_modern_pareto_chart_impl:
            fig_pareto, pareto_data = _create_modern_pareto_chart_impl(series, title='All-Time Defect Pareto', xaxis_title='Defect', top_n=top_n)
        else:
            counts = series.value_counts().head(top_n)
            total = counts.sum()
            percentages = (counts / total * 100).round(1) if total > 0 else counts * 0
            cum = percentages.cumsum()
            fig_pareto = go.Figure()
            fig_pareto.add_trace(go.Bar(x=counts.index, y=counts.values, name='Count'))
            fig_pareto.add_trace(go.Scatter(x=counts.index, y=cum.values, name='Cumulative %', yaxis='y2'))
            pareto_data = pd.DataFrame({'category': counts.index, 'count': counts.values, 'percentage': percentages.values, 'cumulative_percentage': cum.values})
    except Exception:
        return None

    # 2) Monthly defects time series
    df['month'] = pd.to_datetime(df['date']).dt.to_period('M').dt.to_timestamp()
    perf = df.groupby('month').size().reset_index(name='total_defects')
    fig_perf = go.Figure()
    fig_perf.add_trace(go.Scatter(x=perf['month'], y=perf['total_defects'], mode='lines+markers', name='Defects'))
    fig_perf.update_layout(title='Monthly Defects', xaxis_title='Month', yaxis_title='Defects')

    # 3) Disposition pie
    disp = df['disposition'].fillna('UNKNOWN')
    disp_counts = disp.value_counts()
    fig_disp = px.pie(names=disp_counts.index, values=disp_counts.values, title='Disposition Breakdown')

    # 4) Top operators via impl helper (if available) - use overall window returned by load_data_from_db
    fig_ops = None
    top_ops_table = pd.DataFrame()
    if _get_top_operators_section_impl:
        try:
            fig_ops, top_ops_table = _get_top_operators_section_impl(engine, None, None, top_n)
        except Exception:
            fig_ops = None
            top_ops_table = pd.DataFrame()
    else:
        # fallback compute from df
        if 'who_made_it' in df.columns:
            op = df.groupby('who_made_it').agg(defect_count=('id', 'count')).reset_index().rename(columns={'who_made_it': 'operator_id'})
            if 'disposition' in df.columns:
                scraps = df[df['disposition'].str.upper() == 'SCRAP'].groupby('who_made_it').size().reset_index(name='scrap_count')
                scraps = scraps.rename(columns={'who_made_it': 'operator_id'})
                op = op.merge(scraps, on='operator_id', how='left')
                op['scrap_count'] = op['scrap_count'].fillna(0).astype(int)
            else:
                op['scrap_count'] = 0
            op['scrap_rate'] = np.where(op['defect_count'] == 0, 0, (op['scrap_count'] / op['defect_count'] * 100)).round(1)
            op = op.sort_values('defect_count', ascending=False).reset_index(drop=True)
            top_ops_table = op.head(top_n)
            fig_ops = px.bar(top_ops_table, x='operator_id', y='defect_count', title='Top Operators by Defect Count', labels={'operator_id': 'Operator', 'defect_count': 'Total Defects'})

    plots = {
        'Defect Pareto': fig_pareto,
        'Monthly Defects': fig_perf,
        'Disposition Breakdown': fig_disp
    }
    if fig_ops is not None:
        plots['Top Operators'] = fig_ops

    tables = {
        'Top Defects': pareto_data
    }
    if not top_ops_table.empty:
        tables['Top Operators'] = top_ops_table

    # Use pretty PPTX generator if available
    if HAS_PRETTY_PPTX and create_pretty_pptx is not None:
        try:
            pptx_bytes = create_pretty_pptx(plots, tables, title='Quality Pareto Analysis', logo_path=logo_path, brand_color=brand_color, accent_color=accent_color)
            return pptx_bytes
        except Exception as e:
            st.error(f"PPTX generation failed: {e}")
            return None

    # Fallback: basic PPTX via a fallback function if present, else None
    try:
        # If an older fallback exists in another module, use it; otherwise return None
        from web_app.components.pareto_analysis import _create_full_pptx as fallback_pptx  # local fallback (only if present)
        return fallback_pptx(plots, tables, title='Quality Pareto Analysis', logo_path=logo_path)
    except Exception:
        return None

# ---------------------- main dashboard entrypoint required by pages ----------------------
def defect_pareto(engine, top_n=15):
    """
    Primary entry for the Pareto dashboard.
    Compatible with web_app/pages/2_📈_Pareto_Analysis.py which imports defect_pareto.
    This function renders the four tabs and places the Export button on the header row (right-aligned).
    """
    # Header row with title and right-aligned button
    col_title, col_button = st.columns([8, 2])
    with col_title:
        st.markdown("## 📈 Quality Intelligence Dashboard")
    with col_button:
        if st.button("📥 Export PPTX"):
            with st.spinner("Building presentation…"):
                pptx_bytes = export_full_pareto_pptx(engine, top_n=top_n)
                if pptx_bytes:
                    st.download_button(
                        label="Download Presentation",
                        data=pptx_bytes,
                        file_name=f"quality_pareto_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )
                else:
                    st.error("Presentation creation failed or python-pptx not available on the server.")

    df = load_data_from_db(engine)
    if df is None or df.empty:
        st.info("No data available for analysis")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "🔧 Chronic Issues",
        "👥 Operator Trends",
        "📊 Performance",
        "🔍 Advanced"
    ])

    with tab1:
        if _render_chronic_issues_impl:
            try:
                # implementation returns (fig, df) optionally
                r = _render_chronic_issues_impl(engine, top_n=top_n, debug=False, sort_by='scrap_rate')
                if isinstance(r, tuple) and len(r) == 2:
                    fig_top, df_top = r
                    st.plotly_chart(fig_top, use_container_width=True)
            except Exception:
                st.info("Chronic issues view (impl) raised an exception - see console.")
        else:
            st.info("Chronic issues implementation not found.")

    with tab2:
        if _render_operator_trends_impl:
            try:
                _render_operator_trends_impl(engine)
            except Exception:
                st.info("Operator trends view (impl) raised an exception - see console.")
        else:
            st.info("Operator trends implementation not found.")

    with tab3:
        if _render_performance_trends_impl:
            try:
                _render_performance_trends_impl(engine)
            except Exception:
                st.info("Performance view (impl) raised an exception - see console.")
        else:
            st.info("Performance implementation not found.")

    with tab4:
        if _render_advanced_analysis_impl:
            try:
                _render_advanced_analysis_impl(engine)
            except Exception:
                st.info("Advanced analysis implementation not found or raised an exception.")
        else:
            st.info("Advanced analysis implementation not found.")