# synapse/api_contracts.py
# API REQUEST/RESPONSE MODELS — used by api/, web/ and (via types.ts) the frontend.
# PROTECTED: PR required, all 5 approve.
#
# Privacy rule (enforced by tests/test_integration.py::test_teacher_models_never_expose_notes):
# no model reachable from a Teacher-endpoint response may contain NoteVersion or StudentHistory.
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from synapse.schemas import (
    AnalysisPayload,
    Attempt,
    ClassAnalytics,
    ConceptNode,
    Diagnosis,
    GraphEdge,
    NoteVersion,
    ReviewResult,
    Test,
)
from synapse.state_machine import RunState

# ─── Teacher Endpoints ────────────────────────────────────────────────────


class CreateConceptRequest(BaseModel):
    markdown: str = Field(min_length=1, max_length=10000)
    concept_name: str = Field(min_length=1, max_length=100)


class CreateConceptResponse(BaseModel):
    concept: ConceptNode
    run_id: str


class PendingTagsResponse(BaseModel):
    """Extracted concepts awaiting teacher confirmation (run is parked in TAG_CONFIRMATION)."""
    run_id: str
    concept_id: str
    concepts: list[ConceptNode]
    expires_at: datetime


class ConfirmTagsRequest(BaseModel):
    run_id: str  # must equal the {run_id} path parameter, else 422
    confirmed: bool
    edited_concepts: Optional[list[ConceptNode]] = None


class ConfirmTagsResponse(BaseModel):
    run_id: str
    state: RunState
    test: Optional[Test] = None  # None while async test generation is still running


class TeacherAnalyticsResponse(BaseModel):
    concept_id: str
    concept_name: str
    analytics: ClassAnalytics


class TeacherTrendsResponse(BaseModel):
    concept_id: str
    trends: list[AnalysisPayload]


# ─── Student Endpoints ────────────────────────────────────────────────────


class SubmitAttemptRequest(BaseModel):
    test_id: str
    answers: dict[str, str] = Field(default_factory=dict)


class SubmitAttemptResponse(BaseModel):
    run_id: str
    attempt: Attempt
    diagnosis: Diagnosis
    note: NoteVersion
    review: ReviewResult
    analysis: AnalysisPayload


class StudentNotesResponse(BaseModel):
    notes: list[NoteVersion]


class StudentGraphResponse(BaseModel):
    nodes: list[ConceptNode]
    edges: list[GraphEdge]


# ─── Runtime / Shared ─────────────────────────────────────────────────────


class RunStatusResponse(BaseModel):
    run_id: str
    state: RunState
    current_cycle: int  # from RunScope.cycle
    revision_count: int  # derived: failed `review` records in this run + cycle
    model_call_count: int
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict = Field(default_factory=dict)
