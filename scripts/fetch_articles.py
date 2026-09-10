#!/usr/bin/env python3
"""Fetch the literal article text of Regulation (EU) 2024/1689 (the AI Act) and store it in the
repo, one clean file per article. Reproducible and deterministic: re-running when the law is
unchanged produces byte-identical files (a file is only rewritten when its legal text changes).

Source of truth
---------------
The authoritative, structured manifestation on EUR-Lex / the EU Publications Office: the
**Formex v4 XML**, either of the Official Journal document (CELEX 32024R1689) or of a CONSOLIDATED
version (CELEX 02024R1689-<date>), English expression. Formex marks every article, numbered
paragraph and lettered point as its own element, so extraction is deterministic — no HTML scraping,
no LLM in the path, no paraphrase. This is the mechanism that lets us trust the `requirement` fields
in data/policy/spec.yaml: they can be checked, word for word, against the files this script writes.

The two manifestations are laid out differently and this script reads both: an OJ act ships one
Formex part per document (`*.fmx.xml`, annexes with root `<ANNEX>`), a consolidated act ships a
single `CL*.xml` whose annexes are `<CONS.ANNEX>` elements inside it. A consolidation also carries
LETTERED articles inserted by the amending act (4a, 60a, 75a…), which is why an article id here is
a string: reading "Article 4a" as the number 4 does not fail, it overwrites Article 4.

Why not PDF/HTML: the PDF is the legally authentic form but needs lossy layout extraction; the
legacy HTML is class-soup that mixes recitals with articles. Formex carries the same authentic
text in a clean tree — the right source for a reproducible pipeline. The authentic PDF URL is
recorded in each file's front matter for anyone who wants to compare against the OJ original.

Refresh on a new Act version
----------------------------
Versions live side by side under <out-root>/<act_version_date>/, so a report pinned to an older
version stays reproducible after a newer one is fetched. Add the new version to VERSIONS below,
then:

    python scripts/fetch_articles.py --version-date <new-date>

Files are only written when their text changed (compared by sha256), so re-running on an unchanged
version is a no-op and `git status` after a refresh IS the diff of what the legislator altered.

Two things then have to happen, and neither may be silent:
  - every NEW article must be classified in data/policy/scope-<version>.yaml (cited by a rule, or
    out of scope with a reason). The coverage test fails until a human rules on it.
  - every rule whose cited text CHANGED must be reviewed and marked `status: amended`.

TODO — a second version now EXISTS (2026-07-27), so these are no longer hypothetical:
  - scripts/diff_versions.py  --from A --to B : articles added / removed / text-changed, and which
    rules each change touches.
  - scripts/migrate_spec.py   --from A --to B : carry over rules whose cited text is byte-identical;
    mark rules whose text moved as status=amended + amended_by; list new articles as untriaged.
  The 2026-07-27 refresh was triaged by hand (36 articles changed, 6 added, Annexes I and VIII
  changed, Annex XIV added). That was tractable once; it is the argument for building these.

Usage
-----
    python scripts/fetch_articles.py                 # all articles
    python scripts/fetch_articles.py --articles 6,9,14,43
    python scripts/fetch_articles.py --version-date 2026-07-27 --cache .cache/aiact-2026-07-27.zip

A cache holds ONE version's manifestation, so name the file after the version it came from and never
share one between versions. `verify_manifestation` refuses a zip that is not the version being
written — a cached download for another version used to rebuild the store from the wrong text with
every integrity test still green, because each sha256 is recomputed from this script's own output.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from typing import NamedTuple

# --- Pinned provenance for CELEX 32024R1689 (English) -------------------------------------------
CELEX = "32024R1689"
INSTRUMENT = "Regulation (EU) 2024/1689"
LANGUAGE = "ENG"
ELI = "http://data.europa.eu/eli/reg/2024/1689/oj"

# The version the ruleset pins, so a bare run refreshes the store the tool actually resolves
# against. Every other version in VERSIONS is reachable by naming it.
DEFAULT_VERSION_DATE = "2026-07-27"
DEFAULT_OUT_ROOT = Path("data/policy/articles")
DEFAULT_ANNEX_ROOT = Path("data/policy/annexes")


class ActVersion(NamedTuple):
    """One retrievable version of the Regulation. `zip_url` is the direct Formex manifestation."""

    zip_url: str
    resource_url: str
    pdf_url: str
    description: str
    celex: str = CELEX
    """The CELEX of THIS version. A consolidation has its own — `02024R1689-20260727`, not the
    original `32024R1689` — and recording the original against consolidated text would point a
    reader at a document that does not contain the words above it."""


# Registry of retrievable versions, keyed by act_version_date.
#
# 2024-07-12 is the ORIGINAL Official Journal publication (L_202401689). That document is
# immutable — it can never gain or lose an article — which is what makes re-running this script
# byte-for-byte reproducible. IT IS LISTED HERE AND NOT IN THE STORE, and the two facts are
# independent: what a version costs to keep is a directory the coverage ledger must account for
# and the tests must hold to the spec, while what it costs to keep FETCHABLE is these six lines.
# A superseded version is deleted from the store once nothing pins it and stays here, so the text
# behind any citation this repo ever made can be recovered without hunting for the URL again.
#
# Amendments never edit the original; they appear as a CONSOLIDATED version, a different CELLAR
# resource of the form:
#     publications.europa.eu/resource/consolidation/2024R1689%2F<YYYYMMDD>.ENG.fmx4
# When a consolidated version is published, discover its direct manifestation URL from the CELLAR
# notice (https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:32024R1689) and add an
# entry here. Unknown dates fail loudly rather than silently serving the wrong version's text.
VERSIONS: dict[str, ActVersion] = {
    "2024-07-12": ActVersion(
        zip_url=(
            "http://publications.europa.eu/resource/oj/"
            "L_202401689.ENG.fmx4.OJABA_L_202401689_ENG.fmx4.zip"
        ),
        resource_url="http://publications.europa.eu/resource/oj/L_202401689.ENG.fmx4",
        pdf_url="http://publications.europa.eu/resource/oj/L_202401689.ENG.pdfa2a",
        description="Original Official Journal publication (OJ L, 2024/1689, 12.7.2024)",
    ),
    "2026-07-27": ActVersion(
        zip_url=(
            "http://publications.europa.eu/resource/celex/"
            "02024R1689-20260727.ENG.fmx4."
            "CONSLEG_02024R1689-20260727_0010010_ENG.fmx4.zip"
        ),
        resource_url="http://publications.europa.eu/resource/celex/02024R1689-20260727.ENG.fmx4",
        pdf_url="https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:02024R1689-20260727",
        description=(
            "Consolidated text as amended by Regulation (EU) 2026/1744 of 8 July 2026 "
            "(Digital Omnibus on AI), applicable from 27 July 2026"
        ),
        celex="02024R1689-20260727",
    ),
}

# --- Formex rendering ---------------------------------------------------------------------------
# Formex stores typographic quotes around defined terms as empty marker elements; itertext() would
# drop them. Map them back to the curly quotes the printed OJ uses, for literal fidelity.
_QUOT = {"QUOT.START": "‘", "QUOT.END": "’"}
# Block-level children that start a new line; everything else is inline text.
_BLOCK = {"ALINEA", "LIST", "PARAG", "DIVISION"}
_WS = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:)])")
_SPACE_AFTER_OPEN = re.compile(r"(\()\s+")


def _normalise(text: str) -> str:
    """Collapse whitespace and remove serialization-artifact spaces around punctuation. These are
    typographic normalisations (the printed OJ has no space before a comma or inside a bracket);
    they make the text more faithful to the original, not less."""
    text = _WS.sub(" ", text).strip()
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN.sub(r"\1", text)
    return text


def _inline(el: ET.Element) -> str:
    """Serialise an element's inline text, restoring quote markers, then normalise."""
    out: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.tag in _QUOT:
            out.append(_QUOT[node.tag])
        if node.text:
            out.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                out.append(child.tail)

    walk(el)
    return _normalise("".join(out))


