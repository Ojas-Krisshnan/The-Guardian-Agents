# synapse/runtime/stub.py
"""Deterministic runtime stubs and mock helpers."""
from __future__ import annotations

from typing import Any
from slice.store import Store
from synapse.schemas import Attempt, CanonicalNote, ConceptNode, RunScope, Test, utcnow


def seed_test_run(
    store: Store,
    teacher_id: str = "teacher_1",
    concept_name: str = "Recursion",
    markdown: str = "# Recursion\nCore recursion concepts.",
) -> tuple[str, str, str]:
    """Helper to seed a run up to test_ready, returning (run_id, concept_id, test_id)."""
    concept_node = ConceptNode(name=concept_name, summary=f"Basics of {concept_name}")
    canonical = CanonicalNote(
        concept_id=concept_node.id,
        markdown=markdown,
        extracted_concepts=[concept_node],
        teacher_confirmed=True,
        confirmed_at=utcnow(),
    )
    from synapse.curriculum.stub import stub_generate_test
    test = stub_generate_test(concept_node.id, concept_name)

    scope = RunScope(
        concept_id=concept_node.id,
        concept_name=concept_name,
        teacher_id=teacher_id,
        cycle=1,
    )
    from synapse.state_machine import RunState
    run_id = store.create_run("synapse", scope.model_dump(mode="json"))
    store.set_state(run_id, RunState.AWAITING_STUDENT)

    from synapse.schemas import RecordKind
    store.append(run_id, RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="teacher")
    store.append(run_id, RecordKind.TEST, test.model_dump(mode="json"), produced_by="curriculum")

    return run_id, concept_node.id, test.id
