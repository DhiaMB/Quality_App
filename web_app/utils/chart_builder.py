import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import streamlit as st

# Modern color palette
PALETTE = {
    "primary": "#1f77b4", "secondary": "#ff7f0e", "success": "#2ca02c",
    "danger": "#d62728", "warning": "#ff7f0e", "info": "#17becf",
    "light": "#f8f9fa", "dark": "#343a40"
}

def create_modern_pareto_chart(series, title, xaxis_title, top_n=20):
    """Create a modern, readable Pareto chart with robust error handling"""
    
    # Input validation
    if series is None or (hasattr(series, 'empty') and series.empty):
        st.warning("No data available for Pareto chart")
        return None, pd.DataFrame()
    
    try:
        # Handle different input types safely
        if hasattr(series, 'index') and hasattr(series, 'values'):
            # It's already a Series with index and values
            counts = series.head(top_n)
        elif hasattr(series, 'value_counts'):
            # It's a Series that needs value_counts
            counts = series.value_counts().head(top_n)
        else:
            st.error(f"Unsupported data type: {type(series)}")
            return None, pd.DataFrame()
        
        # Check if we have any data after processing
        if len(counts) == 0 or counts.isna().all():
            st.warning("No valid data points after processing")
            return None, pd.DataFrame()
        
        # Create DataFrame safely
        pareto_df = pd.DataFrame({
            'category': counts.index.astype(str),  # Ensure string type
            'count': pd.to_numeric(counts.values, errors='coerce')  # Ensure numeric
        }).reset_index(drop=True)
        
        # Remove any rows with invalid counts
        pareto_df = pareto_df.dropna(subset=['count'])
        
        if pareto_df.empty:
            st.warning("No valid data after cleaning")
            return None, pd.DataFrame()
        
        # Calculate total count safely
        total_count = pareto_df['count'].sum()
        
        # Check if total_count is valid
        if pd.isna(total_count) or total_count <= 0:
            st.warning("Invalid total count calculated")
            return None, pareto_df
        
        # Calculate percentages
        pareto_df['percentage'] = (pareto_df['count'] / total_count * 100).round(1)
        pareto_df['cumulative_percentage'] = pareto_df['percentage'].cumsum().round(1)
        
        # Create chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Bar chart - defects count
        fig.add_trace(
            go.Bar(
                x=pareto_df['category'],
                y=pareto_df['count'],
                name='Defect Count',
                marker_color=PALETTE['primary'],
                opacity=0.8,
                hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
            ),
            secondary_y=False,
        )
        
        # Line chart - cumulative percentage
        fig.add_trace(
            go.Scatter(
                x=pareto_df['category'],
                y=pareto_df['cumulative_percentage'],
                name='Cumulative %',
                line=dict(color=PALETTE['danger'], width=3),
                marker=dict(size=8, symbol='circle'),
                hovertemplate='<b>%{x}</b><br>Cumulative: %{y}%<extra></extra>'
            ),
            secondary_y=True,
        )
        
        # Update layout for modern look
        fig.update_layout(
            title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
            xaxis_title=xaxis_title,
            template='plotly_white',
            height=500,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            font=dict(family="Arial, sans-serif", size=12),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=80, l=60, r=60, b=80)
        )
        
        # Update axes
        fig.update_xaxes(tickangle=45, showgrid=False, tickfont=dict(size=11))
        fig.update_yaxes(title_text="Defect Count", secondary_y=False)
        fig.update_yaxes(title_text="Cumulative %", secondary_y=True, range=[0, 100])
        
        return fig, pareto_df
        
    except Exception as e:
        st.error(f"Error creating Pareto chart: {str(e)}")
        return None, pd.DataFrame()