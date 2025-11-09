        SELECT 
            DATE(date) AS period,
            COUNT(*) AS total_defects,
            COUNT(CASE WHEN UPPER(disposition) = 'SCRAP' THEN 1 END) AS scrap_count
        FROM quality.clean_quality_data
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(date)
        ORDER BY period ASC