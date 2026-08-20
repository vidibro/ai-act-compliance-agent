"""Load a PolicySpec from YAML, resolving each rule's requirement text from the article store.

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
from aiact.schemas.policy import PolicySpec

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n+", re.S)
_PARAGRAPH_START = re.compile(r"^(\d+)\.\s+", re.M)
_FRONT_FIELD = re.compile(r"^(\w+):\s*(.*)$", re.M)
_POINT_LABEL = re.compile(r"^(?P<indent>[ \t]*)\((?P<label>[a-z]+)\)\s", re.M)


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


def _read_article(articles_dir: Path, article: int) -> tuple[str, dict[str, str]]:
    """Return (provision_text, front_matter) for one article file.

    provision_text is the article body with the "Article N" / title heading stripped — i.e. the
    enacted provisions only.
    """
    path = articles_dir / f"article-{article:03d}.md"
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


def _extract_paragraph(provisions: str, paragraph: int, article: int) -> str:
    """Pull one numbered paragraph's literal text out of an article body.

    Paragraphs are rendered by scripts/fetch_articles.py as a line starting `N. ` at column 0,
    with continuation/sub-points indented — so a paragraph runs until the next such line.
    """
    starts = [(int(m.group(1)), m.start(), m.end()) for m in _PARAGRAPH_START.finditer(provisions)]
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
    raise ValueError(
        f"Article {article} has no paragraph {paragraph} (found: {available})."
    )


def _extract_point(text: str, point: str, article: int) -> str:
    """Pull one lettered point's literal text out of an article body or paragraph.

    Needed because not every obligation is a whole paragraph. Article 16 is a chapeau followed by
    points (a) to (l), most of which cross-reference another article — citing the article whole
    would resolve to the entire list and restate twelve duties in one requirement.

    The returned text KEEPS its "(b) " label and drops the chapeau, so it stays a literal substring
    of the stored article. The chapeau is not lost to the reader: it says who owes the point, and
    that is what the rule's `applies_to_role` carries.

    A point runs to the next label at the same or a shallower indent, or to the next numbered
    paragraph — so citing a point that has sub-points resolves to the point and its sub-points
    together, which is how the provision reads.
    """
    labels = list(_POINT_LABEL.finditer(text))
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
    article: int,
    paragraph: int | None,
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


def load_policy_spec(
    path: str | Path | None = None,
    articles_root: str | Path | None = None,
) -> PolicySpec:
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

    version = raw.get("act_version_date")
    if version is None:
        raise ValueError(f"{spec_path} has no act_version_date — cannot select an article store.")
    version_str = version.isoformat() if isinstance(version, date) else str(version)
    art_dir = articles_dir_for(version_str, articles_root)
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

    # Pass 2 — resolve each citation to its literal enacted text, for THIS act version.
    for rule in raw.get("rules", []):
        source = rule.get("source", {})
        article = source.get("article")
        if article is None:
            raise ValueError(f"Rule {rule.get('rule_id')!r} has no source.article to resolve.")
        text, url = resolve_requirement(
            art_dir,
            article,
            source.get("paragraph"),
            expected_version=version_str,
            point=source.get("point"),
        )
        rule["requirement"] = text
        source.setdefault("url", url)

    spec = PolicySpec.model_validate(raw)

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
