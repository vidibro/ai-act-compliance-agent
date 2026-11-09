"""The report as a Markdown file: the page's "Download .md" button.

The file is written in the browser (`static/report-md.js`), from the response the page draws and
the checklist ticks only the browser holds. The page itself is pinned on the files the server
serves, as elsewhere; the export is pinned by RUNNING it — the page's own two scripts, loaded into
Node with a stub DOM, on a real demo review. Without Node on the machine those tests skip; the
served-file checks still run.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aiact.report_app.app import app
from aiact.report_app.samples import load_sample

STATIC = Path(__file__).resolve().parents[1] / "src" / "aiact" / "report_app" / "static"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="the export runs in the page; needs Node")

# Loads report.js and report-md.js as the page does — one global scope — with just enough DOM for
# report.js to load, then writes the Markdown for the response on stdin. `hidden` is what the
# page's Operator filter has switched off, served from a stub localStorage.
_RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const node = () => ({ setAttribute() {}, append() {}, addEventListener() {}, style: {}, dataset: {},
                      classList: { toggle() {} } });
const storage = { "aiact-review:hidden-roles": JSON.stringify(input.hidden || []) };
const ctx = {
  document: { createElement: node, getElementById: node, addEventListener() {},
              documentElement: { dataset: {} }, body: node() },
  window: { addEventListener() {} },
  fetch: () => Promise.resolve({ ok: false, json: () => ({}) }),
  localStorage: { getItem: (k) => storage[k] ?? null, setItem() {}, removeItem() {} },
  queueMicrotask, setTimeout, console,
};
vm.createContext(ctx);
for (const file of ["report.js", "report-md.js"]) {
  vm.runInContext(fs.readFileSync(input.static + "/" + file, "utf8"), ctx, { filename: file });
}
ctx.input = input;
process.stdout.write(JSON.stringify(vm.runInContext(`({
  markdown: reportMarkdown(input.response, { done: new Set(input.done || []),
                                              exportedAt: new Date("2026-01-02T03:04:00Z") }),
  filename: markdownFilename(input.response),
})`, ctx)));
"""


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def _demo(client: TestClient, sample: str) -> dict:
    found = load_sample(sample)
    assert found is not None
    response = client.post("/api/demo/review", json={"document": found.text})
    assert response.status_code == 200
    return response.json()


def _export(response: dict, *, done: list[str] = (), hidden: list[str] = ()) -> tuple[str, str]:
    """The Markdown the page would download for `response`, and the file's name."""
    assert NODE is not None
    payload = {
        "static": str(STATIC),
        "response": response,
        "done": list(done),
        "hidden": list(hidden),
    }
    result = subprocess.run(
        [NODE, "-e", _RUNNER], input=json.dumps(payload), capture_output=True, text=True, check=True
    )
    out = json.loads(result.stdout)
    return out["markdown"], out["filename"]


@pytest.fixture(scope="module")
def high_risk(client) -> dict:
    """A high-risk report with findings, a checklist and other provisions."""
    return _demo(client, "guide-system-card")


def _outstanding(response: dict) -> set[str]:
    report = response["report"]
    ids = {i for ids in report["not_document_verifiable"].values() for i in ids}
    ids |= {i for ids in report["conditional_duties"].values() for i in ids}
    return ids | {t["rule_id"] for t in report["timing_not_active"]}


# ---- the page ----------------------------------------------------------------------------------


