# synapse/agents/stub.py
"""Deterministic stubs for diagnosis, tailoring, and review agents."""
from __future__ import annotations

import re
from synapse.analytics.mastery import calculate_mastery
from synapse.analytics.trends import calculate_trend
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    ReviewResult,
    ReviewStatus,
    Test,
    TrendLabel,
)


def stub_diagnose(
    attempt: Attempt,
    test: Test | None = None,
    canonical: CanonicalNote | None = None,
) -> Diagnosis:
    """Deterministic diagnosis from attempt and test questions."""
    items: list[DiagnosisItem] = []

    if test is not None:
        for q in test.questions:
            student_ans = attempt.answers.get(q.id, "")
            if student_ans != q.correct_answer:
                # Classify mistake based on answer content
                if not student_ans:
                    classification = MistakeClassification.EMPTY
                    reason = f"No answer provided for question: '{q.text[:40]}'."
                elif "double" in student_ans.lower() or "replace" in student_ans.lower():
                    classification = MistakeClassification.CONCEPTUAL_GAP
                    reason = f"Confused base case termination with performance optimisation."
                elif "syntax" in student_ans.lower():
                    classification = MistakeClassification.CARELESS_MISTAKE
                    reason = f"Selected compile-time error instead of runtime call stack behavior."
                else:
                    classification = MistakeClassification.CONTRADICTORY
                    reason = f"Selected contradictory behavior for recursive execution."

                items.append(
                    DiagnosisItem(
                        question_id=q.id,
                        classification=classification,
                        reason=reason,
                    )
                )

    # Calculate mastery from items
    temp_diag = Diagnosis(
        student_id=attempt.student_id,
        concept_id=attempt.concept_id,
        items=items,
        mastery_estimate=1.0,
        trend=TrendLabel.NEW,
    )
    mastery = calculate_mastery(temp_diag)
    temp_diag.mastery_estimate = mastery
    return temp_diag


def stub_tailor_note(
    student_id: str,
    concept_id: str,
    diagnosis: Diagnosis,
    canonical_name: str = "Recursion",
    version: int = 1,
    existing_concepts: list[str] | None = None,
    objections: list[str] | None = None,
) -> NoteVersion:
    """Deterministic tailored markdown note with mistake pattern table and [[links]]."""
    link_target = existing_concepts[0] if existing_concepts else canonical_name

    table_rows = []
    if diagnosis.items:
        for idx, item in enumerate(diagnosis.items, start=1):
            table_rows.append(
                f"| Q{idx}: Problem {idx} | Selected Misconception | Correct Concept Idea | {item.classification.value}: {item.reason} |"
            )
    else:
        table_rows.append("| Q1: All questions | Perfect Answers | Flawless Execution | Fully mastered key concepts |")

    table_content = "\n".join(table_rows)

    markdown = f"""# {canonical_name} Study Guide (v{version})

Personalized study notes for {canonical_name}. Connects closely with [[{link_target}]].

## Key Concepts
{canonical_name} requires a base case to terminate and a recursive step that moves closer to termination.

## Mistake Pattern Table
| Question | Your Answer | Correct Idea | What Happened |
|---|---|---|---|
{table_content}

## Next Steps
Review the termination conditions and trace execution frames carefully.
"""
    return NoteVersion(
        student_id=student_id,
        concept_id=concept_id,
        version=version,
        markdown=markdown,
        diagnosis_id=diagnosis.id,
    )


def stub_review_note(
    note: NoteVersion,
    diagnosis: Diagnosis,
    canonical_note: CanonicalNote,
    existing_concepts: set[str] | None = None,
    revisions_so_far: int = 0,
    force_fail: bool = False,
) -> ReviewResult:
    """Deterministic review checking canonical coverage, diagnosis addressed, and valid links."""
    objections: list[str] = []

    # 1. Canonical coverage
    canonical_coverage = "base case" in note.markdown.lower() or "recursion" in note.markdown.lower()
    if not canonical_coverage:
        objections.append("Note does not cover core canonical base case concepts.")

    # 2. Diagnosis addressed
    diagnosis_addressed = True
    if diagnosis.items and "Mistake Pattern Table" not in note.markdown:
        diagnosis_addressed = False
        objections.append("Note lacks the required Mistake Pattern Table.")

    # 3. Links valid
    links = re.findall(r"\[\[([^\]]+)\]\]", note.markdown)
    links_valid = True
    if existing_concepts is not None and links:
        for link in links:
            if link not in existing_concepts:
                links_valid = False
                objections.append(f"Invalid concept link [[{link}]] does not exist in curriculum.")

    if force_fail:
        objections.append("Pedagogical quality check failed: clarity needs improvement.")

    passed = canonical_coverage and diagnosis_addressed and links_valid and not force_fail

    from synapse.state_machine import resolve_review_status
    status = resolve_review_status(passed, revisions_so_far)

    return ReviewResult(
        passed=passed,
        canonical_coverage=canonical_coverage,
        diagnosis_addressed=diagnosis_addressed,
        links_valid=links_valid,
        objections=objections,
        status=status,
    )
