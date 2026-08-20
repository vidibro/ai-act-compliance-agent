"""Enumerated types encoding the semantics of Regulation (EU) 2024/1689.

Every member carries its legal meaning and, where relevant, the source article.
These are the vocabulary the rest of the schema layer is built on; a bare identifier
list would lose the reasoning that later readers (human or model) depend on.
"""

from datetime import date
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

    GPAI_MODEL = "gpai_model"
    """Art. 3(63) + Chapter V. NOT A RISK TIER, and that is the point of having it.

    A general-purpose AI model is not classified by Art. 6 at all. It is regulated on a separate
    track — Art. 53 technical documentation, information to downstream providers, a copyright policy
    and a public training-data summary; Art. 55 more besides where it carries systemic risk. Asking
    which Annex III area a foundation model falls into is a category error, and answering `minimal`
    because it falls into none is a false clearance of a provider who owes Chapter V today.

    This class is a HANDOVER, in the same spirit as the Art. 6(1)(b) conformity handover: it names
    the regime that governs, says this tool does not apply it, and points the reader at what to
    read. It is emitted only for the MODEL. A system BUILT on a general-purpose model is an ordinary
    AI system (Art. 3(66)) and classifies through the cascade normally — an LLM-backed hiring tool
    is still Annex III(4) high-risk."""

    NEEDS_REVIEW = "needs_review"
    """Not a legal category — an engineering escape hatch. The agent could not reach a
    defensible verdict from the documentation. Preferable to a confident wrong answer;
    surfaced to a human reviewer."""


class ScopeExclusion(StrEnum):
    """Art. 2. WHICH paragraph withholds the Regulation from a system.

    Recorded rather than reduced to a boolean, for the reason `transparency_basis` exists: an
    exclusion that cannot name its paragraph is an assertion. Every one of these is written
    narrowly — "exclusively", "sole purpose", "purely", "prior to" — so for each there is a near
    neighbour that reads like it and is not it, and the paragraph is where that argument lives.

    Art. 2(2) is deliberately absent. It is not an exclusion but a LIMIT on what an Art. 6(1)
    Section B system owes, and it is carried on `AnnexIProduct.chapter_iii_applies`."""

    MILITARY_DEFENCE_NATIONAL_SECURITY = "military_defence_national_security"
    """Art. 2(3). Placed on the market, put into service or used EXCLUSIVELY for military, defence
    or national security purposes — regardless of the type of entity carrying out the activity, so
    a civilian body or a commercial vendor is equally covered. Turns on the purpose of USE: buying
    under defence-and-security procurement law settles which tendering rules apply and nothing
    about scope."""

    THIRD_COUNTRY_LAW_ENFORCEMENT_COOPERATION = "third_country_law_enforcement_cooperation"
    """Art. 2(4). A third-country public authority or an international organisation using AI in the
    framework of law enforcement or judicial cooperation with the Union or a Member State.

    THE ODD ONE OUT, and it is treated differently in the cascade. The paragraph applies only
    "provided that" the third country affords adequate safeguards for fundamental rights and
    freedoms — a condition about a COUNTRY, not about the system. No system description settles it;
    it is settled in the cooperation agreement and the Commission's assessment. So this exclusion is
    READ, never DERIVED, exactly as Art. 6(1)(b) is."""

    SCIENTIFIC_RESEARCH = "scientific_research"
    """Art. 2(6). Specifically developed and put into service for the SOLE purpose of scientific
    research and development. Science is the end, not a stage before something else — which is what
    separates it from 2(8)."""

    PRE_MARKET_DEVELOPMENT = "pre_market_development"
    """Art. 2(8). Research, testing or development activity PRIOR to being placed on the market or
    put into service. The paragraph's own last sentence excepts testing in real-world conditions,
    which Art. 3(57) defines as outside a laboratory or otherwise simulated environment."""

    PERSONAL_NON_PROFESSIONAL = "personal_non_professional"
    """Art. 2(10). The obligations of DEPLOYERS who are natural persons using AI in the course of a
    purely personal non-professional activity.

    Narrower than it looks, and the only exclusion attaching to an actor rather than to a system:
    it lifts the deployer's obligations and leaves the provider's untouched. A consumer product is
    not thereby outside the Regulation."""

    FREE_OPEN_SOURCE = "free_open_source"
    """Art. 2(12). Released under a free and open-source licence — UNLESS placed on the market or
    put into service as a high-risk system, or as one falling under Art. 5 or Art. 50. The
    carve-back is why this exclusion cannot be granted from the licence alone: it depends on the
    Art. 5 and Art. 50 answers, so those are decided first."""

    @property
    def paragraph(self) -> int:
        """The Art. 2 paragraph, for citation."""
        return _SCOPE_EXCLUSION_PARAGRAPH[self]

    @property
    def must_be_stated(self) -> bool:
        """True where the deciding condition is NOT a fact about the system, so no description can
        establish it and the tool must never infer it. Art. 2(4) alone: see its docstring."""
        return self is ScopeExclusion.THIRD_COUNTRY_LAW_ENFORCEMENT_COOPERATION


