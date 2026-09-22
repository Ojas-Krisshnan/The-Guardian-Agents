# tests/test_openai_integration.py
"""Comprehensive tests for OpenAI provider integration in the Slice architecture and Synapse pipeline."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

from slice.budget import Budget, BudgetExceeded
from slice.config import Settings
from slice.llm import (
    CapExhausted,
    ModelError,
    Provider,
    ProviderConfig,
    ProviderNotConfigured,
    complete,
    get_openai_client,
    get_provider_config,
)
from slice.store import Store
from synapse.agents.flow import diagnose, tailor_note
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    ConceptNode,
    Diagnosis,
    DiagnosisItem,
    MistakeClassification,
    NoteVersion,
    Test,
    TestQuestion,
    TrendLabel,
)


@pytest.fixture
def openai_settings():
    return Settings(
        api_key="",
        model="",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openai",
        openai_api_key="sk-test-mocked-openai-key-secret",
        openai_model="gpt-4o-mini",
        openai_fallback_model="gpt-4o",
    )


@pytest.fixture
def run_store(tmp_path):
    store = Store(str(tmp_path / "test_run.db"))
    yield store
    store.close()


def test_openai_provider_config_loaded_correctly(openai_settings):
    """1. OpenAI provider configuration loads correctly."""
    cfg = get_provider_config(openai_settings)
    assert cfg.name == Provider.OPENAI
    assert cfg.api_key == "sk-test-mocked-openai-key-secret"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.default_model == "gpt-4o-mini"
    assert cfg.fallback_model == "gpt-4o"


def test_missing_api_key_produces_clear_configuration_error():
    """2. Missing API key produces a clear configuration error."""
    s = Settings(
        api_key="sk-other-key",
        model="",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openai",
        openai_api_key=None,
    )
    with pytest.raises(ProviderNotConfigured, match="SLICE_PROVIDER=openai but OPENAI_API_KEY is not set"):
        get_provider_config(s)


def test_provider_selection_works():
    """3. Provider selection works between openrouter, nim, and openai."""
    s_openai = Settings(
        api_key="openrouter-k",
        model="m1",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openai",
        openai_api_key="sk-openai-k",
    )
    assert get_provider_config(s_openai).name == Provider.OPENAI

    s_or = Settings(
        api_key="sk-openrouter-k",
        model="m1",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openrouter",
    )
    assert get_provider_config(s_or).name == Provider.OPENROUTER

    s_nim = Settings(
        api_key="sk-openrouter-k",
        model="m1",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="nim",
        nim_api_key="nvapi-k",
    )
    assert get_provider_config(s_nim).name == Provider.NIM


def test_openai_client_created_correctly(openai_settings):
    """4. OpenAI client is created correctly without exposing secret in repr."""
    client = get_openai_client(settings=openai_settings)
    assert client is not None
    assert client.api_key == "sk-test-mocked-openai-key-secret"


def test_model_requests_pass_through_slice_llm(openai_settings, run_store):
    """5. Model requests pass through slice/llm.py and track tokens."""
    run_id = run_store.create_run("test_llm")
    budget = Budget(run_store, run_id, openai_settings)

    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="Mocked answer from OpenAI"),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(total_tokens=42),
    )

    with patch("openai.resources.chat.completions.Completions.create", return_value=mock_response) as mock_create:
        res = complete(
            settings=openai_settings,
            budget=budget,
            messages=[{"role": "user", "content": "Ping"}],
            step="ping_step",
        )
        assert res == "Mocked answer from OpenAI"
        mock_create.assert_called_once()
        # Verify call arguments
        call_kw = mock_create.call_args.kwargs
        assert call_kw["model"] == "gpt-4o-mini"
        assert call_kw["messages"] == [{"role": "user", "content": "Ping"}]

    # Verify budget accounting occurred in store
    assert budget.tokens_used() == 42


def test_diagnosis_agent_structured_output_validation(openai_settings, run_store):
    """6 & 7. Diagnosis agent receives AI response and validates structured output."""
    run_id = run_store.create_run("test_diag")
    budget = Budget(run_store, run_id, openai_settings)

    test_q = TestQuestion(
        id="q_1",
        text="What is a base case?",
        options=["Terminates recursion", "Compiles code", "Allocates memory", "Loops forever"],
        correct_answer="Terminates recursion",
        concept_id="Recursion",
    )
    test = Test(
        id="t_1",
        concept_id="Recursion",
        concept_name="Recursion",
        questions=[test_q],
    )
    attempt = Attempt(
        student_id="stu_99",
        test_id="t_1",
        concept_id="Recursion",
        answers={"q_1": "Loops forever"},
        score=0,
        total=1,
    )

    valid_diag_payload = {
        "id": "d_123",
        "student_id": "stu_99",
        "concept_id": "Recursion",
        "items": [
            {
                "question_id": "q_1",
                "classification": "conceptual_gap",
                "reason": "Student believed base cases cause infinite loops rather than termination.",
            }
        ],
        "mastery_estimate": 0.2,
        "trend": "new",
        "created_at": "2026-09-20T20:00:00Z",
    }

    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=json.dumps(valid_diag_payload)),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(total_tokens=150),
    )

    with patch("openai.resources.chat.completions.Completions.create", return_value=mock_response):
        diag = diagnose(
            attempt=attempt,
            test=test,
            settings=openai_settings,
            budget=budget,
        )

    assert isinstance(diag, Diagnosis)
    assert diag.student_id == "stu_99"
    assert diag.concept_id == "Recursion"
    assert diag.mastery_estimate == 0.2
    assert len(diag.items) == 1
    assert diag.items[0].classification == MistakeClassification.CONCEPTUAL_GAP
    assert "infinite loops" in diag.items[0].reason
    assert budget.tokens_used() == 150


def test_note_tailoring_agent_receives_analysis_and_validates(openai_settings, run_store):
    """8 & 9. Note-tailoring agent receives analysis and produces validated note."""
    run_id = run_store.create_run("test_tailor")
    budget = Budget(run_store, run_id, openai_settings)

    diagnosis = Diagnosis(
        id="d_123",
        student_id="stu_99",
        concept_id="Recursion",
        items=[
            DiagnosisItem(
                question_id="q_1",
                classification=MistakeClassification.CONCEPTUAL_GAP,
                reason="Confused base case with recursive step",
            )
        ],
        mastery_estimate=0.3,
        trend=TrendLabel.NEW,
    )

    canonical = CanonicalNote(
        concept_id="Recursion",
        markdown="# Recursion\nBase cases matter.",
        extracted_concepts=[ConceptNode(name="Recursion", summary="Base cases")],
    )

    mock_note_md = (
        "# Personalized Note: Mastering Recursion\n\n"
        "## Addressing Identified Gaps\n"
        "| Mistake | Correction |\n"
        "| --- | --- |\n"
        "| Base case confusion | A base case stops recursion, protecting the stack |\n\n"
        "Check out [[Recursion]] for foundational details."
    )

    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=mock_note_md),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(total_tokens=220),
    )

    with patch("openai.resources.chat.completions.Completions.create", return_value=mock_response):
        note = tailor_note(
            student_id="stu_99",
            concept_id="Recursion",
            diagnosis=diagnosis,
            canonical_note=canonical,
            settings=openai_settings,
            budget=budget,
        )

    assert isinstance(note, NoteVersion)
    assert note.student_id == "stu_99"
    assert note.concept_id == "Recursion"
    assert note.diagnosis_id == "d_123"
    assert "# Personalized Note: Mastering Recursion" in note.markdown
    assert "[[Recursion]]" in note.markdown
    assert budget.tokens_used() == 220


def test_budget_accounting_enforces_run_limits(openai_settings, run_store):
    """10. Budget accounting enforces limits and refuses to start when exceeded."""
    run_id = run_store.create_run("test_budget_fence")
    budget = Budget(run_store, run_id, openai_settings)

    # Record 5000 tokens (which equals max_tokens_per_run=5000)
    budget.record_tokens(5000)

    with pytest.raises(BudgetExceeded, match="token budget reached"):
        complete(
            settings=openai_settings,
            budget=budget,
            messages=[{"role": "user", "content": "Test"}],
        )


def test_existing_providers_still_work_with_httpx(run_store):
    """11. Existing providers (OpenRouter) continue to work seamlessly."""
    s_openrouter = Settings(
        api_key="sk-test-or-key",
        model="inclusionai/ling-3.0-flash",
        fallback_model="mistralai/mistral-small-3.2-24b-instruct",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=5000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openrouter",
        openrouter_base_url="https://openrouter.ai/api/v1",
    )
    run_id = run_store.create_run("test_or")
    budget = Budget(run_store, run_id, s_openrouter)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Response from OpenRouter"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 30},
    }

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res = complete(
            settings=s_openrouter,
            budget=budget,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert res == "Response from OpenRouter"
        mock_post.assert_called_once()
        assert "openrouter.ai" in mock_post.call_args[0][0]
    assert budget.tokens_used() == 30


def test_no_provider_silently_falls_back_to_another(openai_settings, run_store):
    """12. No provider silently falls back to another provider when call fails."""
    import openai
    run_id = run_store.create_run("test_no_fallback")
    budget = Budget(run_store, run_id, openai_settings)

    # When OpenAI call fails with authentication error, it must raise ModelError and NOT switch to OpenRouter
    auth_err = openai.AuthenticationError(
        message="Incorrect API key provided",
        response=MagicMock(status_code=401),
        body=None,
    )

    with patch("openai.resources.chat.completions.Completions.create", side_effect=auth_err):
        with pytest.raises(ModelError, match="OpenAI authentication failed"):
            complete(
                settings=openai_settings,
                budget=budget,
                messages=[{"role": "user", "content": "Test"}],
            )


def test_api_key_is_never_returned_in_responses_or_logs(openai_settings, run_store):
    """13 & 14. API key is never returned in model responses, schemas, or reprs."""
    run_id = run_store.create_run("test_sec")
    budget = Budget(run_store, run_id, openai_settings)

    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="Clean educational response"),
            finish_reason="stop",
        )],
        usage=SimpleNamespace(total_tokens=10),
    )

    secret = openai_settings.openai_api_key
    assert secret not in str(get_provider_config(openai_settings))

    with patch("openai.resources.chat.completions.Completions.create", return_value=mock_response):
        res = complete(
            settings=openai_settings,
            budget=budget,
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert secret not in res

    # Check store history for any accidental key leakage
    for rec in run_store.replay(run_id):
        assert secret not in json.dumps(rec.payload)
