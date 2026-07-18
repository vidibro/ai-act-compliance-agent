"""Pydantic v2 schemas — the contract between all future components.

A verdict may never exist without its evidence and its legal source: LegalSource is a required,
default-less field on NodeAnswer and Finding, so an uncited assessment cannot be constructed.
"""

from aiact.schemas.classification import (
    ClassificationResult,
    ClassificationState,
    NodeAnswer,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    CheckType,
    DerogationCondition,
    ObligationStatus,
    RiskClass,
    Verdict,
)
from aiact.schemas.eval import AblationType, Difficulty, GoldenCase, GoldenSet
from aiact.schemas.policy import LegalSource, PolicyRule, PolicySpec
from aiact.schemas.report import DISCLAIMER, ComplianceReport, Finding, ReportSummary
from aiact.schemas.system import DocumentChunk, SystemUnderReview

__all__ = [
    # enums — the Regulation's own semantics
    "ActorRole",
    "AnnexIIIArea",
    "CheckType",
    "DerogationCondition",
    "ObligationStatus",
    "RiskClass",
    "Verdict",
    # eval — our harness's vocabulary, NOT part of the Regulation
    "AblationType",
    "Difficulty",
    "GoldenCase",
    "GoldenSet",
    # policy
    "LegalSource",
    "PolicyRule",
    "PolicySpec",
    # system
    "DocumentChunk",
    "SystemUnderReview",
    # classification
    "ClassificationResult",
    "ClassificationState",
    "NodeAnswer",
    "UseCaseClassification",
    # report
    "DISCLAIMER",
    "ComplianceReport",
    "Finding",
    "ReportSummary",
]
