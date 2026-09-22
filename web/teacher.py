# web/teacher.py
"""Server-rendered callback UI for teacher tag confirmation."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from api.dependencies import get_settings_dep, get_store
from slice.config import Settings
from slice.store import Store
from synapse.runtime.flow import advance
from synapse.schemas import CanonicalNote, ConceptNode, RecordKind
from synapse.state_machine import RunState

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
router = APIRouter(tags=["web-teacher"])


@router.get("/web/teacher/tags/{run_id}", response_class=HTMLResponse)
async def get_teacher_tags_form(
    run_id: str,
    request: Request,
    store: Store = Depends(get_store),
):
    note_data = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    if not note_data:
        raise HTTPException(status_code=404, detail="Canonical note not found")

    canonical = CanonicalNote.model_validate(note_data)
    return templates.TemplateResponse(
        "teacher_tags.html",
        {"request": request, "run_id": run_id, "concepts": canonical.extracted_concepts},
    )


@router.post("/web/teacher/tags/{run_id}", response_class=HTMLResponse)
async def post_teacher_tags(
    run_id: str,
    request: Request,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
):
    form_data = await request.form()
    note_data = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    if not note_data:
        raise HTTPException(status_code=404, detail="Canonical note not found")

    canonical = CanonicalNote.model_validate(note_data)
    edited_concepts = []
    for idx, orig in enumerate(canonical.extracted_concepts):
        name = form_data.get(f"concept_name_{idx}", orig.name)
        summary = form_data.get(f"concept_summary_{idx}", orig.summary)
        edited_concepts.append(
            ConceptNode(
                id=orig.id,
                name=name,
                summary=summary,
                prerequisites=orig.prerequisites,
            )
        )

    open_qs = store.open_questions(run_id)
    if open_qs:
        qid = open_qs[0].id
        answer_payload = {
            "confirmed": True,
            "edited_concepts": [c.model_dump(mode="json") for c in edited_concepts],
            "timed_out": False,
        }
        store.answer(qid, json.dumps(answer_payload))
        advance(store, run_id, settings)

    return RedirectResponse(url=f"/web/teacher/tags/{run_id}/confirm", status_code=303)


@router.get("/web/teacher/tags/{run_id}/confirm", response_class=HTMLResponse)
async def get_teacher_confirm_page(
    run_id: str,
    request: Request,
    store: Store = Depends(get_store),
):
    state = store.get_state(run_id)
    return templates.TemplateResponse(
        "teacher_confirm.html",
        {"request": request, "run_id": run_id, "state": state.value if hasattr(state, "value") else str(state)},
    )
