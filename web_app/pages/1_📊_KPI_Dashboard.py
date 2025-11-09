import streamlit as st
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from components.kpi_dashboard import QualityApp
from etl.utils.db_utils import get_target_engine

def main():
    st.set_page_config(page_title="KPI Dashboard", layout="wide")
    
    try:
        engine = get_target_engine()
        app = QualityApp(engine)
        app.run()
        
    except Exception as e:
        st.error(f"❌ Error loading KPI Dashboard: {e}")
        st.info("Please check your database connection and ensure data is available.")

if __name__ == "__main__":
    main()