"""The ruleset: individual provider obligations, their legal source, and how to check them.

A PolicyRuleset is loaded from data (derived from the EC Compliance Checker) — regulatory
movement lives in the data, never hard-coded here.
"""

from __future__ import annotations

import warnings
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aiact.schemas.enums import (
    ActorCategory,
    ActorRole,
    AnnexIIIArea,
    CheckType,
    HighRiskRoute,
    ObligationStatus,
    ProhibitedPractice,
    RiskClass,
    TransparencyDuty,
)
from aiact.schemas.norm import LogicalExpression, NormKind, TemporalRegime, VerificationMode


class LegalSource(BaseModel):
    """A pinpoint citation into a legal instrument. Carried by every verdict in the system so
    that no assessment can exist without pointing at the article it rests on."""

    instrument: str  # "Regulation (EU) 2024/1689"
    article: str | None = None
    paragraph: str | None = None
    """AN ARTICLE OR PARAGRAPH LABEL IS A STRING, always, including when it looks like a number.

    A consolidation inserts provisions without renumbering the ones after them, so Art. 4a,
    Art. 75a-75d and Art. 6(1a)-(1c) are all real addresses, and `int()` of one silently resolves
    to the provision BEFORE it. Half the addresses being integers is what makes that mistake
    available: `f"article-{n:03d}.md"` reads correctly, works for 113 of 119 articles, and then
    raises or resolves wrong. One type for every label removes the case that has to be remembered,
    so `6` written in a spec is normalised to `"6"` below rather than accepted as a second form."""

    point: str | None = None  # "a", "b", ...
    annex: str | None = None  # "III", "IV"
    annex_point: str | None = None  # "4(a)"
    act_version_date: date  # pinned snapshot — REQUIRED for reproducibility
    url: str | None = None  # canonical location of the cited provision — lets a future
    # rule-refresh tool re-fetch the verbatim text and diff it against a new Act version

    @field_validator("article", "paragraph", mode="before")
    @classmethod
    def _one_form_per_label(cls, value: object) -> object:
        """`6` becomes `"6"`; `"1a"` stays `"1a"`.

        Two spellings of one address would compare unequal, and the route and section tests that
        group rules by article do compare them. YAML writes `article: 6` unquoted, so the integer
        arrives here whatever the field says; this is where it stops being one."""
        return str(value) if isinstance(value, int) else value


class GuidanceSource(BaseModel):
    """A pinpoint citation into NON-BINDING interpretive guidance (a Commission Communication).

    Deliberately a DIFFERENT type from LegalSource, and never merged with it. A verdict that rests
    on the Commission's *interpretation* is not the same as one that rests on *enacted law*, and a
    compliance reader must be able to tell them apart — the Court of Justice of the EU is the only
    authoritative interpreter. `binding` is False by construction (a validator forbids True), so a
    'binding guidance source' cannot be built by accident."""

    issuer: str  # "European Commission"
    reference: str  # "C(2025) 5052 final"
    snippet_ref: str  # "C-2025-5052/workplace-covers-recruitment" — id into the guidance store
    locator: str  # "paragraph (254), p. 86"
    topic: str = ""  # human-readable summary of what the passage says
    binding: bool = False
    url: str | None = None

    @field_validator("binding")
    @classmethod
    def _guidance_is_never_binding(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "GuidanceSource.binding must be False — Commission guidance is non-binding "
                "interpretation; enacted law is cited with LegalSource, not this."
            )
        return v


class RuleCriterion(BaseModel):
    """One separately judged norm inside an aggregate rule.

    A rule AUTHORS only `norm_id`. Every other field is materialised at load from the canonical
    generated norm, as `requirement` is from the article store, so the criterion's meaning has one
    source of truth and a model never maps a rule onto the law."""

    model_config = ConfigDict(frozen=True)

    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    kind: NormKind
    actors: list[str] = []
    applies_to_all_actors: bool = False
    targets: list[str]
    action: str = Field(min_length=1)
    norm_text: str = Field(min_length=1)
    conditions: LogicalExpression | None
    exceptions: LogicalExpression | None
    mandatory_content: list[str]
    source_spans: list[str] = Field(min_length=1)
    verification_mode: VerificationMode
    temporal_regime_id: str | None = Field(default=None, pattern=r"^AIA-TEMP-[A-Z0-9-]+$")

    @model_validator(mode="after")
    def _actor_scope_is_unambiguous(self) -> RuleCriterion:
        if self.actors and self.applies_to_all_actors:
            raise ValueError("criterion cannot name actors and apply to all actors")
        return self

    def owed_by(self, role: ActorRole) -> bool:
        """Whether `role` owes this criterion, directly or through a collective noun."""
        return self.applies_to_all_actors or any(
            role in ActorRole.from_value(actor).covered_roles for actor in self.actors
        )

    @property
    def mandatory(self) -> bool:
        """Whether the rule can pass only if this criterion passes.

        Derived, never authored: a duty the gap layer judges. A permission or a duty reported
        without a verdict is listed with its rule but cannot fail it."""
        return (
            self.kind in {NormKind.OBLIGATION, NormKind.PROHIBITION}
            and self.verification_mode is VerificationMode.JUDGED_BY_GAP_ANALYSIS
        )


