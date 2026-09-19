"""
Synapse curriculum domain package (Person 3).
Authoritative contract: Contracts.md Sections A.5, C.2, D.2, D.5, D.8.
"""
from synapse.curriculum.confirmation import (
    process_tag_confirmation,
    request_tag_confirmation,
)
from synapse.curriculum.extract import extract_concepts
from synapse.curriculum.flow import (
    handle_tag_confirmation,
    handle_teacher_setup,
    handle_test_ready,
    ingest_corpus,
)
from synapse.curriculum.test_generation import generate_test

__all__ = [
    "handle_teacher_setup",
    "handle_tag_confirmation",
    "handle_test_ready",
    "extract_concepts",
    "generate_test",
    "request_tag_confirmation",
    "process_tag_confirmation",
    "ingest_corpus",
]
