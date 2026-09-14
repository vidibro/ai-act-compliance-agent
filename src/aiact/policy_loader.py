"""Load a PolicyRuleset from YAML, resolving each rule's requirement text from the article store.

Pure IO + validation — no LLM, no retrieval, no paraphrase.

The enacted wording lives in EXACTLY ONE place: data/policy/articles/*.md, written verbatim from
EUR-Lex Formex XML by scripts/fetch_articles.py. spec.yaml never contains legal text — a rule only
CITES a provision (source.article, optionally source.paragraph and source.point) and supplies the
non-legal retrieval hints (evidence_expected). At load time we resolve the citation to its literal
text and inject it into `requirement` before validation.

Why this way: Resolving from the store makes the legal text mechanically derived — the only way it
can be wrong is if the article file itself is wrong, and that file is reproducible from the
Official Journal with one command.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from aiact.config import get_settings
from aiact.guidance import load_snippet
from aiact.schemas.norm import Norm, NormRelation, NormRelationKind
from aiact.schemas.policy import PolicyRuleset, RuleCriterion
from aiact.yaml_loader import load_yaml_mapping

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n+", re.S)
# A consolidation inserts paragraphs without renumbering the ones after them, so a paragraph label
# is a STRING — `1`, `1a`, `1b` — never an integer. Art. 5(1a)-(1b) and Art. 6(1a)-(1c) are the live
# cases. The letter must be part of the match: without it `1a.` starts no paragraph and its text is
# absorbed into paragraph 1, which then resolves to several paragraphs under one citation.
_PARAGRAPH_START = re.compile(r"^(\d+[a-z]*)\.\s+", re.M)
_FRONT_FIELD = re.compile(r"^(\w+):\s*(.*)$", re.M)
_POINT_LABEL = re.compile(r"^(?P<indent>[ \t]*)\((?P<label>[a-z]+)\)\s", re.M)
# Article 3's definitions are numbered points, `(1)` to `(68)`, not numbered paragraphs. A numbered
# point takes a letter suffix for the same reason a paragraph does — Art. 3(14a) and (14b) were
# inserted between (14) and (15) without renumbering — so the label is a STRING here too. Without
# the suffix in the match, `(14a)` starts no point and its text is absorbed into (14), which then
# resolves to three definitions under one citation and leaves two off the coverage partition
# entirely: both sides of that partition read this expression.
_NUMBERED_POINT = re.compile(r"^(?P<indent>[ \t]*)\((?P<label>\d+[a-z]*)\)\s", re.M)


def verify_integrity(path: Path, raw: str, front: dict[str, str], body: str) -> None:
    """Fail loudly if a stored provision no longer matches the sha256 it was written with.

    The enacted text is the ground truth every verdict is reasoned against and cited to, so silent
    corruption here is the worst failure mode in the project: a hand-edited or mangled article would
    be fed to the model as if it were the Official Journal, and the citation on the resulting
    verdict would point at wording that is not the law. Cheap, so it is checked on every load.

    The covered span is the whole body after the front matter — the same bytes
    `scripts/fetch_articles.py` hashed when it wrote the file (`front + body`, sha of `body`). It
    therefore INCLUDES the "Article N / title" heading that `_read_article` strips for its own use;
    hashing what the generator hashed, not what the caller happens to want, is what makes the two
    sides agree.
    """
    declared = front.get("sha256")
    if not declared:
        raise ValueError(
            f"{path} has no sha256 in its front matter — regenerate it with "
            f"scripts/fetch_articles.py. Unverifiable legal text is not usable."
        )
    actual = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if actual != declared:
        raise ValueError(
            f"{path} does not match its stored sha256 (declared {declared[:12]}…, "
            f"got {actual[:12]}…). The stored enacted text has been altered since it was fetched "
            f"from the Official Journal. Do not classify against it — restore the file or re-run "
            f"scripts/fetch_articles.py."
        )


def label(value: object) -> str:
    """An article, paragraph or point id as the one type it has: a string.

    YAML writes `article: 6` unquoted, so the loader receives integers whatever the schema says.
    Converting here means the rest of the module can take `str` and mean it, rather than each
    function calling `str()` again in case this one did not."""
    return str(value)


def article_filename(article: str) -> str:
    """`4` -> article-004.md, `4a` -> article-004a.md.

    An article id is a STRING. A consolidation inserts articles without renumbering the ones after
    them, so 4a, 60a and 75a-75d are all real ids, and `int()` of one resolves to the article BEFORE
    it — Art. 4a would be read as Art. 4, quietly, with no file missing.

    Public because every caller that needs an article's path needs this rule. Spelling it as
    `f"article-{n:03d}.md"` at the call site works until the id has a letter, and then it either
    raises or resolves to the wrong article.
    """
    match = re.fullmatch(r"(\d+)([a-z]*)", article)
    if match is None:
        raise ValueError(f"{article!r} is not an article id — expected forms like 6 or 75a.")
    return f"article-{int(match.group(1)):03d}{match.group(2)}.md"


def _read_article(articles_dir: Path, article: str) -> tuple[str, dict[str, str]]:
    """Return (provision_text, front_matter) for one article file.

    provision_text is the article body with the "Article N" / title heading stripped — i.e. the
    enacted provisions only.
    """
    path = articles_dir / article_filename(article)
    if not path.is_file():
        raise FileNotFoundError(
            f"No article file for Article {article} at {path}. Run: "
            f"python scripts/fetch_articles.py --version-date {articles_dir.name}"
        )
    raw = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER.match(raw)
    if not m:
        raise ValueError(f"{path} is missing YAML front matter — regenerate it.")
    front = dict(_FRONT_FIELD.findall(m.group(1)))
    body = raw[m.end() :]
    verify_integrity(path, raw, front, body)
    # body = "Article N\n<title>\n\n<provisions>"; drop the heading block. Note the hash above
    # covers the FULL body including that heading — the generator's span, not this function's.
    _, _, provisions = body.partition("\n\n")
    return provisions.strip("\n"), front


def _extract_paragraph(provisions: str, paragraph: str, article: str) -> str:
    """Pull one numbered paragraph's literal text out of an article body.

    Paragraphs are rendered by scripts/fetch_articles.py as a line starting `N. ` at column 0,
    with continuation/sub-points indented — so a paragraph runs until the next such line.

    `paragraph` is compared as a STRING, so a rule may cite `1` or `1a` and get exactly that one.
    """
    starts = [(m.group(1), m.start(), m.end()) for m in _PARAGRAPH_START.finditer(provisions)]
    if not starts:
        raise ValueError(
            f"Article {article} has no numbered paragraphs, but a rule cites paragraph {paragraph}."
        )
    for i, (num, _start, end) in enumerate(starts):
        if num != paragraph:
            continue
        stop = starts[i + 1][1] if i + 1 < len(starts) else len(provisions)
        # Text after the "N. " label, up to the next paragraph.
        return provisions[end:stop].strip("\n").rstrip()
    available = [n for n, _, _ in starts]
    raise ValueError(f"Article {article} has no paragraph {paragraph} (found: {available}).")


def provision_labels(articles_dir: Path, article: str) -> tuple[str, ...]:
    """Every separately citable division of one article, in the order the Article writes them.

    THREE SHAPES, in the order the Act uses them. Numbered paragraphs where the article has them
    (`1`, `1a`, `2`, …); failing that its top-level NUMBERED points (`1`, `2`, … written `(1)`),
    which is how Article 3 lists its sixty-eight definitions; failing that its top-level lettered
    points (`a`, `b`, …), which is how Article 16 and the other chapeau-plus-list articles are
    built. An article that is one unbroken block has none of them and returns empty.

    The numbered-point shape is not cosmetic. Without it Article 3 falls through to the lettered
    branch and reports the sub-points buried inside individual definitions — `('a','b','a','b',…)`,
    duplicated and meaningless — so a ledger enumerating it would be ruling on labels that do not
    identify anything.

    THIS IS WHAT THE COVERAGE LEDGER COUNTS. An article-level partition answers "accounted for" as
    soon as any one rule cites any one paragraph, so most of an article's duties can go unmodelled
    inside an article the ledger records as covered. Enumerating the divisions turns "this article
    is in scope" into a claim about each duty the article contains.
    """
    provisions, _ = _read_article(articles_dir, article)
    paragraphs = tuple(m.group(1) for m in _PARAGRAPH_START.finditer(provisions))
    if paragraphs:
        return paragraphs
    numbered = list(_NUMBERED_POINT.finditer(provisions))
    if numbered:
        top = min(len(m.group("indent")) for m in numbered)
        return tuple(m.group("label") for m in numbered if len(m.group("indent")) == top)
    labels = list(_POINT_LABEL.finditer(provisions))
    if not labels:
        return ()
    top = min(len(m.group("indent")) for m in labels)
    return tuple(m.group("label") for m in labels if len(m.group("indent")) == top)


def _extract_point(text: str, point: str, article: str) -> str:
    """Pull one point's literal text out of an article body or paragraph.

    Needed because not every obligation is a whole paragraph. Article 16 is a chapeau followed by
    points (a) to (l), most of which cross-reference another article — citing the article whole
    would resolve to the entire list and restate twelve duties in one requirement.

    TWO POINT SHAPES, chosen by the label. Most articles number their points with letters; Article 3
    numbers its 68 definitions `(1)` to `(68)`. Matching a numbered one against the lettered pattern
    finds the sub-points nested inside the definitions instead — a handful of stray (a)/(b) labels
    where the caller asked for definition (14) — so a digit label selects the numbered pattern.

    The returned text KEEPS its "(b) " label and drops the chapeau, so it stays a literal substring
    of the stored article. The chapeau is not lost to the reader: it says who owes the point, and
    that is what the rule's `applies_to_role` carries.

    A point runs to the next label at the same or a shallower indent, or to the next numbered
    paragraph — so citing a point that has sub-points resolves to the point and its sub-points
    together, which is how the provision reads.
    """
    # `14a` is a numbered point, not a lettered one — routed on the FIRST character, since a
    # suffixed label is neither all digits nor all letters.
    pattern = _NUMBERED_POINT if point[:1].isdigit() else _POINT_LABEL
    labels = list(pattern.finditer(text))
    hits = [m for m in labels if m.group("label") == point]
    if not hits:
        found = [m.group("label") for m in labels]
        raise ValueError(f"Article {article} has no point ({point}) (found: {found}).")
    if len(hits) > 1:
        # Two points with the same letter means the citation is under-specified — an article whose
        # paragraphs each carry an (a). Picking the first would silently resolve to the wrong duty.
        raise ValueError(
            f"Article {article} has {len(hits)} points labelled ({point}). Cite the paragraph "
            f"as well so the point is unambiguous."
        )
    start = hits[0]
    indent = len(start.group("indent"))
    stop = len(text)
    for later in labels:
        if later.start() > start.start() and len(later.group("indent")) <= indent:
            stop = later.start()
            break
    for para in _PARAGRAPH_START.finditer(text):
        if para.start() > start.start():
            stop = min(stop, para.start())
            break
    return text[start.start() : stop].strip()


def resolve_requirement(
    articles_dir: Path,
    article: str,
    paragraph: str | None,
    expected_version: str | None = None,
    point: str | None = None,
) -> tuple[str, str]:
    """Resolve a citation to its literal enacted text. Returns (requirement_text, source_url).

    When `expected_version` is given, the article file must have been fetched for exactly that act
    version. Without this check, refreshing the article store to a newer Act would silently swap
    the text under a spec still claiming the old pin — the requirements would change meaning while
    every report kept asserting the old act_version_date.
    """
    provisions, front = _read_article(articles_dir, article)
    if expected_version is not None:
        found = front.get("act_version_date", "")
        if found != expected_version:
            raise ValueError(
                f"Article {article} in {articles_dir} was fetched for act version {found!r}, but "
                f"the spec is pinned to {expected_version!r}. Refusing to resolve requirement text "
                f"across versions — regenerate the store for {expected_version} or review the spec."
            )
    text = provisions if paragraph is None else _extract_paragraph(provisions, paragraph, article)
    if point is not None:
        text = _extract_point(text, point, article)
    return text, front.get("source_url", "")


def articles_dir_for(version: str | date, root: str | Path | None = None) -> Path:
    """The version-scoped article directory for one act version.

    The store keeps every fetched version side by side (data/policy/articles/<act_version_date>/),
    so a report pinned to an older version stays reproducible after a newer one is fetched.
    """
    settings = get_settings()
    base = Path(root) if root is not None else Path(settings.policy_articles_path)
    return base / (version.isoformat() if isinstance(version, date) else str(version))


def provision_text(path: Path) -> str:
    """Read a stored article/annex file, verify its integrity, and strip the YAML front matter.

    This text goes STRAIGHT INTO THE PROMPT as "the enacted text you must answer against", so it is
    the single most important place to check that the stored law is the law: a tampered or corrupted
    file here would be presented to the model as the Official Journal, and the verdict's citation
    would point at wording that was never enacted. Verified on every load — see
    `policy_loader.verify_integrity` and SECURITY.md.
    """
    return source_body(path).strip()


def source_body(path: Path, expected_version: str | None = None) -> str:
    """The exact integrity-checked body after generated YAML front matter.

    Unlike :func:`provision_text`, this deliberately preserves every leading and trailing
    character. Normative coverage uses offsets into this string and requires its review segments to
    concatenate back to it exactly; stripping here would make whitespace and final newlines
    impossible to account for.
    """
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if match is None:
        raise ValueError(f"{path} is missing YAML front matter — regenerate it.")
    front = dict(_FRONT_FIELD.findall(match.group(1)))
    body = raw[match.end() :]
    verify_integrity(path, raw, front, body)
    if expected_version is not None and front.get("act_version_date") != expected_version:
        raise ValueError(
            f"{path} was fetched for Act version {front.get('act_version_date')!r}, but normative "
            f"coverage is pinned to {expected_version!r}"
        )
    return body


def criterion_from_norm(norm: Norm) -> RuleCriterion:
    """The criterion a rule judges for one canonical norm — every field copied, none authored."""
    return RuleCriterion(
        norm_id=norm.norm_id,
        kind=norm.kind,
        subjects=[subject.subject_ref for subject in norm.subjects],
        action=norm.action,
        norm_text=norm.norm_text,
        conditions=list(norm.conditions),
        exceptions=list(norm.exceptions),
        mandatory_content=list(norm.mandatory_content),
        source_spans=norm.all_spans,
        verification_mode=norm.verification_mode,
    )


def load_norms_by_id(norms_root: Path, norm_ids: set[str], version: str) -> dict[str, Norm]:
    """Read only the generated norm shards that hold `norm_ids`.

    The whole inventory takes over a second to parse, and a spec is loaded far more often than a
    criterion changes. A shard that does not contain an id as text cannot define it, so the text
    test only skips work; every norm returned is still schema-validated."""
    if not norm_ids:
        return {}
    if norms_root.is_file():
        shards = [norms_root]
    elif norms_root.is_dir():
        shards = sorted(norms_root.rglob("*.yaml"))
    else:
        raise FileNotFoundError(f"No norm inventory at {norms_root} for rule criteria.")
    found: dict[str, Norm] = {}
    for shard in shards:
        text = shard.read_text(encoding="utf-8")
        if not any(f"norm_id: {norm_id}\n" in text for norm_id in norm_ids):
            continue
        for payload in load_yaml_mapping(shard, description="norm inventory shard").get(
            "norms", []
        ):
            if payload.get("norm_id") not in norm_ids:
                continue
            norm = Norm.model_validate(payload)
            if norm.norm_id in found:
                raise ValueError(f"Norm {norm.norm_id} is defined twice under {norms_root}.")
            if norm.act_version_date.isoformat() != version:
                raise ValueError(
                    f"Norm {norm.norm_id} uses Act version {norm.act_version_date}, but the spec "
                    f"is pinned to {version}."
                )
            found[norm.norm_id] = norm
    return found


def _resolve_criteria(rules: list[dict[str, Any]], norms_root: Path, version: str) -> None:
    """Replace each authored `{norm_id}` with the criterion its canonical norm defines."""
    wanted: set[str] = set()
    for rule in rules:
        for entry in rule.get("criteria", []):
            if not isinstance(entry, dict) or set(entry) != {"norm_id"}:
                raise ValueError(
                    f"Rule {rule.get('rule_id')!r} criteria entry {entry!r} must name only "
                    f"`norm_id`. Its meaning is resolved from the norm inventory — a hand-written "
                    f"action or condition would be a second source of truth."
                )
            wanted.add(str(entry["norm_id"]))
    norms = load_norms_by_id(norms_root, wanted, version)
    for rule in rules:
        resolved = []
        for entry in rule.get("criteria", []):
            norm = norms.get(entry["norm_id"])
            if norm is None:
                raise ValueError(
                    f"Rule {rule.get('rule_id')!r} names criterion {entry['norm_id']}, which is "
                    f"not in the norm inventory at {norms_root}."
                )
            if rule.get("rule_id") not in norm.implementation_refs:
                raise ValueError(
                    f"Rule {rule.get('rule_id')!r} names criterion {norm.norm_id}, whose "
                    f"implementation_refs {norm.implementation_refs} do not point back to it."
                )
            resolved.append(criterion_from_norm(norm).model_dump())
        if resolved:
            rule["criteria"] = resolved


def _national_law_notices(norms_root: Path, version: str) -> list[dict[str, object]]:
    """Materialise report notices from canonical targetless national-law relations.

    The policy spec does not author these messages. Their legal boundary and the classification
    routes that activate it live together on the reviewed norm relation, so a runtime report cannot
    quietly retain a stale paraphrase after that relation changes.
    """
    manifest = norms_root if norms_root.is_file() else norms_root / "manifest.yaml"
    payload = load_yaml_mapping(manifest, description="norm inventory manifest")
    artifact_version = str(payload.get("act_version_date", ""))
    if artifact_version != version:
        raise ValueError(
            f"Norm inventory at {norms_root} uses Act version {artifact_version!r}, but the spec "
            f"is pinned to {version!r}."
        )
    notices = []
    for raw_relation in payload.get("relations", []):
        relation = NormRelation.model_validate(raw_relation)
        if relation.kind is not NormRelationKind.NATIONAL_LAW_REGULATION:
            continue
        notices.append(
            {
                "norm_id": relation.source_norm_id,
                "prohibited_practices": relation.report_for_prohibited_practices,
                "detail": relation.detail,
            }
        )
    return notices


def load_policy_spec(
    path: str | Path | None = None,
    articles_root: str | Path | None = None,
    guidance_root: str | Path | None = None,
    annexes_root: str | Path | None = None,
    norms_root: str | Path | None = None,
) -> PolicyRuleset:
    """Read the spec, resolve every rule's requirement from the article store, and validate.

    The spec's own `act_version_date` selects which version of the article store to resolve
    against, and every article file must agree with it — so the pin is real, not decorative.

    Beyond schema validation, enforce two invariants a spec file must hold but the per-rule models
    cannot see on their own:
      - rule_id uniqueness across the whole spec (findings reference rules by id — collisions
        would make a finding ambiguous);
      - every rule pinned to the same act_version_date as the spec header, so a report generated
        from this spec is reproducible against one snapshot of the Regulation.
    """
    settings = get_settings()
    spec_path = Path(path) if path is not None else Path(settings.policy_spec_path)

    if not spec_path.is_file():
        raise FileNotFoundError(f"Policy spec not found at {spec_path}")

    with spec_path.open(encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    if "national_law_notices" in raw:
        raise ValueError(
            "Policy spec hand-writes `national_law_notices`. They are materialised from canonical "
            "national_law_regulation norm relations."
        )

    version = raw.get("act_version_date")
    if version is None:
        raise ValueError(f"{spec_path} has no act_version_date — cannot select an article store.")
    version_str = version.isoformat() if isinstance(version, date) else str(version)
    art_dir = articles_dir_for(version_str, articles_root)
    ann_dir = Path(annexes_root or settings.policy_annexes_path) / version_str
    if not art_dir.is_dir():
        raise FileNotFoundError(
            f"No article store for act version {version_str} at {art_dir}. Run: "
            f"python scripts/fetch_articles.py --version-date {version_str}"
        )

    # Pass 1 — reject hand-written legal text. Done BEFORE any injection: YAML may alias the same
    # rule dict twice, and we must not mistake our own injected text for hand-written text.
    for rule in raw.get("rules", []):
        if "requirement" in rule:
            raise ValueError(
                f"Rule {rule.get('rule_id')!r} hand-writes `requirement`. Legal text lives only in "
                f"{art_dir} and is resolved from source.article/source.paragraph — remove it."
            )
        for field in (
            "annex_context",
            "guidance_context",
            "guidance_sources",
            "qualifier_context",
        ):
            if field in rule:
                raise ValueError(
                    f"Rule {rule.get('rule_id')!r} hand-writes `{field}`. Legal and guidance text "
                    f"is resolved from `source.annex`, `qualified_by` and `guidance_refs` — remove "
                    f"it. A paraphrase is as unverifiable here as it is for the Article."
                )

    # Pass 2 — resolve each citation to its literal enacted text, for THIS act version.
    for rule in raw.get("rules", []):
        source = rule.get("source", {})
        article = source.get("article")
        if article is None:
            raise ValueError(f"Rule {rule.get('rule_id')!r} has no source.article to resolve.")
        text, url = resolve_requirement(
            art_dir,
            label(article),
            label(source["paragraph"]) if source.get("paragraph") is not None else None,
            expected_version=version_str,
            point=source.get("point"),
        )
        rule["requirement"] = text
        source.setdefault("url", url)

        # The Annex the rule cites, verbatim. Art. 11(1) names Annex IV and Annex IV is the list of
        # elements the documentation must contain, so a completeness check without it asks a judge
        # to find every item of a list nobody showed it. Integrity-checked on the same terms as the
        # Article, and kept in its own field so `requirement` stays a literal substring of the
        # Article it cites.
        annex = source.get("annex")
        if annex:
            annex_path = ann_dir / f"annex-{annex}.md"
            if not annex_path.is_file():
                raise FileNotFoundError(
                    f"Rule {rule.get('rule_id')!r} cites Annex {annex}, which is not in the store "
                    f"at {annex_path}. Run: python scripts/fetch_articles.py "
                    f"--version-date {version_str}"
                )
            rule["annex_context"] = provision_text(annex_path)

        # The provisions that QUALIFY this one, verbatim. A duty is often written in one paragraph
        # and conditioned by another that never mentions it: Art. 50(1) says a chatbot must disclose
        # itself and Art. 50(5) says when and how clearly, so a rule citing (1) alone passes a
        # disclosure buried in a footer. Supplied rather than folded into the citation, because
        # widening `source` to the whole Article would hand a deepfake rule the chatbot duty as well
        # and leave the finding pointing at the wrong paragraph.
        qualifiers = []
        for cite in rule.get("qualified_by", []):
            text, _url = resolve_requirement(
                art_dir,
                label(cite["article"]),
                label(cite["paragraph"]) if cite.get("paragraph") is not None else None,
                expected_version=version_str,
                point=cite.get("point"),
            )
            where = f"Article {cite['article']}"
            if cite.get("paragraph") is not None:
                where += f"({cite['paragraph']})"
            qualifiers.append(f"{where}:\n{text}")
        if qualifiers:
            rule["qualifier_context"] = "\n\n".join(qualifiers)

        # Pass 3 — resolve any guidance the rule cites, on the same terms as the law: verbatim,
        # integrity-checked, and failing the LOAD rather than the run when a ref does not resolve.
        # Kept structurally apart from `requirement` all the way to the prompt — a verdict that
        # leaned on the Commission's reading is weaker than one resting on the Article, and merging
        # the two here is how that distinction would be lost.
        chunks, sources = [], []
        for ref in rule.get("guidance_refs", []):
            snippet = load_snippet(ref, guidance_root)
            chunks.append(f"[{snippet.document}, {snippet.locator}]\n{snippet.body}")
            sources.append(snippet.to_source().model_dump())
        if chunks:
            rule["guidance_context"] = "\n\n".join(chunks)
            rule["guidance_sources"] = sources

    # Pass 4 — materialise each criterion from the norm it names, on the same terms as the law.
    norm_path = (
        Path(norms_root)
        if norms_root is not None
        else Path(settings.policy_normative_coverage_path) / version_str / "norms"
    )
    _resolve_criteria(raw.get("rules", []), norm_path, version_str)
    raw["national_law_notices"] = _national_law_notices(norm_path, version_str)

    spec = PolicyRuleset.model_validate(raw)

    duplicates = [rid for rid, n in Counter(r.rule_id for r in spec.rules).items() if n > 1]
    if duplicates:
        raise ValueError(f"Duplicate rule_id(s) in {spec_path}: {sorted(duplicates)}")

    mismatched = [
        r.rule_id for r in spec.rules if r.source.act_version_date != spec.act_version_date
    ]
    if mismatched:
        raise ValueError(
            f"Rule(s) in {spec_path} pinned to a different act_version_date than the spec "
            f"header ({spec.act_version_date}): {sorted(mismatched)}"
        )

    return spec
