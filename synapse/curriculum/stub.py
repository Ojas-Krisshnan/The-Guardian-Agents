"""
Deterministic test fixtures and stubs for curriculum domain.
Authoritative contract: Contracts.md Sections C.2, D.2, D.5.
"""
from __future__ import annotations

from slice.runner import Context
from slice.records import new_id
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState

SAMPLE_CONCEPTS = [
    ConceptNode(
        id="c_001",
        name="Light-dependent reactions",
        summary="Photosystem II and electron transport chain on thylakoid membranes",
        prerequisites=[],
    ),
    ConceptNode(
        id="c_002",
        name="Calvin cycle",
        summary="Carbon fixation catalyzed by RuBisCO producing G3P in chloroplast stroma",
        prerequisites=["Light-dependent reactions"],
    ),
]

SAMPLE_QUESTIONS = [
    TestQuestion(
        id="q_001",
        text="Where do light-dependent reactions occur?",
        correct_answer="Thylakoid membrane",
        options=[
            "Thylakoid membrane",
            "Chloroplast stroma",
            "Cytoplasm",
            "Outer mitochondrial membrane",
        ],
        concept_id="c_001",
    ),
    TestQuestion(
        id="q_002",
        text="Which enzyme catalyzes carbon fixation in the Calvin cycle?",
        correct_answer="RuBisCO",
        options=[
            "RuBisCO",
            "ATP synthase",
            "DNA polymerase",
            "Amylase",
        ],
        concept_id="c_002",
    ),
]

SAMPLE_TEST = Test(
    id="test_curriculum_fixture_01",
    concept_id="c_photosynthesis_01",
    concept_name="Photosynthesis",
    questions=SAMPLE_QUESTIONS,
)


def stub_extract_concepts(markdown: str = "", concept_name: str = "Photosynthesis") -> list[ConceptNode]:
    """Return deterministic sample concepts."""
    return [
        ConceptNode(
            id=f"c_{i+1:03d}",
            name=c.name,
            summary=c.summary,
            prerequisites=c.prerequisites,
        )
        for i, c in enumerate(SAMPLE_CONCEPTS)
    ]


def stub_generate_test(concept_id: str, concept_name: str, concepts: list[ConceptNode] | None = None) -> Test:
    """Return deterministic sample test."""
    return Test(
        id=new_id(),
        concept_id=concept_id,
        concept_name=concept_name,
        questions=[
            TestQuestion(
                id=new_id(),
                text=q.text,
                correct_answer=q.correct_answer,
                options=list(q.options),
                concept_id=concept_id,
            )
            for q in SAMPLE_QUESTIONS
        ],
    )
