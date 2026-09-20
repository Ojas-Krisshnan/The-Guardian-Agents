# api/student_routes.py
"""FastAPI endpoints for student attempts, private notes, and concept graphs."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import User, require_student
from api.dependencies import get_settings_dep, get_store
from slice.config import Settings
from slice.store import Store
from synapse.analytics.graph import build_student_graph
from synapse.api_contracts import (
    AssessmentQuestionResponse,
    AssessmentResponse,
    ClassroomResponse,
    StudentAnalyticsResponse,
    StudentAnswerDetail,
    StudentAttemptResponse,
    StudentAttemptSubmitRequest,
    StudentGraphResponse,
    StudentNotesResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
    TakeAssessmentResponse,
    ConnectedTeacherInfo,
    StudentConnectRequest,
    StudentConnectResponse,
    StudentTeacherListResponse,
)
from synapse.database import (
    get_assessment,
    get_assessment_attempt,
    get_assessment_questions,
    get_classroom,
    get_student_analytics_summary,
    is_student_in_classroom,
    list_classroom_assessments,
    list_student_attempts,
    list_student_classrooms,
    save_assessment_attempt,
)
from synapse.runtime.flow import advance, submit_attempt
from synapse.schemas import (
    AnalysisPayload,
    Attempt,
    CanonicalNote,
    ConceptNode,
    Diagnosis,
    GraphEdge,
    NoteVersion,
    RecordKind,
    ReviewResult,
    RunScope,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState

router = APIRouter(tags=["student"])


# ─── Classroom & Assessment Browsing ────────────────────────────────────────


@router.get("/student/classrooms", response_model=list[dict[str, Any]])
async def api_student_classrooms(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> list[dict[str, Any]]:
    """List classrooms the authenticated student is currently enrolled in."""
    return list_student_classrooms(store.db, student.id)


@router.get("/student/assessments", response_model=list[AssessmentResponse])
async def api_student_assessments(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> list[AssessmentResponse]:
    """List all published assessments for the student's enrolled classrooms."""
    classrooms = list_student_classrooms(store.db, student.id)
    all_assessments = []
    for c in classrooms:
        asms = list_classroom_assessments(store.db, c["id"], status_filter="published")
        all_assessments.extend(asms)
    return [AssessmentResponse(**a) for a in all_assessments]


