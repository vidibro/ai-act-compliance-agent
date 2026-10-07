"""Reading the summary reply. The model call is faked; only the parsing is under test."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aiact.summary import NAME_MAX, SUMMARY_MAX, LLMSummariser


def reply(content: object) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)


@pytest.fixture
def answer(monkeypatch):
    import litellm

    def set_reply(content: object) -> None:
        monkeypatch.setattr(litellm, "completion", lambda **kwargs: reply(content))

    return set_reply


def test_name_and_summary_are_read_from_the_reply(answer):
    answer('{"name": "TalentRank", "summary": "Scores job applicants."}')
    result = LLMSummariser(model="anthropic/claude-haiku-4-5").summarise("doc")

    assert result is not None
    assert result.name == "TalentRank"
    assert result.summary == "Scores job applicants."


def test_a_fenced_reply_is_read(answer):
    answer('```json\n{"name": null, "summary": "Scores job applicants."}\n```')
    result = LLMSummariser(model="anthropic/claude-haiku-4-5").summarise("doc")

    assert result is not None
    assert result.name is None


@pytest.mark.parametrize("content", [None, "", "not json", "[1, 2]", '{"name": "X"}'])
def test_a_reply_without_a_summary_gives_none(answer, content):
    answer(content)
    assert LLMSummariser(model="anthropic/claude-haiku-4-5").summarise("doc") is None


def test_long_values_are_clipped(answer):
    answer(f'{{"name": "{"n" * 500}", "summary": "{"s" * 2000}"}}')
    result = LLMSummariser(model="anthropic/claude-haiku-4-5").summarise("doc")

    assert result is not None
    assert result.name is not None and len(result.name) == NAME_MAX
    assert len(result.summary) == SUMMARY_MAX
