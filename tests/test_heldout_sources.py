"""Held-out cases written from real documents cite them; this pins that the citation stays honest.

The documents themselves are not in the repo — third-party filings, tender notices, project records,
model cards, a manual and a press release, public to read but not ours to redistribute. What is
stored is the hash, so a reader can fetch the original and prove it is the one the case was written
from. A manifest nothing verifies would rot into decoration, which is the failure this file exists
to prevent.

`source_id` is a general identifier rather than a 510(k) number, because batch 3's sources are not
filings. The property that survived the widening is the one worth having: every part of the
identifier appears in the URL, so the citation cannot drift away from the document it names.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from aiact.eval.classification_cases import load_classification_cases

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "golden_set" / "heldout_sources.yaml"
HELDOUT = ROOT / "data" / "golden_set" / "classification_cases_heldout.yaml"

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_SOURCE_ID = re.compile(r"\A\S+\Z")


def _locators(source_id: str) -> list[str]:
    """The parts of an identifier that must appear in the URL.

    A leading `SCHEME:` names the register (TED, CORDIS, HF, ...) and is not part of the address;
    everything after it is, and `@` separates a repository from the revision pinned within it.
    An identifier with no scheme is a 510(k) number and stands whole, as batch 2 wrote it.
    """
    _, _, rest = source_id.rpartition(":")
    return [part for part in (rest or source_id).split("@") if part]


@pytest.fixture(scope="module")
def sources():
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["sources"]


def test_every_cited_case_exists(sources):
    """A manifest entry for a case that was renamed or dropped points at nothing."""
    known = {c.case_id for c in load_classification_cases(HELDOUT).cases}
    cited = {s["case_id"] for s in sources}
    assert cited <= known, f"manifest cites unknown cases: {sorted(cited - known)}"


def test_each_case_is_cited_once(sources):
    cited = [s["case_id"] for s in sources]
    assert len(cited) == len(set(cited)), "a case may come from only one source document"


def test_every_entry_can_actually_be_verified(sources):
    """url + sha256 is the whole bargain: without either, a reader cannot check the paraphrase
    against what it was made from, and the manifest is just a claim."""
    for s in sources:
        where = s["case_id"]
        source_id = s["source_id"]
        assert _SOURCE_ID.match(source_id), f"{where}: source_id must be a single token"
        assert _SHA256.match(s["sha256"]), f"{where}: sha256 must be 64 lowercase hex chars"
        assert s["url"].startswith("https://"), f"{where}: needs a fetchable URL"
        for locator in _locators(source_id):
            assert locator in s["url"], f"{where}: URL does not point at {locator!r}"
        assert s["bytes"] > 0, f"{where}: size is part of the fingerprint"


def test_the_documents_are_not_committed(sources):
    """LICENSING. These are third-party documents. Storing the hash instead of the bytes is the
    deliberate bargain; a committed copy would hash to one of the values below, whatever it was
    named, so the hashes are what this checks rather than a filename pattern."""
    cited = {s["sha256"]: s["case_id"] for s in sources}
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for name in filter(None, tracked):
        path = ROOT / name
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest not in cited, (
            f"{name} is the source document for {cited[digest]} — source documents must not be "
            f"committed"
        )
