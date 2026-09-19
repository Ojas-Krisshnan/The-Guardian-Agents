# synapse/schemas.py
# SOURCE OF TRUTH for Synapse domain data shapes. All teammates import from here.
# PROTECTED: PR required, all 5 approve, CI (including `sync_types.py --check`) must pass.
#
# Scope rules
#   * Domain records only. Infrastructure records (Version, Question [callback],
#     RunRecord, StepRecord) live in slice/records.py and are NOT redefined here.
#   * Data shapes + validators only. Algorithms live in the owning module
#     (e.g. graph traversal -> synapse/analytics/graph.py).
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS (architecture-level, not domain opinions)
# Single definition. state_machine.py and Settings import from here.
# ═══════════════════════════════════════════════════════════════════════════

MAX_REVISIONS_PER_CYCLE: int = 3
MAX_MODEL_CALL_RETRIES: int = 3
TAG_CONFIRMATION_TIMEOUT_SECONDS: int = 600  # overridable via SYNAPSE_TAG_TIMEOUT_SECONDS
MASTERY_WEAK_THRESHOLD: float = 0.5
DEFAULT_MASTERY_ESTIMATE: float = 0.5


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS   (RunState lives in synapse/state_machine.py)
# ═══════════════════════════════════════════════════════════════════════════

class MistakeClassification(str, Enum):
    CONCEPTUAL_GAP = "conceptual_gap"
    CARELESS_MISTAKE = "careless_mistake"
    CONTRADICTORY = "contradictory"
    UNRELATED = "unrelated"
    EMPTY = "empty"


class TrendLabel(str, Enum):
    NEW = "new"
    IMPROVING = "improving"
    STABLE = "stable"
    STILL_WEAK = "still_weak"
    DECLINING = "declining"


class ReviewStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    REVISION_LIMIT_REACHED = "revision_limit_reached"


class RecordKind(str, Enum):
    """`kind` argument of ctx.append(kind, payload). Server-side only (not exported to TS)."""
    CANONICAL_NOTE = "canonical_note"
    CONFIRMATION = "confirmation"
    TEST = "test"
    ATTEMPT = "attempt"
    DIAGNOSIS = "diagnosis"
    NOTE_CANDIDATE = "note_candidate"
    REVIEW = "review"
    NOTE_VERSION = "note_version"
    ANALYSIS = "analysis"
    CLASS_ANALYTICS = "class_analytics"
    CONCEPT_GRAPH = "concept_graph"


# ════════════════════════════════════════════════════════════════════════════
# CORE DOMAIN MODELS
# ════════════════════════════════════════════════════════════════════════════

