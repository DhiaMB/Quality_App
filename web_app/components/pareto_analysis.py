import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from web_app.utils.chart_builder import create_modern_pareto_chart
from datetime import datetime, timedelta

def defect_pareto(df, top_n=15):
    """Redesigned Pareto analysis with meaningful quality charts"""
    st.markdown("## 📈 Quality Intelligence Dashboard")
    
    if df.empty:
        st.info("No data available for analysis")
        return
    
    # Data preprocessing - fix column names and types
    df = preprocess_data(df)
    
    # Three meaningful tabs for quality team
    tab1, tab2, tab3 = st.tabs([
        "🔧 Chronic Issues", 
        "🚨 Today's Hot Spots", 
        "📊 Daily Performance"
    ])
    
    with tab1:
        render_chronic_issues(df, top_n)
    
    with tab2:
        render_todays_hotspots(df)
    
    with tab3:
        render_daily_performance(df)

def preprocess_data(df):
    """Fix column names and data types"""
    # Create consistent column names (adjust based on your actual CSV)
    if 'Code description' in df.columns:
        df['code_description'] = df['Code description']
    if 'Who made it' in df.columns:
        df['operator'] = df['Who made it']
    if 'Disposition' in df.columns:
        df['disposition'] = df['Disposition']
        df['disposition_norm'] = df['Disposition'].str.upper()
    
    # Convert date column
    date_column = None
    for col in ['Date', 'date', 'DATE']:
        if col in df.columns:
            date_column = col
            break
    
    if date_column:
        df['date'] = pd.to_datetime(df[date_column])
        # Create date-only column for grouping
        df['date_only'] = df['date'].dt.date
    
    # Create a unique ID if not present
    if 'id' not in df.columns:
        df['id'] = range(1, len(df) + 1)
    
    return df

def render_chronic_issues(df, top_n):
    """Show chronic/recurring quality issues"""
    st.markdown("### 🔧 Chronic Quality Issues")
    st.info("Top recurring defects that need permanent solutions")
    
    if 'code_description' not in df.columns or df.empty:
        st.warning("No defect data available")
        return
    
    # All-time defect Pareto
    fig, pareto_data = create_modern_pareto_chart(
        df['code_description'], 
        "Most Frequent Defects - All Time",
        "Defect Type",
        top_n
    )
    
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    # Chronic issues insights
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_defects = len(df)
        st.metric("Total Defects", f"{total_defects:,}")
    
    with col2:
        if not pareto_data.empty:
            top_3_coverage = pareto_data.head(3)['cumulative_percentage'].iloc[2]
            st.metric("Top 3 Issues Coverage", f"{top_3_coverage:.1f}%")
    
    with col3:
        unique_defects = df['code_description'].nunique()
        st.metric("Unique Defect Types", unique_defects)
    
    # Actionable insights
    st.markdown("#### 💡 Improvement Opportunities")
    if not pareto_data.empty:
        top_issue = pareto_data.iloc[0]
        st.warning(f"**Priority #1**: {top_issue['category']} - {top_issue['count']} occurrences ({top_issue['percentage']:.1f}%)")
        
        if len(pareto_data) > 1:
            second_issue = pareto_data.iloc[1]
            st.info(f"**Priority #2**: {second_issue['category']} - {second_issue['count']} occurrences")

