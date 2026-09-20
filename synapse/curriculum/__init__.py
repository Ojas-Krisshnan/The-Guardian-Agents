# synapse/curriculum/__init__.py
"""Curriculum and Test Generation module (Person 3)."""
from __future__ import annotations

from .flow import (
    extract_concepts,
    generate_test,
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
)

__all__ = [
    "extract_concepts",
    "generate_test",
    "handle_teacher_setup",
    "handle_tag_confirmation",
    "handle_test_ready",
]
