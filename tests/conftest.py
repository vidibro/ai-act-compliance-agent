"""Test-wide environment isolation."""

from __future__ import annotations

import os

import pytest

_TRACING_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "LANGFUSE_BASE_URL")


@pytest.fixture(autouse=True, scope="session")
def _never_load_a_dotenv_file():
    """litellm calls load_dotenv on import, which walks UP from site-packages and finds the
    operator's own .env — so a test run would trace to their real Langfuse project."""
    import dotenv

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
        yield


@pytest.fixture(autouse=True)
def _no_tracing_keys(_never_load_a_dotenv_file):
    """Second net, for keys already in the environment when pytest started."""
    import aiact.tracing as tracing

    for key in _TRACING_KEYS:
        os.environ.pop(key, None)
    tracing._callback_registered = False
    yield
