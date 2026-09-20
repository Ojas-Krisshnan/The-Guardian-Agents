# synapse/curriculum/stub.py
"""Deterministic stubs and fixtures for curriculum agent testing."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from synapse.schemas import ConceptNode, Test, TestQuestion


class ExtractedConceptsResult(BaseModel):
    concepts: list[ConceptNode] = Field(default_factory=list)


def stub_extract_concepts(markdown: str, concept_name: str = "Recursion") -> list[ConceptNode]:
    """Deterministic concept extraction from markdown for testing."""
    c1 = ConceptNode(
        name=concept_name,
        summary=f"Core principles and definitions of {concept_name}.",
        prerequisites=[],
    )
    c2 = ConceptNode(
        name=f"{concept_name} Base Case",
        summary=f"The terminating condition that halts execution in {concept_name}.",
        prerequisites=[c1.id],
    )
    c3 = ConceptNode(
        name=f"{concept_name} Recursive Step",
        summary=f"The inductive step reducing problem size in {concept_name}.",
        prerequisites=[c1.id],
    )
    return [c1, c2, c3]


def stub_generate_test(concept_id: str, concept_name: str = "Recursion") -> Test:
    """Deterministic 3-question MCQ test for testing."""
    q1 = TestQuestion(
        concept_id=concept_id,
        text=f"What is the primary role of a base case in {concept_name}?",
        options=[
            "To terminate recursion and avoid infinite loops",
            "To double execution speed",
            "To allocate additional heap memory",
            "To replace iterative loops entirely",
        ],
        correct_answer="To terminate recursion and avoid infinite loops",
    )
    q2 = TestQuestion(
        concept_id=concept_id,
        text=f"What happens if a recursive function lacks a valid base case?",
        options=[
            "Stack overflow or maximum recursion depth exceeded",
            "Syntax error at compile time",
            "Silent automatic termination",
            "Function returns null immediately",
        ],
        correct_answer="Stack overflow or maximum recursion depth exceeded",
    )
    q3 = TestQuestion(
        concept_id=concept_id,
        text=f"In a divide-and-conquer algorithm using {concept_name}, what does the recursive step do?",
        options=[
            "Breaks problem into smaller subproblems and calls itself",
            "Sorts all memory addresses",
            "Re-initializes global state",
            "Converts the function to machine code",
        ],
        correct_answer="Breaks problem into smaller subproblems and calls itself",
    )
    return Test(
        concept_id=concept_id,
        concept_name=concept_name,
        questions=[q1, q2, q3],
    )