def render_todays_hotspots(df):
    """Show today's defect hotspots by operator and machine"""
    st.markdown("### 🚨 Today's Hot Spots")
    
    if 'date' not in df.columns:
        st.warning("No date data available")
        return
    
    # Get today's data
    today = pd.Timestamp.now().normalize()
    today_data = df[df['date'].dt.normalize() == today]
    
    if today_data.empty:
        st.info("No defects recorded today")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 👥 Top Defective Operators Today")
        if 'operator' in today_data.columns:
            operator_defects = today_data['operator'].value_counts().head(10)
            if not operator_defects.empty:
                fig = go.Figure(data=[go.Bar(
                    x=operator_defects.values,
                    y=operator_defects.index,
                    orientation='h',
                    marker_color='#ff6b6b'
                )])
                fig.update_layout(
                    title="Top Operators with Defects Today",
                    xaxis_title="Number of Defects",
                    yaxis_title="Operator ID",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No operator data available")
    
    with col2:
        st.markdown("#### 🏭 Top Defective Machines Today")
        if 'Machine no.' in today_data.columns:
            machine_defects = today_data['Machine no.'].value_counts().head(10)
            if not machine_defects.empty:
                fig = go.Figure(data=[go.Bar(
                    x=machine_defects.values,
                    y=machine_defects.index,
                    orientation='h',
                    marker_color='#4ecdc4'
                )])
                fig.update_layout(
                    title="Top Machines with Defects Today",
                    xaxis_title="Number of Defects",
                    yaxis_title="Machine Number",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No machine data available")
    
    # Today's summary
    st.markdown("#### 📋 Today's Summary")
    today_col1, today_col2, today_col3, today_col4 = st.columns(4)
    
    with today_col1:
        st.metric("Defects Today", len(today_data))
    
    with today_col2:
        scrap_today = len(today_data[today_data['disposition_norm'] == 'SCRAP']) if 'disposition_norm' in today_data.columns else 0
        st.metric("Scrap Today", scrap_today)
    
    with today_col3:
        unique_issues_today = today_data['code_description'].nunique() if 'code_description' in today_data.columns else 0
        st.metric("Unique Issues", unique_issues_today)
    
    with today_col4:
        operators_affected = today_data['operator'].nunique() if 'operator' in today_data.columns else 0
        st.metric("Operators Affected", operators_affected)

def render_daily_performance(df):
    """Show daily performance trends and comparisons - FIXED VERSION"""
    st.markdown("### 📊 Daily Performance Trends")
    st.info("Track daily performance against historical averages")
    
    if df.empty or 'date_only' not in df.columns:
        st.warning("No date data available")
        return
    
    try:
        # Calculate daily trends
        daily_stats = df.groupby('date_only').agg({
            'id': 'count',
            'disposition_norm': lambda x: (x == 'SCRAP').sum() if 'disposition_norm' in df.columns else 0
        }).reset_index()
        
        daily_stats.columns = ['date', 'total_defects', 'scrap_count']
        daily_stats['scrap_rate'] = (daily_stats['scrap_count'] / daily_stats['total_defects'] * 100).round(1)
        
        if daily_stats.empty:
            st.warning("No daily data available for analysis")
            return
        
        if len(daily_stats) < 2:
            st.warning("Need at least 2 days of data for trend analysis")
            st.write("Available data:", daily_stats)
            return
        
        # Latest day vs average comparison
        latest_day = daily_stats.iloc[-1]
        
        # Calculate historical average excluding latest day
        historical_avg = daily_stats[:-1].agg({
            'total_defects': 'mean',
            'scrap_count': 'mean', 
            'scrap_rate': 'mean'
        })
        
        # Comparison metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            defects_vs_avg = latest_day['total_defects'] - historical_avg['total_defects']
            st.metric(
                "Defects Today", 
                f"{latest_day['total_defects']}",
                delta=f"{defects_vs_avg:+.0f} vs avg",
                delta_color="normal" if defects_vs_avg <= 0 else "inverse"
            )
        
        with col2:
            scrap_vs_avg = latest_day['scrap_count'] - historical_avg['scrap_count']
            st.metric(
                "Scrap Today", 
                f"{latest_day['scrap_count']}",
                delta=f"{scrap_vs_avg:+.0f} vs avg",
                delta_color="normal" if scrap_vs_avg <= 0 else "inverse"
            )
        
        with col3:
            scrap_rate_vs_avg = latest_day['scrap_rate'] - historical_avg['scrap_rate']
            st.metric(
                "Scrap Rate", 
                f"{latest_day['scrap_rate']:.1f}%",
                delta=f"{scrap_rate_vs_avg:+.1f}% vs avg",
                delta_color="normal" if scrap_rate_vs_avg <= 0 else "inverse"
            )
        
        with col4:
            trend_direction = "📈 Worse" if defects_vs_avg > 0 else "📉 Better"
            st.metric("Overall Trend", trend_direction)
        
        # Daily trends chart - Last 7 days
        st.markdown("#### 📈 7-Day Trend")
        last_7_days = daily_stats.tail(7)
        
        if len(last_7_days) > 1:
            fig = go.Figure()
            
            # Defects line
            fig.add_trace(go.Scatter(
                x=last_7_days['date'],
                y=last_7_days['total_defects'],
                name='Daily Defects',
                line=dict(color='#1f77b4', width=3),
                mode='lines+markers'
            ))
            
            # Scrap rate line (secondary axis)
            fig.add_trace(go.Scatter(
                x=last_7_days['date'],
                y=last_7_days['scrap_rate'],
                name='Scrap Rate %',
                line=dict(color='#d62728', width=2, dash='dot'),
                yaxis='y2'
            ))
            
            # Historical average line
            fig.add_trace(go.Scatter(
                x=last_7_days['date'],
                y=[historical_avg['total_defects']] * len(last_7_days),
                name='Historical Avg Defects',
                line=dict(color='#1f77b4', width=1, dash='dash'),
                opacity=0.7
            ))
            
            fig.update_layout(
                title="Daily Defects & Scrap Rate Trend (Last 7 Days)",
                xaxis_title="Date",
                yaxis_title="Defect Count",
                yaxis2=dict(
                    title="Scrap Rate %",
                    overlaying='y',
                    side='right',
                    range=[0, max(last_7_days['scrap_rate']) * 1.2] if len(last_7_days) > 0 else [0, 100]
                ),
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Need more days of data for trend chart")
        
        # Performance summary
        st.markdown("#### 📋 Performance Summary")
        
        summary_col1, summary_col2 = st.columns(2)
        
        with summary_col1:
            st.markdown("**This Week vs Last Week**")
            
            if len(daily_stats) >= 14:
                this_week = daily_stats.tail(7)['total_defects'].mean()
                last_week = daily_stats.tail(14).head(7)['total_defects'].mean()
                week_change = ((this_week - last_week) / last_week * 100) if last_week > 0 else 0
                
                if week_change > 0:
                    st.error(f"📈 Defects increased by {week_change:.1f}% vs last week")
                else:
                    st.success(f"📉 Defects decreased by {abs(week_change):.1f}% vs last week")
            else:
                st.info("Need 2+ weeks of data for weekly comparison")
        
        with summary_col2:
            st.markdown("**Today's Alert Level**")
            
            if latest_day['total_defects'] > historical_avg['total_defects'] * 1.5:
                st.error("🔴 HIGH - Defects significantly above average")
            elif latest_day['total_defects'] > historical_avg['total_defects'] * 1.2:
                st.warning("🟡 MEDIUM - Defects above average")
            else:
                st.success("🟢 LOW - Defects at or below average")
                
    except Exception as e:
        st.error(f"Error in daily performance analysis: {str(e)}")
        # Show debug info
        st.markdown("#### 🔍 Debug Information")
        if 'daily_stats' in locals():
            st.write("Daily stats shape:", daily_stats.shape)
            st.write("Daily stats columns:", daily_stats.columns.tolist())
            st.write("Latest few rows:", daily_stats.tail())

# If you need a simple version of create_modern_pareto_chart, here's a basic implementation:
def create_modern_pareto_chart(series, title, xaxis_title, top_n=15):
    """Create a modern Pareto chart if your utils module isn't available"""
    counts = series.value_counts().head(top_n)
    
    if counts.empty:
        return None, pd.DataFrame()
    
    # Calculate percentages and cumulative percentages
    total = counts.sum()
    percentages = (counts / total * 100).round(1)
    cumulative_percentages = percentages.cumsum()
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Bar chart for counts
    fig.add_trace(go.Bar(
        x=counts.index,
        y=counts.values,
        name="Count",
        marker_color='#3366cc',
        text=counts.values,
        textposition='auto',
    ))
    
    # Line chart for cumulative percentage
    fig.add_trace(go.Scatter(
        x=counts.index,
        y=cumulative_percentages.values,
        name="Cumulative %",
        yaxis="y2",
        line=dict(color='#ff9900', width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_title,
        yaxis_title="Count",
        yaxis2=dict(
            title="Cumulative Percentage",
            overlaying="y",
            side="right",
            range=[0, 100]
        ),
        xaxis_tickangle=-45,
        hovermode="x unified",
        height=500
    )
    
    # Prepare pareto data
    pareto_data = pd.DataFrame({
        'category': counts.index,
        'count': counts.values,
        'percentage': percentages.values,
        'cumulative_percentage': cumulative_percentages.values
    })
    
    return fig, pareto_data