"""
Human-in-the-loop as a STATE, not an exception.

The naive version blocks: call a human, wait, hope the process survives. It
never does. Here, asking a human is a state transition - the run moves to
AWAITING_EXPERT, the question is persisted, and the process is free to exit
entirely. A later invocation picks the run back up from the database.

That is only possible because state lives in the store rather than in a
conversation, which is why this is Tier 2 and durable state is Tier 1.

And every wait has a deadline. An expert who never answers must not strand a
run forever - the timeout converts an unanswered question into a recorded
"nobody knew", which is a legitimate finding and lets the run continue.
"""
from __future__ import annotations

from typing import Any

from .config import Settings
from .records import Question, RunState
from .store import Store


def ask(store: Store, run_id: str, question: str, context: dict,
        settings: Settings, park_state: Any = None, resume_state: Any = None) -> str:
    """Suspend the run on a human. Returns the question id."""
    ctx = dict(context)
    target_park = park_state or ctx.get("park_state", RunState.AWAITING_EXPERT)
    if resume_state is not None: ctx["resume_state"] = getattr(resume_state, "value", str(resume_state))
    if park_state is not None and "park_state" not in ctx:
        ctx["park_state"] = getattr(park_state, "value", str(park_state))
    qid = store.ask(run_id, question, ctx, settings.expert_timeout_minutes)
    store.set_state(run_id, target_park)
    store.append(run_id, "question", {"id": qid, "question": question, "context": ctx}, produced_by="system")
    return qid


def answer(store: Store, question_id: str, text: str, who: str = "expert") -> str | None:
    """Record a human's answer and wake the run. Returns the run id, or None if
    the question is unknown. Answers are write-once - a second answer to the
    same question is ignored rather than silently overwriting the first."""
    q = store.get_question(question_id)
    if q is None:
        return None
    if q.is_answered:
        return q.run_id
    store.answer(question_id, text)
    store.append(q.run_id, "expert_answer",
                 {"question_id": question_id, "question": q.question,
                  "answer": text, "who": who, "source": "human_expert"},
                 produced_by=who)
    _resume(store, q)
    return q.run_id


def sweep(store: Store, run_id: str | None = None) -> list[Question]:
    """Expire questions nobody answered in time, and let those runs continue.

    Called by the runner before it does anything else, so a resumed run always
    starts from an honest picture. Returns the questions that expired.
    """
    expired = []
    for q in store.open_questions(run_id):
        if not q.is_expired:
            continue
        store.answer(q.id, "")           # closes it; empty answer means nobody replied
        store.append(q.run_id, "expert_answer",
                     {"question_id": q.id, "question": q.question, "answer": None,
                      "who": None, "source": "unresolved_no_expert",
                      "note": "timed out - recorded as unknown, not guessed"},
                     produced_by="system")
        _resume(store, q)
        expired.append(q)
    return expired


def pending(store: Store, run_id: str | None = None) -> list[Question]:
    """Open, unexpired questions - what the expert form shows."""
    return [q for q in store.open_questions(run_id) if not q.is_expired]


def _resume(store: Store, q: Question) -> None:
    cur = store.get_state(q.run_id)
    park = q.context.get("park_state", RunState.AWAITING_EXPERT.value)
    if cur is RunState.AWAITING_EXPERT or cur == park or getattr(cur, "value", str(cur)) == getattr(park, "value", str(park)):
        target = q.context.get("resume_state", RunState.PROBING.value)
        try:
            target = RunState(target)
        except (ValueError, TypeError):
            pass
        store.set_state(q.run_id, target)
