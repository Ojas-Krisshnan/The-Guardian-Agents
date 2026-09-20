"""
Teacher endpoints for Synapse API.
Authoritative contract: Contracts.md Sections C.4, D.5, D.9, F.3.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Path, status

from api.auth import require_teacher
from slice import callback
from synapse.api_contracts import (
    ConfirmTagsRequest,
    ConfirmTagsResponse,
    CreateConceptRequest,
    CreateConceptResponse,
    PendingTagsResponse,
    TeacherAnalyticsResponse,
    TeacherTrendsResponse,
)
from synapse.runtime.service import get_service
from synapse.schemas import (
    AnalysisPayload,
    ClassAnalytics,
    ConceptNode,
    RecordKind,
    Test,
)
from synapse.state_machine import RunState

router = APIRouter(prefix="/teacher", tags=["teacher"])


@router.post("/concepts", response_model=CreateConceptResponse)
def create_concept(
    req: CreateConceptRequest,
    user: dict[str, str] = Depends(require_teacher),
) -> CreateConceptResponse:
    service = get_service()
    teacher_id = user.get("user_id", "teacher_01")
    run_id = service.start_teacher_run(
        markdown=req.markdown,
        concept_name=req.concept_name,
        teacher_id=teacher_id,
    )

    scope = service.store.meta(run_id).get("scope", {})
    concept_id = scope.get("concept_id", "c_" + run_id)
    node = ConceptNode(
        id=concept_id,
        name=req.concept_name,
        summary=req.markdown[:300],
    )
    return CreateConceptResponse(concept=node, run_id=run_id)


@router.get("/concepts/{run_id}", response_model=PendingTagsResponse)
def get_pending_concepts(
    run_id: str = Path(...),
    user: dict[str, str] = Depends(require_teacher),
) -> PendingTagsResponse:
    service = get_service()
    try:
        current_state = service.store.get_state(run_id, state_type=RunState)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    open_qs = [q for q in service.store.open_questions(run_id) if not q.is_expired]
    scope = service.store.meta(run_id).get("scope", {})
    concept_id = scope.get("concept_id", "")

    concepts: list[ConceptNode] = []
    latest_note = service.store.latest(run_id, RecordKind.CANONICAL_NOTE.value)
    if latest_note:
        concepts = [
            ConceptNode.model_validate(c)
            for c in latest_note.get("extracted_concepts", [])
        ]

    expires_at = (
        datetime.fromtimestamp(open_qs[0].timeout_at, tz=timezone.utc)
        if open_qs and open_qs[0].timeout_at
        else datetime.now(timezone.utc) + timedelta(minutes=10)
    )

    return PendingTagsResponse(
        run_id=run_id,
        concept_id=concept_id,
        concepts=concepts,
        expires_at=expires_at,
    )


@router.post("/concepts/{run_id}/confirm", response_model=ConfirmTagsResponse)
def confirm_tags(
    req: ConfirmTagsRequest,
    run_id: str = Path(...),
    user: dict[str, str] = Depends(require_teacher),
) -> ConfirmTagsResponse:
    if req.run_id != run_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Path run_id does not match request body run_id",
        )

    service = get_service()
    try:
        current_state = service.store.get_state(run_id, state_type=RunState)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    if current_state != RunState.TAG_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run {run_id} is in state {current_state}, expected {RunState.TAG_CONFIRMATION}",
        )

    open_qs = [q for q in service.store.open_questions(run_id) if not q.is_expired]
    if not open_qs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Confirmation already submitted or question expired",
        )

    qid = open_qs[0].id
    answer_payload = {
        "confirmed": req.confirmed,
        "edited_concepts": [c.model_dump(mode="json") for c in (req.edited_concepts or [])],
    }
    callback.answer(
        service.store,
        qid,
        json.dumps(answer_payload),
        who=user.get("user_id", "teacher"),
    )

    new_state = service.advance(run_id)
    test_data = service.store.latest(run_id, RecordKind.TEST.value)
    test_obj = Test.model_validate(test_data) if test_data else None

    return ConfirmTagsResponse(
        run_id=run_id,
        state=new_state,
        test=test_obj,
    )


@router.get("/tests/{run_id}", response_model=Test)
def get_teacher_test(
    run_id: str = Path(...),
    user: dict[str, str] = Depends(require_teacher),
) -> Test:
    service = get_service()
    test_data = service.store.latest(run_id, RecordKind.TEST.value)
    if not test_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="test_not_ready",
        )
    return Test.model_validate(test_data)


@router.get("/analytics/{concept_id}", response_model=TeacherAnalyticsResponse)
def get_teacher_analytics(
    concept_id: str = Path(...),
    user: dict[str, str] = Depends(require_teacher),
) -> TeacherAnalyticsResponse:
    service = get_service()
    # Search latest class_analytics record
    analytics_record = None
    for run in service.store.list_runs(limit=100):
        ca = service.store.latest(run["id"], RecordKind.CLASS_ANALYTICS.value)
        if ca and ca.get("concept_id") == concept_id:
            analytics_record = ca
            break

    if analytics_record:
        analytics = ClassAnalytics.model_validate(analytics_record)
    else:
        analytics = ClassAnalytics(
            concept_id=concept_id,
            concept_name=concept_id.replace("_", " ").title(),
            student_count=0,
            average_mastery=0.0,
            trend_distribution={},
            weak_students=[],
        )

    return TeacherAnalyticsResponse(
        concept_id=concept_id,
        concept_name=analytics.concept_name,
        analytics=analytics,
    )


@router.get("/trends/{concept_id}", response_model=TeacherTrendsResponse)
def get_teacher_trends(
    concept_id: str = Path(...),
    user: dict[str, str] = Depends(require_teacher),
) -> TeacherTrendsResponse:
    service = get_service()
    trends: list[AnalysisPayload] = []
    for run in service.store.list_runs(limit=100):
        analysis = service.store.latest(run["id"], RecordKind.ANALYSIS.value)
        if analysis and analysis.get("concept_id") == concept_id:
            trends.append(AnalysisPayload.model_validate(analysis))

    return TeacherTrendsResponse(concept_id=concept_id, trends=trends)
