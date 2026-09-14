"""Reload saved reports against the policy spec that defines their criteria.

A report is not self-describing: it records criteria that were reported, while the policy spec is
the authority for criteria that had to be reported. Use ``load_compliance_report`` for persisted
reports rather than calling ``ComplianceReport`` parsing methods directly.
"""

from __future__ import annotations

from pathlib import Path

from aiact.schemas.policy import PolicyRuleset
from aiact.schemas.report import ComplianceReport


def load_compliance_report(path: str | Path, spec: PolicyRuleset) -> ComplianceReport:
    """Load one JSON report and validate it against its authoritative policy ruleset.

    ``spec`` is required rather than loaded implicitly: the caller chooses the same pinned policy
    version used to create the report. The report schema then verifies every reported rule and its
    complete, ordered criterion list, plus every permission and legal-effect norm.
    """
    return ComplianceReport.model_validate_json(
        Path(path).read_bytes(), context={"policy_spec": spec}
    )
