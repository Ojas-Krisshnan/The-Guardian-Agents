"""Questions router implementation with role-based API protection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import get_current_user, require_teacher
from api.deps import get_store
from api.models import AnswerQuestionRequest, QuestionResponse
from slice import callback
from slice.store import Store

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: str,
    store: Store = Depends(get_store),
    user: dict = Depends(get_current_user),
) -> QuestionResponse:
    """Get question details by question_id (Authenticated)."""
    q = store.get_question(question_id)
    if q is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return QuestionResponse(
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


@router.post("/{question_id}/answer", response_model=QuestionResponse)
def answer_question(
    question_id: str,
    req: AnswerQuestionRequest,
    store: Store = Depends(get_store),
    user: dict = Depends(require_teacher),
) -> QuestionResponse:
    """Answer a pending question and resume the run (Teacher only)."""
    q = store.get_question(question_id)
    if q is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    if q.is_answered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question is already answered",
        )

    who_name = req.who or user.get("sub", "teacher")
    res_run_id = callback.answer(store, question_id, req.answer, who=who_name)
    if res_run_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    updated_q = store.get_question(question_id)
    if updated_q is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    return QuestionResponse(
        id=updated_q.id,
        run_id=updated_q.run_id,
        question=updated_q.question,
        context=updated_q.context,
        asked_at=updated_q.asked_at,
        timeout_at=updated_q.timeout_at,
        answered_at=updated_q.answered_at,
        answer=updated_q.answer,
        is_answered=updated_q.is_answered,
        is_expired=updated_q.is_expired,
    )
