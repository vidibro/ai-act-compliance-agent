"""Langfuse tracing — wired through LiteLLM, and a strict no-op without keys.

WHY IT LIVES HERE and not in the brain or the graph: tracing is cross-cutting bookkeeping, present
or absent, and neither the cascade logic nor the answer parsing should change shape depending on
whether an observability backend happens to be configured. So this module owns the whole decision —
"are we tracing?" and "what metadata does this call carry?" — and everything else calls into it.

THE NO-OP GUARANTEE. With no Langfuse keys in the environment (the default, and all of CI), every
function here short-circuits: `enable_tracing()` returns False and registers nothing, `trace_run()`
is a bare context manager, and `current_metadata()` returns None. No import of langfuse, no network,
no behavioural difference in a run — only the absence of a trace. This is what lets the
deterministic ScriptedBrain path and the test suite stay dependency- and key-free.

HOW THE GROUPING WORKS. One `classify()` run opens one `trace_run()` scope, which puts a trace id
and name in a ContextVar. Each node's LiteLLM call reads that via `current_metadata()` and passes
it as the call's `metadata`, tagged with the node id — so LiteLLM's Langfuse logger files each
generation under the SAME trace. The result in Langfuse is one trace per classified use case, its
spans being the cascade nodes in the order they fired: the decision path, visible.

A ContextVar (not a field on the brain) because the brain is shared across a run's nodes and, in
principle, across concurrent runs; the trace scope is per-run, so it belongs to the call context,
not the object.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# The Langfuse SDK / LiteLLM integration read these straight from the environment; they carry no
# AIACT_ prefix, so they are intentionally NOT part of Settings. Presence of BOTH keys is the single
# switch that turns tracing on.
_REQUIRED_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")

# Set once, the first time enable_tracing() finds keys, so the LiteLLM callback is registered
# exactly once per process no matter how many runs or brains are created.
_callback_registered = False

# The current run's trace context, or None when nothing is tracing. Holds what LiteLLM's Langfuse
# logger needs to group calls: a stable trace id, a human-readable name, and a session id.
_current: ContextVar[dict[str, str] | None] = ContextVar("aiact_trace", default=None)


def langfuse_configured() -> bool:
    """True only when BOTH keys are present and non-empty. A half-configured environment (one key,
    or a placeholder left as an empty string) counts as OFF — better a missing trace than a run that
    fails trying to reach a backend it cannot authenticate against."""
    return all(os.environ.get(k) for k in _REQUIRED_KEYS)


def enable_tracing() -> bool:
    """Register LiteLLM's Langfuse success callback, once, if keys are configured.

    Returns whether tracing is active, so a caller can log it. A no-op (returning False) when keys
    are absent, and idempotent when present — safe to call at the start of every run."""
    global _callback_registered
    if not langfuse_configured():
        return False
    if not _callback_registered:
        import litellm  # lazy: only when actually tracing

        # append, don't overwrite — a host application may have its own callbacks registered
        if "langfuse" not in (litellm.success_callback or []):
            litellm.success_callback = [*(litellm.success_callback or []), "langfuse"]
        _callback_registered = True
    return True


@contextmanager
def trace_run(name: str, session_id: str | None = None) -> Iterator[None]:
    """Open one trace scope for the duration of a classify() run.

    A bare no-op when tracing is off, so the deterministic path pays nothing. When on, it mints a
    trace id and publishes it (plus the run name and a session id) on the ContextVar for the run's
    LLM calls to pick up; the token is always reset, even on exception, so a failed run cannot leak
    its trace context into the next one."""
    if not enable_tracing():
        yield
        return
    context = {
        "trace_id": str(uuid.uuid4()),
        "trace_name": name,
        "session_id": session_id or name,
    }
    token = _current.set(context)
    try:
        yield
    finally:
        _current.reset(token)


def current_metadata(node_id: str) -> dict[str, str | list[str]] | None:
    """The `metadata` for one node's LiteLLM call, or None when not tracing.

    Shapes the keys the way LiteLLM's Langfuse logger expects: `trace_id` groups the call under the
    run's trace, `generation_name` labels the span with the cascade node, and `tags`/`session_id`
    make traces filterable in the Langfuse UI. None means 'add nothing', so the completion call is
    byte-identical to the untraced one."""
    context = _current.get()
    if context is None:
        return None
    return {
        "trace_id": context["trace_id"],
        "trace_name": context["trace_name"],
        "session_id": context["session_id"],
        "generation_name": node_id,
        "tags": ["aiact", "classification", node_id],
    }
