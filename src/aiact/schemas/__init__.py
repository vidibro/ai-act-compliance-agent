"""Pydantic v2 schemas — the contract between all future components.

A verdict may never exist without its evidence and its legal source: LegalSource is a required,
default-less field on Answer and Finding, so an uncited assessment cannot be constructed.

Module layout, in dependency order:
    enums.py           the Regulation's own vocabulary — risk classes, roles, the points of Art. 5.
    policy.py          LegalSource, and the rules a document is checked against.
    question.py        one narrow legal question and its answer, and nothing about a risk class.
    classification.py  what those answers add up to — evidence, a use case, a risk class.
    report.py          findings against the rules, and whose duty each one is.
    system.py          the document under review.
    eval.py            EVAL ONLY, and not part of the Regulation.
"""

from aiact.schemas.classification import (
    ClassificationEvidence,
    ClassificationResult,
    UseCaseClassification,
)
from aiact.schemas.enums import (
    ActorRole,
    AnnexIIIArea,
    CheckType,
    DerogationCondition,
    ObligationStatus,
    ProhibitedPractice,
    RiskClass,
    Verdict,
)
from aiact.schemas.eval import (
    AblationType,
    ClassificationCase,
    ClassificationGoldenSet,
    Difficulty,
    GoldenCase,
    GoldenSet,
)
from aiact.schemas.policy import GuidanceSource, LegalSource, PolicyRule, PolicySpec
from aiact.schemas.question import Answer, Question
from aiact.schemas.report import DISCLAIMER, ComplianceReport, Finding, ReportSummary
from aiact.schemas.system import DocumentChunk, SystemUnderReview

__all__ = [
    # enums — the Regulation's own semantics
    "ActorRole",
    "AnnexIIIArea",
    "CheckType",
    "DerogationCondition",
    "ProhibitedPractice",
    "ObligationStatus",
    "RiskClass",
    "Verdict",
    # eval — our harness's vocabulary, NOT part of the Regulation
    "AblationType",
    "Difficulty",
    "GoldenCase",
    "GoldenSet",
    "ClassificationCase",
    "ClassificationGoldenSet",
    # policy
    "GuidanceSource",
    "LegalSource",
    "PolicyRule",
    "PolicySpec",
    # system
    "DocumentChunk",
    "SystemUnderReview",
    # classification
    "ClassificationResult",
    "Answer",
    "ClassificationEvidence",
    "Question",
    "UseCaseClassification",
    # report
    "DISCLAIMER",
    "ComplianceReport",
    "Finding",
    "ReportSummary",
]
