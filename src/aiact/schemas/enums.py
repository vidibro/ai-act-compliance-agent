"""Enumerated types encoding the semantics of Regulation (EU) 2024/1689.

Every member carries its legal meaning and, where relevant, the source article.
These are the vocabulary the rest of the schema layer is built on; a bare identifier
list would lose the reasoning that later readers (human or model) depend on.
"""

from enum import StrEnum


class RiskClass(StrEnum):
    """Risk tier assigned to an AI system (or to a single use case of one)."""

    PROHIBITED = "prohibited"
    """Art. 5. Banned practice. Cannot be placed on the market or used at all.
    Evaluated BEFORE high-risk classification — a prohibited system never reaches Art. 6."""

    HIGH_RISK = "high_risk"
    """Art. 6. Either an Annex I safety component, or an Annex III use case where no Art. 6(3)
    derogation applies — or where the profiling carve-back overrides any derogation.
    Triggers the full Art. 8-15 requirements and Art. 16+ provider obligations."""

    NOT_HIGH_RISK = "not_high_risk"
    """Falls WITHIN an Annex III area, but a derogation under Art. 6(3)(a)-(d) applies.
    NOT the same as `minimal`: the provider still owes Art. 6(4) — the not-high-risk assessment
    must be documented before market placement — plus Art. 49(2) registration."""

    MINIMAL = "minimal"
    """Outside Annex III entirely. No risk-tier obligations. Art. 4 (AI literacy) still applies,
    and Art. 50 transparency may apply independently of the risk tier."""

    NEEDS_REVIEW = "needs_review"
    """Not a legal category — an engineering escape hatch. The agent could not reach a
    defensible verdict from the documentation. Preferable to a confident wrong answer;
    surfaced to a human reviewer."""


class ActorRole(StrEnum):
    """Art. 2(1), Art. 3. Obligations attach to the ROLE, not to the organisation.
    One organisation may hold several roles and must be assessed separately for each."""

    PROVIDER = "provider"
    """Art. 3(3). Develops the system, or has it developed, and places it on the market /
    puts it into service under its own name or trademark. Bears the heaviest obligations."""

    DEPLOYER = "deployer"
    """Art. 3(4). Uses the system under its own authority in a professional capacity.
    Distinct, lighter obligation set (Art. 26) — out of scope for v0.1."""

    IMPORTER = "importer"
    """Art. 3(6). Established in the EU, places on the market a system bearing the name or
    trademark of a third-country entity."""

    DISTRIBUTOR = "distributor"
    """Art. 3(7). In the supply chain, other than provider or importer, makes the system
    available on the EU market."""

    AUTHORISED_REPRESENTATIVE = "authorised_representative"
    """Art. 3(5). Mandated by a third-country provider to act on its behalf in the EU."""

    PRODUCT_MANUFACTURER = "product_manufacturer"
    """Places a product on the market together with an AI system, under its own name."""


class Verdict(StrEnum):
    """Outcome of checking ONE PolicyRule against the system's documentation."""

    PASS = "pass"
    """The documentation contains evidence that substantively satisfies the requirement."""

    GAP = "gap"
    """The requirement is not addressed in the documentation at all. Nothing to point to."""

    INADEQUATE = "inadequate"
    """CENTRAL TO THIS PROJECT. The requirement is mentioned, but without substance sufficient
    to satisfy it. Example (Art. 14): the document says 'we ensure human oversight' and nothing
    more — no measures, no interface, no ability to intervene, no operator competence.
    A keyword-matching checker returns PASS here. A checker that reads the requirement returns
    INADEQUATE. Distinguishing GAP from INADEQUATE is the core capability being built and
    measured — do not collapse them."""

    NOT_APPLICABLE = "not_applicable"
    """The rule is not activated for this system's risk class / role / use case."""

    NEEDS_REVIEW = "needs_review"
    """Evidence is ambiguous or contradictory; the agent declines to rule. Escalate to a human.
    For a compliance tool a false PASS is the most dangerous error — abstaining beats guessing."""


class ObligationStatus(StrEnum):
    """Legal modality of the requirement. Derived from the Regulation's modal verbs —
    do NOT collapse these; 'shall' and 'should' carry different legal weight."""

    MANDATORY = "mandatory"
    """'shall' — binding."""

    RECOMMENDED = "recommended"
    """'should' / 'may' — not binding. Reported, but never counted as a compliance gap."""


