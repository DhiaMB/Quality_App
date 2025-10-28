from .kpi_dashboard import QualityApp
from .pareto_analysis import defect_pareto
from .alerts_panel import alerts_panel
from .trends_analysis import time_trends
from .part_analysis import part_leaderboard, part_detail_with_excel

__all__ = [
    'QualityApp', 'defect_pareto', 'alerts_panel', 
    'time_trends', 'part_leaderboard', 'part_detail_with_excel'
]