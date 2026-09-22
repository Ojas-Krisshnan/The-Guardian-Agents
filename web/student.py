# web/student.py
"""Server-rendered callback UI for student attempts (no-JS fallback)."""
from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.dependencies import get_settings_dep, get_store
from slice.config import Settings
from slice.store import Store
from synapse.runtime.flow import submit_attempt
from synapse.schemas import Attempt, Diagnosis, NoteVersion, RecordKind, Test

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter(tags=["web-student"])


@router.get("/web/student/attempts/{test_id}", response_class=HTMLResponse)
async def get_student_attempt_form(
    test_id: str,
    request: Request,
    store: Store = Depends(get_store),
):
    runs = store.list_runs(limit=100)
    target_test = None
    for r in runs:
        t_data = store.latest(r["id"], RecordKind.TEST)
        if t_data and t_data.get("id") == test_id:
            target_test = Test.model_validate(t_data)
            break

    if not target_test:
        raise HTTPException(status_code=404, detail="Test not found")

    return templates.TemplateResponse(
        "student_attempt.html",
        {"request": request, "test": target_test},
    )


@router.post("/web/student/attempts/{test_id}", response_class=HTMLResponse)
async def post_student_attempt(
    test_id: str,
    request: Request,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
):
    form_data = await request.form()
    student_id = str(form_data.get("student_id", "student_1"))

    target_run_id = None
    target_test = None
    runs = store.list_runs(limit=100)
    for r in runs:
        t_data = store.latest(r["id"], RecordKind.TEST)
        if t_data and t_data.get("id") == test_id:
            target_run_id = r["id"]
            target_test = Test.model_validate(t_data)
            break

    if not target_run_id or not target_test:
        raise HTTPException(status_code=404, detail="Test not found")

    answers = {}
    for q in target_test.questions:
        if q.id in form_data:
            answers[q.id] = str(form_data[q.id])

    submit_attempt(
        store=store,
        run_id=target_run_id,
        student_id=student_id,
        test_id=test_id,
        answers=answers,
        settings=settings,
    )

    attempt_data = store.latest(target_run_id, RecordKind.ATTEMPT)
    diag_data = store.latest(target_run_id, RecordKind.DIAGNOSIS)
    note_data = store.latest(target_run_id, RecordKind.NOTE_VERSION)

    return templates.TemplateResponse(
        "student_result.html",
        {
            "request": request,
            "attempt": Attempt.model_validate(attempt_data),
            "diagnosis": Diagnosis.model_validate(diag_data),
            "note": NoteVersion.model_validate(note_data),
        },
    )
