"""
Tests for synapse.api_contracts.
Verifies all contract models import, validate, and satisfy privacy invariants.
"""
from datetime import datetime, timezone
import pytest

from synapse.api_contracts import (
    ConfirmTagsRequest,
    ConfirmTagsResponse,
    CreateConceptRequest,
    CreateConceptResponse,
    ErrorResponse,
    PendingTagsResponse,
    RunStatusResponse,
    StudentGraphResponse,
    StudentNotesResponse,
    SubmitAttemptRequest,
    SubmitAttemptResponse,
    TeacherAnalyticsResponse,
    TeacherTrendsResponse,
)
from synapse.schemas import (
    AnalysisPayload,
    Attempt,
    ClassAnalytics,
    ConceptNode,
    Diagnosis,
    GraphEdge,
    MistakeClassification,
    NoteVersion,
    ReviewResult,
    ReviewStatus,
    StudentHistory,
    Test,
    TestQuestion,
    TrendLabel,
)
from synapse.state_machine import RunState


def test_api_contract_models_import_and_instantiate():
    c_node = ConceptNode(name="Cell Biology", summary="Basic cell structure")
    tq = TestQuestion(
        text="What is the powerhouse of the cell?",
        correct_answer="Mitochondria",
        options=["Mitochondria", "Nucleus", "Ribosome", "Chloroplast"],
        concept_id=c_node.id,
    )
    test_obj = Test(concept_id=c_node.id, concept_name="Cell Biology", questions=[tq])
    attempt_obj = Attempt(student_id="s1", test_id=test_obj.id, concept_id=c_node.id, score=1, total=1)
    diag_obj = Diagnosis(student_id="s1", concept_id=c_node.id, mastery_estimate=0.9, trend=TrendLabel.IMPROVING)
    note_obj = NoteVersion(student_id="s1", concept_id=c_node.id, version=1, markdown="# Cell Biology")
    rev_obj = ReviewResult(passed=True, canonical_coverage=True, diagnosis_addressed=True, links_valid=True, status=ReviewStatus.PASSED)
    analysis_obj = AnalysisPayload(student_id="s1", concept_id=c_node.id, mastery_estimate=0.9, trend=TrendLabel.IMPROVING, cycle_number=1)
    class_analytics_obj = ClassAnalytics(concept_id=c_node.id, concept_name="Cell Biology", student_count=20, average_mastery=0.85)

    # Teacher endpoints
    req1 = CreateConceptRequest(markdown="# Cell Biology", concept_name="Cell Biology")
    assert req1.concept_name == "Cell Biology"

    resp1 = CreateConceptResponse(concept=c_node, run_id="run_123")
    assert resp1.run_id == "run_123"

    pt_resp = PendingTagsResponse(run_id="run_123", concept_id=c_node.id, concepts=[c_node], expires_at=datetime.now(timezone.utc))
    assert pt_resp.concept_id == c_node.id

    ct_req = ConfirmTagsRequest(run_id="run_123", confirmed=True, edited_concepts=[c_node])
    assert ct_req.confirmed is True

    ct_resp = ConfirmTagsResponse(run_id="run_123", state=RunState.TEST_READY, test=test_obj)
    assert ct_resp.state is RunState.TEST_READY

    ta_resp = TeacherAnalyticsResponse(concept_id=c_node.id, concept_name="Cell Biology", analytics=class_analytics_obj)
    assert ta_resp.concept_name == "Cell Biology"

    tt_resp = TeacherTrendsResponse(concept_id=c_node.id, trends=[analysis_obj])
    assert len(tt_resp.trends) == 1

    # Student endpoints
    sa_req = SubmitAttemptRequest(test_id=test_obj.id, answers={"q1": "Mitochondria"})
    assert sa_req.test_id == test_obj.id

    sa_resp = SubmitAttemptResponse(
        run_id="run_123",
        attempt=attempt_obj,
        diagnosis=diag_obj,
        note=note_obj,
        review=rev_obj,
        analysis=analysis_obj,
    )
    assert sa_resp.run_id == "run_123"

    sn_resp = StudentNotesResponse(notes=[note_obj])
    assert len(sn_resp.notes) == 1

    edge = GraphEdge(from_concept=c_node.id, to_concept=c_node.id, relationship="related")
    sg_resp = StudentGraphResponse(nodes=[c_node], edges=[edge])
    assert len(sg_resp.nodes) == 1

    # Runtime / Shared
    rs_resp = RunStatusResponse(
        run_id="run_123",
        state=RunState.COMPLETE,
        current_cycle=1,
        revision_count=0,
        model_call_count=3,
        error=None,
    )
    assert rs_resp.current_cycle == 1

    err_resp = ErrorResponse(error="validation_error", message="Field missing", details={"field": "concept_name"})
    assert err_resp.error == "validation_error"


def test_privacy_rule_teacher_models_never_expose_notes():
    """No model reachable from a Teacher-endpoint response may contain NoteVersion or StudentHistory."""
    teacher_models = [
        CreateConceptResponse,
        PendingTagsResponse,
        ConfirmTagsResponse,
        TeacherAnalyticsResponse,
        TeacherTrendsResponse,
    ]

    for model in teacher_models:
        for field_name, field_info in model.model_fields.items():
            field_type = str(field_info.annotation)
            assert "NoteVersion" not in field_type, f"Teacher model {model.__name__} exposes NoteVersion in {field_name}"
            assert "StudentHistory" not in field_type, f"Teacher model {model.__name__} exposes StudentHistory in {field_name}"
