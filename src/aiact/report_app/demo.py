"""Demo mode: the review with every model seam replaced by a deterministic stand-in.

The report app calls a model in exactly three places — the classification brain, the obligation
judge and the summariser. Everything else is code: the cascade and its legal routing, rule
selection, the report's assembly, and how the page resolves what it names. Demo mode swaps those
three seams for the stand-ins below and runs the rest UNCHANGED, so a reader with no model key
(or no wish to spend one) sees the real report, shaped by the real pipeline, on their own document
— in well under a second.

The stand-ins read the document with keyword heuristics. That is the very thing this project is
built to show a model must do instead (see README: "word-matching cannot make it at all"), and
nothing here pretends otherwise:

  - every reasoning string starts with `DEMO_PREFIX`, so a demo verdict can never be mistaken for
    a model's once it leaves this module;
  - every answer is given at "medium" confidence — it is a heuristic, not a judgement, but it is
    not an abstention either, so the cascade reaches a verdict instead of `needs_review`;
  - every evidence quote is a verbatim sentence from the document, never invented;
  - a question with no heuristic abstains, as a model that could not answer would.

A DEMO REPORT IS ILLUSTRATIVE. Its risk class and findings show what the report looks like and
how it reads; they are not an assessment of the document. The page says so wherever one is shown.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from aiact.gap.judge import Judgement
from aiact.schemas.enums import (
    AnnexIIIArea,
    AnnexIProduct,
    CheckType,
    DeployerType,
    DerogationCondition,
    GpaiStatus,
    OpenSourceRelease,
    ProhibitedPractice,
    ProviderReallocation,
    RealWorldTesting,
    ScopeExclusion,
    SystemicRisk,
    TerritorialLink,
    TransparencyDuty,
    Verdict,
)
from aiact.schemas.policy import PolicyRule, RuleCriterion
from aiact.schemas.question import EVIDENCE_QUOTE_MAX, Answer, Question, clip_reasoning
from aiact.schemas.report import CriterionFinding
from aiact.summary import NAME_MAX, SUMMARY_MAX, SystemSummary

DEMO_PREFIX = "Demo: "
"""Every reasoning string the stand-ins write starts with this."""

DEMO_NOTE = (
    "This is a DEMO report. No model read the document: the classification answers, the verdicts "
    "and the summary come from keyword heuristics, so they show what a report looks like and how "
    "it reads, not whether this system is compliant. Run the review in normal mode for an "
    "assessment."
)


# ---- reading the document ---------------------------------------------------------------------

_NEGATION = re.compile(
    r"\b(?:no|not|never|none|neither|nor|without|cannot|n't|nothing|nobody)\b", re.IGNORECASE
)
_MARKUP = re.compile(r"<!--.*?-->|[*_`>#|]+", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n{2,}|\n(?=\s*[-•]\s)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
_WORD = re.compile(r"[a-z][a-z-]{2,}")
# A figure that measures something: a number, optionally decimal or a percentage. Provision
# numbers and years are excluded, since "Art. 9" and "2026" are not metrics.
_FIGURE = re.compile(
    r"(?<![\w§/(.-])(?<!Art\. )(?<!Article )(?<!Annex )(?<!point )(?<!§)"
    r"\d+(?:[.,]\d+)*\s?(?:%|percent|ms|s\b|FLOPs?)?"
)
_YEAR = re.compile(r"^(?:19|20)\d\d$")


def _clean(text: str) -> str:
    return " ".join(_MARKUP.sub(" ", text).split())


def _sentences(text: str) -> list[str]:
    """The document's sentences, cleaned of Markdown, each a quotable line."""
    out: list[str] = []
    for raw in _SENTENCE_END.split(text):
        sentence = _clean(raw)
        if len(sentence) >= 12:
            out.append(sentence)
    return out


def _quote(sentence: str | None) -> str | None:
    """A sentence cut to the quote cap, so it is always a valid `evidence_quote`."""
    if not sentence:
        return None
    if len(sentence) <= EVIDENCE_QUOTE_MAX:
        return sentence
    return sentence[: EVIDENCE_QUOTE_MAX - 1].rstrip() + "\u2026"


def _figures(text: str) -> int:
    return sum(1 for m in _FIGURE.finditer(text) if not _YEAR.match(m.group().strip()))


@dataclass
class Section:
    """A heading and everything under it, subsections included."""

    heading: str
    level: int
    body: str
    """Cleaned text of the section's own paragraphs and its subsections'."""
    paragraphs: list[str] = field(default_factory=list)
    """The section's OWN paragraphs, cleaned, without its subsections' — so a paragraph is read
    once however deep it sits."""

    @property
    def words(self) -> int:
        return len(self.body.split())


def _paragraphs(text: str) -> list[str]:
    return [p for block in re.split(r"\n\s*\n", text) if (p := _clean(block))]


