"""
Tests for Person 2 agents domain: diagnosis, tailoring, review.
Authoritative contract: Contracts.md Sections A.5, C.2, C.3, D.2, D.4.
"""
import pytest

from slice.config import Settings
from slice.records import RunState as SliceRunState
from slice.runner import Context
from slice.store import Store
from synapse.agents import (
    diagnose,
    handle_diagnosing,
    handle_reviewing,
    handle_tailoring,
    review,
    stub_diagnose,
    stub_review,
    stub_tailor,
    tailor,
)
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    RecordKind,
    ReviewResult,
    ReviewStatus,
    StudentHistory,
    Test,
    TestQuestion,
    TrendLabel,
)
from synapse.state_machine import RunState


@pytest.fixture
def test_env(tmp_path):
    store = Store(tmp_path / "agents_test.db")
    settings = Settings(
        api_key="test",
        model="test-model",
        fallback_model="test-fallback",
        escalation_model="test-esc",
        max_tokens=100,
        max_tokens_per_run=1000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    run_id = store.create_run(
        domain="synapse",
        meta={"scope": {"concept_id": "c_photo", "student_id": "student_01", "cycle": 1}},
        initial_state=RunState.DIAGNOSING,
    )
    ctx = Context(store, run_id, settings)
    return store, run_id, ctx


@pytest.fixture
def sample_test_and_attempt():
    questions = [
        TestQuestion(
            id="q1",
            text="Where do light reactions take place?",
            correct_answer="Thylakoid membrane",
            options=["Thylakoid membrane", "Stroma", "Mitochondria", "Cytoplasm"],
            concept_id="c_photo",
        ),
        TestQuestion(
            id="q2",
            text="What is the primary byproduct of light reactions?",
            correct_answer="Oxygen",
            options=["Oxygen", "Carbon Dioxide", "Glucose", "Methane"],
            concept_id="c_photo",
        ),
    ]
    test = Test(
        id="test_01",
        concept_id="c_photo",
        concept_name="Photosynthesis",
        questions=questions,
    )
    attempt = Attempt(
        student_id="student_01",
        test_id="test_01",
        concept_id="c_photo",
        answers={"q1": "Stroma", "q2": "Oxygen"},  # 1 wrong, 1 correct
        score=1,
        total=2,
    )
    canonical_note = CanonicalNote(
        concept_id="c_photo",
        markdown="# Photosynthesis\nLight reactions occur in the [[Thylakoid]] membrane. Dark reactions occur in [[Stroma]].",
        extracted_concepts=[
            ConceptNode(id="c_thylakoid", name="Thylakoid", summary="Site of light-dependent reactions"),
            ConceptNode(id="c_stroma", name="Stroma", summary="Fluid where Calvin cycle takes place"),
        ],
        teacher_confirmed=True,
    )
    return test, attempt, canonical_note


def test_diagnose_shape_and_logic(sample_test_and_attempt):
    """Verify diagnose identifies mistakes, computes mastery estimate, and determines trend."""
    test, attempt, canonical_note = sample_test_and_attempt
    diag = diagnose(attempt=attempt, test=test, canonical_note=canonical_note)

    assert isinstance(diag, Diagnosis)
    assert diag.student_id == "student_01"
    assert diag.concept_id == "c_photo"
    assert diag.mastery_estimate == 0.5  # 1 out of 2 correct
    assert len(diag.items) == 1
    item = diag.items[0]
    assert item.question_id == "q1"
    assert item.classification == MistakeClassification.CONCEPTUAL_GAP
    assert "Stroma" in item.reason


def test_tailor_shape_and_content(sample_test_and_attempt):
    """Verify tailor produces candidate NoteVersion addressing diagnosis and incorporating concepts."""
    test, attempt, canonical_note = sample_test_and_attempt
    diag = diagnose(attempt=attempt, test=test, canonical_note=canonical_note)
    candidate = tailor(canonical_note=canonical_note, diagnosis=diag, version=1)

    assert isinstance(candidate, NoteVersion)
    assert candidate.student_id == "student_01"
    assert candidate.concept_id == "c_photo"
    assert candidate.version == 1
    assert candidate.diagnosis_id == diag.id
    assert "Diagnosis & Focus Areas" in candidate.markdown
    assert "[[Thylakoid]]" in candidate.markdown


def test_review_happy_path(sample_test_and_attempt):
    """Verify reviewer passes candidate with valid links and canonical coverage."""
    test, attempt, canonical_note = sample_test_and_attempt
    diag = diagnose(attempt=attempt, test=test, canonical_note=canonical_note)
    candidate = tailor(canonical_note=canonical_note, diagnosis=diag, version=1)

    rev = review(canonical_note=canonical_note, candidate=candidate, diagnosis=diag, revisions_so_far=0)
    assert isinstance(rev, ReviewResult)
    assert rev.passed is True
    assert rev.canonical_coverage is True
    assert rev.diagnosis_addressed is True
    assert rev.links_valid is True
    assert len(rev.objections) == 0
    assert rev.status == ReviewStatus.PASSED


def test_review_failure_on_invalid_links(sample_test_and_attempt):
    """Verify reviewer fails candidate when invalid wiki-links are introduced."""
    test, attempt, canonical_note = sample_test_and_attempt
    diag = diagnose(attempt=attempt, test=test, canonical_note=canonical_note)
    # Candidate with unreferenced bogus link
    bad_candidate = NoteVersion(
        student_id="student_01",
        concept_id="c_photo",
        version=1,
        markdown="# Notes\nOverview of [[Photosynthesis]]. Check [[NonExistentConceptXYZ123]] for more.",
        diagnosis_id=diag.id,
    )

    rev = review(canonical_note=canonical_note, candidate=bad_candidate, diagnosis=diag, revisions_so_far=0)
    assert rev.passed is False
    assert rev.links_valid is False
    assert rev.status == ReviewStatus.FAILED
    assert any("NonExistentConceptXYZ123" in obj for obj in rev.objections)


def test_review_revision_loop_and_limit(sample_test_and_attempt):
    """Verify failed review transitions to TAILORING for revisions < 3 and NOTE_SAVED at revision limit."""
    test, attempt, canonical_note = sample_test_and_attempt
    diag = diagnose(attempt=attempt, test=test, canonical_note=canonical_note)
    bad_candidate = NoteVersion(
        student_id="student_01",
        concept_id="c_photo",
        version=1,
        markdown="# Bad Note without focus or coverage",
        diagnosis_id=diag.id,
    )

    # Revision 0, 1, 2 should yield FAILED
    rev0 = review(canonical_note=canonical_note, candidate=bad_candidate, diagnosis=diag, revisions_so_far=0)
    assert rev0.status == ReviewStatus.FAILED

    rev1 = review(canonical_note=canonical_note, candidate=bad_candidate, diagnosis=diag, revisions_so_far=1)
    assert rev1.status == ReviewStatus.FAILED

    rev2 = review(canonical_note=canonical_note, candidate=bad_candidate, diagnosis=diag, revisions_so_far=2)
    assert rev2.status == ReviewStatus.FAILED

    # Revision 3 (at limit) must yield REVISION_LIMIT_REACHED
    rev3 = review(canonical_note=canonical_note, candidate=bad_candidate, diagnosis=diag, revisions_so_far=3)
    assert rev3.status == ReviewStatus.REVISION_LIMIT_REACHED


def test_handle_diagnosing_tailoring_reviewing_flow(test_env, sample_test_and_attempt):
    """Verify runtime flow handlers for DIAGNOSING -> TAILORING -> REVIEWING -> NOTE_SAVED."""
    store, run_id, ctx = test_env
    test, attempt, canonical_note = sample_test_and_attempt

    # Seed required records
    store.append(run_id, RecordKind.CANONICAL_NOTE.value, canonical_note.model_dump(mode="json"), "teacher")
    store.append(run_id, RecordKind.TEST.value, test.model_dump(mode="json"), "curriculum")
    store.append(run_id, RecordKind.ATTEMPT.value, attempt.model_dump(mode="json"), "student")

    # Step 1: handle_diagnosing -> transitions to TAILORING
    next_state = handle_diagnosing(ctx)
    assert next_state is RunState.TAILORING
    diag_record = ctx.latest(RecordKind.DIAGNOSIS.value)
    assert diag_record is not None
    assert diag_record["student_id"] == "student_01"

    # Step 2: handle_tailoring -> transitions to REVIEWING
    next_state = handle_tailoring(ctx)
    assert next_state is RunState.REVIEWING
    candidate_record = ctx.latest(RecordKind.NOTE_CANDIDATE.value)
    assert candidate_record is not None
    assert candidate_record["diagnosis_id"] == diag_record["id"]

    # Step 3: handle_reviewing -> transitions to NOTE_SAVED on pass
    next_state = handle_reviewing(ctx)
    assert next_state is RunState.NOTE_SAVED
    review_record = ctx.latest(RecordKind.REVIEW.value)
    assert review_record is not None
    assert review_record["passed"] is True
    assert review_record["status"] == ReviewStatus.PASSED.value


def test_agents_no_forbidden_imports():
    """Verify Person 2 agents domain imports neither sibling domains nor runtime/web/api."""
    import sys
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("synapse.agents"):
            mod = sys.modules[mod_name]
            code = getattr(mod, "__file__", "")
            if code and code.endswith(".py"):
                with open(code, "r", encoding="utf-8") as f:
                    content = f.read()
                    assert "synapse.curriculum" not in content
                    assert "synapse.analytics" not in content
                    assert "synapse.runtime" not in content
                    assert "import api" not in content
                    assert "import web" not in content
                    assert "import frontend" not in content
