# tests/test_synapse/test_contracts.py
# Baseline contract tests from Contracts.md Section E.3
import typing
import pytest
from pydantic import BaseModel, ValidationError

from synapse import api_contracts
from synapse.schemas import (
    ConceptGraph, ConceptNode, GraphEdge, NoteVersion, StudentHistory, TestQuestion,
    ReviewStatus, RecordKind, RECORD_PAYLOADS, MAX_REVISIONS_PER_CYCLE,
)
from synapse.state_machine import (
    RunState, VALID_TRANSITIONS, TRANSITION_RULES, PARKED_STATES, FAILURE_RETRY_STATE,
    resolve_review_status, state_after_review,
)


# ── state machine consistency ────────────────────────────────────────────
def test_every_state_has_a_transition_entry():
    assert set(VALID_TRANSITIONS) == set(RunState)

def test_rules_and_transitions_are_the_same_set():
    from_rules = {(r.from_state, r.to_state) for r in TRANSITION_RULES}
    from_table = {(a, b) for a, bs in VALID_TRANSITIONS.items() for b in bs}
    assert from_rules == from_table

def test_parked_states_and_retry_states_are_valid():
    assert PARKED_STATES <= set(RunState)
    assert set(FAILURE_RETRY_STATE) <= set(RunState)
    assert not (PARKED_STATES & set(FAILURE_RETRY_STATE))

def test_revision_limit_is_bounded():
    assert resolve_review_status(True, 0) is ReviewStatus.PASSED
    assert resolve_review_status(False, MAX_REVISIONS_PER_CYCLE - 1) is ReviewStatus.FAILED
    assert resolve_review_status(False, MAX_REVISIONS_PER_CYCLE) is ReviewStatus.REVISION_LIMIT_REACHED
    assert state_after_review(ReviewStatus.FAILED) is RunState.TAILORING
    assert state_after_review(ReviewStatus.REVISION_LIMIT_REACHED) is RunState.NOTE_SAVED

def test_every_state_is_reachable_from_teacher_setup():
    seen, todo = set(), [RunState.TEACHER_SETUP]
    while todo:
        s = todo.pop()
        if s not in seen:
            seen.add(s); todo += VALID_TRANSITIONS[s]
    assert seen == set(RunState)

# ── record kinds ─────────────────────────────────────────────────────────
def test_every_record_kind_has_a_payload_schema():
    assert set(RECORD_PAYLOADS) == set(RecordKind)

# ── graph integrity ──────────────────────────────────────────────────────
def _n(name, prereqs=()):
    return ConceptNode(name=name, summary=name, prerequisites=list(prereqs))

def test_graph_accepts_a_dag():
    a = _n("a"); b = _n("b", [a.id])
    g = ConceptGraph(nodes=[a, b], edges=[GraphEdge(from_concept=a.id, to_concept=b.id, relationship="prerequisite")])
    assert len(g.edges) == 1

def test_graph_rejects_cycles():
    a = _n("a"); b = _n("b")
    a.prerequisites, b.prerequisites = [b.id], [a.id]
    edges = [GraphEdge(from_concept=b.id, to_concept=a.id, relationship="prerequisite"),
             GraphEdge(from_concept=a.id, to_concept=b.id, relationship="prerequisite")]
    with pytest.raises(ValidationError):
        ConceptGraph(nodes=[a, b], edges=edges)

def test_graph_rejects_dangling_edge_and_drift():
    a = _n("a")
    with pytest.raises(ValidationError):
        ConceptGraph(nodes=[a], edges=[GraphEdge(from_concept=a.id, to_concept="nope", relationship="related")])
    b = _n("b", [a.id])  # declared prereq but no edge
    with pytest.raises(ValidationError):
        ConceptGraph(nodes=[a, b], edges=[])

# ── test question integrity ──────────────────────────────────────────────
def test_question_answer_must_be_an_option():
    with pytest.raises(ValidationError):
        TestQuestion(text="q", correct_answer="z", options=["a", "b", "c", "d"], concept_id="c")

# ── privacy: no note text reachable from teacher responses ───────────────
def _reachable(model, seen=None):
    seen = set() if seen is None else seen
    if model in seen: return seen
    seen.add(model)
    for f in model.model_fields.values():
        stack = [f.annotation]
        while stack:
            t = stack.pop()
            if isinstance(t, type) and issubclass(t, BaseModel):
                _reachable(t, seen)
            stack += list(typing.get_args(t))
    return seen

@pytest.mark.parametrize("name", ["CreateConceptResponse", "PendingTagsResponse", "ConfirmTagsResponse",
                                  "TeacherAnalyticsResponse", "TeacherTrendsResponse"])
def test_teacher_models_never_expose_notes(name):
    reach = _reachable(getattr(api_contracts, name))
    assert NoteVersion not in reach and StudentHistory not in reach
