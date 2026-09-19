"""
Student endpoints for Synapse API.
Authoritative contract: Contracts.md Sections C.4, D.4, D.9, F.3.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.auth import require_student
from synapse.api_contracts import (
    StudentGraphResponse,
    StudentNotesResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
)
from synapse.runtime.service import get_service
from synapse.schemas import (
    AnalysisPayload,
    Attempt,
    ConceptGraph,
    Diagnosis,
    NoteVersion,
    RecordKind,
    ReviewResult,
)

router = APIRouter(prefix="/student", tags=["student"])


@router.post("/attempts", response_model=SubmitAttemptResponse)
def submit_attempt_endpoint(
    req: SubmitAttemptRequest,
    user: dict[str, str] = Depends(require_student),
) -> SubmitAttemptResponse:
    service = get_service()
    student_id = user.get("user_id", "student_01")

    # Locate the active run associated with this test_id
    target_run_id = None
    for run in service.store.list_runs(limit=100):
        test_rec = service.store.latest(run["id"], RecordKind.TEST.value)
        if test_rec and test_rec.get("id") == req.test_id:
            target_run_id = run["id"]
            break

    if not target_run_id:
        # Check if test_id itself is a run_id
        try:
            if service.store.latest(req.test_id, RecordKind.TEST.value):
                target_run_id = req.test_id
        except Exception:
            pass

    if not target_run_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test {req.test_id} not found in any active run",
        )

    try:
        res = service.submit_attempt(
            run_id=target_run_id,
            student_id=student_id,
            test_id=req.test_id,
            answers=req.answers,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    # Assemble response
    attempt_dict = service.store.latest(target_run_id, RecordKind.ATTEMPT.value)
    diag_dict = service.store.latest(target_run_id, RecordKind.DIAGNOSIS.value)
    note_dict = service.store.latest(target_run_id, RecordKind.NOTE_VERSION.value) or service.store.latest(target_run_id, RecordKind.NOTE_CANDIDATE.value)
    review_dict = service.store.latest(target_run_id, RecordKind.REVIEW.value)
    analysis_dict = service.store.latest(target_run_id, RecordKind.ANALYSIS.value)

    if not (attempt_dict and diag_dict and note_dict and review_dict and analysis_dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline did not produce all expected diagnostic records",
        )

    return SubmitAttemptResponse(
        run_id=target_run_id,
        attempt=Attempt.model_validate(attempt_dict),
        diagnosis=Diagnosis.model_validate(diag_dict),
        note=NoteVersion.model_validate(note_dict),
        review=ReviewResult.model_validate(review_dict),
        analysis=AnalysisPayload.model_validate(analysis_dict),
    )


@router.get("/notes/{concept_id}", response_model=StudentNotesResponse)
def get_student_notes(
    concept_id: str = Path(...),
    user: dict[str, str] = Depends(require_student),
) -> StudentNotesResponse:
    service = get_service()
    student_id = user.get("user_id", "student_01")

    # Privacy rule: student may read ONLY own notes
    student_notes: list[NoteVersion] = []
    for run in service.store.list_runs(limit=100):
        history = service.store.history(run["id"], RecordKind.NOTE_VERSION.value)
        for r in history:
            payload = r.payload if hasattr(r, "payload") else r
            if (
                payload.get("student_id") == student_id
                and payload.get("concept_id") == concept_id
            ):
                student_notes.append(NoteVersion.model_validate(payload))

    return StudentNotesResponse(notes=student_notes)


@router.get("/graph", response_model=StudentGraphResponse)
def get_student_graph(
    user: dict[str, str] = Depends(require_student),
) -> StudentGraphResponse:
    service = get_service()
    graph_dict = None
    for run in service.store.list_runs(limit=100):
        g = service.store.latest(run["id"], RecordKind.CONCEPT_GRAPH.value)
        if g:
            graph_dict = g
            break

    if graph_dict:
        cg = ConceptGraph.model_validate(graph_dict)
        return StudentGraphResponse(nodes=cg.nodes, edges=cg.edges)

    return StudentGraphResponse(nodes=[], edges=[])
