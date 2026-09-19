"""
Flow handlers for Person 4 analytics domain: analysing, aggregating.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2.
"""
from __future__ import annotations

from slice.runner import Context
from synapse.analytics.aggregation import aggregate
from synapse.analytics.graph import parse_graph
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend
from synapse.schemas import (
    AnalysisPayload,
    CanonicalNote,
    ClassAnalytics,
    ConceptGraph,
    Diagnosis,
    RecordKind,
)
from synapse.state_machine import RunState


def handle_analysing(ctx: Context) -> RunState:
    """Calculate student mastery and trend, append analysis payload, transition to AGGREGATING."""
    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "default_concept")
    student_id = scope.get("student_id", "student_01")
    cycle = int(scope.get("cycle", 1))

    # Collect student diagnoses history
    diagnoses_records = ctx.history(RecordKind.DIAGNOSIS.value)
    diagnoses: list[Diagnosis] = []
    for r in diagnoses_records:
        payload = r.payload if hasattr(r, "payload") else r
        try:
            diagnoses.append(Diagnosis.model_validate(payload))
        except Exception:
            pass

    mastery = calculate_mastery(diagnoses, student_id=student_id, concept_id=concept_id)
    trend = calculate_trend(diagnoses)

    analysis_payload = AnalysisPayload(
        student_id=student_id,
        concept_id=concept_id,
        mastery_estimate=mastery,
        trend=trend,
        cycle_number=cycle,
    )

    ctx.append(
        RecordKind.ANALYSIS.value,
        analysis_payload.model_dump(mode="json"),
        produced_by="analytics:mastery_calculator",
    )

    return RunState.AGGREGATING


def handle_aggregating(ctx: Context) -> RunState:
    """Aggregate class-level analytics, parse and update concept graph, transition to COMPLETE."""
    scope = ctx.store.meta(ctx.run_id).get("scope", {})
    concept_id = scope.get("concept_id", "default_concept")
    concept_name = scope.get("concept_name", concept_id.replace("_", " ").title())

    # 1. Class-level aggregation
    diagnoses_records = ctx.history(RecordKind.DIAGNOSIS.value)
    diagnoses: list[Diagnosis] = []
    for r in diagnoses_records:
        payload = r.payload if hasattr(r, "payload") else r
        try:
            diagnoses.append(Diagnosis.model_validate(payload))
        except Exception:
            pass

    class_analytics = aggregate(diagnoses, concept_id=concept_id, concept_name=concept_name)
    ctx.append(
        RecordKind.CLASS_ANALYTICS.value,
        class_analytics.model_dump(mode="json"),
        produced_by="analytics:aggregator",
    )

    # 2. Concept Graph construction
    canonical_notes_history = ctx.history(RecordKind.CANONICAL_NOTE.value)
    canonical_notes: list[CanonicalNote] = []
    for r in canonical_notes_history:
        payload = r.payload if hasattr(r, "payload") else r
        try:
            canonical_notes.append(CanonicalNote.model_validate(payload))
        except Exception:
            pass

    concept_graph = parse_graph(canonical_notes)
    ctx.append(
        RecordKind.CONCEPT_GRAPH.value,
        concept_graph.model_dump(mode="json"),
        produced_by="analytics:graph_parser",
    )

    return RunState.COMPLETE
