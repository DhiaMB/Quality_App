import streamlit as st
import pandas as pd
from web_app.utils.calculations import two_prop_z_test
from datetime import datetime, timedelta

def alerts_panel(engine, current_period=None, prior_period=None, rel_thresh=0.5, abs_thresh=0.05, alpha=0.05):
    """Display quality alerts based on scrap rate changes - DATABASE VERSION"""
    st.markdown("## ⚠️ Quality Alerts")
    st.markdown("### Automated Scrap Rate Alerts")
    
    # Determine date ranges - maintain compatibility with existing calls
    if current_period is None or prior_period is None:
        # Default to last 7 days vs previous 7 days
        current_end = datetime.now().date()
        current_start = current_end - timedelta(days=7)
        prior_end = current_start - timedelta(days=1)
        prior_start = prior_end - timedelta(days=7)
    else:
        # Extract dates from period objects if they exist
        # This maintains compatibility with your existing code
        current_start = getattr(current_period, 'start_date', datetime.now().date() - timedelta(days=7))
        current_end = getattr(current_period, 'end_date', datetime.now().date())
        prior_start = getattr(prior_period, 'start_date', current_start - timedelta(days=7))
        prior_end = getattr(prior_period, 'end_date', current_end - timedelta(days=7))
    
    st.info(f"**Current Period:** {current_start} to {current_end}")
    st.info(f"**Prior Period:** {prior_start} to {prior_end}")
    
    # Query for current period data
    current_period_query = """
    SELECT 
        part_number,
        COUNT(*) as total_curr,
        COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_curr
    FROM quality.clean_quality_data
    WHERE date BETWEEN %s AND %s
    GROUP BY part_number
    """
    
    # Query for prior period data
    prior_period_query = """
    SELECT 
        part_number,
        COUNT(*) as total_prior,
        COUNT(CASE WHEN disposition = 'Scrap' THEN 1 END) as scrap_prior
    FROM quality.clean_quality_data
    WHERE date BETWEEN %s AND %s
    GROUP BY part_number
    """
    
    try:
        # Get data from database
        current_data = pd.read_sql(current_period_query, engine, params=(current_start, current_end))
        prior_data = pd.read_sql(prior_period_query, engine, params=(prior_start, prior_end))
        
        # Merge data
        merged = current_data.merge(prior_data, on='part_number', how='left').fillna(0)
        
        if merged.empty:
            st.info("No data available for the selected periods")
            return
        
        # Compute rates and deltas
        merged['rate_curr'] = merged.apply(
            lambda r: (r['scrap_curr'] / r['total_curr']) if r['total_curr'] > 0 else 0, axis=1
        )
        merged['rate_prior'] = merged.apply(
            lambda r: (r['scrap_prior'] / r['total_prior']) if r['total_prior'] > 0 else 0, axis=1
        )
        merged['abs_delta'] = merged['rate_curr'] - merged['rate_prior']
        merged['rel_delta'] = merged.apply(
            lambda r: (r['rate_curr'] / r['rate_prior'] - 1) if r['rate_prior'] > 0 else float('inf') if r['rate_curr'] > 0 else 0, axis=1
        )

        alerts = []
        for _, row in merged.iterrows():
            # Only analyze parts with sufficient data
            if row['total_curr'] >= 10 and row['total_prior'] >= 10:
                # Significance test for proportions
                z, p = two_prop_z_test(
                    int(row['scrap_curr']), int(row['total_curr']), 
                    int(row['scrap_prior']), int(row['total_prior'])
                )
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
            
    except Exception as e:
        st.error(f"Error loading alert data from database: {e}")