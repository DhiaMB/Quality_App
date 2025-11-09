import streamlit as st
import pandas as pd
from typing import Optional


class QualityApp:
    """
    Main dashboard entrypoint.
    This file avoids heavy top-level imports to prevent ImportError caused by
    circular imports or runtime errors during module import.
    """

    def __init__(self, engine):
        self.engine = engine

    def sidebar_controls(self):
        """Sidebar controls for dashboard configuration"""
        st.sidebar.header("🎛️ Dashboard Controls")
        st.sidebar.markdown("### Analysis Period")
        days = st.sidebar.selectbox(
            "Time window", [1, 3, 7, 14, 30, 60, 90], index=3,
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

    def header_kpis_from_aggs(self, part_agg_df: Optional[pd.DataFrame], daily_df: Optional[pd.DataFrame]):
        """Build header KPIs from aggregated tables (no raw df required)."""
        st.markdown("## 📊 Quality Performance Dashboard (Aggregated)")
        if (part_agg_df is None or part_agg_df.empty) and (daily_df is None or daily_df.empty):
            st.warning("No aggregated data available for analysis")
            return

        # Derive current and prior totals from part aggregates if available
        if part_agg_df is not None and not part_agg_df.empty:
            total = int(part_agg_df['total_curr'].sum()) if 'total_curr' in part_agg_df.columns else 0
            scrap = int(part_agg_df['scrap_curr'].sum()) if 'scrap_curr' in part_agg_df.columns else 0
            repaired = int(part_agg_df['repaired_curr'].sum()) if 'repaired_curr' in part_agg_df.columns else 0
            prior_total = int(part_agg_df['total_prior'].sum()) if 'total_prior' in part_agg_df.columns else 0
            prior_scrap = int(part_agg_df['scrap_prior'].sum()) if 'scrap_prior' in part_agg_df.columns else 0
        else:
            # Fallback to daily aggregates
            total = int(daily_df['defect_count'].sum()) if (daily_df is not None and 'defect_count' in daily_df.columns and not daily_df.empty) else 0
            scrap = int(daily_df['scrap_count'].sum()) if (daily_df is not None and 'scrap_count' in daily_df.columns and not daily_df.empty) else 0
            repaired = int(daily_df['repaired_count'].sum()) if (daily_df is not None and 'repaired_count' in daily_df.columns and not daily_df.empty) else 0
            prior_total = 0
            prior_scrap = 0

        scrap_rate = (scrap / total * 100) if total > 0 else 0.0
        prior_scrap_rate = (prior_scrap / prior_total * 100) if prior_total > 0 else 0.0
        delta_scrap = scrap_rate - prior_scrap_rate

        # KPI Cards - Row 1
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Defects", f"{total:,}", delta=f"{(total - prior_total):+,}")
        with col2:
            st.metric("Scrap Count", f"{scrap:,}", delta=f"{(scrap - prior_scrap):+,}")
        with col3:
            st.metric("Scrap Rate", f"{scrap_rate:.1f}%", delta=f"{delta_scrap:+.1f}pp")
        with col4:
            st.metric("Repaired Count", f"{repaired:,}")

        # KPI Cards - Row 2 (best-effort)
        col5, col6, col7, col8 = st.columns(4)
        unique_parts = int(part_agg_df['part_number'].nunique()) if (part_agg_df is not None and 'part_number' in part_agg_df.columns and not part_agg_df.empty) else 0
        active_shifts = "N/A"

        if daily_df is not None and not daily_df.empty and 'date' in daily_df.columns:
            try:
                # ensure date column is datetime
                dates = pd.to_datetime(daily_df['date'], errors='coerce')
                date_range = f"{dates.min().strftime('%m/%d')} - {dates.max().strftime('%m/%d')}"
            except Exception:
                date_range = "N/A"
        else:
            date_range = "N/A"
        last_load_str = "N/A"

        with col5:
            st.metric("Unique Parts", unique_parts)
        with col6:
            st.metric("Active Shifts", active_shifts)
        with col7:
            st.metric("Analysis Period", date_range)
        with col8:
            st.metric("Data Updated", last_load_str)

    @staticmethod
    def is_db_engine(obj) -> bool:
        """
        Heuristic check to see if the provided object looks like a SQLAlchemy engine/connection.
        This is a best-effort heuristic — DataFrame is also accepted as a valid 'engine' for offline mode.
        """
        try:
            import sqlalchemy
            return hasattr(obj, "connect") or isinstance(obj, sqlalchemy.engine.Engine)
        except Exception:
            # Fallback heuristic: presence of connect/execute
            return hasattr(obj, "connect") or hasattr(obj, "execute")

    def run(self):
        """
        Main application flow.
        Imports of components and DB helpers are done lazily here to avoid import-time errors/cycles.
        """

        # Validate engine early
        if not self.is_db_engine(self.engine) and not isinstance(self.engine, pd.DataFrame):
            st.error(f"Expected SQLAlchemy engine/connection or pandas.DataFrame but got {type(self.engine)}. Aborting early. Check get_target_engine().")
            return

        # Lazy imports to avoid circular import issues
        load_agg_by_part = None
        load_agg_by_day = None
        legacy_load_data = None

        try:
            from utils.sql import load_agg_by_part, load_agg_by_day  # preferred hybrid loaders
        except Exception:
            # Fallback to legacy loader if present
            try:
                from utils.data_loader import load_data  # type: ignore
                legacy_load_data = load_data
                load_agg_by_part = None
                load_agg_by_day = None
            except Exception:
                legacy_load_data = None
                load_agg_by_part = None
                load_agg_by_day = None

        # Lazy import UI components
        try:
            from components.alerts_panel import alerts_panel
            from components.trends_analysis import time_trends
            from components.part_analysis import part_leaderboard, part_detail_with_excel
        except Exception as e:
            st.error(f"Error importing UI components: {e}")
            # Provide a safe fallback: stop early
            return

        days, top_n, rel_thresh, abs_thresh, alpha = self.sidebar_controls()

        # Compute date ranges
        end_curr = pd.to_datetime("today").normalize()
        start_full = end_curr - pd.Timedelta(days=days - 1)
        half_days = int(days // 2) if days >= 2 else 1
        curr_start = end_curr - pd.Timedelta(days=half_days - 1)
        curr_end = end_curr
        prior_end = curr_start - pd.Timedelta(days=1)
        prior_start = prior_end - pd.Timedelta(days=half_days - 1)



        # ------------------ REPLACED: Robust loader + normalization ------------------
        import numpy as np

        def debug_loader(loader_fn, *args, name="loader"):
            try:
                df = loader_fn(*args)
                if df is None:
                    st.warning(f"DEBUG: {name} returned None")
                    return pd.DataFrame()
                if not isinstance(df, pd.DataFrame):
                    try:
                        df = pd.DataFrame(df)
                    except Exception:
                        st.warning(f"DEBUG: {name} returned non-DataFrame of type {type(df)}")
                        return pd.DataFrame()

                # DEBUG : st.write(f"DEBUG: {name} shape: {df.shape}")
                #st.write(f"DEBUG: {name} columns: {df.columns.tolist()}")
                #st.write(f"DEBUG: {name} sample:", df.head(5))
                return df
            except Exception as e:
                st.error(f"Error in {name}: {e}")
                return pd.DataFrame()


        # Convert date windows to plain date objects (safer for DB parameter binding)
        curr_start_dt = pd.to_datetime(curr_start).date()
        curr_end_dt = pd.to_datetime(curr_end).date()
        prior_start_dt = pd.to_datetime(prior_start).date()
        prior_end_dt = pd.to_datetime(prior_end).date()
        start_full_dt = pd.to_datetime(start_full).date()
        end_curr_dt = pd.to_datetime(end_curr).date()

        with st.spinner("🔄 Loading aggregated metrics..."):
            try:
                part_agg = pd.DataFrame()
                daily_agg = pd.DataFrame()

                if load_agg_by_part is not None and load_agg_by_day is not None:
                    part_agg = debug_loader(
                        load_agg_by_part,
                        self.engine,
                        curr_start_dt,
                        curr_end_dt,
                        prior_start_dt,
                        prior_end_dt,
                        name="load_agg_by_part"
                    )
                    daily_agg = debug_loader(
                        load_agg_by_day,
                        self.engine,
                        start_full_dt,
                        end_curr_dt,
                        name="load_agg_by_day"
                    )

                elif legacy_load_data is not None:
                    raw = debug_loader(legacy_load_data, self.engine, days, name="legacy_load_data")
                    if raw is None or raw.empty:
                        st.error("No data returned by legacy loader.")
                        part_agg = pd.DataFrame()
                        daily_agg = pd.DataFrame()
                    else:
                        raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
                        daily_agg = (
                            raw
                            .groupby(raw['date'].dt.floor('D'))
                            .size()
                            .reset_index(name='defect_count')
                        )

                        curr_mask = (raw['date'] >= pd.to_datetime(curr_start_dt)) & (raw['date'] <= pd.to_datetime(curr_end_dt))
                        prior_mask = (raw['date'] >= pd.to_datetime(prior_start_dt)) & (raw['date'] <= pd.to_datetime(prior_end_dt))

                        curr = (
                            raw.loc[curr_mask]
                            .groupby('part_number')
                            .agg(total_curr=('part_number', 'size'),
                                 scrap_curr=('disposition', lambda s: (s == 'Scrap').sum()))
                            .reset_index()
                        )

                        prior = (
                            raw.loc[prior_mask]
                            .groupby('part_number')
                            .agg(total_prior=('part_number', 'size'),
                                 scrap_prior=('disposition', lambda s: (s == 'Scrap').sum()))
                            .reset_index()
                        )

                        if not curr.empty:
                            part_agg = curr.merge(prior, on='part_number', how='left').fillna(0)
                            for c in ['total_curr', 'scrap_curr', 'total_prior', 'scrap_prior']:
                                if c in part_agg.columns:
                                    part_agg[c] = pd.to_numeric(part_agg[c], errors='coerce').fillna(0).astype(int)
                            part_agg['rate_curr'] = part_agg.apply(
                                lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0.0, axis=1
                            )
                            part_agg['rate_prior'] = part_agg.apply(
                                lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0.0, axis=1
                            )
                else:
                    st.warning("No aggregation loader available. Add utils/sql.load_agg_by_part & load_agg_by_day or utils.data_loader.load_data.")
            except Exception as e:
                st.error(f"Error loading aggregates: {e}")
                part_agg = pd.DataFrame()
                daily_agg = pd.DataFrame()

        # Normalize part_agg even if it came from SQL loader
        if part_agg is None or not isinstance(part_agg, pd.DataFrame):
            part_agg = pd.DataFrame()

        expected_cols = ['part_number', 'total_curr', 'scrap_curr', 'rate_curr', 'total_prior', 'scrap_prior', 'rate_prior']
        for c in expected_cols:
            if c not in part_agg.columns:
                part_agg[c] = 0.0 if c.startswith('rate_') else 0

        for c in ['total_curr', 'scrap_curr', 'total_prior', 'scrap_prior']:
            part_agg[c] = pd.to_numeric(part_agg[c], errors='coerce').fillna(0).astype(int)

        for c in ['rate_curr', 'rate_prior']:
            part_agg[c] = pd.to_numeric(part_agg[c], errors='coerce').fillna(0.0)

        part_agg['rate_curr'] = part_agg.apply(lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0.0, axis=1)
        part_agg['rate_prior'] = part_agg.apply(lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0.0, axis=1)

        # DEBUG :  Safe debug prints (no references to undefined vars)
        #st.write("PART AGG (post-load):", part_agg.head(10))
        #st.write("PART_AGG SHAPE:", part_agg.shape)

        # -------------------------------------------------------------------------

        # Header KPIs computed from aggregates
        self.header_kpis_from_aggs(part_agg, daily_agg)
        st.markdown("---")

        # Alerts - use part-level aggregated table
        try:
            alerts_panel(part_agg, rel_thresh=rel_thresh, abs_thresh=abs_thresh, alpha=alpha)
        except Exception as e:
            st.error(f"Error rendering alerts: {e}")
        st.markdown("---")

        # Build a best-effort summary for leaderboard
        try:
            if part_agg is None or part_agg.empty:
                summary = pd.DataFrame()
            else:
                # get repaired_curr safely (if present use column, else zeros)
                if 'repaired_curr' in part_agg.columns:
                    repaired_series = part_agg['repaired_curr']
                else:
                    repaired_series = pd.Series(0, index=part_agg.index)

                if 'rate_curr' in part_agg.columns:
                    scrap_rate_series = (part_agg['rate_curr'] * 100).round(2)
                else:
                    # fallback compute (guard divide-by-zero)
                    scrap_rate_series = ((part_agg['scrap_curr'] / part_agg['total_curr']).replace([float('inf'), float('nan')], 0) * 100).round(2)

                summary = pd.DataFrame({
                    "part_number": part_agg['part_number'],
                    "total_defects": part_agg['total_curr'],
                    "SCRAP": part_agg['scrap_curr'],
                    "REPAIRED": repaired_series,
                    "scrap_rate_percent": scrap_rate_series,
                    "top_reasons": ""
                })

            part_leaderboard(summary, top_n=top_n)
        except Exception as e:
            st.error(f"Error rendering leaderboard: {e}")
        st.markdown("---")

        # Trends - use daily aggregated table
        try:
            time_trends(self.engine, days=days)
        except Exception as e:
            st.error(f"Error rendering trends: {e}")
        st.markdown("---")

        # Part detail - call with engine so it can fetch raw rows on-demand
        try:
            part_detail_with_excel(engine=self.engine, df=None)
        except TypeError:
            # fallback if part_detail_with_excel expects (df) only
            try:
                part_detail_with_excel(None)
            except Exception as e:
                st.error(f"Error showing part detail: {e}")
        except Exception as e:
            st.error(f"Error showing part detail: {e}")