class CheckType(StrEnum):
    """How a rule must be verified. Determines the retrieval and judging strategy per rule."""

    PRESENCE = "presence"
    """Existence of the item is sufficient (e.g. Art. 12 logging capability is described)."""

    SUBSTANCE = "substance"
    """Existence is NOT sufficient — the content must be assessed against what the article
    actually demands (Art. 9, 10, 13, 14). This is where INADEQUATE verdicts arise."""

    METRICS = "metrics"
    """Concrete figures must be present and appropriate (Art. 15: accuracy, robustness).
    A claim of 'high accuracy' with no numbers is INADEQUATE, not PASS."""

    COMPLETENESS = "completeness"
    """A prescribed list must be fully covered (Art. 11 / Annex IV technical documentation)."""


class AnnexIIIArea(StrEnum):
    """Art. 6(2), Annex III. The eight high-risk areas. Only EMPLOYMENT is in v0.1 scope;
    the rest are modelled so the graph generalises without schema changes."""

    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"  # Annex III(2)
    BIOMETRICS = "biometrics"  # Annex III(1)
    EDUCATION = "education"  # Annex III(3)
    EMPLOYMENT = "employment"  # Annex III(4) <- v0.1 SCOPE
    ESSENTIAL_SERVICES = "essential_services"  # Annex III(5)
    LAW_ENFORCEMENT = "law_enforcement"  # Annex III(6)
    MIGRATION = "migration"  # Annex III(7)
    JUSTICE_DEMOCRACY = "justice_democracy"  # Annex III(8)


class DerogationCondition(StrEnum):
    """Art. 6(3)(a)-(d). An Annex III system escapes high-risk classification if it poses no
    significant risk of harm — including by not materially influencing the outcome of decision
    making — AND at least one of these conditions holds.

    CRITICAL: all four are overridden by the profiling carve-back. Art. 6(3) states that
    NOTWITHSTANDING these conditions, an Annex III system is ALWAYS high-risk where it performs
    profiling of natural persons. Hence profiling is evaluated as a SEPARATE, PRIOR node in our
    graph — see classification.py."""

    NARROW_PROCEDURAL_TASK = "narrow_procedural_task"
    """(a) e.g. extracting fields from a document without evaluating the person."""

    IMPROVES_COMPLETED_HUMAN_ACTIVITY = "improves_completed_human_activity"
    """(b) improves the result of a previously completed human activity."""

    DETECTS_DECISION_PATTERNS = "detects_decision_patterns"
    """(c) detects decision-making patterns or deviations from prior patterns, and is not meant
    to replace or influence the previously completed human assessment without proper review."""

    PREPARATORY_TASK = "preparatory_task"
    """(d) performs a preparatory task to an assessment relevant to an Annex III use case."""


class AblationType(StrEnum):
    """EVAL ONLY — not part of the Regulation. Describes how a requirement was degraded when
    generating a synthetic test document from the complete reference document. Because we know
    exactly what was altered, ground truth is exact."""

    REMOVED = "removed"
    """Section deleted outright. Expected verdict: GAP. Any checker should catch this."""

    PRESENT_BUT_INADEQUATE = "present_but_inadequate"
    """Section reduced to an empty assertion. Expected verdict: INADEQUATE.
    Defeats keyword matching — the most diagnostic class of example."""

    DISTRACTOR = "distractor"
    """Replaced with plausible-sounding but non-responsive content (e.g. a 'responsible AI'
    marketing section standing in for Art. 10 data governance). Expected verdict: GAP.
    Tests whether the agent distinguishes marketing from evidence of compliance.
    A false PASS here is the most dangerous failure mode of a compliance tool."""

    UNTOUCHED = "untouched"
    """Left intact. Expected verdict: PASS. Measures FALSE POSITIVES — a checker that flags
    everything is useless. Untouched requirements matter as much as ablated ones."""


class Difficulty(StrEnum):
    """EVAL ONLY. How hard the decisive fact is to locate in the input. Enables reporting
    accuracy per difficulty band instead of one meaningless aggregate number."""

    OBVIOUS = "obvious"
    """The decisive fact is stated plainly (e.g. 'returns a candidate fit score')."""

    BURIED = "buried"
    """The decisive fact is present but buried among features and vague marketing language.
    A drop in accuracy here means the agent is keyword-matching, not reading."""

    AMBIGUOUS = "ambiguous"
    """Genuinely contestable — reasonable experts could disagree. Reported separately;
    NEEDS_REVIEW is an acceptable answer here."""