def test_the_download_belongs_to_the_report_not_to_the_input(client):
    """At the report's head, at its end, and in a pill while reading between the two — never under
    the document, where it would read as an action on the input."""
    page = client.get("/").text
    # After report.js, whose helpers it uses.
    assert page.index("/static/report.js") < page.index("/static/report-md.js")
    assert client.get("/static/report-md.js").status_code == 200
    form = page.split('<form class="card input"')[1].split("</form>")[0]
    assert "Download" not in form and "export" not in form

    script = client.get("/static/report.js").text
    header = script.split("function header(data)")[1].split("\n}\n")[0]
    assert '"system-head"' in header and "exportButton()" in header
    render = script.split("function render(data)")[1].split("\n}\n")[0]
    assert render.index('class: "disclaimer"') < render.index('"card report-end"')
    assert "exportButton()" in render
    # The floating pair: the same buttons (class and label), in the row fixed to the window, shown
    # only between the two stops, and re-placed when rows open without a scroll.
    floatbar = page.split('<div class="floatbar" id="floatbar">')[1].split("\n</div>")[0]
    pair = floatbar.split('id="export-float" hidden>')[1]
    print_at = pair.index('class="print-report" id="print-float"')
    assert print_at < pair.index('class="export-md" id="download-float"')  # Download rightmost
    assert ">Download</button>" in pair and '"Download"' in script
    assert 'aria-label="Download report as Markdown"' in pair
    assert '$("download-float").addEventListener("click", () => downloadMarkdown())' in script
    assert '$("report").addEventListener("toggle", placeExportFloat, true)' in script
    styles = client.get("/static/report.css").text
    # One row holds the demo label and the pair, on the report's right edge at every window width —
    # not one on the report's edge and one on the window's, and not stacked.
    assert floatbar.index('id="demo-float"') < floatbar.index('id="export-float"')
    assert "\n.floatbar { position: fixed; right: var(--float-right);" in styles
    assert styles.count("--float-right: calc(max(0px, 50% - 520px)") == 2  # main's two paddings
    # On a phone, centred across the whole width rather than from a midpoint (half the window).
    assert ".floatbar { left: 12px; right: 12px; bottom: 12px; justify-content: center; }" in styles


# ---- what the file says ------------------------------------------------------------------------


@needs_node
def test_the_file_holds_every_row_of_the_report(high_risk):
    markdown, _ = _export(high_risk)
    report = high_risk["report"]

    assert markdown.startswith("# ")
    assert len(re.findall(r"^#### (Met|Not met|Partly met|Unclear) — ", markdown, re.M)) == len(
        report["findings"]
    )
    for finding in report["findings"]:
        assert f"— {high_risk['rules'][finding['rule_id']]['citation']} — " in markdown
    # Every duty the reader confirms is a task-list item: one per duty, however many owe it.
    assert len(re.findall(r"^- \[[ x]\] ", markdown, re.M)) == len(_outstanding(high_risk))
    others = {*report["public_authority_statements"]}
    for key in ("permissions", "rights", "legal_consequences", "conditional_applicability"):
        others |= {i for ids in report[key].values() for i in ids}
    assert len(re.findall(r"^- \*\*[A-Z][a-z ]+\*\* · ", markdown, re.M)) == len(others)
    # The disclaimer, every paragraph of it.
    for paragraph in report["disclaimer"].split("\n\n"):
        assert paragraph.split()[0] in markdown
    assert markdown.endswith("\n") and "\n\n\n" not in markdown


@needs_node
def test_a_rule_separates_each_row_from_the_next(high_risk):
    """Rows run to several paragraphs; without a rule the reader cannot see where one ends. One
    rule between each two rows of a list, none after its last — the next heading separates lists."""
    markdown, _ = _export(high_risk)
    duties = markdown.split("\n## Operator duties\n")[1].split("\n## Other provisions\n")[0]
    lists = re.split(r"^###? .*$", duties, flags=re.M)[1:]  # the notes, then each group of duties
    rows = [len(re.findall(r"^(#### |- \[[ x]\] )", part, re.M)) for part in lists]
    rules = [len(re.findall(r"^---$", part, re.M)) for part in lists]
    assert all(n > 1 for n in rows) and rules == [n - 1 for n in rows]

    others = markdown.split("\n## Other provisions\n")[1].split("\n## Disclaimer\n")[0]
    count = len(re.findall(r"^- \*\*", others, re.M))
    assert count > 1 and len(re.findall(r"^---$", others, re.M)) == count - 1

    # Always after a blank line: "---" straight under text would make that text a heading.
    assert "\n\n---\n\n" in markdown and not re.search(r"[^\n]\n---$", markdown, re.M)
    # The disclaimer under a heading of its own, not after a rule that would read as another row.
    assert "\n\n## Disclaimer\n\n_" in markdown


