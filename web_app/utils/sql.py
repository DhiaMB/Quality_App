import pandas as pd
from typing import Optional

def _is_dataframe(obj) -> bool:
    return isinstance(obj, pd.DataFrame)

def load_agg_by_part(engine_or_df, curr_start, curr_end, prior_start, prior_end) -> pd.DataFrame:
    """
    Load per-part aggregated counts for current and prior windows.
    Accepts either:
      - a SQLAlchemy engine / DBAPI connection (preferred), or
      - a pandas.DataFrame (raw table) in-memory for testing/fallback.
    Returns DataFrame with columns:
      part_number, total_curr, scrap_curr, total_prior, scrap_prior, rate_curr, rate_prior
    """
    # If user passed a DataFrame, compute aggregates in-memory
    if _is_dataframe(engine_or_df):
        raw = engine_or_df.copy()
        if 'date' not in raw.columns:
            return pd.DataFrame()
        raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
        mask = (raw['date'] >= pd.to_datetime(prior_start)) & (raw['date'] <= pd.to_datetime(curr_end))
        raw = raw.loc[mask].dropna(subset=['date'])
        if raw.empty:
            return pd.DataFrame()
        # current
        curr_mask = (raw['date'] >= pd.to_datetime(curr_start)) & (raw['date'] <= pd.to_datetime(curr_end))
        prior_mask = (raw['date'] >= pd.to_datetime(prior_start)) & (raw['date'] <= pd.to_datetime(prior_end))
        curr = raw.loc[curr_mask].groupby('part_number').agg(
            total_curr=('part_number', 'size'),
            scrap_curr=('disposition', lambda s: (s == 'SCRAP').sum())
        ).reset_index()
        prior = raw.loc[prior_mask].groupby('part_number').agg(
            total_prior=('part_number', 'size'),
            scrap_prior=('disposition', lambda s: (s == 'SCRAP').sum())
        ).reset_index()
        merged = curr.merge(prior, on='part_number', how='left').fillna(0)
        # ensure ints
        for c in ['total_curr', 'scrap_curr', 'total_prior', 'scrap_prior']:
            if c in merged.columns:
                merged[c] = merged[c].astype(int)
            else:
                merged[c] = 0
        merged['rate_curr'] = merged.apply(lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0.0, axis=1)
        merged['rate_prior'] = merged.apply(lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0.0, axis=1)
        return merged

    # Otherwise, assume engine_or_df is a DB connection / SQLAlchemy engine
    query = """
    SELECT part_number,
       SUM(CASE WHEN date BETWEEN %(curr_start)s AND %(curr_end)s THEN 1 ELSE 0 END) AS total_curr,
       SUM(CASE WHEN date BETWEEN %(curr_start)s AND %(curr_end)s AND disposition = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_curr,
       SUM(CASE WHEN date BETWEEN %(prior_start)s AND %(prior_end)s THEN 1 ELSE 0 END) AS total_prior,
       SUM(CASE WHEN date BETWEEN %(prior_start)s AND %(prior_end)s AND disposition = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_prior
    FROM quality.clean_quality_data
    WHERE date BETWEEN %(prior_start)s AND %(curr_end)s
    GROUP BY part_number
    """
    params = {
        "curr_start": pd.to_datetime(curr_start),
        "curr_end": pd.to_datetime(curr_end),
        "prior_start": pd.to_datetime(prior_start),
        "prior_end": pd.to_datetime(prior_end),
    }
    try:
        df = pd.read_sql(query, con=engine_or_df, params=params)
    except Exception as e:
        # If engine_or_df was accidentally a DataFrame, callers will get a more helpful fallback above,
        # but if the DB call itself fails, surface the error
        raise RuntimeError(f"Unable to read aggregated part data from DB: {e}") from e

    if df.empty:
        return df
    df['total_curr'] = df['total_curr'].astype(int)
    df['scrap_curr'] = df['scrap_curr'].astype(int)
    df['total_prior'] = df['total_prior'].astype(int)
    df['scrap_prior'] = df['scrap_prior'].astype(int)
    df['rate_curr'] = df.apply(lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0.0, axis=1)
    df['rate_prior'] = df.apply(lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0.0, axis=1)
    return df

