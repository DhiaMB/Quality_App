"""
Implementation module for pareto analysis components — updated to:
 - avoid double-plotting in render_chronic_issues (return fig, df; don't call st.plotly_chart)
 - ensure operator trend pivots are datetime-indexed and sorted so line charts render correctly
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ------------------------ Pareto helper ------------------------------------
def create_modern_pareto_chart(series: pd.Series, title: str, xaxis_title: str, top_n: int = 15) -> Tuple[Optional[go.Figure], pd.DataFrame]:
    """Create a modern Pareto chart (bar + cumulative line) and return (fig, pareto_df)."""
    if series is None or series.dropna().empty:
        return None, pd.DataFrame()

    counts = series.value_counts().head(top_n)
    if counts.empty:
        return None, pd.DataFrame()

    total = int(counts.sum())
    percentages = (counts / total * 100).round(1)
    cumulative = percentages.cumsum()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=counts.index,
        y=counts.values,
        name="Count",
        marker_color="#3366cc",
        text=counts.values,
        textposition="auto",
    ))
    fig.add_trace(go.Scatter(
        x=counts.index,
        y=cumulative.values,
        name="Cumulative %",
        yaxis="y2",
        line=dict(color="#ff9900", width=3),
        marker=dict(size=6)
    ))
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title="Count",
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 100]),
        xaxis_tickangle=-45,
        hovermode="x unified",
        height=520,
        template="plotly_white",
        margin=dict(l=120, r=60, t=80, b=160)
    )

    pareto_df = pd.DataFrame({
        "category": counts.index.astype(str),
        "count": counts.values,
        "percentage": percentages.values,
        "cumulative_percentage": cumulative.values
    })

    return fig, pareto_df


# ------------------------ Chronic issues ------------------------------------
def render_chronic_issues(engine, top_n: int = 15, debug: bool = False, sort_by: str = "scrap_rate"):
    """
    Render chronic issues UI text and return (fig, df_top) — do NOT call st.plotly_chart here
    so the caller (pareto_analysis.py) can render the figure exactly once.
    """
    st.markdown("### 🔧 Chronic Quality Issues")
    st.info("Defects ranked by scrap rate impact for prioritization.")

    query = f"""
    SELECT
        code_description AS defect,
        COUNT(*) AS defect_count,
        COUNT(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 END) AS scrap_count
    FROM quality.clean_quality_data
    WHERE code_description IS NOT NULL AND code_description != ''
    GROUP BY code_description
    HAVING COUNT(*) > 0
    ORDER BY defect_count DESC
    LIMIT {top_n}
    """

    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Failed to load chronic issues: {e}")
        return None

    if df.empty:
        st.info("No chronic defect data available.")
        return None

    # normalize
    df["defect_count"] = pd.to_numeric(df["defect_count"], errors="coerce").fillna(0).astype(int)
    df["scrap_count"] = pd.to_numeric(df["scrap_count"], errors="coerce").fillna(0).astype(int)
    df["scrap_rate"] = np.where(df["defect_count"] > 0, df["scrap_count"] / df["defect_count"] * 100, 0.0).round(1)
    df["defect_percentage"] = (df["defect_count"] / df["defect_count"].sum() * 100).round(1)

    if sort_by == "scrap_rate":
        df = df.sort_values("scrap_rate", ascending=False)
    else:
        df = df.sort_values("defect_count", ascending=False)

    # build chart (but do not render it here)
    def color_for(rate):
        if rate >= 70:
            return "#FF4444"
        if rate >= 40:
            return "#FFAA44"
        if rate >= 20:
            return "#44AAFF"
        return "#44FF88"

    colors = [color_for(r) for r in df["scrap_rate"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=list(df["scrap_rate"]),
        y=list(df["defect"]),
        orientation="h",
        marker=dict(color=colors, line=dict(color="darkgray", width=1)),
        customdata=np.stack([df["defect_count"].astype(int), df["scrap_count"].astype(int), df["defect_percentage"].astype(float)], axis=1),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Scrap Rate: <b>%{x:.1f}%</b><br>"
            "Total Defects: %{customdata[0]:,}<br>"
            "Scrap Count: %{customdata[1]:,}<br>"
            "Frequency: %{customdata[2]:.1f}%<br>"
            "<extra></extra>"
        )
    ))
    fig.update_layout(
        title="Defects by Scrap Rate Impact",
        xaxis=dict(title="Scrap Rate (%)", range=[0, 100]),
        yaxis=dict(title="Defect", autorange="reversed"),
        height=max(480, len(df) * 36),
        template="plotly_white",
        margin=dict(l=220, r=20, t=80, b=50),
    )

    # debug info (keeps developer visibility)
    if debug:
        st.write("DEBUG - chronic df", df.head())
        st.write("DEBUG - sums", {"defect_sum": int(df["defect_count"].sum()), "scrap_sum": int(df["scrap_count"].sum())})

    # Return fig and dataframe to caller — caller should handle st.plotly_chart once.
    return fig, df


# ------------------------ Operator trends (modular) ------------------------
def fetch_operator_data(engine, months: int = 24) -> pd.DataFrame:
    """Fetch monthly operator aggregates (month, operator_id, defect_count, scrap_count)"""
    query = f"""
    SELECT
        DATE_TRUNC('month', date)::date AS month,
        who_made_it AS operator_id,
        COUNT(*) AS defect_count,
        SUM(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '{int(months)} months'
      AND who_made_it IS NOT NULL
    GROUP BY DATE_TRUNC('month', date)::date, who_made_it
    ORDER BY month, who_made_it
    """
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Failed to load operator trend data: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    df["month"] = pd.to_datetime(df["month"])
    df["operator_id"] = df["operator_id"].astype(str)
    df["defect_count"] = pd.to_numeric(df["defect_count"], errors="coerce").fillna(0).astype(int)
    df["scrap_count"] = pd.to_numeric(df["scrap_count"], errors="coerce").fillna(0).astype(int)
    df["scrap_rate"] = np.where(df["defect_count"] > 0, df["scrap_count"] / df["defect_count"] * 100, 0.0).round(2)
    df = df.sort_values("month")  # ensure chronological order
    return df


def to_month_period(dt) -> pd.Timestamp:
    """Normalize an input date to the month period start (Timestamp)."""
    return pd.to_datetime(dt).to_period("M").to_timestamp()


def filter_operator_data_by_month_range(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Filter operator-level monthly dataframe between start and end inclusive."""
    if df.empty:
        return df
    return df[(df["month"] >= start) & (df["month"] <= end)].copy()


def compute_operator_aggregates(filtered_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate by operator and compute scrap rate."""
    if filtered_df.empty:
        return pd.DataFrame(columns=["operator_id", "defect_count", "scrap_count", "scrap_rate"])
    agg = filtered_df.groupby("operator_id", dropna=False)[["defect_count", "scrap_count"]].sum().reset_index()
    agg["scrap_rate"] = np.where(agg["defect_count"] > 0, agg["scrap_count"] / agg["defect_count"] * 100, 0.0).round(2)
    agg = agg.sort_values("defect_count", ascending=False).reset_index(drop=True)
    return agg


def build_operator_plots(filtered_df: pd.DataFrame, agg_df: pd.DataFrame, top_n: int = 10):
    """Return (fig_defects, fig_scrap_rate, fig_top_ops) for the selected top operators."""
    if filtered_df.empty or agg_df.empty:
        return None, None, None

    top_ops = agg_df.head(top_n)["operator_id"].tolist()

    # Monthly defects pivot (ensure month index is datetime and sorted)
    defects_pivot = filtered_df.pivot_table(index="month", columns="operator_id", values="defect_count", aggfunc="sum").fillna(0)
    if not defects_pivot.empty:
        # ensure datetime index and chronological order
        defects_pivot.index = pd.to_datetime(defects_pivot.index)
        defects_pivot = defects_pivot.sort_index()
    if top_ops:
        defects_pivot = defects_pivot.reindex(columns=top_ops, fill_value=0)

    fig_def = None
    if not defects_pivot.empty:
        fig_def = go.Figure()
        for col in defects_pivot.columns:
            fig_def.add_trace(go.Scatter(x=defects_pivot.index, y=defects_pivot[col], mode="lines+markers", name=str(col)))
        fig_def.update_layout(title=f"Monthly Defects - Top {min(len(top_ops), top_n)} Operators", xaxis_title="Month", yaxis_title="Defects", height=380)
        fig_def.update_xaxes(type="date", tickformat="%b %Y")

    # monthly scrap rate pivot
    scrap_pivot = filtered_df.pivot_table(index="month", columns="operator_id", values="scrap_rate", aggfunc="mean").fillna(0)
    if not scrap_pivot.empty:
        scrap_pivot.index = pd.to_datetime(scrap_pivot.index)
        scrap_pivot = scrap_pivot.sort_index()
    if top_ops:
        scrap_pivot = scrap_pivot.reindex(columns=top_ops, fill_value=0)

    fig_scrap = None
    if not scrap_pivot.empty:
        fig_scrap = go.Figure()
        for col in scrap_pivot.columns:
            fig_scrap.add_trace(go.Scatter(x=scrap_pivot.index, y=scrap_pivot[col], mode="lines+markers", name=str(col)))
        fig_scrap.update_layout(title=f"Monthly Scrap Rate (%) - Top {min(len(top_ops), top_n)} Operators", xaxis_title="Month", yaxis_title="Scrap Rate (%)", height=380)
        fig_scrap.update_xaxes(type="date", tickformat="%b %Y")

    # top operators bar
    fig_top = None
    if not agg_df.empty:
        fig_top = px.bar(agg_df.head(top_n), x="operator_id", y="defect_count", labels={"operator_id": "Operator", "defect_count": "Total Defects"}, title=f"Top {min(len(agg_df), top_n)} Operators by Defect Count")
        fig_top.update_layout(height=380)

    return fig_def, fig_scrap, fig_top


def render_operator_trends(engine):
    """Full UI for operator trends, implemented modularly for readability and export reuse."""
    st.markdown("### 👥 Operator Performance Trends")
    st.info("Monthly defect and scrap analysis by operator (select time range)")

    operator_data = fetch_operator_data(engine, months=24)
    if operator_data.empty:
        st.warning("No operator trend data available.")
        return None

    # date selector aligned to months (month-level)
    min_month = operator_data["month"].min().date()
    max_month = operator_data["month"].max().date()
    date_range = st.date_input("Select month range", value=(min_month, max_month), min_value=min_month, max_value=max_month, help="Choose the inclusive month range (monthly granularity).")

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_month = to_month_period(date_range[0])
        end_month = to_month_period(date_range[1])
    else:
        start_month = to_month_period(date_range)
        end_month = start_month

    filtered = filter_operator_data_by_month_range(operator_data, start_month, end_month)
    if filtered.empty:
        st.warning("No operator data in the selected range.")
        return None

    top_n_ops = st.slider("Top N operators to show", min_value=3, max_value=30, value=5)

    agg = compute_operator_aggregates(filtered)
    total_defects = int(agg["defect_count"].sum()) if not agg.empty else 0
    total_scrap = int(agg["scrap_count"].sum()) if not agg.empty else 0
    overall_scrap_rate = (total_scrap / total_defects * 100) if total_defects > 0 else 0.0

    # KPI row
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Defects (selected)", f"{total_defects:,}")
    c2.metric("Total Scrap (selected)", f"{total_scrap:,}")
    c3.metric("Overall Scrap Rate", f"{overall_scrap_rate:.1f}%")

    st.markdown("#### 🔝 Top Operators by Total Defects (selected range)")
    display_table = agg.rename(columns={"operator_id": "Operator", "defect_count": "Total Defects", "scrap_count": "Scrap Count", "scrap_rate": "Scrap Rate (%)"})
    st.dataframe(display_table.head(top_n_ops), use_container_width=True)

    # CSV download
    csv_bytes = display_table.to_csv(index=False).encode("utf-8")
    st.download_button(label="Download Top Operators CSV", data=csv_bytes, file_name=f"top_operators_{start_month.strftime('%Y%m')}_{end_month.strftime('%Y%m')}.csv", mime="text/csv")

    # plots
    fig_def, fig_scrap, fig_top = build_operator_plots(filtered, agg, top_n=top_n_ops)

    st.subheader("📈 Monthly Defects per Operator")
    if fig_def:
        st.plotly_chart(fig_def, use_container_width=True)
    else:
        st.info("No monthly defect series to display.")

    st.subheader("📉 Monthly Scrap Rate (%) per Operator")
    if fig_scrap:
        st.plotly_chart(fig_scrap, use_container_width=True)
    else:
        st.info("No scrap rate series to display.")



    # Return nothing (UI is rendered). get_top_operators_section can be used by exports.
    return None


# ------------------------ Advanced analysis --------------------------------
def render_performance_trends(engine):
    """Daily/Weekly/Monthly defect + scrap time-trends view."""
    st.markdown("### 📊 Performance Trends")
    st.info("Analyze defects and scrap rate trends by time period")

    view = st.selectbox("Select time granularity:", ["Daily", "Weekly", "Monthly"], index=2)

    if view == "Daily":
        query = """
        SELECT
            DATE(date) AS period,
            COUNT(*) AS total_defects,
            COUNT(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 END) AS scrap_count
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(date)
        ORDER BY period ASC
        """
    elif view == "Weekly":
        query = """
        SELECT
            DATE_TRUNC('week', date)::date AS period,
            COUNT(*) AS total_defects,
            COUNT(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 END) AS scrap_count
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '12 weeks'
        GROUP BY DATE_TRUNC('week', date)::date
        ORDER BY period ASC
        """
    else:
        query = """
        SELECT
            DATE_TRUNC('month', date)::date AS period,
            COUNT(*) AS total_defects,
            COUNT(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 END) AS scrap_count
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY DATE_TRUNC('month', date)::date
        ORDER BY period ASC
        """

    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Error fetching performance data: {e}")
        return None

    if df.empty:
        st.info("No performance data available for the selected range.")
        return None

    df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period")
    df["scrap_rate"] = (df["scrap_count"] / df["total_defects"] * 100).round(2)

    # KPIs for latest vs previous average
    if len(df) > 1:
        latest = df.iloc[-1]
        avg_prev = df.iloc[:-1].mean(numeric_only=True)
    else:
        latest = df.iloc[0]
        avg_prev = latest

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta = latest["total_defects"] - avg_prev["total_defects"] if len(df) > 1 else 0
        st.metric("Defects", f"{int(latest['total_defects']):,}", f"{delta:+.0f} vs avg")
    with c2:
        delta = latest["scrap_count"] - avg_prev["scrap_count"] if len(df) > 1 else 0
        st.metric("Scrap", f"{int(latest['scrap_count']):,}", f"{delta:+.0f} vs avg")
    with c3:
        delta = latest["scrap_rate"] - avg_prev["scrap_rate"] if len(df) > 1 else 0
        st.metric("Scrap Rate", f"{latest['scrap_rate']:.1f}%", f"{delta:+.1f}% vs avg")
    with c4:
        trend = "📈 Worse" if delta > 0 else "📉 Better" if len(df) > 1 else "➡️ Stable"
        st.metric("Trend Direction", trend)

    # altair scrap rate chart (if altair available) else simple plotly
    try:
        import altair as alt

        if view == "Daily":
            df["period_display"] = df["period"].dt.strftime("%Y-%m-%d")
        elif view == "Weekly":
            df["period_display"] = df["period"].dt.strftime("Week of %Y-%m-%d")
        else:
            df["period_display"] = df["period"].dt.strftime("%b %Y")

        scrap_chart = alt.Chart(df).mark_line(point=True, strokeWidth=3, color="red").encode(
            x=alt.X("period:T", title=view, axis=alt.Axis(format="%b %d" if view == "Daily" else "%b %Y")),
            y=alt.Y("scrap_rate:Q", title="Scrap Rate (%)", scale=alt.Scale(zero=True)),
            tooltip=[
                alt.Tooltip("period_display:N", title="Date"),
                alt.Tooltip("total_defects:Q", title="Defect Count", format=",.0f"),
                alt.Tooltip("scrap_count:Q", title="Scrap Count", format=",.0f"),
                alt.Tooltip("scrap_rate:Q", title="Scrap Rate %", format=".1f"),
            ],
        ).properties(height=400, title=f"{view} Scrap Rate Trend").interactive()

        st.altair_chart(scrap_chart, use_container_width=True)
    except Exception:
        # fallback: simple plotly
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["period"], y=df["scrap_rate"], mode="lines+markers", name="Scrap Rate", line=dict(color="red")))
        fig.update_layout(title=f"{view} Scrap Rate Trend", xaxis_title=view, yaxis_title="Scrap Rate (%)", height=400)
        fig.update_xaxes(type="date", tickformat="%b %Y")
        st.plotly_chart(fig, use_container_width=True)


# ------------------------ Advanced analysis --------------------------------
def render_advanced_analysis(engine):
    """Several advanced SQL-driven analyses kept compact and readable."""
    st.markdown("### 🔍 Advanced Quality Analysis")

    # Operator-machine combinations heatmap
    operator_query = """
    SELECT
        who_made_it as operator_id,
        code_description as defect,
        machine_no,
        COUNT(*) as defect_count,
        COUNT(CASE WHEN disposition = 'SCRAP' THEN 1 END) as scrap_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 1,2,3
    ORDER BY 4 DESC
    LIMIT 50
    """
    try:
        operator_data = pd.read_sql(operator_query, engine)
    except Exception as e:
        st.error(f"Advanced analysis query failed: {e}")
        return None

    if not operator_data.empty:
        pivot = operator_data.pivot_table(index="operator_id", columns="machine_no", values="defect_count", aggfunc="sum").fillna(0)
        if not pivot.empty and len(pivot) > 1:
            fig = px.imshow(pivot, title="Operator Defects by Machine", aspect="auto", color_continuous_scale="Reds")
            st.plotly_chart(fig, use_container_width=True)

        display_data = operator_data.head(15)[["operator_id", "machine_no", "defect", "defect_count", "scrap_count"]].copy()
        display_data["scrap_rate"] = (display_data["scrap_count"] / display_data["defect_count"] * 100).round(1)
        st.markdown("**Top Operator-Machine Combinations**")
        st.dataframe(display_data, use_container_width=True)

    # Top defective machines
    machine_query = """
    SELECT
        machine_no,
        code_description as defect,
        COUNT(*) as defect_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 1,2
    ORDER BY 3 DESC
    LIMIT 15
    """
    try:
        machine_data = pd.read_sql(machine_query, engine)
        if not machine_data.empty:
            fig = px.sunburst(machine_data, path=["machine_no", "defect"], values="defect_count", title="Machine-Defect Relationship")
            st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass


# ------------------------ Export helper (top operators) ------------------------
def get_top_operators_section(engine, start_month: Optional[pd.Timestamp] = None, end_month: Optional[pd.Timestamp] = None, top_n: int = 10) -> Tuple[Optional[go.Figure], pd.DataFrame]:
    """
    Return (fig, df) for top operators between start_month and end_month.
    If start_month/end_month are None, operate on the full window available.
    """
    df = fetch_operator_data(engine, months=36)
    if df.empty:
        return None, pd.DataFrame()

    if start_month is None:
        start_month = df["month"].min()
    if end_month is None:
        end_month = df["month"].max()

    filtered = filter_operator_data_by_month_range(df, start_month, end_month)
    if filtered.empty:
        return None, pd.DataFrame()

    agg = compute_operator_aggregates(filtered)
    top_df = agg.head(top_n)
    if top_df.empty:
        return None, top_df

    fig = px.bar(top_df, x="operator_id", y="defect_count", title=f"Top {min(len(top_df), top_n)} Operators by Defect Count", labels={"operator_id": "Operator", "defect_count": "Total Defects"})
    return fig, top_df