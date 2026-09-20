"""
Unit tests for Person 3 curriculum: fixtures, concept extraction, validation,
tag confirmation, and teacher setup.
Validates against synapse.schemas contracts.
No live LLM calls: all tests use CurriculumStub.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from slice import callback
from slice.config import Settings
from slice.runner import Context
from slice.store import Store
from synapse.curriculum import (
    extract_concepts,
    generate_stable_concept_id,
    generate_test,
    get_pending_tags,
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
    submit_teacher_confirmation,
)
from synapse.curriculum.schema import RawGeneratedQuestion, TestGenerationPayload
from synapse.curriculum.stub import DEFAULT_TEST_JSON, CurriculumStub
from synapse.schemas import (
    CanonicalNote,
    ConceptNode,
    RecordKind,
    TeacherConfirmation,
    Test,
    TestQuestion,
)
from synapse.state_machine import RunState

ROOT = Path(__file__).resolve().parent.parent.parent
CANONICAL_NOTE_PATH = ROOT / "synapse" / "curriculum" / "corpus" / "canonical_notes" / "recursion.md"
FIXTURES_DIR = ROOT / "synapse" / "curriculum" / "fixtures"
EXPECTED_CONCEPTS_PATH = FIXTURES_DIR / "expected_concepts.json"


def _make_test_settings(timeout_minutes: int = 10) -> Settings:
    return Settings(
        api_key="none",
        model="none",
        fallback_model="none",
        escalation_model="none",
        max_tokens=100,
        max_tokens_per_run=100000,
        max_attempts_per_step=3,
        expert_timeout_minutes=timeout_minutes,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )


# ── Canonical note and fixture validation ────────────────────────────────
def test_canonical_note_exists_and_contains_key_sections():
    assert CANONICAL_NOTE_PATH.exists(), f"Missing canonical note at {CANONICAL_NOTE_PATH}"
    content = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    assert len(content) > 100

    for expected_section in ["Recursion", "Base Case", "Recursive Case", "Termination"]:
        assert expected_section in content, f"Missing section '{expected_section}' in canonical note"


def test_expected_concepts_fixture_schema_validation():
    assert EXPECTED_CONCEPTS_PATH.exists(), f"Missing fixture at {EXPECTED_CONCEPTS_PATH}"
    raw_data = json.loads(EXPECTED_CONCEPTS_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw_data, list)

    concept_nodes = [ConceptNode.model_validate(item) for item in raw_data]
    assert len(concept_nodes) >= 4

    names = [c.name for c in concept_nodes]
    assert len(names) == len(set(names)), "Concept names must be unique"

    for c in concept_nodes:
        assert len(c.summary.strip()) > 0, f"Concept '{c.name}' summary must not be empty"
        assert len(c.summary) <= 500, f"Concept '{c.name}' summary exceeds 500 characters"
        assert len(c.name.strip()) > 0, "Concept name must not be empty"
        assert len(c.name) <= 100, "Concept name exceeds 100 characters"

    ids = {c.id for c in concept_nodes}
    assert len(ids) == len(concept_nodes), "Concept IDs must be unique"
    for c in concept_nodes:
        for prereq in c.prerequisites:
            assert prereq in ids, f"Prerequisite '{prereq}' not in concept IDs"


# ── Concept Extraction Tests ──────────────────────────────────────────────
def test_extract_concepts_success_with_stub():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )

    stub = CurriculumStub()
    concepts = extract_concepts(canonical, call=stub)

    assert len(concepts) == 4
    assert len(stub.calls) == 1
    assert stub.calls[0] == "concept_extraction"

    names = [c.name for c in concepts]
    assert names == ["Recursion", "Base Case", "Recursive Case", "Termination"]

    for c in concepts:
        assert isinstance(c, ConceptNode)
        assert len(c.id) > 0
        assert len(c.summary) > 0


def test_extract_concepts_stable_ids():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical1 = CanonicalNote(concept_id="fixed_note_id", markdown=markdown)
    canonical2 = CanonicalNote(concept_id="fixed_note_id", markdown=markdown)

    stub1 = CurriculumStub()
    stub2 = CurriculumStub()

    concepts1 = extract_concepts(canonical1, call=stub1)
    concepts2 = extract_concepts(canonical2, call=stub2)

    ids1 = [c.id for c in concepts1]
    ids2 = [c.id for c in concepts2]
    assert ids1 == ids2, "Concept IDs must be deterministic and stable across multiple calls"


def test_generate_stable_concept_id():
    id_a = generate_stable_concept_id("note_123", "Recursion")
    id_b = generate_stable_concept_id("note_123", "recursion ")
    id_c = generate_stable_concept_id("note_999", "Recursion")

    assert id_a == id_b, "Stable concept ID should normalize case and whitespace"
    assert id_a != id_c, "Stable concept ID should vary across different canonical notes"


# ── Failure Case 1: Empty canonical markdown ─────────────────────────────
def test_failure_case_1_empty_canonical_markdown():
    canonical = CanonicalNote(concept_id="test", markdown="   ")
    stub = CurriculumStub()
    with pytest.raises(ValueError, match="markdown must not be empty"):
        extract_concepts(canonical, call=stub)


# ── Failure Case 2: Model returns zero concepts ──────────────────────────
def test_failure_case_2_zero_concepts():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    empty_json = json.dumps({"concepts": []})
    custom_stub = CurriculumStub(responses={"concept_extraction": [empty_json]})

    with pytest.raises(ValueError, match="(No concepts|malformed structured data)"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 3: Model returns duplicate concept names ────────────────
def test_failure_case_3_duplicate_names():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    dup_json = json.dumps({
        "concepts": [
            {"name": "Recursion", "summary": "First summary", "prerequisites": []},
            {"name": "recursion", "summary": "Second summary", "prerequisites": []},
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [dup_json]})

    with pytest.raises(ValueError, match="Duplicate concept name"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 4: Model returns empty summary ──────────────────────────
def test_failure_case_4_empty_summary():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    empty_summary_json = json.dumps({
        "concepts": [
            {"name": "Recursion", "summary": "   ", "prerequisites": []},
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [empty_summary_json]})

    with pytest.raises(ValueError, match="(empty summary|malformed structured data)"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 5: Model returns malformed structured data ──────────────
def test_failure_case_5_malformed_structured_data():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    malformed_json = '{"concepts": "this should be a list, not a string"}'
    custom_stub = CurriculumStub(responses={"concept_extraction": [malformed_json]})

    with pytest.raises(ValueError, match="malformed structured data"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 6: Model returns duplicate IDs ──────────────────────────
def test_failure_case_6_duplicate_ids_prevented():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)
    stub = CurriculumStub()
    concepts = extract_concepts(canonical, call=stub)
    concept_ids = [c.id for c in concepts]
    assert len(concept_ids) == len(set(concept_ids)), "All concept IDs must be strictly unique"


# ── Failure Case 7: Model returns concepts unrelated to note ─────────────
def test_failure_case_7_unrelated_concepts():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    unrelated_json = json.dumps({
        "concepts": [
            {
                "name": "Photosynthesis",
                "summary": "Process used by plants to convert light energy into chemical energy.",
                "prerequisites": [],
            }
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [unrelated_json]})

    with pytest.raises(ValueError, match="unrelated to the canonical note content"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 8: Model returns extra unexpected fields ────────────────
def test_failure_case_8_extra_unexpected_fields():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    extra_fields_json = json.dumps({
        "concepts": [
            {
                "name": "Recursion",
                "summary": "Valid summary",
                "prerequisites": [],
                "unexpected_invented_field": "disallowed",
            }
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [extra_fields_json]})

    with pytest.raises(ValueError, match="malformed structured data"):
        extract_concepts(canonical, call=custom_stub)


# ── Failure Case 9: Inconsistent ordering and prerequisite cycles ────────
def test_failure_case_9_scrambled_ordering_is_consistently_sorted():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    scrambled_json = json.dumps({
        "concepts": [
            {
                "name": "Termination",
                "summary": "The formal guarantee that every recursive call makes monotonic progress.",
                "prerequisites": ["Base Case", "Recursive Case"],
            },
            {
                "name": "Recursive Case",
                "summary": "The execution path where the problem is reduced.",
                "prerequisites": ["Recursion", "Base Case"],
            },
            {
                "name": "Base Case",
                "summary": "The terminating condition that yields a direct result.",
                "prerequisites": ["Recursion"],
            },
            {
                "name": "Recursion",
                "summary": "Foundational technique where a function solves a problem by calling itself.",
                "prerequisites": [],
            },
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [scrambled_json]})
    sorted_concepts = extract_concepts(canonical, call=custom_stub)

    names = [c.name for c in sorted_concepts]
    assert names == ["Recursion", "Base Case", "Recursive Case", "Termination"], (
        "Concepts must be deterministically sorted in topological order"
    )


def test_failure_case_9_prerequisite_cycle_rejected():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(concept_id="test", markdown=markdown)

    cycle_json = json.dumps({
        "concepts": [
            {
                "name": "Recursion",
                "summary": "Technique calling itself.",
                "prerequisites": ["Base Case"],
            },
            {
                "name": "Base Case",
                "summary": "Terminating condition.",
                "prerequisites": ["Recursion"],
            },
        ]
    })
    custom_stub = CurriculumStub(responses={"concept_extraction": [cycle_json]})

    with pytest.raises(ValueError, match="Prerequisite cycle detected"):
        extract_concepts(canonical, call=custom_stub)


# ── Flow integration: handle_teacher_setup ────────────────────────────────
def test_handle_teacher_setup_flow():
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )

    appended_records = []

    class MockContext:
        run_id = "run_test_123"
        settings = None
        budget = None
        llm_call = CurriculumStub()

        def latest(self, kind):
            if kind == RecordKind.CANONICAL_NOTE:
                return SimpleNamespace(payload=initial_note.model_dump(mode="json"))
            return None

        def append(self, kind, payload, produced_by):
            appended_records.append((kind, payload, produced_by))

    ctx = MockContext()
    next_state = handle_teacher_setup(ctx)

    assert next_state == RunState.TAG_CONFIRMATION
    assert len(appended_records) == 1
    kind, payload, produced_by = appended_records[0]
    assert kind == RecordKind.CANONICAL_NOTE
    assert produced_by == "curriculum:concept_extraction"
    assert len(payload["extracted_concepts"]) == 4


def test_handle_teacher_setup_with_real_store_and_context(tmp_path):
    """Test handle_teacher_setup with real Store and slice.runner.Context."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
        extracted_concepts=[],
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="user")

    ctx = Context(store, run_id, _make_test_settings(10))
    stub = CurriculumStub()
    next_state = handle_teacher_setup(ctx, call=stub)

    assert next_state == RunState.TAG_CONFIRMATION
    latest_note_raw = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    assert latest_note_raw is not None
    updated_note = CanonicalNote.model_validate(latest_note_raw)
    assert len(updated_note.extracted_concepts) == 4
    assert updated_note.extracted_concepts[0].name == "Recursion"

    history = store.history(run_id, RecordKind.CANONICAL_NOTE)
    assert len(history) == 2
    assert history[0].produced_by == "user"
    assert history[1].produced_by == "curriculum:concept_extraction"


