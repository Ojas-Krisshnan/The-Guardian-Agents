"""
Tests for Person 4 analytics domain: mastery, trends, aggregation, flow.
Authoritative contract: Contracts.md Sections A.5, C.2, D.2.
"""
import pytest

from slice.config import Settings
from slice.runner import Context
from slice.store import Store
from synapse.analytics import (
    aggregate,
    calculate_mastery,
    calculate_trend,
    handle_aggregating,
    handle_analysing,
)
from synapse.schemas import (
    CanonicalNote,
    ClassAnalytics,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    RecordKind,
    TrendLabel,
)
from synapse.state_machine import RunState


@pytest.fixture
def test_env(tmp_path):
    store = Store(tmp_path / "analytics_test.db")
    settings = Settings(
        api_key="test",
        model="test-model",
        fallback_model="test-fallback",
        escalation_model="test-esc",
        max_tokens=100,
        max_tokens_per_run=1000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    run_id = store.create_run(
        domain="synapse",
        meta={"scope": {"concept_id": "c_photo", "student_id": "student_01", "cycle": 1}},
        initial_state=RunState.ANALYSING,
    )
    ctx = Context(store, run_id, settings)
    return store, run_id, ctx


def test_calculate_mastery_and_trend():
    """Verify mastery weighting and trend classification."""
    diag1 = Diagnosis(
        id="d1",
        student_id="s1",
        concept_id="c1",
        mastery_estimate=0.4,
        trend=TrendLabel.NEW,
    )
    diag2 = Diagnosis(
        id="d2",
        student_id="s1",
        concept_id="c1",
        mastery_estimate=0.7,
        trend=TrendLabel.IMPROVING,
    )

    # 1. Mastery
    m1 = calculate_mastery([diag1], student_id="s1", concept_id="c1")
    assert m1 == 0.4

    # Weighted: 70% of 0.7 + 30% of 0.4 = 0.49 + 0.12 = 0.61
    m2 = calculate_mastery([diag1, diag2], student_id="s1", concept_id="c1")
    assert m2 == 0.61

    # 2. Trend
    t1 = calculate_trend([diag1])
    assert t1 == TrendLabel.NEW

    t2 = calculate_trend([diag1, diag2])
    assert t2 == TrendLabel.IMPROVING

    # Declining
    diag3 = Diagnosis(
        id="d3",
        student_id="s1",
        concept_id="c1",
        mastery_estimate=0.3,
        trend=TrendLabel.DECLINING,
    )
    t3 = calculate_trend([diag2, diag3])
    assert t3 == TrendLabel.DECLINING


def test_aggregate_multi_student():
    """Verify class-level aggregation properly identifies weak students and distributions."""
    diagnoses = [
        Diagnosis(id="d1", student_id="s1", concept_id="c_photo", mastery_estimate=0.8, trend=TrendLabel.IMPROVING),
        Diagnosis(id="d2", student_id="s2", concept_id="c_photo", mastery_estimate=0.4, trend=TrendLabel.STILL_WEAK),
        Diagnosis(id="d3", student_id="s3", concept_id="c_photo", mastery_estimate=0.6, trend=TrendLabel.STABLE),
    ]
    ca = aggregate(diagnoses, concept_id="c_photo", concept_name="Photosynthesis")
    assert isinstance(ca, ClassAnalytics)
    assert ca.student_count == 3
    assert ca.average_mastery == 0.6
    assert ca.weak_students == ["s2"]
    assert ca.trend_distribution[TrendLabel.IMPROVING] == 1
    assert ca.trend_distribution[TrendLabel.STILL_WEAK] == 1
    assert ca.trend_distribution[TrendLabel.STABLE] == 1


def test_handle_analysing_and_aggregating_flow(test_env):
    """Verify flow handlers for ANALYSING -> AGGREGATING -> COMPLETE."""
    store, run_id, ctx = test_env

    # Seed diagnosis and canonical note
    diag = Diagnosis(
        id="d_01",
        student_id="student_01",
        concept_id="c_photo",
        mastery_estimate=0.75,
        trend=TrendLabel.IMPROVING,
    )
    note = CanonicalNote(
        concept_id="c_photo",
        markdown="# Photosynthesis\nLight reactions in [[Thylakoid]].",
        extracted_concepts=[
            ConceptNode(id="c_thylakoid", name="Thylakoid", summary="Membrane site"),
        ],
        teacher_confirmed=True,
    )
    store.append(run_id, RecordKind.DIAGNOSIS.value, diag.model_dump(mode="json"), "agents")
    store.append(run_id, RecordKind.CANONICAL_NOTE.value, note.model_dump(mode="json"), "curriculum")

    # Step 1: handle_analysing -> transitions to AGGREGATING
    next_state = handle_analysing(ctx)
    assert next_state is RunState.AGGREGATING
    analysis = ctx.latest(RecordKind.ANALYSIS.value)
    assert analysis is not None
    assert analysis["student_id"] == "student_01"
    assert analysis["mastery_estimate"] == 0.75

    # Step 2: handle_aggregating -> transitions to COMPLETE
    next_state = handle_aggregating(ctx)
    assert next_state is RunState.COMPLETE
    class_rec = ctx.latest(RecordKind.CLASS_ANALYTICS.value)
    assert class_rec is not None
    assert class_rec["concept_id"] == "c_photo"
    assert class_rec["student_count"] == 1

    graph_rec = ctx.latest(RecordKind.CONCEPT_GRAPH.value)
    assert graph_rec is not None
    assert len(graph_rec["nodes"]) >= 1


def test_analytics_no_forbidden_imports():
    """Verify Person 4 analytics domain does not import agents, curriculum, runtime, api, web."""
    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("synapse.analytics"):
            mod = sys.modules[mod_name]
            code = getattr(mod, "__file__", "")
            if code and code.endswith(".py"):
                with open(code, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "synapse.curriculum" not in content
                    assert "synapse.agents" not in content
                    assert "synapse.runtime" not in content
                    assert "import api" not in content
                    assert "import web" not in content
                    assert "import frontend" not in content