# No default, and every member listed. A dict.get() fallback would give a newly added exclusion a
# plausible wrong citation; a missing key raises instead.
_SCOPE_EXCLUSION_PARAGRAPH: dict[ScopeExclusion, int] = {
    ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY: 3,
    ScopeExclusion.THIRD_COUNTRY_LAW_ENFORCEMENT_COOPERATION: 4,
    ScopeExclusion.SCIENTIFIC_RESEARCH: 6,
    ScopeExclusion.PRE_MARKET_DEVELOPMENT: 8,
    ScopeExclusion.PERSONAL_NON_PROFESSIONAL: 10,
    ScopeExclusion.FREE_OPEN_SOURCE: 12,
}


class TerritorialLink(StrEnum):
    """Art. 2(1). WHICH limb brings the system within the Regulation's reach — or that none does.

    THE POSITIVE LIMB of Art. 2, and the one the cascade was missing. Paragraphs (3) to (12) are
    exclusions carved OUT of a Regulation assumed to apply; (1) is what makes it apply in the first
    place. Without this a system placed only outside the Union, whose output is never used here,
    comes back with a full risk tier and a list of duties nobody owes.

    THE DEFAULT IS THAT IT APPLIES, and `NOT_ADDRESSED` is how that is recorded honestly. Most
    documentation never mentions territory at all, so abstaining on silence would send nearly every
    case to needs_review, while picking a limb the text does not support would fabricate a finding.
    The member says exactly what happened — no limb was ruled out — and the assessment proceeds.
    Only `None`, an affirmative statement that the system reaches the Union nowhere, takes a system
    out. Over-inclusion, never a silent clearance: the same rule `_scope_exclusion` follows."""

    EU_PLACING_OR_SERVICE = "eu_placing_or_service"
    """2(1)(a). A provider placing the system on the market or putting it into service in the
    Union — irrespective of whether that provider is established inside the Union or in a third
    country. Establishment is not the test; where the system is placed is."""

    EU_DEPLOYER = "eu_deployer"
    """2(1)(b). A deployer whose place of establishment is, or who is located, within the Union."""

    THIRD_COUNTRY_OUTPUT_USED_IN_UNION = "third_country_output_used_in_union"
    """2(1)(c). A provider or deployer established in a third country where the OUTPUT the system
    produces is used in the Union. The reach that catches a system built and run entirely
    elsewhere, and the reason 'we do not operate in Europe' settles nothing on its own."""

    EU_SUPPLY_CHAIN = "eu_supply_chain"
    """2(1)(d)-(f). Importers and distributors, product manufacturers placing an AI system on the
    market with their product under their own name, and authorised representatives of providers not
    established in the Union. Grouped because they share one question — is this party putting the
    system onto the Union market — and each has its own obligations elsewhere."""

    AFFECTED_PERSONS_IN_UNION = "affected_persons_in_union"
    """2(1)(g). Affected persons located in the Union. Listed as a limb of reach rather than as a
    duty-holder: it is who the Regulation protects, not who it binds."""

    OUTSIDE_UNION = "outside_union"
    """NOT a limb — the finding that NO limb applies: the description positively establishes the
    system is not placed or put into service in the Union, has no deployer here, its output is not
    used here, and the persons it is used on are not here. The Regulation never applies.

    An explicit member rather than `None`, deliberately. `None` is what a brain returns when it has
    not answered, and everywhere else in this cascade that collapses to the SAFE reading — no
    exclusion, no Annex III area, no ban. Here the unsafe reading is the one that clears a system
    entirely, so it must be stated to be reached. Over-inclusion, never a silent clearance."""

    NOT_ADDRESSED = "not_addressed"
    """NOT a limb of the Article — a record that the description never addressed territory, so no
    limb was ruled out and the Regulation is presumed to apply.

    Kept as an answer rather than an abstention because the alternative is worse in both
    directions: declining would make needs_review the answer for almost every real document, and
    naming a limb would assert a fact the text never gave. A reader who needs certainty can see
    that this is what the tool found, and supply the missing sentence."""

    @property
    def rules_out_the_union(self) -> bool:
        """Whether this answer puts the system beyond the Regulation's reach.

        True for `OUTSIDE_UNION` alone. Every other member either names a limb that brings the
        system in or records that the question went unanswered, and both continue the assessment."""
        return self is TerritorialLink.OUTSIDE_UNION


