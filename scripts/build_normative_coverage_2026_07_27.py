# ruff: noqa: E501
"""Build exact normative-coverage artifacts from reviewed normative source records.

The source record list is deliberately proposition-first. It does not discover norms by counting modal
verbs; it records an exact enacted quote for each proposed legal effect, then tags the channels
that would also have found it. The generated artifacts are validated independently of runtime use.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from aiact.norm_loader import load_normative_coverage
from aiact.norm_metrics import measure_normative_coverage, render_coverage_markdown
from aiact.policy_loader import article_filename, load_policy_spec, source_body
from aiact.text_segments import corpus_documents

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-07-27"
ARTICLES = ROOT / "data" / "policy" / "articles" / VERSION
ANNEXES = ROOT / "data" / "policy" / "annexes" / VERSION
TEXT_OUTPUT = ROOT / "data" / "policy" / "text-review-2026-07-27.yaml"
NORM_OUTPUT = ROOT / "data" / "policy" / "norms-2026-07-27.yaml"
REPORT_OUTPUT = ROOT / "docs" / "NORMATIVE-COVERAGE-REPORT-2026-07-27.md"


@dataclass(frozen=True)
class Division:
    label: str
    marker: str | None
    disposition: str
    reason: str = ""


@dataclass(frozen=True)
class Document:
    kind: str
    number: str
    divisions: tuple[Division, ...]


@dataclass(frozen=True)
class NormSourceRecord:
    norm_id: str
    source: str
    quote: str
    action: str
    subject_ref: str
    subject_category: str
    kind: str = "obligation"
    product_scope: str = "in_scope"
    product_scope_reason: str = ""
    implementation_refs: tuple[str, ...] = ()
    implementation_mode: str | None = None
    implementation_reason: str = ""
    verification_mode: str | None = None
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    mandatory_content: tuple[str, ...] = ()
    dependencies: tuple[tuple[str, str, str], ...] = ()
    qualifier_spans: tuple[str, ...] = ()
    effective_date_spans: tuple[str, ...] = ()


def div(label: str, marker: str | None, disposition: str, reason: str = "") -> Division:
    return Division(label, marker, disposition, reason)


NEEDS = "Not yet semantically extracted; retained as explicit review debt."
SAVING = "Saving clause preserves other law but creates no independent product-facing action."

REVIEWED_DOCUMENTS = (
    Document(
        "article",
        "11",
        (
            div("HEAD", None, "structural"),
            div("P1", "1. ", "normative"),
            div("P2", "2. ", "needs_review", NEEDS),
            div("P3", "3. ", "normative"),
        ),
    ),
    Document(
        "article",
        "26",
        (
            div("HEAD", None, "structural"),
            *(
                div(
                    f"P{i}",
                    f"{i}. ",
                    "normative" if i == 5 else "needs_review",
                    "" if i == 5 else NEEDS,
                )
                for i in range(1, 13)
            ),
        ),
    ),
    Document(
        "article",
        "43",
        (
            div("HEAD", None, "structural"),
            div("P1", "1. ", "needs_review", NEEDS),
            div("P2", "2. ", "needs_review", NEEDS),
            div("P3", "3. ", "normative"),
            div("P4", "4. ", "needs_review", NEEDS),
            div("P5", "5. ", "normative"),
            div("P6", "6. ", "normative"),
        ),
    ),
    Document(
        "article",
        "50",
        (
            div("HEAD", None, "structural"),
            *(div(f"P{i}", f"{i}. ", "normative") for i in range(1, 8)),
        ),
    ),
    Document(
        "article",
        "60",
        (
            div("HEAD", None, "structural"),
            div("P1", "1. ", "needs_review", NEEDS),
            div("P2", "2. ", "needs_review", NEEDS),
            div("P3", "3. ", "context_only", SAVING),
            div("P4", "4. ", "normative"),
            *(div(f"P{i}", f"{i}. ", "needs_review", NEEDS) for i in range(5, 10)),
        ),
    ),
    Document(
        "article",
        "75",
        (
            div("HEAD", None, "structural"),
            div("P1", "1. ", "normative"),
            div("P1A", "1a. ", "needs_review", NEEDS),
            div("P1B", "1b. ", "needs_review", NEEDS),
            div("P1C", "1c. ", "needs_review", NEEDS),
            div("P1D", "1d. ", "needs_review", NEEDS),
            div("P1E", "1e. ", "normative"),
            div("P2", "2. ", "needs_review", NEEDS),
            div("P2A", "2a. ", "needs_review", NEEDS),
            div("P3", "3. ", "needs_review", NEEDS),
        ),
    ),
    Document(
        "article",
        "113",
        (
            div("HEAD", None, "structural"),
            div("ENTRY", "This Regulation shall enter", "normative"),
            div("GENERAL", "It shall apply from", "normative"),
            div("HOWEVER", "However:", "structural"),
            div("A", "    (a) ", "normative"),
            div("B", "    (b) ", "normative"),
            div("C", "    (c) ", "normative"),
            div("D", "    (d) ", "normative"),
        ),
    ),
    Document(
        "annex",
        "IV",
        (
            div("HEAD", None, "structural"),
            div("CHAPEAU", "The technical documentation referred", "normative"),
            *(div(f"I{i}", f"{i}. ", "normative") for i in range(1, 10)),
        ),
    ),
    Document(
        "annex",
        "VII",
        (
            div("HEAD", None, "structural"),
            div("I1", "1.Introduction", "needs_review", NEEDS),
            div("I2", "2.Overview", "needs_review", NEEDS),
            div("I3", "3.Quality management system", "normative"),
            div("I4", "4.Control of the technical documentation.", "normative"),
            div("I5", "5.Surveillance", "normative"),
        ),
    ),
    Document(
        "annex",
        "VIII",
        (
            div("HEAD", None, "structural"),
            div("A", "Section A", "normative"),
            div("B", "Section B", "normative"),
            div("C", "Section C", "normative"),
        ),
    ),
)


def source_record(
    suffix: str,
    source: str,
    quote: str,
    action: str,
    subject: str = "provider",
    category: str = "supported_operator",
    **kwargs: Any,
) -> NormSourceRecord:
    return NormSourceRecord(
        norm_id=f"AIA-NORM-{suffix}",
        source=source,
        quote=quote,
        action=action,
        subject_ref=subject,
        subject_category=category,
        **kwargs,
    )


OUTSIDE = {
    "product_scope": "outside_supported_actor",
    "product_scope_reason": "The present product does not report compliance for this addressee.",
    "implementation_mode": "none_required",
    "implementation_reason": "Outside the supported operator reporting surface.",
    "verification_mode": "not_assessed",
}
DEPENDENCY = {
    "product_scope": "dependency_only",
    "product_scope_reason": "This proposition supplies applicability or content to operator norms.",
    "implementation_mode": "none_required",
    "implementation_reason": "Represented as a dependency rather than an independent finding.",
    "verification_mode": "not_assessed",
}

NORM_SOURCE_RECORDS = (
    # Article 11(1): seven occurrences of shall conceal duties, a permission, and two other actors.
    source_record(
        "A011-P1-DRAW",
        "A011-P1",
        "shall be drawn up before that system is placed on the market or put into service",
        "draw up technical documentation before placing the system on the market or putting it into service",
        implementation_refs=("AIA-HR-A11",),
        verification_mode="judged_from_document",
    ),
    source_record(
        "A011-P1-UPDATE",
        "A011-P1",
        "shall be kept up-to date",
        "keep technical documentation up to date",
        implementation_refs=("AIA-HR-A11",),
        verification_mode="judged_from_document",
    ),
    source_record(
        "A011-P1-DEMONSTRATE",
        "A011-P1",
        "shall be drawn up in such a way as to demonstrate that the high-risk AI system complies",
        "draw up documentation that demonstrates compliance and enables assessment",
        implementation_refs=("AIA-HR-A11",),
        verification_mode="judged_from_document",
    ),
    source_record(
        "A011-P1-ANNEX-IV",
        "A011-P1",
        "It shall contain, at a minimum, the elements set out in Annex IV.",
        "include every applicable Annex IV element",
        implementation_refs=("AIA-HR-A11",),
        verification_mode="judged_from_document",
        dependencies=(
            (
                "AIA-NORM-ANNEX-IV-CONTENT",
                "internal_resolved",
                "Annex IV supplies the mandatory content.",
            ),
        ),
    ),
    source_record(
        "A011-P1-SIMPLIFY",
        "A011-P1",
        "may provide the elements of the technical documentation specified in Annex IV in a simplified manner",
        "use the simplified-documentation option",
        kind="permission",
        conditions=("provider is an SME, start-up, or SMC",),
    ),
    source_record(
        "A011-P1-FORM",
        "A011-P1",
        "the Commission shall establish a simplified technical documentation form",
        "establish a simplified technical-documentation form",
        "commission",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A011-P1-USE-FORM",
        "A011-P1",
        "it shall use the form referred to in this paragraph",
        "use the Commission form when taking the simplified-documentation option",
        conditions=("provider is an SME, start-up, or SMC and opts for simplified documentation",),
        implementation_refs=("AIA-HR-A11",),
        verification_mode="judged_from_document",
    ),
    source_record(
        "A011-P1-ACCEPT-FORM",
        "A011-P1",
        "Notified bodies shall accept the form",
        "accept the simplified form for conformity assessment",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "A011-P3-AMEND",
        "A011-P3",
        "The Commission is empowered to adopt delegated acts",
        "adopt delegated acts amending Annex IV",
        "commission",
        "union_institution_or_body",
        kind="power",
        **OUTSIDE,
    ),
    # Article 26(5): event-specific duties, relief, fallback, and a deeming rule.
    source_record(
        "A026-P5-MONITOR",
        "A026-P5",
        "Deployers shall monitor the operation of the high-risk AI system",
        "monitor system operation using the instructions for use",
        "deployer",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-INFORM-PROVIDER",
        "A026-P5",
        "Deployers shall monitor the operation of the high-risk AI system on the basis of the instructions for use and, where relevant, inform providers in accordance with Article 72.",
        "inform the provider where monitoring makes that relevant",
        "deployer",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-RISK-NOTIFY",
        "A026-P5",
        "they shall, without undue delay, inform the provider or distributor and the relevant market surveillance authority",
        "notify the provider or distributor and market-surveillance authority of an Article 79(1) risk",
        "deployer",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-SUSPEND",
        "A026-P5",
        "shall suspend the use of that system",
        "suspend use when compliant use may present an Article 79(1) risk",
        "deployer",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-INCIDENT",
        "A026-P5",
        "they shall also immediately inform first the provider, and then the importer or distributor and the relevant market surveillance authorities",
        "report an identified serious incident in the enacted sequence",
        "deployer",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-FALLBACK",
        "A026-P5",
        "If the deployer is not able to reach the provider, Article 73 shall apply mutatis mutandis.",
        "apply the Article 73 reporting route when the provider cannot be reached",
        "deployer",
        kind="applicability",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A026-P5-SENSITIVE",
        "A026-P5",
        "This obligation shall not cover sensitive operational data",
        "exclude sensitive operational data of law-enforcement deployers",
        "deployer",
        kind="applicability",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="reported_conditionally",
    ),
    source_record(
        "A026-P5-FINANCIAL",
        "A026-P5",
        "shall be deemed to be fulfilled by complying with the rules on internal governance arrangements",
        "deem financial institutions compliant through relevant financial-services governance rules",
        "financial_institution_deployer",
        kind="legal_consequence",
        implementation_refs=("AIA-DP-A26",),
        verification_mode="reported_conditionally",
    ),
    # Article 43(3), plus the institutional amendment powers selected as controls.
    source_record(
        "A043-P3-PROCEDURE",
        "A043-P3",
        "shall follow the relevant conformity assessment procedure",
        "follow the applicable Section A Annex I conformity-assessment procedure",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A043-P3-SECTION2",
        "A043-P3",
        "shall be part of that assessment",
        "include Chapter III Section 2 requirements in that assessment",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A043-P3-QMS",
        "A043-P3",
        "Assessment of the quality management system set out in Article 17 shall also be undertaken",
        "undertake assessment of the Article 17 quality-management system",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A043-P3-ANNEXVII",
        "A043-P3",
        "points 3, 4.3, 4.4. and 4.5, the fifth paragraph of point 4.6 and point 5 of Annex VII shall apply",
        "apply the specified Annex VII procedural requirements",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
        dependencies=(
            (
                "AIA-TEXT-ANNEX-VII-I3",
                "internal_resolved",
                "Annex VII point 3 is imported in full.",
            ),
            (
                "AIA-TEXT-ANNEX-VII-I4",
                "internal_resolved",
                "The specified point 4 subparagraphs are represented within this source segment.",
            ),
            (
                "AIA-TEXT-ANNEX-VII-I5",
                "internal_resolved",
                "Annex VII point 5 is imported in full.",
            ),
        ),
    ),
    source_record(
        "A043-P3-BODY-POWER",
        "A043-P3",
        "shall have the power to assess the conformity of high-risk AI systems",
        "assess conformity with Chapter III Section 2",
        "sectoral_notified_body",
        "notified_or_conformity_body",
        kind="power",
        **OUTSIDE,
    ),
    source_record(
        "A043-P3-DESIGNATE",
        "A043-P3",
        "shall apply for designation in accordance with Section 4 of this Chapter by 28 January 2028",
        "apply for AI Act designation by 28 January 2028",
        "sectoral_notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "A043-P3-OPTION",
        "A043-P3",
        "that manufacturer may use that option only if it has also applied harmonised standards",
        "use a no-third-party sectoral route only after applying standards covering all Section 2 requirements",
        "product_manufacturer",
        kind="permission",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A043-P3-NO-EFFECT",
        "A043-P3",
        "does not affect the choice of the conformity assessment procedure",
        "preserve the sectoral conformity-route choice despite AI high-risk classification",
        "product_manufacturer",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A043-P3-NO-THIRD-PARTY",
        "A043-P3",
        "are not required to choose a conformity assessment procedure involving third-party conformity assessment only because the product includes a high-risk AI system",
        "avoid a third-party procedure where sectoral law does not otherwise require it",
        "product_manufacturer",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A043-P3-DUAL",
        "A043-P3",
        "shall follow the relevant conformity assessment procedure as required pursuant to the relevant Union harmonisation legislation",
        "use the Section A Annex I procedure when the system is also in Annex III",
        implementation_refs=("AIA-PO-A43-3",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A043-P5-AMEND",
        "A043-P5",
        "The Commission is empowered to adopt delegated acts",
        "amend Annexes VI and VII for technical progress",
        "commission",
        "union_institution_or_body",
        kind="power",
        **OUTSIDE,
    ),
    source_record(
        "A043-P6-AMEND",
        "A043-P6",
        "The Commission is empowered to adopt delegated acts",
        "move Annex III points 2 to 8 to some or all of the Annex VII procedure",
        "commission",
        "union_institution_or_body",
        kind="power",
        **OUTSIDE,
    ),
    # Article 50. Paragraph 5 is a shared qualifier; paragraph 6 preserves cumulative duties.
    source_record(
        "A050-P1-DISCLOSE",
        "A050-P1",
        "Providers shall ensure that AI systems intended to interact directly with natural persons are designed and developed in such a way that the natural persons concerned are informed that they are interacting with an AI system",
        "design direct-interaction systems to inform natural persons they are interacting with AI",
        implementation_refs=("AIA-TR-A50-1",),
        verification_mode="judged_from_document",
        qualifier_spans=("A050-P5",),
        exceptions=("obvious interaction in context", "qualifying law-enforcement authorisation"),
    ),
    source_record(
        "A050-P2-MARK-DETECT",
        "A050-P2",
        "Providers of AI systems, including general-purpose AI systems, generating synthetic audio, image, video or text content, shall ensure that the outputs of the AI system are marked in a machine-readable format and detectable as artificially generated or manipulated.",
        "make synthetic outputs both machine-readably marked and detectable",
        implementation_refs=("AIA-TR-A50-2",),
        verification_mode="judged_from_document",
        qualifier_spans=("A050-P5",),
        mandatory_content=(
            "machine-readable marking",
            "detectability as artificial or manipulated",
            "effective, interoperable, robust and reliable solution as technically feasible",
        ),
    ),
    source_record(
        "A050-P3-INFORM",
        "A050-P3",
        "shall inform the natural persons exposed thereto of the operation of the system",
        "inform people exposed to emotion recognition or biometric categorisation",
        "deployer",
        implementation_refs=("AIA-TR-A50-3",),
        verification_mode="listed_for_confirmation",
        qualifier_spans=("A050-P5",),
    ),
    source_record(
        "A050-P3-DATA",
        "A050-P3",
        "shall process the personal data in accordance with Regulations (EU) 2016/679 and (EU) 2018/1725 and Directive (EU) 2016/680",
        "process personal data under the referenced data-protection instruments",
        "deployer",
        dependencies=(
            (
                "Regulation (EU) 2016/679; Regulation (EU) 2018/1725; Directive (EU) 2016/680",
                "external_recorded",
                "Referenced instruments are outside the enacted corpus.",
            ),
        ),
    ),
    source_record(
        "A050-P4-DEEPFAKE",
        "A050-P4",
        "shall disclose that the content has been artificially generated or manipulated",
        "disclose artificial generation or manipulation of deep-fake image, audio, or video",
        "deployer",
        implementation_refs=("AIA-TR-A50-4",),
        verification_mode="listed_for_confirmation",
        qualifier_spans=("A050-P5",),
    ),
    source_record(
        "A050-P4-TEXT",
        "A050-P4",
        "shall disclose that the text has been artificially generated or manipulated",
        "disclose artificial generation or manipulation of public-interest text",
        "deployer",
        implementation_refs=("AIA-TR-A50-4",),
        verification_mode="listed_for_confirmation",
        qualifier_spans=("A050-P5",),
    ),
    source_record(
        "A050-P5-MANNER",
        "A050-P5",
        "shall be provided to the natural persons concerned in a clear and distinguishable manner",
        "provide paragraphs 1 to 4 information clearly, distinguishably, on time, and accessibly",
        "provider_or_deployer",
        implementation_mode="carried_by_other_norm",
        implementation_reason="The four existing transparency rules carry this shared qualifier.",
        verification_mode="reported_conditionally",
        mandatory_content=(
            "clear and distinguishable",
            "no later than first interaction or exposure",
            "applicable accessibility requirements",
        ),
    ),
    source_record(
        "A050-P6-CUMULATIVE",
        "A050-P6",
        "Paragraphs 1 to 4 shall not affect the requirements and obligations set out in Chapter III",
        "preserve Chapter III and other transparency duties alongside Article 50",
        "provider_or_deployer",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A050-P7-CODES",
        "A050-P7",
        "The Commission shall encourage and facilitate the drawing up of codes of practice",
        "encourage and facilitate Union-level codes of practice",
        "commission",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A050-P7-ASSESS",
        "A050-P7",
        "The Commission, taking utmost account of the opinion of the Board, shall assess",
        "assess whether code adherence adequately ensures compliance",
        "commission",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A050-P7-ACT",
        "A050-P7",
        "the Commission may adopt an implementing act",
        "adopt common implementation rules if a code is inadequate",
        "commission",
        "union_institution_or_body",
        kind="power",
        **OUTSIDE,
    ),
    # Article 60(4): one cumulative permission plus independently applicable consequences.
    source_record(
        "A060-P4-PERMISSION",
        "A060-P4",
        "may conduct the testing in real world conditions only where all of the following conditions are met",
        "conduct real-world testing only when all eleven conditions are met",
        kind="permission",
        implementation_refs=("AIA-PO-A60-4",),
        verification_mode="listed_for_confirmation",
        mandatory_content=(
            "testing plan submitted",
            "authority approval or applicable tacit approval",
            "correct registration route",
            "Union establishment or representative",
            "third-country transfer safeguards",
            "six-month limit and extension process",
            "vulnerable-subject protection",
            "participating deployer information, instructions, and agreement",
            "informed consent or law-enforcement substitute safeguards",
            "qualified effective oversight",
            "reversible and disregardable outputs",
        ),
    ),
    source_record(
        "A060-P4-TACIT",
        "A060-P4",
        "shall be understood to have been approved",
        "deem testing approved after 30 days of authority silence where national law permits",
        kind="legal_consequence",
        **DEPENDENCY,
    ),
    source_record(
        "A060-P4-EXTEND",
        "A060-P4",
        "may be extended for an additional period of six months",
        "extend testing once for six months after prior notice and explanation",
        kind="permission",
        conditions=("prior notification and explanation of need",),
        implementation_refs=("AIA-PO-A60-4",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A060-P4-AGREEMENT",
        "A060-P4",
        "shall conclude an agreement specifying their roles and responsibilities",
        "conclude a roles-and-responsibilities agreement with participating deployers",
        "provider_and_deployer",
        implementation_refs=("AIA-PO-A60-4",),
        verification_mode="listed_for_confirmation",
    ),
    # Article 75(1)/(1e): mixed institutional machinery and two provider payment duties.
    source_record(
        "A075-P1-COMPETENCE",
        "A075-P1",
        "The AI Office shall be exclusively competent",
        "hold exclusive supervision and enforcement competence for the listed systems",
        "ai_office",
        "union_institution_or_body",
        kind="legal_consequence",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-RESPONSIBLE",
        "A075-P1E",
        "The AI Office shall be responsible for conformity assessments and tests",
        "take responsibility for third-party conformity assessments and tests of paragraph 1 systems",
        "ai_office",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-VERIFY",
        "A075-P1E",
        "Those tests and assessments shall verify that the systems comply",
        "verify regulatory conformity and market eligibility",
        "ai_office",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-ENTRUST",
        "A075-P1E",
        "The Commission shall entrust the performance of those tests or assessments to notified bodies",
        "entrust tests or assessments to designated notified bodies",
        "commission",
        "union_institution_or_body",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-ACT",
        "A075-P1E",
        "the notified body shall act on behalf of the Commission",
        "act on the Commission's behalf when entrusted",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-WITHDRAW",
        "A075-P1E",
        "the Commission may withdraw the delegation with immediate effect",
        "withdraw an inadequately performed delegation immediately",
        "commission",
        "union_institution_or_body",
        kind="power",
        **OUTSIDE,
    ),
    source_record(
        "A075-P1E-FEES",
        "A075-P1E",
        "The fees for testing and assessment activities shall be levied on the provider",
        "bear testing and assessment fees",
        implementation_refs=("AIA-PO-A75-1E",),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "A075-P1E-PAY",
        "A075-P1E",
        "The provider shall pay the costs related to the services",
        "pay entrusted-service costs directly to the notified body",
        implementation_refs=("AIA-PO-A75-1E",),
        verification_mode="listed_for_confirmation",
    ),
    # Article 113: legal consequences and route-specific applicability, most without a duty-holder.
    source_record(
        "A113-ENTRY",
        "A113-ENTRY",
        "shall enter into force on the twentieth day following that of its publication",
        "enter into force twenty days after publication",
        "regulation",
        "other",
        kind="legal_consequence",
        **DEPENDENCY,
    ),
    source_record(
        "A113-GENERAL",
        "A113-GENERAL",
        "It shall apply from 2 August 2026.",
        "apply generally from 2 August 2026",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-A-EARLY",
        "A113-A",
        "Chapters I and II shall apply from 2 February 2025",
        "apply Chapters I and II from 2 February 2025",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-A-LATE",
        "A113-A",
        "shall apply from 2 December 2026",
        "apply the listed Article 5 amendments from 2 December 2026",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-B",
        "A113-B",
        "shall apply from 2 August 2025",
        "apply the listed chapters and Article 78 from 2 August 2025 except Article 101",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-C-ANNEXIII",
        "A113-C",
        "Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from:\n            (i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III",
        "apply Chapter III Sections 1 to 3 to the Annex III route from 2 December 2027",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-C-ANNEXI",
        "A113-C",
        "Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), shall apply from:\n            (i) 2 December 2027 as regards AI systems classified as high-risk pursuant to Article 6(2) and Annex III; and\n            (ii) 2 August 2028 as regards AI systems classified as high-risk pursuant to Article 6(1) and Annex I",
        "apply Chapter III Sections 1 to 3 to the Annex I route from 2 August 2028",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    source_record(
        "A113-D",
        "A113-D",
        "Articles 102 to 110 shall apply from 27 July 2026.",
        "apply Articles 102 to 110 from 27 July 2026",
        "regulation",
        "other",
        kind="applicability",
        **DEPENDENCY,
    ),
    # Annex IV: the list is mandatory content of one document obligation and travels together.
    source_record(
        "ANNEX-IV-CONTENT",
        "ANNEX-IV-CHAPEAU",
        "shall contain at least the following information",
        "include all nine applicable Annex IV information groups in technical documentation",
        implementation_mode="carried_by_other_norm",
        implementation_reason="Carried by the Article 11(1) technical-documentation norm.",
        verification_mode="judged_from_document",
        mandatory_content=(
            "general system description",
            "system elements and development process",
            "monitoring, functioning and control",
            "appropriateness of performance metrics",
            "risk-management system",
            "lifecycle changes",
            "standards or alternative compliance solutions",
            "EU declaration of conformity",
            "post-market performance evaluation and monitoring plan",
        ),
        qualifier_spans=tuple(f"ANNEX-IV-I{i}" for i in range(1, 10)),
    ),
    # Both sides of the Annex VII procedure imported by Article 43(3).
    source_record(
        "ANNEX-VII-QMS-APPLICATION",
        "ANNEX-VII-I3",
        "The application of the provider shall include",
        "complete the Annex VII quality-management application",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
        mandatory_content=(
            "provider and representative identity",
            "covered systems",
            "technical documentation for every system",
            "Article 17 QMS documentation",
            "procedures maintaining QMS adequacy and effectiveness",
            "declaration no duplicate application",
        ),
    ),
    source_record(
        "ANNEX-VII-QMS-MAINTAIN",
        "ANNEX-VII-I3",
        "shall continue to be implemented and maintained by the provider",
        "continue implementing and maintaining the approved quality-management system",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-QMS-CHANGE",
        "ANNEX-VII-I3",
        "shall be brought to the attention of the notified body by the provider",
        "notify the notified body of intended QMS or covered-system-list changes",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-QMS-ASSESS",
        "ANNEX-VII-I3",
        "The quality management system shall be assessed by the notified body",
        "assess whether the quality-management system satisfies Article 17",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-QMS-DECISION",
        "ANNEX-VII-I3",
        "The decision shall be notified to the provider or its authorised representative.",
        "notify the provider of the quality-management assessment decision and reasons",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-QMS-CHANGE-DECISION",
        "ANNEX-VII-I3",
        "The proposed changes shall be examined by the notified body",
        "examine proposed changes, decide whether reassessment is needed, and notify the provider",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-DOC-EXAMINE",
        "ANNEX-VII-I4",
        "The technical documentation shall be examined by the notified body.",
        "examine the technical documentation",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-DATA-ACCESS",
        "ANNEX-VII-I4",
        "the notified body shall be granted full access to the training, validation, and testing data sets used",
        "grant the notified body necessary full dataset access",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-EVIDENCE",
        "ANNEX-VII-I4",
        "the provider supply further evidence or carry out further tests",
        "supply further evidence or tests required for the conformity assessment",
        conditions=("notified body requires them",),
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-TESTS",
        "ANNEX-VII-I4",
        "the notified body shall itself directly carry out adequate tests",
        "carry out adequate tests when provider testing is unsatisfactory",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-MODEL-ACCESS",
        "ANNEX-VII-I4",
        "the notified body shall also be granted access to the training and trained models",
        "grant reasoned and necessary model access after other means are exhausted",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-RETRAIN",
        "ANNEX-VII-I4",
        "re-training of the AI system will be needed prior to the application for a new conformity assessment",
        "retrain before reapplying where training data fail the requirement",
        kind="legal_consequence",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-DOC-DECISION",
        "ANNEX-VII-I4",
        "The decision of the notified body shall be notified to the provider or its authorised representative.",
        "notify the provider of the technical-documentation assessment decision",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-CERTIFICATE",
        "ANNEX-VII-I4",
        "the notified body shall issue a Union technical documentation assessment certificate",
        "issue the certificate where the system conforms",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-REFUSE",
        "ANNEX-VII-I4",
        "the notified body shall refuse to issue a Union technical documentation assessment certificate and shall inform the applicant accordingly",
        "refuse certification and give detailed reasons where the system does not conform",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-DATA-REASONS",
        "ANNEX-VII-I4",
        "shall contain specific considerations on the quality data used to train the AI system",
        "state specific training-data non-compliance considerations in the refusal decision",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    source_record(
        "ANNEX-VII-SURVEILLANCE",
        "ANNEX-VII-I5",
        "the provider shall allow the notified body to access the premises",
        "allow surveillance access to premises and share all necessary information",
        implementation_refs=("AIA-PO-A43-1B", "AIA-PO-A43-3"),
        verification_mode="listed_for_confirmation",
    ),
    source_record(
        "ANNEX-VII-AUDIT",
        "ANNEX-VII-I5",
        "The notified body shall carry out periodic audits",
        "carry out periodic audits and provide the provider an audit report",
        "notified_body",
        "notified_or_conformity_body",
        **OUTSIDE,
    ),
    # Annex VIII's three routes remain distinct because their duty-holder and contents differ.
    source_record(
        "ANNEX-VIII-A",
        "ANNEX-VIII-A",
        "The following information shall be provided and thereafter kept up to date",
        "submit and maintain the Section A provider registration information",
        mandatory_content=tuple(f"Section A item {i}" for i in range(1, 14)),
        implementation_mode="unresolved",
        verification_mode="unresolved",
    ),
    source_record(
        "ANNEX-VIII-B",
        "ANNEX-VIII-B",
        "The following information shall be provided and thereafter kept up to date",
        "submit and maintain the Section B not-high-risk registration information",
        mandatory_content=tuple(f"Section B item {i}" for i in range(1, 10)),
        implementation_mode="unresolved",
        verification_mode="unresolved",
    ),
    source_record(
        "ANNEX-VIII-C",
        "ANNEX-VIII-C",
        "The following information shall be provided and thereafter kept up to date",
        "submit and maintain the Section C deployer registration information",
        "deployer",
        mandatory_content=tuple(f"Section C item {i}" for i in range(1, 6)),
        implementation_mode="unresolved",
        verification_mode="unresolved",
    ),
)


def source_file(document: Document) -> Path:
    if document.kind == "article":
        return ARTICLES / article_filename(document.number)
    return ANNEXES / f"annex-{document.number}.md"


def document_key(document: Document) -> tuple[str, str]:
    return document.kind, document.number


def document_sort_key(document: Document) -> tuple[int, int, str]:
    if document.kind == "annex":
        return 1, 0, document.number
    match = re.fullmatch(r"(\d+)([a-z]?)", document.number)
    if match is None:
        raise ValueError(f"invalid article identifier {document.number!r}")
    return 0, int(match.group(1)), match.group(2)


def complete_document_inventory() -> tuple[Document, ...]:
    reviewed = {document_key(document): document for document in REVIEWED_DOCUMENTS}
    if len(reviewed) != len(REVIEWED_DOCUMENTS):
        raise ValueError("reviewed document inventory contains duplicate source addresses")

    expected = {
        (kind.value, document)
        for kind, document in corpus_documents(
            date.fromisoformat(VERSION), ARTICLES.parent, ANNEXES.parent
        )
    }
    unknown = sorted(set(reviewed) - expected)
    if unknown:
        raise ValueError(f"reviewed document inventory references unknown sources: {unknown}")

    documents = [
        reviewed.get(
            key,
            Document(
                kind=key[0],
                number=key[1],
                divisions=(Division("FULL", None, "needs_review", NEEDS),),
            ),
        )
        for key in expected
    ]
    return tuple(sorted(documents, key=document_sort_key))


def segment_id(document: Document, label: str) -> str:
    if document.kind == "article":
        match = re.fullmatch(r"(\d+)([a-z]?)", document.number)
        if match is None:
            raise ValueError(f"invalid article identifier {document.number!r}")
        prefix = f"A{int(match.group(1)):03d}{match.group(2).upper()}"
    else:
        prefix = f"ANNEX-{document.number}"
    return f"AIA-TEXT-{prefix}-{label}"


def review(status: str, fully_displayed: bool) -> dict[str, Any]:
    return {
        "status": status,
        "extracted_by": "semantic-legal-effect-pass",
        "verified_by": "",
        "review_run_id": "normative-coverage-2026-08-28",
        "presentation_mode": "exact-source-slice",
        "display_chunks": 1 if fully_displayed else 0,
        "fully_displayed": fully_displayed,
        "elapsed_seconds": None,
    }


def detection_channels(source_record: NormSourceRecord) -> list[str]:
    quote = source_record.quote.lower()
    channels = ["semantic_legal_effect"]
    if "shall" in quote:
        channels.append("shall_token")
    if any(token in quote for token in (" may ", "is empowered", "will be needed")):
        channels.append("other_modal")
    if source_record.kind in {"legal_consequence", "applicability"}:
        channels.append("deeming_or_consequence")
    if source_record.dependencies or source_record.qualifier_spans:
        channels.append("cross_reference_structure")
    if source_record.implementation_refs:
        channels.append("existing_implementation")
    return channels


def resolved_mode(source_record: NormSourceRecord) -> str:
    if source_record.implementation_mode is not None:
        return source_record.implementation_mode
    if source_record.implementation_refs:
        return "compliance_rule"
    if source_record.product_scope == "in_scope":
        return "missing"
    return "none_required"


def resolved_verification(source_record: NormSourceRecord) -> str:
    if source_record.verification_mode is not None:
        return source_record.verification_mode
    return "unresolved" if source_record.product_scope == "in_scope" else "not_assessed"


def line_start(body: str, marker: str, cursor: int) -> int:
    """Find a division marker only at a source line boundary."""
    start = body.find(marker, cursor)
    while start >= 0 and start > 0 and body[start - 1] != "\n":
        start = body.find(marker, start + 1)
    return start


def numbered_items(text: str) -> list[str]:
    """Extract exact indented numbered content from an Annex VIII section."""
    return [
        match.group(1).strip()
        for match in re.finditer(r"(?ms)^    \d+\. (.*?)(?=^    \d+\. |\Z)", text)
    ]


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    divisions: dict[str, Division] = {}
    segments: list[dict[str, Any]] = []

    for document in complete_document_inventory():
        body = source_body(source_file(document), expected_version=VERSION)
        starts: list[int] = []
        cursor = 0
        for index, division in enumerate(document.divisions):
            if index == 0:
                start = 0
            else:
                assert division.marker is not None
                start = line_start(body, division.marker, cursor)
                if start < 0:
                    raise ValueError(
                        f"{document.kind} {document.number}: marker {division.marker!r} not found"
                    )
            starts.append(start)
            cursor = start + 1

        for index, division in enumerate(document.divisions):
            start = starts[index]
            end = starts[index + 1] if index + 1 < len(starts) else len(body)
            sid = segment_id(document, division.label)
            if sid in divisions:
                raise ValueError(f"duplicate generated segment id {sid}")
            divisions[sid] = division
            exact = body[start:end]
            segments.append(
                {
                    "segment_id": sid,
                    "source": {
                        "kind": document.kind,
                        "document": document.number,
                        "act_version_date": VERSION,
                    },
                    "start": start,
                    "end": end,
                    "sha256": hashlib.sha256(exact.encode()).hexdigest(),
                    "text": exact,
                    "disposition": division.disposition,
                    "disposition_reason": division.reason,
                    "norm_ids": [],
                    "review": review(
                        "needs_review" if division.disposition == "needs_review" else "proposed",
                        division.disposition != "needs_review",
                    ),
                }
            )

    segments_by_id = {item["segment_id"]: item for item in segments}
    policy = load_policy_spec(
        articles_root=ARTICLES.parent,
        annexes_root=ANNEXES.parent,
        guidance_root=ROOT / "data" / "policy" / "guidance",
    )
    known_rule_ids = {rule.rule_id for rule in policy.rules}
    norms: list[dict[str, Any]] = []
    norm_ids = {source_record.norm_id for source_record in NORM_SOURCE_RECORDS}
    for source_record in NORM_SOURCE_RECORDS:
        primary = f"AIA-TEXT-{source_record.source}"
        spans = [primary, *[f"AIA-TEXT-{span}" for span in source_record.qualifier_spans]]
        effective = [f"AIA-TEXT-{span}" for span in source_record.effective_date_spans]
        unknown = [span for span in [*spans, *effective] if span not in segments_by_id]
        if unknown:
            raise ValueError(f"{source_record.norm_id}: unknown source-record span(s) {unknown}")
        if source_record.quote not in segments_by_id[primary]["text"]:
            raise ValueError(f"{source_record.norm_id}: quote is not exact in {primary}: {source_record.quote!r}")
        unknown_rules = sorted(set(source_record.implementation_refs) - known_rule_ids)
        if unknown_rules:
            raise ValueError(f"{source_record.norm_id}: unknown implementation rule(s) {unknown_rules}")
        for span in [*spans, *effective]:
            if segments_by_id[span]["disposition"] != "normative":
                raise ValueError(f"{source_record.norm_id}: linked span {span} is not normative")
            segments_by_id[span]["norm_ids"].append(source_record.norm_id)
        dependencies = [
            {"dependency_ref": ref, "resolution": resolution, "detail": detail}
            for ref, resolution, detail in source_record.dependencies
        ]
        for dependency in dependencies:
            if (
                dependency["resolution"] == "internal_resolved"
                and dependency["dependency_ref"] not in norm_ids
                and dependency["dependency_ref"] not in segments_by_id
            ):
                raise ValueError(
                    f"{source_record.norm_id}: internal dependency {dependency['dependency_ref']} is unknown"
                )
        mandatory_content = list(source_record.mandatory_content)
        if source_record.norm_id.startswith("AIA-NORM-ANNEX-VIII-"):
            mandatory_content = numbered_items(segments_by_id[primary]["text"])
            if not mandatory_content:
                raise ValueError(f"{source_record.norm_id}: no Annex VIII numbered items found")
        norms.append(
            {
                "norm_id": source_record.norm_id,
                "act_version_date": VERSION,
                "kind": source_record.kind,
                "subjects": [
                    {
                        "subject_ref": source_record.subject_ref,
                        "category": source_record.subject_category,
                    }
                ],
                "action": source_record.action,
                "norm_text": source_record.quote,
                "detection_channels": detection_channels(source_record),
                "primary_spans": [primary],
                "qualifier_spans": [f"AIA-TEXT-{span}" for span in source_record.qualifier_spans],
                "effective_date_spans": effective,
                "conditions": list(source_record.conditions),
                "exceptions": list(source_record.exceptions),
                "mandatory_content": mandatory_content,
                "dependencies": dependencies,
                "product_scope": source_record.product_scope,
                "product_scope_reason": source_record.product_scope_reason,
                "implementation_mode": resolved_mode(source_record),
                "implementation_refs": list(source_record.implementation_refs),
                "implementation_reason": source_record.implementation_reason,
                "verification_mode": resolved_verification(source_record),
                "review": review("proposed", True),
            }
        )

    # This shared qualifier is carried by each of the four runtime transparency rules.
    manner = next(n for n in norms if n["norm_id"] == "AIA-NORM-A050-P5-MANNER")
    manner["carried_by_norm_ids"] = [
        "AIA-NORM-A050-P1-DISCLOSE",
        "AIA-NORM-A050-P2-MARK-DETECT",
        "AIA-NORM-A050-P3-INFORM",
        "AIA-NORM-A050-P4-DEEPFAKE",
        "AIA-NORM-A050-P4-TEXT",
    ]

    annex_iv = next(n for n in norms if n["norm_id"] == "AIA-NORM-ANNEX-IV-CONTENT")
    annex_iv["carried_by_norm_ids"] = ["AIA-NORM-A011-P1-ANNEX-IV"]

    interpretations = [
        {
            "interpretation_id": "AIA-INT-A050-P2-C2026-5054",
            "snippet_refs": [
                "C-2026-5054/machine-readable-marking-defined",
                "C-2026-5054/both-elements-required",
                "C-2026-5054/detection-must-be-available",
            ],
            "norm_ids": ["AIA-NORM-A050-P2-MARK-DETECT"],
            "targets": [{"kind": "policy_rule", "target_id": "AIA-TR-A50-2"}],
            "effect": "defines_mechanism",
            "effect_explanation": "Explains machine readability and the separate detection mechanism.",
            "review_scope": "passage_with_context",
            "review_scope_detail": "Stored paragraphs (70), (71), (75), and (76) with declared omissions.",
            "binding": False,
            "review": review("proposed", True),
        }
    ]

    return (
        {
            "act_version_date": VERSION,
            "corpus_complete": True,
            "segments": segments,
        },
        {
            "act_version_date": VERSION,
            "norms": norms,
            "interpretations": interpretations,
        },
    )


def rendered() -> tuple[str, str]:
    text_review, norms = build()
    heading = (
        "# Generated by scripts/build_normative_coverage_2026_07_27.py; "
        "edit normative source records, not offsets.\n"
    )
    return (
        heading + yaml.safe_dump(text_review, sort_keys=False, width=100),
        heading + yaml.safe_dump(norms, sort_keys=False, width=100),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text, norms = rendered()
    if args.check:
        stale = [
            str(path)
            for path, expected in ((TEXT_OUTPUT, text), (NORM_OUTPUT, norms))
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(f"generated coverage artifacts are stale: {', '.join(stale)}")
        report = render_coverage_markdown(
            measure_normative_coverage(
                load_normative_coverage(
                    TEXT_OUTPUT,
                    NORM_OUTPUT,
                    articles_root=ARTICLES.parent,
                    annexes_root=ANNEXES.parent,
                    guidance_root=ROOT / "data" / "policy" / "guidance",
                )
            )
        )
        if not REPORT_OUTPUT.is_file() or REPORT_OUTPUT.read_text(encoding="utf-8") != report:
            raise SystemExit(f"generated coverage report is stale: {REPORT_OUTPUT}")
        return 0
    TEXT_OUTPUT.write_text(text, encoding="utf-8")
    NORM_OUTPUT.write_text(norms, encoding="utf-8")
    bundle = load_normative_coverage(
        TEXT_OUTPUT,
        NORM_OUTPUT,
        articles_root=ARTICLES.parent,
        annexes_root=ANNEXES.parent,
        guidance_root=ROOT / "data" / "policy" / "guidance",
    )
    REPORT_OUTPUT.write_text(
        render_coverage_markdown(measure_normative_coverage(bundle)),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
