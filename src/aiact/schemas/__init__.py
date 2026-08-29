"""Pydantic v2 schemas — the contract between all future components.

A verdict may never exist without its evidence and its legal source: LegalSource is a required,
default-less field on Answer and Finding, so an uncited assessment cannot be constructed.

Module layout, in dependency order:
    enums.py           the Regulation's own vocabulary — risk classes, roles, the points of Art. 5.
    policy.py          LegalSource, and the rules a document is checked against.
    question.py        one narrow legal question and its answer. Shared by BOTH askers: the
                       classification cascade and the gap layer's Art. 25 role question.
    classification.py  what the cascade adds up to — evidence, a use case, a risk class.
    report.py          what the gap layer adds up to — findings, and whose they are.
    system.py          the document under review.
    review.py          independent review provenance for assurance artifacts.
    interpretation.py  non-binding guidance links and their implementation targets.
    norm.py            exact source segments and atomic legal propositions.
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
from aiact.schemas.interpretation import (
    GuidanceReviewScope,
    InterpretationTarget,
    InterpretationTargetKind,
    InterpretiveEffect,
    InterpretiveLink,
)
from aiact.schemas.norm import (
    CandidateDetectionChannel,
    DependencyResolution,
    ImplementationMode,
    Norm,
    NormativeCoverageBundle,
    NormDependency,
    NormInventory,
    NormKind,
    NormSubject,
    ProductScope,
    SegmentDisposition,
    SegmentSource,
    SourceKind,
    SubjectCategory,
    TextReviewInventory,
    TextReviewSegment,
    VerificationMode,
)
from aiact.schemas.norm_review import (
    NormCandidate,
    NormCandidateRun,
)
from aiact.schemas.policy import GuidanceSource, LegalSource, PolicyRule, PolicyRuleset
from aiact.schemas.question import Answer, Question
from aiact.schemas.report import DISCLAIMER, ComplianceReport, Finding, ReportSummary
from aiact.schemas.review import ReviewRecord, ReviewStatus
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
    # normative-coverage assurance
    "ReviewStatus",
    "ReviewRecord",
    "GuidanceReviewScope",
    "InterpretationTarget",
    "InterpretationTargetKind",
    "InterpretiveEffect",
    "InterpretiveLink",
    "CandidateDetectionChannel",
    "DependencyResolution",
    "ImplementationMode",
    "Norm",
    "NormDependency",
    "NormInventory",
    "NormKind",
    "NormSubject",
    "NormativeCoverageBundle",
    "ProductScope",
    "SegmentDisposition",
    "SegmentSource",
    "SourceKind",
    "SubjectCategory",
    "TextReviewInventory",
    "TextReviewSegment",
    "VerificationMode",
    "NormCandidate",
    "NormCandidateRun",
    # policy
    "GuidanceSource",
    "LegalSource",
    "PolicyRule",
    "PolicyRuleset",
    # system
    "DocumentChunk",
    "SystemUnderReview",
    # the question/answer contract, shared by both askers
    "Question",
    "Answer",
    # classification
    "ClassificationResult",
    "ClassificationEvidence",
    "UseCaseClassification",
    # report
    "DISCLAIMER",
    "ComplianceReport",
    "Finding",
    "ReportSummary",
]