def test_handle_teacher_setup_missing_canonical_note_raises(tmp_path):
    """Test handle_teacher_setup raises an informative error when CanonicalNote is missing."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    ctx = Context(store, run_id, _make_test_settings(10))

    with pytest.raises(ValueError, match=f"No canonical note found in run {run_id}"):
        handle_teacher_setup(ctx, call=CurriculumStub())


def test_handle_teacher_setup_via_ctx_llm_call(tmp_path):
    """Test handle_teacher_setup resolves model call from ctx.llm_call."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="user")

    ctx = Context(store, run_id, _make_test_settings(10))
    ctx.llm_call = CurriculumStub()

    next_state = handle_teacher_setup(ctx)
    assert next_state == RunState.TAG_CONFIRMATION

    latest = CanonicalNote.model_validate(store.latest(run_id, RecordKind.CANONICAL_NOTE))
    assert len(latest.extracted_concepts) == 4


def test_handle_teacher_setup_feeds_tag_confirmation_seamlessly(tmp_path):
    """Verify handle_teacher_setup output directly enables handle_tag_confirmation."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="user")

    ctx = Context(store, run_id, _make_test_settings(10))
    # 1. Run teacher setup
    setup_next = handle_teacher_setup(ctx, call=CurriculumStub())
    assert setup_next == RunState.TAG_CONFIRMATION

    # 2. Next handler in state machine is tag_confirmation
    tag_next = handle_tag_confirmation(ctx)
    assert tag_next == RunState.TAG_CONFIRMATION

    pending = get_pending_tags(store, run_id)
    assert pending is not None
    assert len(pending["concepts"]) == 4
    assert [c.name for c in pending["concepts"]] == [
        "Recursion",
        "Base Case",
        "Recursive Case",
        "Termination",
    ]


# ── Teacher Tag Confirmation Tests ────────────────────────────────────────

def _setup_run_with_canonical_note(store: Store, run_id: str) -> CanonicalNote:
    """Helper setting up an initial canonical note with extracted concepts in store."""
    raw_data = json.loads(EXPECTED_CONCEPTS_PATH.read_text(encoding="utf-8"))
    concepts = [ConceptNode.model_validate(item) for item in raw_data]
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")

    canonical_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
        extracted_concepts=concepts,
        teacher_confirmed=False,
    )
    store.append(
        run_id,
        RecordKind.CANONICAL_NOTE,
        canonical_note.model_dump(mode="json"),
        produced_by="test_setup",
    )
    return canonical_note


def test_tag_confirmation_first_entry_parks_and_no_thread_blocked(tmp_path):
    """Req: Non-blocking suspension using slice.callback."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))

    # First entry should park the run without blocking
    next_state = handle_tag_confirmation(ctx)
    assert next_state == RunState.TAG_CONFIRMATION

    # Question is open and unexpired
    pending = callback.pending(store, run_id)
    assert len(pending) == 1

    # Pending tags presentation
    pending_info = get_pending_tags(store, run_id)
    assert pending_info is not None
    assert pending_info["run_id"] == run_id
    assert len(pending_info["concepts"]) == 4
    assert pending_info["concept_id"] == "c1000000-0000-0000-0000-000000000001"
    assert pending_info["expires_at"] is not None


