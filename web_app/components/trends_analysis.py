import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def time_trends(df):
    """Display defect trends over time"""
    st.markdown("## 📈 Defect Trends Over Time")
    
    if df.empty:
        st.info("No data available for trend analysis.")
        return
    
    # Data validation and cleaning
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    
    if df.empty:
        st.warning("No valid date data available after cleaning.")
        return
    
    # Date range filter
    min_date, max_date = df['date'].min(), df['date'].max()
    date_range = st.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    
    if len(date_range) == 2:
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    if df.empty:
        st.warning("No data in selected date range.")
        return
    
    # Daily defect trend
    render_daily_trend(df)
    
    # Disposition trend
    if 'disposition_norm' in df.columns:
        render_disposition_trend(df)
    
    # Trend summary
    render_trend_summary(df)

def render_daily_trend(df):
    """Render daily defect trend chart"""
    daily_trend = df.groupby(df['date'].dt.date).size().reset_index()
    daily_trend.columns = ['date', 'defect_count']
    
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Scatter(
        x=daily_trend['date'],
        y=daily_trend['defect_count'],
        mode='lines+markers',
        name='Daily Defects',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=6, color='#1f77b4'),
        hovertemplate='<b>%{x}</b><br>Defects: %{y}<extra></extra>'
    ))
    
    # Add 7-day moving average
    if len(daily_trend) >= 7:
        daily_trend['moving_avg'] = daily_trend['defect_count'].rolling(window=7, min_periods=1).mean()
        fig_daily.add_trace(go.Scatter(
            x=daily_trend['date'],
            y=daily_trend['moving_avg'],
            mode='lines',
            name='7-Day Average',
            line=dict(color='#ff7f0e', width=2, dash='dash')
        ))
    
    fig_daily.update_layout(
        title="📈 Daily Defect Trend",
        template='plotly_white',
        xaxis_title="Date",
        yaxis_title="Defect Count",
        hovermode='x unified',
        showlegend=True,
        height=400
    )
    st.plotly_chart(fig_daily, use_container_width=True)

def render_disposition_trend(df):
    """Render disposition trend chart"""
    disposition_trend = df.groupby([df['date'].dt.date, 'disposition_norm']).size().reset_index()
    disposition_trend.columns = ['date', 'disposition', 'count']
    
    # Only show top 3 dispositions
    top_dispositions = disposition_trend.groupby('disposition')['count'].sum().nlargest(3).index
    disposition_trend = disposition_trend[disposition_trend['disposition'].isin(top_dispositions)]
    
    fig_disp = px.area(
        disposition_trend,
        x='date',
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
        height=400
    )
    st.plotly_chart(fig_disp, use_container_width=True)

def render_trend_summary(df):
    """Render trend summary metrics"""
    daily_trend = df.groupby(df['date'].dt.date).size().reset_index()
    daily_trend.columns = ['date', 'defect_count']
    
    st.markdown("### 📋 Trend Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_daily = daily_trend['defect_count'].mean()
        st.metric("Avg Daily Defects", f"{avg_daily:.1f}")
    
    with col2:
        max_daily = daily_trend['defect_count'].max()
        st.metric("Peak Daily Defects", f"{max_daily:.0f}")
    
    with col3:
        total_defects = daily_trend['defect_count'].sum()
        st.metric("Total Defects", f"{total_defects:,}")
    
    with col4:
        if len(daily_trend) > 1:
            trend = "📈 Increasing" if daily_trend['defect_count'].iloc[-1] > daily_trend['defect_count'].iloc[0] else "📉 Decreasing"
            st.metric("Overall Trend", trend)