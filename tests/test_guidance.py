"""The Commission-guidance store — reference resolution and integrity.

Guidance is the Commission's NON-BINDING interpretation, stored separately from enacted law. These
pin the two things that keep a guidance citation honest: it must resolve to a real snippet, and the
quoted text must still match the sha it was verified under (so a citation can't silently drift from
the passage a human checked against the PDF).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from aiact.eval.classification_cases import load_classification_cases
from aiact.gap.judge import LLMJudge
from aiact.guidance import load_snippet, snippet_path
from aiact.policy_loader import load_policy_spec
from aiact.schemas.enums import ActorRole, Verdict
from aiact.schemas.report import Finding

ROOT = Path(__file__).resolve().parents[1]
GUIDANCE_ROOT = ROOT / "data" / "policy" / "guidance"
CASES = ROOT / "data" / "golden_set" / "classification_cases.yaml"
REF = "C-2025-5052/workplace-covers-recruitment"


def test_ref_maps_to_the_snippet_path():
    assert snippet_path(REF, GUIDANCE_ROOT).name == "workplace-covers-recruitment.md"
    assert snippet_path(REF, GUIDANCE_ROOT).parent.name == "snippets"


@pytest.mark.parametrize("bad", ["no-slash", "C-2025-5052/", "/slug", "a/b/c"])
def test_malformed_refs_are_rejected(bad):
    with pytest.raises(ValueError, match="guidance ref must be"):
        snippet_path(bad, GUIDANCE_ROOT)


def test_the_recruitment_snippet_loads_and_is_verbatim():
    ex = load_snippet(REF, GUIDANCE_ROOT)
    assert ex.binding is False, "guidance is non-binding — the flag must say so"
    assert "para" in ex.locator.lower() or "p." in ex.locator
    # the two load-bearing sentences, verbatim from para 254
    assert "should be interpreted broadly" in ex.body
    assert "candidates during the selection and hiring process" in ex.body
    assert "during the recruitment process is prohibited" in ex.body


def test_missing_snippet_raises():
    with pytest.raises(FileNotFoundError):
        load_snippet("C-2025-5052/does-not-exist", GUIDANCE_ROOT)


def test_a_drifted_quote_fails_its_integrity_check(tmp_path):
    """If the quoted text is edited without re-verifying against the PDF, the stored sha no longer
    matches and the snippet refuses to load — this stops a citation quietly becoming wrong."""
    doc = tmp_path / "C-9999-0000" / "snippets"
    doc.mkdir(parents=True)
    src = GUIDANCE_ROOT / "C-2025-5052" / "snippets" / "workplace-covers-recruitment.md"
    tampered = src.read_text().replace("interpreted broadly", "interpreted narrowly")
    (doc / "tampered.md").write_text(tampered)
    with pytest.raises(ValueError, match="does not match its stored sha256"):
        load_snippet("C-9999-0000/tampered", tmp_path)


# --- wiring into the golden set -----------------------------------------------------------------
def test_every_golden_guidance_ref_resolves():
    """The loader resolves each ref; this asserts the set as shipped has no dangling citation."""
    gs = load_classification_cases(CASES, GUIDANCE_ROOT)
    refs = [r for c in gs.cases for r in c.guidance_refs]
    assert REF in refs, "the recruitment case should cite the workplace-covers-recruitment snippet"
    for ref in refs:
        load_snippet(ref, GUIDANCE_ROOT)  # raises if missing or drifted


def test_a_dangling_guidance_ref_fails_the_loader(tmp_path):
    bad = tmp_path / "cases.yaml"
    bad.write_text(
        "act_version_date: 2024-07-12\n"
        "default_split: dev\n"
        "cases:\n"
        "  - case_id: x\n"
        "    description: y\n"
        "    expected_risk_class: prohibited\n"
        "    expected_is_ai_system: true\n"
        "    expected_prohibited_practice: social_scoring\n"
        "    guidance_refs: [C-2025-5052/nope]\n"
        "    decisive_fact: z\n"
        "    difficulty: obvious\n"
    )
    with pytest.raises(ValueError, match="guidance_ref"):
        load_classification_cases(bad, GUIDANCE_ROOT)


def test_the_recruitment_case_is_now_prohibited_and_cited():
    gs = load_classification_cases(CASES, GUIDANCE_ROOT)
    case = next(c for c in gs.cases if c.case_id == "emotion_screening_candidates")
    assert case.expected_risk_class.value == "prohibited"
    assert case.expected_prohibited is True
    assert case.guidance_refs == [REF], "the prohibited label must carry its non-binding basis"


# --- the PDF anchor ----------------------------------------------------------------------------
def test_every_guidance_document_matches_its_recorded_sha():
    """The PDF is the anchor every snippet traces to, and nothing checked it until now.

    A snippet's own sha proves the QUOTE has not drifted since a human verified it. It says nothing
    about the document that human read: replace source.pdf with a different revision and every
    snippet still passes its own check while pointing at page numbers in a file that no longer says
    what they say. The store's README calls the PDF "authoritative, byte-exact" — this is what makes
    that true rather than aspirational."""
    docs = sorted(p for p in GUIDANCE_ROOT.iterdir() if p.is_dir())
    assert docs, "expected at least one guidance document"
    for doc in docs:
        source_md, pdf = doc / "source.md", doc / "source.pdf"
        assert source_md.is_file() and pdf.is_file(), f"{doc.name} is missing source.md/source.pdf"
        declared = re.search(
            r"^pdf_sha256:\s*([0-9a-f]{64})\s*$", source_md.read_text(encoding="utf-8"), re.M
        )
        assert declared, f"{doc.name}/source.md records no pdf_sha256"
        actual = hashlib.sha256(pdf.read_bytes()).hexdigest()
        assert actual == declared.group(1), (
            f"{doc.name}/source.pdf does not match its recorded sha256 — the stored document has "
            f"changed since its snippets were verified against it. Re-verify every snippet's "
            f"locator before trusting them."
        )


def test_every_snippet_names_a_document_that_exists():
    """A snippet's `document` must be the reference its directory actually holds — a snippet filed
    under one Communication while quoting another would cite the wrong instrument."""
    for doc in sorted(p for p in GUIDANCE_ROOT.iterdir() if p.is_dir()):
        reference = re.search(
            r"^reference:\s*(.+?)\s*$", (doc / "source.md").read_text(encoding="utf-8"), re.M
        )
        assert reference, f"{doc.name}/source.md has no reference"
        for snippet in sorted((doc / "snippets").glob("*.md")):
            loaded = load_snippet(f"{doc.name}/{snippet.stem}", GUIDANCE_ROOT)
            assert loaded.document == reference.group(1), snippet.name
            assert loaded.binding is False, f"{snippet.name} claims to be binding"


# --- Art. 50 transparency guidance -------------------------------------------------------------
def test_the_marking_snippet_loads_and_is_verbatim():
    """C(2026) 5054 para (71) is what grounds AIA-TR-A50-2's `evidence_expected`, which until now
    asserted on our own authority that a human-readable "AI-generated" label does not discharge
    Art. 50(2). It does not — but the passage also says such labels are not EXCLUDED, they are a
    complement, and that second half is the part an interpretation written from the bare Article
    was most likely to get wrong."""
    snippet = load_snippet("C-2026-5054/machine-readable-marking-defined", GUIDANCE_ROOT)
    assert snippet.binding is False
    assert "p. 25" in snippet.locator
    assert "limited to implementing marks in a machine-readable format" in snippet.body
    assert "without\nhuman intervention" in snippet.body or (
        "without human intervention" in snippet.body
    )
    assert "Perceptible marks and labels are not excluded as a complementary" in snippet.body


# --- a RULE citing guidance ---------------------------------------------------------------------
def test_the_marking_rule_resolves_its_guidance_at_load():
    """`guidance_refs` is the only guidance a rule authors; the passage and its citation are filled
    by the loader, exactly as `requirement` is filled from `source`. So a rule cannot hand-write an
    interpretation any more than it can hand-write the law."""
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-TR-A50-2")

    assert rule.guidance_refs == [
        "C-2026-5054/machine-readable-marking-defined",
        "C-2026-5054/both-elements-required",
        "C-2026-5054/detection-must-be-available",
    ]
    assert "without human intervention" in rule.guidance_context
    assert all(g.binding is False for g in rule.guidance_sources)
    assert {g.reference for g in rule.guidance_sources} == {"C(2026) 5054 final"}


def test_the_marking_rule_carries_the_detection_half_of_the_paragraph():
    """ART. 50(2) IS A CONJUNCTION, and both sides have to be asked for.

    The enacted words are "marked in a machine-readable format AND detectable as artificially
    generated or manipulated". Marking is the half a provider documents readily; detection is the
    half that goes unsaid, so evidence written around marking alone passes a provider whose marks
    only the provider can read — a false PASS on half a duty, on the only Art. 50 rule that is both
    document_verifiable and check_type substance.

    Both halves are pinned here: the enacted conjunction, which comes from the resolved law, and
    the guidance that says one element does not suffice, which comes from the store."""
    rule = next(r for r in load_policy_spec().rules if r.rule_id == "AIA-TR-A50-2")

    assert "detectable as artificially generated or manipulated" in rule.requirement
    assert "will not suffice to comply" in rule.guidance_context
    assert "means of detection are available to the persons" in rule.guidance_context
    assert "DETECTION" in rule.evidence_expected, (
        "the evidence must ask for the detection half, not only the marking half"
    )


def test_no_other_rule_leans_on_interpretation():
    """Guidance is for where the enacted text leaves a question open, and that should stay rare.
    A ruleset quietly accumulating interpretations is one whose verdicts are progressively less
    grounded in the Article they cite."""
    spec = load_policy_spec()
    citing = {r.rule_id for r in spec.rules if r.guidance_refs}
    assert citing == {"AIA-TR-A50-2"}


def test_a_dangling_rule_guidance_ref_fails_the_spec_load(tmp_path):
    """Fails the LOAD, not the run — the same contract as a missing article file. A ruleset that
    starts up and only discovers its citation is broken while judging has already shipped."""
    raw = yaml.safe_load((ROOT / "data" / "policy" / "spec.yaml").read_text(encoding="utf-8"))
    raw["rules"][0]["guidance_refs"] = ["C-2026-5054/does-not-exist"]
    bad = tmp_path / "dangling.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_policy_spec(bad, ROOT / "data" / "policy" / "articles")


@pytest.mark.parametrize("field", ["guidance_context", "guidance_sources"])
def test_a_rule_may_not_hand_write_its_guidance(tmp_path, field):
    """A paraphrased interpretation is as unverifiable as a paraphrased Article, and the loader
    rejects both on the same terms."""
    raw = yaml.safe_load((ROOT / "data" / "policy" / "spec.yaml").read_text(encoding="utf-8"))
    raw["rules"][0][field] = "the Commission says this is fine"
    bad = tmp_path / "handwritten.yaml"
    bad.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=f"hand-writes `{field}`"):
        load_policy_spec(bad, ROOT / "data" / "policy" / "articles")


def test_the_judge_sees_guidance_labelled_and_apart_from_the_law():
    """The Commission's reading of a provision is not the provision. Shown as one passage, a judge
    would weigh an interpretation as enacted text and the finding could not say which it rested
    on."""
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-TR-A50-2")
    judge = LLMJudge.__new__(LLMJudge)
    judge.profile = SimpleNamespace(caches=lambda _: False)
    prompt = judge._user_content(rule, hits=())

    assert "NON-BINDING guidance from the European Commission" in prompt
    assert "only authoritative interpreter" in prompt
    # The enacted text ends before the guidance block opens — the two are never one passage.
    assert prompt.index(rule.requirement) < prompt.index("NON-BINDING")
    assert "never treat it as adding a requirement the Article does not contain" in prompt


def test_a_finding_records_the_interpretation_it_was_reached_with():
    """The report has to be able to say a verdict leaned on Commission interpretation. Taken from
    the RULE — what the judge was shown — rather than from the model's reply, because the model is
    never asked and a self-report would be the wrong evidence anyway."""
    spec = load_policy_spec()
    rule = next(r for r in spec.rules if r.rule_id == "AIA-TR-A50-2")
    finding = Finding(
        rule_id=rule.rule_id,
        use_case_id="uc",
        role=ActorRole.PROVIDER,
        verdict=Verdict.PASS,
        reasoning="stub",
        citation=rule.source,
        confidence="high",
        guidance=list(rule.guidance_sources),
    )
    assert finding.rests_on_guidance is True
    assert finding.guidance[0].snippet_ref == "C-2026-5054/machine-readable-marking-defined"

    plain = finding.model_copy(update={"guidance": []})
    assert plain.rests_on_guidance is False


def test_every_snippet_declares_what_it_leaves_out():
    """A SHA PROVES A QUOTE IS UNALTERED, NEVER THAT IT IS COMPLETE.

    A passage that keeps half its worked examples hashes perfectly and reads as the whole passage.
    That is not hypothetical: the Art. 5(1)(f) snippet is a paragraph plus five bulleted examples,
    and a quote of it carrying only the two that say "is prohibited" would present the Commission as
    supporting a wider ban than it wrote — the other three include "is not prohibited by Article
    5(1)(f)" and "are allowed".

    So `omits` is required, and the loader refuses a snippet without it. It cannot be verified
    mechanically against a PDF this repo has no library to read, which is exactly why it is a claim
    someone has to write down rather than a check nobody performs."""
    root = ROOT / "data" / "policy" / "guidance"
    refs = [
        f"{doc.name}/{snippet.stem}"
        for doc in sorted(root.iterdir())
        if doc.is_dir()
        for snippet in sorted((doc / "snippets").glob("*.md"))
    ]
    assert refs, "no guidance snippets found — re-derive this test"
    for ref in refs:
        snippet = load_snippet(ref)
        assert len(snippet.omits.strip()) > 6, (
            f"{ref} declares `omits` without saying anything. Write `omits: nothing` where the "
            f"passage is quoted whole, or name what was left out and why it does not matter."
        )


def test_a_snippet_without_an_omits_field_fails_to_load(tmp_path):
    """The field is enforced at LOAD, so a truncated quote cannot reach a prompt while someone
    means to document it later."""
    store = tmp_path / "C-2025-5052" / "snippets"
    store.mkdir(parents=True)
    body = "(1) A passage.\n"
    (store / "no-omits.md").write_text(
        "---\nid: C-2025-5052/no-omits\ndocument: C(2025) 5052 final\nbinding: false\n"
        f"sha256: {hashlib.sha256(body.encode()).hexdigest()}\n---\n\n{body}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="no `omits:` field"):
        load_snippet("C-2025-5052/no-omits", root=tmp_path)