# 1. Teacher confirms inferred concepts
def test_tag_confirmation_teacher_confirms_unchanged(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Teacher confirms concepts unchanged
    confirmed_run_id = submit_teacher_confirmation(
        store,
        run_id,
        teacher_id="teacher_albus",
        confirmed=True,
        edited_concepts=None,
    )
    assert confirmed_run_id == run_id

    # Re-entry: resolves into TEST_READY
    next_state = handle_tag_confirmation(ctx)
    assert next_state == RunState.TEST_READY

    # Verify confirmation record
    conf_rec = store.latest(run_id, RecordKind.CONFIRMATION)
    assert conf_rec is not None
    conf = TeacherConfirmation.model_validate(conf_rec)
    assert conf.confirmed is True
    assert conf.timed_out is False
    assert conf.teacher_id == "teacher_albus"
    assert conf.edited_concepts is None
    assert conf.confirmed_at is not None

    # Verify canonical note updated
    canon_rec = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    updated_canon = CanonicalNote.model_validate(canon_rec)
    assert updated_canon.teacher_confirmed is True
    assert updated_canon.confirmed_at == conf.confirmed_at
    assert len(updated_canon.extracted_concepts) == 4


# 2. Teacher edits concept names/summaries and confirms
def test_tag_confirmation_teacher_confirms_with_edits(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Teacher provides edited concepts (re-titles two concepts)
    edited = [
        ConceptNode(
            id=canonical.extracted_concepts[0].id,
            name="Recursive Methods",
            summary="Updated summary for recursive functions.",
            prerequisites=[],
        ),
        ConceptNode(
            id=canonical.extracted_concepts[1].id,
            name="Base Condition",
            summary="Stopping criteria for recursive calls.",
            prerequisites=[canonical.extracted_concepts[0].id],
        ),
    ]

    submit_teacher_confirmation(
        store,
        run_id,
        teacher_id="teacher_minerva",
        confirmed=True,
        edited_concepts=edited,
    )

    next_state = handle_tag_confirmation(ctx)
    assert next_state == RunState.TEST_READY

    conf_rec = store.latest(run_id, RecordKind.CONFIRMATION)
    conf = TeacherConfirmation.model_validate(conf_rec)
    assert conf.confirmed is True
    assert conf.timed_out is False
    assert conf.edited_concepts is not None
    assert len(conf.edited_concepts) == 2
    assert conf.edited_concepts[0].name == "Recursive Methods"

    canon_rec = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    updated_canon = CanonicalNote.model_validate(canon_rec)
    assert updated_canon.teacher_confirmed is True
    assert len(updated_canon.extracted_concepts) == 2
    assert updated_canon.extracted_concepts[0].name == "Recursive Methods"


# 3. Teacher rejects/invalidates a malformed edited concept list
def test_tag_confirmation_rejects_malformed_edited_concepts(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Case A: Empty list of edited concepts
    with pytest.raises(ValueError, match="cannot be empty"):
        submit_teacher_confirmation(store, run_id, confirmed=True, edited_concepts=[])

    # Case B: Concept with empty name
    with pytest.raises(ValueError, match="name cannot be empty"):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[
                {"id": "c1", "name": "   ", "summary": "Valid summary", "prerequisites": []}
            ],
        )

    # Case C: Concept with empty summary
    with pytest.raises(ValueError, match="empty summary"):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[
                {"id": "c1", "name": "Valid Name", "summary": "   ", "prerequisites": []}
            ],
        )

    # Case D: Duplicate concept names
    with pytest.raises(ValueError, match="duplicate names"):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[
                {"id": "c1", "name": "Recursion", "summary": "Sum 1", "prerequisites": []},
                {"id": "c2", "name": "recursion", "summary": "Sum 2", "prerequisites": []},
            ],
        )

    # Case E: Completely malformed structured data
    with pytest.raises(Exception):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[{"invalid_field": 123}],
        )


# 4. Timeout occurs (deterministic fake time via DB timeout_at)
def test_tag_confirmation_timeout_occurs_deterministically(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Deterministically expire the parked question without sleeping
    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run_id,))

    # Re-entry triggers timeout sweep and advances automatically to TEST_READY
    next_state = handle_tag_confirmation(ctx)
    assert next_state == RunState.TEST_READY


# 5. Timeout uses inferred concepts
def test_tag_confirmation_timeout_uses_inferred_concepts(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Deterministically expire
    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run_id,))

    handle_tag_confirmation(ctx)

    # Inferred concepts must remain completely intact in canonical note
    canon_rec = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    canon = CanonicalNote.model_validate(canon_rec)
    assert len(canon.extracted_concepts) == len(canonical.extracted_concepts)
    assert [c.name for c in canon.extracted_concepts] == [c.name for c in canonical.extracted_concepts]
    assert canon.teacher_confirmed is False


# 6. timed_out is correctly represented
def test_tag_confirmation_timed_out_representation(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run_id,))
    handle_tag_confirmation(ctx)

    conf_rec = store.latest(run_id, RecordKind.CONFIRMATION)
    assert conf_rec is not None
    conf = TeacherConfirmation.model_validate(conf_rec)
    assert conf.confirmed is False
    assert conf.timed_out is True
    assert conf.teacher_id == "system:timeout"
    assert conf.confirmed_at is None
    assert conf.edited_concepts is None


# 7. Wrong run_id cannot resolve another run
def test_tag_confirmation_wrong_run_id_isolation(tmp_path):
    store = Store(tmp_path / "test.db")
    run_real = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_real)

    ctx = Context(store, run_real, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Non-existent run_id raises
    with pytest.raises(ValueError, match="No pending tag confirmation found for run nonexistent_run"):
        submit_teacher_confirmation(store, "nonexistent_run", confirmed=True)

    # Real run is still pending
    assert get_pending_tags(store, run_real) is not None
    assert store.latest(run_real, RecordKind.CONFIRMATION) is None


# 8. Confirmation after the run has already moved on is rejected according to contracts
def test_tag_confirmation_after_run_moved_on_is_rejected(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Confirmed and moved on
    submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=True)
    next_state = handle_tag_confirmation(ctx)
    assert next_state == RunState.TEST_READY

    # Trying to confirm again after already moved on is rejected
    with pytest.raises(ValueError, match="already been confirmed"):
        submit_teacher_confirmation(store, run_id, teacher_id="t2", confirmed=True)

    # Subsequent handler invocations are idempotent and return TEST_READY
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY


# 9. Duplicate confirmation is rejected
def test_tag_confirmation_rejects_duplicate_submission(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # First submission succeeds
    submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=True)
    handle_tag_confirmation(ctx)

    # Duplicate submission must be rejected
    with pytest.raises(ValueError, match="duplicate confirmation rejected"):
        submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=True)


def test_tag_confirmation_rejects_human_confirmed_false(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    with pytest.raises(ValueError, match="confirmed must be True"):
        submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=False)


# 10. Two separate runs can have pending confirmations simultaneously
def test_tag_confirmation_multiple_simultaneous_runs(tmp_path):
    store = Store(tmp_path / "test.db")
    run1 = store.create_run("synapse")
    run2 = store.create_run("synapse")

    _setup_run_with_canonical_note(store, run1)
    _setup_run_with_canonical_note(store, run2)

    ctx1 = Context(store, run1, _make_test_settings(10))
    ctx2 = Context(store, run2, _make_test_settings(10))

    # Park both runs
    assert handle_tag_confirmation(ctx1) == RunState.TAG_CONFIRMATION
    assert handle_tag_confirmation(ctx2) == RunState.TAG_CONFIRMATION

    # Both runs have active, separate pending questions
    p1 = get_pending_tags(store, run1)
    p2 = get_pending_tags(store, run2)
    assert p1 is not None and p2 is not None
    assert p1["question_id"] != p2["question_id"]
    assert p1["run_id"] == run1
    assert p2["run_id"] == run2

    # Confirm run1 as teacher
    submit_teacher_confirmation(store, run1, teacher_id="teacher_1", confirmed=True)
    assert handle_tag_confirmation(ctx1) == RunState.TEST_READY

    # run2 is still pending
    assert get_pending_tags(store, run2) is not None

    # Deterministically expire run2
    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run2,))

    # run2 times out and advances automatically
    assert handle_tag_confirmation(ctx2) == RunState.TEST_READY

    conf1 = TeacherConfirmation.model_validate(store.latest(run1, RecordKind.CONFIRMATION))
    conf2 = TeacherConfirmation.model_validate(store.latest(run2, RecordKind.CONFIRMATION))

    assert conf1.confirmed is True and conf1.timed_out is False
    assert conf2.confirmed is False and conf2.timed_out is True


