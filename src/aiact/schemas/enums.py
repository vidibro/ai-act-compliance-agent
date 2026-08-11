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

    OUT_OF_SCOPE = "out_of_scope"
    """Art. 2. The Regulation does not govern this system at all — military, defence or national
    security use (2(3)), scientific research and development (2(6)), pre-market research and
    testing (2(8)), purely personal non-professional use (2(10)), or a free and open-source release
    that is not high-risk and falls under neither Art. 5 nor Art. 50 (2(12)).

    NOT the same as `minimal`, and the difference is the whole point of the class: a minimal-risk
    system is inside the Regulation and still owes Art. 4 AI literacy, with Art. 50 possibly
    attaching. An out-of-scope system owes nothing under this Regulation. Collapsing the two tells
    a defence contractor they hold duties the legislator expressly withheld."""

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
    measured — do not collapse them.

    THE BOUNDARY, settled 2026-07-28 because the eval kept landing on it. The deciding question is
    not how much text is present, it is WHAT THE PROVIDER MUST DO NEXT:

      GAP        -> "write this."      The content does not exist anywhere in the document.
      INADEQUATE -> "strengthen this." The content exists and falls short.

    So a CROSS-REFERENCE TO A SECTION THAT DOES NOT EXIST is a GAP, not an INADEQUATE. A file
    saying "the oversight measures are described in §7" when there is no §7 has mentioned the
    obligation and documented nothing; the work still to be done is writing it from scratch. The
    sentence is a pointer, not evidence, and its presence changes nothing a provider must do.

    Recorded here rather than argued case by case, because this was the answer key's most-hit
    boundary and it had no stated reason behind it."""

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


class AnnexIProduct(StrEnum):
    """Art. 6(1), Annex I. The twenty Union harmonisation instruments, named by the product they
    govern rather than by directive number — a system card says "surgical robot", never
    "Regulation (EU) 2017/745".

    The SECTION a value belongs to decides which obligations follow, so it is carried in the enum
    rather than looked up: see `section` and `chapter_iii_applies`."""

    # --- Section A — New Legislative Framework. Chapter III applies in full. ---
    MACHINERY = "machinery"  # Annex I(A)(1) — Directive 2006/42/EC
    TOYS = "toys"  # Annex I(A)(2) — Directive 2009/48/EC
    RECREATIONAL_CRAFT = "recreational_craft"  # Annex I(A)(3) — Directive 2013/53/EU
    LIFTS = "lifts"  # Annex I(A)(4) — Directive 2014/33/EU
    EXPLOSIVE_ATMOSPHERES = "explosive_atmospheres"  # Annex I(A)(5) — Directive 2014/34/EU
    RADIO_EQUIPMENT = "radio_equipment"  # Annex I(A)(6) — Directive 2014/53/EU
    PRESSURE_EQUIPMENT = "pressure_equipment"  # Annex I(A)(7) — Directive 2014/68/EU
    CABLEWAYS = "cableways"  # Annex I(A)(8) — Regulation (EU) 2016/424
    PERSONAL_PROTECTIVE_EQUIPMENT = "personal_protective_equipment"  # Annex I(A)(9) — 2016/425
    GAS_APPLIANCES = "gas_appliances"  # Annex I(A)(10) — Regulation (EU) 2016/426
    MEDICAL_DEVICES = "medical_devices"  # Annex I(A)(11) — Regulation (EU) 2017/745
    IVD_MEDICAL_DEVICES = "ivd_medical_devices"  # Annex I(A)(12) — Regulation (EU) 2017/746

    # --- Section B — other harmonisation legislation. Art. 2(2) LIMITS what applies. ---
    CIVIL_AVIATION_SECURITY = "civil_aviation_security"  # Annex I(B)(13) — Reg (EC) 300/2008
    TWO_THREE_WHEEL_VEHICLES = "two_three_wheel_vehicles"  # Annex I(B)(14) — Reg (EU) 168/2013
    AGRICULTURAL_VEHICLES = "agricultural_vehicles"  # Annex I(B)(15) — Reg (EU) 167/2013
    MARINE_EQUIPMENT = "marine_equipment"  # Annex I(B)(16) — Directive 2014/90/EU
    RAIL_INTEROPERABILITY = "rail_interoperability"  # Annex I(B)(17) — Directive (EU) 2016/797
    MOTOR_VEHICLES = "motor_vehicles"  # Annex I(B)(18) — Regulation (EU) 2018/858
    VEHICLE_GENERAL_SAFETY = "vehicle_general_safety"  # Annex I(B)(19) — Reg (EU) 2019/2144
    CIVIL_AVIATION_UAS = "civil_aviation_uas"  # Annex I(B)(20) — Reg (EU) 2018/1139

    @property
    def section(self) -> str:
        """ "A" or "B" — which half of Annex I lists this instrument."""
        return "B" if self in _ANNEX_I_SECTION_B else "A"

    @property
    def legislation(self) -> str:
        """The Union instrument this product is covered by, as Annex I cites it."""
        return _ANNEX_I_LEGISLATION[self]

    @property
    def who_decides_conformity(self) -> str:
        """Who can answer Art. 6(1)(b) for this product — the question this tool declines.

        Named rather than left to the reader: "consult a specialist" is not actionable, and the
        specialist differs by sector. The route is set by the instrument above, which this tool
        does not carry, so this is a handover and should read like one."""
        return _ANNEX_I_CONFORMITY_ROUTE[self]

    @property
    def chapter_iii_applies(self) -> bool:
        """Art. 2(2): for a Section B product classified high-risk under Art. 6(1), ONLY Art. 6(1),
        Arts. 102-109 and Art. 112 apply. Chapter III does not — so an aircraft or motor-vehicle
        system is high-risk AND owes none of Art. 9-15. Raising them anyway would accuse a
        provider of gaps the Regulation does not put on them."""
        return self.section == "A"


_ANNEX_I_SECTION_B = frozenset(
    {
        AnnexIProduct.CIVIL_AVIATION_SECURITY,
        AnnexIProduct.TWO_THREE_WHEEL_VEHICLES,
        AnnexIProduct.AGRICULTURAL_VEHICLES,
        AnnexIProduct.MARINE_EQUIPMENT,
        AnnexIProduct.RAIL_INTEROPERABILITY,
        AnnexIProduct.MOTOR_VEHICLES,
        AnnexIProduct.VEHICLE_GENERAL_SAFETY,
        AnnexIProduct.CIVIL_AVIATION_UAS,
    }
)


# Annex I cites each instrument in full; these are the short forms a report can carry. Every
# product is listed with no default, so an act version that amends Annex I fails on a missing
# key instead of reporting a product with no instrument behind it.
_ANNEX_I_LEGISLATION: dict[AnnexIProduct, str] = {
    AnnexIProduct.MACHINERY: "Directive 2006/42/EC (machinery)",
    AnnexIProduct.TOYS: "Directive 2009/48/EC (safety of toys)",
    AnnexIProduct.RECREATIONAL_CRAFT: "Directive 2013/53/EU (recreational craft)",
    AnnexIProduct.LIFTS: "Directive 2014/33/EU (lifts and safety components for lifts)",
    AnnexIProduct.EXPLOSIVE_ATMOSPHERES: "Directive 2014/34/EU (ATEX equipment)",
    AnnexIProduct.RADIO_EQUIPMENT: "Directive 2014/53/EU (radio equipment)",
    AnnexIProduct.PRESSURE_EQUIPMENT: "Directive 2014/68/EU (pressure equipment)",
    AnnexIProduct.CABLEWAYS: "Regulation (EU) 2016/424 (cableway installations)",
    AnnexIProduct.PERSONAL_PROTECTIVE_EQUIPMENT: (
        "Regulation (EU) 2016/425 (personal protective equipment)"
    ),
    AnnexIProduct.GAS_APPLIANCES: "Regulation (EU) 2016/426 (appliances burning gaseous fuels)",
    AnnexIProduct.MEDICAL_DEVICES: "Regulation (EU) 2017/745 (medical devices)",
    AnnexIProduct.IVD_MEDICAL_DEVICES: (
        "Regulation (EU) 2017/746 (in vitro diagnostic medical devices)"
    ),
    AnnexIProduct.CIVIL_AVIATION_SECURITY: (
        "Regulation (EC) No 300/2008 (civil aviation security)"
    ),
    AnnexIProduct.TWO_THREE_WHEEL_VEHICLES: (
        "Regulation (EU) No 168/2013 (two- or three-wheel vehicles and quadricycles)"
    ),
    AnnexIProduct.AGRICULTURAL_VEHICLES: (
        "Regulation (EU) No 167/2013 (agricultural and forestry vehicles)"
    ),
    AnnexIProduct.MARINE_EQUIPMENT: "Directive 2014/90/EU (marine equipment)",
    AnnexIProduct.RAIL_INTEROPERABILITY: "Directive (EU) 2016/797 (rail interoperability)",
    AnnexIProduct.MOTOR_VEHICLES: "Regulation (EU) 2018/858 (approval of motor vehicles)",
    AnnexIProduct.VEHICLE_GENERAL_SAFETY: "Regulation (EU) 2019/2144 (vehicle general safety)",
    AnnexIProduct.CIVIL_AVIATION_UAS: (
        "Regulation (EU) 2018/1139 (civil aviation, unmanned aircraft)"
    ),
}

_NOTIFIED_BODY = (
    "the notified body designated under that legislation, or the regulatory-affairs lead who "
    "holds the product's conformity assessment file"
)
_TYPE_APPROVAL = (
    "the type-approval authority or technical service that approved the vehicle, or the "
    "homologation lead who holds its approval file"
)
# Who settles Art. 6(1)(b) per sector. NOT legal advice and not a route this tool applies —
# it is the handover, so a parked question names its owner instead of stopping at "ask a
# specialist". Every product is listed with no default: a default would hand a newly added
# Annex I instrument a plausible-sounding wrong answer — "ask the notified body" is right for
# most Section A products and wrong for every transport one — and the report would state it
# confidently. A missing key raises instead.
_ANNEX_I_CONFORMITY_ROUTE: dict[AnnexIProduct, str] = {
    # Section A — notified-body regimes.
    AnnexIProduct.TOYS: _NOTIFIED_BODY,
    AnnexIProduct.RECREATIONAL_CRAFT: _NOTIFIED_BODY,
    AnnexIProduct.LIFTS: _NOTIFIED_BODY,
    AnnexIProduct.EXPLOSIVE_ATMOSPHERES: _NOTIFIED_BODY,
    AnnexIProduct.RADIO_EQUIPMENT: _NOTIFIED_BODY,
    AnnexIProduct.PRESSURE_EQUIPMENT: _NOTIFIED_BODY,
    AnnexIProduct.CABLEWAYS: _NOTIFIED_BODY,
    AnnexIProduct.PERSONAL_PROTECTIVE_EQUIPMENT: _NOTIFIED_BODY,
    AnnexIProduct.GAS_APPLIANCES: _NOTIFIED_BODY,
    AnnexIProduct.MACHINERY: (
        "the notified body, or the engineer who can say whether this machine is listed in "
        "Annex IV of the Machinery Directive — listed machines need one, others self-certify"
    ),
    AnnexIProduct.MEDICAL_DEVICES: (
        "the notified body designated under the MDR, or the regulatory-affairs lead who holds "
        "the device's risk class (Annex VIII) and conformity assessment route"
    ),
    AnnexIProduct.IVD_MEDICAL_DEVICES: (
        "the notified body designated under the IVDR, or the regulatory-affairs lead who holds "
        "the device's risk class and conformity assessment route"
    ),
    # Section B — type-approval and sector-authority regimes.
    AnnexIProduct.TWO_THREE_WHEEL_VEHICLES: _TYPE_APPROVAL,
    AnnexIProduct.AGRICULTURAL_VEHICLES: _TYPE_APPROVAL,
    AnnexIProduct.MOTOR_VEHICLES: _TYPE_APPROVAL,
    AnnexIProduct.VEHICLE_GENERAL_SAFETY: _TYPE_APPROVAL,
    AnnexIProduct.CIVIL_AVIATION_SECURITY: (
        "the national civil aviation security authority, or EASA where the equipment falls "
        "under its remit"
    ),
    AnnexIProduct.CIVIL_AVIATION_UAS: (
        "EASA, or the design-organisation lead who holds the aircraft's certification basis"
    ),
    AnnexIProduct.RAIL_INTEROPERABILITY: (
        "the notified body for the interoperability constituent, or the national safety "
        "authority that authorised the subsystem"
    ),
    AnnexIProduct.MARINE_EQUIPMENT: (
        "the notified body under the Marine Equipment Directive, or the flag-state administration"
    ),
}


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
