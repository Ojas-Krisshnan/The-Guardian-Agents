"""
Run lifecycle and status inspection endpoints.
Authoritative contract: Contracts.md Sections C.4, D.2.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path
from synapse.api_contracts import RunStatusResponse
from synapse.runtime.service import get_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}/status", response_model=RunStatusResponse)
def get_run_status(run_id: str = Path(...)) -> RunStatusResponse:
    service = get_service()
    try:
        status_res = service.get_run_status(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunStatusResponse(
        run_id=status_res.run_id,
        state=status_res.state,
        current_cycle=status_res.current_cycle,
        revision_count=status_res.revision_count,
        model_call_count=status_res.model_call_count,
        error=status_res.error,
    )
