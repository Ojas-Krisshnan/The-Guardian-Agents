"""
synapse.curriculum.stub

Canned model responses for keyless testing of concept extraction and test generation.
Drop-in replacement for slice.llm.complete.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel

_FIXTURES = Path(__file__).parent / "fixtures"
_EXPECTED_CONCEPTS_PATH = _FIXTURES / "expected_concepts.json"

if _EXPECTED_CONCEPTS_PATH.exists():
    _expected = json.loads(_EXPECTED_CONCEPTS_PATH.read_text(encoding="utf-8"))
    _raw_items = [
        {"name": c["name"], "summary": c["summary"], "prerequisites": c.get("prerequisites", [])}
        for c in _expected
    ]
    DEFAULT_CONCEPTS_JSON = json.dumps({"concepts": _raw_items})
else:
    DEFAULT_CONCEPTS_JSON = """{
  "concepts": [
    {
      "name": "Recursion",
      "summary": "Function calling itself to solve sub-problems until a base case",
      "prerequisites": []
    },
    {
      "name": "Base Case",
      "summary": "Terminating condition preventing infinite recursion",
      "prerequisites": ["Recursion"]
    },
    {
      "name": "Recursive Case",
      "summary": "Step that reduces problem size toward base case",
      "prerequisites": ["Recursion", "Base Case"]
    },
    {
      "name": "Termination",
      "summary": "Guarantee that recursive calls monotonically reach a base case",
      "prerequisites": ["Base Case", "Recursive Case"]
    }
  ]
}"""

_EXPECTED_TEST_PATH = _FIXTURES / "expected_test_questions.json"
if _EXPECTED_TEST_PATH.exists():
    _expected_test = json.loads(_EXPECTED_TEST_PATH.read_text(encoding="utf-8"))
    DEFAULT_TEST_JSON = json.dumps({"questions": _expected_test["questions"]})
else:
    DEFAULT_TEST_JSON = """{
  "questions": [
    {
      "concept_id": "c1000000-0000-0000-0000-000000000001",
      "text": "What is the defining operational mechanism of a recursive function?",
      "options": [
        "It solves a problem by having a subroutine call itself on smaller instances of the same problem",
        "It replaces all loop structures by mutating global state variables across threads",
        "It precomputes all future return values in a static lookup table at compile time",
        "It executes every branch simultaneously using asynchronous worker pools"
      ],
      "correct_answer": "It solves a problem by having a subroutine call itself on smaller instances of the same problem"
    },
    {
      "concept_id": "c1000000-0000-0000-0000-000000000001",
      "text": "Why must every recursive algorithm include a reachable base case?",
      "options": [
        "To provide a direct non-recursive termination condition and prevent unbounded stack allocation",
        "To allow the garbage collector to reclaim inactive heap memory before function execution begins",
        "To ensure the function signature matches the standard library interface specification",
        "To convert the call stack frames into an explicit heap-allocated singly linked list"
      ],
      "correct_answer": "To provide a direct non-recursive termination condition and prevent unbounded stack allocation"
    },
    {
      "concept_id": "c1000000-0000-0000-0000-000000000001",
      "text": "What happens to the program call stack during the recursive execution before reaching the base case?",
      "options": [
        "Each active invocation pushes a new stack frame containing its local variables and return address",
        "The operating system replaces the stack with a queue that executes in first-in first-out order",
        "Previous stack frames are automatically overwritten by the newest invocation to conserve memory",
        "All local variables are promoted to global storage to prevent re-instantiation"
      ],
      "correct_answer": "Each active invocation pushes a new stack frame containing its local variables and return address"
    }
  ]
}"""

_EXPECTED_BINARY_SEARCH_TEST_PATH = _FIXTURES / "expected_test_questions_binary_search.json"
if _EXPECTED_BINARY_SEARCH_TEST_PATH.exists():
    _expected_bs = json.loads(_EXPECTED_BINARY_SEARCH_TEST_PATH.read_text(encoding="utf-8"))
    BINARY_SEARCH_TEST_JSON = json.dumps({"questions": _expected_bs["questions"]})
else:
    BINARY_SEARCH_TEST_JSON = DEFAULT_TEST_JSON


class CurriculumStub:
    """A drop-in for slice.llm.complete with canned responses for curriculum steps.

    Enables testing Person 3 concept extraction, teacher tag confirmation,
    and MCQ test generation deterministically with zero API keys and zero network.
    """

    def __init__(
        self,
        responses: dict[str, list[Any]] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.responses: dict[str, list[Any]] = responses or {
            "concept_extraction": [DEFAULT_CONCEPTS_JSON],
            "test_generation": [DEFAULT_TEST_JSON],
        }
        self._counts: dict[str, int] = {}

    def reset(self) -> None:
        """Reset call history and invocation counters."""
        self.calls.clear()
        self._counts.clear()

    def __call__(
        self,
        *,
        settings: Any = None,
        budget: Any = None,
        messages: list[dict],
        schema: Type[BaseModel] | None = None,
        model: str | None = None,
        step: str = "call",
        timeout: float = 120.0,
    ) -> Any:
        base = step.split(":")[0]
        idx = self._counts.get(base, 0)
        self._counts[base] = idx + 1
        self.calls.append(step)

        if base in self.responses and idx < len(self.responses[base]):
            raw = self.responses[base][idx]
        elif base in self.responses and self.responses[base]:
            raw = self.responses[base][-1]
        else:
            raw = "{}"

        # If using default canned test, adapt concept_id to target concept in messages
        if base == "test_generation" and raw == DEFAULT_TEST_JSON and messages:
            import re
            target_id = None
            for m in messages:
                match = re.search(r"\(id:\s*([^)]+)\)", m.get("content", ""))
                if match:
                    target_id = match.group(1).strip()
                    break
            if target_id and target_id != "c1000000-0000-0000-0000-000000000001":
                raw = raw.replace("c1000000-0000-0000-0000-000000000001", target_id)

        if budget is not None:
            if hasattr(budget, "check_tokens"):
                budget.check_tokens()
            if hasattr(budget, "record_tokens"):
                token_count = len(str(raw)) // 4
                budget.record_tokens(max(1, token_count))

        if schema is not None:
            if isinstance(raw, schema):
                return raw
            if isinstance(raw, dict):
                return schema.model_validate(raw)
            if isinstance(raw, str):
                return schema.model_validate_json(raw)
            return schema.model_validate(raw)

        if isinstance(raw, (dict, list)):
            return json.dumps(raw)
        return str(raw)
