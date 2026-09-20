"""
synapse.curriculum.flow

Curriculum flow handlers and domain logic for Person 3:
- extract_concepts: Concept extraction from canonical markdown using shared slice LLM
- handle_teacher_setup: Flow handler parsing canonical notes into ConceptNode records
- handle_tag_confirmation: Human-in-the-loop teacher tag confirmation via slice.callback
- handle_test_ready: Flow handler generating MCQ diagnostic tests
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from slice import callback
from slice.llm import complete
from slice.records import Question
from slice.runner import Context
from slice.store import Store
from synapse.curriculum.schema import ConceptExtractionPayload, RawGeneratedQuestion, TestGenerationPayload
from synapse.schemas import (
    MAX_MODEL_CALL_RETRIES,
    TAG_CONFIRMATION_TIMEOUT_SECONDS,
    CanonicalNote,
    ConceptNode,
    RecordKind,
    TeacherConfirmation,
    Test,
    TestQuestion,
    utcnow,
)
from synapse.state_machine import RunState

PROMPTS_DIR = Path(__file__).parent / "prompts"
NAMESPACE_SYNAPSE_CONCEPT = uuid.UUID("c0000000-0000-0000-0000-000000000000")


def _extract_payload(rec_or_dict: Any) -> dict[str, Any]:
    """Normalize store record to a dict payload."""
    if isinstance(rec_or_dict, BaseModel):
        return rec_or_dict.model_dump(mode="json")
    if hasattr(rec_or_dict, "payload"):
        return rec_or_dict.payload
    return rec_or_dict


def generate_stable_concept_id(canonical_concept_id: str, concept_name: str) -> str:
    """Generate a deterministic UUID for a concept within a canonical note scope."""
    key = f"{canonical_concept_id.strip()}:{concept_name.strip().lower()}"
    return str(uuid.uuid5(NAMESPACE_SYNAPSE_CONCEPT, key))


def build_concept_extraction_messages(markdown: str) -> list[dict]:
    """Construct prompt messages for concept extraction from canonical markdown."""
    prompt_file = PROMPTS_DIR / "concept_extraction.md"
    system_prompt = prompt_file.read_text(encoding="utf-8")
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Teacher's Canonical Note:\n\n{markdown}"},
    ]


def _sort_concepts_deterministically(
    nodes: list[ConceptNode],
    markdown: str,
) -> list[ConceptNode]:
    """Sort ConceptNodes in topological prerequisite order with document appearance tie-breaking.

    Raises:
        ValueError: If a prerequisite cycle is detected.
    """
    markdown_lower = markdown.lower()

    def doc_position(node: ConceptNode) -> int:
        pos = markdown_lower.find(node.name.lower())
        return pos if pos != -1 else 999999

    ids = {n.id for n in nodes}
    by_id = {n.id: n for n in nodes}
    indegree = {n.id: 0 for n in nodes}
    outgoing: dict[str, list[str]] = {n.id: [] for n in nodes}

    for n in nodes:
        for p in n.prerequisites:
            if p in ids:
                outgoing[p].append(n.id)
                indegree[n.id] += 1

    ready = [nid for nid, deg in indegree.items() if deg == 0]
    ready.sort(key=lambda nid: (doc_position(by_id[nid]), by_id[nid].name))

    sorted_nodes: list[ConceptNode] = []
    while ready:
        cur_id = ready.pop(0)
        sorted_nodes.append(by_id[cur_id])
        for nxt_id in outgoing[cur_id]:
            indegree[nxt_id] -= 1
            if indegree[nxt_id] == 0:
                ready.append(nxt_id)
                ready.sort(key=lambda nid: (doc_position(by_id[nid]), by_id[nid].name))

    if len(sorted_nodes) != len(nodes):
        raise ValueError("Prerequisite cycle detected in extracted concepts")

    return sorted_nodes


def extract_concepts(
    canonical_note: CanonicalNote,
    *,
    call: Callable = complete,
    settings: Any = None,
    budget: Any = None,
) -> list[ConceptNode]:
    """Extract discrete ConceptNodes from a CanonicalNote using slice LLM abstraction.

    Args:
        canonical_note: CanonicalNote containing markdown and parent concept_id.
        call: LLM completion function (defaults to slice.llm.complete).
        settings: Settings instance (loaded from slice.config if None).
        budget: Budget instance for token accounting.

    Returns:
        list[ConceptNode] with validated summaries, unique names, grounded concepts,
        and consistently ordered stable IDs.

    Raises:
        ValueError: On empty markdown, zero concepts, duplicate names, empty summaries,
                    unrelated concepts, duplicate IDs, or prerequisite cycles.
    """
    if not canonical_note.markdown or not canonical_note.markdown.strip():
        raise ValueError("Canonical note markdown must not be empty")

    if settings is None:
        try:
            from slice.config import Settings
            settings = Settings()
        except Exception:
            settings = None

    messages = build_concept_extraction_messages(canonical_note.markdown)

    try:
        payload = call(
            settings=settings,
            budget=budget,
            messages=messages,
            schema=ConceptExtractionPayload,
            step="concept_extraction",
        )
    except Exception as exc:
        raise ValueError(f"Model returned malformed structured data: {exc}") from exc

    if not payload or not getattr(payload, "concepts", None):
        raise ValueError("No concepts were extracted from the canonical note")

    markdown_lower = canonical_note.markdown.lower()

    seen_names: set[str] = set()
    for item in payload.concepts:
        name_clean = item.name.strip()
        if not name_clean:
            raise ValueError("Concept name cannot be empty")
        name_lower = name_clean.lower()
        if name_lower in seen_names:
            raise ValueError(f"Duplicate concept name detected: '{name_clean}'")
        seen_names.add(name_lower)

        summary_clean = item.summary.strip()
        if not summary_clean:
            raise ValueError(f"Concept '{name_clean}' has an empty summary")
        if len(summary_clean) > 500:
            raise ValueError(f"Concept '{name_clean}' summary exceeds 500 characters")

        tokens = [w for w in re.findall(r"\w+", name_lower) if len(w) >= 3]
        if name_lower not in markdown_lower and not any(t in markdown_lower for t in tokens):
            raise ValueError(f"Concept '{name_clean}' is unrelated to the canonical note content")

    name_to_id = {
        item.name.strip(): generate_stable_concept_id(canonical_note.concept_id, item.name)
        for item in payload.concepts
    }
    name_lower_to_id = {
        item.name.strip().lower(): name_to_id[item.name.strip()]
        for item in payload.concepts
    }

    if len(set(name_to_id.values())) != len(name_to_id):
        raise ValueError("Duplicate concept IDs generated across distinct concepts")

    concept_nodes: list[ConceptNode] = []
    for item in payload.concepts:
        cid = name_to_id[item.name.strip()]
        resolved_prereqs: list[str] = []
        for prereq in item.prerequisites:
            p_clean = prereq.strip()
            if p_clean in name_to_id:
                resolved_prereqs.append(name_to_id[p_clean])
            elif p_clean.lower() in name_lower_to_id:
                resolved_prereqs.append(name_lower_to_id[p_clean.lower()])
            else:
                resolved_prereqs.append(p_clean)

        node = ConceptNode(
            id=cid,
            name=item.name.strip(),
            summary=item.summary.strip(),
            prerequisites=resolved_prereqs,
        )
        concept_nodes.append(node)

    node_ids = [node.id for node in concept_nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Duplicate concept IDs detected in extracted concept nodes")

    return _sort_concepts_deterministically(concept_nodes, canonical_note.markdown)


def handle_teacher_setup(ctx: Context, call: Callable | None = None) -> RunState:
    """Parse canonical note markdown into structured concepts.

    Follows slice.runner Flow handler conventions:
    1. Reads latest CanonicalNote from run context.
    2. Runs extract_concepts using shared LLM call abstraction.
    3. Appends updated CanonicalNote containing extracted ConceptNodes.
    4. Returns RunState.TAG_CONFIRMATION.
    """
    canonical_ver = ctx.latest(RecordKind.CANONICAL_NOTE)
    if not canonical_ver:
        raise ValueError(f"No canonical note found in run {ctx.run_id}")

    canonical_note = CanonicalNote.model_validate(_extract_payload(canonical_ver))

    actual_call = call or getattr(ctx, "llm_call", None) or complete
    settings = getattr(ctx, "settings", None)
    budget = getattr(ctx, "budget", None)

    concepts = extract_concepts(
        canonical_note,
        call=actual_call,
        settings=settings,
        budget=budget,
    )

    canonical_note.extracted_concepts = concepts
    ctx.append(
        RecordKind.CANONICAL_NOTE,
        canonical_note.model_dump(mode="json"),
        produced_by="curriculum:concept_extraction",
    )
    return RunState.TAG_CONFIRMATION


# ── Tag Confirmation Helpers & Handler ───────────────────────────────────

def _find_question_for_run(store: Store, run_id: str) -> Question | None:
    """Find the most relevant callback Question for a run."""
    open_qs = store.open_questions(run_id)
    if open_qs:
        return open_qs[0]
    rows = store.db.execute(
        "SELECT id FROM questions WHERE run_id=? ORDER BY asked_at DESC LIMIT 1",
        (run_id,),
    ).fetchall()
    if rows:
        return store.get_question(rows[0]["id"])
    return None


def get_pending_tags(store: Store, run_id: str) -> dict[str, Any] | None:
    """Retrieve pending tag confirmation details for a run.

    Returns:
        Dict with keys (run_id, question_id, concept_id, concepts, expires_at)
        or None if no unexpired pending question exists.
    """
    pending_qs = callback.pending(store, run_id)
    if not pending_qs:
        return None
    q = pending_qs[0]
    raw_concepts = q.context.get("concepts", [])
    concepts = [ConceptNode.model_validate(c) for c in raw_concepts]
    expires_at = datetime.fromtimestamp(q.timeout_at, tz=timezone.utc)
    return {
        "run_id": run_id,
        "question_id": q.id,
        "concept_id": q.context.get("concept_id", ""),
        "concepts": concepts,
        "expires_at": expires_at,
    }


def submit_teacher_confirmation(
    store: Store,
    run_id: str,
    *,
    teacher_id: str = "teacher",
    confirmed: bool = True,
    edited_concepts: list[ConceptNode] | list[dict] | None = None,
) -> str:
    """Submit teacher tag confirmation for a parked run.

    Args:
        store: Store persistence instance.
        run_id: Target run ID.
        teacher_id: Teacher identifier.
        confirmed: Confirmation flag (must be True for human submissions).
        edited_concepts: Optional list of edited ConceptNodes.

    Returns:
        run_id of the confirmed run.

    Raises:
        ValueError: If confirmed is False, if run is already confirmed,
                    or if no pending question exists.
    """
    if not confirmed:
        raise ValueError("Human teacher confirmation cannot reject; confirmed must be True")

    # Reject duplicate confirmation
    if store.latest(run_id, RecordKind.CONFIRMATION):
        raise ValueError(f"Run {run_id} has already been confirmed (duplicate confirmation rejected)")

    pending_qs = callback.pending(store, run_id)
    if not pending_qs:
        raise ValueError(f"No pending tag confirmation found for run {run_id}")
    q = pending_qs[0]

    validated_edited: list[ConceptNode] | None = None
    if edited_concepts is not None:
        if len(edited_concepts) == 0:
            raise ValueError("Edited concepts list cannot be empty")
        validated_edited = [
            c if isinstance(c, ConceptNode) else ConceptNode.model_validate(c)
            for c in edited_concepts
        ]
        for c in validated_edited:
            if not c.name.strip():
                raise ValueError("Edited concept name cannot be empty")
            if not c.summary.strip():
                raise ValueError(f"Edited concept '{c.name}' has an empty summary")
        names = [c.name.strip().lower() for c in validated_edited]
        if len(names) != len(set(names)):
            raise ValueError("Edited concepts contain duplicate names")

    answer_dict = {
        "confirmed": True,
        "teacher_id": teacher_id,
        "edited_concepts": [c.model_dump(mode="json") for c in validated_edited] if validated_edited is not None else None,
    }
    callback.answer(store, q.id, json.dumps(answer_dict), who=teacher_id)
    return run_id


def handle_tag_confirmation(ctx: Context) -> RunState:
    """Human-in-the-loop teacher tag confirmation handler.

    First entry: parks a Question using slice.callback.ask() with timeout deadline.
    Re-entry (after teacher answer): appends TeacherConfirmation and updated CanonicalNote.
    Re-entry (after timeout/sweep): appends TeacherConfirmation(confirmed=False, timed_out=True).

    Returns:
        RunState.TAG_CONFIRMATION while waiting, or RunState.TEST_READY when resolved.
    """
    # 1. If already confirmed, move to TEST_READY
    if ctx.latest(RecordKind.CONFIRMATION):
        return RunState.TEST_READY

    canonical_ver = ctx.latest(RecordKind.CANONICAL_NOTE)
    if not canonical_ver:
        raise ValueError(f"No canonical note found in run {ctx.run_id}")
    canonical_note = CanonicalNote.model_validate(_extract_payload(canonical_ver))

    q = _find_question_for_run(ctx.store, ctx.run_id)

    # 2. First entry: No question asked yet -> Park question via callback.ask()
    if q is None:
        context = {
            "concept_id": canonical_note.concept_id,
            "concepts": [c.model_dump(mode="json") for c in canonical_note.extracted_concepts],
        }
        if hasattr(ctx.settings, "expert_timeout_minutes") and ctx.settings.expert_timeout_minutes is not None:
            timeout_minutes = ctx.settings.expert_timeout_minutes
        elif hasattr(ctx.settings, "tag_confirmation_timeout_minutes") and ctx.settings.tag_confirmation_timeout_minutes is not None:
            timeout_minutes = ctx.settings.tag_confirmation_timeout_minutes
        else:
            timeout_minutes = int(TAG_CONFIRMATION_TIMEOUT_SECONDS / 60.0)

        from slice.config import Settings
        ask_settings = ctx.settings
        if ask_settings is None or getattr(ask_settings, "expert_timeout_minutes", None) != timeout_minutes:
            ask_settings = Settings(
                api_key="none", model="none", fallback_model="none", escalation_model="none",
                max_tokens=100, max_tokens_per_run=1000, max_attempts_per_step=3,
                expert_timeout_minutes=int(timeout_minutes),
                langfuse_public="", langfuse_secret="", langfuse_host="",
            )

        callback.ask(ctx.store, ctx.run_id, "Teacher tag confirmation", context, ask_settings)
        return RunState.TAG_CONFIRMATION

    # 3. Question exists: Check expiration/sweep
    if not q.is_answered and q.is_expired:
        callback.sweep(ctx.store, ctx.run_id)
        q = ctx.store.get_question(q.id)

    # 4. Question answered: Check whether teacher answered or timed out
    if q and q.is_answered:
        # Case A: Teacher answered
        if q.answer:
            try:
                ans_data = json.loads(q.answer) if q.answer.startswith("{") else {"confirmed": True, "answer": q.answer}
            except Exception:
                ans_data = {"confirmed": True}

            if ans_data.get("confirmed") is False:
                raise ValueError("Teacher confirmation response cannot have confirmed=False")

            teacher_id = ans_data.get("teacher_id", "teacher")
            raw_edited = ans_data.get("edited_concepts")
            edited_concepts = (
                [ConceptNode.model_validate(c) for c in raw_edited]
                if raw_edited is not None
                else None
            )
            if edited_concepts is not None:
                if len(edited_concepts) == 0:
                    raise ValueError("Edited concepts list cannot be empty")
                for c in edited_concepts:
                    if not c.name.strip():
                        raise ValueError("Edited concept name cannot be empty")
                    if not c.summary.strip():
                        raise ValueError(f"Edited concept '{c.name}' has an empty summary")
                names = [c.name.strip().lower() for c in edited_concepts]
                if len(names) != len(set(names)):
                    raise ValueError("Edited concepts contain duplicate names")

            now = utcnow()
            confirmation = TeacherConfirmation(
                concept_id=canonical_note.concept_id,
                teacher_id=teacher_id,
                confirmed=True,
                edited_concepts=edited_concepts,
                confirmed_at=now,
                timed_out=False,
            )

            canonical_note.teacher_confirmed = True
            canonical_note.confirmed_at = now
            if edited_concepts is not None:
                canonical_note.extracted_concepts = edited_concepts

            ctx.append(RecordKind.CONFIRMATION, confirmation.model_dump(mode="json"), produced_by=teacher_id)
            ctx.append(RecordKind.CANONICAL_NOTE, canonical_note.model_dump(mode="json"), produced_by=teacher_id)
            return RunState.TEST_READY

        # Case B: Timed out (empty answer from sweep)
        confirmation = TeacherConfirmation(
            concept_id=canonical_note.concept_id,
            teacher_id="system:timeout",
            confirmed=False,
            edited_concepts=None,
            confirmed_at=None,
            timed_out=True,
        )
        ctx.append(RecordKind.CONFIRMATION, confirmation.model_dump(mode="json"), produced_by="system:timeout")
        return RunState.TEST_READY

    # 5. Still pending
    return RunState.TAG_CONFIRMATION


# ── Test Generation ──────────────────────────────────────────────────────

def build_test_generation_messages(
    concept: ConceptNode,
    canonical_note: CanonicalNote,
    num_questions: int = 3,
) -> list[dict]:
    """Build messages for LLM test generation based on prompt template."""
    prompt_path = PROMPTS_DIR / "test_generation.md"
    template = (
        prompt_path.read_text(encoding="utf-8")
        if prompt_path.exists()
        else "Generate diagnostic MCQs for the concept."
    )
    system_prompt = (
        template
        .replace("{concept_id}", concept.id)
        .replace("{concept_name}", concept.name)
        .replace("{concept_summary}", concept.summary)
        .replace("{canonical_markdown}", canonical_note.markdown)
    )
    user_content = (
        f"Generate exactly {num_questions} multiple-choice questions for confirmed concept '{concept.name}' (id: {concept.id}).\n"
        f"Concept summary: {concept.summary}\n"
        f"Ground each question in the canonical note content."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _validate_and_build_test(
    raw_payload: Any,
    concept: ConceptNode,
    num_questions: int = 3,
) -> Test:
    """Deterministically validate generated structured data in Python.

    Validates:
    - Expected number of questions
    - Non-empty, bounded question text
    - No duplicate question texts across the test
    - Exactly 4 options per question
    - Non-empty, bounded option strings
    - All 4 options are mutually unique (no duplicates)
    - Non-empty, bounded correct_answer
    - correct_answer is verbatim present in options
    - concept_id matches the target concept ID
    """
    if raw_payload is None:
        raise ValueError("Model returned empty payload")

    if isinstance(raw_payload, str):
        try:
            data = json.loads(raw_payload)
        except Exception as exc:
            raise ValueError(f"Model returned invalid JSON string: {exc}") from exc
    elif hasattr(raw_payload, "model_dump"):
        data = raw_payload.model_dump(mode="json")
    elif isinstance(raw_payload, dict):
        data = raw_payload
    else:
        raise ValueError(f"Unsupported payload type: {type(raw_payload)}")

    raw_questions = data.get("questions")
    if raw_questions is None:
        raise ValueError("Payload missing 'questions' list")
    if not isinstance(raw_questions, list):
        raise ValueError("'questions' must be a list")

    if len(raw_questions) != num_questions:
        raise ValueError(f"Expected exactly {num_questions} questions, got {len(raw_questions)}")

    test_questions: list[TestQuestion] = []
    seen_texts: set[str] = set()

    for idx, q_data in enumerate(raw_questions):
        if not isinstance(q_data, dict):
            if hasattr(q_data, "model_dump"):
                q_data = q_data.model_dump(mode="json")
            else:
                raise ValueError(f"Question {idx} is not a valid object")

        # 1. Text validation
        text = q_data.get("text")
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError(f"Question {idx} has empty question text")
        text_clean = text.strip()
        if len(text_clean) > 500:
            raise ValueError(f"Question {idx} text exceeds 500 characters")

        text_norm = text_clean.lower()
        if text_norm in seen_texts:
            raise ValueError(f"Duplicate question text detected across test: '{text_clean}'")
        seen_texts.add(text_norm)

        # 2. Concept ID validation
        q_concept_id = q_data.get("concept_id")
        if q_concept_id and q_concept_id.strip() != concept.id:
            raise ValueError(
                f"Question {idx} concept_id '{q_concept_id}' does not match target concept '{concept.id}'"
            )

        # 3. Options validation
        options = q_data.get("options")
        if not options or not isinstance(options, list):
            raise ValueError(f"Question {idx} options must be a list")
        if len(options) != 4:
            raise ValueError(f"Question {idx} must have exactly 4 options, got {len(options)}")

        cleaned_options: list[str] = []
        for opt_idx, opt in enumerate(options):
            if not isinstance(opt, str) or not opt.strip():
                raise ValueError(f"Question {idx} option {opt_idx} is empty")
            opt_clean = opt.strip()
            if len(opt_clean) > 200:
                raise ValueError(f"Question {idx} option {opt_idx} exceeds 200 characters")
            cleaned_options.append(opt_clean)

        norm_options = [opt.lower() for opt in cleaned_options]
        if len(set(norm_options)) != len(cleaned_options):
            raise ValueError(f"Question {idx} contains duplicate options: {cleaned_options}")

        # 4. Correct answer validation
        correct_answer = q_data.get("correct_answer")
        if not correct_answer or not isinstance(correct_answer, str) or not correct_answer.strip():
            raise ValueError(f"Question {idx} has empty correct_answer")
        correct_clean = correct_answer.strip()
        if len(correct_clean) > 200:
            raise ValueError(f"Question {idx} correct_answer exceeds 200 characters")

        if correct_clean not in cleaned_options:
            raise ValueError(
                f"Question {idx} correct_answer '{correct_clean}' is not present in options {cleaned_options}"
            )

        qid = q_data.get("id") or str(uuid.uuid4())
        test_question = TestQuestion(
            id=qid,
            text=text_clean,
            correct_answer=correct_clean,
            options=cleaned_options,
            concept_id=concept.id,
        )
        test_questions.append(test_question)

    return Test(
        concept_id=concept.id,
        concept_name=concept.name,
        questions=test_questions,
    )


def generate_test(
    concept: ConceptNode,
    canonical_note: CanonicalNote,
    *,
    call: Callable = complete,
    num_questions: int = 3,
    settings: Any = None,
    budget: Any = None,
) -> Test:
    """Generate diagnostic MCQs for a confirmed ConceptNode using slice LLM abstraction.

    Args:
        concept: Confirmed ConceptNode to generate test questions for.
        canonical_note: CanonicalNote containing source curriculum markdown.
        call: LLM completion function (defaults to slice.llm.complete).
        num_questions: Number of questions to generate (default 3).
        settings: Settings instance.
        budget: Budget instance for token accounting.

    Returns:
        Test domain model containing validated TestQuestion items.

    Raises:
        ValueError: If validation fails after bounded retries (MAX_MODEL_CALL_RETRIES).
    """
    if settings is None:
        try:
            from slice.config import Settings
            settings = Settings()
        except Exception:
            settings = None

    messages = build_test_generation_messages(concept, canonical_note, num_questions=num_questions)

    last_error: Exception | None = None
    for attempt in range(1, MAX_MODEL_CALL_RETRIES + 1):
        step_name = f"test_generation:attempt_{attempt}" if attempt > 1 else "test_generation"
        try:
            payload = call(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=TestGenerationPayload if num_questions == 3 else None,
                step=step_name,
            )
            return _validate_and_build_test(payload, concept, num_questions=num_questions)
        except Exception as exc:
            last_error = exc
            continue

    raise ValueError(
        f"Failed to generate valid test for concept '{concept.name}' after {MAX_MODEL_CALL_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


def handle_test_ready(ctx: Context, call: Callable | None = None) -> RunState:
    """Generate diagnostic MCQ test from confirmed concepts for the run.

    Follows slice.runner Flow handler conventions:
    1. Reads confirmed concepts and CanonicalNote from run context.
    2. Generates Test using Person 3's generate_test.
    3. Validates Test against shared schemas and concept association.
    4. Persists Test using ctx.append(RecordKind.TEST).
    5. Advances to RunState.AWAITING_STUDENT.
    """
    if ctx.latest(RecordKind.TEST):
        return RunState.AWAITING_STUDENT

    canonical_ver = ctx.latest(RecordKind.CANONICAL_NOTE)
    if not canonical_ver:
        raise ValueError(f"No canonical note found in run {ctx.run_id}")
    canonical_note = CanonicalNote.model_validate(_extract_payload(canonical_ver))

    conf_ver = ctx.latest(RecordKind.CONFIRMATION)
    if conf_ver:
        confirmation = TeacherConfirmation.model_validate(_extract_payload(conf_ver))
        if confirmation.edited_concepts:
            confirmed_concepts = confirmation.edited_concepts
        else:
            confirmed_concepts = canonical_note.extracted_concepts
    else:
        confirmed_concepts = canonical_note.extracted_concepts

    if not confirmed_concepts:
        raise ValueError(f"No confirmed concepts found for run {ctx.run_id}")

    # Determine target concept for diagnostic test
    target_concept = next(
        (c for c in confirmed_concepts if c.id == canonical_note.concept_id),
        confirmed_concepts[0],
    )

    actual_call = call or getattr(ctx, "llm_call", None) or complete
    settings = getattr(ctx, "settings", None)
    budget = getattr(ctx, "budget", None)

    test_obj = generate_test(
        target_concept,
        canonical_note,
        call=actual_call,
        num_questions=3,
        settings=settings,
        budget=budget,
    )

    validated_test = Test.model_validate(test_obj)
    if validated_test.concept_id != target_concept.id:
        raise ValueError(
            f"Generated test concept_id '{validated_test.concept_id}' does not match target concept '{target_concept.id}'"
        )
    for q in validated_test.questions:
        if q.concept_id != target_concept.id:
            raise ValueError(
                f"Question concept_id '{q.concept_id}' does not match target concept '{target_concept.id}'"
            )

    ctx.append(
        RecordKind.TEST,
        validated_test.model_dump(mode="json"),
        produced_by="curriculum:test_generation",
    )
    return RunState.AWAITING_STUDENT
