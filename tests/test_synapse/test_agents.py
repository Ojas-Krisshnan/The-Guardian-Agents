# tests/test_synapse/test_agents.py
import pytest
from slice.config import Settings
from slice.runner import Context
from slice.store import Store
from synapse.agents.flow import (
    diagnose,
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
    review_note,
    tailor_note,
)
from synapse.curriculum.stub import stub_generate_test
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    RecordKind,
    ReviewStatus,
    TrendLabel,
)
from synapse.state_machine import RunState


@pytest.fixture
def store():
    st = Store(":memory:")
    yield st
    st.close()


@pytest.fixture
def settings():
    return Settings(
        api_key="",
        model="dummy",
        fallback_model="dummy",
        escalation_model="dummy",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )


def test_diagnose_perfect_score():
    test = stub_generate_test("c1", "Recursion")
    answers = {q.id: q.correct_answer for q in test.questions}
    attempt = Attempt(
        student_id="student_1",
        test_id=test.id,
        concept_id="c1",
        answers=answers,
        score=3,
        total=3,
    )
    diag = diagnose(attempt, test)
    assert diag.mastery_estimate == 1.0
    assert len(diag.items) == 0


def test_diagnose_misconception():
    test = stub_generate_test("c1", "Recursion")
    # Answer first question wrong with performance confusion
    answers = {
        test.questions[0].id: "To double execution speed",
        test.questions[1].id: test.questions[1].correct_answer,
        test.questions[2].id: test.questions[2].correct_answer,
    }
    attempt = Attempt(
        student_id="student_1",
        test_id=test.id,
        concept_id="c1",
        answers=answers,
        score=2,
        total=3,
    )
    diag = diagnose(attempt, test)
    assert diag.mastery_estimate < 1.0
    assert len(diag.items) == 1
    assert diag.items[0].classification == MistakeClassification.CONCEPTUAL_GAP


def test_tailor_note_generation():
    diag = Diagnosis(
        student_id="s1",
        concept_id="c1",
        items=[
            DiagnosisItem(
                question_id="q1",
                classification=MistakeClassification.CONCEPTUAL_GAP,
                reason="Confused termination with performance",
            )
        ],
        mastery_estimate=0.75,
        trend=TrendLabel.NEW,
    )
    note = tailor_note("s1", "c1", diag, canonical_name="Recursion", existing_concepts=["Recursion"])
    assert "Mistake Pattern Table" in note.markdown
    assert "[[Recursion]]" in note.markdown
    assert note.version == 1


def test_review_note_passes_clean_note():
    diag = Diagnosis(
        student_id="s1",
        concept_id="c1",
        items=[],
        mastery_estimate=1.0,
        trend=TrendLabel.STABLE,
    )
    canonical = CanonicalNote(concept_id="c1", markdown="Recursion and base cases.")
    note = tailor_note("s1", "c1", diag, canonical_name="Recursion", existing_concepts=["Recursion"])
    res = review_note(note, diag, canonical, existing_concepts={"Recursion"})
    assert res.passed is True
    assert res.status == ReviewStatus.PASSED


def test_review_note_catches_invalid_links():
    diag = Diagnosis(
        student_id="s1",
        concept_id="c1",
        mastery_estimate=0.5,
        trend=TrendLabel.STABLE,
    )
    canonical = CanonicalNote(concept_id="c1", markdown="Recursion")
    bad_note = NoteVersion(
        student_id="s1",
        concept_id="c1",
        version=1,
        markdown="Here is a link to [[NonExistentConcept]] and base case.",
    )
    res = review_note(bad_note, diag, canonical, existing_concepts={"Recursion"})
    assert res.passed is False
    assert res.links_valid is False
    assert any("NonExistentConcept" in obj for obj in res.objections)


@pytest.mark.anyio
async def test_revision_loop_in_reviewing_state(store, settings):
    run_id = store.create_run("synapse", {"concept_id": "c1"})
    diag = Diagnosis(
        student_id="s1",
        concept_id="c1",
        mastery_estimate=0.5,
        trend=TrendLabel.STABLE,
    )
    store.append(run_id, RecordKind.DIAGNOSIS, diag.model_dump(mode="json"), produced_by="test")

    canonical = CanonicalNote(concept_id="c1", markdown="Recursion base case", extracted_concepts=[ConceptNode(name="Recursion", summary="s")])
    store.append(run_id, RecordKind.CANONICAL_NOTE, canonical.model_dump(mode="json"), produced_by="test")

    # Bad candidate missing base case
    bad_note = NoteVersion(student_id="s1", concept_id="c1", version=1, markdown="Invalid content with [[Fake]]")
    store.append(run_id, RecordKind.NOTE_CANDIDATE, bad_note.model_dump(mode="json"), produced_by="test")

    ctx = Context(store, run_id, settings)

    # First fail -> TAILORING
    s1 = await handle_reviewing(ctx)
    assert s1 == RunState.TAILORING

    # Second fail -> TAILORING
    s2 = await handle_reviewing(ctx)
    assert s2 == RunState.TAILORING

    # Third fail -> TAILORING
    s3 = await handle_reviewing(ctx)
    assert s3 == RunState.TAILORING

    # Fourth fail (revisions_so_far >= 3) -> NOTE_SAVED with REVISION_LIMIT_REACHED
    s4 = await handle_reviewing(ctx)
    assert s4 == RunState.NOTE_SAVED
    last_review = store.latest(run_id, RecordKind.REVIEW)
    assert last_review["status"] == ReviewStatus.REVISION_LIMIT_REACHED.value
