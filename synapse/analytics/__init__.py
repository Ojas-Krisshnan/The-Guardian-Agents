"""
Person 4 Analytics domain: mastery, trends, aggregation, concept graph.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, F.4.
"""
from synapse.analytics.aggregation import aggregate
from synapse.analytics.flow import (
    handle_aggregating,
    handle_analysing,
)
from synapse.analytics.graph import (
    get_learning_path,
    get_prerequisites,
    parse_graph,
    topological_sort,
)
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.stub import (
    stub_aggregate,
    stub_calculate_mastery,
    stub_calculate_trend,
    stub_concept_graph,
)
from synapse.analytics.trends import calculate_trend

__all__ = [
    "calculate_mastery",
    "calculate_trend",
    "aggregate",
    "parse_graph",
    "get_prerequisites",
    "get_learning_path",
    "topological_sort",
    "handle_analysing",
    "handle_aggregating",
    "stub_calculate_mastery",
    "stub_calculate_trend",
    "stub_aggregate",
    "stub_concept_graph",
]
