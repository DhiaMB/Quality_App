import streamlit as st
import pandas as pd
from web_app.utils.calculations import two_prop_z_test

def alerts_panel(df, current_period, prior_period, rel_thresh=0.5, abs_thresh=0.05, alpha=0.05):
    """Display quality alerts based on scrap rate changes"""
    st.markdown("## ⚠️ Quality Alerts")
    st.markdown("### Automated Scrap Rate Alerts")
    
    # Merge per-part metrics
    curr = current_period['per_part'].rename(columns={'total_defects': 'total_curr', 'scrap_count': 'scrap_curr'})
    prior = prior_period['per_part'].rename(columns={'total_defects': 'total_prior', 'scrap_count': 'scrap_prior'})
    merged = curr.merge(prior, how='left', on='part_number').fillna(0)

    # Compute rates and deltas
    merged['rate_curr'] = merged.apply(lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0, axis=1)
    merged['rate_prior'] = merged.apply(lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0, axis=1)
    merged['abs_delta'] = merged['rate_curr'] - merged['rate_prior']
    merged['rel_delta'] = merged.apply(lambda r: (r['rate_curr'] / r['rate_prior'] - 1) if r['rate_prior'] > 0 else float('inf') if r['rate_curr']>0 else 0, axis=1)

    alerts = []
    for _, row in merged.iterrows():
        # Significance test for proportions
        z, p = two_prop_z_test(int(row['scrap_curr']), int(row['total_curr']), int(row['scrap_prior']), int(row['total_prior']))
        signif = (p is not None and p < alpha)
        triggered = (row['rel_delta'] >= rel_thresh) or (row['abs_delta'] >= abs_thresh)
        
        if triggered:
            alerts.append({
                'part_number': row['part_number'],
                'total_curr': int(row['total_curr']),
                'scrap_curr': int(row['scrap_curr']),
                'rate_curr_pct': round(row['rate_curr'] * 100, 2),
                'total_prior': int(row['total_prior']),
                'scrap_prior': int(row['scrap_prior']),
                'rate_prior_pct': round(row['rate_prior'] * 100, 2),
                'abs_delta_pp': round(row['abs_delta'] * 100, 2),
                'rel_delta_pct': round(row['rel_delta'] * 100 if row['rel_delta'] != float('inf') else 9999, 1),
                'z': round(z, 3) if z is not None else None,
                'p_value': round(p, 4) if p is not None else None,
                'significant': signif
            })

    alerts_df = pd.DataFrame(alerts).sort_values(['abs_delta_pp'], ascending=False)
    
    if alerts_df.empty:
        st.success("✅ No alerts triggered for the selected thresholds")
    else:
        st.info(f"Showing alerts where p < {alpha}, relative ≥ {rel_thresh*100}% or absolute ≥ {abs_thresh*100} pp.")
        st.dataframe(alerts_df, use_container_width=True)
        
        # Download button
        csv = alerts_df.to_csv(index=False)
        st.download_button('📥 Download Alerts CSV', csv, file_name='quality_alerts.csv')