class ReportNorm(BaseModel):
    """A non-judged report statement rendered from one canonical norm.

    This is deliberately not authored in ``spec.yaml``.  The loader materialises it from a norm
    marked ``report_only`` and retains the rule(s) that activate its report.  Thus an allowed route
    legal relief, or scope limit has the same single source of truth as an obligation, but cannot
    be mistaken for a criterion whose failure decides a compliance verdict.
    """

    model_config = ConfigDict(frozen=True)

    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    kind: NormKind
    actors: list[str]
    actor_categories: list[ActorCategory]
    applies_to_all_actors: bool = False
    targets: list[str]
    action: str = Field(min_length=1)
    norm_text: str = Field(min_length=1)
    conditions: LogicalExpression | None
    exceptions: LogicalExpression | None
    source_spans: list[str] = Field(min_length=1)
    activation_rule_ids: list[str] = Field(min_length=1)
    verification_mode: VerificationMode

    @model_validator(mode="after")
    def _actor_scope_is_unambiguous(self) -> ReportNorm:
        if self.actors and self.applies_to_all_actors:
            raise ValueError("report norm cannot name actors and apply to all actors")
        if self.actor_categories and self.applies_to_all_actors:
            raise ValueError("universal report norm cannot name actor categories")
        return self


class PolicyRule(BaseModel):
    """One obligation the documentation is checked against."""

    rule_id: str = Field(pattern=r"^AIA-RULE-[A-Za-z0-9-]+$")
    # Stable, human-readable canonical identifier; distinct from AIA-NORM, AIA-CQ, and AIA-TEXT.
    requirement: str  # the obligation, in the Commission's own wording
    action: str | None = Field(default=None, min_length=1, max_length=80)
    """What the duty-holder must do, in a few plain imperative words ("Report serious incidents to
    the market surveillance authority"), condensed from the norms the rule carries. A label for a
    reader scanning the report, never a statement of the law: the law is `requirement`, and the
    judge never sees this field. Every rule in the spec carries one, enforced by a test."""
    source: LegalSource
    applies_to_risk_class: list[RiskClass] = []
    """WHICH tiers owe this. Empty ONLY for an Art. 50 rule, which gates on a duty instead — see
    `applies_to_transparency_duty`. The default is empty rather than required so that an Art. 50
    rule need not write `applies_to_risk_class: []` to say something it does not mean; a rule that
    names neither axis is rejected by the validator below, so nothing slips through unactivated."""

    applies_to_role: list[ActorRole]

    applies_to_transparency_duty: list[TransparencyDuty] = []
    """WHICH Art. 50 duty makes this rule fire. Empty is the ordinary case: the rule gates on the
    risk class like every other.

    A non-empty list REPLACES the tier condition rather than narrowing it, and that is the whole
    reason the field exists. Art. 50 cuts across the Art. 6 tiers: a minimal-risk text generator
    owes 50(2) and a high-risk scorer owes nothing under Art. 50 at all. There is no set of risk
    classes that expresses "whenever this duty attached", so a rule written with
    `applies_to_risk_class` would either miss the minimal-risk system or raise Art. 50 against every
    high-risk one.

    Several duties in one list means ANY of them fires the rule, and 50(4) is why: one paragraph,
    two subparagraphs, deep fakes and published public-interest text — the same provision, cited
    once, reached by either duty."""

    @model_validator(mode="after")
    def _gates_on_a_tier_or_a_duty_but_not_both(self) -> PolicyRule:
        """Exactly one activation axis. Both, or neither, is a rule that fires at the wrong times.

        Naming both would make an Art. 50 duty conditional on a tier the Article does not mention.
        Naming neither leaves a rule with nothing to activate it, which reads in the spec as covered
        and in every report as absent."""
        if self.applies_to_transparency_duty and self.applies_to_risk_class:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: names both applies_to_transparency_duty and "
                f"applies_to_risk_class. Art. 50 attaches independently of the risk tier — a duty "
                f"rule must leave applies_to_risk_class empty."
            )
        if not self.applies_to_transparency_duty and not self.applies_to_risk_class:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: names neither applies_to_risk_class nor "
                f"applies_to_transparency_duty, so nothing can ever activate it."
            )
        return self

    @model_validator(mode="after")
    def _duty_is_owed_by_a_role_this_rule_names(self) -> PolicyRule:
        """An Art. 50 rule must be filed under the role the Article puts the duty on.

        `TransparencyDuty.owed_by` already knows: (1) and (2) bind the provider, (3) and (4) the
        deployer. Filing 50(3) under the provider would select it for a party that cannot discharge
        it and leave the deployer's duty unreported — the split this enum exists to preserve."""
        for duty in self.applies_to_transparency_duty:
            if duty.owed_by not in self.applies_to_role:
                raise ValueError(
                    f"PolicyRule {self.rule_id!r}: Art. 50({duty.paragraph}) is owed by "
                    f"{duty.owed_by.value}, which is not among applies_to_role "
                    f"({[r.value for r in self.applies_to_role]})."
                )
        return self

    applies_to_route: HighRiskRoute | None = None
    """WHICH of Art. 6's two doors this rule needs the use case to have come through, or None for
    the ordinary case where it does not care.

    None means NO CONDITION, not "neither" — Arts. 9-15 and 17-21 bind every high-risk system
    whichever door it came through, and that is most of the ruleset. Art. 43 is why the field
    exists: 43(3) governs an Annex I system and 43(1)-(2) an Annex III one, so a single rule would
    have to cite one of them at both."""

    applies_to_annex_iii_area: list[AnnexIIIArea] = []
    """WHICH Annex III areas this rule fires for. Empty is the ordinary case: no area condition.

    A non-empty list is a condition on the AREA and therefore also on the route — an Annex I system
    has no Annex III area, so it can never match one. Art. 43 again: 43(1) reaches Annex III point 1
    alone and 43(2) points 2 to 8, and until this field existed the spec carried 43(2) with the
    comment "employment is Annex III point 4" and fired it at biometrics too. A condition written in
    a comment is not a condition."""
    applies_to_prohibited_practice: list[ProhibitedPractice] = []
    """WHICH Art. 5(1) practice this rule fires for. Empty is the ordinary case: no condition.

    A non-empty list is how a rule reaches the LAWFUL BRANCH of a prohibition. Most of Art. 5 bans
    outright and a banned practice owes nothing but withdrawal. Point (h) is the exception: it bans
    real-time remote biometric identification for law enforcement "unless and in so far as such use
    is strictly necessary" for the objectives it lists, and Art. 5(5) lets a Member State authorise
    that use. A deployer on that branch owes Art. 5(2), (3) and (4) — a fundamental rights impact
    assessment, an EU database registration, prior judicial authorisation, per-use notification.
    Naming the practice is what keeps those duties off a system banned for social scoring, which has
    no lawful branch and owes none of them."""
    requires_provider_reallocation: bool = False
    """Whether this rule activates ONLY where Art. 25 has moved the provider role to another party.

    `False` is no condition, and is every rule but one. `True` says the obligation does not exist
    until a reallocation has actually occurred — Art. 25(2)'s cooperation duty binds the party that
    placed the system on the market and then stopped being its provider, and there is no such party
    unless Art. 25(1) or 25(3) fired.

    This is the one activation condition answered by a QUESTION rather than by the classification:
    `gap.roles` asks it, and `select_rules` takes the answer. Withholding here is right where
    withholding elsewhere was not — Art. 27 is a duty that exists and may or may not reach a given
    deployer, whereas this one does not exist at all until the role moves. Asserting it on every
    high-risk system would invent a party and give it homework.

    A run where the question ABSTAINED leaves this unselected, and the report carries the
    unresolved Art. 25 answer so the silence is visible rather than implied."""

    requires_real_world_testing: bool = False
    """Whether this rule activates only where the provider is testing the system IN REAL WORLD
    CONDITIONS outside a sandbox under Art. 60.

    The second question-answered condition, and it works the OPPOSITE WAY ROUND to the first.
    `requires_provider_reallocation` withholds unless the answer positively says the role moved,
    because a duty owed by a party the facts do not produce is invented. Here the duties are owed
    by a party who certainly exists — this system's provider — and turn on something they are
    doing that a technical file has no reason to mention. So silence selects, and only a positive
    `RealWorldTesting.NONE` withholds, on the same reasoning the cascade applies to Art. 2(1): a
    document that never addresses a question has not answered it in the reader's favour.

    Six duties depend on it — Art. 60(4)'s eleven conditions, 60(7)'s incident, mitigation and
    recall duties, 60(8)'s notification, and Art. 61's informed consent — and every one of them
    binds BEFORE OR DURING testing, which is before the technical file is finished. Reporting them
    late is reporting them uselessly."""

    activation_condition: str | None = None
    """WHICH members of the role owe this, where the Act binds only some of them — stated plainly,
    in terms of the organisations concerned rather than of whoever is reading.

    The Regulation sometimes narrows a duty by a fact about the ORGANISATION rather than about the
    system. Art. 27 is the case: the fundamental rights impact assessment binds deployers that are
    bodies governed by public law or private entities providing public services, not deployers at
    large. Nothing in a system's documentation establishes that, and nothing in this ruleset can
    derive it — READ, NEVER DERIVED, the same discipline as Art. 6(1)(b) and Art. 2(4) in the
    cascade.

    IT NARROWS THE DUTY-HOLDER, NOT THE REPORT. Such a rule is still selected, still listed under
    its role, and still counted. The report describes what the Act requires of each role for this
    system; it is not addressed to one organisation, and dropping an obligation into a "might not
    apply" list would be the tool deciding on someone's behalf which of their duties to demote —
    the same error as omitting a role because no ruleset was written for it. What this field buys
    is that the obligation is stated WITH its condition rather than as an unqualified duty of every
    deployer."""

    guidance_refs: list[str] = []
    """Snippet ids into the guidance store, where the Commission has read a provision this rule
    cites and the reading changes what counts as evidence.

    THE ONLY THING A RULE AUTHORS. `guidance_context` and `guidance_sources` below are filled by the
    loader from these ids, exactly as `requirement` is filled from `source` — so a rule cannot
    hand-write an interpretation any more than it can hand-write the law, and a ref naming a snippet
    that does not exist fails the spec load rather than the run.

    Empty is the ordinary case and should stay that way. A rule reaches for guidance only where the
    enacted text leaves the question open; most do not."""

    guidance_context: str = ""
    """The verbatim guidance passages, injected at load. Goes into the judge's prompt LABELLED
    non-binding, beside the enacted text and never merged with it."""

    guidance_sources: list[GuidanceSource] = []
    """Citations for whatever is in `guidance_context`, injected at load and carried onto any
    finding this rule produces — so a verdict that leaned on Commission interpretation says so
    rather than presenting itself as resting on the Article alone."""

    qualified_by: list[dict[str, str]] = []
    """OTHER provisions that condition this one, each `{article, paragraph}` — the only place a rule
    names enacted text besides `source` and `source.annex`. The labels are strings, as in
    `LegalSource`, so an address written here compares equal to the same address written there.

    A duty and its qualifier are often written apart. Art. 50(1) says a chatbot must disclose that
    it is one; Art. 50(5) says the disclosure must be clear, distinguishable and given at the latest
    at first interaction. A rule citing (1) alone passes a disclosure buried in a footer, and the
    fix cannot be to cite Art. 50 whole: all four transparency rules would then carry all four
    duties, and each finding would point at the Article rather than at the paragraph breached.

    Resolved at load into `qualifier_context` and carried into the judge prompt in its own block, so
    `requirement` stays a literal substring of the paragraph the finding cites."""

    qualifier_context: str = ""
    """The verbatim text of the provisions `qualified_by` names, injected at load. Labelled with its
    own Article and paragraph, because a judge shown two provisions must be able to tell which one
    the verdict is about."""

    annex_context: str = ""
    """The verbatim text of the Annex `source.annex` names, injected at load.

    THE ANNEX IS OFTEN THE REQUIREMENT. Art. 11(1) says the technical documentation "shall contain,
    at a minimum, the elements set out in Annex IV" — the Article names a list and the Annex is the
    list, so a `completeness` check resolved from the Article alone asks a judge to find every
    element of something it cannot see. Supplied labelled and separately, never merged into
    `requirement`, which stays a literal substring of the cited Article.

    Filled by the loader, like `requirement` and `guidance_context`; a rule hand-writing it fails
    the load."""

    criteria: list[RuleCriterion] = []
    """The norms this rule implements, each judged and reported separately.

    Empty is the ordinary case: the rule is judged as one obligation. A non-empty list makes the
    rule an AGGREGATE — its verdict is computed from the criteria, and passes only when every
    mandatory criterion passes. A non-document-verifiable rule may instead have a reported-only
    list: all criteria are then `not_applicable`, so it cannot manufacture a pass. The loader
    resolves each entry from the canonical norm inventory, and `build_normative_coverage.py
    --check` proves the list matches the norms that point back."""

    @model_validator(mode="after")
    def _criteria_are_unique_and_decidable(self) -> PolicyRule:
        ids = [criterion.norm_id for criterion in self.criteria]
        duplicates = sorted({norm_id for norm_id in ids if ids.count(norm_id) > 1})
        if duplicates:
            raise ValueError(f"PolicyRule {self.rule_id!r}: duplicate criteria {duplicates}")
        kinds = {criterion.kind for criterion in self.criteria}
        if len(kinds) > 1:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: criteria mix norm kinds "
                f"{sorted(kind.value for kind in kinds)}. A rule implements one legal kind; "
                "permissions and legal consequences are report norms."
            )
        verification_modes = {criterion.verification_mode for criterion in self.criteria}
        if len(verification_modes) > 1:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: criteria mix verification modes "
                f"{sorted(mode.value for mode in verification_modes)}. A rule has one "
                "deterministic "
                "assessment treatment."
            )
        # One rule may bind several roles, with each criterion owed by its own duty-holders: Art.
        # 60(4)(h) and (j) bind the deployer beside the provider, the rest the provider alone. Each
        # role is then reported only the criteria it owes, so a criterion must be owed by one of
        # the rule's roles, and every role must owe at least one criterion.
        for criterion in self.criteria:
            if not any(criterion.owed_by(role) for role in self.applies_to_role):
                raise ValueError(
                    f"PolicyRule {self.rule_id!r}: criterion {criterion.norm_id} names actors "
                    f"{criterion.actors}, none of which is or covers a role in applies_to_role "
                    f"{sorted(role.value for role in self.applies_to_role)}, so no report could "
                    "show it."
                )
        for role in self.applies_to_role:
            if self.criteria and not self.criteria_for(role):
                raise ValueError(
                    f"PolicyRule {self.rule_id!r}: applies to {role.value}, but no criterion "
                    "names that role, so its report would hold an empty rule."
                )
        if (
            self.criteria
            and self.document_verifiable
            and not any(criterion.mandatory for criterion in self.criteria)
        ):
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: document-verifiable criteria has no mandatory "
                "criterion, so nothing could ever fail the rule."
            )
        return self

    def criteria_for(self, role: ActorRole) -> list[RuleCriterion]:
        """The criteria `role` owes, in the rule's order."""
        return [criterion for criterion in self.criteria if criterion.owed_by(role)]

    def for_role(self, role: ActorRole) -> PolicyRule:
        """This rule as `role` reads it: only the criteria that role owes."""
        scoped = self.criteria_for(role)
        if len(scoped) == len(self.criteria):
            return self
        return self.model_copy(update={"criteria": scoped})

    obligation_status: ObligationStatus
    check_type: CheckType
    evidence_expected: str  # what in the documentation would satisfy this
    document_verifiable: bool  # see model_validator below
    report_as_public_authority_notice: bool = False
    """Render activated public-authority norms separately, never as a provider/deployer duty."""
    effective_date: date | None = None
    """WHEN this obligation starts to apply, where that does not depend on the Art. 6 route."""

    effective_date_by_route: dict[HighRiskRoute, date] = {}
    """WHEN it starts to apply, where Art. 113 gives the two doors DIFFERENT dates.

    Empty is the ordinary case. It is non-empty for Chapter III Sections 1 to 3 — Arts. 6-27 — and
    the reason is Regulation (EU) 2026/1744: it rewrote Art. 113 so those Sections apply from
    2 December 2027 to a system that is high-risk under Art. 6(2) and Annex III, and from
    2 August 2028 to one high-risk under Art. 6(1) and Annex I.

    So the SAME rule now starts on two different days depending on which door the system came
    through, and a single `effective_date` cannot say that. This is structurally the same gap
    `applies_to_route` was built for — there the route decided WHICH law applies, here it decides
    WHEN — and it is answered the same way rather than by picking one date and rounding.

    Sections 4 and 5 were NOT moved. Arts. 43 and 47-49 keep the general date, which is why the
    conformity assessment and registration rules carry a plain `effective_date` while the
    requirements they attest to do not."""

    effective_date_note: str | None = None
    """WHY this obligation's timing is not what a reader would assume — carried to the report, not
    left in a comment only we read.

    Two shapes, both real in the current ruleset:

    A DATE THAT IS CONTESTED. Art. 113's limbs describe systems that ARE high-risk, and Art. 6(4)
    binds a provider who concluded theirs is NOT, so no limb reaches it literally. A date had to be
    chosen; choosing silently would present our reading as the Act's. The note names the other one
    and what turns on it.

    A DATE THAT IS RIGHT AND READS WRONG. Chapter III Section 5 was not moved, so conformity
    assessment and registration apply from 2 August 2026 while the requirements they attest to wait
    until December 2027. A reader meeting that with no explanation reasonably concludes the tool is
    broken, and the more damaging response is to disregard the date.

    Distinct from `activation_condition`, which narrows WHO owes a duty; this qualifies WHEN. Both
    are reported beside the obligation and neither withholds it."""

    @field_validator("qualified_by", mode="before")
    @classmethod
    def _qualifier_labels_are_strings(cls, value: object) -> object:
        """`{article: 50, paragraph: 5}` becomes `{"article": "50", "paragraph": "5"}`.

        The same normalisation `LegalSource` runs on its own labels, and needed for the same
        reason: `test_every_provision_a_rule_is_qualified_by_reaches_that_rule` matches these
        addresses against ledger keys and rule sources, and `50 != "50"`."""
        if not isinstance(value, list):
            return value
        return [
            {k: str(v) for k, v in cite.items()} if isinstance(cite, dict) else cite
            for cite in value
        ]

    @model_validator(mode="after")
    def _one_way_of_saying_when(self) -> PolicyRule:
        """A rule states its date one way or the other, never both.

        Both would leave two answers to one question with nothing deciding between them, and the
        one a reader got would depend on which field the renderer happened to read."""
        if self.effective_date is not None and self.effective_date_by_route:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: sets both effective_date and "
                f"effective_date_by_route. Art. 113 gives this obligation either one date or one "
                f"per Art. 6 route — say which."
            )
        return self

    def effective_date_for(self, route: HighRiskRoute | None) -> date | None:
        """The date this obligation applies from, for a use case that came through `route`.

        An unknown route resolves to the EARLIEST date on offer, deliberately. The alternative is
        telling a reader they have until 2028 when the answer might have been 2027, and a deadline
        that is wrong in that direction is the one that costs them. Every high-risk use case
        actually carries a route, so this is a fallback rather than a normal path."""
        if not self.effective_date_by_route:
            return self.effective_date
        if route is not None and route in self.effective_date_by_route:
            return self.effective_date_by_route[route]
        return min(self.effective_date_by_route.values())

    status: Literal["active", "postponed", "amended"]
    # "postponed": adopted but not yet applicable (e.g. Annex III obligations whose
    # application date was pushed back). Regulatory movement lives in DATA, not in code.
    amended_by: str | None = None

    @model_validator(mode="after")
    def _area_and_route_agree(self) -> PolicyRule:
        """Naming Annex III areas already fixes the route, so a rule may not also claim Annex I.

        Not pedantry: such a rule could never fire — an Annex I use case carries no Annex III area —
        and a rule that never fires is indistinguishable in a report from an obligation nobody
        owes."""
        if self.applies_to_annex_iii_area and self.applies_to_route is HighRiskRoute.ANNEX_I:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: applies_to_annex_iii_area names areas but "
                f"applies_to_route is annex_i. An Annex I use case has no Annex III area, so this "
                f"rule could never activate."
            )
        # Same shape, same reason: a practice is carried only by the tier its point produces, so a
        # rule naming one and not naming that tier could never fire. Every point but (h) produces
        # PROHIBITED; point (h) bans only use, so its system keeps an ordinary tier, high-risk
        # under Annex III(1)(a).
        tiers = set(self.applies_to_risk_class or [])
        for practice in self.applies_to_prohibited_practice:
            needed = RiskClass.HIGH_RISK if practice.bans_only_use else RiskClass.PROHIBITED
            if needed not in tiers:
                raise ValueError(
                    f"PolicyRule {self.rule_id!r}: applies_to_prohibited_practice names "
                    f"{practice.value} but applies_to_risk_class does not include {needed.value}, "
                    f"the tier that practice is classified under, so this rule could never "
                    f"activate for it."
                )
        return self

    @model_validator(mode="after")
    def _warn_substance_but_not_document_verifiable(self) -> PolicyRule:
        """A substance check that isn't document-verifiable is almost always a modelling slip:
        substance verdicts (including INADEQUATE) are drawn FROM the documentation, so a rule
        that demands substance yet claims it can't be seen in the docs contradicts itself.
        Warn rather than raise — the spec author may have a deliberate reason."""
        if self.check_type == CheckType.SUBSTANCE and not self.document_verifiable:
            warnings.warn(
                f"PolicyRule {self.rule_id!r}: check_type=substance but "
                f"document_verifiable=False — a substance judgement is drawn from the "
                f"documentation, so this pairing is likely a mistake.",
                stacklevel=2,
            )
        return self


