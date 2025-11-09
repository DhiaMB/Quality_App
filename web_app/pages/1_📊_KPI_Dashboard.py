import streamlit as st
import os
import sys
import pandas as pd
import sqlalchemy
from sqlalchemy import text

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from components.kpi_dashboard import QualityApp
from etl.utils.db_utils import get_target_engine

def main():
    st.set_page_config(page_title="KPI Dashboard", layout="wide")
    
    try:
        engine = get_target_engine()


        #st.sidebar.markdown("### Connection diagnostics")
        #st.sidebar.write("get_target_engine() ->", repr(engine))
      #  st.sidebar.write("type(engine) ->", type(engine))
       # st.sidebar.write("is instance of pd.DataFrame ->", isinstance(engine, pd.DataFrame))
        #st.sidebar.write("has attr 'connect' ->", hasattr(engine, "connect"))
   #     st.sidebar.write("has attr 'cursor' ->", hasattr(engine, "cursor"))
    #    st.sidebar.write("has attr 'execute' ->", hasattr(engine, "execute"))

        # Try a test DB call (safe) only if engine looks like a real SQLAlchemy engine/connection
        def looks_like_engine(e):
            try:
                import sqlalchemy
                return hasattr(e, "connect") or isinstance(e, sqlalchemy.engine.Engine)
            except Exception:
                return False

        if looks_like_engine(engine):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                st.sidebar.success("DB test query succeeded (SELECT 1)")
            except Exception as ex:
                st.sidebar.error(f"DB test query failed: {ex}")
        else:
            st.sidebar.error("Engine does not look like a SQLAlchemy engine. Check get_target_engine() and callers.")
        app = QualityApp(engine)
        app.run()
        
    except Exception as e:
        st.error(f"❌ Error loading KPI Dashboard: {e}")
        st.info("Please check your database connection and ensure data is available.")

if __name__ == "__main__":
    main()