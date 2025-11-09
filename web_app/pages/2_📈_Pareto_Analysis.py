import streamlit as st
from components.pareto_analysis import defect_pareto
from etl.utils.db_utils import get_target_engine

def main():
    engine = get_target_engine()
    defect_pareto(engine,top_n=15)

if __name__ == "__main__":
    main()