class GpaiStatus(StrEnum):
    """Art. 3(63). WHAT the document describes, on the model/system line — and, for a model,
    whether it has been placed on the market yet.

    THREE VALUES, NOT A BOOLEAN, and the third is the point. Art. 3(63) excludes "AI models that are
    used for research, development or prototyping activities before they are placed on the market",
    so a pre-market model is not yet a GPAI model in the Article's sense. Answering that with a bare
    `false` would drop it back into the risk cascade and report `minimal` — telling a lab building a
    frontier model that it owes almost nothing, when what is true is that it owes Chapter V the day
    it ships. The exclusion is TEMPORAL, and a verdict that cannot express "not yet" turns a
    deadline into a clearance."""

    AI_SYSTEM = "ai_system"
    """Not a general-purpose model: an AI system, INCLUDING one built on such a model. Art. 3(66)
    makes a general-purpose AI system an ordinary AI system, so a chatbot or a hiring tool running
    on a foundation model classifies through the risk cascade normally."""

    GENERAL_PURPOSE_MODEL = "general_purpose_model"
    """A general-purpose AI model that has been placed on the market or put into service. Chapter V
    governs it now — Art. 53 throughout, Art. 55 where it carries systemic risk."""

    GENERAL_PURPOSE_MODEL_PRE_MARKET = "general_purpose_model_pre_market"
    """A general-purpose AI model still in research, development or prototyping, not yet placed on
    the market. Art. 3(63) puts it outside the definition FOR NOW, and Art. 2(8) excludes the
    development activity itself — but neither is a permanent state. Reported as a model with its
    obligations named and dated, so the reader learns what attaches on the day it ships rather than
    reading an exclusion as a clean bill of health."""

    @property
    def is_a_model(self) -> bool:
        """Whether the document describes a MODEL rather than a system — placed or not."""
        return self is not GpaiStatus.AI_SYSTEM