class Reader:
    """One document, read once: its sentences for the brain, its sections for the judge."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.lower = text.lower()
        self.sentences = _sentences(text)
        self.sections = _split_sections(text)

    def mentions(self, pattern: str) -> list[str]:
        """Every sentence matching `pattern`, negated or not."""
        rx = re.compile(pattern, re.IGNORECASE)
        return [s for s in self.sentences if rx.search(s)]

    def affirms(self, pattern: str) -> str | None:
        """The first sentence that matches `pattern` and does not negate it ("does not score")."""
        for sentence in self.mentions(pattern):
            if not _NEGATION.search(sentence):
                return sentence
        return None

    def denies(self, pattern: str) -> str | None:
        """The first sentence that matches `pattern` and negates it."""
        for sentence in self.mentions(pattern):
            if _NEGATION.search(sentence):
                return sentence
        return None

    def count(self, pattern: str) -> int:
        return len(re.findall(pattern, self.lower))


def _split_sections(text: str) -> list[Section]:
    """The document by heading. Each section's body includes its subsections, so a parent always
    says at least what its children say; a document without headings is one section."""
    headings = list(_HEADING.finditer(text))
    if not headings:
        return [Section(heading="", level=0, body=_clean(text), paragraphs=_paragraphs(text))]
    sections: list[Section] = []
    if headings[0].start() > 0:
        lead = text[: headings[0].start()]
        sections.append(
            Section(heading="", level=0, body=_clean(lead), paragraphs=_paragraphs(lead))
        )
    for i, match in enumerate(headings):
        level = len(match.group(1))
        end = len(text)
        own_end = headings[i + 1].start() if i + 1 < len(headings) else end
        for later in headings[i + 1 :]:
            if len(later.group(1)) <= level:
                end = later.start()
                break
        sections.append(
            Section(
                heading=match.group(2),
                level=level,
                body=_clean(text[match.end() : end]),
                paragraphs=_paragraphs(text[match.end() : own_end]),
            )
        )
    return sections


# ---- the brain ----------------------------------------------------------------------------------

_PERSON = (
    r"\b(?:applicants?|candidates?|employees?|students?|pupils?|persons?|people|individuals?|"
    r"workers?|staff|users?|customers?|patients?|citizens?|claimants?|borrowers?|suspects?|"
    r"passengers?|travellers?|tenants?|them|him|her|someone|anyone)\b"
)
_EVALUATES = (
    r"\b(?:scor(?:e|es|ed|ing)|rank(?:s|ed|ing)?|rat(?:e|es|ed|ing)|evaluat\w+|assess(?:es|ed|ing)|"
    r"predict\w+|profil(?:e|es|ed|ing)|shortlist\w*|prioriti[sz]\w+|grad(?:e|es|ed|ing)|"
    r"fit score)\b"
)

_AREA_TERMS: dict[AnnexIIIArea, str] = {
    AnnexIIIArea.EMPLOYMENT: (
        r"recruit\w*|candidates?|applicants?|hiring|\bjobs?\b|employees?|employment|promotion|"
        r"vacanc\w+|\bcvs?\b|r[ée]sum[ée]s?|workers?|shortlist\w*|requisitions?|termination|"
        r"task allocation|performance (?:evaluation|monitoring|review|appraisal)|interview\w*"
    ),
    AnnexIIIArea.EDUCATION: (
        r"students?|pupils?|admissions?|exams?|examination|grading|schools?|universit\w+|"
        r"learners?|vocational|proctor\w*"
    ),
    AnnexIIIArea.BIOMETRICS: (
        r"biometric\w*|facial recognition|face (?:match\w*|recognition|images?)|fingerprints?|"
        r"voice ?prints?|emotion recognition|\biris\b|gait"
    ),
    AnnexIIIArea.ESSENTIAL_SERVICES: (
        r"credit\w*|\bloans?\b|insurance|social (?:benefits?|assistance|welfare|housing)|"
        r"emergency (?:calls?|services|dispatch)|public assistance|triage"
    ),
    AnnexIIIArea.LAW_ENFORCEMENT: (
        r"police|law enforcement|suspects?|offenders?|\bcrimes?\b|criminal|investigat\w+|polygraph"
    ),
    AnnexIIIArea.MIGRATION: r"asylum|visas?|border\w*|migration|migrants?|residence permits?",
    AnnexIIIArea.JUSTICE_DEMOCRACY: r"\bcourts?\b|judicial|judges?|elections?|voting|referend\w+",
    AnnexIIIArea.CRITICAL_INFRASTRUCTURE: (
        r"electricity|water supply|gas supply|heating|road traffic|critical (?:digital )?"
        r"infrastructure|power grid"
    ),
}
_AREA_MIN_HITS = 3

_PROHIBITED_TERMS: list[tuple[ProhibitedPractice, str]] = [
    (
        ProhibitedPractice.SUBLIMINAL_MANIPULATION,
        r"subliminal|manipulative techniques?|deceptive techniques?",
    ),
    (ProhibitedPractice.EXPLOITING_VULNERABILITIES, r"exploit\w* (?:the |their )?vulnerabilit\w+"),
    (ProhibitedPractice.NON_CONSENSUAL_INTIMATE_IMAGERY, r"intimate (?:imagery|images?)"),
    (ProhibitedPractice.CHILD_SEXUAL_ABUSE_MATERIAL, r"child sexual abuse material|\bcsam\b"),
    (ProhibitedPractice.SOCIAL_SCORING, r"social scor\w+|social credit|trustworthiness score"),
    (
        ProhibitedPractice.CRIMINAL_OFFENCE_PREDICTION,
        r"predict\w* (?:the )?(?:risk|likelihood|probability) (?:of|that) .{0,40}"
        r"(?:crime|criminal offence|offend|re-?offend)|recidivism",
    ),
    (
        ProhibitedPractice.FACIAL_IMAGE_SCRAPING,
        r"scrap\w+ .{0,40}(?:facial|face) images|untargeted scraping",
    ),
    (
        ProhibitedPractice.BIOMETRIC_CATEGORISATION_SENSITIVE,
        r"biometric categori[sz]ation .{0,80}(?:race|ethnic|political|religio|sexual|trade union)",
    ),
    (
        ProhibitedPractice.REALTIME_REMOTE_BIOMETRIC_IDENTIFICATION,
        r"real-?time remote biometric identification",
    ),
]
# Art. 5(1)(f) needs two things in one sentence: emotion read off a person, at work or in education.
_EMOTION = (
    r"(?:infer\w*|detect\w*|recogni[sz]\w*|gauge\w*|analys\w+|read\w*|measur\w*) "
    r".{0,30}(?:emotion\w*|\bmoods?\b|sentiment|enthusiasm|composure|affective state)|"
    r"emotion (?:recognition|inference|detection|analysis)|"
    r"(?:facial expressions?|tone of voice|vocal energy|body language|gaze) .{0,60}"
    r"(?:enthusiasm|confidence|engagement|composure|emotion\w*|\bmoods?\b|stress)"
)
_WORK_OR_SCHOOL = (
    r"workplace|work|employ\w*|recruit\w*|hiring|interview\w*|candidates?|applicants?|staff|"
    r"school|education|students?|pupils?|learners?|classroom"
)

_ANNEX_I_TERMS: list[tuple[AnnexIProduct, str]] = [
    (AnnexIProduct.MEDICAL_DEVICES, r"medical devices?|2017/745|\bmdr\b"),
    (AnnexIProduct.IVD_MEDICAL_DEVICES, r"in vitro diagnostic|2017/746|\bivdr\b"),
    (AnnexIProduct.MACHINERY_REGULATION, r"2023/1230"),
    (AnnexIProduct.MACHINERY, r"machinery|2006/42"),
    (AnnexIProduct.TOYS, r"\btoys?\b|2009/48"),
    (AnnexIProduct.LIFTS, r"\blifts?\b|elevators?|2014/33"),
    (AnnexIProduct.RADIO_EQUIPMENT, r"radio equipment|2014/53"),
    (AnnexIProduct.MOTOR_VEHICLES, r"motor vehicles?|2018/858|passenger cars?|driver assistance"),
    (AnnexIProduct.CIVIL_AVIATION_UAS, r"unmanned aircraft|\bdrones?\b|2018/1139"),
]
_ANNEX_I_CONTEXT = r"safety component|regulated product|product (?:law|legislation)|annex i\b"

_DEROGATION_TERMS: list[tuple[DerogationCondition, str]] = [
    (DerogationCondition.NARROW_PROCEDURAL_TASK, r"6\(3\)\(a\)|narrow procedural task"),
    (
        DerogationCondition.IMPROVES_COMPLETED_HUMAN_ACTIVITY,
        r"6\(3\)\(b\)|improv\w+ .{0,30}completed human activity",
    ),
    (
        DerogationCondition.DETECTS_DECISION_PATTERNS,
        r"6\(3\)\(c\)|decision[- ]making patterns?|deviations? from .{0,30}patterns?",
    ),
    (DerogationCondition.PREPARATORY_TASK, r"6\(3\)\(d\)|preparatory task"),
]

_TRANSPARENCY_TERMS: list[tuple[TransparencyDuty, str]] = [
    (
        TransparencyDuty.DIRECT_INTERACTION,
        r"chat ?bot|conversational|chat interface|voice assistant|virtual assistant|"
        r"interacts? directly|talks? (?:to|with) (?:users|people|applicants|customers|callers)|"
        r"answers? (?:questions|queries) from (?:users|people|customers)",
    ),
    (
        TransparencyDuty.SYNTHETIC_CONTENT_MARKING,
        r"generat\w+ .{0,20}(?:text|images?|audio|video|content|adverts?|descriptions?|"
        r"summaries|articles|code)|generative|text-to-(?:image|speech|video)|"
        r"synthetic (?:text|images?|audio|video|content)|large language model",
    ),
    (
        TransparencyDuty.EMOTION_OR_BIOMETRIC_CATEGORISATION,
        r"emotion recognition|biometric categori[sz]ation|infer\w* emotions?",
    ),
    (TransparencyDuty.DEEP_FAKE_DISCLOSURE, r"deep ?fakes?"),
    (
        TransparencyDuty.PUBLIC_INTEREST_TEXT_DISCLOSURE,
        r"publish\w* .{0,40}(?:news|articles|public interest)|journalis\w+",
    ),
]

_EU = (
    r"\b(?:EU|E\.U\.|European Union|the Union|Member States?|EEA|Europe|European)\b|"
    r"\b(?:Austria|Belgium|Bulgaria|Croatia|Cyprus|Czech|Denmark|Estonia|Finland|France|Germany|"
    r"Greece|Hungary|Ireland|Italy|Latvia|Lithuania|Luxembourg|Malta|Netherlands|Poland|Portugal|"
    r"Romania|Slovakia|Slovenia|Spain|Sweden)\b"
)


@dataclass
class Heuristic:
    """What a node's stand-in found: the value, why, and the sentence it rests on."""

    value: object
    why: str
    quote: str | None = None
    silent: bool = False
    """True where the document does not state the fact and the stand-in declines, as a model
    would, rather than guess — the cascade then ends in needs_review and names the fact."""


