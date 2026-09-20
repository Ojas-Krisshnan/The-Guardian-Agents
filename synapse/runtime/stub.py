"""
SYNAPSE RUNTIME STUB — Deterministic test-time stubs for downstream orchestration.
Enables runtime tests to exercise full state machine without live models or Person 2/3/4 code.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, D.5.
"""
from __future__ import annotations

from typing import Any, Callable

from slice import callback
from slice.runner import Context
from synapse.runtime.flow import SynapseFlow, build_synapse_flow
from synapse.state_machine import (
    MAX_REVISIONS_PER_CYCLE,
    ReviewStatus,
    RunState,
    resolve_review_status,
    state_after_review,
)

# ----------------------------------------------------------------------
# Deterministic Sample Fixtures
# ----------------------------------------------------------------------

SAMPLE_CONCEPTS = [
    {"name": "Light-dependent reactions", "summary": "Photosystem II and electron transport chain"},
    {"name": "Calvin cycle", "summary": "Carbon fixation producing G3P"},
]

SAMPLE_TEST = {
    "test_id": "test_photosynthesis_01",
    "questions": [
        {
            "question_id": "q1",
            "prompt": "Where do light-dependent reactions occur?",
            "options": ["Thylakoid membrane", "Stroma", "Cytoplasm", "Outer membrane"],
            "correct_answer": "Thylakoid membrane",
        }
    ],
}

SAMPLE_DIAGNOSIS = {
    "misconceptions": ["Confuses stroma with thylakoid membrane function"],
    "recommended_focus": ["Thylakoid architecture and proton gradients"],
}

SAMPLE_NOTE = {
    "markdown": "# Revision: Light Reactions\nRemember that ATP synthesis occurs on thylakoid membranes.",
    "version": 1,
}

SAMPLE_ANALYSIS = {
    "mastery_level": 0.75,
    "trend": "improving",
}

SAMPLE_CLASS_ANALYTICS = {
    "average_mastery": 0.72,
    "common_gaps": ["Thylakoid structure"],
}


# ----------------------------------------------------------------------
# Deterministic Stub Handlers for Person 2/3/4 States
# ----------------------------------------------------------------------

def stub_teacher_setup(ctx: Context) -> RunState:
    """Stub for Curriculum handle_teacher_setup: extracts concepts and transitions."""
    if not ctx.latest("canonical_note"):
        ctx.append(
            "canonical_note",
            {"concepts": SAMPLE_CONCEPTS, "teacher_confirmed": False},
            produced_by="curriculum_stub",
        )
    callback.ask(
        store=ctx.store,
        run_id=ctx.run_id,
        question="Please confirm extracted concepts",
        context={"concepts": SAMPLE_CONCEPTS, "park_state": RunState.TAG_CONFIRMATION.value, "resume_state": RunState.TEST_READY.value},
        settings=ctx.settings,
        park_state=RunState.TAG_CONFIRMATION,
        resume_state=RunState.TEST_READY,
    )
    return RunState.TAG_CONFIRMATION


def stub_tag_confirmation(ctx: Context) -> RunState:
    """Stub for Curriculum handle_tag_confirmation: asks callback question."""
    # If not already asked, park via callback.ask
    open_qs = [q for q in ctx.store.open_questions(ctx.run_id) if not q.is_expired]
    if not open_qs:
        callback.ask(
            store=ctx.store,
            run_id=ctx.run_id,
            question="Please confirm extracted concepts",
            context={"concepts": SAMPLE_CONCEPTS, "park_state": RunState.TAG_CONFIRMATION.value, "resume_state": RunState.TEST_READY.value},
            settings=ctx.settings,
            park_state=RunState.TAG_CONFIRMATION,
            resume_state=RunState.TEST_READY,
        )
    return RunState.TAG_CONFIRMATION


def stub_test_ready(ctx: Context) -> RunState:
    """Stub for Curriculum handle_test_ready: generates test and waits for student."""
    if not ctx.latest("test"):
        ctx.append("test", SAMPLE_TEST, produced_by="curriculum_stub")
    return RunState.AWAITING_STUDENT


def stub_diagnosing(ctx: Context) -> RunState:
    """Stub for Agents handle_diagnosing: writes diagnosis item."""
    ctx.append("diagnosis", SAMPLE_DIAGNOSIS, produced_by="diagnosis_stub")
    return RunState.TAILORING


def stub_tailoring(ctx: Context) -> RunState:
    """Stub for Agents handle_tailoring: writes note candidate."""
    ctx.append("note_candidate", SAMPLE_NOTE, produced_by="tailoring_stub")
    return RunState.REVIEWING


def stub_reviewing_pass(ctx: Context) -> RunState:
    """Stub for Agents handle_reviewing: simulates passing review."""
    ctx.append(
        "review",
        {"status": ReviewStatus.PASSED.value, "comments": "Accurate and clear"},
        produced_by="review_stub",
    )
    return RunState.NOTE_SAVED


def stub_reviewing_fail_once(ctx: Context) -> RunState:
    """Stub for Agents handle_reviewing: fails once, then passes on revision."""
    meta = ctx.store.meta(ctx.run_id)
    cycle = meta.get("scope", {}).get("cycle", 1)
    revisions = sum(
        1 for r in ctx.history("review")
        if r.payload.get("status") == "failed" and r.payload.get("cycle", 1) == cycle
    )
    if revisions == 0:
        ctx.append(
            "review",
            {"status": ReviewStatus.FAILED.value, "cycle": cycle, "objections": ["Needs clearer terminology"]},
            produced_by="review_stub",
        )
        return RunState.TAILORING
    ctx.append(
        "review",
        {"status": ReviewStatus.PASSED.value, "cycle": cycle, "comments": "Resolved"},
        produced_by="review_stub",
    )
    return RunState.NOTE_SAVED


def stub_analysing(ctx: Context) -> RunState:
    """Stub for Analytics handle_analysing: computes mastery trends."""
    ctx.append("analysis", SAMPLE_ANALYSIS, produced_by="analytics_stub")
    return RunState.AGGREGATING


def stub_aggregating(ctx: Context) -> RunState:
    """Stub for Analytics handle_aggregating: aggregates class metrics."""
    ctx.append("class_analytics", SAMPLE_CLASS_ANALYTICS, produced_by="analytics_stub")
    return RunState.COMPLETE


def build_stubbed_synapse_flow(
    review_fails: bool = False,
    extra_handlers: dict[RunState, Callable] | None = None,
) -> SynapseFlow:
    """Construct a full SynapseFlow backed by deterministic test stubs."""
    handlers = {
        RunState.TEACHER_SETUP: stub_teacher_setup,
        RunState.TAG_CONFIRMATION: stub_tag_confirmation,
        RunState.TEST_READY: stub_test_ready,
        RunState.DIAGNOSING: stub_diagnosing,
        RunState.TAILORING: stub_tailoring,
        RunState.REVIEWING: stub_reviewing_fail_once if review_fails else stub_reviewing_pass,
        RunState.ANALYSING: stub_analysing,
        RunState.AGGREGATING: stub_aggregating,
    }
    if extra_handlers:
        handlers.update(extra_handlers)
    return build_synapse_flow(handler_overrides=handlers)
