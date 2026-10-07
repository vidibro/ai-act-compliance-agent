"""Everything a norm card shows, keyed by id so the browser can resolve references itself.

Norms keep their canonical shape (conditions and exceptions stay logical trees); the browser turns
them into sentences. Segments, regimes, rules and guidance are sent once and referenced by id.
"""

from __future__ import annotations

from typing import Any

from aiact.classify.graph import QUESTION_GUIDANCE, QUESTIONS
from aiact.guidance import DEFAULT_GUIDANCE_ROOT, load_snippet
from aiact.schemas.norm import NormativeCoverageBundle
from aiact.schemas.policy import PolicyRuleset


def _source_label(article: str | None, paragraph: str | None, annex: str | None) -> str:
    parts = []
    if article:
        parts.append(f"Art. {article}" + (f"({paragraph})" if paragraph else ""))
    if annex:
        parts.append(f"Annex {annex}")
    return ", ".join(parts)


def build_norm_cards(bundle: NormativeCoverageBundle, spec: PolicyRuleset) -> dict[str, Any]:
    inventory = bundle.norm_inventory

    norms = {
        norm.norm_id: norm.model_dump(
            mode="json", exclude={"act_version_date", "detection_channels"}
        )
        for norm in inventory.norms
    }
    relations = [relation.model_dump(mode="json") for relation in inventory.relations]
    regimes = {
        regime.regime_id: regime.model_dump(mode="json", exclude_none=True)
        for regime in inventory.temporal_regimes
    }

    snippet_refs = {ref for link in inventory.interpretations for ref in link.snippet_refs}
    snippet_refs |= {ref for rule in spec.rules for ref in rule.guidance_refs}
    snippet_refs |= {ref for refs in QUESTION_GUIDANCE.values() for ref in refs}
    snippets = {}
    for ref in sorted(snippet_refs):
        snippet = load_snippet(ref, DEFAULT_GUIDANCE_ROOT)
        snippets[ref] = {
            "document": snippet.document,
            "topic": snippet.topic,
            "locator": snippet.locator,
            "binding": snippet.binding,
            "body": snippet.body,
        }
    interpretations = [
        {
            "id": link.interpretation_id,
            "norm_ids": link.norm_ids,
            "snippet_refs": link.snippet_refs,
            "effect": link.effect.value,
            "explanation": link.effect_explanation,
            "targets": [target.target_id for target in link.targets],
            "status": link.review.status.value,
        }
        for link in inventory.interpretations
    ]

    rules = {
        rule.rule_id: {
            "action": rule.action,
            "requirement": rule.requirement,
            "evidence_expected": rule.evidence_expected,
            "check_type": str(rule.check_type),
            "document_verifiable": rule.document_verifiable,
            "activation_condition": rule.activation_condition,
            "qualified_by": [
                ", ".join(f"{key} {value}" for key, value in ref.items())
                for ref in rule.qualified_by
            ],
            "criteria": [criterion.norm_id for criterion in rule.criteria],
            "guidance_refs": list(rule.guidance_refs),
            "effective_date": str(rule.effective_date) if rule.effective_date else None,
            "roles": [str(role) for role in rule.applies_to_role],
            "risk_classes": [str(value) for value in rule.applies_to_risk_class],
            "transparency_duties": [str(value) for value in rule.applies_to_transparency_duty],
            "route": str(rule.applies_to_route) if rule.applies_to_route else None,
            "annex_iii_areas": [str(value) for value in rule.applies_to_annex_iii_area],
            "prohibited_practices": [str(value) for value in rule.applies_to_prohibited_practice],
            "requires_provider_reallocation": rule.requires_provider_reallocation,
            "requires_real_world_testing": rule.requires_real_world_testing,
            "effective_date_by_route": {
                str(route): str(day) for route, day in (rule.effective_date_by_route or {}).items()
            },
            "effective_date_note": rule.effective_date_note,
            "source": _source_label(rule.source.article, rule.source.paragraph, rule.source.annex),
        }
        for rule in spec.rules
    }

    # Classification questions in cascade order; norms reference them as AIA-CQ-<NODE>.
    questions = [
        {
            "id": f"AIA-CQ-{node.upper().replace('_', '-')}",
            "node": node,
            "label": question.label,
            "text": question.text.split("\n", 1)[0],
            "answer_type": question.answer_type,
            "source": _source_label(
                question.source.article, question.source.paragraph, question.source.annex
            ),
            "guidance_refs": list(QUESTION_GUIDANCE.get(node, ())),
        }
        for node, question in QUESTIONS.items()
    ]

    segments = {
        segment.segment_id: {
            "kind": segment.source.kind.value,
            "document": segment.source.document,
            "text": segment.text,
        }
        for segment in bundle.text_review.segments
        if segment.norm_ids or segment.qualifying_norm_ids
    }

    return {
        "norms": norms,
        "relations": relations,
        "regimes": regimes,
        "interpretations": interpretations,
        "snippets": snippets,
        "rules": rules,
        "questions": questions,
        "segments": segments,
    }
