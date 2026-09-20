# api/teacher_routes.py
"""FastAPI endpoints for teacher interactions and analytics."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.auth import User, require_teacher
from api.dependencies import get_settings_dep, get_store
from slice.config import Settings
from slice.store import Store
from synapse.api_contracts import (
    AssessmentQuestionResponse,
    AssessmentResponse,
    ClassroomAnalyticsResponse,
    ClassroomResponse,
    ClassroomStudentItem,
    ConfirmTagsRequest,
    ConfirmTagsResponse,
    CreateAssessmentRequest,
    CreateClassroomRequest,
    CreateConceptRequest,
    CreateConceptResponse,
    GenerateStudentsRequest,
    GenerateStudentsResponse,
    MapConceptsRequest,
    PendingTagsResponse,
    RunStatusResponse,
    StudentCredentialResponse,
    TeacherAnalyticsResponse,
    TeacherConnectionCodeResponse,
    TeacherInsightResponse,
    TeacherTrendsResponse,
    UploadAnswersRequest,
    UploadQuestionsRequest,
    ConnectedStudentPerformanceResponse,
    ConnectedStudentSummary,
)
from synapse.analytics.insights import generate_teacher_insights
from synapse.database import (
    create_assessment,
    create_classroom,
    generate_student_accounts,
    get_assessment,
    get_assessment_questions,
    get_classroom,
    get_classroom_analytics,
    list_classroom_assessments,
    list_classroom_students,
    list_teacher_classrooms,
    map_question_concepts,
    save_assessment_questions,
    update_assessment_status,
)
from synapse.runtime.flow import advance, get_run_status, start_teacher_run
from synapse.schemas import (
    AnalysisPayload,
    CanonicalNote,
    ClassAnalytics,
    ConceptNode,
    RecordKind,
    Test,
    TrendLabel,
    utcnow,
)
from synapse.state_machine import RunState

router = APIRouter(tags=["teacher"])


# ─── Classroom Management ───────────────────────────────────────────────────


@router.post("/teacher/classrooms", response_model=ClassroomResponse)
async def api_create_classroom(
    req: CreateClassroomRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> ClassroomResponse:
    """Create a new classroom owned by the authenticated teacher."""
    data = create_classroom(
        db=store.db,
        teacher_id=teacher.id,
        name=req.name,
        subject=req.subject,
        description=req.description,
        academic_year=req.academic_year,
    )
    return ClassroomResponse(**data)


@router.get("/teacher/classrooms", response_model=list[ClassroomResponse])
async def api_list_classrooms(
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[ClassroomResponse]:
    """List all classrooms belonging to the authenticated teacher."""
    classrooms = list_teacher_classrooms(store.db, teacher.id)
    return [ClassroomResponse(**c) for c in classrooms]


@router.get("/teacher/classrooms/{classroom_id}", response_model=ClassroomResponse)
async def api_get_classroom(
    classroom_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> ClassroomResponse:
    """Retrieve details for a specific classroom, ensuring teacher ownership."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden: you do not own this classroom")
    return ClassroomResponse(**c)


@router.post("/teacher/classrooms/{classroom_id}/students/generate", response_model=GenerateStudentsResponse)
async def api_generate_students(
    classroom_id: str,
    req: GenerateStudentsRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> GenerateStudentsResponse:
    """Generate cryptographically unique student IDs and accounts for the classroom."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden: you do not own this classroom")

    students = generate_student_accounts(store.db, classroom_id, req.count)
    return GenerateStudentsResponse(
        classroom_id=classroom_id,
        students=[StudentCredentialResponse(**s) for s in students],
    )


@router.get("/teacher/classrooms/{classroom_id}/students", response_model=list[ClassroomStudentItem])
async def api_list_classroom_students(
    classroom_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[ClassroomStudentItem]:
    """List all students enrolled in a classroom with login ID and activation status."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden: you do not own this classroom")

    students = list_classroom_students(store.db, classroom_id)
    return [ClassroomStudentItem(**s) for s in students]


# ─── Assessment Management ──────────────────────────────────────────────────