class DemoBrain:
    """Answers the cascade's questions from keyword heuristics. Satisfies `Brain`."""

    name: str = "demo"

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[Reader], Heuristic]] = {
            "is_ai": self._is_ai,
            "territorial": self._territorial,
            "scope": self._scope,
            "gpai_model": self._gpai_model,
            "systemic_risk": self._systemic_risk,
            "gpai_open_source_release": self._open_source,
            "prohibited": self._prohibited,
            "annex_i": self._annex_i,
            "third_party_assessment": self._third_party,
            "annex_iii": self._annex_iii,
            "profiling": self._profiling,
            "derogation": self._derogation,
            "significant_risk": self._significant_risk,
            "transparency": self._transparency,
            "provider_reallocation": self._reallocation,
            "deployer_type": self._deployer_type,
            "real_world_testing": self._real_world_testing,
        }
        self._last: tuple[str, Reader] | None = None

    def _reader(self, description: str) -> Reader:
        # One document is asked up to seventeen questions; read it once.
        if self._last is None or self._last[0] != description:
            self._last = (description, Reader(description))
        return self._last[1]

    def decide(self, question: Question, description: str) -> Answer:
        handler = self._handlers.get(question.node_id)
        if handler is None:
            return Answer(
                value=None,
                reasoning=clip_reasoning(
                    f"{DEMO_PREFIX}no heuristic answers the question {question.node_id!r}; a "
                    "model would read the document here."
                ),
                confidence="low",
                source=question.source,
                node_id=question.node_id,
                abstained_because="reply_unusable",
            )
        found = handler(self._reader(description))
        if found.silent:
            return Answer(
                value=None,
                reasoning=clip_reasoning(DEMO_PREFIX + found.why),
                confidence="low",
                source=question.source,
                node_id=question.node_id,
                abstained_because="description_silent",
            )
        return Answer(
            value=found.value,
            reasoning=clip_reasoning(DEMO_PREFIX + found.why),
            evidence_quote=_quote(found.quote),
            confidence="medium",
            source=question.source,
            node_id=question.node_id,
        )

    # Each handler reads the document for ONE fact and says, in its reasoning, which words it went
    # by — so a reader can see exactly how shallow the reading was.

    def _is_ai(self, doc: Reader) -> Heuristic:
        learned = doc.affirms(
            r"\b(?:trained|training data|machine[- ]learning|neural|gradient|classifier|"
            r"deep learning|statistical model|language model|\bml\b|\bllm\b|learn(?:s|ed|ing))\b"
        )
        if learned:
            return Heuristic(True, "the document describes a trained or learned model.", learned)
        rules_only = doc.mentions(
            r"rules? engine|rule-based|no model is involved|hand-written rules"
        )
        if rules_only:
            return Heuristic(
                False, "the document says the outputs follow rules a person wrote.", rules_only[0]
            )
        return Heuristic(
            True, "nothing says the outputs are rule-written, so inference is assumed."
        )

    def _territorial(self, doc: Reader) -> Heuristic:
        outside = doc.denies(
            r"(?:sold|placed|deployed|used|offered|available|operated) .{0,30}(?:EU|Union|Europe)"
        )
        if outside and not doc.affirms(_EU):
            return Heuristic(
                TerritorialLink.OUTSIDE_UNION,
                "the document says the system is not placed, used or deployed in the Union.",
                outside,
            )
        reached = doc.affirms(_EU)
        if reached:
            return Heuristic(
                TerritorialLink.EU_PLACING_OR_SERVICE,
                "the document names the Union or a Member State as where the system is placed "
                "or used.",
                reached,
            )
        return Heuristic(
            TerritorialLink.NOT_ADDRESSED,
            "nothing in the document says where the system is placed or used, so the Act is "
            "presumed to apply.",
        )

    def _scope(self, doc: Reader) -> Heuristic:
        checks: list[tuple[ScopeExclusion, str]] = [
            (
                ScopeExclusion.MILITARY_DEFENCE_NATIONAL_SECURITY,
                r"(?:exclusively|solely|only) for (?:military|defence|national security)",
            ),
            (
                ScopeExclusion.SCIENTIFIC_RESEARCH,
                r"(?:sole|only) purpose of scientific research",
            ),
            (
                ScopeExclusion.PERSONAL_NON_PROFESSIONAL,
                r"purely personal,? non-professional",
            ),
        ]
        for exclusion, pattern in checks:
            hit = doc.affirms(pattern)
            if hit:
                return Heuristic(
                    exclusion,
                    f"the document claims the Art. 2({exclusion.paragraph}) exclusion in terms.",
                    hit,
                )
        return Heuristic(None, "no Art. 2 exclusion is claimed in the document.")

    def _gpai_model(self, doc: Reader) -> Heuristic:
        for sentence in doc.mentions(r"general[- ]purpose (?:ai )?model|foundation model"):
            if re.search(r"built on|based on|powered by|uses|integrat|fine-?tun", sentence, re.I):
                continue  # a SYSTEM built on a model is an AI system, Art. 3(66)
            if _NEGATION.search(sentence):
                continue
            return Heuristic(
                GpaiStatus.GENERAL_PURPOSE_MODEL,
                "the document describes a general-purpose AI model itself, not a system built "
                "on one.",
                sentence,
            )
        return Heuristic(
            GpaiStatus.AI_SYSTEM,
            "the document describes an AI system, not a general-purpose model.",
        )

    def _systemic_risk(self, doc: Reader) -> Heuristic:
        designated = doc.affirms(
            r"designated .{0,40}systemic risk|notified the (?:ai office|commission)"
        )
        if designated:
            return Heuristic(
                SystemicRisk.DESIGNATED,
                "the document reports a designation or notification.",
                designated,
            )
        above = doc.affirms(r"10\^25|1e25|10²⁵|above the (?:compute )?threshold")
        if above:
            return Heuristic(
                SystemicRisk.HIGH_IMPACT_CAPABILITIES,
                "the document gives a compute figure at or above 10^25 FLOPs.",
                above,
            )
        below = doc.affirms(r"\bflops?\b|training compute")
        if below:
            return Heuristic(
                SystemicRisk.BELOW_THRESHOLD,
                "the document gives a compute figure without reaching the 10^25 presumption.",
                below,
            )
        return Heuristic(
            SystemicRisk.NOT_STATED,
            "the document gives no training-compute figure and reports no designation.",
        )

    def _open_source(self, doc: Reader) -> Heuristic:
        open_release = doc.affirms(
            r"weights .{0,60}publicly available|open[- ]source licen[cs]e|apache[- ]2|"
            r"\bmit licen[cs]e"
        )
        if open_release:
            return Heuristic(
                OpenSourceRelease.FULLY_OPEN,
                "the document describes a free and open-source release with public weights.",
                open_release,
            )
        closed = doc.affirms(
            r"proprietary|commercial licen[cs]e|closed[- ]weights?|not (?:publicly )?released"
        )
        if closed:
            return Heuristic(
                OpenSourceRelease.NOT_OPEN,
                "the document describes a proprietary or closed release.",
                closed,
            )
        return Heuristic(
            OpenSourceRelease.NOT_STATED,
            "the document does not state the licence or whether the weights are public.",
        )

    def _prohibited(self, doc: Reader) -> Heuristic:
        for practice, pattern in _PROHIBITED_TERMS:
            hit = doc.affirms(pattern)
            if hit:
                return Heuristic(
                    practice,
                    f"a sentence describes the Art. 5(1)({practice.point}) practice in terms.",
                    hit,
                )
        for sentence in doc.mentions(_EMOTION):
            if _NEGATION.search(sentence):
                continue
            if re.search(_WORK_OR_SCHOOL, sentence, re.I) or doc.affirms(_WORK_OR_SCHOOL):
                return Heuristic(
                    ProhibitedPractice.EMOTION_INFERENCE_WORKPLACE_EDUCATION,
                    "a sentence describes reading emotions or affect off people, in a workplace or "
                    "education setting (Art. 5(1)(f)).",
                    sentence,
                )
        return Heuristic(None, "no sentence describes an Art. 5 practice without negating it.")

    def _annex_i(self, doc: Reader) -> Heuristic:
        for product, pattern in _ANNEX_I_TERMS:
            hit = doc.affirms(pattern)
            if hit and (re.search(_ANNEX_I_CONTEXT, hit, re.I) or doc.affirms(_ANNEX_I_CONTEXT)):
                return Heuristic(
                    product,
                    "the document places the system in a product covered by Annex I legislation.",
                    hit,
                )
        return Heuristic(None, "no Annex I product legislation is named as covering the system.")

    def _third_party(self, doc: Reader) -> Heuristic:
        hit = doc.affirms(r"notified body")
        if hit:
            return Heuristic(
                True,
                "the document names a notified body for the product's conformity assessment.",
                hit,
            )
        own = doc.affirms(
            r"self-assess\w*|self-certif\w*|internal production control|"
            r"conformity assessment (?:is |was )?(?:carried out|performed|done) "
            r"(?:by the manufacturer|in-house|internally)"
        )
        if own:
            return Heuristic(
                False, "the document says the manufacturer assesses conformity itself.", own
            )
        # The guide's own rule: who assesses the product's conformity is a fact the card must
        # state, and the tool does not work it out from the type of product.
        return Heuristic(
            None,
            "the document does not say whether a notified body or the manufacturer assesses the "
            "product's conformity, and Art. 6(1)(b) turns on that.",
            silent=True,
        )

    def _annex_iii(self, doc: Reader) -> Heuristic:
        counts = {area: doc.count(pattern) for area, pattern in _AREA_TERMS.items()}
        area, hits = max(counts.items(), key=lambda item: item[1])
        if hits < _AREA_MIN_HITS:
            return Heuristic(
                None, "too few words of any Annex III area appear to place the system in one."
            )
        quote = doc.affirms(_AREA_TERMS[area])
        return Heuristic(
            area,
            f"words of the {area.value.replace('_', ' ')} area appear {hits} times, more than "
            "any other area's.",
            quote,
        )

    def _profiling(self, doc: Reader) -> Heuristic:
        for sentence in doc.mentions(_EVALUATES):
            if re.search(_PERSON, sentence, re.I) and not _NEGATION.search(sentence):
                return Heuristic(
                    True,
                    "a sentence says the system scores, ranks, rates or evaluates people.",
                    sentence,
                )
        denied = doc.denies(_EVALUATES)
        if denied:
            return Heuristic(
                False,
                "the document says the system does not score, rank or evaluate people.",
                denied,
            )
        return Heuristic(
            False, "no sentence says the system scores, ranks, rates or evaluates people."
        )

    def _derogation(self, doc: Reader) -> Heuristic:
        for condition, pattern in _DEROGATION_TERMS:
            hit = doc.affirms(pattern)
            if hit:
                return Heuristic(
                    condition,
                    f"the document claims the Art. 6(3)({condition.letter}) condition in terms.",
                    hit,
                )
        denied = doc.denies(r"exemption|derogation")
        if denied:
            return Heuristic(None, "the document says no Art. 6(3) exemption is claimed.", denied)
        return Heuristic(
            DerogationCondition.NARROW_PROCEDURAL_TASK,
            "no sentence says the system evaluates people and no Art. 6(3) condition is claimed; "
            "the demo treats it as a narrow procedural task. A model would ask for the claim.",
        )

    def _significant_risk(self, doc: Reader) -> Heuristic:
        denied = doc.denies(r"significant risk")
        if denied:
            return Heuristic(
                False, "the document says the system poses no significant risk of harm.", denied
            )
        relied = doc.affirms(
            r"significant risk|materially influenc\w+|rel(?:y|ies) on the (?:output|score)|"
            r"filters? (?:out )?(?:applicants|people|candidates)"
        )
        if relied:
            return Heuristic(
                True,
                "a sentence says people rely on the output or that it carries a significant risk.",
                relied,
            )
        return Heuristic(
            False, "nothing says the output is relied on or carries a significant risk."
        )

    def _transparency(self, doc: Reader) -> Heuristic:
        duties: list[TransparencyDuty] = []
        quotes: list[str] = []
        for duty, pattern in _TRANSPARENCY_TERMS:
            hit = doc.affirms(pattern)
            if hit and duty not in duties:
                duties.append(duty)
                quotes.append(hit)
        if not duties:
            return Heuristic(
                [], "no sentence says the system talks to people or generates content."
            )
        duties.sort(key=lambda d: (d.paragraph, d.value))
        named = ", ".join(f"Art. 50({d.paragraph})" for d in duties)
        return Heuristic(duties, f"sentences describe what {named} reach.", quotes[0])

    def _reallocation(self, doc: Reader) -> Heuristic:
        checks: list[tuple[ProviderReallocation, str]] = [
            (
                ProviderReallocation.NAME_OR_TRADEMARK,
                r"white[- ]label\w*|rebadg\w*|rebrand\w*|"
                r"resell\w* .{0,30}under (?:its|their|our) own (?:name|brand|trade ?mark)",
            ),
            (ProviderReallocation.SUBSTANTIAL_MODIFICATION, r"substantial(?:ly)? modif\w+"),
            (
                ProviderReallocation.INTENDED_PURPOSE_CHANGE,
                r"chang\w+ the intended purpose|repurpos\w+",
            ),
            (
                ProviderReallocation.PRODUCT_MANUFACTURER,
                r"safety component of a product (?:we|they|it) manufactur\w+",
            ),
        ]
        for limb, pattern in checks:
            hit = doc.affirms(pattern)
            if hit:
                return Heuristic(
                    limb, f"a sentence describes the Art. 25({limb.paragraph}) circumstance.", hit
                )
        return Heuristic(None, "nothing shows the provider role changing hands under Art. 25.")

    def _deployer_type(self, doc: Reader) -> Heuristic:
        public = doc.affirms(
            r"public (?:body|bodies|authorit\w+|sector|hospital|administration)|municipalit\w+|"
            r"ministr\w+|government|state school|\bcourts?\b|police"
        )
        if public:
            return Heuristic(
                DeployerType.PUBLIC_BODY,
                "the document names a public body as operating the system.",
                public,
            )
        service = doc.affirms(
            r"public service|healthcare provider|social services|housing association"
        )
        if service:
            return Heuristic(
                DeployerType.PUBLIC_SERVICE_PROVIDER,
                "the document names a private provider of public services as operating the system.",
                service,
            )
        private = doc.affirms(
            r"private[- ]sector|commercial (?:customers|employers|clients)|recruiters|"
            r"staffing agenc\w+|client organi[sz]ations|our customers"
        )
        if private:
            return Heuristic(
                DeployerType.NEITHER,
                "the document says the system is sold to or operated by ordinary commercial "
                "customers.",
                private,
            )
        return Heuristic(
            DeployerType.NOT_STATED,
            "the document does not say what kind of organisation operates the system.",
        )

    def _real_world_testing(self, doc: Reader) -> Heuristic:
        live = (
            r"live (?:trials?|pilots?)|pilots? (?:with|at) |field (?:trials?|deployment)|"
            r"real[- ]world conditions|tested (?:on|with) (?:live|real) "
        )
        denied = doc.denies(live)
        if denied and not doc.affirms(live):
            return Heuristic(
                RealWorldTesting.NONE, "the document rules out live testing before release.", denied
            )
        hit = doc.affirms(live)
        if hit:
            planned = re.search(r"\bwill\b|planned|intend", hit, re.I)
            return Heuristic(
                RealWorldTesting.PLANNED if planned else RealWorldTesting.UNDERWAY,
                "a sentence describes testing on live inputs outside a laboratory.",
                hit,
            )
        return Heuristic(
            RealWorldTesting.NOT_STATED,
            "the document does not say whether the system is trialled live before release.",
        )


