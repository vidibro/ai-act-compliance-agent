"""The input cap — refusing a document before anything is spent on it."""

from __future__ import annotations

from pathlib import Path

import pytest

from aiact.classify import ScriptedBrain, classify
from aiact.classify.graph import QUESTIONS
from aiact.config import get_settings
from aiact.document import FULL_DOCUMENT_CALLS, DocumentTooLarge, check_size
from aiact.gap.roles import QUESTIONS as ROLE_QUESTIONS


def test_a_document_within_the_limit_passes_through_unchanged():
    document = "A system that scores job applicants."
    assert check_size(document) is document


def test_a_document_over_the_limit_is_refused():
    with pytest.raises(DocumentTooLarge):
        check_size("x" * 101, limit=100)


def test_the_limit_itself_is_allowed():
    assert check_size("x" * 100, limit=100)


def test_the_error_says_the_size_and_the_limit():
    with pytest.raises(DocumentTooLarge) as caught:
        check_size("x" * 500_000, limit=300_000)
    assert "500,000" in str(caught.value)
    assert "300,000" in str(caught.value)


def test_the_error_describes_no_internals():
    """The sender is not always the operator, and over HTTP is untrusted."""
    with pytest.raises(DocumentTooLarge) as caught:
        check_size("x" * 500_000, limit=300_000)
    message = str(caught.value)
    assert "AIACT_" not in message
    assert str(FULL_DOCUMENT_CALLS) not in message
    assert message.count(".") == 1 and len(message) < 120


def test_zero_disables_the_check():
    assert check_size("x" * 10_000_000, limit=0)


def test_the_default_limit_clears_every_document_in_the_golden_set():
    """A cap that refuses the measured corpus would surface only as a failed eval."""
    documents = list(Path("data/golden_set").rglob("*.md"))
    assert documents, "re-derive this test: the golden set has moved"
    largest = max(len(p.read_text(encoding="utf-8")) for p in documents)
    assert largest < get_settings().max_document_chars


def test_the_full_document_call_count_matches_the_questions_declared():
    assert FULL_DOCUMENT_CALLS == len(QUESTIONS) + len(ROLE_QUESTIONS)


def test_classify_refuses_before_the_cascade_runs(monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "1000")
    asked = []

    class CountingBrain(ScriptedBrain):
        def decide(self, question, description):
            asked.append(question.node_id)
            return super().decide(question, description)

    with pytest.raises(DocumentTooLarge):
        classify("x" * 1001, CountingBrain({}))
    assert asked == [], "the cascade ran before the document was refused"


def test_the_limit_is_configurable(monkeypatch):
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "50")
    with pytest.raises(DocumentTooLarge):
        check_size("x" * 51)
    monkeypatch.setenv("AIACT_MAX_DOCUMENT_CHARS", "100")
    assert check_size("x" * 51)
