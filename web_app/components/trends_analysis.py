import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from utils.data_loader import load_data

def time_trends(engine, days=30):
    """Display defect trends over time (robust to tz/dtype/aggregation issues)"""
    st.markdown("## 📈 Defect Trends Over Time")
    
    # Load data with the specified days parameter
    with st.spinner('Loading trend data...'):
        df = load_data(engine, days=days)
    
    if df is None or df.empty:
        st.info("No data available for trend analysis.")
        return
    
    # Work on a copy and normalize date column
    df = df.copy()
    # Coerce to datetimelike, drop rows that can't be parsed
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    # Remove timezone info (if present) to avoid comparison/coercion surprises
    df['date'] = df['date'].dt.tz_localize(None, ambiguous='NaT', nonexistent='NaT')
    df = df.dropna(subset=['date'])
    if df.empty:
        st.warning("No valid date data available after cleaning.")
        return

    # Create a normalized day column (datetime at midnight) to keep types consistent
    df['date_day'] = df['date'].dt.floor('D')  # preserves as datetime64[ns]

    # Date range selector: ensure default values are datetime.date objects
    min_date = df['date_day'].min().date()
    max_date = df['date_day'].max().date()
    date_range = st.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    # Normalize date_range input (st.date_input can return a single date or a tuple)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date = pd.to_datetime(date_range[0]).normalize()
        end_date = pd.to_datetime(date_range[1]).normalize()
    else:
        # single date selected -> show that single day
        start_date = pd.to_datetime(date_range).normalize()
        end_date = start_date

    # Filter using date_day (inclusive)
    df = df[(df['date_day'] >= start_date) & (df['date_day'] <= end_date)]
    if df.empty:
        st.warning("No data in selected date range.")
        return

    st.sidebar.info(f"📅 Analyzing last {days} days of data (showing {start_date.date()} → {end_date.date()})")

    # Daily defect trend
    render_daily_trend(df)

    # Disposition trend (if disposition_norm exists)
    if 'disposition_norm' in df.columns:
        render_disposition_trend(df)

    # Trend summary
    render_trend_summary(df)


def render_daily_trend(df):
    """Render daily defect trend chart (uses date_day datetime index, sorted)"""
    # Aggregate by normalized day
    daily_trend = df.groupby('date_day').size().rename('defect_count').reset_index()
    # Ensure sorting by date
    daily_trend = daily_trend.sort_values('date_day').reset_index(drop=True)

    # Convert date_day to proper datetime for plotting
    daily_trend['date_day'] = pd.to_datetime(daily_trend['date_day'])

    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=daily_trend['date_day'],
        y=daily_trend['defect_count'],
        mode='lines+markers',
        name='Daily Defects',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=6, color='#1f77b4'),
        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Defects: %{y}<extra></extra>'
    ))

    # Add 7-day moving average (computed on sorted series)
    if len(daily_trend) >= 1:
        daily_trend['moving_avg'] = daily_trend['defect_count'].rolling(window=7, min_periods=1).mean()
        fig_daily.add_trace(go.Scatter(
            x=daily_trend['date_day'],
            y=daily_trend['moving_avg'],
            mode='lines',
            name='7-Day Average',
            line=dict(color='#ff7f0e', width=2, dash='dash'),
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>7-day avg: %{y:.1f}<extra></extra>'
        ))

    fig_daily.update_layout(
        title="📈 Daily Defect Trend",
        template='plotly_white',
        xaxis_title="Date",
        yaxis_title="Defect Count",
        hovermode='x unified',
        showlegend=True,
        height=420
    )
    st.plotly_chart(fig_daily, use_container_width=True)


def render_disposition_trend(df):
    """Render disposition trend chart. Pivot to ensure zero-fill for missing dates/dispositions."""
    # Aggregate counts per day and disposition
    disposition_trend = (
        df.groupby(['date_day', 'disposition_norm'])
          .size()
          .rename('count')
          .reset_index()
    )

    if disposition_trend.empty:
        st.info("No disposition data to show.")
        return

    # Pick top dispositions across the selected range by total count
    top_dispositions = (
        disposition_trend.groupby('disposition_norm')['count']
        .sum()
        .nlargest(3)
        .index
        .tolist()
    )

    disposition_trend = disposition_trend[disposition_trend['disposition_norm'].isin(top_dispositions)]

    # Pivot so every date has an entry for each disposition (missing -> 0)
    pivot = disposition_trend.pivot_table(index='date_day', columns='disposition_norm', values='count', aggfunc='sum').fillna(0)
    pivot = pivot.sort_index()
    # Melt back for plotly express (ensures x is datetime and series are continuous)
    plot_df = pivot.reset_index().melt(id_vars='date_day', var_name='disposition', value_name='count')

    fig_disp = px.area(
        plot_df,
        x='date_day',
        y='count',
        color='disposition',
        title="🔄 Disposition Trend Over Time",
        color_discrete_sequence=px.colors.qualitative.Set2
    )

    fig_disp.update_layout(
        template='plotly_white',
        xaxis_title="Date",
        yaxis_title="Count",
        hovermode='x unified',
        height=420
    )
    st.plotly_chart(fig_disp, use_container_width=True)


def render_trend_summary(df):
    """Render trend summary statistics"""
    st.markdown("### 📊 Trend Summary")

    # Use date_day for day-based stats
    daily_counts = df.groupby('date_day').size().rename('count').reset_index()
    total_defects = int(len(df))
    avg_daily = float(daily_counts['count'].mean()) if not daily_counts.empty else 0.0
    peak_day = int(daily_counts['count'].max()) if not daily_counts.empty else 0
    date_range_days = (df['date_day'].max().normalize() - df['date_day'].min().normalize()).days + 1

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Defects", f"{total_defects:,}")

    with col2:
        st.metric("Avg Daily Defects", f"{avg_daily:.1f}")

    with col3:
        st.metric("Peak Daily Defects", f"{peak_day:,}")

    with col4:
        st.metric("Analysis Period", f"{date_range_days} days")