def _split(el: ET.Element, skip: set[str]) -> tuple[list[str], list[ET.Element]]:
    """Partition a container's children into inline text parts and block children."""
    parts: list[str] = []
    blocks: list[ET.Element] = []
    if el.text and el.text.strip():
        parts.append(el.text.strip())
    for child in el:
        if child.tag in skip:
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())
            continue
        # A child is a block if it IS one, or if it merely wraps one. Annexes nest
        # <P><LIST>…</LIST></P>, so treating a wrapper as inline would flatten a whole
        # lettered list onto a single line and destroy the numbering. <NP> is a numbered point in
        # its own right: Annex XI Section 2 hangs its points straight off <GR.SEQ> with no <LIST>
        # around them, and reading those as inline runs the whole section into one line with each
        # label glued to its text ("1.A detailed description…").
        if (
            child.tag in _BLOCK
            or child.tag == "NP"
            or child.find("LIST") is not None
            or child.find("PARAG") is not None
            or child.find("NP") is not None
        ):
            blocks.append(child)
        else:
            t = _inline(child)
            if t:
                parts.append(t)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())
    return parts, blocks


def _render(el: ET.Element, indent: int) -> list[str]:
    """Render a block element to indented text lines."""
    if el.tag == "LIST":
        lines: list[str] = []
        for item in el.findall("ITEM"):
            lines += _render(item, indent)
        return lines
    if el.tag == "ITEM":
        # `is not None`, never `or`: an <NP> that holds only attributes or an empty <NO.P> is
        # FALSY as an Element, so `el.find("NP") or el` silently falls back to the ITEM and loses
        # the point's label. Element truthiness is also deprecated and will raise in future Python.
        np = el.find("NP")
        holder = np if np is not None else el
        no = holder.find("NO.P")
        label = _inline(no) if no is not None else ""
        return _labeled(holder, indent, label, {"NO.P"})
    if el.tag == "NP":
        no = el.find("NO.P")
        label = _inline(no) if no is not None else ""
        return _labeled(el, indent, label, {"NO.P"})
    if el.tag == "PARAG":
        no = el.find("NO.PARAG")
        label = _inline(no) if no is not None else ""
        return _labeled(el, indent, label, {"NO.PARAG"})
    if el.tag == "GR.SEQ":
        # A grouped sequence carries a <TITLE> of <TI>/<STI>, exactly like an annex. render_annex
        # puts those on their own lines; concatenating them inline instead runs the two together
        # ("Section 2Additional information…"), because Formex leaves no whitespace between them.
        title = el.find("TITLE")
        lines = []
        if title is not None:
            for tag in ("TI", "STI"):
                sub = title.find(tag)
                if sub is None:
                    continue
                # Annex X numbers its categories inside the title (<TI><NP><NO.P>3.</NO.P>Eurodac);
                # rendering that as plain inline text loses the separator and yields "3.Eurodac".
                np = sub.find("NP")
                if np is not None:
                    lines += _render(np, indent)
                elif text := _inline(sub):
                    lines.append("    " * indent + text)
        parts, blocks = _split(el, {"TITLE"})
        # Running text directly under the heading is the section's whole body when nothing else
        # follows — Annex X lists categories 3, 4 and 6 as a single regulation this way, where the
        # others use a lettered list — so indent it like those items. With blocks present that text
        # is a chapeau introducing them and stays at the heading's level.
        if intro := _normalise(" ".join(parts)):
            lines.append("    " * (indent if blocks else indent + 1) + intro)
        for block in blocks:
            lines += _render(block, indent + 1)
        return lines
    return _labeled(el, indent, "", set())