class ProhibitedPractice(StrEnum):
    """Art. 5(1). WHICH point bans the practice.

    It matters most here — this is the only class that tells a provider their system may not ship
    at all, and "Art. 5" alone gives them nothing to check the claim against, nor to argue with.

    Every point carries an exception or a qualifier, and several of them are where the real
    argument lives: (d) does not reach a system supporting a human assessment already grounded in
    objective facts, (f) does not reach medical or safety uses, (g) does not reach the labelling of
    lawfully acquired datasets, and (h) is lifted for three named law-enforcement objectives. A bare
    `true` cannot say which of those was considered."""

    SUBLIMINAL_MANIPULATION = "subliminal_manipulation"
    """5(1)(a). Subliminal, purposefully manipulative or deceptive techniques that materially
    distort behaviour by impairing informed decision-making, causing significant harm."""

    EXPLOITING_VULNERABILITIES = "exploiting_vulnerabilities"
    """5(1)(b). Exploits vulnerabilities due to age, disability, or a specific social or economic
    situation, materially distorting behaviour so as to cause significant harm."""

    NON_CONSENSUAL_INTIMATE_IMAGERY = "non_consensual_intimate_imagery"
    """5(1)(ba). Generating or manipulating REALISTIC images, video or audio of an identifiable
    person's intimate parts, or of them engaged in sexually explicit activity, without that person's
    freely given, specific, informed, unambiguous and explicit consent.

    Inserted by Regulation (EU) 2026/1744 and NOT IN FORCE until 2 December 2026 — see
    `applies_from`. Narrowed twice over by Art. 5(1a): a provider is caught only where such
    generation is the system's INTENDED PURPOSE, or where it is a reasonably foreseeable and
    reproducible outcome that the system has no reasonable safeguards against; a deployer only where
    it USES the system for that purpose. And Art. 5(1b) excludes manipulation that does not increase
    the exposure of intimate parts or alter the nature of the activity depicted. A general-purpose
    image generator is therefore not caught by capability alone, which is the whole difficulty of
    this point."""

    CHILD_SEXUAL_ABUSE_MATERIAL = "child_sexual_abuse_material"
    """5(1)(bb). Generating or manipulating material or a performance within the meaning of
    Art. 2, points (c) and (e), of Directive 2011/93/EU, except where a 'without right' defence
    applies under national law.

    Inserted by Regulation (EU) 2026/1744, in force from 2 December 2026, and narrowed by the same
    Art. 5(1a) test as (ba). The 'without right' carve-out is a question of national criminal law,
    not of the system, so nothing here can resolve it."""

    SOCIAL_SCORING = "social_scoring"
    """5(1)(c). Evaluating or classifying persons over time on social behaviour or personal
    characteristics, where the social score leads to detrimental treatment that is either
    out-of-context (i) or disproportionate to the behaviour (ii)."""

    CRIMINAL_OFFENCE_PREDICTION = "criminal_offence_prediction"
    """5(1)(d). Predicting the risk of a person committing a criminal offence based SOLELY on
    profiling or personality traits. Expressly does not cover systems supporting a human assessment
    already based on objective and verifiable facts linked to criminal activity."""

    FACIAL_IMAGE_SCRAPING = "facial_image_scraping"
    """5(1)(e). Creating or expanding facial recognition databases by untargeted scraping of facial
    images from the internet or CCTV footage."""

    EMOTION_INFERENCE_WORKPLACE_EDUCATION = "emotion_inference_workplace_education"
    """5(1)(f). Inferring emotions of a natural person in the workplace or in education
    institutions, except for medical or safety reasons. Whether "workplace" reaches recruitment is
    not settled by the text — see the Commission guidance in data/policy/guidance/."""

    BIOMETRIC_CATEGORISATION_SENSITIVE = "biometric_categorisation_sensitive"
    """5(1)(g). Biometric categorisation deducing race, political opinions, trade union membership,
    religious or philosophical beliefs, sex life or sexual orientation. Does not cover labelling or
    filtering of lawfully acquired biometric datasets."""

    REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION = "realtime_remote_biometric_identification"
    """5(1)(h). 'Real-time' remote biometric identification in publicly accessible spaces for law
    enforcement, unless strictly necessary for one of three named objectives — targeted search for
    victims or missing persons, an imminent threat to life or of terrorist attack, or locating a
    suspect for an Annex II offence. Where an objective applies, Arts. 5(2)-(3) still require a
    fundamental rights impact assessment, registration, and prior judicial authorisation."""

    @property
    def point(self) -> str:
        """The Art. 5(1) point, for citation — same discipline as `ScopeExclusion.paragraph`."""
        return _PROHIBITED_POINT[self]

    @property
    def applies_from(self) -> date:
        """WHEN this prohibition began, or begins, to apply.

        Not decoration, and not the same for every point. Art. 5 applied from 2 February 2025 under
        Art. 113(a), and until Regulation (EU) 2026/1744 that was true of the whole Article — so the
        date could be left implicit. It inserted points (ba) and (bb) and gave them their own date,
        2 December 2026, which is in the FUTURE at the time of writing.

        A prohibited verdict is the one verdict that tells an organisation to stop rather than to
        document, so 'this practice is banned' and 'this practice will be banned in three months'
        are different things to be told, and a report that cannot tell them apart would be wrong in
        whichever direction it guessed. This is the same gap as M4d-5, in miniature and answerable.
        """
        return _PROHIBITED_APPLIES_FROM[self]


