# synapse/analytics/__init__.py
"""Analytics package: mastery scoring, trend calculation, class aggregation, and graph DAG algorithms."""
from synapse.analytics.aggregation import aggregate
from synapse.analytics.flow import handle_aggregating, handle_analysing
from synapse.analytics.graph import (
    build_student_graph,
    get_learning_path,
    get_prerequisites,
    parse_concept_links,
    topological_sort,
)
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend

__all__ = [
    "calculate_mastery",
    "calculate_trend",
    "aggregate",
    "parse_concept_links",
    "get_prerequisites",
    "get_learning_path",
    "topological_sort",
    "build_student_graph",
    "handle_analysing",
    "handle_aggregating",
]
