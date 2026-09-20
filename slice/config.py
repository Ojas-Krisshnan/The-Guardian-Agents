"""
One place that reads configuration. Nowhere else calls os.environ.

Scattered getenv calls are how a project ends up with three different defaults
for the same setting and no idea which one is live. Everything comes from .env,
loaded once, with the defaults visible here rather than buried at call sites.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: str | Path = ".env") -> bool:
    """Read .env into the environment. Real environment variables win, so a
    Codespaces secret or an exported value can override the file."""
    try:
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
        return True
    except FileNotFoundError:
        return False


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    fallback_model: str
    escalation_model: str
    max_tokens: int              # per request
    max_tokens_per_run: int      # the run-level fence
    max_attempts_per_step: int
    expert_timeout_minutes: int
    langfuse_public: str
    langfuse_secret: str
    langfuse_host: str
    provider: str = "openrouter"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    nim_api_key: str | None = None
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_model: str = "meta/llama-3.1-70b-instruct"
    nim_fallback_model: str | None = "nvidia/nemotron-3-ultra"
    synapse_jwt_secret: str = "dev-secret-change-in-prod"
    tag_confirmation_timeout_seconds: int = 600
    database_path: str = "synapse.db"
    slice_db_path: str = "run.db"

    @property
    def openrouter_api_key(self) -> str:
        return self.api_key

    @property
    def slice_model(self) -> str:
        return self.model

    @property
    def slice_fallback_model(self) -> str:
        return self.fallback_model

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public and self.langfuse_secret)


def settings(reload: bool = True) -> Settings:
    if reload:
        load_env()
    g = os.environ.get
    return Settings(
        api_key               = g("OPENROUTER_API_KEY", "").strip(),
        model                 = g("SLICE_MODEL", "inclusionai/ling-3.0-flash").strip(),
        fallback_model        = g("SLICE_FALLBACK_MODEL", "mistralai/mistral-small-3.2-24b-instruct").strip(),
        escalation_model      = g("SLICE_ESCALATION_MODEL", "anthropic/claude-haiku-4.5").strip(),
        max_tokens            = int(g("SLICE_MAX_TOKENS", "1200")),
        max_tokens_per_run    = int(g("SLICE_MAX_TOKENS_PER_RUN", "250000")),
        max_attempts_per_step = int(g("SLICE_MAX_ATTEMPTS_PER_STEP", "3")),
        expert_timeout_minutes= int(g("SLICE_EXPERT_TIMEOUT_MINUTES", "45")),
        langfuse_public       = g("LANGFUSE_PUBLIC_KEY", "").strip(),
        langfuse_secret       = g("LANGFUSE_SECRET_KEY", "").strip(),
        langfuse_host         = g("LANGFUSE_HOST", "https://cloud.langfuse.com").strip(),
        provider              = g("SLICE_PROVIDER", "openrouter").strip(),
        openrouter_base_url   = g("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        nim_api_key           = g("NIM_API_KEY", "").strip() or None,
        nim_base_url          = g("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").strip(),
        nim_model             = g("NIM_MODEL", "meta/llama-3.1-70b-instruct").strip(),
        nim_fallback_model    = g("NIM_FALLBACK_MODEL", "nvidia/nemotron-3-ultra").strip() or None,
        synapse_jwt_secret    = g("SYNAPSE_JWT_SECRET", "dev-secret-change-in-prod").strip(),
        tag_confirmation_timeout_seconds = int(g("SYNAPSE_TAG_TIMEOUT_SECONDS", "600")),
        database_path         = g("SYNAPSE_DB_PATH", "synapse.db").strip(),
        slice_db_path         = g("SLICE_DB", "run.db").strip(),
    )
