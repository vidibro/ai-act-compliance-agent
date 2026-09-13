"""Redacting credentials from anything on its way out of the process."""

from __future__ import annotations

import os
import re
import sys
import traceback
from types import TracebackType

REDACTED = "***REDACTED***"

_SECRET_NAME = re.compile(r"(API_KEY|SECRET_KEY|_TOKEN|PASSWORD|CREDENTIALS)$")

# Vendor key shapes, for a secret supplied per-request rather than through the environment.
_SECRET_SHAPE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|pk-lf-[A-Za-z0-9-]{8,}|gsk_[A-Za-z0-9]{8,})")

_MIN_LENGTH = 8
"""Below this a value is not a credential, and redacting it would corrupt unrelated text."""


def secret_values(environ: dict[str, str] | None = None) -> set[str]:
    """Every environment value whose NAME marks it as a credential."""
    env = os.environ if environ is None else environ
    return {
        value
        for name, value in env.items()
        if _SECRET_NAME.search(name) and len(value) >= _MIN_LENGTH
    }


def scrub(text: str, extra: object = None) -> str:
    """`text` with known and key-shaped secrets replaced. `extra` covers a per-request key."""
    for secret in sorted(secret_values(), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    if isinstance(extra, str) and len(extra) >= _MIN_LENGTH:
        text = text.replace(extra, REDACTED)
    return _SECRET_SHAPE.sub(REDACTED, text)


def install_excepthook() -> None:
    """Scrub uncaught tracebacks. Call from a CLI entry point; safe to call twice."""
    if getattr(sys.excepthook, "_aiact_scrubbing", False):
        return

    def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
        sys.stderr.write(scrub("".join(traceback.format_exception(kind, value, tb))))

    hook._aiact_scrubbing = True  # type: ignore[attr-defined]
    sys.excepthook = hook
