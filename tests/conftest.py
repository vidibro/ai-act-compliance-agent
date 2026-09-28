"""Test-wide environment isolation, and one parse of the committed corpus per session."""

from __future__ import annotations

import functools
import os
from pathlib import Path

import pytest

import aiact.norm_loader
import aiact.policy_loader
from aiact.config import get_settings

_TRACING_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "LANGFUSE_BASE_URL")
_DATA = Path(__file__).resolve().parents[1] / "data"


def _parse_once(load):
    """Parse the committed corpus once and hand every caller its own deep copy.

    Parsing and validating the norm inventory or the policy spec takes about two seconds and some
    test modules do it on every test; a deep copy takes milliseconds. A copy per call keeps tests
    isolated: one that edits its bundle cannot leak into the next. Only inputs under `data/` are
    cached, since tests never write there; a call on a temporary directory always reads fresh, so
    a test that rewrites its own fixture files and reloads sees the change.
    """
    parsed: dict[str, object] = {}

    @functools.wraps(load)
    def cached(*args, **kwargs):
        paths = [Path(value) for value in (*args, *kwargs.values()) if value is not None]
        if not all(path.resolve().is_relative_to(_DATA) for path in paths):
            return load(*args, **kwargs)
        key = repr((args, sorted(kwargs.items()), get_settings().model_dump()))
        if key not in parsed:
            parsed[key] = load(*args, **kwargs)
        return parsed[key].model_copy(deep=True)

    return cached


# Rebound before any test module imports them, so `from aiact... import load_...` gets the cache.
aiact.norm_loader.load_normative_coverage = _parse_once(aiact.norm_loader.load_normative_coverage)
aiact.policy_loader.load_policy_spec = _parse_once(aiact.policy_loader.load_policy_spec)


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
