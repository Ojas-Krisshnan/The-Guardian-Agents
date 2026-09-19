"""API Pydantic HTTP models for foundation, Auth, Runs, and Questions."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class CreateRunRequest(BaseModel):
    domain: str = "demo"
    meta: dict[str, Any] | None = None


class RunResponse(BaseModel):
    id: str
    domain: str
    state: str
    created_at: float
    updated_at: float
    meta: dict[str, Any] = Field(default_factory=dict)


class VersionResponse(BaseModel):
    seq: int
    kind: str
    produced_by: str
    payload: dict[str, Any]
    created_at: float


class QuestionResponse(BaseModel):
    id: str
    run_id: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    asked_at: float
    timeout_at: float
    answered_at: float | None = None
    answer: str | None = None
    is_answered: bool
    is_expired: bool


class AnswerQuestionRequest(BaseModel):
    answer: str
    who: str = "expert"


class ErrorResponse(BaseModel):
    detail: str
