# synapse/runtime/flow.py
"""Synapse Flow assembly, runtime handlers, and lifecycle orchestration (Person 1)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from slice import callback, runner
from slice.config import Settings, settings as get_settings
from slice.store import Store
from synapse.agents.flow import (
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
)
from synapse.analytics.flow import (
    handle_aggregating,
    handle_analysing,
)
from synapse.api_contracts import RunStatusResponse
from synapse.curriculum.flow import (
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
)
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    ConceptNode,
    NoteVersion,
    RecordKind,
    ReviewStatus,
    RunScope,
    Test,
)
from synapse.state_machine import RunState


async def handle_awaiting_student(ctx: Any) -> RunState:
    """Parked state waiting for a student attempt to arrive."""
    attempt_data = ctx.latest(RecordKind.ATTEMPT)
    if attempt_data is not None:
        return RunState.ATTEMPT_RECEIVED
    return RunState.AWAITING_STUDENT


async def handle_attempt_received(ctx: Any) -> RunState:
    """Scores student attempt against Test and moves to diagnosing."""
    attempt_data = ctx.latest(RecordKind.ATTEMPT)
    if attempt_data is None:
        return RunState.AWAITING_STUDENT
    attempt = Attempt.model_validate(attempt_data)

    test_data = ctx.latest(RecordKind.TEST)
    if test_data:
        test = Test.model_validate(test_data)
        score = 0
        total = len(test.questions)
        for q in test.questions:
            student_ans = attempt.answers.get(q.id)
            if student_ans == q.correct_answer:
                score += 1
        attempt.score = score
        attempt.total = total
        ctx.append(RecordKind.ATTEMPT, attempt.model_dump(mode="json"), produced_by="runtime:scoring")

    return RunState.DIAGNOSING


async def handle_note_saved(ctx: Any) -> RunState:
    """Promotes candidate note to canonical student NoteVersion."""
    cand_data = ctx.latest(RecordKind.NOTE_CANDIDATE)
    if cand_data:
        candidate = NoteVersion.model_validate(cand_data)
        ctx.append(RecordKind.NOTE_VERSION, candidate.model_dump(mode="json"), produced_by="runtime:note_saved")

    return RunState.ANALYSING


async def handle_complete(ctx: Any) -> RunState:
    """Terminal state for cycle. If a subsequent cycle is started, restarts."""
    scope = getattr(ctx, "scope", {})
    if scope.get("next_cycle_ready", False):
        return RunState.AWAITING_STUDENT
    return RunState.COMPLETE


def _make_sync_wrapper(async_fn):
    """Bridge async handlers to slice runner's synchronous advance dispatcher."""
    import asyncio
    import concurrent.futures

    def sync_handler(ctx):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, async_fn(ctx)).result()
        else:
            import anyio
            return anyio.run(async_fn, ctx)

    return sync_handler


SYNAPSE_FLOW = SimpleNamespace(
    name="synapse",
    handlers={
        RunState.TEACHER_SETUP: _make_sync_wrapper(handle_teacher_setup),
        RunState.TAG_CONFIRMATION: _make_sync_wrapper(handle_tag_confirmation),
        RunState.TEST_READY: _make_sync_wrapper(handle_test_ready),
        RunState.AWAITING_STUDENT: _make_sync_wrapper(handle_awaiting_student),
        RunState.ATTEMPT_RECEIVED: _make_sync_wrapper(handle_attempt_received),
        RunState.DIAGNOSING: _make_sync_wrapper(handle_diagnosing),
        RunState.TAILORING: _make_sync_wrapper(handle_tailoring),
        RunState.REVIEWING: _make_sync_wrapper(handle_reviewing),
        RunState.NOTE_SAVED: _make_sync_wrapper(handle_note_saved),
        RunState.ANALYSING: _make_sync_wrapper(handle_analysing),
        RunState.AGGREGATING: _make_sync_wrapper(handle_aggregating),
        RunState.COMPLETE: _make_sync_wrapper(handle_complete),
    },
)


