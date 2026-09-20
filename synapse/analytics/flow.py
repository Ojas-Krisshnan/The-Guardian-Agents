# synapse/analytics/flow.py
"""State machine flow handlers for Person 4 (analysing, aggregating).

Follows slice Context / Flow protocol:
- A handler reads records through `ctx`, writes results with `ctx.append(kind, payload)`,
  and returns the next RunState.
- Pure logic; no model calls or external network dependencies.
"""
from __future__ import annotations

from typing import Any

from synapse.analytics.aggregation import aggregate
from synapse.analytics.graph import build_student_graph
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend
from synapse.schemas import (
    AnalysisPayload,
    ConceptGraph,
    ConceptNode,
    Diagnosis,
    NoteVersion,
    RecordKind,
    TrendLabel,
)
from synapse.state_machine import RunState


async def handle_analysing(ctx: Any) -> RunState:
    """Handler for the 'analysing' state.

    1. Reads the latest Diagnosis record.
    2. Calculates mastery score using deterministic domain heuristic.
    3. Calculates trend label comparing against previous cycle history.
    4. Appends AnalysisPayload record to run context.
    5. Transitions to AGGREGATING state.
    """
    diagnosis: Diagnosis | None = getattr(ctx, "get_latest", lambda k: None)(RecordKind.DIAGNOSIS)
    if diagnosis is None:
        # Check dictionary-style or fallback lookup
        if hasattr(ctx, "records"):
            for r in reversed(ctx.records):
                if getattr(r, "kind", None) == RecordKind.DIAGNOSIS or getattr(r, "kind", None) == "diagnosis":
                    diagnosis = r.payload
                    break

    scope = getattr(ctx, "scope", {})
    concept_id = scope.get("concept_id", diagnosis.concept_id if diagnosis else "unknown")
    student_id = scope.get("student_id", diagnosis.student_id if diagnosis else "unknown")
    cycle_number = int(scope.get("cycle", 1))

    # Calculate mastery
    if diagnosis is not None:
        mastery = calculate_mastery(diagnosis)
    else:
        mastery = 0.5

    # Retrieve cycle history if present on student history or scope
    history: list[tuple[int, float]] = scope.get("mastery_history", [])
    trend: TrendLabel = calculate_trend(mastery, history)

    analysis_payload = AnalysisPayload(
        student_id=student_id,
        concept_id=concept_id,
        mastery_estimate=mastery,
        trend=trend,
        cycle_number=cycle_number,
    )

    if hasattr(ctx, "append"):
        ctx.append(RecordKind.ANALYSIS, analysis_payload)

    return RunState.AGGREGATING


async def handle_aggregating(ctx: Any) -> RunState:
    """Handler for the 'aggregating' state.

    1. Collects analysis payloads for this concept.
    2. Calculates ClassAnalytics (average mastery, distribution, weak students).
    3. Builds updated ConceptGraph from notes and concepts.
    4. Appends ClassAnalytics and ConceptGraph records.
    5. Transitions to COMPLETE state.
    """
    scope = getattr(ctx, "scope", {})
    concept_id = scope.get("concept_id", "")
    student_id = scope.get("student_id", "")

    # Retrieve all AnalysisPayload records
    payloads: list[AnalysisPayload] = []
    if hasattr(ctx, "find_all"):
        payloads = ctx.find_all(RecordKind.ANALYSIS)
    elif hasattr(ctx, "records"):
        payloads = [
            r.payload
            for r in ctx.records
            if getattr(r, "kind", None) in (RecordKind.ANALYSIS, "analysis")
            and isinstance(getattr(r, "payload", None), AnalysisPayload)
        ]

    class_analytics = aggregate(payloads)
    if hasattr(ctx, "append"):
        ctx.append(RecordKind.CLASS_ANALYTICS, class_analytics)

    # Reconstruct student ConceptGraph if notes are available in ctx
    notes: list[NoteVersion] = []
    concepts: list[ConceptNode] = []
    if hasattr(ctx, "find_all"):
        notes = ctx.find_all(RecordKind.NOTE_VERSION)
        concepts = ctx.find_all(RecordKind.CANONICAL_NOTE)
    elif hasattr(ctx, "records"):
        notes = [
            r.payload
            for r in ctx.records
            if getattr(r, "kind", None) in (RecordKind.NOTE_VERSION, "note_version")
            and isinstance(getattr(r, "payload", None), NoteVersion)
        ]

    student_graph = build_student_graph(
        student_id=student_id,
        notes=notes,
        all_concepts=concepts,
    )
    if hasattr(ctx, "append"):
        ctx.append(RecordKind.CONCEPT_GRAPH, student_graph)

    return RunState.COMPLETE