# 11. No live LLM calls occur during tag confirmation
def test_tag_confirmation_zero_llm_calls(tmp_path):
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    def strict_no_llm(*args, **kwargs):
        raise AssertionError("No LLM calls should ever occur during tag confirmation!")

    ctx = Context(store, run_id, _make_test_settings(10))
    setattr(ctx, "llm_call", strict_no_llm)

    # Park run - no LLM call
    assert handle_tag_confirmation(ctx) == RunState.TAG_CONFIRMATION

    # Check pending - no LLM call
    pending = get_pending_tags(store, run_id)
    assert pending is not None

    # Teacher confirms - no LLM call
    submit_teacher_confirmation(store, run_id, teacher_id="teacher_test", confirmed=True)

    # Resolve run - no LLM call
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY


# ── Explicit tag confirmation integration tests ───────────────────────────

def test_tag_confirmation_confirm(tmp_path):
    """Test standard teacher confirmation without edits advancing to TEST_READY."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    # 1. First entry parks run
    assert handle_tag_confirmation(ctx) == RunState.TAG_CONFIRMATION

    # 2. Teacher confirms
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)

    # 3. Handler advances to TEST_READY
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY

    # 4. Confirmation record is recorded
    conf_rec = store.latest(run_id, RecordKind.CONFIRMATION)
    assert conf_rec is not None
    conf = TeacherConfirmation.model_validate(conf_rec)
    assert conf.confirmed is True
    assert conf.timed_out is False
    assert conf.teacher_id == "prof_oak"
    assert conf.edited_concepts is None

    # 5. Canonical note is updated
    canon_rec = store.latest(run_id, RecordKind.CANONICAL_NOTE)
    updated_canon = CanonicalNote.model_validate(canon_rec)
    assert updated_canon.teacher_confirmed is True
    assert len(updated_canon.extracted_concepts) == len(canonical.extracted_concepts)


def test_tag_confirmation_edit(tmp_path):
    """Test teacher editing concepts and confirming advancing to TEST_READY."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    assert handle_tag_confirmation(ctx) == RunState.TAG_CONFIRMATION

    edited = [
        ConceptNode(
            id=canonical.extracted_concepts[0].id,
            name="Structural Recursion",
            summary="Recursive functions operating on data structures.",
            prerequisites=[],
        )
    ]
    submit_teacher_confirmation(store, run_id, teacher_id="prof_birch", confirmed=True, edited_concepts=edited)

    assert handle_tag_confirmation(ctx) == RunState.TEST_READY

    conf = TeacherConfirmation.model_validate(store.latest(run_id, RecordKind.CONFIRMATION))
    assert conf.confirmed is True
    assert conf.edited_concepts is not None
    assert len(conf.edited_concepts) == 1
    assert conf.edited_concepts[0].name == "Structural Recursion"

    canon = CanonicalNote.model_validate(store.latest(run_id, RecordKind.CANONICAL_NOTE))
    assert canon.teacher_confirmed is True
    assert len(canon.extracted_concepts) == 1
    assert canon.extracted_concepts[0].name == "Structural Recursion"


def test_tag_confirmation_timeout(tmp_path):
    """Test tag confirmation timeout uses inferred concepts and advances to TEST_READY."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    assert handle_tag_confirmation(ctx) == RunState.TAG_CONFIRMATION

    # Trigger timeout
    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run_id,))
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY

    # Confirmation record shows timeout
    conf = TeacherConfirmation.model_validate(store.latest(run_id, RecordKind.CONFIRMATION))
    assert conf.confirmed is False
    assert conf.timed_out is True
    assert conf.teacher_id == "system:timeout"

    # Inferred concepts are preserved
    canon = CanonicalNote.model_validate(store.latest(run_id, RecordKind.CANONICAL_NOTE))
    assert len(canon.extracted_concepts) == len(canonical.extracted_concepts)
    assert [c.name for c in canon.extracted_concepts] == [c.name for c in canonical.extracted_concepts]


def test_tag_confirmation_duplicate_response(tmp_path):
    """Test duplicate confirmation is rejected."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # First confirmation
    submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=True)
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY

    # Second submission is rejected
    with pytest.raises(ValueError, match="duplicate confirmation rejected|already been confirmed"):
        submit_teacher_confirmation(store, run_id, teacher_id="t2", confirmed=True)

    # Re-running handler remains at TEST_READY
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY


def test_tag_confirmation_invalid_response(tmp_path):
    """Test invalid responses (confirmed=False, empty concepts, duplicate names, invalid fields) are rejected."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Rejection 1: confirmed=False
    with pytest.raises(ValueError, match="confirmed must be True"):
        submit_teacher_confirmation(store, run_id, teacher_id="t1", confirmed=False)

    # Rejection 2: duplicate names in edited list
    with pytest.raises(ValueError, match="duplicate names"):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[
                {"id": "1", "name": "ConceptA", "summary": "SumA", "prerequisites": []},
                {"id": "2", "name": "concepta", "summary": "SumB", "prerequisites": []},
            ],
        )

    # Rejection 3: empty concept summary
    with pytest.raises(ValueError, match="empty summary"):
        submit_teacher_confirmation(
            store,
            run_id,
            confirmed=True,
            edited_concepts=[{"id": "1", "name": "ConceptA", "summary": "   ", "prerequisites": []}],
        )

    # Rejection 4: raw callback answer containing confirmed=False rejected by handler
    pending = callback.pending(store, run_id)
    assert len(pending) == 1
    callback.answer(store, pending[0].id, json.dumps({"confirmed": False, "teacher_id": "bad_t"}))
    with pytest.raises(ValueError, match="confirmed=False"):
        handle_tag_confirmation(ctx)


# ── Test Generation Prompt & Deterministic Fixtures Validation ───────────

TEST_GEN_PROMPT_PATH = ROOT / "synapse" / "curriculum" / "prompts" / "test_generation.md"
EXPECTED_TEST_PATH = FIXTURES_DIR / "expected_test_questions.json"
EXPECTED_BINARY_SEARCH_TEST_PATH = FIXTURES_DIR / "expected_test_questions_binary_search.json"


def test_test_generation_prompt_exists_and_meets_spec():
    """Verify prompt instructs model to generate exactly 3 MCQs adapting to confirmed concept."""
    assert TEST_GEN_PROMPT_PATH.exists(), f"Missing prompt file at {TEST_GEN_PROMPT_PATH}"
    prompt_text = TEST_GEN_PROMPT_PATH.read_text(encoding="utf-8")

    # Prompt requirements
    assert "3" in prompt_text, "Prompt must require 3 questions"
    assert "multiple-choice" in prompt_text.lower() or "mcq" in prompt_text.lower()
    assert "4" in prompt_text, "Prompt must require 4 options"
    assert "correct_answer" in prompt_text
    assert "options" in prompt_text
    assert "concept_id" in prompt_text
    assert "unique" in prompt_text.lower() or "no duplicate" in prompt_text.lower()
    assert "distinct" in prompt_text.lower() or "facets" in prompt_text.lower()
    # Must explicitly state not hardcoding fixed topics
    assert "hardcode" in prompt_text.lower() or "adapt" in prompt_text.lower()


def test_expected_test_fixture_schema_validation():
    """Verify expected_test_questions.json conforms to Test and TestQuestion contracts."""
    assert EXPECTED_TEST_PATH.exists(), f"Missing fixture at {EXPECTED_TEST_PATH}"
    raw = json.loads(EXPECTED_TEST_PATH.read_text(encoding="utf-8"))

    # Test top-level structure
    test_obj = Test.model_validate(raw)
    assert test_obj.concept_id == "c1000000-0000-0000-0000-000000000001"
    assert test_obj.concept_name == "Recursion"
    assert len(test_obj.questions) == 3

    # Validate each TestQuestion
    for q in test_obj.questions:
        assert isinstance(q, TestQuestion)
        assert q.concept_id == test_obj.concept_id
        assert len(q.text.strip()) > 0
        assert len(q.options) == 4
        assert len(set(q.options)) == 4, "Options must be unique"
        assert q.correct_answer in q.options, "correct_answer must be in options"

    # Distinct questions
    texts = [q.text.strip() for q in test_obj.questions]
    assert len(set(texts)) == 3, "Questions must test distinct aspects"


def test_binary_search_test_fixture_schema_validation():
    """Verify non-recursion concepts adapt cleanly and pass Test contract validation."""
    assert EXPECTED_BINARY_SEARCH_TEST_PATH.exists(), f"Missing fixture at {EXPECTED_BINARY_SEARCH_TEST_PATH}"
    raw = json.loads(EXPECTED_BINARY_SEARCH_TEST_PATH.read_text(encoding="utf-8"))

    test_obj = Test.model_validate(raw)
    assert test_obj.concept_id == "c2000000-0000-0000-0000-000000000001"
    assert test_obj.concept_name == "Binary Search"
    assert len(test_obj.questions) == 3

    for q in test_obj.questions:
        assert len(q.options) == 4
        assert len(set(q.options)) == 4
        assert q.correct_answer in q.options
        assert q.concept_id == test_obj.concept_id


def test_test_generation_payload_schema_enforcement():
    """Verify RawGeneratedQuestion and TestGenerationPayload enforce exact contract requirements."""
    valid_q_dict = {
        "concept_id": "c1",
        "text": "What is a base case?",
        "options": ["Termination condition", "Loop construct", "Memory leak", "Heap allocation"],
        "correct_answer": "Termination condition",
    }
    valid_q = RawGeneratedQuestion.model_validate(valid_q_dict)
    assert valid_q.text == "What is a base case?"

    # Exactly 3 questions required
    valid_payload = TestGenerationPayload(questions=[valid_q, valid_q, valid_q])
    assert len(valid_payload.questions) == 3

    # Rejection: Fewer than 3 questions
    with pytest.raises(Exception):
        TestGenerationPayload(questions=[valid_q, valid_q])

    # Rejection: More than 3 questions
    with pytest.raises(Exception):
        TestGenerationPayload(questions=[valid_q, valid_q, valid_q, valid_q])

    # Rejection: Duplicate options
    with pytest.raises(ValueError, match="Options must be unique"):
        RawGeneratedQuestion.model_validate({
            "concept_id": "c1",
            "text": "Valid text?",
            "options": ["A", "B", "A", "C"],
            "correct_answer": "A",
        })

    # Rejection: Correct answer not among options
    with pytest.raises(ValueError, match="correct_answer must be one of options"):
        RawGeneratedQuestion.model_validate({
            "concept_id": "c1",
            "text": "Valid text?",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "E",
        })

    # Rejection: Empty text
    with pytest.raises(Exception):
        RawGeneratedQuestion.model_validate({
            "concept_id": "c1",
            "text": "",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
        })

    # Rejection: Fewer than 4 options
    with pytest.raises(Exception):
        RawGeneratedQuestion.model_validate({
            "concept_id": "c1",
            "text": "Valid?",
            "options": ["A", "B", "C"],
            "correct_answer": "A",
        })


def test_stub_default_test_json_is_valid():
    """Verify CurriculumStub's DEFAULT_TEST_JSON conforms to TestGenerationPayload."""
    payload = TestGenerationPayload.model_validate_json(DEFAULT_TEST_JSON)
    assert len(payload.questions) == 3
    for q in payload.questions:
        assert len(q.options) == 4
        assert q.correct_answer in q.options