def load_agg_by_day(engine_or_df, start_date, end_date) -> pd.DataFrame:
    """
    Load daily aggregated counts for trend charts.
    Accepts a DB engine/connection or a pandas.DataFrame (raw).
    Returns DataFrame with date(normalized), defect_count, scrap_count, repaired_count
    """
    if _is_dataframe(engine_or_df):
        raw = engine_or_df.copy()
        if 'date' not in raw.columns:
            return pd.DataFrame()
        raw['date'] = pd.to_datetime(raw['date'], errors='coerce').dt.normalize()
        mask = (raw['date'] >= pd.to_datetime(start_date)) & (raw['date'] <= pd.to_datetime(end_date))
        raw = raw.loc[mask].dropna(subset=['date'])
        if raw.empty:
            return pd.DataFrame()
        daily = raw.groupby('date').agg(
            defect_count=('part_number', 'size'),
            scrap_count=('disposition', lambda s: (s == 'SCRAP').sum()),
            repaired_count=('disposition', lambda s: (s == 'REPAIRED').sum())
        ).reset_index().sort_values('date')
        return daily

    query = """
    SELECT date::date as date,
           COUNT(*) AS defect_count,
           SUM(CASE WHEN disposition = 'SCRAP' THEN 1 ELSE 0 END) AS scrap_count,
           SUM(CASE WHEN disposition = 'REPAIRED' THEN 1 ELSE 0 END) AS repaired_count
    FROM quality.clean_quality_data
    WHERE date BETWEEN %(start_date)s AND %(end_date)s
    GROUP BY date::date
    ORDER BY date::date
    """
    params = {"start_date": pd.to_datetime(start_date), "end_date": pd.to_datetime(end_date)}
    try:
        df = pd.read_sql(query, con=engine_or_df, params=params)
    except Exception as e:
        raise RuntimeError(f"Unable to read daily aggregates from DB: {e}") from e

    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date']).dt.normalize()
    df['defect_count'] = df['defect_count'].astype(int)
    df['scrap_count'] = df['scrap_count'].astype(int)
    df['repaired_count'] = df['repaired_count'].astype(int)
    return df

def load_part_records(engine_or_df, part_number: str, start_date: Optional[pd.Timestamp]=None, end_date: Optional[pd.Timestamp]=None, limit: Optional[int]=None) -> pd.DataFrame:
    """
    Fetch raw rows for a single part. Works with DB engine or in-memory DataFrame.
    """
    if _is_dataframe(engine_or_df):
        raw = engine_or_df.copy()
        if 'part_number' not in raw.columns:
            return pd.DataFrame()
        raw['date'] = pd.to_datetime(raw['date'], errors='coerce')
        mask = (raw['part_number'] == part_number)
        if start_date is not None and end_date is not None:
            mask = mask & (raw['date'] >= pd.to_datetime(start_date)) & (raw['date'] <= pd.to_datetime(end_date))
        res = raw.loc[mask].sort_values('date', ascending=False)
        if limit:
            res = res.head(limit)
        return res.reset_index(drop=True)

    base = "SELECT * FROM quality.clean_quality_data WHERE part_number = %(part)s"
    params = {"part": part_number}
    if start_date is not None and end_date is not None:
        base += " AND date BETWEEN %(start)s AND %(end)s"
        params["start"] = pd.to_datetime(start_date)
        params["end"] = pd.to_datetime(end_date)
    base += " ORDER BY date DESC"
    if limit:
        base += " LIMIT %(limit)s"
        params["limit"] = int(limit)
    try:
        df = pd.read_sql(base, con=engine_or_df, params=params)
    except Exception as e:
        raise RuntimeError(f"Unable to read part records from DB: {e}") from e
    return df