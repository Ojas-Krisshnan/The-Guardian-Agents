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


def test_openai_provider_resolution():
    s = Settings(
        api_key="",
        model="",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openai",
        openai_api_key="sk-test-openai-secret-key-12345",
        openai_model="gpt-4o-mini",
        openai_fallback_model="gpt-4o",
    )
    cfg = get_provider_config(s)
    assert cfg.name == Provider.OPENAI
    assert cfg.api_key == "sk-test-openai-secret-key-12345"
    assert cfg.base_url == "https://api.openai.com/v1"
    assert cfg.default_model == "gpt-4o-mini"
    assert cfg.fallback_model == "gpt-4o"


def test_missing_openai_key_raises_without_fallback():
    s = Settings(
        api_key="sk-openrouter-key-that-must-not-be-used",
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
        provider="openai",
        openai_api_key=None,
    )
    # Must raise ProviderNotConfigured specifically and NOT fall back to OpenRouter!
    with pytest.raises(ProviderNotConfigured, match="SLICE_PROVIDER=openai but OPENAI_API_KEY is not set"):
        get_provider_config(s)


def test_unknown_provider_raises():
    s = Settings(
        api_key="sk-key",
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
        provider="unsupported_provider_xyz",
    )
    with pytest.raises(ProviderNotConfigured, match="Unsupported SLICE_PROVIDER"):
        get_provider_config(s)


def test_openai_client_is_created_correctly():
    from slice.llm import get_openai_client
    s = Settings(
        api_key="",
        model="",
        fallback_model="",
        escalation_model="",
        max_tokens=1000,
        max_tokens_per_run=10000,
        max_attempts_per_step=3,
        expert_timeout_minutes=10,
        langfuse_public="",
        langfuse_secret="",
        langfuse_host="",
        provider="openai",
        openai_api_key="sk-mock-client-key-12345678",
        openai_base_url="https://api.openai.com/v1",
    )
    client = get_openai_client(settings=s)
    assert client is not None
    assert client.api_key == "sk-mock-client-key-12345678"
    assert str(client.base_url).rstrip("/") == "https://api.openai.com/v1"


def test_provider_config_masks_api_key_in_repr():
    cfg = ProviderConfig(
        name=Provider.OPENAI,
        api_key="sk-proj-super-secret-api-key-here",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
    )
    repr_str = repr(cfg)
    assert "sk-proj-super-secret-api-key-here" not in repr_str
    assert "***" in repr_str or "..." in repr_str