# ---- the judge ----------------------------------------------------------------------------------

_STOP = frozenset(
    """the and for with from that this into over under upon each every their there where which
    what when whom whose shall must should include including includes ensure ensuring make making
    keep keeping provide providing system systems high-risk risk-ai provider providers deployer
    deployers document documentation requirement requirements appropriate relevant necessary
    accordance article paragraph point annex regulation union member states natural persons
    person such other than only also those these them they its own before after during across
    whole while within without against about through out all any one two three between via
    being been have has had does not are was were will would may might can could set use used
    using uses your you our""".split()
)

# What the judge looks for per provision, keyed "article" or "article(paragraph)": words that mark
# the SECTION (matched against headings first, then paragraphs) and words that carry SUBSTANCE
# inside it. Rules not listed derive both from their own action and criteria text.
_TOPICS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "9": (
        "risk management",
        ("risk",),
        (
            "risk management",
            "identified risk",
            "foreseeable misuse",
            "mitigat",
            "residual",
            "post-market",
            "testing",
            "review",
            "lifecycle",
            "vulnerable",
        ),
    ),
    "10": (
        "data governance",
        ("data",),
        (
            "training",
            "validation",
            "test",
            "provenance",
            "bias",
            "representative",
            "preparation",
            "labelling",
            "gaps",
            "relevan",
            "collection",
            "design choices",
        ),
    ),
    "11": (
        "technical documentation",
        ("technical documentation", "documentation", "annex iv", "technical file"),
        (
            "annex iv",
            "general description",
            "development process",
            "monitoring",
            "performance",
            "risk management",
            "changes",
            "standards",
            "declaration of conformity",
            "validation",
        ),
    ),
    "12": (
        "logging",
        ("log", "record", "event"),
        (
            "log",
            "event",
            "timestamp",
            "retain",
            "retention",
            "period of use",
            "input data",
            "identif",
            "traceab",
            "tamper",
            "post-market",
        ),
    ),
    "13": (
        "transparency and instructions for use",
        ("instructions", "transparen", "deployer"),
        (
            "instructions for use",
            "interpret",
            "deployer",
            "intended purpose",
            "accuracy",
            "limitations",
            "human oversight",
            "maintenance",
            "contact",
            "lifetime",
        ),
    ),
    "13(3)": (
        "the contents of the instructions for use",
        ("instructions",),
        (
            "contact",
            "intended purpose",
            "accuracy",
            "robustness",
            "cybersecurity",
            "foreseeable misuse",
            "limitations",
            "input data",
            "human oversight",
            "computational",
            "hardware",
            "lifetime",
            "maintenance",
            "log",
            "interpret",
            "performance",
        ),
    ),
    "14": (
        "human oversight",
        ("oversight", "human"),
        (
            "oversight",
            "override",
            "overrid",
            "interrupt",
            "stop",
            "automation bias",
            "monitor",
            "interpret",
            "disregard",
            "reverse",
            "intervene",
            "training",
            "explanation",
            "anomal",
        ),
    ),
    "15": (
        "accuracy, robustness and cybersecurity",
        ("accuracy", "robust", "performance", "security", "resilien"),
        (
            "accuracy",
            "robustness",
            "cybersecurity",
            "metric",
            "precision",
            "recall",
            "auc",
            "ndcg",
            "calibration",
            "adversarial",
            "resilien",
            "fallback",
            "drift",
            "error",
            "attack",
            "poisoning",
            "feedback loop",
        ),
    ),
    "16": (
        "the provider's name and contact address",
        ("provider", "parties", "contact"),
        (
            "provider",
            "trading as",
            "contact",
            "address",
            "@",
            "trade mark",
            "trademark",
            "registered",
        ),
    ),
    "6(4)": (
        "the not-high-risk assessment",
        ("exemption", "derogation", "6(3)", "6(4)", "not high-risk", "classification"),
        (
            "exemption",
            "derogation",
            "6(3)",
            "narrow procedural",
            "significant risk",
            "preparatory",
            "materially",
            "registered",
            "assessment",
        ),
    ),
    "50(1)": (
        "telling people they interact with an AI system",
        ("transparen", "disclos", "interaction", "notice"),
        (
            "informed",
            "told",
            "disclos",
            "aware",
            "interacting with",
            "notice",
            "label",
            "ai system",
            "obvious",
        ),
    ),
    "50(2)": (
        "marking generated content",
        ("mark", "watermark", "provenance", "transparen", "generated"),
        (
            "watermark",
            "machine-readable",
            "metadata",
            "c2pa",
            "detect",
            "mark",
            "provenance",
            "robust",
            "interoperab",
        ),
    ),
}


