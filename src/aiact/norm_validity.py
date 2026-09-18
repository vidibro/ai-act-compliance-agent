"""Deterministic norm-validity findings, adjudications, and exact fix patches.

The audit detects structural signals rather than deciding legal meaning. A versioned
adjudication ledger closes that loop: every finding in an enforced document must have one
source-hash-bound decision, and stale decisions fail validation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from aiact.schemas.norm import Norm, NormativeCoverageBundle, SourceKind, TemporalRegime

STRUCTURAL_PREFIX = re.compile(r"^\s*(?:Article\s+\S+\s*)?(?:\d+\.|\([a-z]+\))?\s*", re.I)
LEGAL_EFFECT = re.compile(
    r"\b(?:shall|must|may(?:\s+only)?|is required to|are required to|does not apply|"
    r"is without prejudice|are without prejudice|is deemed|are deemed)\b",
    re.I,
)
CONDITION = re.compile(
    r"\b(?:if|where|when|provided that|subject to|unless|only if|only where|in the event that)\b",
    re.I,
)
EXCEPTION = re.compile(r"\b(?:except|unless|without prejudice|derogation|does not apply)\b", re.I)
DEADLINE = re.compile(
    r"\b(?:by\s+\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|within\s+\d+|no later than|"
    r"without undue delay|immediately|at least\s+\d+)\b",
    re.I,
)
CALENDAR_DEADLINE = re.compile(r"\bby\s+\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\b", re.I)
RELATIVE_DEADLINE = re.compile(
    r"\b(?:within|not later than)\s+\d+\s+"
    r"(?:calendar\s+days?|hours?|days?|weeks?|months?|years?)\b",
    re.I,
)


class FieldValidation(StrEnum):
    """A staged field family that an adjudication scope has fully migrated."""

    ACTOR_EVIDENCE = "actor_evidence"
    TARGET_EVIDENCE = "target_evidence"
    TEMPORAL_REGIME = "temporal_regime"


class AdjudicationScope(BaseModel):
    kind: SourceKind
    document: str = Field(min_length=1)
    required_field_validations: list[FieldValidation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _field_validations_are_unique(self) -> AdjudicationScope:
        if len(self.required_field_validations) != len(set(self.required_field_validations)):
            raise ValueError("duplicate required_field_validations")
        return self


class LegalBasisQuote(BaseModel):
    """Exact source text supplying meaning omitted by a fragmentary norm quote."""

    span_id: str = Field(pattern=r"^AIA-TEXT-[A-Z0-9-]+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    quote: str = Field(min_length=1)


class FixReference(BaseModel):
    """Hash-bound reference from an adjudication to its exact text patch."""

    patch_file: str = Field(pattern=r"^fixes/AIA-VALID-[A-F0-9]{16}\.patch\.yaml$")
    patch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class TextReplacement(BaseModel):
    """One unambiguous exact-text substitution."""

    old: str = Field(min_length=1)
    new: str = Field(min_length=1)
    expected_occurrences: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _replacement_changes_text(self) -> TextReplacement:
        if self.old == self.new:
            raise ValueError("fix replacement old and new text must differ")
        return self


class NormFixPatch(BaseModel):
    """A reproducible patch against one canonical authoring file."""

    schema_version: Literal[1]
    finding_id: str = Field(pattern=r"^AIA-VALID-[A-F0-9]{16}$")
    target_file: str = Field(pattern=r"^source-records/(?:articles|annexes)/[^/]+\.yaml$")
    before_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replacements: list[TextReplacement] = Field(min_length=1)


class ValidityAdjudication(BaseModel):
    finding_id: str = Field(pattern=r"^AIA-VALID-[A-F0-9]{16}$")
    target: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    source_ref: str = Field(pattern=r"^AIA-TEXT-[A-Z0-9-]+$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["accepted_with_basis", "false_positive", "fixed"]
    reason: str = Field(min_length=1)
    legal_basis: list[LegalBasisQuote] = Field(default_factory=list)
    fix: FixReference | None = None
    reviewed_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _accepted_fragment_has_explicit_basis(self) -> ValidityAdjudication:
        if self.decision == "accepted_with_basis" and not self.legal_basis:
            raise ValueError("accepted_with_basis adjudication requires legal_basis")
        if self.decision == "fixed" and self.fix is None:
            raise ValueError("fixed adjudication requires fix")
        if self.decision != "fixed" and self.fix is not None:
            raise ValueError("only a fixed adjudication may reference a fix")
        return self


class AdjudicationShard(BaseModel):
    """One declared file of decisions for exactly one enacted document."""

    kind: SourceKind
    document: str = Field(min_length=1)
    file: str = Field(pattern=r"^(?:articles|annexes)/[^/]+\.yaml$")


class ValidityAdjudicationManifest(BaseModel):
    """The small index that declares the complete, closed set of decision shards."""

    schema_version: Literal[1]
    act_version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    enforced_scope: list[AdjudicationScope] = Field(min_length=1)
    shards: list[AdjudicationShard] = Field(min_length=1)

    @model_validator(mode="after")
    def _scope_and_shards_are_one_to_one(self) -> ValidityAdjudicationManifest:
        scopes = {(scope.kind, scope.document) for scope in self.enforced_scope}
        shard_scopes = {(shard.kind, shard.document) for shard in self.shards}
        if len(scopes) != len(self.enforced_scope):
            raise ValueError("duplicate validity adjudication scope")
        if len(shard_scopes) != len(self.shards):
            raise ValueError("duplicate validity adjudication shard scope")
        if scopes != shard_scopes:
            raise ValueError("validity adjudication shards must match enforced_scope exactly")
        files = [shard.file for shard in self.shards]
        if len(files) != len(set(files)):
            raise ValueError("duplicate validity adjudication shard file")
        return self


class ValidityAuditAttestation(BaseModel):
    """A reproducible record that a document's structural audit was actually run."""

    audit_schema_version: Literal[1]
    segments_scanned: int = Field(ge=0)
    norms_scanned: int = Field(ge=0)
    finding_count: int = Field(ge=0)
    audit_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidityAdjudicationShard(BaseModel):
    """The decisions for one article or annex, loaded only through the manifest."""

    schema_version: Literal[1]
    act_version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source: AdjudicationScope
    audit: ValidityAuditAttestation
    decisions: list[ValidityAdjudication] = Field(default_factory=list)

    @model_validator(mode="after")
    def _decisions_are_unique(self) -> ValidityAdjudicationShard:
        ids = [decision.finding_id for decision in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate validity adjudication finding_id in shard")
        return self


class ValidityAdjudicationLedger(BaseModel):
    act_version_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    enforced_scope: list[AdjudicationScope] = Field(min_length=1)
    decisions: list[ValidityAdjudication] = Field(default_factory=list)
    shard_scope_by_finding: dict[str, AdjudicationScope] = Field(default_factory=dict, exclude=True)
    audit_by_scope: dict[tuple[SourceKind, str], ValidityAuditAttestation] = Field(
        default_factory=dict, exclude=True
    )

    @model_validator(mode="after")
    def _decisions_are_unique(self) -> ValidityAdjudicationLedger:
        ids = [decision.finding_id for decision in self.decisions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate validity adjudication finding_id")
        scopes = [(scope.kind, scope.document) for scope in self.enforced_scope]
        if len(scopes) != len(set(scopes)):
            raise ValueError("duplicate validity adjudication scope")
        return self


@dataclass(frozen=True)
class ValidityFinding:
    finding_id: str
    target: str
    rule: str
    source_ref: str
    source_sha256: str
    target_sha256: str
    evidence: str

    def as_dict(self) -> dict[str, str]:
        return {
            "finding_id": self.finding_id,
            "target": self.target,
            "rule": self.rule,
            "source_ref": self.source_ref,
            "source_sha256": self.source_sha256,
            "target_sha256": self.target_sha256,
            "evidence": self.evidence,
        }


def _semantic_text(norm: Norm) -> str:
    dumped = norm.model_dump(mode="json")
    parts = [
        dumped["action"],
        json.dumps(dumped["conditions"], ensure_ascii=False),
        json.dumps(dumped["exceptions"], ensure_ascii=False),
        json.dumps(dumped["mandatory_content"], ensure_ascii=False),
        "[]",  # Legacy dependency payload, fixed empty after canonical relation migration.
    ]
    return " ".join(parts)


def _uncovered_text(text: str, quotes: list[str]) -> str:
    covered = [False] * len(text)
    for quote in quotes:
        start = text.find(quote)
        if start < 0:
            continue
        for index in range(start, start + len(quote)):
            covered[index] = True
    uncovered = "".join(
        character if not covered[index] else " " for index, character in enumerate(text)
    )
    return " ".join(STRUCTURAL_PREFIX.sub("", uncovered).split())


def _finding(
    *,
    target: str,
    rule: str,
    source_ref: str,
    source_sha256: str,
    target_sha256: str,
    evidence: str,
) -> ValidityFinding:
    identity = (f"{target}\0{rule}\0{source_ref}\0{source_sha256}\0{target_sha256}").encode()
    finding_id = f"AIA-VALID-{hashlib.sha256(identity).hexdigest()[:16].upper()}"
    return ValidityFinding(
        finding_id=finding_id,
        target=target,
        rule=rule,
        source_ref=source_ref,
        source_sha256=source_sha256,
        target_sha256=target_sha256,
        evidence=evidence,
    )


def _norm_sha256(norm: Norm) -> str:
    """Bind a finding to the fields this audit actually evaluates.

    Relation-graph and reporting metadata must not invalidate a legal-content adjudication.
    This deliberately selected payload is therefore a stable audit contract, rather than a dump
    of the evolving ``Norm`` schema.
    """
    canonical_norm = norm.model_dump(mode="json")
    payload = {
        "norm_id": norm.norm_id,
        "norm_text": norm.norm_text,
        "action": norm.action,
        "qualifier_spans": norm.qualifier_spans,
        "conditions": canonical_norm["conditions"],
        "exceptions": norm.exceptions,
        "mandatory_content": norm.mandatory_content,
        # Preserve the published adjudication hash contract while dependencies are represented
        # only by relations and therefore intentionally excluded from legal-content review.
        "dependencies": [],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _actor_basis_sha256(norm: Norm, actor_index: int) -> str:
    """Bind an actor-evidence finding to exactly one actor assignment."""
    actor = norm.actors[actor_index]
    payload = {
        "norm_id": norm.norm_id,
        "actor_ref": actor.actor_ref.value,
        "basis_segment_ids": actor.basis_segment_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _target_basis_sha256(norm: Norm, target_index: int) -> str:
    """Bind a target-evidence finding to exactly one target assignment."""
    target = norm.targets[target_index]
    payload = {
        "norm_id": norm.norm_id,
        "target_ref": target.target_ref,
        "target_kind": target.target_kind.value,
        "basis_segment_ids": target.basis_segment_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _temporal_assignment_sha256(norm: Norm, regime: TemporalRegime) -> str:
    """Bind a timing finding to one norm's selected, source-backed regime."""
    payload = {
        "norm_id": norm.norm_id,
        "temporal_regime_id": norm.temporal_regime_id,
        "regime": regime.canonical_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _actor_term_is_in_text(term: str, text: str) -> bool:
    """Match one declared legal label, allowing normal whitespace and a final plural ``s``."""
    escaped = re.escape(term).replace(r"\ ", r"[\s-]+")
    return re.search(rf"\b{escaped}s?\b", text, re.I) is not None


def _enacted_date(value) -> str:
    return f"{value.day} {value.strftime('%B')} {value.year}"


def _contains_exact_words(text: str, fragment: str) -> bool:
    return " ".join(fragment.split()).casefold() in " ".join(text.split()).casefold()


def _requires_calendar_deadline(norm: Norm) -> bool:
    return CALENDAR_DEADLINE.search(norm.norm_text) is not None


def _requires_relative_deadline(norm: Norm) -> bool:
    return RELATIVE_DEADLINE.search(norm.norm_text) is not None


def _new_field_findings(
    bundle: NormativeCoverageBundle,
    *,
    scope: set[tuple[SourceKind, str]] | None,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]] | None,
) -> list[ValidityFinding]:
    """Audit populated actor-evidence and timing fields without requiring their migration yet.

    Empty new fields are deliberately not findings: the existing inventory is being migrated in
    controlled batches. Once a field is populated, however, every deterministic check below is
    enforced and its exact value becomes part of the audit attestation.
    """
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    regimes = {regime.regime_id: regime for regime in bundle.norm_inventory.temporal_regimes}
    findings: list[ValidityFinding] = []
    for norm in bundle.norm_inventory.norms:
        primary = segments[norm.primary_spans[0]]
        if scope is not None and (primary.source.kind, primary.source.document) not in scope:
            continue
        requirements = (required_field_validations or {}).get(
            (primary.source.kind, primary.source.document), set()
        )
        for actor_index, actor in enumerate(norm.actors):
            if (
                FieldValidation.ACTOR_EVIDENCE in requirements
                and not actor.basis_segment_ids
            ):
                findings.append(
                    _finding(
                        target=f"{norm.norm_id}:actor:{actor.actor_ref.value}",
                        rule="actor_basis_missing",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=_actor_basis_sha256(norm, actor_index),
                        evidence=norm.norm_text,
                    )
                )
            for basis_segment_id in actor.basis_segment_ids:
                basis = segments[basis_segment_id]
                if any(
                    _actor_term_is_in_text(term, basis.text)
                    for term in actor.actor_ref.legal_reference_terms
                ):
                    continue
                findings.append(
                    _finding(
                        target=(
                            f"{norm.norm_id}:actor:{actor.actor_ref.value}:{basis_segment_id}"
                        ),
                        rule="actor_basis_does_not_name_actor",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=_actor_basis_sha256(norm, actor_index),
                        evidence=basis.text,
                    )
                )

        for target_index, target_item in enumerate(norm.targets):
            if (
                FieldValidation.TARGET_EVIDENCE in requirements
                and not target_item.basis_segment_ids
            ):
                findings.append(
                    _finding(
                        target=f"{norm.norm_id}:target:{target_item.target_ref}",
                        rule="target_basis_missing",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=_target_basis_sha256(norm, target_index),
                        evidence=norm.norm_text,
                    )
                )
            for basis_segment_id in target_item.basis_segment_ids:
                basis = segments[basis_segment_id]
                if _contains_exact_words(basis.text, target_item.target_ref):
                    continue
                findings.append(
                    _finding(
                        target=(
                            f"{norm.norm_id}:target:{target_item.target_ref}:{basis_segment_id}"
                        ),
                        rule="target_basis_does_not_name_target",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=_target_basis_sha256(norm, target_index),
                        evidence=basis.text,
                    )
                )

        requires_calendar_deadline = _requires_calendar_deadline(norm)
        requires_relative_deadline = _requires_relative_deadline(norm)
        if norm.temporal_regime_id is None:
            if FieldValidation.TEMPORAL_REGIME in requirements:
                target_sha256 = hashlib.sha256(
                    json.dumps(
                        {
                            "norm_id": norm.norm_id,
                            "temporal_regime_id": None,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
                findings.append(
                    _finding(
                        target=f"{norm.norm_id}:temporal",
                        rule=(
                            "temporal_deadline_regime_missing"
                            if requires_calendar_deadline or requires_relative_deadline
                            else "temporal_regime_missing"
                        ),
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=target_sha256,
                        evidence=norm.norm_text,
                    )
                )
            continue
        regime = regimes[norm.temporal_regime_id]
        basis_text = "\n".join(segments[span].text for span in regime.legal_basis_spans)
        target = f"{norm.norm_id}:temporal:{regime.regime_id}"
        target_sha256 = _temporal_assignment_sha256(norm, regime)
        for label, value in (
            ("temporal_application_start_not_in_basis", regime.application_start),
            ("temporal_application_end_not_in_basis", regime.application_end),
            ("temporal_deadline_not_in_basis", regime.deadline),
        ):
            if value is not None and not _contains_exact_words(basis_text, _enacted_date(value)):
                findings.append(
                    _finding(
                        target=target,
                        rule=label,
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=target_sha256,
                        evidence=basis_text,
                    )
                )
        if (
            FieldValidation.TEMPORAL_REGIME in requirements
            and requires_calendar_deadline
            and regime.deadline is None
        ):
            findings.append(
                _finding(
                    target=target,
                    rule="temporal_calendar_deadline_missing",
                    source_ref=primary.segment_id,
                    source_sha256=primary.sha256,
                    target_sha256=target_sha256,
                    evidence=norm.norm_text,
                )
            )
        if (
            FieldValidation.TEMPORAL_REGIME in requirements
            and requires_relative_deadline
            and regime.relative_deadline is None
        ):
            findings.append(
                _finding(
                    target=target,
                    rule="temporal_relative_deadline_missing",
                    source_ref=primary.segment_id,
                    source_sha256=primary.sha256,
                    target_sha256=target_sha256,
                    evidence=norm.norm_text,
                )
            )
        if regime.relative_deadline is not None:
            relative = regime.relative_deadline
            if not _contains_exact_words(basis_text, relative.enacted_period):
                findings.append(
                    _finding(
                        target=target,
                        rule="temporal_relative_deadline_not_in_basis",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=target_sha256,
                        evidence=basis_text,
                    )
                )
            if not _contains_exact_words(basis_text, relative.trigger):
                findings.append(
                    _finding(
                        target=target,
                        rule="temporal_deadline_trigger_not_in_basis",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=target_sha256,
                        evidence=basis_text,
                    )
                )
        for condition in regime.timing_conditions:
            if not _contains_exact_words(basis_text, condition):
                findings.append(
                    _finding(
                        target=f"{target}:condition:{condition}",
                        rule="temporal_condition_not_in_basis",
                        source_ref=primary.segment_id,
                        source_sha256=primary.sha256,
                        target_sha256=target_sha256,
                        evidence=basis_text,
                    )
                )
    return findings


def _bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_coverage_path(root: Path, relative: str, *, prefix: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"unsafe validity path: {relative}")
    if not relative_path.parts or relative_path.parts[0] != prefix:
        raise ValueError(f"validity path must be below {prefix}/: {relative}")
    resolved_root = root.resolve()
    resolved = (root / relative_path).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"validity path escapes coverage root: {relative}")
    return resolved


def _coverage_root(ledger_path: Path) -> Path:
    """The coverage-version root for either a legacy ledger file or a shard directory."""
    return ledger_path.parent


def _replace_exact(content: str, patch: NormFixPatch, *, reverse: bool = False) -> str:
    replacements = list(reversed(patch.replacements)) if reverse else patch.replacements
    for replacement in replacements:
        old, new = (
            (replacement.new, replacement.old) if reverse else (replacement.old, replacement.new)
        )
        actual = content.count(old)
        if actual != replacement.expected_occurrences:
            direction = "reverse" if reverse else "forward"
            raise ValueError(
                f"{patch.finding_id} {direction} patch expected "
                f"{replacement.expected_occurrences} occurrence(s), found {actual}"
            )
        content = content.replace(old, new)
    return content


def load_fix_patch(
    ledger_path: Path,
    decision: ValidityAdjudication,
) -> tuple[NormFixPatch, Path]:
    """Load a decision's patch and validate its location and content hash."""
    if decision.fix is None:
        raise ValueError(f"validity adjudication {decision.finding_id} has no fix")
    root = _coverage_root(ledger_path)
    patch_path = _safe_coverage_path(root, decision.fix.patch_file, prefix="fixes")
    if not patch_path.is_file():
        raise ValueError(f"validity fix patch is missing: {patch_path}")
    payload = patch_path.read_bytes()
    if _bytes_sha256(payload) != decision.fix.patch_sha256:
        raise ValueError(f"validity fix patch hash is stale: {decision.fix.patch_file}")
    patch = NormFixPatch.model_validate(yaml.safe_load(payload))
    if patch.finding_id != decision.finding_id:
        raise ValueError(
            f"validity fix patch {decision.fix.patch_file} belongs to {patch.finding_id}, "
            f"not {decision.finding_id}"
        )
    return patch, patch_path


def verify_applied_fix(ledger_path: Path, decision: ValidityAdjudication) -> Path:
    """Prove the current canonical file is exactly the recorded patch result."""
    patch, _ = load_fix_patch(ledger_path, decision)
    target_path = _safe_coverage_path(
        _coverage_root(ledger_path), patch.target_file, prefix="source-records"
    )
    if not target_path.is_file():
        raise ValueError(f"validity fix target is missing: {target_path}")
    current = target_path.read_bytes()
    if _bytes_sha256(current) != patch.after_sha256:
        raise ValueError(
            f"validity fix {decision.finding_id} is not applied to {patch.target_file}"
        )
    try:
        current_text = current.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"validity fix target is not UTF-8: {patch.target_file}") from exc
    reconstructed = _replace_exact(current_text, patch, reverse=True).encode()
    if _bytes_sha256(reconstructed) != patch.before_sha256:
        raise ValueError(
            f"validity fix {decision.finding_id} cannot reconstruct its declared preimage"
        )
    if _replace_exact(reconstructed.decode(), patch).encode() != current:
        raise ValueError(f"validity fix {decision.finding_id} does not round-trip exactly")
    return target_path


def apply_recorded_fix(ledger_path: Path, finding_id: str) -> tuple[Path, bool]:
    """Apply one reviewed patch, refusing any unrecorded starting content.

    Returns the canonical target and whether it was changed. An already-applied patch is
    accepted, which makes the operation safe to repeat.
    """
    ledger = load_adjudication_ledger(ledger_path)
    decision = next((item for item in ledger.decisions if item.finding_id == finding_id), None)
    if decision is None:
        raise ValueError(f"unknown validity finding: {finding_id}")
    if decision.decision != "fixed":
        raise ValueError(f"validity finding {finding_id} is not adjudicated as fixed")
    patch, _ = load_fix_patch(ledger_path, decision)
    target_path = _safe_coverage_path(
        _coverage_root(ledger_path), patch.target_file, prefix="source-records"
    )
    if not target_path.is_file():
        raise ValueError(f"validity fix target is missing: {target_path}")
    before = target_path.read_bytes()
    current_sha256 = _bytes_sha256(before)
    if current_sha256 == patch.after_sha256:
        verify_applied_fix(ledger_path, decision)
        return target_path, False
    if current_sha256 != patch.before_sha256:
        raise ValueError(
            f"validity fix {finding_id} refuses unexpected preimage for {patch.target_file}"
        )
    try:
        after = _replace_exact(before.decode("utf-8"), patch).encode()
    except UnicodeDecodeError as exc:
        raise ValueError(f"validity fix target is not UTF-8: {patch.target_file}") from exc
    if _bytes_sha256(after) != patch.after_sha256:
        raise ValueError(f"validity fix {finding_id} produced an unexpected result hash")
    target_path.write_bytes(after)
    verify_applied_fix(ledger_path, decision)
    return target_path, True


def audit_norm_validity(
    bundle: NormativeCoverageBundle,
    *,
    scope: set[tuple[SourceKind, str]] | None = None,
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]] | None = None,
) -> list[ValidityFinding]:
    """Return stable, source-bound structural findings in deterministic order."""
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    norms_by_source: dict[str, list[Norm]] = {}
    for norm in bundle.norm_inventory.norms:
        source_ref = norm.primary_spans[0]
        source = segments[source_ref].source
        if scope is not None and (source.kind, source.document) not in scope:
            continue
        norms_by_source.setdefault(source_ref, []).append(norm)

    findings: list[ValidityFinding] = []
    for source_ref, norms in sorted(norms_by_source.items()):
        segment = segments[source_ref]
        if segment.disposition.value != "normative":
            continue
        uncovered = _uncovered_text(segment.text, [norm.norm_text for norm in norms])
        if uncovered and LEGAL_EFFECT.search(uncovered):
            linked_quotes = json.dumps(
                sorted((norm.norm_id, norm.norm_text) for norm in norms),
                separators=(",", ":"),
                ensure_ascii=False,
            )
            findings.append(
                _finding(
                    target=source_ref,
                    rule="uncovered_legal_effect_text",
                    source_ref=source_ref,
                    source_sha256=segment.sha256,
                    target_sha256=hashlib.sha256(linked_quotes.encode()).hexdigest(),
                    evidence=uncovered,
                )
            )

    for source_ref, norms in sorted(norms_by_source.items()):
        segment = segments[source_ref]
        for norm in sorted(norms, key=lambda item: item.norm_id):
            semantic = _semantic_text(norm)
            quote = norm.norm_text.lstrip()
            rules: list[str] = []
            if quote and quote[0].islower() and not norm.qualifier_spans:
                rules.append("fragment_without_qualifier_span")
            if (
                CONDITION.search(norm.norm_text)
                and not norm.conditions
                and not CONDITION.search(norm.action)
            ):
                rules.append("condition_not_structured_or_retained_in_action")
            if (
                EXCEPTION.search(norm.norm_text)
                and not norm.exceptions
                and not EXCEPTION.search(semantic)
            ):
                rules.append("exception_not_structured_or_retained")
            if DEADLINE.search(norm.norm_text) and not DEADLINE.search(semantic):
                rules.append("deadline_not_structured_or_retained")
            for rule in rules:
                findings.append(
                    _finding(
                        target=norm.norm_id,
                        rule=rule,
                        source_ref=source_ref,
                        source_sha256=segment.sha256,
                        target_sha256=_norm_sha256(norm),
                        evidence=norm.norm_text,
                    )
                )

    findings.extend(
        _new_field_findings(
            bundle,
            scope=scope,
            required_field_validations=required_field_validations,
        )
    )
    return sorted(findings, key=lambda item: (item.source_ref, item.target, item.rule))


def _populated_field_snapshot(
    bundle: NormativeCoverageBundle,
    *,
    scope: set[tuple[SourceKind, str]],
) -> dict[str, object]:
    """Return only new-field values that have actually been migrated into the inventory.

    Omitting empty lists keeps existing Article adjudications valid while their records have no
    actor evidence or temporal regime yet. A migrated value, by contrast, is hash-bound from its
    first audit onward.
    """
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    regimes = {regime.regime_id: regime for regime in bundle.norm_inventory.temporal_regimes}
    actor_assignments: list[dict[str, object]] = []
    target_assignments: list[dict[str, object]] = []
    temporal_assignments: list[dict[str, object]] = []
    for norm in sorted(bundle.norm_inventory.norms, key=lambda item: item.norm_id):
        primary = segments[norm.primary_spans[0]]
        if (primary.source.kind, primary.source.document) not in scope:
            continue
        for actor in norm.actors:
            if actor.basis_segment_ids:
                actor_assignments.append(
                    {
                        "norm_id": norm.norm_id,
                        "actor_ref": actor.actor_ref.value,
                        "basis_segment_ids": actor.basis_segment_ids,
                    }
                )
        for target in norm.targets:
            if target.basis_segment_ids:
                target_assignments.append(
                    {
                        "norm_id": norm.norm_id,
                        "target_ref": target.target_ref,
                        "target_kind": target.target_kind.value,
                        "basis_segment_ids": target.basis_segment_ids,
                    }
                )
        if norm.temporal_regime_id is not None:
            temporal_assignments.append(
                {
                    "norm_id": norm.norm_id,
                    "temporal_regime_id": norm.temporal_regime_id,
                    "regime": regimes[norm.temporal_regime_id].canonical_payload(),
                }
            )
    snapshot: dict[str, object] = {}
    if actor_assignments:
        snapshot["actor_assignments"] = actor_assignments
    if target_assignments:
        snapshot["target_assignments"] = target_assignments
    if temporal_assignments:
        snapshot["temporal_assignments"] = temporal_assignments
    return snapshot


def audit_attestation(
    bundle: NormativeCoverageBundle,
    *,
    scope: set[tuple[SourceKind, str]],
    required_field_validations: dict[tuple[SourceKind, str], set[FieldValidation]] | None = None,
) -> ValidityAuditAttestation:
    """Return the exact, hash-bound result of one deterministic structural audit.

    A document with zero findings still needs this record. Otherwise an empty `decisions` list
    cannot distinguish “audited cleanly” from “never audited”. The snapshot binds every scanned
    segment and the legal-content fields of every scanned norm, so a later edit requires a fresh
    audit even when the heuristic happens to produce zero findings again.
    """
    segments = [
        segment
        for segment in bundle.text_review.segments
        if (segment.source.kind, segment.source.document) in scope
    ]
    segments_by_id = {segment.segment_id: segment for segment in segments}
    norms = [
        norm
        for norm in bundle.norm_inventory.norms
        if (segments_by_id.get(norm.primary_spans[0]) is not None)
    ]
    findings = audit_norm_validity(
        bundle,
        scope=scope,
        required_field_validations=required_field_validations,
    )
    snapshot = {
        "audit_schema_version": 1,
        "segments": [
            {"segment_id": segment.segment_id, "sha256": segment.sha256}
            for segment in sorted(segments, key=lambda item: item.segment_id)
        ],
        "norms": [
            {"norm_id": norm.norm_id, "sha256": _norm_sha256(norm)}
            for norm in sorted(norms, key=lambda item: item.norm_id)
        ],
        "findings": [finding.as_dict() for finding in findings],
    }
    populated_fields = _populated_field_snapshot(bundle, scope=scope)
    if populated_fields:
        snapshot["populated_field_validation"] = populated_fields
    sorted_requirements = sorted(
        (required_field_validations or {}).items(),
        key=lambda item: (item[0][0].value, item[0][1]),
    )
    scoped_requirements = {
        f"{kind.value}/{document}": sorted(requirement.value for requirement in requirements)
        for (kind, document), requirements in sorted_requirements
        if (kind, document) in scope and requirements
    }
    if scoped_requirements:
        snapshot["required_field_validations"] = scoped_requirements
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ValidityAuditAttestation(
        audit_schema_version=1,
        segments_scanned=len(segments),
        norms_scanned=len(norms),
        finding_count=len(findings),
        audit_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
    )


def _load_yaml(path: Path, *, description: str) -> dict:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {description}: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be a YAML mapping: {path}")
    return payload


def _safe_shard_path(root: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError(f"unsafe validity adjudication shard path: {relative}")
    if len(relative_path.parts) != 2 or relative_path.parts[0] not in {"articles", "annexes"}:
        raise ValueError(
            f"validity adjudication shard must be below articles/ or annexes/: {relative}"
        )
    if relative_path.suffix != ".yaml":
        raise ValueError(f"validity adjudication shard must be YAML: {relative}")
    return root / relative_path


def load_adjudication_ledger(path: Path) -> ValidityAdjudicationLedger:
    """Load a manifest-declared directory of decision shards as one logical ledger.

    A legacy single YAML file is accepted only for temporary fixtures and older callers. Versioned
    coverage uses the directory form, which refuses undeclared or missing shard files.
    """
    if path.is_file():
        return ValidityAdjudicationLedger.model_validate(_load_yaml(path, description="ledger"))
    if not path.is_dir():
        raise ValueError(f"validity adjudication ledger is missing: {path}")

    index_path = path / "index.yaml"
    if not index_path.is_file():
        raise ValueError(f"validity adjudication manifest is missing: {index_path}")
    manifest = ValidityAdjudicationManifest.model_validate(
        _load_yaml(index_path, description="validity adjudication manifest")
    )
    declared = {_safe_shard_path(path, shard.file) for shard in manifest.shards}
    actual = {candidate for candidate in path.rglob("*.yaml") if candidate != index_path}
    missing = sorted(declared - actual)
    unexpected = sorted(actual - declared)
    if missing or unexpected:
        details = [
            *(f"missing {item}" for item in missing),
            *(f"undeclared {item}" for item in unexpected),
        ]
        raise ValueError(
            "validity adjudication shard set differs from manifest: " + "; ".join(details)
        )

    decisions: list[ValidityAdjudication] = []
    shard_scope_by_finding: dict[str, AdjudicationScope] = {}
    audit_by_scope: dict[tuple[SourceKind, str], ValidityAuditAttestation] = {}
    manifest_scope_by_address = {
        (scope.kind, scope.document): scope for scope in manifest.enforced_scope
    }
    for declared_shard in sorted(manifest.shards, key=lambda item: item.file):
        shard_path = _safe_shard_path(path, declared_shard.file)
        shard = ValidityAdjudicationShard.model_validate(
            _load_yaml(shard_path, description="validity adjudication shard")
        )
        if shard.act_version_date != manifest.act_version_date:
            raise ValueError(
                f"validity adjudication shard version differs from manifest: {shard_path}"
            )
        expected_scope = manifest_scope_by_address[(declared_shard.kind, declared_shard.document)]
        if shard.source != expected_scope:
            raise ValueError(
                f"validity adjudication shard source differs from manifest: {shard_path}"
            )
        audit_by_scope[(shard.source.kind, shard.source.document)] = shard.audit
        for decision in shard.decisions:
            if decision.finding_id in shard_scope_by_finding:
                raise ValueError(
                    "duplicate validity adjudication finding_id across shards: "
                    f"{decision.finding_id}"
                )
            decisions.append(decision)
            shard_scope_by_finding[decision.finding_id] = shard.source
    return ValidityAdjudicationLedger(
        act_version_date=manifest.act_version_date,
        enforced_scope=manifest.enforced_scope,
        decisions=decisions,
        shard_scope_by_finding=shard_scope_by_finding,
        audit_by_scope=audit_by_scope,
    )


def enforce_validity_adjudications(
    bundle: NormativeCoverageBundle,
    ledger_path: Path,
) -> tuple[int, int]:
    """Require one current decision for every active finding in the ledger's scope."""
    ledger = load_adjudication_ledger(ledger_path)
    version = bundle.text_review.act_version_date.isoformat()
    if ledger.act_version_date != version:
        raise ValueError(
            f"validity adjudication ledger uses Act version {ledger.act_version_date}, "
            f"coverage uses {version}"
        )
    scope = {(item.kind, item.document) for item in ledger.enforced_scope}
    required_field_validations = {
        (item.kind, item.document): set(item.required_field_validations)
        for item in ledger.enforced_scope
    }
    for item in ledger.enforced_scope:
        document_scope = {(item.kind, item.document)}
        recorded_audit = ledger.audit_by_scope.get((item.kind, item.document))
        if recorded_audit is None:
            raise ValueError(
                f"validity adjudication {item.kind.value}/{item.document} lacks audit attestation"
            )
        current_audit = audit_attestation(
            bundle,
            scope=document_scope,
            required_field_validations=required_field_validations,
        )
        if recorded_audit != current_audit:
            raise ValueError(
                f"validity audit attestation is stale for {item.kind.value}/{item.document}"
            )
    findings = audit_norm_validity(
        bundle,
        scope=scope,
        required_field_validations=required_field_validations,
    )
    findings_by_id = {finding.finding_id: finding for finding in findings}
    decisions_by_id = {decision.finding_id: decision for decision in ledger.decisions}
    segments = {segment.segment_id: segment for segment in bundle.text_review.segments}
    for decision in ledger.decisions:
        segment = segments.get(decision.source_ref)
        if segment is None:
            raise ValueError(
                f"validity adjudication {decision.finding_id} references unknown source "
                f"{decision.source_ref}"
            )
        if (segment.source.kind, segment.source.document) not in scope:
            raise ValueError(
                f"validity adjudication {decision.finding_id} is outside enforced scope"
            )
        declared_shard_scope = ledger.shard_scope_by_finding.get(decision.finding_id)
        if declared_shard_scope is not None and (
            segment.source.kind,
            segment.source.document,
        ) != (declared_shard_scope.kind, declared_shard_scope.document):
            raise ValueError(
                f"validity adjudication {decision.finding_id} is filed under "
                f"{declared_shard_scope.kind.value}/{declared_shard_scope.document}, but its "
                f"source belongs to {segment.source.kind.value}/{segment.source.document}"
            )
        if segment.sha256 != decision.source_sha256:
            raise ValueError(
                f"validity adjudication {decision.finding_id} source hash no longer matches"
            )
        expected_id = _finding(
            target=decision.target,
            rule=decision.rule,
            source_ref=decision.source_ref,
            source_sha256=decision.source_sha256,
            target_sha256=decision.target_sha256,
            evidence="",
        ).finding_id
        if decision.finding_id != expected_id:
            raise ValueError(
                f"validity adjudication {decision.finding_id} no longer matches its bound identity"
            )
    missing = sorted(set(findings_by_id) - set(decisions_by_id))
    active_fixed = sorted(
        finding_id
        for finding_id in findings_by_id
        if decisions_by_id.get(finding_id) is not None
        and decisions_by_id[finding_id].decision == "fixed"
    )
    stale = sorted(
        finding_id
        for finding_id, decision in decisions_by_id.items()
        if decision.decision != "fixed" and finding_id not in findings_by_id
    )
    if missing:
        raise ValueError(f"validity findings lack adjudication: {missing}")
    if active_fixed:
        raise ValueError(f"validity findings adjudicated as fixed are still active: {active_fixed}")
    if stale:
        raise ValueError(f"validity adjudications are stale or no longer produced: {stale}")

    active_signatures = {(finding.target, finding.rule, finding.source_ref) for finding in findings}
    for decision in ledger.decisions:
        if decision.decision != "fixed":
            continue
        signature = (decision.target, decision.rule, decision.source_ref)
        if signature in active_signatures:
            raise ValueError(
                f"validity fix {decision.finding_id} did not remove its target/rule finding"
            )
        verify_applied_fix(ledger_path, decision)

    for finding_id, finding in findings_by_id.items():
        decision = decisions_by_id[finding_id]
        compared = {
            "target": (decision.target, finding.target),
            "rule": (decision.rule, finding.rule),
            "source_ref": (decision.source_ref, finding.source_ref),
            "source_sha256": (decision.source_sha256, finding.source_sha256),
            "target_sha256": (decision.target_sha256, finding.target_sha256),
        }
        mismatched = [name for name, (declared, actual) in compared.items() if declared != actual]
        if mismatched:
            raise ValueError(
                f"validity adjudication {finding_id} no longer matches its finding: {mismatched}"
            )
        for basis in decision.legal_basis:
            segment = segments.get(basis.span_id)
            if segment is None:
                raise ValueError(
                    f"validity adjudication {finding_id} references unknown basis {basis.span_id}"
                )
            if basis.source_sha256 != segment.sha256:
                raise ValueError(
                    f"validity adjudication {finding_id} basis source hash is stale for "
                    f"{basis.span_id}"
                )
            if basis.quote not in segment.text:
                raise ValueError(
                    f"validity adjudication {finding_id} basis quote is not exact in "
                    f"{basis.span_id}: {basis.quote!r}"
                )
    return len(findings), len(ledger.decisions)
