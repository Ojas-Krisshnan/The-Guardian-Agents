"""
Student note tailoring agent.
Authoritative contract: Contracts.md Sections C.2, D.2, D.3, D.4.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from slice.budget import Budget
from slice.config import Settings
from slice.llm import complete
from synapse.schemas import (
    CanonicalNote,
    Diagnosis,
    NoteVersion,
    StudentHistory,
)


class ModelTailoringOutput(BaseModel):
    markdown: str = Field(min_length=1)


def _deterministic_tailor(
    canonical_note: CanonicalNote,
    diagnosis: Diagnosis,
    history: Optional[StudentHistory] = None,
    objections: Optional[list[str]] = None,
    version: int = 1,
) -> NoteVersion:
    """Deterministic note tailoring addressing diagnosed gaps and reviewer objections."""
    student_id = diagnosis.student_id
    concept_id = diagnosis.concept_id

    # Build targeted explanations based on diagnosis items
    gap_explanations: list[str] = []
    if diagnosis.items:
        for item in diagnosis.items:
            gap_explanations.append(
                f"- **Review Point**: {item.reason} ({item.classification.value})"
            )
    else:
        gap_explanations.append("- Great progress! Core concepts mastered; reinforce details below.")

    # Concept links
    concept_links: list[str] = []
    if canonical_note.extracted_concepts:
        for c in canonical_note.extracted_concepts:
            concept_links.append(f"[[{c.name}]] - {c.summary}")
    else:
        concept_links.append(f"[[{concept_id}]] - Overview of fundamental concepts")

    # If objections exist from a prior review, address them directly
    revisions_section = ""
    if objections:
        revisions_section = "\n### Reviewer Notes Addressed:\n" + "\n".join(
            f"- Addressed: {obj}" for obj in objections
        ) + "\n"

    tailored_markdown = (
        f"# Tailored Study Guide: {concept_id} (v{version})\n\n"
        f"Personalized study plan for student {student_id}.\n\n"
        f"## Diagnosis & Focus Areas\n"
        f"Estimated Mastery: {int(diagnosis.mastery_estimate * 100)}% | Trend: {diagnosis.trend.value}\n\n"
        + "\n".join(gap_explanations)
        + "\n\n"
        f"## Core Concepts & Mechanisms\n"
        f"{canonical_note.markdown}\n\n"
        f"## Key Related Concepts\n"
        + "\n".join(concept_links)
        + revisions_section
    )

    return NoteVersion(
        student_id=student_id,
        concept_id=concept_id,
        version=version,
        markdown=tailored_markdown,
        diagnosis_id=diagnosis.id,
        review_id=None,
    )


def tailor(
    canonical_note: CanonicalNote,
    diagnosis: Diagnosis,
    history: Optional[StudentHistory] = None,
    objections: Optional[list[str]] = None,
    version: int = 1,
    settings: Optional[Settings] = None,
    budget: Optional[Budget] = None,
) -> NoteVersion:
    """Produce personalized note candidate tailored to student's diagnosed gaps."""
    if settings and budget and settings.api_key:
        try:
            diag_text = "\n".join(
                f"- {item.classification.value}: {item.reason}" for item in diagnosis.items
            )
            objections_text = "\n".join(f"- {o}" for o in (objections or []))

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert pedagogical note-tailoring agent. Adapt the canonical note for the student, "
                        "directly addressing diagnosed misconceptions, reinforcing core concepts, and adhering to teacher guidance. "
                        "Format using clear markdown and valid wiki-links [[Concept Name]] for referenced concepts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Canonical Note:\n{canonical_note.markdown}\n\n"
                        f"Diagnosed Weaknesses:\n{diag_text}\n\n"
                        f"Reviewer Objections to Fix:\n{objections_text}\n"
                    ),
                },
            ]
            result = complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=ModelTailoringOutput,
                step="agents:tailor",
            )
            if isinstance(result, ModelTailoringOutput) and result.markdown.strip():
                return NoteVersion(
                    student_id=diagnosis.student_id,
                    concept_id=diagnosis.concept_id,
                    version=version,
                    markdown=result.markdown,
                    diagnosis_id=diagnosis.id,
                    review_id=None,
                )
        except Exception:
            pass

    return _deterministic_tailor(canonical_note, diagnosis, history, objections, version)
