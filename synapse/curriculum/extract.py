"""
Concept extraction from teacher-authored canonical notes.
Authoritative contract: Contracts.md Sections C.2, D.2, D.5.
"""
from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

from slice.budget import Budget
from slice.config import Settings
from slice.llm import complete
from slice.records import new_id
from synapse.schemas import ConceptNode


class ExtractedConcept(BaseModel):
    name: str
    summary: str
    prerequisites: list[str] = Field(default_factory=list)


class ConceptExtractionSchema(BaseModel):
    concepts: list[ExtractedConcept]


def _deterministic_extract(markdown: str, concept_name: str | None = None) -> list[ConceptNode]:
    """Deterministic fallback parser extracting concepts from markdown structure."""
    nodes: list[ConceptNode] = []
    
    # 1. Match headings: ## Concept Name\nSummary text
    heading_pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    matches = list(heading_pattern.finditer(markdown))
    
    if matches:
        for i, match in enumerate(matches):
            name = match.group(2).strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            body = markdown[start_pos:end_pos].strip()
            summary = body.split("\n\n")[0].strip() if body else f"Key concept for {name}"
            # Extract any wiki-link prerequisites [[Prerequisite]]
            prereqs = re.findall(r'\[\[(.*?)\]\]', body)
            nodes.append(
                ConceptNode(
                    id=new_id(),
                    name=name,
                    summary=summary[:300],
                    prerequisites=prereqs,
                )
            )
    else:
        # Fallback to single primary concept if no markdown headers exist
        primary_name = concept_name or "Core Concept"
        nodes.append(
            ConceptNode(
                id=new_id(),
                name=primary_name,
                summary=markdown.strip()[:300] if markdown.strip() else f"Overview of {primary_name}",
                prerequisites=[],
            )
        )
    return nodes


def extract_concepts(
    markdown: str,
    concept_name: str | None = None,
    settings: Settings | None = None,
    budget: Budget | None = None,
) -> list[ConceptNode]:
    """Extract ConceptNode instances from canonical note markdown."""
    if not markdown or not markdown.strip():
        return [
            ConceptNode(
                id=new_id(),
                name=concept_name or "Untitled Concept",
                summary="Empty note",
                prerequisites=[],
            )
        ]

    # If settings and budget are present with an API key, call slice.llm.complete
    if settings and budget and settings.api_key:
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Extract key educational concepts from the following curriculum note. "
                        "For each concept provide its name, concise summary, and prerequisites if mentioned."
                    ),
                },
                {"role": "user", "content": f"Topic: {concept_name or ''}\n\nNote:\n{markdown}"},
            ]
            result = complete(
                settings=settings,
                budget=budget,
                messages=messages,
                schema=ConceptExtractionSchema,
                step="curriculum:extract_concepts",
            )
            if isinstance(result, ConceptExtractionSchema) and result.concepts:
                return [
                    ConceptNode(
                        id=new_id(),
                        name=c.name,
                        summary=c.summary,
                        prerequisites=c.prerequisites,
                    )
                    for c in result.concepts
                ]
        except Exception:
            # Fall back to deterministic extraction on any model failure
            pass

    return _deterministic_extract(markdown, concept_name)
