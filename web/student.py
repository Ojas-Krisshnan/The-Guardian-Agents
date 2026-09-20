"""
Server-rendered web endpoints for student test submissions.
Authoritative contract: Contracts.md Sections D.6.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from synapse.runtime.service import get_service
from synapse.schemas import RecordKind, Test

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/web/student", tags=["web_student"])


@router.get("/attempts/{test_id}", response_class=HTMLResponse)
async def get_student_attempt_page(request: Request, test_id: str):
    service = get_service()

    target_run_id = None
    test_obj = None
    for run in service.store.list_runs(limit=100):
        t = service.store.latest(run["id"], RecordKind.TEST.value)
        if t and (t.get("id") == test_id or run["id"] == test_id):
            target_run_id = run["id"]
            test_obj = Test.model_validate(t)
            break

    if not test_obj:
        raise HTTPException(status_code=404, detail="Test not found")

    return templates.TemplateResponse(
        request=request,
        name="student_attempt.html",
        context={
            "test": test_obj,
            "run_id": target_run_id,
        },
    )


@router.post("/attempts/{test_id}")
async def post_student_attempt(request: Request, test_id: str):
    service = get_service()
    form_data = await request.form()
    run_id = form_data.get("run_id")

    if not run_id:
        for run in service.store.list_runs(limit=100):
            t = service.store.latest(run["id"], RecordKind.TEST.value)
            if t and (t.get("id") == test_id or run["id"] == test_id):
                run_id = run["id"]
                break

    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found for test")

    answers = {}
    for key, val in form_data.items():
        if key.startswith("q_"):
            qid = key[2:]
            answers[qid] = str(val)

    student_id = "web_student_01"
    try:
        resp = service.submit_attempt(
            run_id=str(run_id),
            student_id=student_id,
            test_id=test_id,
            answers=answers,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return JSONResponse(
        content={
            "status": "success",
            "message": "Assessment submitted and analyzed successfully.",
            "run_id": str(run_id),
            "diagnosis": resp.diagnosis,
            "score": resp.attempt.get("score") if resp.attempt else None,
            "total": resp.attempt.get("total") if resp.attempt else None,
        }
    )
