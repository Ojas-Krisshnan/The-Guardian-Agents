"""
Note candidate reviewer agent.
Authoritative contract: Contracts.md Sections C.2, C.3, D.2, D.4.
"""
from __future__ import annotations

import re
from typing import Optional
from pydantic import BaseModel, Field

from slice.budget import Budget
from slice.config import Settings
from slice.llm import complete
from slice.records import new_id
from synapse.schemas import (
    CanonicalNote,
    Diagnosis,
    NoteVersion,
    ReviewResult,
    ReviewStatus,
)
from synapse.state_machine import resolve_review_status


class ModelReviewOutput(BaseModel):
    canonical_coverage: bool
    diagnosis_addressed: bool
    links_valid: bool
    objections: list[str] = Field(default_factory=list)


def _deterministic_review(
    canonical_note: CanonicalNote,
    candidate: NoteVersion,
    diagnosis: Diagnosis,
    existing_concept_names: Optional[set[str]] = None,
    revisions_so_far: int = 0,
) -> ReviewResult:
    """Deterministic review verification against canonical content, diagnosis, and link integrity."""
    objections: list[str] = []

    # 1. Canonical coverage
    # Ensure note mentions either canonical concepts or substantial content from canonical note
    canonical_coverage = True
    if canonical_note.extracted_concepts:
        found_any = any(
            c.name.lower() in candidate.markdown.lower()
            for c in canonical_note.extracted_concepts
        )
        if not found_any and len(candidate.markdown) < 100:
            canonical_coverage = False
            objections.append("Missing coverage of key canonical concepts.")
    elif len(candidate.markdown.strip()) < 50:
        canonical_coverage = False
        objections.append("Candidate note content is too sparse.")

    # 2. Diagnosis addressed
    # If there were conceptual gap items, ensure some focus/explanation is included
    diagnosis_addressed = True
    if diagnosis.items:
        gap_count = sum(1 for item in diagnosis.items)
        if gap_count > 0 and "diagnosis" not in candidate.markdown.lower() and "focus" not in candidate.markdown.lower() and "review" not in candidate.markdown.lower():
            diagnosis_addressed = False
            objections.append("Candidate does not explicitly address diagnosed gaps.")

    # 3. Links valid
    # Extract wiki-links [[Concept]] and verify against existing concept names or canonical concepts
    known_names = {k.lower() for k in (existing_concept_names or set())}
    if canonical_note.extracted_concepts:
        known_names.update(c.name.lower() for c in canonical_note.extracted_concepts)
    known_names.add(canonical_note.concept_id.lower())
    known_names.add(diagnosis.concept_id.lower())

    # Extract concept names from canonical markdown headers e.g. # Photosynthesis
    for line in canonical_note.markdown.splitlines():
        if line.startswith("#"):
            hdr = line.lstrip("#").strip().lower()
            if hdr:
                known_names.add(hdr)

    wiki_links = re.findall(r'\[\[(.*?)\]\]', candidate.markdown)
    links_valid = True
    for link in wiki_links:
        clean_link = link.strip().lower()
        # Allow self/canonical/extracted names
        if clean_link and not any(k == clean_link or clean_link in k or k in clean_link for k in known_names):
            links_valid = False
            objections.append(f"Invalid or unresolved concept link: [[{link}]].")

    passed = canonical_coverage and diagnosis_addressed and links_valid and (len(objections) == 0)
    status = resolve_review_status(passed=passed, revisions_so_far=revisions_so_far)

    return ReviewResult(
        id=new_id(),
        passed=passed,
        canonical_coverage=canonical_coverage,
        diagnosis_addressed=diagnosis_addressed,
        links_valid=links_valid,
        objections=objections,
        status=status,
    )


def review(
    canonical_note: CanonicalNote,
    candidate: NoteVersion,
    diagnosis: Diagnosis,
    existing_concept_names: Optional[set[str]] = None,
    revisions_so_far: int = 0,
    settings: Optional[Settings] = None,
    budget: Optional[Budget] = None,
) -> ReviewResult:
    """Evaluate note candidate and produce ReviewResult according to contract rules."""
    if settings and budget and settings.api_key:
        try:
            diag_text = "\n".join(f"- {i.reason}" for i in diagnosis.items)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an educational content reviewer. Evaluate this candidate study note against: "
                        "1) canonical_coverage (does it accurately cover the canonical source?), "
                        "2) diagnosis_addressed (does it address the student's weaknesses?), "
                        "3) links_valid (are referenced links appropriate?), "
                        "and list any concrete objections if not passing."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Canonical Source:\n{canonical_note.markdown}\n\n"
                        f"Student Diagnosed Issues:\n{diag_text}\n\n"
                        f"Candidate Note to Review:\n{candidate.markdown}"
                    ),
                },
            ]
            result = complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=ModelReviewOutput,
                step="agents:review",
            )
            if isinstance(result, ModelReviewOutput):
                passed = (
                    result.canonical_coverage
                    and result.diagnosis_addressed
                    and result.links_valid
                    and len(result.objections) == 0
                )
                status = resolve_review_status(passed=passed, revisions_so_far=revisions_so_far)
                return ReviewResult(
                    id=new_id(),
                    passed=passed,
                    canonical_coverage=result.canonical_coverage,
                    diagnosis_addressed=result.diagnosis_addressed,
                    links_valid=result.links_valid,
                    objections=result.objections,
                    status=status,
                )
        except Exception:
            pass

    return _deterministic_review(
        canonical_note,
        candidate,
        diagnosis,
        existing_concept_names,
        revisions_so_far,
    )
