import streamlit as st
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from components.trends_analysis import time_trends
from etl.utils.db_utils import get_target_engine

def main():
    st.set_page_config(page_title="Trends Analysis", layout="wide")
    st.title("📈 Trends Analysis")
    
    try:
        engine = get_target_engine()
        
        # Add page-specific controls
        days = st.sidebar.selectbox(
            "Analysis Period", 
            [7, 14, 30, 60, 90], 
            index=2,
            help="Select the number of days to analyze"
        )
        
        # Pass the days parameter to time_trends
        time_trends(engine, days=days)
        
    except Exception as e:
        st.error(f"❌ Error loading Trends Analysis: {e}")

#if __name__ == "__main__":
  #  main()