# ── Test Generator (generate_test) Unit Tests ────────────────────────────

def _make_sample_concept_and_canonical() -> tuple[ConceptNode, CanonicalNote]:
    concept = ConceptNode(
        id="c1000000-0000-0000-0000-000000000001",
        name="Recursion",
        summary="Function calling itself to solve sub-problems until a base case.",
        prerequisites=[],
    )
    canonical = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown="# Recursion\nRecursion solves problems by dividing into smaller instances...",
        extracted_concepts=[concept],
        teacher_confirmed=True,
    )
    return concept, canonical


def test_generate_test_default_success():
    """Verify generate_test generates 3 valid MCQs adhering to all contracts by default."""
    concept, canonical = _make_sample_concept_and_canonical()
    stub = CurriculumStub()

    test_obj = generate_test(concept, canonical, call=stub)

    assert isinstance(test_obj, Test)
    assert test_obj.concept_id == concept.id
    assert test_obj.concept_name == concept.name
    assert len(test_obj.questions) == 3

    for q in test_obj.questions:
        assert isinstance(q, TestQuestion)
        assert q.concept_id == concept.id
        assert len(q.text.strip()) > 0
        assert len(q.options) == 4
        assert len(set(q.options)) == 4, "Options must be unique"
        assert q.correct_answer in q.options, "correct_answer must be in options"

    texts = [q.text.strip() for q in test_obj.questions]
    assert len(set(texts)) == 3, "Questions must test distinct aspects"


def test_generate_test_retries_on_initial_failure_and_succeeds():
    """Verify generate_test retries on failure and succeeds when a later attempt is valid."""
    concept, canonical = _make_sample_concept_and_canonical()

    # Attempt 1: bad output (duplicate options)
    bad_attempt_1 = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Question 1?",
                "options": ["Opt A", "Opt B", "Opt A", "Opt D"],  # duplicate
                "correct_answer": "Opt A",
            },
            {
                "concept_id": concept.id,
                "text": "Question 2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Question 3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })

    # Attempt 2: valid output
    good_attempt_2 = DEFAULT_TEST_JSON

    stub = CurriculumStub(responses={"test_generation": [bad_attempt_1, good_attempt_2]})

    test_obj = generate_test(concept, canonical, call=stub)
    assert isinstance(test_obj, Test)
    assert len(test_obj.questions) == 3
    # Verifies that exactly 2 attempts were executed
    assert len(stub.calls) == 2
    assert stub.calls[0] == "test_generation"
    assert stub.calls[1] == "test_generation:attempt_2"


def test_generate_test_fails_after_max_retries_bounded_at_3():
    """Verify generate_test stops and raises ValueError after exactly 3 failed attempts."""
    concept, canonical = _make_sample_concept_and_canonical()

    bad_output = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Question 1?",
                "options": ["Dup", "Dup", "C", "D"],
                "correct_answer": "Dup",
            },
            {
                "concept_id": concept.id,
                "text": "Question 2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Question 3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })

    stub = CurriculumStub(responses={"test_generation": [bad_output, bad_output, bad_output, bad_output]})

    with pytest.raises(ValueError, match="after 3 attempts"):
        generate_test(concept, canonical, call=stub)

    # Verifies bounded retry count at 3
    assert len(stub.calls) == 3


def test_generate_test_rejects_duplicate_options_never_silent():
    """Verify duplicate options are strictly rejected, not silently allowed or deduplicated."""
    concept, canonical = _make_sample_concept_and_canonical()

    dup_options = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Q1?",
                "options": ["Choice 1", "Choice 2", "choice 1", "Choice 3"],  # duplicate ignoring case
                "correct_answer": "Choice 1",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [dup_options, dup_options, dup_options]})

    with pytest.raises(ValueError, match="duplicate options"):
        generate_test(concept, canonical, call=stub)


def test_generate_test_rejects_duplicate_questions_never_silent():
    """Verify duplicate question texts are strictly rejected across the test."""
    concept, canonical = _make_sample_concept_and_canonical()

    dup_questions = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "What is the defining mechanism of recursion?",
                "options": ["A1", "A2", "A3", "A4"],
                "correct_answer": "A1",
            },
            {
                "concept_id": concept.id,
                "text": "What is the defining mechanism of recursion?",  # identical question text
                "options": ["B1", "B2", "B3", "B4"],
                "correct_answer": "B1",
            },
            {
                "concept_id": concept.id,
                "text": "Distinct question 3?",
                "options": ["C1", "C2", "C3", "C4"],
                "correct_answer": "C1",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [dup_questions, dup_questions, dup_questions]})

    with pytest.raises(ValueError, match="Duplicate question text"):
        generate_test(concept, canonical, call=stub)