# No default, and every member listed, for the reason given at _SCOPE_EXCLUSION_PARAGRAPH: a member
# added without its point would be cited under a letter belonging to another prohibition.
_PROHIBITED_POINT: dict[ProhibitedPractice, str] = {
    ProhibitedPractice.SUBLIMINAL_MANIPULATION: "a",
    ProhibitedPractice.EXPLOITING_VULNERABILITIES: "b",
    ProhibitedPractice.NON_CONSENSUAL_INTIMATE_IMAGERY: "ba",
    ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL: "bb",
    ProhibitedPractice.SOCIAL_SCORING: "c",
    ProhibitedPractice.CRIMINAL_OFFENCE_PREDICTION: "d",
    ProhibitedPractice.FACIAL_IMAGE_SCRAPING: "e",
    ProhibitedPractice.EMOTION_INFERENCE_WORKPLACE_EDUCATION: "f",
    ProhibitedPractice.BIOMETRIC_CATEGORISATION_SENSITIVE: "g",
    ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION: "h",
}

# Art. 113(a) as amended. Every member listed, no default, for the reason given above: a member
# added without a date would silently inherit someone else's, and here that means reporting a
# practice as banned today when the Article gives it another three months.
_ART_5_GENERAL = date(2025, 2, 2)
_ART_5_OMNIBUS_INSERTIONS = date(2026, 12, 2)
_PROHIBITED_APPLIES_FROM: dict[ProhibitedPractice, date] = {
    ProhibitedPractice.SUBLIMINAL_MANIPULATION: _ART_5_GENERAL,
    ProhibitedPractice.EXPLOITING_VULNERABILITIES: _ART_5_GENERAL,
    ProhibitedPractice.NON_CONSENSUAL_INTIMATE_IMAGERY: _ART_5_OMNIBUS_INSERTIONS,
    ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL: _ART_5_OMNIBUS_INSERTIONS,
    ProhibitedPractice.SOCIAL_SCORING: _ART_5_GENERAL,
    ProhibitedPractice.CRIMINAL_OFFENCE_PREDICTION: _ART_5_GENERAL,
    ProhibitedPractice.FACIAL_IMAGE_SCRAPING: _ART_5_GENERAL,
    ProhibitedPractice.EMOTION_INFERENCE_WORKPLACE_EDUCATION: _ART_5_GENERAL,
    ProhibitedPractice.BIOMETRIC_CATEGORISATION_SENSITIVE: _ART_5_GENERAL,
    ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION: _ART_5_GENERAL,
}


class ActorRole(StrEnum):
    """Art. 2(1), Art. 3. Obligations attach to the ROLE, not to the organisation.
    One organisation may hold several roles and must be assessed separately for each."""

    PROVIDER = "provider"
    """Art. 3(3). Develops the system, or has it developed, and places it on the market /
    puts it into service under its own name or trademark. Bears the heaviest obligations."""

    INITIAL_PROVIDER = "initial_provider"
    """Art. 25(2). The party that placed the system on the market BEFORE Art. 25 moved the provider
    role to someone else — and which, on that paragraph's own words, "shall no longer be considered
    to be a provider of that specific AI system".

    A role of its own because the duty runs the wrong way to sit anywhere else. Art. 25(2) leaves
    this party owing a cooperation duty — supply the information, technical access and assistance
    the new provider needs, in particular for the conformity assessment — and attaching that to
    PROVIDER would put it on the organisation that has just taken the role ON, which is the exact
    reverse of who owes it. `Finding.role` exists to stop that kind of mis-attribution; naming the
    role is how it is stopped here.

    It holds exactly one rule, and holds it only where a reallocation actually occurred. A high-risk
    system whose provider never changed has no initial provider distinct from its provider, so the
    role is selected for and comes back empty."""

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