class NationalLawNotice(BaseModel):
    """A canonical national-law boundary materialised for a live report."""

    norm_id: str = Field(pattern=r"^AIA-NORM-[A-Z0-9-]+$")
    prohibited_practices: list[ProhibitedPractice] = Field(min_length=1)
    detail: str = Field(min_length=1)


class PolicyRuleset(BaseModel):
    """The full loaded ruleset for one pinned version of the Regulation."""

    spec_version: str
    act_version_date: date
    source_note: str  # provenance: derived from EC Compliance Checker
    rules: list[PolicyRule]
    national_law_notices: list[NationalLawNotice] = []
    report_norms: list[ReportNorm] = []
    temporal_regimes: list[TemporalRegime] = []

    @model_validator(mode="after")
    def _report_norms_are_unique_and_target_live_rules(self) -> PolicyRuleset:
        ids = [norm.norm_id for norm in self.report_norms]
        duplicates = sorted({norm_id for norm_id in ids if ids.count(norm_id) > 1})
        if duplicates:
            raise ValueError(f"PolicyRuleset: duplicate report norm ids {duplicates}")
        known_rules = {rule.rule_id for rule in self.rules}
        for norm in self.report_norms:
            missing = sorted(set(norm.activation_rule_ids) - known_rules)
            if missing:
                raise ValueError(
                    f"Report norm {norm.norm_id!r} names absent activation rule(s) {missing}"
                )
        regime_ids = [regime.regime_id for regime in self.temporal_regimes]
        duplicate_regimes = sorted({item for item in regime_ids if regime_ids.count(item) > 1})
        if duplicate_regimes:
            raise ValueError(f"PolicyRuleset: duplicate temporal regime ids {duplicate_regimes}")
        known_regimes = set(regime_ids)
        for rule in self.rules:
            missing_regimes = sorted(
                {
                    criterion.temporal_regime_id
                    for criterion in rule.criteria
                    if criterion.temporal_regime_id is not None
                }
                - known_regimes
            )
            if missing_regimes:
                raise ValueError(
                    f"PolicyRule {rule.rule_id!r}: criteria name absent temporal regime(s) "
                    f"{missing_regimes}"
                )
        return self

    def temporal_regime_for(self, rule: PolicyRule) -> TemporalRegime | None:
        """Return the one canonical timing regime for a fully migrated rule.

        A rule may use canonical timing only once every mandatory criterion names the same regime.
        Anything less would let a timed criterion hide an untimed one, or let two legal dates become
        one report date. Rules not yet migrated keep their legacy timing fields until their norms
        are reconciled.
        """
        mandatory = [criterion for criterion in rule.criteria if criterion.mandatory]
        if not mandatory or any(criterion.temporal_regime_id is None for criterion in mandatory):
            return None
        regime_ids = {criterion.temporal_regime_id for criterion in mandatory}
        if len(regime_ids) != 1:
            return None
        regime_id = regime_ids.pop()
        return next((item for item in self.temporal_regimes if item.regime_id == regime_id), None)