# ════════════════════════════════════════════════════════════════════════════
# RUNTIME SERVICES
# ════════════════════════════════════════════════════════════════════════════

def start_teacher_run(
    store: Store,
    markdown: str,
    concept_name: str,
    teacher_id: str,
    settings: Settings | None = None,
) -> str:
    """Creates a run at TEACHER_SETUP, appends initial canonical note, and advances."""
    s = settings or get_settings()
    concept = ConceptNode(name=concept_name, summary=f"Overview of {concept_name}")
    canonical = CanonicalNote(
        concept_id=concept.id,
        markdown=markdown,
        extracted_concepts=[concept],
    )
    scope = RunScope(
        concept_id=concept.id,
        concept_name=concept_name,
        teacher_id=teacher_id,
        cycle=1,
    )

    run_id = store.create_run("synapse", scope.model_dump(mode="json"))
    store.set_state(run_id, RunState.TEACHER_SETUP)
    store.append(run_id, RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="teacher")

    # Advance until parked at TAG_CONFIRMATION
    runner.advance(store, run_id, SYNAPSE_FLOW, s)
    return run_id


def submit_attempt(
    store: Store,
    run_id: str,
    student_id: str,
    test_id: str,
    answers: dict[str, str],
    settings: Settings | None = None,
) -> str:
    """Submits a student's test attempt and advances through the pipeline."""
    s = settings or get_settings()

    test_data = store.latest(run_id, RecordKind.TEST)
    concept_id = "c1"
    score = 0
    total = len(answers)
    if test_data:
        test = Test.model_validate(test_data)
        concept_id = test.concept_id
        total = len(test.questions)
        for q in test.questions:
            if answers.get(q.id) == q.correct_answer:
                score += 1

    attempt = Attempt(
        student_id=student_id,
        test_id=test_id,
        concept_id=concept_id,
        answers=answers,
        score=score,
        total=total,
    )

    # Append attempt and set state to ATTEMPT_RECEIVED
    store.append(run_id, RecordKind.ATTEMPT, attempt.model_dump(mode="json"), produced_by=f"student:{student_id}")
    store.set_state(run_id, RunState.ATTEMPT_RECEIVED)

    # Advance until complete or parked
    runner.advance(store, run_id, SYNAPSE_FLOW, s)
    return run_id


def get_run_status(store: Store, run_id: str) -> RunStatusResponse:
    """Computes current status, cycle number, and derived revision count."""
    state = store.get_state(run_id)
    scope_data = {}
    try:
        run_meta = store.get_run(run_id)
        scope_data = run_meta.get("scope", {})
    except Exception:
        pass

    cycle = int(scope_data.get("cycle", 1))

    # Derive revisions from review history
    reviews = store.history(run_id, RecordKind.REVIEW)
    revision_count = sum(1 for r in reviews if getattr(r, "payload", {}).get("status") == ReviewStatus.FAILED.value)

    # Model calls
    call_count = store.get_counter(run_id, "model_calls") if hasattr(store, "get_counter") else 0

    failure_rec = store.latest(run_id, "failure")
    error = failure_rec.get("detail") if failure_rec else None

    # Convert state to Synapse RunState if needed
    synapse_state = state if isinstance(state, RunState) else RunState(state.value if hasattr(state, "value") else str(state))

    return RunStatusResponse(
        run_id=run_id,
        state=synapse_state,
        current_cycle=cycle,
        revision_count=revision_count,
        model_call_count=call_count,
        error=error,
    )


def sweep_expired(store: Store) -> list[Any]:
    """Sweeps expired human callback questions and triggers timeouts."""
    return callback.sweep(store)


def advance(store: Store, run_id: str, settings: Settings | None = None, max_steps: int = 40) -> RunState:
    """Advances run through the Synapse flow."""
    s = settings or get_settings()
    res = runner.advance(store, run_id, SYNAPSE_FLOW, s, max_steps=max_steps)
    return res if isinstance(res, RunState) else RunState(res.value if hasattr(res, "value") else str(res))