class ConceptNode(BaseModel):
    id: str = Field(default_factory=new_uuid)
    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    prerequisites: list[str] = Field(default_factory=list)  # concept ids; mirrored by graph edges
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CanonicalNote(BaseModel):
    concept_id: str
    markdown: str = Field(min_length=1)
    extracted_concepts: list[ConceptNode] = Field(default_factory=list)
    teacher_confirmed: bool = False
    confirmed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class TestQuestion(BaseModel):
    """A multiple-choice test item. (Renamed from `Question` to avoid colliding with
    slice.records.Question, which is the human-in-the-loop callback question.)"""
    __test__ = False  # stop pytest trying to collect this class when a test module imports it

    id: str = Field(default_factory=new_uuid)
    text: str = Field(min_length=1, max_length=500)
    correct_answer: str = Field(min_length=1, max_length=200)
    options: list[str] = Field(min_length=4, max_length=4)
    concept_id: str

    @field_validator("options")
    @classmethod
    def unique_options(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("Options must be unique")
        return v

    @model_validator(mode="after")
    def answer_in_options(self) -> "TestQuestion":
        if self.correct_answer not in self.options:
            raise ValueError("correct_answer must be one of options")
        return self


class Test(BaseModel):
    __test__ = False  # stop pytest trying to collect this class when a test module imports it

    id: str = Field(default_factory=new_uuid)
    concept_id: str
    concept_name: str
    questions: list[TestQuestion] = Field(min_length=1)
    created_at: datetime = Field(default_factory=utcnow)


class Attempt(BaseModel):
    student_id: str = Field(min_length=1)
    test_id: str
    concept_id: str
    answers: dict[str, str] = Field(default_factory=dict)  # question_id -> answer
    score: int = Field(ge=0)
    total: int = Field(ge=1)
    submitted_at: datetime = Field(default_factory=utcnow)


class DiagnosisItem(BaseModel):
    question_id: str
    classification: MistakeClassification
    reason: str = Field(min_length=1, max_length=300)


class Diagnosis(BaseModel):
    id: str = Field(default_factory=new_uuid)  # referenced by NoteVersion.diagnosis_id
    student_id: str
    concept_id: str
    items: list[DiagnosisItem] = Field(default_factory=list)
    mastery_estimate: float = Field(ge=0.0, le=1.0)
    trend: TrendLabel
    created_at: datetime = Field(default_factory=utcnow)


class NoteVersion(BaseModel):
    """PRIVATE to the student. `markdown` must never appear in any teacher-facing response."""
    student_id: str
    concept_id: str
    version: int = Field(ge=1)  # monotonic per student + concept
    markdown: str = Field(min_length=1)
    diagnosis_id: Optional[str] = None
    review_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class ReviewResult(BaseModel):
    id: str = Field(default_factory=new_uuid)  # referenced by NoteVersion.review_id
    passed: bool
    canonical_coverage: bool
    diagnosis_addressed: bool
    links_valid: bool
    objections: list[str] = Field(default_factory=list)
    status: ReviewStatus
    created_at: datetime = Field(default_factory=utcnow)


class AnalysisPayload(BaseModel):
    student_id: str
    concept_id: str
    mastery_estimate: float = Field(ge=0.0, le=1.0)
    trend: TrendLabel
    cycle_number: int = Field(ge=1)
    created_at: datetime = Field(default_factory=utcnow)


class TeacherConfirmation(BaseModel):
    concept_id: str
    teacher_id: str
    confirmed: bool
    edited_concepts: Optional[list[ConceptNode]] = None
    confirmed_at: Optional[datetime] = None
    timed_out: bool = False


# ════════════════════════════════════════════════════════════════════════════
# CONCEPT GRAPH (data only; traversal lives in synapse/analytics/graph.py)
# ════════════════════════════════════════════════════════════════════════════

class GraphEdge(BaseModel):
    """Direction: `prerequisite` => from_concept must be learned BEFORE to_concept.
    `subconcept` => from_concept is the parent, to_concept the child.
    `related` is symmetric and stored once."""
    from_concept: str
    to_concept: str
    relationship: Literal["prerequisite", "related", "subconcept"]


class ConceptGraph(BaseModel):
    nodes: list[ConceptNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_integrity(self) -> "ConceptGraph":
        ids = {n.id for n in self.nodes}
        if len(ids) != len(self.nodes):
            raise ValueError("Duplicate node ids")
        for e in self.edges:
            if e.from_concept not in ids or e.to_concept not in ids:
                raise ValueError("Edge references an unknown concept id")
        prereq_edges = {(e.from_concept, e.to_concept) for e in self.edges if e.relationship == "prerequisite"}
        declared = {(p, n.id) for n in self.nodes for p in n.prerequisites}
        if prereq_edges != declared:
            raise ValueError("ConceptNode.prerequisites and prerequisite edges disagree")
        # Prerequisite edges must form a DAG (Kahn's algorithm)
        indegree = {i: 0 for i in ids}
        outgoing: dict[str, list[str]] = {i: [] for i in ids}
        for a, b in prereq_edges:
            outgoing[a].append(b)
            indegree[b] += 1
        ready = [i for i, d in indegree.items() if d == 0]
        visited = 0
        while ready:
            cur = ready.pop()
            visited += 1
            for nxt in outgoing[cur]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        if visited != len(ids):
            raise ValueError("Prerequisite cycle detected")
        return self


# ════════════════════════════════════════════════════════════════════════════
# AGGREGATE / HISTORY / RUN SCOPE
# ════════════════════════════════════════════════════════════════════════════

class StudentHistory(BaseModel):
    """INTERNAL (agents only). Contains private notes. Never used in an API model."""
    student_id: str
    concept_id: str
    previous_diagnoses: list[Diagnosis] = Field(default_factory=list)
    previous_notes: list[NoteVersion] = Field(default_factory=list)
    mastery_history: list[tuple[int, float]] = Field(default_factory=list)  # [(cycle, mastery)]
    existing_concept_names: set[str] = Field(default_factory=set)


class ClassAnalytics(BaseModel):
    concept_id: str
    concept_name: str
    student_count: int = Field(ge=0)
    average_mastery: float = Field(ge=0.0, le=1.0)
    trend_distribution: dict[TrendLabel, int] = Field(default_factory=dict)
    weak_students: list[str] = Field(default_factory=list)  # student_ids below MASTERY_WEAK_THRESHOLD
    updated_at: datetime = Field(default_factory=utcnow)


class RunScope(BaseModel):
    """Synapse-specific keys carried on slice RunRecord.scope (stored as model_dump(mode="json"))."""
    concept_id: str
    student_id: Optional[str] = None
    teacher_id: Optional[str] = None
    cycle: int = Field(default=1, ge=1)


# ════════════════════════════════════════════════════════════════════════════
# RECORD KIND -> PAYLOAD SCHEMA   (what ctx.append(kind, payload) must receive)
# ════════════════════════════════════════════════════════════════════════════

RECORD_PAYLOADS: dict[RecordKind, type[BaseModel]] = {
    RecordKind.CANONICAL_NOTE: CanonicalNote,
    RecordKind.CONFIRMATION: TeacherConfirmation,
    RecordKind.TEST: Test,
    RecordKind.ATTEMPT: Attempt,
    RecordKind.DIAGNOSIS: Diagnosis,
    RecordKind.NOTE_CANDIDATE: NoteVersion,
    RecordKind.REVIEW: ReviewResult,
    RecordKind.NOTE_VERSION: NoteVersion,
    RecordKind.ANALYSIS: AnalysisPayload,
    RecordKind.CLASS_ANALYTICS: ClassAnalytics,
    RecordKind.CONCEPT_GRAPH: ConceptGraph,
}