def _labeled(el: ET.Element, indent: int, label: str, skip: set[str]) -> list[str]:
    """Render `el`, attaching a paragraph/point label to the first output line so numbering never
    dangles on a line of its own."""
    parts, blocks = _split(el, skip)
    pad = "    " * indent
    lines: list[str] = []
    intro = _normalise(" ".join(parts))
    if intro:
        lines.append(pad + intro)
    for block in blocks:
        lines += _render(block, indent + 1)
    if label:
        if lines:
            lines[0] = pad + f"{label} {lines[0].lstrip()}"
        else:
            lines = [pad + label]
    return lines


def article_sort_key(article_id: str) -> tuple[int, str]:
    """Order "4" before "4a" before "5" — the Act's own order, which plain string sort loses."""
    m = re.match(r"(\d+)([a-z]*)", article_id)
    return (int(m.group(1)), m.group(2)) if m else (0, article_id)


def render_article(art: ET.Element) -> tuple[str, str, str]:
    """Return (article_id, title, literal_body_text) for one ARTICLE element.

    The id is a STRING because an amending act inserts lettered articles — Regulation (EU)
    2026/1744 added Articles 4a, 60a and 75a to 75d. Matching `(\\d+)` alone reads "Article 4a" as
    4, and in a dict keyed by number that does not fail, it OVERWRITES Article 4 with the text of a
    different provision. A silently wrong article is the worst output this script has.
    """
    ti = art.find("TI.ART")
    number_text = _inline(ti) if ti is not None else ""  # e.g. "Article 9", "Article 4a"
    m = re.search(r"(\d+[a-z]?)", number_text)
    number = m.group(1) if m else ""
    sti = art.find("STI.ART")
    title = _inline(sti) if sti is not None else ""
    lines = [number_text]
    if title:
        lines.append(title)
    lines.append("")
    for child in art:
        if child.tag in ("TI.ART", "STI.ART"):
            continue
        lines += _render(child, 0)
    return number, title, "\n".join(lines).rstrip() + "\n"