@router.post("/teacher/classrooms/{classroom_id}/assessments", response_model=AssessmentResponse)
async def api_create_assessment(
    classroom_id: str,
    req: CreateAssessmentRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> AssessmentResponse:
    """Create a new assessment draft inside a classroom."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden: you do not own this classroom")

    asm = create_assessment(
        db=store.db,
        classroom_id=classroom_id,
        teacher_id=teacher.id,
        title=req.title,
        description=req.description,
        concept_ids=req.concept_ids,
    )
    return AssessmentResponse(**asm)


@router.get("/teacher/classrooms/{classroom_id}/assessments", response_model=list[AssessmentResponse])
async def api_list_classroom_assessments(
    classroom_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[AssessmentResponse]:
    """List all assessments for a classroom."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden: you do not own this classroom")

    assessments = list_classroom_assessments(store.db, classroom_id)
    return [AssessmentResponse(**a) for a in assessments]


@router.get("/teacher/assessments/{assessment_id}", response_model=dict[str, Any])
async def api_get_assessment(
    assessment_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """Get assessment metadata and full question set with answer key."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    c = get_classroom(store.db, asm["classroom_id"])
    if c and c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    questions = get_assessment_questions(store.db, assessment_id, include_answers=True)
    return {
        "assessment": AssessmentResponse(**asm),
        "questions": [AssessmentQuestionResponse(**q) for q in questions],
    }


@router.post("/teacher/assessments/{assessment_id}/questions/upload", response_model=list[AssessmentQuestionResponse])
async def api_upload_questions(
    assessment_id: str,
    req: UploadQuestionsRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[AssessmentQuestionResponse]:
    """Upload and validate question set for an assessment."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    c = get_classroom(store.db, asm["classroom_id"])
    if c and c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    # Validate questions
    if not req.questions:
        raise HTTPException(status_code=422, detail="Question set cannot be empty")

    q_dicts = []
    seen_texts = set()
    for i, q in enumerate(req.questions):
        txt = q.question_text.strip()
        if not txt:
            raise HTTPException(status_code=422, detail=f"Question {i+1} has empty text")
        if txt in seen_texts:
            raise HTTPException(status_code=422, detail=f"Duplicate question detected: '{txt}'")
        seen_texts.add(txt)

        if len(q.options) < 2:
            raise HTTPException(status_code=422, detail=f"Question {i+1} must have at least 2 options")
        if len(set(q.options)) != len(q.options):
            raise HTTPException(status_code=422, detail=f"Question {i+1} options must be unique")
        if q.correct_answer not in q.options:
            raise HTTPException(
                status_code=422,
                detail=f"Question {i+1} correct_answer '{q.correct_answer}' is not in options {q.options}",
            )

        q_dicts.append(q.model_dump())

    saved = save_assessment_questions(store.db, assessment_id, q_dicts)
    return [AssessmentQuestionResponse(**s) for s in saved]


@router.post("/teacher/assessments/{assessment_id}/answers/upload", response_model=list[AssessmentQuestionResponse])
async def api_upload_answers(
    assessment_id: str,
    req: UploadAnswersRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[AssessmentQuestionResponse]:
    """Upload or update answer key for existing questions in an assessment."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    c = get_classroom(store.db, asm["classroom_id"])
    if c and c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    questions = get_assessment_questions(store.db, assessment_id, include_answers=True)
    if not questions:
        raise HTTPException(status_code=400, detail="Cannot upload answer key before questions are created")

    # Support matching by question ID or by 1-based index (e.g. "Q1", "1")
    q_map = {q["id"]: q for q in questions}
    idx_map = {str(i + 1): q for i, q in enumerate(questions)}
    q_prefix_map = {f"Q{i + 1}": q for i, q in enumerate(questions)}

    updated_count = 0
    for key, ans in req.answers.items():
        q = q_map.get(key) or idx_map.get(str(key)) or q_prefix_map.get(str(key).upper())
        if not q:
            raise HTTPException(status_code=422, detail=f"Answer key references unknown question '{key}'")
        if ans not in q["options"]:
            raise HTTPException(
                status_code=422,
                detail=f"Answer '{ans}' for question {q['order_num']} is not one of valid options: {q['options']}",
            )
        store.db.execute(
            "UPDATE assessment_questions SET correct_answer = ? WHERE id = ?",
            (ans, q["id"]),
        )
        q["correct_answer"] = ans
        updated_count += 1

    return [AssessmentQuestionResponse(**q) for q in questions]


@router.post("/teacher/assessments/{assessment_id}/map-concepts", response_model=list[AssessmentQuestionResponse])
async def api_map_concepts(
    assessment_id: str,
    req: MapConceptsRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[AssessmentQuestionResponse]:
    """Map questions to concept nodes."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    c = get_classroom(store.db, asm["classroom_id"])
    if c and c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    map_question_concepts(store.db, assessment_id, req.mappings)
    questions = get_assessment_questions(store.db, assessment_id, include_answers=True)
    return [AssessmentQuestionResponse(**q) for q in questions]


@router.post("/teacher/assessments/{assessment_id}/publish", response_model=AssessmentResponse)
async def api_publish_assessment(
    assessment_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> AssessmentResponse:
    """Publish an assessment so students in the classroom can take it."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    c = get_classroom(store.db, asm["classroom_id"])
    if c and c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    questions = get_assessment_questions(store.db, assessment_id, include_answers=True)
    if not questions:
        raise HTTPException(status_code=400, detail="Cannot publish an assessment with zero questions")

    # Ensure all questions have a valid correct answer
    for q in questions:
        if not q.get("correct_answer") or q["correct_answer"] not in q["options"]:
            raise HTTPException(
                status_code=400,
                detail=f"Question {q['order_num']} ('{q['question_text'][:30]}...') lacks a valid correct answer",
            )

    update_assessment_status(store.db, assessment_id, "published")
    updated = get_assessment(store.db, assessment_id)
    return AssessmentResponse(**updated)


# ─── Classroom Analytics & AI Insights ──────────────────────────────────────


@router.get("/teacher/classrooms/{classroom_id}/analytics", response_model=ClassroomAnalyticsResponse)
async def api_get_classroom_analytics(
    classroom_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> ClassroomAnalyticsResponse:
    """Aggregated class analytics (Privacy: NEVER contains individual student notes)."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    analytics_data = get_classroom_analytics(store.db, classroom_id)
    return ClassroomAnalyticsResponse(**analytics_data)


@router.get("/teacher/classrooms/{classroom_id}/insights", response_model=list[TeacherInsightResponse])
async def api_get_classroom_insights(
    classroom_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
) -> list[TeacherInsightResponse]:
    """Data-grounded AI teaching insights and pedagogical recommendations."""
    c = get_classroom(store.db, classroom_id)
    if not c:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if c["teacher_id"] != teacher.id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    insights = generate_teacher_insights(store, classroom_id, settings=settings)
    return insights



@router.post("/teacher/concepts", response_model=CreateConceptResponse)
async def create_concept(
    req: CreateConceptRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
) -> CreateConceptResponse:
    """Teacher creates a concept from canonical notes; triggers concept extraction."""
    run_id = start_teacher_run(
        store=store,
        markdown=req.markdown,
        concept_name=req.concept_name,
        teacher_id=teacher.id,
        settings=settings,
    )

    note_data = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    concept = None
    if note_data:
        canonical = CanonicalNote.model_validate(note_data)
        if canonical.extracted_concepts:
            concept = canonical.extracted_concepts[0]

    if not concept:
        concept = ConceptNode(name=req.concept_name, summary=f"Overview of {req.concept_name}")

    return CreateConceptResponse(concept=concept, run_id=run_id)


@router.get("/teacher/concepts/{run_id}", response_model=PendingTagsResponse)
async def get_pending_tags(
    run_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> PendingTagsResponse:
    """Retrieve pending concepts for confirmation while run is parked in tag_confirmation."""
    note_data = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    if not note_data:
        raise HTTPException(status_code=404, detail="Run or canonical note not found")

    canonical = CanonicalNote.model_validate(note_data)
    concept_id = canonical.concept_id

    # Find deadline if open question exists
    open_qs = store.open_questions(run_id)
    if open_qs:
        expires_at = datetime.fromtimestamp(open_qs[0].timeout_at, tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    return PendingTagsResponse(
        run_id=run_id,
        concept_id=concept_id,
        concepts=canonical.extracted_concepts,
        expires_at=expires_at,
    )


@router.post("/teacher/concepts/{run_id}/confirm", response_model=ConfirmTagsResponse)
async def confirm_tags(
    run_id: str,
    req: ConfirmTagsRequest,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
) -> ConfirmTagsResponse:
    """Teacher confirms or edits extracted concept tags, resuming the pipeline."""
    if req.run_id != run_id:
        raise HTTPException(status_code=422, detail="Path run_id does not match request body run_id")

    # Check if run is in tag confirmation
    state = store.get_state(run_id)
    if state.value != RunState.TAG_CONFIRMATION.value:
        raise HTTPException(status_code=409, detail=f"Run is not in tag_confirmation state (current: {state})")

    open_qs = store.open_questions(run_id)
    if not open_qs:
        raise HTTPException(status_code=409, detail="No pending tag confirmation question for this run (already answered)")

    qid = open_qs[0].id
    answer_payload = {
        "confirmed": req.confirmed,
        "edited_concepts": [c.model_dump(mode="json") for c in req.edited_concepts] if req.edited_concepts else None,
        "timed_out": False,
    }
    store.answer(qid, json.dumps(answer_payload))

    # Advance through test generation
    end_state = advance(store, run_id, settings)

    test_data = store.latest(run_id, RecordKind.TEST)
    test = Test.model_validate(test_data) if test_data else None

    return ConfirmTagsResponse(
        run_id=run_id,
        state=end_state,
        test=test,
    )


@router.get("/teacher/tests/{run_id}", response_model=Test)
async def get_test(
    run_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> Test:
    """Retrieve generated diagnostic test once test_ready has completed."""
    test_data = store.latest(run_id, RecordKind.TEST)
    if not test_data:
        raise HTTPException(
            status_code=404,
            detail={"error": "test_not_ready", "message": "Diagnostic test generation is still in progress"},
        )
    return Test.model_validate(test_data)


@router.get("/teacher/analytics/{concept_id}", response_model=TeacherAnalyticsResponse)
async def get_teacher_analytics(
    concept_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> TeacherAnalyticsResponse:
    """Retrieve class-level aggregated analytics for a concept (Privacy: NEVER includes private notes)."""
    # Look for class_analytics across runs
    found_analytics = None
    runs = store.list_runs(limit=100)
    for r in runs:
        c_data = store.latest(r["id"], RecordKind.CLASS_ANALYTICS)
        if c_data and c_data.get("concept_id") == concept_id:
            found_analytics = ClassAnalytics.model_validate(c_data)
            break

    if not found_analytics:
        # Fallback default empty analytics
        found_analytics = ClassAnalytics(
            concept_id=concept_id,
            concept_name="Recursion",
            student_count=0,
            average_mastery=0.0,
            trend_distribution={},
            weak_students=[],
        )

    return TeacherAnalyticsResponse(
        concept_id=concept_id,
        concept_name=found_analytics.concept_name,
        analytics=found_analytics,
    )


@router.get("/teacher/trends/{concept_id}", response_model=TeacherTrendsResponse)
async def get_teacher_trends(
    concept_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> TeacherTrendsResponse:
    """Retrieve historical analysis payloads across cycles for class trends."""
    trends: list[AnalysisPayload] = []
    runs = store.list_runs(limit=100)
    for r in runs:
        history = store.history(r["id"], RecordKind.ANALYSIS)
        for v in history:
            p = v.payload
            if p.get("concept_id") == concept_id:
                trends.append(AnalysisPayload.model_validate(p))

    return TeacherTrendsResponse(concept_id=concept_id, trends=trends)


@router.get("/runs/{run_id}/status", response_model=RunStatusResponse)
async def get_status(
    run_id: str,
    user: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> RunStatusResponse:
    """Retrieve live status, current cycle, and revision count for a run."""
    return get_run_status(store, run_id)


# ─── Student ↔ Teacher Connection & Analytics Endpoints ───────────────────────


@router.get("/teacher/connection-code", response_model=TeacherConnectionCodeResponse)
async def api_get_teacher_connection_code(
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> TeacherConnectionCodeResponse:
    """Get or generate the persistent connection code for the authenticated teacher."""
    code = store.get_or_create_teacher_code(teacher.id)
    return TeacherConnectionCodeResponse(code=code, teacher_id=teacher.id)


@router.get("/teacher/students", response_model=list[ConnectedStudentSummary])
async def api_list_connected_students(
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> list[ConnectedStudentSummary]:
    """List all students connected to the authenticated teacher with live performance summaries."""
    students = store.list_teacher_connected_students(teacher.id)
    return [ConnectedStudentSummary(**s) for s in students]


@router.get("/teacher/students/{student_id}/performance", response_model=ConnectedStudentPerformanceResponse)
async def api_get_connected_student_performance(
    student_id: str,
    teacher: User = Depends(require_teacher),
    store: Store = Depends(get_store),
) -> ConnectedStudentPerformanceResponse:
    """Authoritatively retrieve a connected student's performance.
    
    Returns 403 Forbidden if the student does not belong or is not connected to this teacher.
    """
    perf = store.get_connected_student_performance(teacher.id, student_id)
    if perf is None:
        u = store.get_user_by_id(student_id)
        if not u:
            raise HTTPException(status_code=404, detail="Student not found")
        raise HTTPException(status_code=403, detail="Access forbidden: student is not connected to your account")
    return ConnectedStudentPerformanceResponse(**perf)

