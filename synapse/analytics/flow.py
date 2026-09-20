# synapse/analytics/flow.py
"""State machine flow handlers for Person 4 (analysing, aggregating).

Follows slice Context / Flow protocol:
- A handler reads records through `ctx`, writes results with `ctx.append(kind, payload, produced_by)`,
  and returns the next RunState.
- Pure logic; no model calls or external network dependencies.
"""
from __future__ import annotations

import inspect
from typing import Any

from synapse.analytics.aggregation import aggregate
from synapse.analytics.graph import build_student_graph
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend
from synapse.schemas import (
    AnalysisPayload,
    CanonicalNote,
    ConceptGraph,
    ConceptNode,
    Diagnosis,
    NoteVersion,
    RecordKind,
    TrendLabel,
)
from synapse.state_machine import RunState


def _safe_append(ctx: Any, kind: Any, payload: Any, produced_by: str = "analytics"):
    if hasattr(ctx, "append"):
        sig = inspect.signature(ctx.append)
        if len(sig.parameters) >= 3:
            data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
            ctx.append(kind, data, produced_by)
        else:
            ctx.append(kind, payload)


async def handle_analysing(ctx: Any) -> RunState:
    """Handler for the 'analysing' state.

    1. Reads the latest Diagnosis record.
    2. Calculates mastery score using deterministic domain heuristic.
    3. Calculates trend label comparing against previous cycle history.
    4. Appends AnalysisPayload record to run context.
    5. Transitions to AGGREGATING state.
    """
    diag_data = None
    if hasattr(ctx, "latest"):
        diag_data = ctx.latest(RecordKind.DIAGNOSIS)
    if diag_data is None and hasattr(ctx, "get_latest"):
        diag_data = ctx.get_latest(RecordKind.DIAGNOSIS)
    if diag_data is None and hasattr(ctx, "records"):
        for r in reversed(ctx.records):
            if getattr(r, "kind", None) in (RecordKind.DIAGNOSIS, "diagnosis"):
                diag_data = getattr(r, "payload", None)
                break

    diagnosis: Diagnosis | None = None
    if isinstance(diag_data, Diagnosis):
        diagnosis = diag_data
    elif isinstance(diag_data, dict):
        diagnosis = Diagnosis.model_validate(diag_data)

    scope = getattr(ctx, "scope", {})
    if hasattr(ctx, "store"):
        try:
            run_meta = ctx.store.get_run(ctx.run_id)
            if "scope" in run_meta:
                scope = run_meta["scope"]
        except Exception:
            pass

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

    _safe_append(ctx, RecordKind.ANALYSIS, analysis_payload, produced_by="analytics:analysing")
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
    if hasattr(ctx, "store"):
        try:
            run_meta = ctx.store.get_run(ctx.run_id)
            if "scope" in run_meta:
                scope = run_meta["scope"]
        except Exception:
            pass

    concept_id = scope.get("concept_id", "")
    student_id = scope.get("student_id", "")

    # Retrieve all AnalysisPayload records
    payloads: list[AnalysisPayload] = []
    if hasattr(ctx, "history"):
        hist = ctx.history(RecordKind.ANALYSIS)
        for h in hist:
            p = getattr(h, "payload", None)
            if isinstance(p, AnalysisPayload):
                payloads.append(p)
            elif isinstance(p, dict):
                payloads.append(AnalysisPayload.model_validate(p))
    elif hasattr(ctx, "find_all"):
        for p in ctx.find_all(RecordKind.ANALYSIS):
            payloads.append(p if isinstance(p, AnalysisPayload) else AnalysisPayload.model_validate(p))
    elif hasattr(ctx, "records"):
        for r in ctx.records:
            if getattr(r, "kind", None) in (RecordKind.ANALYSIS, "analysis"):
                p = getattr(r, "payload", None)
                if isinstance(p, AnalysisPayload):
                    payloads.append(p)
                elif isinstance(p, dict):
                    payloads.append(AnalysisPayload.model_validate(p))

    class_analytics = aggregate(payloads)
    _safe_append(ctx, RecordKind.CLASS_ANALYTICS, class_analytics, produced_by="analytics:aggregating")

    # Reconstruct student ConceptGraph if notes are available in ctx
    notes: list[NoteVersion] = []
    concepts: list[ConceptNode] = []

    if hasattr(ctx, "history"):
        for h in ctx.history(RecordKind.NOTE_VERSION):
            p = getattr(h, "payload", None)
            if isinstance(p, NoteVersion):
                notes.append(p)
            elif isinstance(p, dict):
                notes.append(NoteVersion.model_validate(p))

        for h in ctx.history(RecordKind.CANONICAL_NOTE):
            p = getattr(h, "payload", None)
            if isinstance(p, CanonicalNote) and p.extracted_concepts:
                concepts.extend(p.extracted_concepts)
            elif isinstance(p, dict) and "extracted_concepts" in p:
                concepts.extend([ConceptNode.model_validate(c) for c in p["extracted_concepts"]])
    elif hasattr(ctx, "records"):
        for r in ctx.records:
            k = getattr(r, "kind", None)
            p = getattr(r, "payload", None)
            if k in (RecordKind.NOTE_VERSION, "note_version"):
                notes.append(p if isinstance(p, NoteVersion) else NoteVersion.model_validate(p))
            elif k in (RecordKind.CANONICAL_NOTE, "canonical_note"):
                note_obj = p if isinstance(p, CanonicalNote) else CanonicalNote.model_validate(p)
                concepts.extend(note_obj.extracted_concepts)

    student_graph = build_student_graph(
        student_id=student_id,
        notes=notes,
        all_concepts=concepts,
    )
    _safe_append(ctx, RecordKind.CONCEPT_GRAPH, student_graph, produced_by="analytics:graph")

    return RunState.COMPLETE
