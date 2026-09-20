# tests/test_providers.py
import pytest
from slice.config import Settings
from slice.llm import Provider, ProviderConfig, ProviderNotConfigured, get_provider_config


def test_default_provider_resolves_openrouter():
    s = Settings(
        api_key="sk-test-openrouter-key",
        model="inclusionai/ling-3.0-flash",
        fallback_model="mistralai/mistral-small-3.2-24b-instruct",
        escalation_model="anthropic/claude-haiku-4.5",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openrouter",
    )
    cfg = get_provider_config(s)
    assert cfg.name == Provider.OPENROUTER
    assert cfg.api_key == "sk-test-openrouter-key"
    assert "openrouter" in cfg.base_url
    assert cfg.default_model == "inclusionai/ling-3.0-flash"


def test_nim_provider_resolution():
    s = Settings(
        api_key="sk-test-openrouter-key",
        model="inclusionai/ling-3.0-flash",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="nim",
        nim_api_key="nvapi-test-key",
    )
    cfg = get_provider_config(s)
    assert cfg.name == Provider.NIM
    assert cfg.api_key == "nvapi-test-key"
    assert "nvidia.com" in cfg.base_url


def test_missing_openrouter_key_raises():
    s = Settings(
        api_key="",
        model="m",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openrouter",
    )
    with pytest.raises(ProviderNotConfigured):
        get_provider_config(s)


def test_missing_nim_key_raises():
    s = Settings(
        api_key="sk-openrouter",
        model="m",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="nim",
        nim_api_key=None,
    )
    with pytest.raises(ProviderNotConfigured):
        get_provider_config(s)


def test_api_key_as_link_uses_url_as_base():
    s = Settings(
        api_key="https://custom.api.link/v1",
        model="m",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
    )
    cfg = get_provider_config(s)
    assert cfg.base_url == "https://custom.api.link/v1"
