import pandas as pd
from math import erf, sqrt

def normal_cdf(x: float) -> float:
    """Standard Normal CDF using error function"""
    return 0.5 * (1 + erf(x / sqrt(2)))

def two_prop_z_test(x1, n1, x2, n2):
    """Two-proportion z-test (two-sided). Returns z, p-value."""
    if n1 == 0 or n2 == 0:
        return None, None

    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)
    se = sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return None, None
        
    z = (p1 - p2) / se
    p_value = 2 * (1 - normal_cdf(abs(z)))
    return z, p_value

def summary_by_part(df):
    """Create part-level summary with defect counts and scrap rates"""
    if df.empty:
        return pd.DataFrame()

    # Pivot table for part dispositions
    pivot = df.pivot_table(
        index='part_number', 
        columns='disposition_norm', 
        values='id', 
        aggfunc='count', 
        fill_value=0
    ).reset_index()

    # Ensure all disposition columns exist
    for col in ['SCRAP', 'REPAIRED', 'OK']:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot['total_defects'] = pivot[['SCRAP', 'REPAIRED', 'OK']].sum(axis=1)
    pivot['scrap_rate'] = (pivot['SCRAP'] / pivot['total_defects']).fillna(0)

    # Top defect reasons per part
    reasons = (
        df.groupby(['part_number', 'code_description'])
        .size()
        .reset_index(name='count')
        .sort_values(['part_number', 'count'], ascending=[True, False])
    )
    
    top_reasons = (
        reasons.groupby('part_number')
        .apply(lambda g: '; '.join(
            g.head(3).apply(lambda r: f"{r['code_description']} ({r['count']})", axis=1)
        ))
        .reset_index(name='top_reasons')
    )

    summary = pivot.merge(top_reasons, how='left', on='part_number')
    summary['scrap_rate_percent'] = (summary['scrap_rate'] * 100).round(1)
    return summary.sort_values('total_defects', ascending=False)

def period_metrics(df, start_date, end_date):
    """Compute overall and per-part metrics for a period"""
    mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
    period_df = df.loc[mask]
    
    total = len(period_df)
    scrap = period_df[period_df['disposition_norm'] == 'SCRAP'].shape[0]
    repaired = period_df[period_df['disposition_norm'] == 'REPAIRED'].shape[0]

    per_part = (
        period_df.groupby('part_number')
        .agg(
            total_defects=('id', 'count'), 
            scrap_count=('disposition_norm', lambda s: (s == 'SCRAP').sum())
        )
        .reset_index()
    )
    
    return {
        'df': period_df,
        'total': total,
        'scrap': scrap,
        'repaired': repaired,
        'per_part': per_part
    }