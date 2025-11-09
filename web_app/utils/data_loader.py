import pandas as pd
import streamlit as st
from sqlalchemy import text

def load_data(engine, days=None, table="quality.clean_quality_data", date_col="date"):
    """
    Load and clean quality data from the database and return a DataFrame with:
      - date_col as a timezone-naive pd.Timestamp (dtype datetime64[ns])
      - date_day column (datetime floored to midnight, dtype datetime64[ns])
      - rows with invalid/unparseable dates dropped
    Parameters:
      engine   : SQLAlchemy engine / connection
      days     : optional number of days of history to return (int)
      table    : table name (optionally schema-qualified)
      date_col : name of the datetime column in the table (default "date")
    Notes:
      - Attempts a DB-side cutoff when `days` is provided; falls back to reading the table
        and applying a client-side cutoff if the DB query fails.
      - Returns an empty DataFrame if the table cannot be read or if no valid dates remain.
    """
    if engine is None:
        raise ValueError("engine is required")

    df = None
    params = {}

    # Build the base SELECT (only pull columns commonly needed; adjust if you need more)
    select_cols = "id, part_number, serial_number, date, shift, disposition, code_description, category, type, load_date, load_timestamp"
    # Attempt DB-side cutoff using a parameterized timestamp (works across many dialects)
    try:
        if days is not None:
            cutoff_ts = pd.Timestamp.utcnow().floor("D") - pd.Timedelta(days=int(days))
            # Use ISO format (tz-naive UTC) for passing to DB
            params["cutoff"] = cutoff_ts.isoformat()
            sql = text(f"""
                SELECT {select_cols}
                FROM {table}
                WHERE {date_col} IS NOT NULL
                  AND {date_col} >= :cutoff
                ORDER BY {date_col} DESC
            """)
        else:
            sql = text(f"""
                SELECT {select_cols}
                FROM {table}
                WHERE {date_col} IS NOT NULL
                ORDER BY {date_col} DESC
            """)

        with engine.connect() as conn:
            df = pd.read_sql(sql, conn, params=params if params else None)
    except Exception:
        # DB-side filter/query failed — fall back to reading the table and filtering in pandas
        try:
            if "." in table:
                schema, tbl = table.split(".", 1)
            else:
                schema, tbl = None, table
            df = pd.read_sql_table(tbl, con=engine, schema=schema)
        except Exception as e:
            st.error(f"Unable to read table {table} from DB: {e}")
            return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Pass through cleaning & normalization
    return clean_quality_data(df, date_col=date_col, days=days)


def clean_quality_data(df, date_col="date", days=None):
    """
    Clean and standardize quality data.
    - Coerce date columns to tz-naive datetime64[ns]
    - Create date_day (date floored to midnight) for grouping/filtering
    - Standardize text columns and create disposition_norm
    - Apply client-side cutoff if days is provided (defensive)
    """
    df = df.copy()

    # Parse datetimes defensively
    df[date_col] = pd.to_datetime(df.get(date_col), errors="coerce")
    if "load_timestamp" in df.columns:
        df["load_timestamp"] = pd.to_datetime(df["load_timestamp"], errors="coerce")

    # Drop rows with invalid main date
    df = df.dropna(subset=[date_col])
    if df.empty:
        return pd.DataFrame()

    # Ensure timezone-naive (drop tz info). Try safe conversion/dropping.
    try:
        # If tz-aware, convert to UTC then drop tz info
        if getattr(df[date_col].dt, "tz", None) is not None:
            df[date_col] = df[date_col].dt.tz_convert("UTC").dt.tz_localize(None)
    except Exception:
        # If above fails, try tz_localize(None) which will drop tz on some Series types
        try:
            df[date_col] = df[date_col].dt.tz_localize(None)
        except Exception:
            # Last resort: coerce again (will drop tz info from string representations)
            df[date_col] = pd.to_datetime(df[date_col].astype(str), errors="coerce")

    # Re-drop any rows that couldn't be coerced
    df = df.dropna(subset=[date_col])
    if df.empty:
        return pd.DataFrame()

    # Ensure dtype is datetime64[ns]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if df.empty:
        return pd.DataFrame()

    # Add helper column date_day (midnight, tz-naive)
    df["date_day"] = df[date_col].dt.floor("D")

    # Client-side cutoff as extra safety if days provided and DB-side cutoff failed
    if days is not None:
        try:
            cutoff = pd.Timestamp.utcnow().floor("D") - pd.Timedelta(days=int(days))
            df = df[df[date_col] >= cutoff]
        except Exception:
            # ignore cutoff failure, return normalized df
            pass

    # Standardize text fields
    text_columns = ['shift', 'disposition', 'part_number', 'code_description']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip().str.upper()

    # Normalize disposition values with a fallback to original normalized uppercase value
    disposition_map = {
        'SCRAP': 'SCRAP', 'SCRAPPED': 'SCRAP',
        'REPAIRED': 'REPAIRED', 'REPAIR': 'REPAIRED',
        'OK': 'OK', 'PASS': 'OK', 'USE AS IS': 'OK'
    }
    if "disposition" in df.columns:
        df["disposition_norm"] = df["disposition"].map(disposition_map).fillna(df["disposition"])
    else:
        df["disposition_norm"] = pd.NA

    # Reset index for caller convenience
    df = df.reset_index(drop=True)

    return df