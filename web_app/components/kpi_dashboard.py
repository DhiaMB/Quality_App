import streamlit as st
import pandas as pd
from web_app.utils.data_loader import load_data
from web_app.utils.calculations import period_metrics, summary_by_part
from web_app.components.pareto_analysis import defect_pareto
from web_app.components.alerts_panel import alerts_panel
from web_app.components.trends_analysis import time_trends
from web_app.components.part_analysis import part_leaderboard, part_detail_with_excel

class QualityApp:
    def __init__(self, engine):
        self.engine = engine

    def sidebar_controls(self):
        """Sidebar controls for dashboard configuration"""
        st.sidebar.header("🎛️ Dashboard Controls")
        
        st.sidebar.markdown("### Analysis Period")
        days = st.sidebar.selectbox(
            "Time window", 
            [1, 3, 7, 14, 30, 60, 90], 
            index=3,
            format_func=lambda x: f"Last {x} days"
        )
        
        st.sidebar.markdown("### Chart Settings")
        top_n = st.sidebar.slider("Top N items in charts", 5, 25, 15)
        
        st.sidebar.markdown("### Alert Settings") 
        alert_rel_threshold = st.sidebar.number_input(
            "Relative increase threshold (%)",
            min_value=10.0, max_value=500.0, value=50.0, step=5.0
        )
        
        alert_abs_threshold = st.sidebar.number_input(
            "Absolute increase threshold (pp)",
            min_value=1.0, max_value=20.0, value=5.0, step=1.0
        )
        
        alpha = st.sidebar.slider(
            "Statistical significance level",
            min_value=0.001, max_value=0.10, value=0.05, step=0.01
        )
        
        return days, top_n, alert_rel_threshold / 100.0, alert_abs_threshold / 100.0, alpha

    def header_kpis(self, df, current_period, prior_period):
        """Display main KPI dashboard"""
        st.markdown("## 📊 Quality Performance Dashboard")
        
        if df.empty:
            st.warning("No data available for analysis")
            return

        # Calculate metrics
        total = current_period['total']
        scrap = current_period['scrap']
        repaired = current_period['repaired']
        scrap_rate = (scrap / total * 100) if total > 0 else 0

        prior_total = prior_period['total']
        prior_scrap = prior_period['scrap']
        prior_scrap_rate = (prior_scrap / prior_total * 100) if prior_total > 0 else 0
        delta_scrap = scrap_rate - prior_scrap_rate

        # KPI Cards - Row 1
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Defects", f"{total:,}", delta=f"{total - prior_total:+,}")
        
        with col2:
            st.metric("Scrap Count", f"{scrap:,}", delta=f"{scrap - prior_scrap:+,}")
        
        with col3:
            st.metric("Scrap Rate", f"{scrap_rate:.1f}%", delta=f"{delta_scrap:+.1f}pp")
        
        with col4:
            st.metric("Repaired Count", f"{repaired:,}")

        # KPI Cards - Row 2
        col5, col6, col7, col8 = st.columns(4)
        
        with col5:
            st.metric("Unique Parts", df['part_number'].nunique())
        
        with col6:
            st.metric("Active Shifts", df['shift'].nunique())
        
        with col7:
            date_range = f"{df['date'].min().strftime('%m/%d')} - {df['date'].max().strftime('%m/%d')}"
            st.metric("Analysis Period", date_range)
        
        with col8:
            last_load = df['load_timestamp'].max()
            last_load_str = last_load.strftime("%m/%d %H:%M") if pd.notnull(last_load) else "N/A"
            st.metric("Data Updated", last_load_str)

    def run(self):
        """Main application flow"""
        # Sidebar controls
        days, top_n, rel_thresh, abs_thresh, alpha = self.sidebar_controls()
        
        # Load data from database
        with st.spinner('🔄 Loading quality data...'):
            df = load_data(self.engine, days=days)
        
        if df.empty:
            st.error("No data available. Check ETL pipeline or adjust date range.")
            return

        # Calculate periods for comparison
        end_curr = df['date'].max()
        start_curr = end_curr - pd.Timedelta(days=days/2)
        start_prior = start_curr - pd.Timedelta(days=days/2)
        end_prior = start_curr - pd.Timedelta(days=1)

        current_period = period_metrics(df, start_curr, end_curr)
        prior_period = period_metrics(df, start_prior, end_prior)

        # Dashboard sections
        self.header_kpis(df, current_period, prior_period)
        st.markdown("---")
        
        # Pass engine to defect_pareto so it can load data from DB itself
        defect_pareto(self.engine, top_n=top_n)
        st.markdown("---")

        alerts_panel(self.engine, current_period, prior_period, rel_thresh=rel_thresh, abs_thresh=abs_thresh, alpha=alpha)
        st.markdown("---")

        summary = summary_by_part(df)
        part_leaderboard(summary, top_n=top_n)
        st.markdown("---")

        time_trends(df)
        st.markdown("---")

        part_detail_with_excel(df)
