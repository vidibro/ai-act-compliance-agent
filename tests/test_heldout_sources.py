"""The Annex I held-out cases cite real documents; this pins that the citation stays honest.

The documents themselves are not in the repo — they are manufacturer-authored FDA filings, public
to read but not ours to redistribute. What is stored is the hash, so a reader can fetch the
original and prove it is the one the case was written from. A manifest nothing verifies would rot
into decoration, which is the failure this file exists to prevent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from aiact.eval.classification_cases import load_classification_cases

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "golden_set" / "heldout_sources.yaml"
HELDOUT = ROOT / "data" / "golden_set" / "classification_cases_heldout.yaml"

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_SUBMISSION = re.compile(r"\AK\d{6}\Z")


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
        assert _SUBMISSION.match(s["submission"]), f"{where}: not a 510(k) number"
        assert _SHA256.match(s["sha256"]), f"{where}: sha256 must be 64 lowercase hex chars"
        assert s["url"].startswith("https://"), f"{where}: needs a fetchable URL"
        assert s["submission"] in s["url"], f"{where}: URL must point at the cited submission"
        assert s["bytes"] > 0, f"{where}: size is part of the fingerprint"


def test_the_documents_are_not_committed():
    """LICENSING. These are third-party filings. Storing the hash instead of the bytes is the
    deliberate bargain; if the PDFs ever reappear in the tree, it has been broken silently."""
    stray = [p for p in ROOT.rglob("K[0-9][0-9][0-9][0-9][0-9][0-9].pdf") if ".git" not in p.parts]
    assert not stray, f"source filings must not be committed: {[str(p) for p in stray]}"
