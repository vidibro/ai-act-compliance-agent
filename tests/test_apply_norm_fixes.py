"""The recorded-fix workflow must preserve every enforced audit gate."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

from aiact.norm_validity import AdjudicationScope, FieldValidation
from aiact.schemas.norm import SourceKind

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("apply_norm_fixes", SCRIPTS / "apply_norm_fixes.py")
apply_norm_fixes = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(apply_norm_fixes)


def test_refreshed_fix_audit_uses_the_ledger_validation_gates(tmp_path, monkeypatch):
    scope = AdjudicationScope(
        kind=SourceKind.ARTICLE,
        document="15",
        required_field_validations=[FieldValidation.LOGICAL_EXPRESSION_EVIDENCE],
    )
    requirements = apply_norm_fixes._required_field_validations(
        SimpleNamespace(enforced_scope=[scope])
    )
    assert requirements == {
        (SourceKind.ARTICLE, "15"): {FieldValidation.LOGICAL_EXPRESSION_EVIDENCE}
    }

    ledger_path = tmp_path / "adjudications"
    shard_path = ledger_path / "articles" / "015.yaml"
    shard_path.parent.mkdir(parents=True)
    (ledger_path / "index.yaml").write_text(
        yaml.safe_dump(
            {"shards": [{"kind": "article", "document": "15", "file": "articles/015.yaml"}]}
        ),
        encoding="utf-8",
    )
    shard_path.write_text(yaml.safe_dump({"audit": {"old": True}}), encoding="utf-8")
    ledger = SimpleNamespace(shard_scope_by_finding={"AIA-VALID-TEST": scope})
    captured = {}

    def fake_attestation(bundle, *, scope, required_field_validations):
        captured["bundle"] = bundle
        captured["scope"] = scope
        captured["required_field_validations"] = required_field_validations
        return SimpleNamespace(model_dump=lambda mode: {"refreshed": True})

    monkeypatch.setattr(apply_norm_fixes, "audit_attestation", fake_attestation)
    bundle = object()
    apply_norm_fixes._refresh_decision_shard_audit(
        ledger_path=ledger_path,
        ledger=ledger,
        finding_id="AIA-VALID-TEST",
        bundle=bundle,
        required_field_validations=requirements,
    )

    assert captured == {
        "bundle": bundle,
        "scope": {(SourceKind.ARTICLE, "15")},
        "required_field_validations": requirements,
    }
    assert yaml.safe_load(shard_path.read_text(encoding="utf-8"))["audit"] == {"refreshed": True}