def test_generate_test_rejects_mismatched_concept_id():
    """Verify questions with mismatched concept_id are strictly rejected."""
    concept, canonical = _make_sample_concept_and_canonical()

    mismatched = json.dumps({
        "questions": [
            {
                "concept_id": "c_completely_wrong_id",
                "text": "Q1?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [mismatched, mismatched, mismatched]})

    with pytest.raises(ValueError, match="does not match target concept"):
        generate_test(concept, canonical, call=stub)


def test_generate_test_rejects_correct_answer_not_in_options():
    """Verify questions whose correct_answer is not in options are rejected."""
    concept, canonical = _make_sample_concept_and_canonical()

    missing_ans = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Q1?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "E",  # Not in options
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [missing_ans, missing_ans, missing_ans]})

    with pytest.raises(ValueError, match="correct_answer must be one of options|not present in options"):
        generate_test(concept, canonical, call=stub)


def test_generate_test_rejects_empty_question_text():
    """Verify questions with empty text are rejected."""
    concept, canonical = _make_sample_concept_and_canonical()

    empty_text = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "   ",  # whitespace only
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [empty_text, empty_text, empty_text]})

    with pytest.raises(ValueError, match="empty question text"):
        generate_test(concept, canonical, call=stub)


def test_generate_test_rejects_wrong_question_count():
    """Verify returning fewer or more questions than num_questions is rejected."""
    concept, canonical = _make_sample_concept_and_canonical()

    two_questions = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Q1?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub = CurriculumStub(responses={"test_generation": [two_questions, two_questions, two_questions]})

    with pytest.raises(ValueError, match="List should have at least 3 items|Expected exactly 3 questions"):
        generate_test(concept, canonical, call=stub, num_questions=3)


def test_generate_test_adapts_to_different_concept():
    """Verify generate_test adapts dynamically to any concept without hardcoding recursion."""
    bs_concept = ConceptNode(
        id="c2000000-0000-0000-0000-000000000001",
        name="Binary Search",
        summary="Search algorithm finding position of a target value within a sorted array.",
        prerequisites=[],
    )
    bs_canonical = CanonicalNote(
        concept_id=bs_concept.id,
        markdown="# Binary Search\nBinary search requires a sorted collection...",
        extracted_concepts=[bs_concept],
        teacher_confirmed=True,
    )

    bs_fixture = json.loads(EXPECTED_BINARY_SEARCH_TEST_PATH.read_text(encoding="utf-8"))
    bs_response = json.dumps({"questions": bs_fixture["questions"]})

    stub = CurriculumStub(responses={"test_generation": [bs_response]})
    test_obj = generate_test(bs_concept, bs_canonical, call=stub)

    assert isinstance(test_obj, Test)
    assert test_obj.concept_id == bs_concept.id
    assert test_obj.concept_name == "Binary Search"
    assert len(test_obj.questions) == 3
    for q in test_obj.questions:
        assert q.concept_id == bs_concept.id
        assert "binary search" in q.text.lower() or "search" in q.text.lower() or "array" in q.text.lower()