class TransparencyDuty(StrEnum):
    """Art. 50. WHICH transparency duty attaches, and therefore ON WHOM.

    A LIST, not a flag, and this is the point of the type: Art. 50 holds five separate duties and
    one system can owe several at once — a chatbot that drafts published copy owes 50(1) and 50(2)
    to its provider and 50(4) to its deployer. A single boolean says "Art. 50 applies" and leaves
    the reader to work out which duty, whose it is, and what to write.

    THE ROLE IS THE HALF A BOOLEAN LOSES. Paragraphs (1) and (2) bind the PROVIDER — build the
    system so it announces itself, mark its output machine-readably. Paragraphs (3) and (4) bind the
    DEPLOYER — tell the people exposed, disclose the deep fake. They are different duties, owed by
    different parties, discharged in different documents. A provider handed "Art. 50 applies" for a
    duty that is in fact their deployer's cannot act on it, and a report that never says so leaves
    the deployer's duty unnamed.

    Every paragraph is disapplied for law-enforcement use authorised by law, and (1), (2) and (4)
    carry further carve-outs of their own — see the members."""

    DIRECT_INTERACTION = "direct_interaction"
    """50(1), PROVIDER. Systems intended to interact directly with natural persons must be built so
    those persons are informed they are dealing with an AI system — unless that is obvious to a
    reasonably well-informed, observant and circumspect person."""

    SYNTHETIC_CONTENT_MARKING = "synthetic_content_marking"
    """50(2), PROVIDER. Systems generating synthetic audio, image, video or text must mark their
    outputs in a machine-readable format, detectable as artificially generated or manipulated. Does
    NOT apply where the system performs an assistive function for standard editing, or does not
    substantially alter the deployer's input data or its semantics."""

    EMOTION_OR_BIOMETRIC_CATEGORISATION = "emotion_or_biometric_categorisation"
    """50(3), DEPLOYER. Deployers of an emotion recognition or biometric categorisation system must
    inform the persons exposed to it. Attaches to the SYSTEM TYPE, so it can stand beside an Art. 5
    prohibition: Art. 5(1)(f) itself excepts medical and safety uses, under which such a system is
    lawfully deployed and this duty squarely bites."""

    DEEP_FAKE_DISCLOSURE = "deep_fake_disclosure"
    """50(4), first subparagraph, DEPLOYER. Deployers of a system generating or manipulating image,
    audio or video constituting a deep fake must disclose that it is artificially generated. For an
    evidently artistic, creative, satirical or fictional work the duty is reduced to disclosing the
    existence of such content in a way that does not hamper its enjoyment."""

    PUBLIC_INTEREST_TEXT_DISCLOSURE = "public_interest_text_disclosure"
    """50(4), second subparagraph, DEPLOYER. Deployers publishing AI-generated text to inform the
    public on matters of public interest must disclose it. Does NOT apply where the content has
    undergone human review or editorial control and a person holds editorial responsibility."""

    @property
    def paragraph(self) -> int:
        """The Art. 50 paragraph, for citation."""
        return _TRANSPARENCY_PARAGRAPH[self]

    @property
    def owed_by(self) -> ActorRole:
        """WHO owes this duty. Art. 50 splits by role, and the split is not cosmetic: a provider
        cannot discharge a deployer's duty and vice versa."""
        return _TRANSPARENCY_ROLE[self]


# No default, and every member listed, for the reason given at _SCOPE_EXCLUSION_PARAGRAPH.
_TRANSPARENCY_PARAGRAPH: dict[TransparencyDuty, int] = {
    TransparencyDuty.DIRECT_INTERACTION: 1,
    TransparencyDuty.SYNTHETIC_CONTENT_MARKING: 2,
    TransparencyDuty.EMOTION_OR_BIOMETRIC_CATEGORISATION: 3,
    TransparencyDuty.DEEP_FAKE_DISCLOSURE: 4,
    TransparencyDuty.PUBLIC_INTEREST_TEXT_DISCLOSURE: 4,
}

_TRANSPARENCY_ROLE: dict[TransparencyDuty, ActorRole] = {
    TransparencyDuty.DIRECT_INTERACTION: ActorRole.PROVIDER,
    TransparencyDuty.SYNTHETIC_CONTENT_MARKING: ActorRole.PROVIDER,
    TransparencyDuty.EMOTION_OR_BIOMETRIC_CATEGORISATION: ActorRole.DEPLOYER,
    TransparencyDuty.DEEP_FAKE_DISCLOSURE: ActorRole.DEPLOYER,
    TransparencyDuty.PUBLIC_INTEREST_TEXT_DISCLOSURE: ActorRole.DEPLOYER,
}


