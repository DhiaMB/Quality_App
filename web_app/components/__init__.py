# Lightweight package init for components with lazy imports to avoid circular import problems.
# Accessing attributes on the package (e.g., `from components import defect_pareto`)
# will import the underlying submodule on demand.

from importlib import import_module
from types import ModuleType
from typing import Any

__all__ = [
    "QualityApp",
    "defect_pareto",
    "alerts_panel",
    "time_trends",
    "part_leaderboard",
    "part_detail_with_excel",
]

# map exported name -> (module_path, attribute_name)
_lazy_map = {
    "QualityApp": ("web_app.components.kpi_dashboard", "QualityApp"),
    "defect_pareto": ("web_app.components.pareto_analysis", "defect_pareto"),
    "alerts_panel": ("web_app.components.alerts_panel", "alerts_panel"),
    "time_trends": ("web_app.components.trends_analysis", "time_trends"),
    "part_leaderboard": ("web_app.components.part_analysis", "part_leaderboard"),
    "part_detail_with_excel": ("web_app.components.part_analysis", "part_detail_with_excel"),
}


def __getattr__(name: str) -> Any:
    """Lazily import attributes from submodules to avoid circular imports."""
    if name in _lazy_map:
        module_path, attr = _lazy_map[name]
        try:
            module = import_module(module_path)
        except Exception as e:
            # Re-raise with a clearer message for debugging
            raise ImportError(f"Could not import module '{module_path}' for attribute '{name}': {e}") from e
        try:
            value = getattr(module, attr)
        except AttributeError as e:
            raise AttributeError(f"Module '{module_path}' has no attribute '{attr}' (needed for components.{name})") from e
        # cache on package module to avoid repeated imports
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    # make dir() and autocompletion friendly
    return sorted(list(globals().keys()) + list(_lazy_map.keys()))