def _keywords(*texts: str) -> tuple[str, ...]:
    """Topic words from rule text, for a rule the table above does not know."""
    words: dict[str, None] = {}
    for text in texts:
        for word in _WORD.findall(text.lower()):
            if len(word) > 3 and word not in _STOP:
                words.setdefault(word, None)
    return tuple(words)


def _topic(rule: PolicyRule) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    article = str(rule.source.article or "")
    keyed = _TOPICS.get(f"{article}({rule.source.paragraph})") if rule.source.paragraph else None
    found = keyed or _TOPICS.get(article)
    if found:
        return found
    derived = _keywords(rule.action or "", *(c.action for c in rule.criteria))
    return (rule.action or rule.rule_id).rstrip("."), derived[:4], derived


@dataclass
class Located:
    """Where the document speaks to a topic, and how much it says."""

    section: Section
    terms: list[str] = field(default_factory=list)
    """The substance terms found in it, each once."""
    in_passing: bool = False
    """True where no heading names the topic and a paragraph elsewhere merely uses its words."""

    @property
    def figures(self) -> int:
        return _figures(self.section.body)


def _locate(doc: Reader, heading_terms: Iterable[str], body_terms: Iterable[str]) -> Located | None:
    """The section that speaks to the topic: one whose heading names it, else the one whose
    paragraphs mention at least two of its terms, else none."""
    heads = [t.lower() for t in heading_terms]
    bodies = [t.lower() for t in body_terms]

    def found_in(text: str) -> list[str]:
        low = text.lower()
        return [t for t in bodies if t in low]

    by_heading = [s for s in _titled(doc.sections) if any(t in s.heading.lower() for t in heads)]
    if by_heading:
        best = max(by_heading, key=lambda s: (len(found_in(s.body)), s.words))
        return Located(best, found_in(best.body))
    # No heading names it: a paragraph anywhere that uses three of its words counts, with its own
    # section as the context a reader opens.
    candidates: list[tuple[int, Section]] = []
    for section in doc.sections:
        for paragraph in section.paragraphs:
            hits = found_in(paragraph)
            if len(hits) >= 3:
                candidates.append((len(hits), Section(section.heading, section.level, paragraph)))
    if not candidates:
        return None
    _, best = max(candidates, key=lambda c: (c[0], c[1].words))
    return Located(best, found_in(best.body), in_passing=True)