@needs_node
def test_the_verdict_reads_as_it_does_on_the_page(high_risk):
    markdown, _ = _export(high_risk)
    verdict = markdown.split("## Verdict (demo): ")[1].split("\n## ")[0]
    # The guide's card leaves Arts. 9-15 unwritten: the fixes are listed under their date.
    assert verdict.startswith("Documentation not ready for ")
    assert "Fix before that date:" in verdict
    assert re.search(r"^  1\. .+ — Not covered in your document, Art\. \d+", verdict, re.M)
    assert "a document can't show are ticked off" in verdict


@needs_node
def test_a_demo_report_says_so_in_its_title_at_its_top_and_on_its_verdict(high_risk):
    markdown, filename = _export(high_risk)
    title, _, rest = markdown.partition("\n\n")
    assert title.endswith("(demo)")
    assert rest.startswith("> **Demo report — illustrative.**")
    assert "## Verdict (demo): " in markdown
    assert "- **Model:** none — keyword heuristics (demo mode)" in markdown
    assert filename.endswith("-demo.md")


@needs_node
def test_a_live_report_names_its_model_and_carries_no_demo_mark(high_risk):
    live = {**high_risk, "demo": False, "demo_note": None, "model": "anthropic/claude-haiku-4-5"}
    markdown, filename = _export(live)
    assert "- **Model:** anthropic/claude-haiku-4-5" in markdown
    # The demo's marks are gone; the demo judge's own reasons, which this test reuses, stay.
    assert "(demo)" not in markdown and "Demo report" not in markdown
    assert "demo mode" not in markdown and "Quoted from the document by the demo" not in markdown
    assert not filename.endswith("-demo.md")


@needs_node
def test_ticks_reach_the_file_and_the_verdict_counts_them(high_risk):
    ticked = sorted(_outstanding(high_risk))[:2]
    markdown, _ = _export(high_risk, done=ticked)
    assert len(re.findall(r"^- \[x\] ", markdown, re.M)) == 2
    assert re.search(r"2 of \d+ duties a document can't show are ticked off", markdown)
    # And the file says whose ticks they are.
    assert "the review did not check it" in markdown


@needs_node
def test_the_file_is_the_whole_report_whatever_the_page_filters(high_risk):
    """A compliance record that silently dropped a role because a filter was on would read as
    complete and not be."""
    everything, _ = _export(high_risk)
    filtered, _ = _export(high_risk, hidden=["provider", "deployer"])
    assert filtered == everything
    assert "**Owed by:** Provider" in filtered


@needs_node
def test_text_from_the_document_and_the_model_stays_text(high_risk):
    hostile = json.loads(json.dumps(high_risk))
    hostile["system_name"] = "Acme <img src=x onerror=alert(1)> **Bold**"
    hostile["system_summary"] = "# Not a heading\n\n- not a list <script>alert(1)</script>"
    hostile["report"]["findings"][0]["evidence_quote"] = "[click](javascript:alert(1)) `code` &amp;"
    markdown, _ = _export(hostile)

    assert "\\<img src=x" in markdown and "<img" not in markdown.replace("\\<img", "")
    assert "\\<script>" in markdown and "\\*\\*Bold\\*\\*" in markdown
    assert "\n\\# Not a heading - not a list" in markdown  # folded, and no block opened
    assert "> \\[click\\](javascript:alert(1)) \\`code\\` &amp;amp;" in markdown


@needs_node
def test_the_file_is_named_for_the_system_and_the_review_date(high_risk):
    day = high_risk["report"]["generated_at"][:10]
    _, filename = _export(
        {**high_risk, "demo": False, "system_name": "Smart Screening / v2: ÉLITE"}
    )
    assert filename == f"ai-act-report-smart-screening-v2-elite-{day}.md"
    _, unnamed = _export({**high_risk, "demo": False, "system_name": None})
    assert unnamed == f"ai-act-report-{high_risk['report']['system_id']}-{day}.md"


@needs_node
@pytest.mark.parametrize(
    "sample, verdict",
    [
        ("vendor-video-interview-analysis", "Not allowed"),
        ("sentinel-m-military", "Not covered by the AI Act"),
        ("liftguard-assessor-not-stated", "Not enough information to classify"),
        ("aurora-7b-model-card", "No duties to verify from your document"),
    ],
)
def test_every_outcome_exports(client, sample, verdict):
    markdown, _ = _export(_demo(client, sample))
    assert f"## Verdict (demo): {verdict}\n" in markdown
