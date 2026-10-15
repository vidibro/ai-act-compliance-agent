"""Plain-language explanations of the report's rows, written once and stored with the ruleset.

A row's own words are the Act's — its paragraph, and the provisions that paragraph cites — and a
reader who does not know what a "structured dialogue" or "Article 75b commitments" are learns
nothing from them. Each row therefore carries one or two plain sentences saying what it means.

They are written by a model ONCE, by `scripts/write_explanations.py`, from exactly the text the row
shows, and stored in data/policy/explanations/<act version>.yaml. Never at review time: the same
row reads the same way in every report, and a reviewer can check every sentence before it is shown
as settled. Each entry records a fingerprint of the text it was written from, so an explanation of
wording that has since changed is not shown, and `verified_by` is the user's sign-off.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from aiact.config import get_settings
from aiact.llm.json_reply import unfence
from aiact.providers import NO_THINKING, gateway_kwargs, profile_for
from aiact.report_app.law import (
    article_of,
    cited_definitions,
    paragraph_text,
    provision,
    references,
)
from aiact.schemas.policy import PolicyRule, PolicyRuleset, ReportNorm
from aiact.usage import Usage

EXPLANATIONS_ROOT = Path("data/policy/explanations")  # relative to the working directory
EXPLANATION_MAX = 600
_REFERENCE_CHARS = 2500  # of each cited provision, enough for what it is about

_SYSTEM_PROMPT = (
    "You explain one provision of the EU AI Act (Regulation (EU) 2024/1689) to a business reader "
    "with no legal training, for a compliance report. You get the provision as the Act words it, "
    "the parties it binds, and the text of any other provision it refers to. Reply with a JSON "
    'object with one key, "explanation": one to three short sentences, at most 60 words, saying '
    "in everyday words who must or may do what, and when it matters. Explain any term or "
    "referenced provision the reader needs, using only the texts given. Name the party (the "
    'provider, the deployer, the AI Office) rather than writing "you". Add nothing the texts do '
    "not say: no obligation, deadline, exception or definition of your own, no advice, no "
    "opinion. If a term is not explained in the texts, use it without defining it — never define "
    "it from your own knowledge. No article numbers unless the reader needs one. Plain text only: "
    "no headings, lists or Markdown."
)


class Explanation(BaseModel):
    text: str
    source_sha256: str
    """Fingerprint of the input it was written from; a mismatch means the wording has changed."""
    model: str
    written_at: date
    verified_by: str | None = None


def rule_input(rule: PolicyRule) -> str:
    """What a duty row shows, as the model gets it."""
    parts = [
        f"Provision: Art. {rule.source.article}"
        + (f"({rule.source.paragraph})" if rule.source.paragraph else ""),
        f"Binds: {', '.join(role.value.replace('_', ' ') for role in rule.applies_to_role)}",
        f"Short title: {rule.action or ''}",
        f"The Act says:\n{rule.requirement}",
    ]
    if rule.activation_condition:
        parts.append(f"Applies only to: {rule.activation_condition}")
    return "\n\n".join(parts + _referenced(rule.requirement, str(rule.source.article or "")))


def norm_input(norm: ReportNorm) -> str:
    """What a permission, right, effect or limitation row shows, as the model gets it."""
    from aiact.reporting import condition_text  # local: reporting imports the report schemas

    law = "\n\n".join(dict.fromkeys(t for span in norm.source_spans if (t := paragraph_text(span))))
    parts = [
        f"Kind: {norm.kind.value.replace('_', ' ')}",
        f"Concerns: {', '.join(actor.replace('_', ' ') for actor in norm.actors) or 'everyone'}",
        f"Short title: {norm.action}",
        f"The Act says:\n{law or norm.norm_text}",
    ]
    if norm.conditions:
        parts.append(f"Only if: {condition_text(norm.conditions)}")
    if norm.exceptions:
        parts.append(f"Except: {condition_text(norm.exceptions)}")
    return "\n\n".join(parts + _referenced(law, article_of(norm.source_spans)))


def _referenced(text: str, own: str | None) -> list[str]:
    # A definition cited by its point is given whole; the start of Art. 3 would not contain it.
    found = [f"Definition it relies on (Art. 3):\n{d}" for d in cited_definitions(text)]
    for ref in references(text, own):
        if ref.key == "3" and found:
            continue
        full = provision(ref.key)
        body = (full.text if full else "")[:_REFERENCE_CHARS]
        found.append(f"Referenced provision {ref.citation} ({ref.title}):\n{body}")
    return found


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inputs(spec: PolicyRuleset) -> dict[str, str]:
    """Every row a report can show, by id, with the input its explanation is written from."""
    rows = {rule.rule_id: rule_input(rule) for rule in spec.rules}
    rows.update({norm.norm_id: norm_input(norm) for norm in spec.report_norms})
    return rows


def path_for(version: date | str) -> Path:
    return EXPLANATIONS_ROOT / f"{version}.yaml"


@lru_cache(maxsize=4)
def load(version: str) -> dict[str, Explanation]:
    """The stored explanations for one act version; empty when none are written yet."""
    path = path_for(version)
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {key: Explanation(**value) for key, value in (payload.get("explanations") or {}).items()}


def save(version: date | str, explanations: dict[str, Explanation]) -> None:
    path = path_for(version)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "act_version_date": str(version),
        "explanations": {
            key: explanations[key].model_dump(mode="json") for key in sorted(explanations)
        },
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    load.cache_clear()


def current(row_id: str, row_input: str, version: date | str) -> Explanation | None:
    """The stored explanation for a row, or None where there is none or its wording changed."""
    found = load(str(version)).get(row_id)
    return found if found and found.source_sha256 == fingerprint(row_input) else None


class LLMExplainer:
    """Writes one explanation with one completion, without extended thinking."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or get_settings().llm_model
        self.profile = profile_for(self.model, NO_THINKING)
        self.usage = Usage()

    def explain(self, row_input: str) -> str | None:
        import litellm  # lazy: only needed when actually calling a model

        response = litellm.completion(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": row_input},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
            **gateway_kwargs(),
            **self.profile.completion_kwargs,
        )
        self.usage.record(response)
        raw = response.choices[0].message.content
        try:
            data = json.loads(unfence(raw)) if isinstance(raw, str) else None
        except json.JSONDecodeError:
            return None
        text = data.get("explanation") if isinstance(data, dict) else None
        text = " ".join(text.split()) if isinstance(text, str) else ""
        return text[:EXPLANATION_MAX] or None