def render_annex(annex: ET.Element) -> tuple[str, str, str]:
    """Return (roman_numeral, title, literal_body_text) for one ANNEX element.

    Annexes matter as much as articles: Annex III IS the list of high-risk areas the classification
    cascade asks about, and Annex IV is the technical-documentation checklist Art. 11 points at.
    Leaving them out would mean the graph reasons about Annex III from a model's memory rather than
    from the enacted text — the exact thing the article store exists to prevent.
    """
    title_el = annex.find("TITLE")
    ti = title_el.find("TI") if title_el is not None else None
    # Most annexes put the number in <TI> and the subject in <STI>. Annex X instead nests both as
    # two <P> elements inside <TI>, and flattening those inline runs them together
    # ("ANNEX XUnion legislative acts…"), so take each paragraph as its own line.
    ti_lines = [_inline(p) for p in ti.findall("P")] if ti is not None else []
    ti_lines = [line for line in ti_lines if line] or ([_inline(ti)] if ti is not None else [])
    heading = ti_lines[0] if ti_lines else ""  # "ANNEX III"
    m = re.search(r"ANNEX\s+([IVXL]+)", heading)
    roman = m.group(1) if m else ""
    sti = title_el.find("STI") if title_el is not None else None
    title = _inline(sti) if sti is not None else " ".join(ti_lines[1:])

    lines = list(ti_lines)
    if title and title not in ti_lines:
        lines.append(title)
    lines.append("")
    contents = annex.find("CONTENTS")
    if contents is not None:
        for child in contents:
            lines += _render(child, 0)
    return roman, title, "\n".join(lines).rstrip() + "\n"


