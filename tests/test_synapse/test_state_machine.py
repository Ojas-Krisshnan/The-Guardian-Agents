"""
Tests for synapse.state_machine.
Verifies exact compliance with Contracts.md Section C.3:
- State and transition inventories
- Parked states and terminal semantics
- Helper properties (is_terminal, is_suspended)
- can_transition, get_transition_rule, can_revise, resolve_review_status, state_after_review
- TransitionRule.max_retries and FAILURE_RETRY_STATE
"""
import pytest
from synapse.schemas import (
    MAX_MODEL_CALL_RETRIES,
    MAX_REVISIONS_PER_CYCLE,
    ReviewStatus,
)
from synapse.state_machine import (
    FAILURE_RETRY_STATE,
    PARKED_STATES,
    TRANSITION_RULES,
    VALID_TRANSITIONS,
    RunState,
    TransitionRule,
    can_revise,
    can_transition,
    get_transition_rule,
    resolve_review_status,
    state_after_review,
)


def test_state_inventory_exact_12_states():
    """State machine must contain exactly 12 states and NO FAILED state."""
    states = list(RunState)
    assert len(states) == 12
    state_values = {s.value for s in states}
    expected = {
        "teacher_setup",
        "tag_confirmation",
        "test_ready",
        "awaiting_student",
        "attempt_received",
        "diagnosing",
        "tailoring",
        "reviewing",
        "note_saved",
        "analysing",
        "aggregating",
        "complete",
    }
    assert state_values == expected
    assert "failed" not in state_values
    assert not hasattr(RunState, "FAILED")


def test_parked_states():
    """Parked states are exactly TAG_CONFIRMATION and AWAITING_STUDENT."""
    assert PARKED_STATES == frozenset({RunState.TAG_CONFIRMATION, RunState.AWAITING_STUDENT})
    assert RunState.COMPLETE not in PARKED_STATES


def test_run_state_helper_properties():
    """is_terminal and is_suspended behave correctly."""
    for state in RunState:
        if state is RunState.COMPLETE:
            assert state.is_terminal is True
        else:
            assert state.is_terminal is False

        if state in PARKED_STATES:
            assert state.is_suspended is True
        else:
            assert state.is_suspended is False


def test_transitions_inventory_exact():
    """Canonical transitions must match Contracts.md Section C.3."""
    expected_transitions = {
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
        RunState.COMPLETE: [RunState.AWAITING_STUDENT],
    }
    assert VALID_TRANSITIONS == expected_transitions


def test_transition_rule_attributes_and_max_retries():
    """TransitionRule has max_retries defaulting to MAX_MODEL_CALL_RETRIES."""
    rule = TransitionRule(
        from_state=RunState.TEACHER_SETUP,
        to_state=RunState.TAG_CONFIRMATION,
        trigger="code",
        description="test",
    )
    assert rule.max_retries == MAX_MODEL_CALL_RETRIES
    assert rule.max_retries == 3

    custom_rule = TransitionRule(
        from_state=RunState.TEACHER_SETUP,
        to_state=RunState.TAG_CONFIRMATION,
        trigger="code",
        description="custom",
        max_retries=5,
    )
    assert custom_rule.max_retries == 5


def test_failure_retry_state():
    """FAILURE_RETRY_STATE has exactly 5 entries mapping each to itself."""
    assert len(FAILURE_RETRY_STATE) == 5
    expected_keys = {
        RunState.DIAGNOSING,
        RunState.TAILORING,
        RunState.REVIEWING,
        RunState.ANALYSING,
        RunState.AGGREGATING,
    }
    assert set(FAILURE_RETRY_STATE.keys()) == expected_keys
    for k, v in FAILURE_RETRY_STATE.items():
        assert k == v
    assert RunState.COMPLETE not in FAILURE_RETRY_STATE


def test_can_transition():
    """can_transition returns True for all valid transitions, False otherwise."""
    for from_state, to_states in VALID_TRANSITIONS.items():
        for to_state in to_states:
            assert can_transition(from_state, to_state) is True

    # Invalid transitions
    assert can_transition(RunState.TEACHER_SETUP, RunState.COMPLETE) is False
    assert can_transition(RunState.AWAITING_STUDENT, RunState.NOTE_SAVED) is False
    assert can_transition(RunState.COMPLETE, RunState.DIAGNOSING) is False
    assert can_transition(RunState.NOTE_SAVED, RunState.TEACHER_SETUP) is False


def test_get_transition_rule():
    """get_transition_rule returns matching rule or None."""
    rule = get_transition_rule(RunState.TEACHER_SETUP, RunState.TAG_CONFIRMATION)
    assert rule is not None
    assert rule.from_state == RunState.TEACHER_SETUP
    assert rule.to_state == RunState.TAG_CONFIRMATION
    assert rule.trigger == "code"
    assert rule.max_retries == MAX_MODEL_CALL_RETRIES

    # Reviewing loops back to tailoring
    review_loop = get_transition_rule(RunState.REVIEWING, RunState.TAILORING)
    assert review_loop is not None
    assert review_loop.trigger == "model"

    # Invalid transition returns None
    invalid = get_transition_rule(RunState.TEACHER_SETUP, RunState.COMPLETE)
    assert invalid is None


def test_can_revise_boundaries():
    """can_revise boundary semantics for default and custom maximums."""
    # Default MAX_REVISIONS_PER_CYCLE = 3
    assert can_revise(0) is True
    assert can_revise(1) is True
    assert can_revise(2) is True
    assert can_revise(3) is False  # Exactly at limit
    assert can_revise(4) is False  # Above limit

    # Custom limit
    assert can_revise(1, max_revisions=2) is True
    assert can_revise(2, max_revisions=2) is False
    assert can_revise(3, max_revisions=2) is False


def test_resolve_review_status():
    """resolve_review_status signature and verdict handling."""
    # Passed always returns PASSED regardless of revisions
    assert resolve_review_status(passed=True, revisions_so_far=0) == ReviewStatus.PASSED
    assert resolve_review_status(passed=True, revisions_so_far=3) == ReviewStatus.PASSED
    assert resolve_review_status(passed=True, revisions_so_far=5) == ReviewStatus.PASSED

    # Failed before revision limit returns FAILED
    assert resolve_review_status(passed=False, revisions_so_far=0) == ReviewStatus.FAILED
    assert resolve_review_status(passed=False, revisions_so_far=1) == ReviewStatus.FAILED
    assert resolve_review_status(passed=False, revisions_so_far=2) == ReviewStatus.FAILED

    # Failed at or above revision limit returns REVISION_LIMIT_REACHED
    assert resolve_review_status(passed=False, revisions_so_far=3) == ReviewStatus.REVISION_LIMIT_REACHED
    assert resolve_review_status(passed=False, revisions_so_far=4) == ReviewStatus.REVISION_LIMIT_REACHED


def test_state_after_review():
    """state_after_review transitions based on ReviewStatus."""
    assert state_after_review(ReviewStatus.FAILED) == RunState.TAILORING
    assert state_after_review(ReviewStatus.PASSED) == RunState.NOTE_SAVED
    assert state_after_review(ReviewStatus.REVISION_LIMIT_REACHED) == RunState.NOTE_SAVED
