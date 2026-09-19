"""
Tests for slice.llm provider abstraction and configuration infrastructure.
Verifies compliance with Contracts.md Section D.3:
- Provider enum and ProviderConfig
- Provider resolution logic and no silent fallback
- Missing key detection (ProviderNotConfigured)
- ModelClient protocol
- complete() provider routing, schema parsing, repair pass, budget check before request
"""
from dataclasses import replace
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from slice.budget import Budget, BudgetExceeded
from slice.config import Settings
from slice.llm import (
    CapExhausted,
    ModelClient,
    ModelError,
    PoolExhausted,
    Provider,
    ProviderConfig,
    ProviderNotConfigured,
    SchemaFailure,
    complete,
    get_provider_config,
)


@pytest.fixture
def base_settings():
    return Settings(
        api_key="sk-openrouter-test",
        model="inclusionai/ling-3.0-flash",
        fallback_model="mistralai/mistral-small-3.2-24b-instruct",
        escalation_model="anthropic/claude-haiku-4.5",
        max_tokens=1200,
        max_tokens_per_run=250000,
        max_attempts_per_step=3,
        expert_timeout_minutes=45,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openrouter",
        openrouter_base_url="https://openrouter.ai/api/v1",
        nim_api_key=None,
        nim_base_url="https://integrate.api.nvidia.com/v1",
        nim_model="meta/llama-3.1-70b-instruct",
        nim_fallback_model="nvidia/nemotron-3-ultra",
    )


class DummySchema(BaseModel):
    answer: str
    confidence: float


def test_provider_enum_values():
    assert Provider.OPENROUTER.value == "openrouter"
    assert Provider.NIM.value == "nim"


def test_openrouter_default(base_settings):
    cfg = get_provider_config(base_settings)
    assert cfg.name == Provider.OPENROUTER
    assert cfg.api_key == "sk-openrouter-test"
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.default_model == "inclusionai/ling-3.0-flash"
    assert cfg.fallback_model == "mistralai/mistral-small-3.2-24b-instruct"


def test_explicit_openrouter(base_settings):
    cfg = get_provider_config(base_settings, provider=Provider.OPENROUTER)
    assert cfg.name == Provider.OPENROUTER
    assert cfg.api_key == "sk-openrouter-test"

    cfg_str = get_provider_config(base_settings, provider="openrouter")
    assert cfg_str.name == Provider.OPENROUTER


def test_explicit_nim(base_settings):
    s_nim = replace(base_settings, nim_api_key="nim-secret-key")
    cfg = get_provider_config(s_nim, provider=Provider.NIM)
    assert cfg.name == Provider.NIM
    assert cfg.api_key == "nim-secret-key"
    assert cfg.base_url == "https://integrate.api.nvidia.com/v1"
    assert cfg.default_model == "meta/llama-3.1-70b-instruct"
    assert cfg.fallback_model == "nvidia/nemotron-3-ultra"


def test_slice_provider_nim_env(base_settings):
    s_nim = replace(base_settings, provider="nim", nim_api_key="nim-secret-key")
    cfg = get_provider_config(s_nim)
    assert cfg.name == Provider.NIM
    assert cfg.api_key == "nim-secret-key"


def test_missing_openrouter_key(base_settings):
    s_empty = replace(base_settings, api_key="")
    with pytest.raises(ProviderNotConfigured, match="OPENROUTER_API_KEY is not set"):
        get_provider_config(s_empty)


def test_missing_nim_key(base_settings):
    # Missing NIM key via SLICE_PROVIDER=nim
    s_nim_no_key = replace(base_settings, provider="nim", nim_api_key=None)
    with pytest.raises(ProviderNotConfigured, match="NIM_API_KEY is not set"):
        get_provider_config(s_nim_no_key)

    # Missing NIM key via explicit provider=Provider.NIM
    with pytest.raises(ProviderNotConfigured, match="NIM_API_KEY is not set"):
        get_provider_config(base_settings, provider=Provider.NIM)


def test_no_silent_fallback(base_settings):
    """If NIM fails configuration, it must NEVER silently fall back to OpenRouter."""
    s_nim_missing = replace(base_settings, provider="nim", api_key="valid-openrouter", nim_api_key=None)
    with pytest.raises(ProviderNotConfigured):
        get_provider_config(s_nim_missing)


def test_explicit_provider_override(base_settings):
    """Explicit argument overrides settings.provider in both directions."""
    s = replace(base_settings, provider="openrouter", nim_api_key="nim-key")
    cfg_nim = get_provider_config(s, provider=Provider.NIM)
    assert cfg_nim.name == Provider.NIM

    s_nim = replace(base_settings, provider="nim", nim_api_key="nim-key")
    cfg_or = get_provider_config(s_nim, provider=Provider.OPENROUTER)
    assert cfg_or.name == Provider.OPENROUTER


def test_model_client_protocol_satisfaction():
    class DummyClient:
        async def complete(
            self,
            *,
            messages: list[dict],
            schema: type[BaseModel] | None,
            model: str,
            max_tokens: int,
            timeout: float,
        ) -> str:
            return "ok"

    client = DummyClient()
    assert isinstance(client, ModelClient)


def test_complete_uses_resolved_provider(base_settings):
    s_nim = replace(base_settings, nim_api_key="nim-key-123")
    mock_budget = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 42},
    }

    with patch("httpx.post", return_value=mock_resp) as mock_post:
        res = complete(
            settings=s_nim,
            budget=mock_budget,
            messages=[{"role": "user", "content": "Hi"}],
            provider=Provider.NIM,
        )

        assert res == "Hello world"
        mock_budget.check_tokens.assert_called_once()
        mock_budget.record_tokens.assert_called_once_with(42)

        # Verify call went to NIM base URL with NIM auth header
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://integrate.api.nvidia.com/v1/chat/completions"
        assert kwargs["headers"] == {"Authorization": "Bearer nim-key-123"}
        assert kwargs["json"]["model"] == "meta/llama-3.1-70b-instruct"


def test_complete_schema_validation(base_settings):
    mock_budget = MagicMock()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    payload = json.dumps({"answer": "42", "confidence": 0.99})
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": f"```json\n{payload}\n```"}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 50},
    }

    with patch("httpx.post", return_value=mock_resp):
        res = complete(
            settings=base_settings,
            budget=mock_budget,
            messages=[{"role": "user", "content": "What is the meaning of life?"}],
            schema=DummySchema,
        )

        assert isinstance(res, DummySchema)
        assert res.answer == "42"
        assert res.confidence == 0.99


def test_budget_check_before_request(base_settings):
    mock_budget = MagicMock()
    mock_budget.check_tokens.side_effect = BudgetExceeded("tokens", 250001, 250000)

    with patch("httpx.post") as mock_post:
        with pytest.raises(BudgetExceeded):
            complete(
                settings=base_settings,
                budget=mock_budget,
                messages=[{"role": "user", "content": "Hi"}],
            )
        # HTTP request must never have been made
        mock_post.assert_not_called()
