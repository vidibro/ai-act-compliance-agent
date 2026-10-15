"""The plain-language explanations stored with the ruleset."""

from __future__ import annotations

from aiact.policy_loader import load_policy_spec
from aiact.report_app import explanations
from aiact.report_app.views import resolve_norms, resolve_rules


def test_every_row_has_an_explanation_of_its_current_wording():
    """A rule or norm added, or a paragraph whose wording changed, needs its explanation written
    again — `python scripts/write_explanations.py` writes exactly the missing and stale ones."""
    spec = load_policy_spec()
    version = str(spec.act_version_date)
    missing = [
        row_id
        for row_id, text in explanations.inputs(spec).items()
        if explanations.current(row_id, text, version) is None
    ]
    assert not missing, f"run scripts/write_explanations.py — no current explanation for {missing}"


def test_an_explanation_of_changed_wording_is_not_shown():
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-HR-A09")
    text = explanations.rule_input(rule)
    version = str(spec.act_version_date)

    assert explanations.current(rule.rule_id, text, version) is not None
    assert explanations.current(rule.rule_id, text + " amended", version) is None


def test_an_explanation_reaches_the_page():
    spec = load_policy_spec()
    rule = resolve_rules(["AIA-RULE-HR-A09"], [], spec)["AIA-RULE-HR-A09"]
    norm = resolve_norms(["AIA-NORM-A075C-P3-PROPOSE-COMMITMENTS"], spec)[
        "AIA-NORM-A075C-P3-PROPOSE-COMMITMENTS"
    ]

    for row in (rule, norm):
        assert row.explanation and len(row.explanation) <= explanations.EXPLANATION_MAX


def test_an_explanation_is_given_the_definition_its_provision_relies_on():
    """Art. 73(10) narrows reporting to serious incidents "referred to in Article 3, point
    (49)(c)". Given only the start of Art. 3 the model defined the term from memory, and wrongly;
    the cited definition itself must be in what it reads."""
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-RULE-ALL-A73-10")
    text = explanations.rule_input(rule)

    assert "‘serious incident’ means" in text
    assert "infringement of obligations under Union law intended to protect fundamental" in text
