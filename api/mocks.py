"""Mock dependencies for deterministic run advancement."""
from __future__ import annotations

from typing import Any
from demo.smoke.flow import build_flow
from demo.smoke.stub import Stub


def get_mock_flow():
    """Return a deterministic Flow instance backed by Stub canned responses."""
    return build_flow(call=Stub())
