"""Article-level validity reconciliation keeps decisions and audit gates together."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from aiact.norm_validity import load_adjudication_ledger

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LEDGER = ROOT / "data/policy/normative-coverage/2026-07-27/adjudications"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location(
    "reconcile_article_adjudications", SCRIPTS / "reconcile_article_adjudications.py"
)
reconcile_article_adjudications = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = reconcile_article_adjudications
_spec.loader.exec_module(reconcile_article_adjudications)


def test_article_selection_keeps_decisions_in_their_declared_shard():
    ledger = load_adjudication_ledger(LEDGER)

    scope = reconcile_article_adjudications._article_scope(ledger, "18")
    decisions = reconcile_article_adjudications._decisions_for_scope(ledger, scope)

    assert scope.document == "18"
    assert decisions
    assert all(
        ledger.shard_scope_by_finding[decision.finding_id] == scope
        for decision in decisions
    )


def test_article_selection_refuses_an_article_outside_the_closed_scope():
    ledger = load_adjudication_ledger(LEDGER)

    with pytest.raises(ValueError, match="not in the enforced adjudication scope"):
        reconcile_article_adjudications._article_scope(ledger, "29")


def test_article_check_verifies_the_current_closed_build():
    reconcile_article_adjudications.check_article("2026-07-27", "15")
