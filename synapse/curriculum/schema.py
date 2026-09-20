"""
synapse.curriculum.schema

Module-private schemas for Person 3 curriculum parsing and generation.
These schemas are internal to synapse.curriculum and are not part of the shared contracts.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RawExtractedConcept(BaseModel):
    """Raw concept item emitted by the LLM during concept extraction."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=500)
    prerequisites: list[str] = Field(default_factory=list)


class ConceptExtractionPayload(BaseModel):
    """Payload schema passed to slice.llm.complete for concept extraction."""

    model_config = ConfigDict(extra="forbid")

    concepts: list[RawExtractedConcept] = Field(min_length=1)


class RawGeneratedQuestion(BaseModel):
    """Raw MCQ item emitted by the LLM during test generation."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    concept_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_answer: str = Field(min_length=1, max_length=200)

    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list[str]) -> list[str]:
        cleaned = [opt.strip() for opt in v]
        if any(not opt for opt in cleaned):
            raise ValueError("Options must not be empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Options must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_answer(self) -> "RawGeneratedQuestion":
        if self.correct_answer.strip() not in self.options:
            raise ValueError("correct_answer must be one of options")
        return self


class TestGenerationPayload(BaseModel):
    """Structured response schema for test generation (exactly 3 MCQs)."""

    __test__ = False

    model_config = ConfigDict(extra="forbid")

    questions: list[RawGeneratedQuestion] = Field(min_length=3, max_length=3)