class ProviderReallocation(StrEnum):
    """Art. 25. WHICH circumstance has made the reader the PROVIDER of a system someone else built.

    A question about ROLE, not about risk — and the only one in the cascade that is. Everything else
    the cascade decides is what the system IS; this decides whose obligations the report's provider
    section holds. Getting it wrong is quiet in a way a tier error is not: a company that
    white-labels a vendor's high-risk tool reads a report listing the provider's nineteen duties
    beside the deployer's three, assumes the short column is theirs, and is wrong about all
    twenty-two.

    ONLY REACHED AT HIGH RISK. Every limb of Art. 25(1) speaks of "a high-risk AI system", and
    25(3) of "high-risk AI systems that are safety components". A system that is not high-risk
    cannot have a provider reallocated by this Article, so the question is not put.

    ONE VALUE, not a list, unlike TransparencyDuty. Art. 50 holds five duties that are discharged
    differently and by different parties, so which ones attach carries information. Here every limb
    has the SAME consequence — you are the provider and owe Art. 16 whole — so naming the clearest
    trigger cites the finding without changing it. Two limbs applying at once is under-citation, not
    a wrong answer.

    Art. 25(2) is the other half and is not a member here: where any of these applies, the INITIAL
    provider stops being the provider of that system, and must hand over what the new one needs.
    That is a statement about the other party, so it belongs in the verdict's prose rather than in
    a value describing the reader."""

    NAME_OR_TRADEMARK = "name_or_trademark"
    """25(1)(a). Puts its own name or trademark on a high-risk system already placed on the market
    or put into service — white-labelling. Expressly "without prejudice to contractual arrangements
    stipulating that the obligations are otherwise allocated", so a contract can move the duties
    between the parties but cannot decide this classification."""

    SUBSTANTIAL_MODIFICATION = "substantial_modification"
    """25(1)(b). Makes a substantial modification to a high-risk system already on the market, such
    that it REMAINS high-risk under Art. 6. 'Substantial modification' is defined at Art. 3(23): a
    change not foreseen in the provider's initial conformity assessment, which affects compliance
    with Chapter III Section 2 or modifies the assessed intended purpose. Ordinary configuration,
    tuning within the documented envelope, and updates the provider planned for are not it."""

    INTENDED_PURPOSE_CHANGE = "intended_purpose_change"
    """25(1)(c). Changes the intended purpose of a system — INCLUDING a general-purpose AI system —
    that was not classified as high-risk, so that it becomes high-risk under Art. 6. The limb that
    catches an ordinary tool put to a listed use: a summariser aimed at job applications is a
    recruitment system, and whoever aimed it there is its provider."""

    PRODUCT_MANUFACTURER = "product_manufacturer"
    """25(3). The system is a safety component of a product covered by Annex I Section A, and is
    placed on the market with that product under the manufacturer's name or trademark (25(3)(a)) or
    put into service under it afterwards (25(3)(b)). The manufacturer is then the provider.

    This is why ActorRole.PRODUCT_MANUFACTURER carries no ruleset of its own: Art. 25(3) gives it
    the provider's, whole."""

    @property
    def paragraph(self) -> int:
        """The Art. 25 paragraph, for citation."""
        return _REALLOCATION_CITE[self][0]

    @property
    def point(self) -> str | None:
        """The point within that paragraph, where the limb names one. `None` for 25(3), which
        reallocates on either of its own points and does not need to choose between them."""
        return _REALLOCATION_CITE[self][1]

    @property
    def citation(self) -> str:
        """The provision, written out — "Art. 25(1)(a)", "Art. 25(3)"."""
        point = self.point
        return f"Art. 25({self.paragraph})" + (f"({point})" if point else "")


# No default, and every member listed, for the reason given at _SCOPE_EXCLUSION_PARAGRAPH.
_REALLOCATION_CITE: dict[ProviderReallocation, tuple[int, str | None]] = {
    ProviderReallocation.NAME_OR_TRADEMARK: (1, "a"),
    ProviderReallocation.SUBSTANTIAL_MODIFICATION: (1, "b"),
    ProviderReallocation.INTENDED_PURPOSE_CHANGE: (1, "c"),
    ProviderReallocation.PRODUCT_MANUFACTURER: (3, None),
}


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


