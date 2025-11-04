import numpy as np
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta


def defect_pareto(engine, top_n=15):
    """Main pareto analysis function - updated for database integration"""
    st.markdown("## 📈 Quality Intelligence Dashboard")
    
    # Load data from database
    df = load_data_from_db(engine)
    
    if df.empty:
        st.info("No data available for analysis")
        return
    
    # Four tabs for different analyses
    tab1, tab2, tab3, tab4 = st.tabs([
        "🔧 Chronic Issues", 
        "👥 Operator Trends", 
        "📊 Daily Performance",
        "🔍 Advanced Analysis"
    ])
    
    with tab1:
        render_chronic_issues(engine, top_n)
    
    with tab2:
        render_operator_trends(engine)
    
    with tab3:
        render_daily_performance(engine)
    
    with tab4:
        render_advanced_analysis(engine)

def run_query(query, engine):
    """Run SQL query and return DataFrame"""
    if not hasattr(engine, "connect"):
        st.error(f"❌ Invalid engine passed to run_query (got {type(engine)})")
        return pd.DataFrame()
    try:
        return pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()

def load_data_from_db(engine):
    """Load data from database"""
    try:
        # Quick test to confirm engine works
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




def render_chronic_issues(engine, top_n):
    """Show chronic/recurring quality issues - DIRECT FROM DATABASE"""
    st.markdown("### 🔧 Chronic Quality Issues")
    st.info("Top recurring defects that need permanent solutions")
    
    # Query 1: Get defect counts directly from database
    defect_query = """
    SELECT 
        code_description as defect,
        COUNT(*) as count,
        COUNT(CASE WHEN disposition = 'SCRAP' THEN 1 END) as scrap_count
    FROM quality.clean_quality_data
    GROUP BY code_description
    ORDER BY count DESC
    LIMIT %s
    """
    
    try:
        # Get defect data directly from database
        defect_data = pd.read_sql(defect_query, engine, params=(top_n,))
        
        if defect_data.empty:
            st.warning("No defect data available from database")
            return
        
        # Create Pareto chart from database results
        fig = go.Figure()
        
        # Bar chart for counts
        fig.add_trace(go.Bar(
            x=defect_data['defect'],
            y=defect_data['count'],
            name="Count",
            marker_color='#3366cc',
            text=defect_data['count'],
            textposition='auto',
        ))
        
        # Calculate cumulative percentages
        total_defects = defect_data['count'].sum()
        defect_data['percentage'] = (defect_data['count'] / total_defects * 100).round(1)
        defect_data['cumulative_percentage'] = defect_data['percentage'].cumsum()
        
        # Line chart for cumulative percentage
        fig.add_trace(go.Scatter(
            x=defect_data['defect'],
            y=defect_data['cumulative_percentage'],
            name="Cumulative %",
            yaxis="y2",
            line=dict(color='#ff9900', width=3),
            marker=dict(size=8)
        ))
        
        fig.update_layout(
            title="Most Frequent Defects - Direct from Database",
            xaxis_title="Defect Type",
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
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Query 2: Get total metrics directly from database
        metrics_query = """
        SELECT 
            COUNT(*) as total_defects,
            COUNT(DISTINCT code_description) as unique_defects,
            COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as total_scrap
        FROM quality.clean_quality_data
        """
        
        metrics_data = pd.read_sql(metrics_query, engine)
        
        # Chronic issues insights
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_defects = metrics_data['total_defects'].iloc[0]
            st.metric("Total Defects", f"{total_defects:,}")
        
        with col2:
            if not defect_data.empty:
                top_3_coverage = defect_data.head(3)['count'].sum() / total_defects * 100
                st.metric("Top 3 Issues Coverage", f"{top_3_coverage:.1f}%")
        
        with col3:
            unique_defects = metrics_data['unique_defects'].iloc[0]
            st.metric("Unique Defect Types", unique_defects)
            
        with col4:
            scrap_rate = (metrics_data['total_scrap'].iloc[0] / total_defects * 100).round(1)
            st.metric("Overall Scrap Rate", f"{scrap_rate}%")
        
        # Actionable insights
        st.markdown("#### 💡 Improvement Opportunities")
        if not defect_data.empty:
            top_issue = defect_data.iloc[0]
            scrap_rate_top = (top_issue['scrap_count'] / top_issue['count'] * 100).round(1)
            st.warning(f"**Priority #1**: {top_issue['defect']} - {top_issue['count']} occurrences ({top_issue['percentage']:.1f}%), Scrap Rate: {scrap_rate_top}%")
            
            if len(defect_data) > 1:
                second_issue = defect_data.iloc[1]
                scrap_rate_second = (second_issue['scrap_count'] / second_issue['count'] * 100).round(1)
                st.info(f"**Priority #2**: {second_issue['defect']} - {second_issue['count']} occurrences, Scrap Rate: {scrap_rate_second}%")
                
        # Show defect details table
        st.markdown("#### 📋 Defect Details")
        display_data = defect_data[['defect', 'count', 'scrap_count', 'percentage']].copy()
        display_data['scrap_rate'] = (display_data['scrap_count'] / display_data['count'] * 100).round(1)
        st.dataframe(display_data, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error loading data from database: {e}")
import streamlit as st
import pandas as pd
import numpy as np

import streamlit as st
import pandas as pd
import numpy as np

def render_operator_trends(engine):
    """Show operator performance trends over time using monthly aggregation"""
    st.markdown("### 👥 Operator Performance Trends")
    st.info("Monthly defect and scrap analysis by operator (last 12 months)")

    # ---------------- SQL QUERY ----------------
    operator_query = """
    SELECT
        DATE_TRUNC('month', date)::date AS month,
        who_made_it AS operator_id,
        COUNT(*) AS defect_count,
        SUM(CASE WHEN disposition = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '12 months'
      AND who_made_it IS NOT NULL
    GROUP BY DATE_TRUNC('month', date)::date, who_made_it
    ORDER BY month, who_made_it
    """

    # Load data from the database
    operator_data = pd.read_sql(operator_query, engine)

    if operator_data.empty:
        st.warning("No operator trend data available.")
        return

    # ---------------- DATA CLEANING ----------------
    operator_data['month'] = pd.to_datetime(operator_data['month'])
    operator_data['scrap_rate'] = np.where(
        operator_data['defect_count'] == 0,
        0,
        (operator_data['scrap_count'] / operator_data['defect_count']) * 100
    ).round(2)

    # ---------------- TOP OPERATORS ----------------
    top_operators = (
        operator_data.groupby('operator_id')['defect_count']
        .sum()
        .nlargest(10)
        .index
    )

    st.markdown("#### 🔝 Top Operators by Total Defects (Last 12 Months)")
    st.dataframe(
        operator_data.groupby('operator_id')['defect_count']
        .sum()
        .sort_values(ascending=False)
        .reset_index()
        .rename(columns={'defect_count': 'Total Defects'})
    )

    selected_operators = st.multiselect(
        "Select operators to analyze:",
        options=operator_data['operator_id'].unique(),
        default=list(top_operators[:5])
    )

    if not selected_operators:
        st.warning("Please select at least one operator.")
        return

    filtered = operator_data[operator_data['operator_id'].isin(selected_operators)]

    # ---------------- MONTHLY DEFECT TREND ----------------
    st.subheader("📈 Monthly Defects per Operator")

    defects_pivot = filtered.pivot_table(
        index='month',
        columns='operator_id',
        values='defect_count',
        aggfunc='sum'
    ).fillna(0)

    st.line_chart(defects_pivot, height=400)

    # ---------------- MONTHLY SCRAP RATE TREND ----------------
    st.subheader("📉 Monthly Scrap Rate (%) per Operator")

    scrap_pivot = filtered.pivot_table(
        index='month',
        columns='operator_id',
        values='scrap_rate',
        aggfunc='mean'
    ).fillna(0)

    st.line_chart(scrap_pivot, height=400)

    # ---------------- KPI SUMMARY ----------------
    st.subheader("📊 Operator Summary (Last 12 Months)")

    kpi = (
        filtered.groupby('operator_id')[['defect_count', 'scrap_count']]
        .sum()
        .reset_index()
    )
    kpi['scrap_rate (%)'] = (kpi['scrap_count'] / kpi['defect_count'] * 100).round(1)
    st.dataframe(kpi.sort_values('defect_count', ascending=False))


def render_daily_performance(engine):
    """Show daily performance trends and comparisons - DIRECT FROM DATABASE"""
    st.markdown("### 📊 Daily Performance Trends")
    
    # Query for daily performance data
    daily_query = """
    SELECT 
        DATE(date) as date,
        COUNT(*) as total_defects,
        COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY DATE(date)
    ORDER BY date DESC
    """
    
    try:
        daily_data = pd.read_sql(daily_query, engine)
        
        if daily_data.empty:
            st.warning("No daily data available for analysis")
            return
        
        # Calculate scrap rate
        daily_data['scrap_rate'] = (daily_data['scrap_count'] / daily_data['total_defects'] * 100).round(1)
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        
        # Latest day vs average comparison
        latest_day = daily_data.iloc[0]  # Most recent day (DESC order)
        historical_avg = daily_data.iloc[1:].mean()  # Exclude latest day
        
        # Comparison metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            defects_vs_avg = latest_day['total_defects'] - historical_avg['total_defects']
            st.metric(
                "Latest Day Defects", 
                f"{latest_day['total_defects']}",
                delta=f"{defects_vs_avg:+.0f} vs avg"
            )
        
        with col2:
            scrap_vs_avg = latest_day['scrap_count'] - historical_avg['scrap_count']
            st.metric(
                "Latest Day Scrap", 
                f"{latest_day['scrap_count']}",
                delta=f"{scrap_vs_avg:+.0f} vs avg"
            )
        
        with col3:
            scrap_rate_vs_avg = latest_day['scrap_rate'] - historical_avg['scrap_rate']
            st.metric(
                "Latest Scrap Rate", 
                f"{latest_day['scrap_rate']:.1f}%",
                delta=f"{scrap_rate_vs_avg:+.1f}% vs avg"
            )
        
        with col4:
            trend_direction = "📈 Worse" if defects_vs_avg > 0 else "📉 Better"
            st.metric("Trend Direction", trend_direction)
        
        # Daily trends chart
        st.markdown("#### 📈 30-Day Trend")
        if len(daily_data) > 1:
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=daily_data['date'],
                y=daily_data['total_defects'],
                name='Daily Defects',
                line=dict(color='#1f77b4', width=3),
                mode='lines+markers'
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_data['date'],
                y=daily_data['scrap_rate'],
                name='Scrap Rate %',
                line=dict(color='#d62728', width=2, dash='dot'),
                yaxis='y2'
            ))
            
            fig.update_layout(
                title="Daily Defects & Scrap Rate Trend (Last 30 Days)",
                xaxis_title="Date",
                yaxis_title="Defect Count",
                yaxis2=dict(
                    title="Scrap Rate %",
                    overlaying='y',
                    side='right'
                ),
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Weekly summary
        st.markdown("#### 📅 Weekly Performance")
        weekly_query = """
        SELECT 
            EXTRACT(WEEK FROM date) as week_number,
            COUNT(*) as total_defects,
            COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_count
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '8 weeks'
        GROUP BY week_number
        ORDER BY week_number
        """
        
        weekly_data = pd.read_sql(weekly_query, engine)
        if not weekly_data.empty:
            weekly_data['scrap_rate'] = (weekly_data['scrap_count'] / weekly_data['total_defects'] * 100).round(1)
            st.dataframe(weekly_data, use_container_width=True)
            
    except Exception as e:
        st.error(f"Error loading daily performance data: {e}")

def render_advanced_analysis(engine):
    """New advanced analyses from SQL queries"""
    st.markdown("### 🔍 Advanced Quality Analysis")
    
    # Analysis 1: Operator defect rate with machine details
    st.markdown("#### 👥 Operator-Machine Defect Analysis")
    operator_query = """
    SELECT 
        who_made_it as operator_id,
        code_description as defect,
        machine_no,
        COUNT(*) as defect_count,
        COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_count
    FROM quality.clean_quality_data  
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 1, 2, 3
    ORDER BY 4 DESC
    LIMIT 50
    """
    
    operator_data = run_query(operator_query, engine)
    
    if not operator_data.empty:
        # Pivot table for heatmap
        pivot_data = operator_data.pivot_table(
            index='operator_id',
            columns='machine_no',
            values='defect_count',
            aggfunc='sum'
        ).fillna(0)
        
        if not pivot_data.empty and len(pivot_data) > 1:
            fig = px.imshow(
                pivot_data,
                title="Operator Defects by Machine (Heatmap)",
                aspect="auto",
                color_continuous_scale="reds"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Top operator-machine combinations
        st.markdown("**Top Operator-Machine Defect Combinations**")
        display_data = operator_data.head(15)[['operator_id', 'machine_no', 'defect', 'defect_count', 'scrap_count']]
        display_data['scrap_rate'] = (display_data['scrap_count'] / display_data['defect_count'] * 100).round(1)
        st.dataframe(display_data, use_container_width=True)
    
    # Analysis 2: Top defective machines
    st.markdown("#### 🏭 Top Defective Machines Analysis")
    machine_query = """
    SELECT 
        machine_no,
        code_description as defect,
        COUNT(*) as defect_count
    FROM quality.clean_quality_data  
    WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY 1, 2
    ORDER BY 3 DESC
    LIMIT 15
    """
    
    machine_data = run_query(machine_query, engine)
    
    if not machine_data.empty:
        fig = px.sunburst(
            machine_data,
            path=['machine_no', 'defect'],
            values='defect_count',
            title="Machine-Defect Relationship (Sunburst Chart)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Analysis 3: Monthly defect trends by category
    st.markdown("#### 📅 Monthly Defect Trends by Category")
    monthly_query = """
    SELECT 
        DATE_TRUNC('month', date) as month,
        category,
        COUNT(*) as defect_count
    FROM quality.clean_quality_data  
    WHERE date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
    """
    
    monthly_data = run_query(monthly_query, engine)
    
    if not monthly_data.empty:
        monthly_data['month'] = pd.to_datetime(monthly_data['month'])
        
        fig = px.line(
            monthly_data,
            x='month',
            y='defect_count',
            color='category',
            title="Monthly Defect Trends by Category",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Analysis 4: Monthly operator performance
    st.markdown("#### 📊 Monthly Operator Performance")
    operator_monthly_query = """
    SELECT
        DATE_TRUNC('month', date) as month,
        who_made_it as operator_id,
        COUNT(*) as defect_count,
        COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_count
    FROM quality.clean_quality_data
    WHERE date >= CURRENT_DATE - INTERVAL '6 months'
    GROUP BY 1, 2
    HAVING COUNT(*) >= 5
    ORDER BY 1, 3 DESC
    """
    
    operator_monthly_data = run_query(operator_monthly_query, engine)
    
    if not operator_monthly_data.empty:
        operator_monthly_data['month'] = pd.to_datetime(operator_monthly_data['month'])
        operator_monthly_data['scrap_rate'] = (operator_monthly_data['scrap_count'] / operator_monthly_data['defect_count'] * 100).round(1)
        
        # Top 10 operators by defect count
        top_operators = operator_monthly_data.groupby('operator_id')['defect_count'].sum().nlargest(10).index
        filtered_data = operator_monthly_data[operator_monthly_data['operator_id'].isin(top_operators)]
        
        fig = px.line(
            filtered_data,
            x='month',
            y='defect_count',
            color='operator_id',
            title="Top 10 Operators - Monthly Defect Trends",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)

def create_modern_pareto_chart(series, title, xaxis_title, top_n=15):
    """Create a modern Pareto chart"""
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