# --- Fetch / parse ------------------------------------------------------------------------------
def download_zip(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "aiact-compliance-agent/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted EU gov URL)
        return resp.read()


def pick_body_xml(zip_bytes: bytes) -> bytes:
    """From the Formex zip, return the doc part containing the enacting articles (the member with
    the most ARTICLE elements)."""
    # `.xml`, not `.fmx.xml`: an OJ act ships one part per document (`*.fmx.xml`), a CONSOLIDATED
    # act ships the whole thing as a single `CL*.xml`. Picking the member with the most ARTICLE
    # elements works for both, so the two layouts need no branch beyond this.
    best: tuple[int, bytes] = (-1, b"")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            data = zf.read(name)
            try:
                root = ET.fromstring(data)
            except ET.ParseError:
                continue
            count = len(root.findall(".//ARTICLE"))
            if count > best[0]:
                best = (count, data)
    if best[0] <= 0:
        sys.exit("No Formex part with ARTICLE elements found in the zip.")
    return best[1]


def parse_articles(body_xml: bytes) -> dict[str, tuple[str, str]]:
    root = ET.fromstring(body_xml)
    articles: dict[str, tuple[str, str]] = {}
    for art in root.findall(".//ARTICLE"):
        number, title, text = render_article(art)
        if not number:
            continue
        if number in articles:
            sys.exit(f"Two ARTICLE elements both parsed as Article {number} — refusing to guess.")
        articles[number] = (title, text)
    return articles


def zip_layout(zip_bytes: bytes) -> str:
    """Return "consolidated" if the zip carries <CONS.ANNEX> annexes, else "official-journal"."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".xml"):
                continue
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            if next(root.iter("CONS.ANNEX"), None) is not None:
                return "consolidated"
    return "official-journal"


def expected_layout(version: ActVersion) -> str:
    return "consolidated" if version.celex.startswith("0") else "official-journal"


def stored_ids(store_dir: Path, pattern: str) -> set[str]:
    ids: set[str] = set()
    for path in store_dir.glob(pattern.replace("{}", "*")):
        m = re.fullmatch(pattern.replace("{}", r"(.+)"), path.name)
        if m:
            ids.add(m.group(1).lstrip("0") or "0")
    return ids


def verify_manifestation(
    zip_bytes: bytes,
    version: ActVersion,
    version_date: str,
    out_dir: Path,
    annex_dir: Path,
) -> None:
    "Refuse a Formex zip that is not the requested version."
    found, wanted = zip_layout(zip_bytes), expected_layout(version)
    if found != wanted:
        sys.exit(
            f"Formex zip is a {found} manifestation, but act version {version_date} "
            f"({version.celex}) is {wanted}. Refusing to write another version's text.\n"
            f"Expected manifestation: {version.zip_url}"
        )

    articles = set(parse_articles(pick_body_xml(zip_bytes)))
    annexes = set(parse_annexes(zip_bytes))
    for label, parsed, stored in (
        ("article", articles, stored_ids(out_dir, "article-{}.md")),
        ("annex", annexes, stored_ids(annex_dir, "annex-{}.md")),
    ):
        lost = stored - parsed
        if lost:
            sys.exit(
                f"Formex zip is missing {len(lost)} {label}(s) already stored for {version_date}: "
                f"{', '.join(sorted(lost))}.\n"
                f"That means the zip is not {version.celex} — a cached download for a different "
                f"version, most likely. Delete the cache and re-fetch:\n"
                f"  {version.zip_url}"
            )


def parse_annexes(zip_bytes: bytes) -> dict[str, tuple[str, str]]:
    """roman numeral -> (title, literal text).

    TWO LAYOUTS, because the two manifestations differ. In an OJ act each annex is its own Formex
    part with root <ANNEX>; in a CONSOLIDATED act every annex is a <CONS.ANNEX> element inside the
    single body document. Missing the second would drop all fourteen annexes silently — including
    Annex III, which the whole classification cascade reads.
    """
    annexes: dict[str, tuple[str, str]] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in sorted(zf.namelist()):
            if not name.endswith(".xml"):
                continue
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            elements = [root] if root.tag == "ANNEX" else list(root.iter("CONS.ANNEX"))
            for el in elements:
                roman, title, text = render_annex(el)
                if roman:
                    annexes[roman] = (title, text)
    return annexes


# --- Write (deterministic: skip unchanged) ------------------------------------------------------
_FRONT_SHA = re.compile(r"^sha256:\s*([0-9a-f]{64})\s*$", re.M)


def existing_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    m = _FRONT_SHA.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def write_article(
    path: Path, number: str, title: str, body: str, version_date: str, version: ActVersion
) -> bool:
    """Write the article file. Returns True if written, False if unchanged (skipped).
    retrieved_at reflects the last time the TEXT changed, not the last run, so re-running on an
    unchanged Act leaves the repo byte-identical."""
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if existing_sha(path) == body_sha:
        return False
    front = (
        "---\n"
        f"instrument: {INSTRUMENT}\n"
        f"celex: {version.celex}\n"
        f"eli: {ELI}\n"
        f"language: {LANGUAGE}\n"
        f"article: {number}\n"
        f"title: {title}\n"
        "source: EUR-Lex Formex v4 XML (fmx4), Publications Office of the EU\n"
        f"source_url: {version.resource_url}\n"
        f"authentic_pdf: {version.pdf_url}\n"
        f"act_version_date: {version_date}\n"
        f"retrieved_at: {date.today().isoformat()}\n"
        f"sha256: {body_sha}\n"
        "---\n\n"
    )
    path.write_text(front + body, encoding="utf-8")
    return True


def write_annex(
    path: Path, roman: str, title: str, body: str, version_date: str, version: ActVersion
) -> bool:
    """Same contract as write_article: only writes when the legal text actually changed."""
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if existing_sha(path) == body_sha:
        return False
    front = (
        "---\n"
        f"instrument: {INSTRUMENT}\n"
        f"celex: {version.celex}\n"
        f"eli: {ELI}\n"
        f"language: {LANGUAGE}\n"
        f"annex: {roman}\n"
        f"title: {title}\n"
        "source: EUR-Lex Formex v4 XML (fmx4), Publications Office of the EU\n"
        f"source_url: {version.resource_url}\n"
        f"authentic_pdf: {version.pdf_url}\n"
        f"act_version_date: {version_date}\n"
        f"retrieved_at: {date.today().isoformat()}\n"
        f"sha256: {body_sha}\n"
        "---\n\n"
    )
    path.write_text(front + body, encoding="utf-8")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch literal AI Act article text into the repo.")
    ap.add_argument(
        "--version-date",
        default=DEFAULT_VERSION_DATE,
        help=f"act version to fetch; known: {', '.join(sorted(VERSIONS))}",
    )
    ap.add_argument(
        "--out-root",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help="article store root; articles are written to <root>/<version-date>/",
    )
    ap.add_argument("--articles", default="all", help='"all" or comma list, e.g. "6,9,14,43"')
    ap.add_argument(
        "--annex-root",
        type=Path,
        default=DEFAULT_ANNEX_ROOT,
        help="annex store root; annexes are written to <root>/<version-date>/",
    )
    ap.add_argument("--cache", type=Path, help="path to a local Formex zip to read/write")
    args = ap.parse_args()

    version = VERSIONS.get(args.version_date)
    if version is None:
        sys.exit(
            f"Unknown act version {args.version_date!r}. Known: {', '.join(sorted(VERSIONS))}.\n"
            f"A new consolidated version must be added to the VERSIONS registry in this script — "
            f"see the comment there for how to discover its manifestation URL. Refusing to guess."
        )
    print(f"Act version {args.version_date} — {version.description}")

    if args.cache and args.cache.is_file():
        print(f"Using cached Formex zip: {args.cache}")
        zip_bytes = args.cache.read_bytes()
    else:
        print(f"Downloading Formex zip: {version.zip_url}")
        zip_bytes = download_zip(version.zip_url)
        if args.cache:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_bytes(zip_bytes)

    out_dir = args.out_root / args.version_date
    annex_dir = args.annex_root / args.version_date
    verify_manifestation(zip_bytes, version, args.version_date, out_dir, annex_dir)

    articles = parse_articles(pick_body_xml(zip_bytes))
    print(f"Parsed {len(articles)} articles from Formex.")

    if args.articles == "all":
        wanted = sorted(articles, key=article_sort_key)
    else:
        wanted = [x.strip() for x in args.articles.split(",") if x.strip()]

    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = missing = 0
    for n in wanted:
        if n not in articles:
            print(f"  ! article {n} not found")
            missing += 1
            continue
        title, body = articles[n]
        # "9" -> article-009.md, "4a" -> article-004a.md. Zero-padding the numeric part keeps the
        # directory in the Act's own order, and the suffix keeps 4a distinct from 4 on disk as well
        # as in memory.
        parsed = re.match(r"(\d+)([a-z]*)", n)
        if parsed is None:
            print(f"  ! article {n} has no parsable number")
            missing += 1
            continue
        num, suffix = parsed.groups()
        path = out_dir / f"article-{int(num):03d}{suffix}.md"
        if write_article(path, n, title, body, args.version_date, version):
            written += 1
        else:
            skipped += 1
    print(f"\nWrote articles to {out_dir}")
    print(f"  articles: written={written} skipped(unchanged)={skipped} missing={missing}")

    # --- annexes ---------------------------------------------------------------------------
    # Annex III is the list of high-risk areas the classification cascade asks about, and Annex IV
    # is the checklist Art. 11 points at. They are law, not appendix — stored on the same terms as
    # the articles so nothing is reasoned about from memory.
    annexes = parse_annexes(zip_bytes)
    annex_dir.mkdir(parents=True, exist_ok=True)
    a_written = a_skipped = 0
    for roman in annexes:
        title, body = annexes[roman]
        path = annex_dir / f"annex-{roman}.md"
        if write_annex(path, roman, title, body, args.version_date, version):
            a_written += 1
        else:
            a_skipped += 1
    print(f"Wrote annexes to {annex_dir}")
    print(f"  annexes:  {len(annexes)} parsed, written={a_written} skipped(unchanged)={a_skipped}")


if __name__ == "__main__":
    main()