class DeployerType(StrEnum):
    """WHAT KIND of organisation deploys the system — a fact about the deployer, not the system.

    The Act narrows several deployer duties by this, and Art. 27 is the one modelled today: the
    fundamental rights impact assessment binds deployers that are bodies governed by public law or
    private entities providing public services, not deployers at large. Art. 49(3) narrows deployer
    registration the same way, to public authorities and Union bodies.

    NOT_STATED IS ITS OWN VALUE, and the ordinary one. Most documentation describes a system, not
    its customers, and a description that never mentions the deploying organisation is not a
    description of a private commercial one. Folding silence into `NEITHER` would resolve the
    condition against a duty on evidence nobody supplied — the same failure `TerritorialLink`
    avoids with `not_addressed`.

    It never withholds an obligation. A rule narrowed this way is still selected and still listed
    under its role; this answer only tells a reader which side of the condition the document falls
    on, and says so plainly where the document does not fall on either."""

    PUBLIC_BODY = "public_body"
    """A body governed by public law — a public authority or agency, or an entity established to
    meet needs in the general interest and controlled or financed by the state. Art. 27(1), first
    limb."""

    PUBLIC_SERVICE_PROVIDER = "public_service_provider"
    """A private entity providing public services — education, healthcare, social services, housing,
    justice administration. Private in form, public in function, and Art. 27(1) reaches it for that
    reason."""

    NEITHER = "neither"
    """A private organisation not providing public services, established by the description rather
    than assumed from its silence. The Art. 27(1) organisation limb does not reach it — though the
    Annex III(5)(b)/(c) limb still can, whoever the deployer is."""

    NOT_STATED = "not_stated"
    """THE ORDINARY ANSWER. The description does not say what kind of organisation deploys the
    system. The condition stands unresolved, and the report says so rather than choosing a side."""

    @property
    def caught_by_article_27(self) -> bool | None:
        """Whether Art. 27(1)'s ORGANISATION limb reaches this deployer — `None` where the
        description does not settle it.

        Tri-state deliberately: `False` is a finding that the limb does not reach them, `None` is
        the absence of one, and a report that could not tell those apart would present a silence as
        a clearance. Answers only the first limb; a system within Annex III(5)(b) or (c) is caught
        whatever this returns."""
        if self is DeployerType.NOT_STATED:
            return None
        return self is not DeployerType.NEITHER

    @property
    def caught_by_article_49_3(self) -> bool | None:
        """Whether Art. 49(3)'s deployer registration reaches this deployer — `None` where the
        description does not settle it.

        NARROWER THAN ART. 27, on the same fact, and that is why it is a property of its own rather
        than a second use of `caught_by_article_27`. Art. 27 reaches bodies governed by public law
        AND private entities providing public services; Art. 49(3) reaches "public authorities,
        Union institutions, bodies, offices or agencies or persons acting on their behalf". A
        private entity providing public services is private — a hospital company running a state
        contract is not a public authority — so it answers True to one Article and False to the
        other. Collapsing the two would give a public-service provider a registration duty the
        Article does not put on it.

        The `False` is narrower than it looks, and the caller has to say so: "persons acting on
        their behalf" can reach a private organisation operating a system FOR a public authority,
        which is a relationship no description of the organisation's own type establishes."""
        if self is DeployerType.NOT_STATED:
            return None
        return self is DeployerType.PUBLIC_BODY


class HighRiskRoute(StrEnum):
    """WHICH of Art. 6's two doors made a use case high-risk.

    Not a tier and not a property of a rule's subject matter — a condition on when a rule fires.
    Most obligations do not care which door was used: Arts. 9-15 and 17-21 bind every high-risk
    system alike. A few care completely, and Art. 43 is the clearest: conformity assessment is
    43(1) or 43(2) for an Annex III system depending on the area, and 43(3) — the sectoral act's
    own procedure, not this Regulation's — for an Annex I one. One rule cannot hold all three, and
    a rule that names no route would cite the wrong law to two systems out of three."""

    ANNEX_I = "annex_i"
    """Art. 6(1). A safety component of, or itself, a product covered by an Annex I instrument."""

    ANNEX_III = "annex_iii"
    """Art. 6(2). Used in one of the areas Annex III lists."""


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

    @property
    def letter(self) -> str:
        """The Art. 6(3) point, for citation — same discipline as `ScopeExclusion.paragraph`."""
        return _DEROGATION_LETTER[self]


# No default, and every member listed, for the reason given at _SCOPE_EXCLUSION_PARAGRAPH: Art. 6(6)
# and 6(7) empower the Commission to add and delete these conditions, so a new member is expected
# and must raise rather than be cited under a letter that belongs to another condition.
_DEROGATION_LETTER: dict[DerogationCondition, str] = {
    DerogationCondition.NARROW_PROCEDURAL_TASK: "a",
    DerogationCondition.IMPROVES_COMPLETED_HUMAN_ACTIVITY: "b",
    DerogationCondition.DETECTS_DECISION_PATTERNS: "c",
    DerogationCondition.PREPARATORY_TASK: "d",
}
