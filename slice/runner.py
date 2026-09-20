"""
The state machine. Deterministic code, not a model, decides what happens next.

Use a model for JUDGEMENT INSIDE a step. Use code for SEQUENCING BETWEEN steps.
A model that picks its own next action is unbounded in cost and unauditable
afterwards, because the control flow is different on every run.

This module knows nothing about theses, gates or evidence. It knows how to move
a run through states, how to stop, and how to resume. The domain lives in
demo/flow.py - which is the file you rewrite for your own problem.

Resume is free: `advance()` simply runs again. There is no separate resume
path to keep in sync, because a suspended run is just a run in a state whose
handler happens to be "wait".
"""
from __future__ import annotations

from typing import Any, Callable, Protocol

from . import callback
from .budget import Budget, BudgetExceeded
from .config import Settings
from .llm import CapExhausted, ModelError, PoolExhausted
from .records import RunState
from .store import Store

# A handler takes the context and returns the state to move to next.
Handler = Callable[["Context"], Any]


class Context:
    """Everything a step needs, assembled once."""

    def __init__(self, store: Store, run_id: str, settings: Settings):
        self.store, self.run_id, self.settings = store, run_id, settings
        self.budget = Budget(store, run_id, settings)

    # convenience passthroughs so handlers read cleanly
    def latest(self, kind): return self.store.latest(self.run_id, kind)
    def history(self, kind): return self.store.history(self.run_id, kind)
    def append(self, kind, payload, produced_by):
        return self.store.append(self.run_id, kind, payload, produced_by)


class Flow(Protocol):
    """What a domain must provide. See demo/flow.py."""
    name: str
    handlers: dict[Any, Handler]
    state_type: Any = None


def advance(store: Store, run_id: str, flow: Flow, settings: Settings,
            max_steps: int = 40) -> Any:
    """Run until the run is finished, suspended, or out of budget.

    Call it again later to resume. `max_steps` is a fence on the state machine
    itself - a domain with a cycle in it should stop, not spin.
    """
    callback.sweep(store, run_id)          # expire stale questions first
    ctx = Context(store, run_id, settings)
    state_type = getattr(flow, "state_type", None)

    for _ in range(max_steps):
        state = store.get_state(run_id, state_type=state_type) if state_type is not None else store.get_state(run_id)

        if getattr(state, "is_terminal", False):
            return state
        if getattr(state, "is_suspended", False):
            return state                    # waiting on a human: nothing to do

        handler = flow.handlers.get(state)
        if handler is None and hasattr(state, "value"):
            handler = flow.handlers.get(state.value)
        if handler is None:
            val = getattr(state, "value", str(state))
            return _fail(ctx, "no_handler", f"No handler for state {val}.", state, state_type)

        try:
            nxt = handler(ctx)
        except (BudgetExceeded, PoolExhausted, CapExhausted, ModelError) as e:
            k = "budget" if isinstance(e, BudgetExceeded) else ("pool_exhausted" if isinstance(e, PoolExhausted) else ("cap_exhausted" if isinstance(e, CapExhausted) else "model"))
            return _fail(ctx, k, str(e), state, state_type)

        if nxt is not state and nxt != state:
            store.set_state(run_id, nxt)
        elif getattr(nxt, "is_suspended", False) or getattr(nxt, "is_terminal", False):
            store.set_state(run_id, nxt)
        else:
            val = getattr(state, "value", str(state))
            return _fail(ctx, "no_progress",
                         f"Handler for {val} returned its own state without "
                         "suspending. That is a loop; fix the handler.", state, state_type)

    cur = store.get_state(run_id, state_type=state_type) if state_type is not None else store.get_state(run_id)
    return _fail(ctx, "max_steps", f"Did not settle within {max_steps} steps.", cur, state_type)


def _fail(ctx: Context, kind: str, detail: str,
          current_state: Any = None, state_type: Any = None) -> Any:
    """Record WHY a run stopped, in the history, where a replay will show it.
    A run that fails without leaving a reason is the thing you cannot debug."""
    ctx.append("failure", {"kind": kind, "detail": detail}, produced_by="runner")
    try:
        ctx.store.update_meta(ctx.run_id, {"error": detail})
    except Exception:
        pass
    if state_type is not None:
        if hasattr(state_type, "FAILED"):
            failed = getattr(state_type, "FAILED")
            ctx.store.set_state(ctx.run_id, failed)
            return failed
        return current_state if current_state is not None else ctx.store.get_state(ctx.run_id, state_type=state_type)
    ctx.store.set_state(ctx.run_id, RunState.FAILED)
    return RunState.FAILED