@router.get("/student/assessments/{assessment_id}", response_model=TakeAssessmentResponse)
async def api_get_student_assessment(
    assessment_id: str,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> TakeAssessmentResponse:
    """Retrieve assessment and questions for taking the test (answers strictly omitted!)."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if asm["status"] != "published":
        raise HTTPException(status_code=403, detail="This assessment is not currently published")

    if not is_student_in_classroom(store.db, asm["classroom_id"], student.id):
        raise HTTPException(status_code=403, detail="You are not enrolled in the classroom for this assessment")

    # Correct answers are omitted for student test taking
    questions = get_assessment_questions(store.db, assessment_id, include_answers=False)
    return TakeAssessmentResponse(
        assessment=AssessmentResponse(**asm),
        questions=[AssessmentQuestionResponse(**q) for q in questions],
    )


@router.post("/student/assessments/{assessment_id}/attempt", response_model=StudentAttemptResponse)
async def api_submit_student_assessment_attempt(
    assessment_id: str,
    req: StudentAttemptSubmitRequest,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
) -> StudentAttemptResponse:
    """Submit assessment answers: grades server-side, triggers Synapse AI diagnosis & tailoring."""
    asm = get_assessment(store.db, assessment_id)
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if asm["status"] != "published":
        raise HTTPException(status_code=403, detail="Assessment is not published")

    if not is_student_in_classroom(store.db, asm["classroom_id"], student.id):
        raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

    questions = get_assessment_questions(store.db, assessment_id, include_answers=True)
    if not questions:
        raise HTTPException(status_code=400, detail="Assessment has no questions")

    # 1. Create agent run for this student attempt
    primary_concept = questions[0].get("concept_id") or "Recursion"
    scope = RunScope(
        concept_id=primary_concept,
        student_id=student.id,
        teacher_id=asm.get("created_by", ""),
        cycle=1,
    )
    run_id = store.create_run("synapse", scope.model_dump(mode="json"))

    # Convert questions into Synapse Test schema
    test_questions = []
    for q in questions:
        # Ensure 4 unique options for TestQuestion validation
        opts = list(q["options"])
        while len(opts) < 4:
            opts.append(f"Option {len(opts) + 1}")
        if len(opts) > 4:
            opts = opts[:4]
            if q["correct_answer"] not in opts:
                opts[0] = q["correct_answer"]

        test_questions.append(
            TestQuestion(
                id=q["id"],
                text=q["question_text"],
                options=opts,
                correct_answer=q["correct_answer"],
                concept_id=q.get("concept_id") or primary_concept,
            )
        )

    synapse_test = Test(
        id=assessment_id,
        concept_id=primary_concept,
        concept_name=primary_concept,
        questions=test_questions,
    )
    store.append(run_id, RecordKind.TEST, synapse_test.model_dump(mode="json"), produced_by="assessment_engine")

    # Also append canonical note so diagnosis/tailoring knows concept
    c_node = ConceptNode(id=primary_concept, name=primary_concept, summary=f"Core concepts of {primary_concept}")
    canonical = CanonicalNote(concept_id=primary_concept, markdown=f"# {primary_concept}\nOverview", extracted_concepts=[c_node])
    store.append(run_id, RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="assessment_engine")

    # 2. Score and save attempt in SQLite
    attempt_record = save_assessment_attempt(
        db=store.db,
        assessment_id=assessment_id,
        student_id=student.id,
        run_id=run_id,
        answers=req.answers,
    )

    # 3. Advance Synapse agent pipeline (Diagnosis -> Tailoring -> Review -> Analysis)
    submit_attempt(
        store=store,
        run_id=run_id,
        student_id=student.id,
        test_id=assessment_id,
        answers=req.answers,
        settings=settings,
    )

    # 4. Fetch outputs
    diag_data = store.latest(run_id, RecordKind.DIAGNOSIS)
    note_data = store.latest(run_id, RecordKind.NOTE_VERSION)

    diagnosis = Diagnosis.model_validate(diag_data) if diag_data else None
    note = NoteVersion.model_validate(note_data) if note_data else None

    if diagnosis:
        store.save_attempt_diagnosis(attempt_record["id"], diagnosis.model_dump(mode="json"))

    # Load complete attempt with answers
    full_att = get_assessment_attempt(store.db, attempt_record["id"])
    answer_details = [
        StudentAnswerDetail(
            question_id=a["question_id"],
            answer=a["answer"],
            is_correct=bool(a["is_correct"]),
            question_text=a["question_text"],
            options=a["options"],
            correct_answer=a["correct_answer"],
            concept_id=a.get("concept_id", ""),
        )
        for a in (full_att.get("answers") if full_att else [])
    ]

    return StudentAttemptResponse(
        id=attempt_record["id"],
        assessment_id=assessment_id,
        student_id=student.id,
        submitted_at=attempt_record["submitted_at"],
        score=attempt_record["score"],
        total=attempt_record["total"],
        percentage=attempt_record["percentage"],
        answers=answer_details,
        diagnosis=diagnosis,
        note=note,
    )


@router.get("/student/attempts", response_model=list[dict[str, Any]])
async def api_list_student_attempts(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> list[dict[str, Any]]:
    """List all completed attempts for this student."""
    return list_student_attempts(store.db, student.id)


@router.get("/student/attempts/{attempt_id}", response_model=dict[str, Any])
async def api_get_student_attempt(
    attempt_id: str,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """Get detailed results for an attempt (enforces student ownership)."""
    att = get_assessment_attempt(store.db, attempt_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if att["student_id"] != student.id:
        raise HTTPException(status_code=403, detail="Access forbidden: this attempt belongs to another student")
    return att


@router.get("/student/analytics", response_model=StudentAnalyticsResponse)
async def api_get_student_analytics(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentAnalyticsResponse:
    """Retrieve personalized mastery, progress history, and concept breakdown for this student."""
    summary = get_student_analytics_summary(store.db, student.id)
    return StudentAnalyticsResponse(**summary)


@router.get("/student/notes", response_model=StudentNotesResponse)
async def api_get_all_student_notes(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentNotesResponse:
    """Retrieve ALL private notes for THIS student only."""
    student_notes: list[NoteVersion] = []
    runs = store.list_runs(limit=200)
    for r in runs:
        history = store.history(r["id"], RecordKind.NOTE_VERSION)
        for v in history:
            p = v.payload
            if p.get("student_id") == student.id:
                student_notes.append(NoteVersion.model_validate(p))

    # Keep latest version per concept or return all sorted
    student_notes.sort(key=lambda n: n.version, reverse=True)
    return StudentNotesResponse(notes=student_notes)



@router.post("/student/attempts", response_model=SubmitAttemptResponse)
async def submit_student_attempt(
    req: SubmitAttemptRequest,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
) -> SubmitAttemptResponse:
    """Student submits a diagnostic test attempt; triggers diagnosis, tailoring, and review."""
    # Find run containing this test_id
    target_run_id = None
    runs = store.list_runs(limit=100)
    for r in runs:
        test_data = store.latest(r["id"], RecordKind.TEST)
        if test_data and test_data.get("id") == req.test_id:
            target_run_id = r["id"]
            break

    if not target_run_id:
        raise HTTPException(status_code=404, detail=f"No active test found matching test_id {req.test_id}")

    # Submit and advance
    submit_attempt(
        store=store,
        run_id=target_run_id,
        student_id=student.id,
        test_id=req.test_id,
        answers=req.answers,
        settings=settings,
    )

    attempt_data = store.latest(target_run_id, RecordKind.ATTEMPT)
    diag_data = store.latest(target_run_id, RecordKind.DIAGNOSIS)
    note_data = store.latest(target_run_id, RecordKind.NOTE_VERSION)
    rev_data = store.latest(target_run_id, RecordKind.REVIEW)
    analysis_data = store.latest(target_run_id, RecordKind.ANALYSIS)

    if not (attempt_data and diag_data and note_data and rev_data and analysis_data):
        raise HTTPException(status_code=500, detail="Run did not produce all expected output records")

    return SubmitAttemptResponse(
        run_id=target_run_id,
        attempt=Attempt.model_validate(attempt_data),
        diagnosis=Diagnosis.model_validate(diag_data),
        note=NoteVersion.model_validate(note_data),
        review=ReviewResult.model_validate(rev_data),
        analysis=AnalysisPayload.model_validate(analysis_data),
    )


@router.get("/student/notes/{concept_id}", response_model=StudentNotesResponse)
async def get_student_notes(
    concept_id: str,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentNotesResponse:
    """Retrieve private notes for THIS student only (Privacy: student A never sees student B's notes)."""
    student_notes: list[NoteVersion] = []
    runs = store.list_runs(limit=100)
    for r in runs:
        history = store.history(r["id"], RecordKind.NOTE_VERSION)
        for v in history:
            p = v.payload
            if p.get("student_id") == student.id and p.get("concept_id") == concept_id:
                student_notes.append(NoteVersion.model_validate(p))

    # Sort oldest to newest
    student_notes.sort(key=lambda n: n.version)
    return StudentNotesResponse(notes=student_notes)


@router.get("/student/graph", response_model=StudentGraphResponse)
async def get_student_graph(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentGraphResponse:
    """Retrieve interactive DAG concept graph for the calling student."""
    notes: list[NoteVersion] = []
    concepts: list[ConceptNode] = []

    runs = store.list_runs(limit=100)
    for r in runs:
        history_notes = store.history(r["id"], RecordKind.NOTE_VERSION)
        for v in history_notes:
            p = v.payload
            if p.get("student_id") == student.id:
                notes.append(NoteVersion.model_validate(p))

        c_data = store.latest(r["id"], RecordKind.CANONICAL_NOTE)
        if c_data and "extracted_concepts" in c_data:
            concepts.extend([ConceptNode.model_validate(c) for c in c_data["extracted_concepts"]])

    graph = build_student_graph(
        student_id=student.id,
        notes=notes,
        all_concepts=concepts,
    )

    return StudentGraphResponse(
        nodes=graph.nodes,
        edges=graph.edges,
    )


# ─── Student ↔ Teacher Connection Endpoints ───────────────────────────────────


@router.post("/student/connect", response_model=StudentConnectResponse)
async def api_connect_to_teacher(
    req: StudentConnectRequest,
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentConnectResponse:
    """Connect student to a teacher using teacher connection code."""
    try:
        res = store.connect_student_to_teacher(student.id, req.code)
        return StudentConnectResponse(
            success=res["success"],
            message=res["message"],
            teacher=ConnectedTeacherInfo(**res["teacher"]),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/student/teacher", response_model=StudentTeacherListResponse)
async def api_get_student_teachers(
    student: User = Depends(require_student),
    store: Store = Depends(get_store),
) -> StudentTeacherListResponse:
    """List teachers connected to the authenticated student."""
    teachers = store.get_student_connected_teachers(student.id)
    return StudentTeacherListResponse(teachers=[ConnectedTeacherInfo(**t) for t in teachers])

