# synapse/state_machine.py
# SYNAPSE STATE MACHINE — states, legal transitions, revision rules.
# PROTECTED: PR required, all 5 approve.
#
# Relationship to slice/:
#   * slice/runner.py owns the mechanics (advance, Context, Flow protocol, persistence).
#   * This file owns the *vocabulary*: the state names the Synapse Flow registers handlers for.
#   * slice.records.RunState (generic lifecycle) is a different type. Do NOT import both under
#     the same name; if you need it: `from slice.records import RunState as SliceRunState`.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from synapse.schemas import (
    MAX_MODEL_CALL_RETRIES,
    MAX_REVISIONS_PER_CYCLE,
    ReviewStatus,
)


class RunState(str, Enum):
    TEACHER_SETUP = "teacher_setup"
    TAG_CONFIRMATION = "tag_confirmation"
    TEST_READY = "test_ready"
    AWAITING_STUDENT = "awaiting_student"
    ATTEMPT_RECEIVED = "attempt_received"
    DIAGNOSING = "diagnosing"
    TAILORING = "tailoring"
    REVIEWING = "reviewing"
    NOTE_SAVED = "note_saved"
    ANALYSING = "analysing"
    AGGREGATING = "aggregating"
    COMPLETE = "complete"


# Valid forward transitions
VALID_TRANSITIONS: dict[RunState, list[RunState]] = {
    RunState.TEACHER_SETUP: [RunState.TAG_CONFIRMATION],
    RunState.TAG_CONFIRMATION: [RunState.TEST_READY],
    RunState.TEST_READY: [RunState.AWAITING_STUDENT],
    RunState.AWAITING_STUDENT: [RunState.ATTEMPT_RECEIVED],
    RunState.ATTEMPT_RECEIVED: [RunState.DIAGNOSING],
    RunState.DIAGNOSING: [RunState.TAILORING],
    RunState.TAILORING: [RunState.REVIEWING],
    RunState.REVIEWING: [RunState.NOTE_SAVED, RunState.TAILORING],
    RunState.NOTE_SAVED: [RunState.ANALYSING],
    RunState.ANALYSING: [RunState.AGGREGATING],
    RunState.AGGREGATING: [RunState.COMPLETE],
    RunState.COMPLETE: [RunState.AWAITING_STUDENT],  # next cycle (RunScope.cycle += 1)
}

# States that wait for an external event. The runner parks the run here; it resumes only when
# slice.callback.answer() / sweep() or an API-triggered advance supplies the event.
PARKED_STATES: frozenset[RunState] = frozenset({RunState.TAG_CONFIRMATION, RunState.AWAITING_STUDENT})

TriggerType = Literal["code", "model", "human", "timeout", "human_or_timeout"]


@dataclass(frozen=True)
class TransitionRule:
    from_state: RunState
    to_state: RunState
    trigger: TriggerType
    description: str
    max_retries: int = MAX_MODEL_CALL_RETRIES


TRANSITION_RULES: list[TransitionRule] = [
    TransitionRule(RunState.TEACHER_SETUP, RunState.TAG_CONFIRMATION, "code", "Canonical note structured into concepts"),
    TransitionRule(RunState.TAG_CONFIRMATION, RunState.TEST_READY, "human_or_timeout", "Teacher confirms/tags or timeout expires"),
    TransitionRule(RunState.TEST_READY, RunState.AWAITING_STUDENT, "code", "Test passes schema validation"),
    TransitionRule(RunState.AWAITING_STUDENT, RunState.ATTEMPT_RECEIVED, "code", "Student submits attempt"),
    TransitionRule(RunState.ATTEMPT_RECEIVED, RunState.DIAGNOSING, "code", "Auto-transition to diagnosis"),
    TransitionRule(RunState.DIAGNOSING, RunState.TAILORING, "model", "LLM produces diagnosis"),
    TransitionRule(RunState.TAILORING, RunState.REVIEWING, "model", "LLM produces candidate note"),
    TransitionRule(RunState.REVIEWING, RunState.NOTE_SAVED, "model", "Review passes, or revision limit reached"),
    TransitionRule(RunState.REVIEWING, RunState.TAILORING, "model", "Review fails -> revision"),
    TransitionRule(RunState.NOTE_SAVED, RunState.ANALYSING, "code", "Note persisted"),
    TransitionRule(RunState.ANALYSING, RunState.AGGREGATING, "code", "Mastery/trend calculated (pure logic)"),
    TransitionRule(RunState.AGGREGATING, RunState.COMPLETE, "code", "Class summary + concept graph updated"),
    TransitionRule(RunState.COMPLETE, RunState.AWAITING_STUDENT, "code", "New test cycle begins"),
]

# Infrastructure failure (exception, invalid model output after repair) -> state to retry.
# Retries are bounded by MAX_MODEL_CALL_RETRIES (slice/budget.py attempt fence); after that the
# run stays in its state with `error` set and is resumable. A failed review VERDICT is not a
# failure: it is handled by resolve_review_status() below.
FAILURE_RETRY_STATE: dict[RunState, RunState] = {
    RunState.DIAGNOSING: RunState.DIAGNOSING,
    RunState.TAILORING: RunState.TAILORING,
    RunState.REVIEWING: RunState.REVIEWING,
    RunState.ANALYSING: RunState.ANALYSING,
    RunState.AGGREGATING: RunState.AGGREGATING,
}


def can_transition(from_state: RunState, to_state: RunState) -> bool:
    return to_state in VALID_TRANSITIONS.get(from_state, [])


def get_transition_rule(from_state: RunState, to_state: RunState) -> Optional[TransitionRule]:
    for rule in TRANSITION_RULES:
        if rule.from_state == from_state and rule.to_state == to_state:
            return rule
    return None


def can_revise(revisions_so_far: int, max_revisions: int = MAX_REVISIONS_PER_CYCLE) -> bool:
    return revisions_so_far < max_revisions


def resolve_review_status(passed: bool, revisions_so_far: int) -> ReviewStatus:
    """revisions_so_far = number of FAILED review records already stored for this run + cycle."""
    if passed:
        return ReviewStatus.PASSED
    return ReviewStatus.FAILED if can_revise(revisions_so_far) else ReviewStatus.REVISION_LIMIT_REACHED


def state_after_review(status: ReviewStatus) -> RunState:
    """FAILED loops back to TAILORING; PASSED and REVISION_LIMIT_REACHED both go to NOTE_SAVED."""
    return RunState.TAILORING if status is ReviewStatus.FAILED else RunState.NOTE_SAVED

