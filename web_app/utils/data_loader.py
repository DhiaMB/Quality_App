import pandas as pd
import streamlit as st
from etl.utils.db_utils import get_target_engine

def load_data(engine, days=None, table="quality.clean_quality_data"):
    """Load and clean quality data from database"""
    query = f"""
        SELECT id, part_number, serial_number, date, shift, disposition,
               code_description, category, type, load_date, load_timestamp
        FROM {table}
        WHERE date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY date DESC
    """
    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

    if df.empty:
        return df

    return clean_quality_data(df)

def clean_quality_data(df):
    """Clean and standardize quality data"""
    # Date conversion
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['load_timestamp'] = pd.to_datetime(df['load_timestamp'], errors='coerce')
    
    # Text standardization
    text_columns = ['shift', 'disposition', 'part_number', 'code_description']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype('string').str.strip().str.upper()

    # Disposition normalization
    disposition_map = {
        'SCRAP': 'SCRAP', 'SCRAPPED': 'SCRAP',
        'REPAIRED': 'REPAIRED', 'REPAIR': 'REPAIRED',
        'OK': 'OK', 'PASS': 'OK', 'USE AS IS': 'OK'
    }
    df['disposition_norm'] = df['disposition'].map(disposition_map).fillna(df['disposition'])

    return df