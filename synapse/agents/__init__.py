"""
Person 2 Agents domain: diagnosis, tailoring, review.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, D.4.
"""
from synapse.agents.diagnosis import diagnose
from synapse.agents.flow import (
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
)
from synapse.agents.review import review
from synapse.agents.stub import (
    stub_diagnose,
    stub_review,
    stub_tailor,
)
from synapse.agents.tailoring import tailor

__all__ = [
    "diagnose",
    "tailor",
    "review",
    "handle_diagnosing",
    "handle_tailoring",
    "handle_reviewing",
    "stub_diagnose",
    "stub_tailor",
    "stub_review",
]
