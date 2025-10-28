import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from web_app.utils.chart_builder import create_modern_pareto_chart

def defect_pareto(df, top_n=15):
    """Redesigned Pareto analysis with meaningful quality charts"""
    st.markdown("## 📈 Quality Intelligence Dashboard")
    
    if df.empty:
        st.info("No data available for analysis")
        return
    
    # Three meaningful tabs for quality team
    tab1, tab2, tab3 = st.tabs([
        "🔧 Chronic Issues", 
        "🚨 Today's Hot Spots", 
        "📊 Daily Performance"
    ])
    
    with tab1:
        render_chronic_issues(df, top_n)
    
    with tab2:
        render_daily_performance(df)

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
            top_3_coverage = pareto_data.head(3)['percentage'].sum()
            st.metric("Top 3 Issues Coverage", f"{top_3_coverage:.1f}%")
    
    with col3:
        unique_defects = df['code_description'].nunique()
        st.metric("Unique Defect Types", unique_defects)
    
    # Actionable insights
    st.markdown("#### 💡 Improvement Opportunities")
    if not pareto_data.empty:
        top_issue = pareto_data.iloc[0]
        st.warning(f"**Priority #1**: {top_issue['category']} - {top_issue['count']} occurrences ({top_issue['percentage']}%)")
        
        if len(pareto_data) > 1:
            second_issue = pareto_data.iloc[1]
            st.info(f"**Priority #2**: {second_issue['category']} - {second_issue['count']} occurrences")

def render_daily_performance(df):
    """Show daily performance trends and comparisons - FIXED VERSION"""
    st.markdown("### 📊 Daily Performance Trends")
    st.info("Track daily performance against historical averages")
    
    if df.empty or 'date' not in df.columns:
        st.warning("No date data available")
        return
    
    try:
        # Calculate daily trends - only include numeric columns
        daily_stats = df.groupby(df['date'].dt.date).agg({
            'id': 'count',
            'disposition_norm': lambda x: (x == 'SCRAP').sum()
        }).reset_index()
        
        daily_stats.columns = ['date', 'total_defects', 'scrap_count']
        daily_stats['scrap_rate'] = (daily_stats['scrap_count'] / daily_stats['total_defects'] * 100).round(1)
        
        if daily_stats.empty or len(daily_stats) < 2:
            st.warning("Need at least 2 days of data for trend analysis")
            return
        
        # Latest day vs average comparison - FIXED
        latest_day = daily_stats.iloc[-1]
        
        # Calculate historical average excluding latest day - only numeric columns
        historical_data = daily_stats[:-1]  # Exclude latest day
        historical_avg = {
            'total_defects': historical_data['total_defects'].mean(),
            'scrap_count': historical_data['scrap_count'].mean(),
            'scrap_rate': historical_data['scrap_rate'].mean()
        }
        
        # Comparison metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            defects_vs_avg = latest_day['total_defects'] - historical_avg['total_defects']
            st.metric(
                "Defects Today vs Avg", 
                f"{latest_day['total_defects']}",
                delta=f"{defects_vs_avg:+.0f}",
                delta_color="normal" if defects_vs_avg <= 0 else "inverse"
            )
        
        with col2:
            scrap_vs_avg = latest_day['scrap_count'] - historical_avg['scrap_count']
            st.metric(
                "Scrap Today vs Avg", 
                f"{latest_day['scrap_count']}",
                delta=f"{scrap_vs_avg:+.0f}",
                delta_color="normal" if scrap_vs_avg <= 0 else "inverse"
            )
        
        with col3:
            scrap_rate_vs_avg = latest_day['scrap_rate'] - historical_avg['scrap_rate']
            st.metric(
                "Scrap Rate vs Avg", 
                f"{latest_day['scrap_rate']:.1f}%",
                delta=f"{scrap_rate_vs_avg:+.1f}%",
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
            st.write("Daily stats data:", daily_stats)