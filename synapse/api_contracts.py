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
    Attempt,
    ClassAnalytics,
    ConceptNode,
    AnalysisPayload,
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


# ─── Auth Contracts ─────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    login_id: Optional[str] = None
    role: Optional[str] = None


class RegisterRequest(BaseModel):
    role: str = Field(default="teacher", pattern="^(teacher|student)$")
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    role: str
    name: str
    username: Optional[str] = None
    login_id: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


# ─── Classroom Contracts ───────────────────────────────────────────────────


class CreateClassroomRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=100)
    description: str = ""
    academic_year: str = ""


class ClassroomResponse(BaseModel):
    id: str
    teacher_id: str
    name: str
    subject: str
    description: str = ""
    academic_year: str = ""
    created_at: float
    student_count: int = 0
    assessment_count: int = 0
    average_mastery: float = 0.0


class GenerateStudentsRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=100)


class StudentCredentialResponse(BaseModel):
    student_id: str
    login_id: str
    name: str
    is_active: bool
    created_at: float


class GenerateStudentsResponse(BaseModel):
    classroom_id: str
    students: list[StudentCredentialResponse]


class ClassroomStudentItem(BaseModel):
    student_id: str
    name: str
    login_id: Optional[str] = None
    is_active: bool = False
    joined_at: float = 0.0


# ─── Assessment Contracts ───────────────────────────────────────────────────


class CreateAssessmentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = ""
    concept_ids: list[str] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    id: str
    classroom_id: str
    title: str
    description: str = ""
    concept_ids: list[str] = Field(default_factory=list)
    status: str = "draft"
    created_by: str
    created_at: float
    published_at: Optional[float] = None
    question_count: int = 0


class UploadQuestionItem(BaseModel):
    question_text: str = Field(min_length=1)
    options: list[str] = Field(min_length=2)
    correct_answer: str = Field(min_length=1)
    concept_id: str = ""
    explanation: str = ""
    question_type: str = "multiple_choice"


class UploadQuestionsRequest(BaseModel):
    questions: list[UploadQuestionItem]


class UploadAnswersRequest(BaseModel):
    answers: dict[str, str]  # question_id or 1-based index -> correct answer


class MapConceptsRequest(BaseModel):
    mappings: dict[str, str]  # question_id -> concept_id


class AssessmentQuestionResponse(BaseModel):
    id: str
    assessment_id: str
    concept_id: str = ""
    question_text: str
    question_type: str = "multiple_choice"
    options: list[str] = Field(default_factory=list)
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    order_num: int = 0


class TakeAssessmentResponse(BaseModel):
    assessment: AssessmentResponse
    questions: list[AssessmentQuestionResponse]


# ─── Document Extraction Contracts ──────────────────────────────────────────


class ExtractedQuestionItem(BaseModel):
    question_text: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str = ""
    concept_id: str = ""
    explanation: str = ""
    question_type: str = "multiple_choice"
    needs_review: bool = False
    warning: Optional[str] = None


class ExtractDocumentResponse(BaseModel):
    title: str = ""
    topic: str = ""
    questions: list[ExtractedQuestionItem]
    total_extracted: int
    warnings: list[str] = Field(default_factory=list)



# ─── Student Attempt Contracts ──────────────────────────────────────────────


class StudentAttemptSubmitRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class StudentAnswerDetail(BaseModel):
    question_id: str
    answer: str
    is_correct: bool
    question_text: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    concept_id: str = ""


class StudentAttemptResponse(BaseModel):
    id: str
    assessment_id: str
    student_id: str
    submitted_at: float
    score: int
    total: int
    percentage: float
    answers: list[StudentAnswerDetail] = Field(default_factory=list)
    diagnosis: Optional[Diagnosis] = None
    note: Optional[NoteVersion] = None


class AttemptHistoryItem(BaseModel):
    assessment_id: str
    title: str
    score: int
    total: int
    percentage: float
    submitted_at: float


class StudentAnalyticsResponse(BaseModel):
    student_id: str
    total_attempts: int
    overall_mastery: float
    history: list[AttemptHistoryItem] = Field(default_factory=list)
    concept_mastery: dict[str, float] = Field(default_factory=dict)


# ─── Teacher Analytics & Insights Contracts ─────────────────────────────────


class ConceptPerformanceItem(BaseModel):
    concept_id: str
    total_questions: int
    correct_answers: int
    mastery_percentage: float


class ClassroomAnalyticsResponse(BaseModel):
    classroom_id: str
    total_students: int
    total_attempts: int
    average_mastery: float
    distribution: dict[str, int] = Field(default_factory=dict)
    concept_performance: list[ConceptPerformanceItem] = Field(default_factory=list)


class TeacherInsightResponse(BaseModel):
    id: str
    classroom_id: str
    assessment_id: Optional[str] = None
    concept_id: str
    finding: str
    evidence: str
    recommendation: str
    generated_at: float


# ─── Student ↔ Teacher Connection & Performance Contracts ────────────────────


class TeacherConnectionCodeResponse(BaseModel):
    code: str
    teacher_id: str


class ConnectedStudentSummary(BaseModel):
    student_id: str
    name: str
    username: str
    email: Optional[str] = None
    login_id: Optional[str] = None
    joined_at: float
    total_attempts: int
    overall_mastery: Optional[float] = None
    recent_score: Optional[float] = None
    trend: str


class StudentAttemptSummaryItem(BaseModel):
    id: str
    assessment_id: str
    title: str
    score: int
    total: int
    percentage: float
    submitted_at: float


class DiagnosticSummaryItem(BaseModel):
    total_questions_answered: int
    correct_answers: int
    incorrect_answers: int
    accuracy_percentage: float


class DiagnosisItemSummary(BaseModel):
    question_id: str
    classification: str
    reason: str


class DiagnosisDetailResponse(BaseModel):
    id: str
    student_id: str
    concept_id: str
    items: list[DiagnosisItemSummary] = Field(default_factory=list)
    mastery_estimate: float = 0.0
    trend: str = "new"
    created_at: float = 0.0


class ConnectedStudentPerformanceResponse(BaseModel):
    student_id: str
    name: str
    username: str
    email: Optional[str] = None
    login_id: Optional[str] = None
    joined_at: float
    total_attempts: int
    overall_mastery: Optional[float] = None
    average_score: Optional[float] = None
    recent_score: Optional[float] = None
    trend: str
    recent_attempts: list[StudentAttemptSummaryItem] = Field(default_factory=list)
    concept_mastery: dict[str, float] = Field(default_factory=dict)
    concepts_studied: list[str] = Field(default_factory=list)
    concepts_needing_attention: list[str] = Field(default_factory=list)
    diagnostics_summary: DiagnosticSummaryItem
    latest_diagnosis: Optional[DiagnosisDetailResponse] = None


class StudentConnectRequest(BaseModel):
    code: str = Field(min_length=3, max_length=32)


class ConnectedTeacherInfo(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    username: Optional[str] = None


class StudentConnectResponse(BaseModel):
    success: bool
    message: str
    teacher: ConnectedTeacherInfo


class StudentTeacherListResponse(BaseModel):
    teachers: list[ConnectedTeacherInfo] = Field(default_factory=list)