def _titled(sections: list[Section]) -> list[Section]:
    """The sections a heading names — without the document's own title. A lone top-level heading
    is the document's name, and its "section" is the whole document, which would make every
    topic the title happens to mention look covered."""
    headed = [s for s in sections if s.heading]
    if not headed:
        return []
    top = min(s.level for s in headed)
    titles = [s for s in headed if s.level == top]
    if len(titles) == 1 and len(headed) > 1:
        return [s for s in headed if s is not titles[0]]
    return headed


def _first_sentence_with(text: str, terms: Iterable[str]) -> str | None:
    for sentence in _sentences(text):
        low = sentence.lower()
        if any(t in low for t in terms):
            return sentence
    return None


class DemoJudge:
    """Judges one rule against one document by whether, and how substantially, the document speaks
    to the rule's topic. Has the `judge(rule, document)` shape the gap graph calls."""

    name: str = "demo-judge"

    def __init__(self) -> None:
        self._last: tuple[str, Reader] | None = None
        self._lock = threading.Lock()

    def _reader(self, document: str) -> Reader:
        # Judgements run concurrently against the same document; read it once, under a lock.
        with self._lock:
            if self._last is None or self._last[0] != document:
                self._last = (document, Reader(document))
            return self._last[1]

    def judge(self, rule: PolicyRule, document: str) -> Judgement:
        doc = self._reader(document)
        name, heading_terms, body_terms = _topic(rule)
        located = _locate(doc, heading_terms, body_terms)
        if located is None:
            looked = ", ".join(list(heading_terms)[:3]) or name
            why = (
                f"nothing in the document speaks to {name}: no heading or paragraph uses its "
                f"words ({looked})."
            )
            return Judgement(
                verdict=Verdict.GAP,
                reasoning=clip_reasoning(DEMO_PREFIX + why),
                evidence_quote=None,
                evidence_chunk_id=None,
                confidence="medium",
                criteria=tuple(self._criteria(rule, Verdict.GAP, why, None, None)),
            )
        verdict, why = self._substance(rule, name, located)
        where = f'"{located.section.heading}"' if located.section.heading else "the document"
        quote = _quote(_first_sentence_with(located.section.body, located.terms or body_terms))
        return Judgement(
            verdict=verdict,
            reasoning=clip_reasoning(f"{DEMO_PREFIX}{why} ({where})."),
            evidence_quote=quote,
            evidence_chunk_id=None,
            confidence="medium",
            criteria=tuple(self._criteria(rule, verdict, why, located, quote, doc.text)),
        )

    @staticmethod
    def _substance(rule: PolicyRule, name: str, located: Located) -> tuple[Verdict, str]:
        """PASS or INADEQUATE for a topic the document does speak to, by check type."""
        words, terms, figures = located.section.words, len(located.terms), located.figures
        size = f"{words} words, {terms} of its terms, {figures} figures"
        if rule.check_type is CheckType.PRESENCE:
            return Verdict.PASS, f"the document states {name}"
        if located.in_passing:
            # Words of the topic in a paragraph about something else: mentioned, not addressed.
            return (
                Verdict.INADEQUATE,
                f"no section addresses {name}; a paragraph only touches on it ({size})",
            )
        if rule.check_type is CheckType.METRICS:
            if figures >= 3 and terms >= 2:
                return Verdict.PASS, f"the section on {name} declares figures ({size})"
            return (
                Verdict.INADEQUATE,
                f"the section on {name} claims it without enough figures ({size})",
            )
        if rule.check_type is CheckType.COMPLETENESS and rule.criteria:
            covered = sum(
                1 for c in rule.criteria if c.mandatory and _criterion_hit(c, located.section.body)
            )
            mandatory = sum(1 for c in rule.criteria if c.mandatory)
            if mandatory and covered / mandatory >= 0.6:
                return (
                    Verdict.PASS,
                    f"the section on {name} covers {covered} of {mandatory} listed elements",
                )
            return (
                Verdict.INADEQUATE,
                f"the section on {name} covers only {covered} of {mandatory} listed elements",
            )
        if words >= 80 and (terms >= 3 or figures >= 2):
            return Verdict.PASS, f"the section on {name} describes measures ({size})"
        return Verdict.INADEQUATE, f"the section on {name} asserts it without substance ({size})"

    @staticmethod
    def _criteria(
        rule: PolicyRule,
        verdict: Verdict,
        why: str,
        located: Located | None,
        quote: str | None,
        whole: str = "",
    ) -> list[CriterionFinding]:
        """One finding per mandatory criterion. With no section, every criterion is a gap; with a
        thin one, every criterion is inadequate; with a substantive one, a criterion passes where
        the section uses its words and is inadequate where it does not."""
        out: list[CriterionFinding] = []
        for criterion in rule.criteria:
            if not criterion.mandatory:
                continue
            if located is None or verdict is Verdict.INADEQUATE:
                out.append(
                    CriterionFinding(
                        norm_id=criterion.norm_id,
                        mandatory=True,
                        verdict=verdict,
                        reasoning=clip_reasoning(DEMO_PREFIX + why),
                        evidence_quote=quote if verdict is not Verdict.GAP else None,
                        confidence="medium",
                    )
                )
                continue
            # The section first, then the whole document: a technical file often answers one
            # criterion of Art. 15 under another heading.
            hit = _criterion_hit(criterion, f"{located.section.heading} {located.section.body}")
            hit = hit or _criterion_hit(criterion, whole)
            out.append(
                CriterionFinding(
                    norm_id=criterion.norm_id,
                    mandatory=True,
                    verdict=Verdict.PASS if hit else Verdict.INADEQUATE,
                    reasoning=clip_reasoning(
                        f"{DEMO_PREFIX}the section uses the words of this criterion ({hit})."
                        if hit
                        else f"{DEMO_PREFIX}the section does not use the words of this criterion "
                        f"({', '.join(_criterion_terms(criterion)[:4])})."
                    ),
                    evidence_quote=_quote(_first_sentence_with(located.section.body, [hit]))
                    if hit
                    else None,
                    confidence="medium",
                )
            )
        return out


