import streamlit as st
import pandas as pd
from web_app.utils.calculations import two_prop_z_test

def alerts_panel(agg_df, rel_thresh=0.5, abs_thresh=0.05, alpha=0.05):
    """
    Display actionable quality alerts based on pre-aggregated scrap rates (from DB).
    Expects agg_df columns: part_number, total_curr, scrap_curr, rate_curr, total_prior, scrap_prior, rate_prior
    """
    st.markdown("## ⚠️ Quality Alerts (Hybrid Aggregation)")
    if agg_df is None or agg_df.empty:
        st.info("No aggregated part-level data available. Contact admin if the DB view/table is missing.")
        return

    # Defensive column handling
    for col in ['rate_curr', 'rate_prior']:
        if col not in agg_df.columns:
            agg_df[col] = 0.0

    agg_df = agg_df.copy()
    agg_df['abs_delta'] = agg_df['rate_curr'] - agg_df['rate_prior']
    # safe relative delta: if prior==0 and curr>0 -> inf, if both 0 -> 0
    def rel_delta_row(r):
        if r['rate_prior'] == 0:
            return float('inf') if r['rate_curr'] > 0 else 0.0
        return (r['rate_curr'] / r['rate_prior']) - 1
    agg_df['rel_delta'] = agg_df.apply(rel_delta_row, axis=1)

    alerts = []
    for _, row in agg_df.iterrows():
        total_curr = int(row.get('total_curr', 0))
        total_prior = int(row.get('total_prior', 0))
        scrap_curr = int(row.get('scrap_curr', 0))
        scrap_prior = int(row.get('scrap_prior', 0))

        # only meaningful when both windows have enough observations
        if total_curr >= 10 and total_prior >= 10:
            z, p = two_prop_z_test(scrap_curr, total_curr, scrap_prior, total_prior)
            triggered = (row['rel_delta'] >= rel_thresh) or (row['abs_delta'] >= abs_thresh)
            signif = (p is not None and p < alpha)
            if triggered:
                alerts.append({
                    'part_number': row['part_number'],
                    'total_curr': total_curr,
                    'scrap_curr': scrap_curr,
                    'rate_curr_pct': round(row['rate_curr'] * 100, 2),
                    'total_prior': total_prior,
                    'scrap_prior': scrap_prior,
                    'rate_prior_pct': round(row['rate_prior'] * 100, 2),
                    'abs_delta_pp': round(row['abs_delta'] * 100, 2),
                    'rel_delta_pct': round(row['rel_delta'] * 100, 1) if row['rel_delta'] != float('inf') else 9999.0,
                    'z': round(z, 3) if z is not None else None,
                    'p_value': round(p, 4) if p is not None else None,
                    'significant': signif
                })

    alerts_df = pd.DataFrame(alerts)
    st.write("RAW ALERT DATA:", alerts)
    if alerts_df.empty:
        st.success("✅ No alerts triggered for the selected thresholds")
    else:
        st.info(f"Showing alerts where p < {alpha}, relative ≥ {rel_thresh*100}% or absolute ≥ {abs_thresh*100} pp.")
        alerts_df = alerts_df.sort_values('abs_delta_pp', ascending=False).reset_index(drop=True)
        st.dataframe(alerts_df, use_container_width=True)
        csv = alerts_df.to_csv(index=False)
        st.download_button('📥 Download Alerts CSV', csv, file_name='quality_alerts.csv')