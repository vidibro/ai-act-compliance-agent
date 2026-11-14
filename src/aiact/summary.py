"""The system's name and a short plain-language summary of what it does, for the top of a report.

The reader sees it before the classification. It is never input to the classification or the
obligation check: both read the document itself.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel

from aiact.config import get_settings
from aiact.llm.fencing import DATA_NOT_INSTRUCTIONS, fence, new_marker
from aiact.llm.json_reply import unfence
from aiact.providers import NO_THINKING, gateway_kwargs, profile_for
from aiact.usage import Usage

SUMMARY_MAX = 800
NAME_MAX = 120

_SYSTEM_PROMPT = (
    "You introduce AI system documentation at the top of a compliance report. Reply with a JSON "
    'object with two keys. "name": the system\'s name as the document gives it, or null if it '
    'gives none. "summary": two or three plain sentences saying what the system does, who it '
    "affects, and who uses its output. Use only what the document states; where it does not say, "
    "leave that out rather than guess. Give no legal assessment, no risk classification and no "
    "praise. Plain text only inside the strings: no headings, lists or Markdown.\n\n"
    + DATA_NOT_INSTRUCTIONS
)


class SystemSummary(BaseModel):
    name: str | None
    summary: str


class Summariser(Protocol):
    def summarise(self, document: str) -> SystemSummary | None: ...


class LLMSummariser:
    """Writes the name and summary with one completion, without extended thinking."""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or get_settings().llm_model
        self.profile = profile_for(self.model, NO_THINKING)
        # A caller's own key (bring-your-own-key), or None for the environment's.
        self._api_key = api_key
        self.usage = Usage()

    def summarise(self, document: str) -> SystemSummary | None:
        """The name and summary, or None when the reply carries no summary."""
        import litellm  # lazy: only needed when actually calling a model

        marker = new_marker(document)
        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "Summarise this documentation:\n"
                    + fence("DOCUMENT", document, marker),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
            **gateway_kwargs(self._api_key),
            **self.profile.completion_kwargs,
        )
        self.usage.record(response)
        raw = response.choices[0].message.content
        try:
            data = json.loads(unfence(raw)) if isinstance(raw, str) else None
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        summary = _clean(data.get("summary"), SUMMARY_MAX)
        if summary is None:
            return None
        return SystemSummary(name=_clean(data.get("name"), NAME_MAX), summary=summary)


def _clean(value: object, limit: int) -> str | None:
    """One line of text within `limit` characters, or None for anything else."""
    text = " ".join(value.split()) if isinstance(value, str) else ""
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