def _criterion_terms(criterion: RuleCriterion) -> tuple[str, ...]:
    return _keywords(criterion.action, *criterion.mandatory_content)


def _criterion_hit(criterion: RuleCriterion, text: str) -> str | None:
    """The first of the criterion's words the text uses, matched on a 5-letter stem so "logging"
    finds "logs" and "mitigation" finds "mitigated"."""
    low = text.lower()
    for term in _criterion_terms(criterion):
        stem = term[:5] if len(term) > 5 else term
        if stem in low:
            return term
    return None


# ---- the summariser -----------------------------------------------------------------------------

_TITLE_SPLIT = re.compile(r"\s+[—–-]\s+|:\s+|\s+\(")
_TITLE_NOISE = re.compile(
    r"\b(?:technical (?:documentation|file)|system card|product (?:overview|page|sheet)|"
    r"how it works|documentation|overview)\b",
    re.IGNORECASE,
)
# A stated purpose is a LABEL at the start of a line ("**Intended purpose.** ...", "Intended
# purpose: ..."), never the words in passing ("...or changing its intended purpose."). The text
# runs to the end of the paragraph.
_PURPOSE = re.compile(
    r"^[ \t]*(?:[-*]\s+)?\*{0,2}intended purpose\*{0,2}[.:]\*{0,2}[ \t]*(.+?)"
    r"(?:\n\s*\n|\n(?=\s*[-*#]|\s*\*\*)|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
_SYSTEM_LINE = re.compile(
    r"^\*{0,2}system\*{0,2}:\*{0,2}\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)


class DemoSummariser:
    """Quotes the document rather than writing about it: the first heading as the name, the stated
    intended purpose — or, failing that, the first real paragraph — as the summary."""

    def summarise(self, document: str) -> SystemSummary | None:
        text = re.sub(r"<!--.*?-->", "", document, flags=re.DOTALL)
        summary = self._purpose(text) or self._first_paragraph(text)
        if not summary:
            return None
        return SystemSummary(name=self._name(text), summary=_fit(summary, SUMMARY_MAX))

    @staticmethod
    def _name(text: str) -> str | None:
        heading = _HEADING.search(text)
        if heading:
            title = _clean(heading.group(2))
            title = _TITLE_SPLIT.split(title)[0]
            title = _TITLE_NOISE.sub("", title).strip(" -—–:")
            if title:
                return _fit(title, NAME_MAX)
        line = _SYSTEM_LINE.search(text)
        if line:
            return _fit(_clean(line.group(1)), NAME_MAX)
        return None

    @staticmethod
    def _purpose(text: str) -> str | None:
        match = _PURPOSE.search(text)
        if not match:
            return None
        purpose = _clean(match.group(1))
        return _lead(purpose, 3) if len(purpose) >= 40 else None

    @staticmethod
    def _first_paragraph(text: str) -> str | None:
        for block in re.split(r"\n\s*\n", text):
            stripped = block.strip()
            if not stripped or stripped[0] in "#*-|<>`[" or stripped.startswith("Version"):
                continue
            paragraph = _clean(stripped)
            if len(paragraph) >= 80:
                return _lead(paragraph, 3)
        return None


def _lead(text: str, sentences: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:sentences])


def _fit(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"
