"""
synapse.curriculum

PERSON 3 — Curriculum & Test Generation Engineer.

Owns:
1. Concept extraction from canonical notes (handle_teacher_setup, extract_concepts)
2. Teacher tag confirmation via callback (handle_tag_confirmation, get_pending_tags, submit_teacher_confirmation)
3. MCQ test generation from confirmed concepts (handle_test_ready)
4. Tests/stubs/fixtures for these components
"""
from .flow import (
    extract_concepts,
    generate_stable_concept_id,
    generate_test,
    get_pending_tags,
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
    submit_teacher_confirmation,
)
from .stub import (
    BINARY_SEARCH_TEST_JSON,
    DEFAULT_CONCEPTS_JSON,
    DEFAULT_TEST_JSON,
    CurriculumStub,
)

__all__ = [
    "BINARY_SEARCH_TEST_JSON",
    "DEFAULT_CONCEPTS_JSON",
    "DEFAULT_TEST_JSON",
    "CurriculumStub",
    "extract_concepts",
    "generate_stable_concept_id",
    "generate_test",
    "get_pending_tags",
    "handle_tag_confirmation",
    "handle_teacher_setup",
    "handle_test_ready",
    "submit_teacher_confirmation",
]