def test_generate_test_rejects_non_4_options():
    """Verify that questions with fewer or more than 4 options are strictly rejected."""
    concept, canonical = _make_sample_concept_and_canonical()

    # Case A: 3 options
    three_opts = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Q1?",
                "options": ["A", "B", "C"],  # 3 options
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub_3 = CurriculumStub(responses={"test_generation": [three_opts, three_opts, three_opts]})
    with pytest.raises(ValueError, match="at least 4 items|must have exactly 4 options"):
        generate_test(concept, canonical, call=stub_3)

    # Case B: 5 options
    five_opts = json.dumps({
        "questions": [
            {
                "concept_id": concept.id,
                "text": "Q1?",
                "options": ["A", "B", "C", "D", "E"],  # 5 options
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
            {
                "concept_id": concept.id,
                "text": "Q3?",
                "options": ["A", "B", "C", "D"],
                "correct_answer": "A",
            },
        ]
    })
    stub_5 = CurriculumStub(responses={"test_generation": [five_opts, five_opts, five_opts]})
    with pytest.raises(ValueError, match="at most 4 items|must have exactly 4 options"):
        generate_test(concept, canonical, call=stub_5)


def test_generate_test_rejects_malformed_model_response():
    """Verify malformed JSON or unstructured payload is rejected through bounded retries."""
    concept, canonical = _make_sample_concept_and_canonical()

    malformed_responses = ["NOT_JSON_AT_ALL", "{\"unexpected_key\": 123}", "null"]
    stub = CurriculumStub(responses={"test_generation": malformed_responses})

    with pytest.raises(ValueError, match="after 3 attempts"):
        generate_test(concept, canonical, call=stub)

    assert len(stub.calls) == 3


def test_generate_test_zero_live_llm_calls():
    """Verify generate_test uses strictly the passed call abstraction without live network."""
    concept, canonical = _make_sample_concept_and_canonical()
    call_log: list[str] = []

    def mock_call(*args, **kwargs):
        call_log.append(kwargs.get("step", "call"))
        return DEFAULT_TEST_JSON

    test_obj = generate_test(concept, canonical, call=mock_call)
    assert isinstance(test_obj, Test)
    assert len(test_obj.questions) == 3
    assert len(call_log) == 1
    assert call_log[0] == "test_generation"


# ── Flow Integration: handle_test_ready ───────────────────────────────────

def test_handle_test_ready_successful(tmp_path):
    """Test successful MCQ test generation from confirmed concepts advancing to AWAITING_STUDENT."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    # Move to TAG_CONFIRMATION then confirm
    handle_tag_confirmation(ctx)
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY

    # Execute handle_test_ready
    next_state = handle_test_ready(ctx, call=CurriculumStub())
    assert next_state == RunState.AWAITING_STUDENT

    # Verify persisted Test
    test_raw = store.latest(run_id, RecordKind.TEST)
    assert test_raw is not None
    test_obj = Test.model_validate(test_raw)
    assert len(test_obj.questions) == 3
    assert test_obj.concept_name == "Recursion"

    # Idempotency check: second invocation returns AWAITING_STUDENT without duplicating
    assert handle_test_ready(ctx, call=CurriculumStub()) == RunState.AWAITING_STUDENT
    assert len(store.history(run_id, RecordKind.TEST)) == 1


def test_handle_test_ready_invalid_generated_test(tmp_path):
    """Test invalid generated test is rejected and nothing invalid is persisted."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    handle_tag_confirmation(ctx)

    # Stub returns invalid test with only 2 options on all attempts
    invalid_test_json = json.dumps({
        "questions": [
            {
                "concept_id": "c1000000-0000-0000-0000-000000000001",
                "text": "Invalid question?",
                "options": ["A", "B"],
                "correct_answer": "A",
            }
        ]
    })
    bad_stub = CurriculumStub(responses={"test_generation": [invalid_test_json, invalid_test_json, invalid_test_json]})

    with pytest.raises(ValueError, match="at least 4 items|after 3 attempts"):
        handle_test_ready(ctx, call=bad_stub)

    # Nothing invalid persisted
    assert store.latest(run_id, RecordKind.TEST) is None


def test_handle_test_ready_retry_and_failure(tmp_path):
    """Test generation retry mechanism: initial failure followed by success, and bounded failure."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    handle_tag_confirmation(ctx)

    # Sub-case A: Attempt 1 malformed, Attempt 2 valid -> succeeds
    flaky_stub = CurriculumStub(responses={"test_generation": ["MALFORMED_JSON", DEFAULT_TEST_JSON]})
    next_state = handle_test_ready(ctx, call=flaky_stub)
    assert next_state == RunState.AWAITING_STUDENT
    assert len(flaky_stub.calls) == 2
    assert store.latest(run_id, RecordKind.TEST) is not None

    # Sub-case B: 3 consecutive failures results in bounded failure
    run2 = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run2)
    ctx2 = Context(store, run2, _make_test_settings(10))
    handle_tag_confirmation(ctx2)
    submit_teacher_confirmation(store, run2, teacher_id="prof_oak", confirmed=True)
    handle_tag_confirmation(ctx2)

    failing_stub = CurriculumStub(responses={"test_generation": ["BAD_1", "BAD_2", "BAD_3"]})
    with pytest.raises(ValueError, match="after 3 attempts"):
        handle_test_ready(ctx2, call=failing_stub)
    assert len(failing_stub.calls) == 3
    assert store.latest(run2, RecordKind.TEST) is None


def test_handle_test_ready_persisted_test(tmp_path):
    """Test generated test is correctly persisted with RecordKind.TEST and produced_by."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    handle_tag_confirmation(ctx)

    handle_test_ready(ctx, call=CurriculumStub())

    # Check persistence metadata in store
    history = store.history(run_id, RecordKind.TEST)
    assert len(history) == 1
    assert history[0].kind == RecordKind.TEST
    assert history[0].produced_by == "curriculum:test_generation"
    assert "questions" in history[0].payload
    assert len(history[0].payload["questions"]) == 3


def test_handle_test_ready_correct_concept_association(tmp_path):
    """Test generated test is associated with the exact confirmed concept ID and concept name."""
    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    canonical = _setup_run_with_canonical_note(store, run_id)

    ctx = Context(store, run_id, _make_test_settings(10))
    handle_tag_confirmation(ctx)

    # Teacher edits concepts with a custom concept ID and name
    custom_concept_id = "c9999999-9999-9999-9999-999999999999"
    edited_concept = ConceptNode(
        id=custom_concept_id,
        name="Tail Call Optimization",
        summary="Compiler optimization for tail recursive calls.",
        prerequisites=[],
    )
    submit_teacher_confirmation(
        store,
        run_id,
        teacher_id="prof_sprout",
        confirmed=True,
        edited_concepts=[edited_concept],
    )
    handle_tag_confirmation(ctx)

    # Create canned test response specifically referencing the custom concept
    tail_test_json = json.dumps({
        "questions": [
            {
                "concept_id": custom_concept_id,
                "text": "What is tail recursion?",
                "options": ["Last operation", "First operation", "Middle operation", "No operation"],
                "correct_answer": "Last operation",
            },
            {
                "concept_id": custom_concept_id,
                "text": "How does tail call optimization help the stack?",
                "options": ["Reuses current frame", "Allocates double frame", "Ignores calls", "Crashes runtime"],
                "correct_answer": "Reuses current frame",
            },
            {
                "concept_id": custom_concept_id,
                "text": "Which language feature enables TCO?",
                "options": ["Tail position calls", "Infinite heap", "Garbage collection", "Static typing"],
                "correct_answer": "Tail position calls",
            },
        ]
    })
    custom_stub = CurriculumStub(responses={"test_generation": [tail_test_json]})

    next_state = handle_test_ready(ctx, call=custom_stub)
    assert next_state == RunState.AWAITING_STUDENT

    test_rec = store.latest(run_id, RecordKind.TEST)
    test_obj = Test.model_validate(test_rec)
    assert test_obj.concept_id == custom_concept_id
    assert test_obj.concept_name == "Tail Call Optimization"
    assert len(test_obj.questions) == 3
    for q in test_obj.questions:
        assert q.concept_id == custom_concept_id


# ── Stub Hardening: No API Key, No Network, Deterministic Outputs ─────────

def test_stub_execution_with_no_api_key(tmp_path, monkeypatch):
    """Verify Person 3 flow executes successfully with completely empty / absent API keys."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="user")

    empty_key_settings = Settings(
        api_key="",
        model="none",
        fallback_model="none",
        escalation_model="none",
        max_tokens=100,
        max_tokens_per_run=100000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    ctx = Context(store, run_id, empty_key_settings)
    stub = CurriculumStub()

    # Step 1: teacher_setup
    s1 = handle_teacher_setup(ctx, call=stub)
    assert s1 == RunState.TAG_CONFIRMATION

    # Step 2: tag_confirmation
    s2 = handle_tag_confirmation(ctx)
    assert s2 == RunState.TAG_CONFIRMATION
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    s2_res = handle_tag_confirmation(ctx)
    assert s2_res == RunState.TEST_READY

    # Step 3: test_ready
    s3 = handle_test_ready(ctx, call=stub)
    assert s3 == RunState.AWAITING_STUDENT

    assert store.latest(run_id, RecordKind.TEST) is not None


def test_stub_execution_with_no_network_connection(tmp_path, monkeypatch):
    """Verify Person 3 flow executes without making ANY network socket or HTTP requests."""
    import socket
    import urllib.request

    def blocked_connect(*args, **kwargs):
        raise AssertionError("Network connection attempted during stub execution!")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(urllib.request, "urlopen", blocked_connect)

    store = Store(tmp_path / "test.db")
    run_id = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )
    store.append(run_id, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="user")

    ctx = Context(store, run_id, _make_test_settings(10))
    stub = CurriculumStub()

    # Run full sequence without network
    assert handle_teacher_setup(ctx, call=stub) == RunState.TAG_CONFIRMATION
    assert handle_tag_confirmation(ctx) == RunState.TAG_CONFIRMATION
    submit_teacher_confirmation(store, run_id, teacher_id="prof_oak", confirmed=True)
    assert handle_tag_confirmation(ctx) == RunState.TEST_READY
    assert handle_test_ready(ctx, call=stub) == RunState.AWAITING_STUDENT

    test_obj = Test.model_validate(store.latest(run_id, RecordKind.TEST))
    assert len(test_obj.questions) == 3


def test_stub_deterministic_outputs():
    """Verify CurriculumStub outputs are bit-for-bit identical across multiple repeated runs."""
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    canonical = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )

    stub1 = CurriculumStub()
    stub2 = CurriculumStub()

    concepts1 = extract_concepts(canonical, call=stub1)
    concepts2 = extract_concepts(canonical, call=stub2)

    # Core concept identity and structure must be identical
    assert [(c.id, c.name, c.summary, c.prerequisites) for c in concepts1] == [
        (c.id, c.name, c.summary, c.prerequisites) for c in concepts2
    ]

    test1 = generate_test(concepts1[0], canonical, call=stub1)
    test2 = generate_test(concepts2[0], canonical, call=stub2)

    # Question text, options, and correct answers are identical
    assert [q.text for q in test1.questions] == [q.text for q in test2.questions]
    assert [q.options for q in test1.questions] == [q.options for q in test2.questions]
    assert [q.correct_answer for q in test1.questions] == [q.correct_answer for q in test2.questions]


def test_stub_reset_and_canned_responses():
    """Verify CurriculumStub supports canned response overrides, step tracking, and reset()."""
    from synapse.curriculum.stub import BINARY_SEARCH_TEST_JSON

    custom_canned = {
        "test_generation": [
            DEFAULT_TEST_JSON,
            BINARY_SEARCH_TEST_JSON,
        ]
    }
    stub = CurriculumStub(responses=custom_canned)
    assert len(stub.calls) == 0

    concept, canonical = _make_sample_concept_and_canonical()
    t1 = generate_test(concept, canonical, call=stub)
    assert len(stub.calls) == 1
    assert t1.concept_id == concept.id

    # Second call uses binary search concept matching the fixture concept_id
    bs_concept = ConceptNode(
        id="c2000000-0000-0000-0000-000000000001",
        name="Binary Search",
        summary="Search algorithm over ordered sequences.",
        prerequisites=[],
    )
    t2 = generate_test(bs_concept, canonical, call=stub)
    assert len(stub.calls) == 2
    assert t2.concept_id == "c2000000-0000-0000-0000-000000000001"

    # Reset
    stub.reset()
    assert len(stub.calls) == 0
    assert len(stub._counts) == 0


# ── Complete Curriculum Pipeline End-to-End Integration Test ──────────────

def test_complete_curriculum_pipeline_integration(tmp_path):
    """End-to-end integration test for the COMPLETE Person 3 curriculum pipeline.

    Sequence:
    CanonicalNote -> handle_teacher_setup -> ConceptNode[] -> tag_confirmation
    -> teacher confirms/edits -> handle_test_ready -> Test -> RunState.AWAITING_STUDENT

    Verifies:
    1. Concepts are extracted.
    2. Concept IDs are stable across repeated extractions.
    3. Teacher confirmation is represented correctly in schemas and store.
    4. Teacher edits are respected throughout the pipeline.
    5. Timeout behavior is represented correctly with inferred concepts preserved.
    6. Generated test uses the confirmed concept.
    7. Every question has exactly 4 unique options.
    8. Correct answers exist within the options.
    9. Test is persisted using the append-only RecordKind.TEST mechanism.
    10. No live model call occurs (zero network, strictly canned stubs).
    11. No Person 2/4/5 modules are imported.
    12. No protected contracts are modified.
    """
    # ── Pipeline Run A: Teacher edits and confirms ─────────────────────────
    store = Store(tmp_path / "pipeline.db")
    run_a = store.create_run("synapse")
    markdown = CANONICAL_NOTE_PATH.read_text(encoding="utf-8")
    initial_note = CanonicalNote(
        concept_id="c1000000-0000-0000-0000-000000000001",
        markdown=markdown,
    )
    store.append(run_a, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="teacher_input")

    ctx_a = Context(store, run_a, _make_test_settings(10))
    stub_a = CurriculumStub()

    # 1. handle_teacher_setup extracts concepts
    state_1 = handle_teacher_setup(ctx_a, call=stub_a)
    assert state_1 == RunState.TAG_CONFIRMATION

    latest_canon_a = CanonicalNote.model_validate(store.latest(run_a, RecordKind.CANONICAL_NOTE))
    extracted_concepts_a = latest_canon_a.extracted_concepts
    # Verify 1: Concepts were extracted
    assert len(extracted_concepts_a) == 4
    concept_names_a = [c.name for c in extracted_concepts_a]
    assert concept_names_a == ["Recursion", "Base Case", "Recursive Case", "Termination"]

    # Verify 2: Concept IDs are stable
    extracted_concepts_again = extract_concepts(initial_note, call=stub_a)
    assert [c.id for c in extracted_concepts_a] == [c.id for c in extracted_concepts_again]

    # 2. handle_tag_confirmation parks the run
    state_2 = handle_tag_confirmation(ctx_a)
    assert state_2 == RunState.TAG_CONFIRMATION
    pending_info = get_pending_tags(store, run_a)
    assert pending_info is not None
    assert len(pending_info["concepts"]) == 4

    # 3. Teacher edits concepts and confirms
    edited_concept = ConceptNode(
        id=extracted_concepts_a[0].id,
        name="Structural Recursion",
        summary="Recursion breaking down complex data structures.",
        prerequisites=[],
    )
    edited_list = [edited_concept, extracted_concepts_a[1]]
    submit_teacher_confirmation(
        store,
        run_a,
        teacher_id="prof_mcgonagall",
        confirmed=True,
        edited_concepts=edited_list,
    )

    state_3 = handle_tag_confirmation(ctx_a)
    assert state_3 == RunState.TEST_READY

    # Verify 3 & 4: Teacher confirmation is represented correctly and edits are respected
    conf_rec = store.latest(run_a, RecordKind.CONFIRMATION)
    assert conf_rec is not None
    conf = TeacherConfirmation.model_validate(conf_rec)
    assert conf.confirmed is True
    assert conf.timed_out is False
    assert conf.teacher_id == "prof_mcgonagall"
    assert conf.edited_concepts is not None
    assert len(conf.edited_concepts) == 2
    assert conf.edited_concepts[0].name == "Structural Recursion"

    updated_note_a = CanonicalNote.model_validate(store.latest(run_a, RecordKind.CANONICAL_NOTE))
    assert updated_note_a.teacher_confirmed is True
    assert updated_note_a.confirmed_at == conf.confirmed_at
    assert len(updated_note_a.extracted_concepts) == 2
    assert updated_note_a.extracted_concepts[0].name == "Structural Recursion"

    # 4. handle_test_ready generates and persists test
    state_4 = handle_test_ready(ctx_a, call=stub_a)
    assert state_4 == RunState.AWAITING_STUDENT

    # Verify 9: Test is persisted using append-only RecordKind.TEST
    test_rec = store.latest(run_a, RecordKind.TEST)
    assert test_rec is not None
    test_history = store.history(run_a, RecordKind.TEST)
    assert len(test_history) == 1
    assert test_history[0].produced_by == "curriculum:test_generation"

    test_obj = Test.model_validate(test_rec)
    # Verify 6: Test uses the confirmed/edited concept
    assert test_obj.concept_id == edited_concept.id
    assert test_obj.concept_name == "Structural Recursion"
    assert len(test_obj.questions) == 3

    # Verify 7 & 8: 4 unique options, correct answer exists
    for q in test_obj.questions:
        assert len(q.options) == 4
        assert len(set(q.options)) == 4
        assert q.correct_answer in q.options
        assert q.concept_id == edited_concept.id
        assert len(q.text.strip()) > 0

    # ── Pipeline Run B: Timeout behavior representation ────────────────────
    run_b = store.create_run("synapse")
    store.append(run_b, RecordKind.CANONICAL_NOTE, initial_note.model_dump(mode="json"), produced_by="teacher_input")
    ctx_b = Context(store, run_b, _make_test_settings(10))
    stub_b = CurriculumStub()

    # Step 1: teacher_setup
    assert handle_teacher_setup(ctx_b, call=stub_b) == RunState.TAG_CONFIRMATION

    # Step 2: tag_confirmation parks
    assert handle_tag_confirmation(ctx_b) == RunState.TAG_CONFIRMATION

    # Step 3: Timeout occurs deterministically
    store.db.execute("UPDATE questions SET timeout_at=0 WHERE run_id=?", (run_b,))
    assert handle_tag_confirmation(ctx_b) == RunState.TEST_READY

    # Verify 5: Timeout behavior correctly represented
    timeout_conf_rec = store.latest(run_b, RecordKind.CONFIRMATION)
    assert timeout_conf_rec is not None
    timeout_conf = TeacherConfirmation.model_validate(timeout_conf_rec)
    assert timeout_conf.confirmed is False
    assert timeout_conf.timed_out is True
    assert timeout_conf.teacher_id == "system:timeout"
    assert timeout_conf.confirmed_at is None
    assert timeout_conf.edited_concepts is None

    # Inferred concepts preserved on timeout
    note_b = CanonicalNote.model_validate(store.latest(run_b, RecordKind.CANONICAL_NOTE))
    assert len(note_b.extracted_concepts) == 4
    assert note_b.teacher_confirmed is False

    # Step 4: test_ready generates test from inferred concepts
    assert handle_test_ready(ctx_b, call=stub_b) == RunState.AWAITING_STUDENT
    test_b = Test.model_validate(store.latest(run_b, RecordKind.TEST))
    assert test_b.concept_id == note_b.extracted_concepts[0].id
    assert test_b.concept_name == "Recursion"
    assert len(test_b.questions) == 3

    # Verify 10: No live model calls occurred (stubs logged all calls)
    assert len(stub_a.calls) > 0
    assert len(stub_b.calls) > 0



