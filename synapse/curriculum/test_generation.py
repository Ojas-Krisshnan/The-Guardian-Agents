"""
Test generation for concepts in curriculum domain.
Authoritative contract: Contracts.md Sections C.2, D.2, D.5.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from slice.budget import Budget
from slice.config import Settings
from slice.llm import complete
from slice.records import new_id
from synapse.schemas import ConceptNode, Test, TestQuestion


class GeneratedQuestionItem(BaseModel):
    text: str
    correct_answer: str
    options: list[str]
    concept_id: str | None = None


class GeneratedTestSchema(BaseModel):
    questions: list[GeneratedQuestionItem]


def _deterministic_generate_test(
    concept_id: str,
    concept_name: str,
    concepts: list[ConceptNode],
) -> Test:
    """Generate deterministic test questions with exactly 4 unique options."""
    questions: list[TestQuestion] = []
    
    target_concepts = concepts if concepts else [
        ConceptNode(id=concept_id, name=concept_name, summary=f"Fundamentals of {concept_name}")
    ]

    for i, c in enumerate(target_concepts, 1):
        correct = f"Primary function of {c.name}: {c.summary[:60]}"
        # Ensure 4 unique options
        opts = [
            correct,
            f"Incorrect: Reverses the primary mechanism of {c.name}",
            f"Incorrect: Inhibits normal operation of {c.name}",
            f"Incorrect: Unrelated cellular process detached from {c.name}",
        ]
        q = TestQuestion(
            id=new_id(),
            text=f"Which statement correctly describes the function of {c.name}?",
            correct_answer=correct,
            options=opts,
            concept_id=c.id,
        )
        questions.append(q)

    return Test(
        id=new_id(),
        concept_id=concept_id,
        concept_name=concept_name,
        questions=questions,
    )


def generate_test(
    concept_id: str,
    concept_name: str,
    concepts: list[ConceptNode],
    settings: Settings | None = None,
    budget: Budget | None = None,
) -> Test:
    """Generate a valid Test package with 4-option questions."""
    if not concepts:
        concepts = [
            ConceptNode(id=concept_id, name=concept_name, summary=f"Overview of {concept_name}")
        ]

    if settings and budget and settings.api_key:
        try:
            concept_summaries = "\n".join(f"- {c.name} (id={c.id}): {c.summary}" for c in concepts)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Generate a multiple-choice diagnostic test for the following concepts. "
                        "For every question, provide: text, correct_answer, and options (EXACTLY 4 unique options, "
                        "where correct_answer is one of the options), and concept_id matching the relevant concept."
                    ),
                },
                {"role": "user", "content": f"Topic: {concept_name}\n\nConcepts:\n{concept_summaries}"},
            ]
            result = complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=GeneratedTestSchema,
                step="curriculum:generate_test",
            )
            if isinstance(result, GeneratedTestSchema) and result.questions:
                validated_questions: list[TestQuestion] = []
                for q_item in result.questions:
                    cid = q_item.concept_id or concepts[0].id
                    # Ensure options has exactly 4 items and contains correct_answer
                    opts = list(dict.fromkeys(q_item.options))  # Deduplicate preserving order
                    if q_item.correct_answer not in opts:
                        opts[0] = q_item.correct_answer
                    while len(opts) < 4:
                        opts.append(f"Alternative choice {len(opts) + 1}")
                    opts = opts[:4]

                    validated_questions.append(
                        TestQuestion(
                            id=new_id(),
                            text=q_item.text,
                            correct_answer=q_item.correct_answer,
                            options=opts,
                            concept_id=cid,
                        )
                    )
                if validated_questions:
                    return Test(
                        id=new_id(),
                        concept_id=concept_id,
                        concept_name=concept_name,
                        questions=validated_questions,
                    )
        except Exception:
            pass

    return _deterministic_generate_test(concept_id, concept_name, concepts)
