#!/usr/bin/env python3
"""Fetch the literal article text of Regulation (EU) 2024/1689 (the AI Act) and store it in the
repo, one clean file per article. Reproducible and deterministic: re-running when the law is
unchanged produces byte-identical files (a file is only rewritten when its legal text changes).

Source of truth
---------------
The authoritative, structured manifestation on EUR-Lex / the EU Publications Office: the
**Formex v4 XML** of the Official Journal document (CELEX 32024R1689, English expression). Formex
marks every article, numbered paragraph and lettered point as its own element, so extraction is
deterministic — no HTML scraping, no LLM in the path, no paraphrase. This is the mechanism that
lets us trust the `requirement` fields in data/policy/spec.yaml: they can be checked, word for
word, against the files this script writes.

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

TODO (deferred — see the "3" item in the version-refresh design):
  - scripts/diff_versions.py  --from A --to B : articles added / removed / text-changed, and which
    rules each change touches.
  - scripts/migrate_spec.py   --from A --to B : carry over rules whose cited text is byte-identical;
    mark rules whose text moved as status=amended + amended_by; list new articles as untriaged.
  Only worth building once a second version actually exists; until then the coverage test plus
  `git status` cover the same ground manually.

Usage
-----
    python scripts/fetch_articles.py                 # all articles
    python scripts/fetch_articles.py --articles 6,9,14,43
    python scripts/fetch_articles.py --cache .cache/aiact.fmx.zip   # reuse a local download

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

DEFAULT_VERSION_DATE = "2024-07-12"
DEFAULT_OUT_ROOT = Path("data/policy/articles")


class ActVersion(NamedTuple):
    """One retrievable version of the Regulation. `zip_url` is the direct Formex manifestation."""

    zip_url: str
    resource_url: str
    pdf_url: str
    description: str


# Registry of retrievable versions, keyed by act_version_date.
#
# 2024-07-12 is the ORIGINAL Official Journal publication (L_202401689). That document is
# immutable — it can never gain or lose an article — which is what makes re-running this script
# byte-for-byte reproducible.
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
        if child.tag in _BLOCK:
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
        holder = el.find("NP") or el
        no = holder.find("NO.P")
        label = _inline(no) if no is not None else ""
        return _labeled(holder, indent, label, {"NO.P"})
    if el.tag == "PARAG":
        no = el.find("NO.PARAG")
        label = _inline(no) if no is not None else ""
        return _labeled(el, indent, label, {"NO.PARAG"})
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


def render_article(art: ET.Element) -> tuple[int, str, str]:
    """Return (article_number, title, literal_body_text) for one ARTICLE element."""
    ti = art.find("TI.ART")
    number_text = _inline(ti) if ti is not None else ""  # e.g. "Article 9"
    m = re.search(r"(\d+)", number_text)
    number = int(m.group(1)) if m else 0
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


# --- Fetch / parse ------------------------------------------------------------------------------
def download_zip(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "aiact-compliance-agent/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 (trusted EU gov URL)
        return resp.read()


def pick_body_xml(zip_bytes: bytes) -> bytes:
    """From the Formex zip, return the doc part containing the enacting articles (the member with
    the most ARTICLE elements)."""
    best: tuple[int, bytes] = (-1, b"")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".fmx.xml"):
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


def parse_articles(body_xml: bytes) -> dict[int, tuple[str, str]]:
    root = ET.fromstring(body_xml)
    articles: dict[int, tuple[str, str]] = {}
    for art in root.findall(".//ARTICLE"):
        number, title, text = render_article(art)
        if number:
            articles[number] = (title, text)
    return articles


# --- Write (deterministic: skip unchanged) ------------------------------------------------------
_FRONT_SHA = re.compile(r"^sha256:\s*([0-9a-f]{64})\s*$", re.M)


def existing_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    m = _FRONT_SHA.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def write_article(
    path: Path, number: int, title: str, body: str, version_date: str, version: ActVersion
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
        f"celex: {CELEX}\n"
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

    articles = parse_articles(pick_body_xml(zip_bytes))
    print(f"Parsed {len(articles)} articles from Formex.")

    if args.articles == "all":
        wanted = sorted(articles)
    else:
        wanted = [int(x) for x in args.articles.split(",") if x.strip()]

    out_dir = args.out_root / args.version_date
    out_dir.mkdir(parents=True, exist_ok=True)
    written = skipped = missing = 0
    for n in wanted:
        if n not in articles:
            print(f"  ! article {n} not found")
            missing += 1
            continue
        title, body = articles[n]
        path = out_dir / f"article-{n:03d}.md"
        if write_article(path, n, title, body, args.version_date, version):
            written += 1
        else:
            skipped += 1
    print(f"\nWrote to {out_dir}")
    print(f"Done. written={written} skipped(unchanged)={skipped} missing={missing}")


if __name__ == "__main__":
    main()
