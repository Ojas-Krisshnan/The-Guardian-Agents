"""Runs router implementation with role-based API protection."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.auth import get_current_user, require_teacher
from api.deps import get_settings, get_store
from api.mocks import get_mock_flow
from api.models import CreateRunRequest, QuestionResponse, RunResponse, VersionResponse
from slice import callback
from slice.config import Settings
from slice.runner import advance
from slice.store import Store

router = APIRouter(prefix="/runs", tags=["runs"])


def _find_run_dict(store: Store, run_id: str) -> dict[str, Any]:
    """Helper to fetch full run metadata via Store API."""
    try:
        state = store.get_state(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    meta = store.meta(run_id)
    for r in store.list_runs(limit=1000):
        if r["id"] == run_id:
            return {
                "id": r["id"],
                "domain": r["domain"],
                "state": state.value,
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "meta": meta,
            }

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=RunResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_run(
    req: CreateRunRequest,
    store: Store = Depends(get_store),
    user: dict = Depends(require_teacher),
) -> RunResponse:
    """Create a new run using Store.create_run (Teacher only)."""
    run_id = store.create_run(domain=req.domain, meta=req.meta)
    run_dict = _find_run_dict(store, run_id)
    return RunResponse(**run_dict)


@router.get("", response_model=list[RunResponse])
@router.get("/", response_model=list[RunResponse], include_in_schema=False)
def list_runs(
    limit: int = Query(default=50, ge=1, le=500),
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> list[RunResponse]:
    """List existing runs using Store.list_runs (Authenticated)."""
    raw_runs = store.list_runs(limit=limit)
    result = []
    for r in raw_runs:
        meta = store.meta(r["id"])
        result.append(
            RunResponse(
                id=r["id"],
                domain=r["domain"],
                state=r["state"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
                meta=meta,
            )
        )
    return result


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: str,
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> RunResponse:
    """Get run state and details by run_id (Authenticated)."""
    run_dict = _find_run_dict(store, run_id)
    return RunResponse(**run_dict)


@router.post("/{run_id}/advance", response_model=RunResponse)
def advance_run(
    run_id: str,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings),
    user: dict = Depends(get_current_user),
) -> RunResponse:
    """Advance run state deterministically using slice.runner.advance (Authenticated)."""
    try:
        _ = store.get_state(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    if store.latest(run_id, "input") is None:
        meta = store.meta(run_id)
        input_text = meta.get("input") or meta.get("text") or "Students struggle to get internships and it is a real problem"
        store.append(run_id, "input", {"text": input_text}, produced_by="user")

    flow = get_mock_flow()
    _ = advance(store, run_id, flow, settings)

    run_dict = _find_run_dict(store, run_id)
    return RunResponse(**run_dict)


@router.get("/{run_id}/questions", response_model=list[QuestionResponse])
def get_run_questions(
    run_id: str,
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> list[QuestionResponse]:
    """Get pending/open questions for a run (Authenticated)."""
    try:
        _ = store.get_state(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    questions = callback.pending(store, run_id)
    return [
        QuestionResponse(
            id=q.id,
            run_id=q.run_id,
            question=q.question,
            context=q.context,
            asked_at=q.asked_at,
            timeout_at=q.timeout_at,
            answered_at=q.answered_at,
            answer=q.answer,
            is_answered=q.is_answered,
            is_expired=q.is_expired,
        )
        for q in questions
    ]


@router.get("/{run_id}/history", response_model=list[VersionResponse])
def get_run_history(
    run_id: str,
    kind: str = Query(..., description="Kind of version records to retrieve"),
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> list[VersionResponse]:
    """Get version history for a run by kind (Authenticated)."""
    try:
        _ = store.get_state(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    versions = store.history(run_id, kind)
    return [
        VersionResponse(
            seq=v.seq,
            kind=v.kind,
            produced_by=v.produced_by,
            payload=v.payload,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{run_id}/replay", response_model=list[VersionResponse])
def replay_run(
    run_id: str,
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> list[VersionResponse]:
    """Get full replay version history for a run (Authenticated)."""
    try:
        _ = store.get_state(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    versions = store.replay(run_id)
    return [
        VersionResponse(
            seq=v.seq,
            kind=v.kind,
            produced_by=v.produced_by,
            payload=v.payload,
            created_at=v.created_at,
        )
        for v in versions
    ]
