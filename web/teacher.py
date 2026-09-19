"""
Server-rendered web endpoints for teacher workflows.
Authoritative contract: Contracts.md Sections D.5, D.6.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from slice import callback
from synapse.runtime.service import get_service
from synapse.schemas import ConceptNode, RecordKind
from synapse.state_machine import RunState

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/web/teacher", tags=["web_teacher"])


@router.get("/tags/{run_id}", response_class=HTMLResponse)
async def get_teacher_tags_page(request: Request, run_id: str):
    service = get_service()
    try:
        current_state = service.store.get_state(run_id, state_type=RunState)
    except KeyError:
        raise HTTPException(status_code=404, detail="Run not found")

    scope = service.store.meta(run_id).get("scope", {})
    concept_name = scope.get("concept_name", "Curriculum Topic")

    concepts = []
    latest_note = service.store.latest(run_id, RecordKind.CANONICAL_NOTE.value)
    if latest_note:
        concepts = [
            ConceptNode.model_validate(c)
            for c in latest_note.get("extracted_concepts", [])
        ]

    return templates.TemplateResponse(
        request=request,
        name="teacher_tags.html",
        context={
            "run_id": run_id,
            "concept_name": concept_name,
            "concepts": concepts,
        },
    )


@router.post("/tags/{run_id}")
async def post_teacher_tags(request: Request, run_id: str):
    service = get_service()
    form_data = await request.form()

    # Find open question for tag confirmation
    open_qs = [q for q in service.store.open_questions(run_id) if not q.is_expired]
    if not open_qs:
        raise HTTPException(status_code=409, detail="Tag confirmation question not open or already answered")

    qid = open_qs[0].id

    # Parse edited concepts from form
    edited_concepts = []
    idx = 0
    while f"concept_name_{idx}" in form_data:
        cid = form_data.get(f"concept_id_{idx}")
        name = form_data.get(f"concept_name_{idx}")
        summary = form_data.get(f"concept_summary_{idx}")
        if cid and name and summary:
            edited_concepts.append(
                ConceptNode(id=str(cid), name=str(name), summary=str(summary))
            )
        idx += 1

    answer_payload = {
        "confirmed": True,
        "edited_concepts": [c.model_dump(mode="json") for c in edited_concepts],
    }
    callback.answer(
        service.store,
        qid,
        json.dumps(answer_payload),
        who="teacher_web",
    )
    service.advance(run_id)

    return RedirectResponse(
        url=f"/web/teacher/tags/{run_id}/confirm",
        status_code=303,
    )


@router.get("/tags/{run_id}/confirm", response_class=HTMLResponse)
async def get_teacher_confirm_page(request: Request, run_id: str):
    return templates.TemplateResponse(
        request=request,
        name="teacher_confirm.html",
        context={
            "run_id": run_id,
        },
    )
