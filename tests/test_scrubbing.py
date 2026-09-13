"""Credentials must not leave the process in a traceback or in trace metadata."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from aiact.scrubbing import REDACTED, install_excepthook, scrub, secret_values

KEY = "sk-ant-api03-NOTAREALKEYbutlongenough"


@pytest.fixture(autouse=True)
def _a_key_in_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-alsoasecretvalue")


def test_a_credential_named_variable_is_collected():
    assert KEY in secret_values()


def test_a_short_value_is_not_treated_as_a_credential(monkeypatch):
    """Redacting a two-character value would corrupt unrelated text."""
    monkeypatch.setenv("TINY_API_KEY", "no")
    assert "no" not in secret_values()


def test_an_ordinary_variable_is_not_collected(monkeypatch):
    monkeypatch.setenv("AIACT_LLM_MODEL", "anthropic/claude-haiku-4-5")
    assert "anthropic/claude-haiku-4-5" not in secret_values()


def test_the_key_is_redacted_from_text():
    assert KEY not in scrub(f"AuthenticationError: bad key {KEY} for anthropic")


def test_a_key_shape_is_redacted_even_when_not_in_the_environment():
    """A BYOK caller's key arrives on the request, so it is in no environment variable."""
    assert "sk-someoneelseskey123456" not in scrub("failed for sk-someoneelseskey123456")


def test_a_per_request_key_can_be_named_explicitly():
    byok = "hunter2-and-then-some"
    assert byok not in scrub(f"boom {byok}", byok)


def test_ordinary_text_survives():
    assert scrub("Article 6(3) derogation did not apply") == (
        "Article 6(3) derogation did not apply"
    )


def test_an_uncaught_traceback_is_scrubbed():
    """End to end in a real process, because the hook replaces sys.excepthook."""
    # The key reaches the child through the environment, never the source line: a traceback prints
    # the failing line, so a literal here would be reported as a leak the scrubber cannot cause.
    program = (
        "import os, sys;"
        "sys.path.insert(0, 'src');"
        "from aiact.scrubbing import install_excepthook;"
        "install_excepthook();"
        "raise RuntimeError('auth failed for ' + os.environ['ANTHROPIC_API_KEY'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        env={**os.environ, "ANTHROPIC_API_KEY": KEY},
    )
    assert KEY not in result.stderr
    assert REDACTED in result.stderr
    assert "RuntimeError" in result.stderr


def test_installing_twice_does_not_nest():
    original = sys.excepthook
    try:
        install_excepthook()
        once = sys.excepthook
        install_excepthook()
        assert sys.excepthook is once
    finally:
        sys.excepthook = original


@pytest.mark.parametrize(
    ("script", "argv", "stops_with"),
    [("classify", ["--help"], SystemExit), ("review", ["/nonexistent.md"], OSError)],
)
def test_the_cli_installs_the_hook_as_soon_as_dotenv_is_loaded(
    script, argv, stops_with, monkeypatch
):
    """load_dotenv puts the keys in the environment; nothing may raise between that and the hook."""
    import importlib
    import pathlib

    monkeypatch.syspath_prepend(str(pathlib.Path("scripts").resolve()))
    module = importlib.import_module(script)
    installed: list[bool] = []
    monkeypatch.setattr(module, "install_excepthook", lambda: installed.append(True))
    monkeypatch.setattr(sys, "argv", [script, *argv])
    with pytest.raises(stops_with):  # each script stops before doing any real work
        module.main()
    assert installed == [True]


def test_trace_metadata_carries_no_secret():
    """The promise SECURITY.md makes about the observability layer."""
    from aiact import tracing

    token = tracing._current.set({"trace_id": "t", "trace_name": "n", "session_id": "s"})
    try:
        metadata = tracing.current_metadata("annex_iii")
    finally:
        tracing._current.reset(token)
    assert metadata is not None
    flat = repr(metadata)
    for secret in secret_values():
        assert secret not in flat
