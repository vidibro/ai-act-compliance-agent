"""A test run must never reach the operator's own observability backend."""

from __future__ import annotations

import os

from aiact import tracing

_TRACING_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def test_no_tracing_keys_are_present():
    assert not any(os.environ.get(k) for k in _TRACING_KEYS)


def test_importing_litellm_does_not_switch_tracing_on():
    """litellm calls load_dotenv on import, which finds the operator's .env by walking up. Deleting
    the keys in a fixture does not cover this: the import can happen mid-test and put them back."""
    import litellm  # noqa: F401

    assert tracing.langfuse_configured() is False


def test_enable_tracing_stays_a_noop():
    import litellm  # noqa: F401

    assert tracing.enable_tracing() is False
