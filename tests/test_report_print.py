"""Printing the report: the page's "Print report" button.

The button calls the browser's print; what goes on paper is set up on the browser's own print
events (so Ctrl/Cmd+P prints the same) and laid out by report.css's print rules. Paper holds what
the Markdown file holds — the whole report whatever the filters show, every row open, the checklist
as ticked — so the lifecycle is pinned by RUNNING the page's scripts in Node with a stub DOM, as
the Markdown export is; the button and the paper rules are pinned on the files the server serves.
Without Node on the machine the lifecycle tests skip.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aiact.report_app.app import app

STATIC = Path(__file__).resolve().parents[1] / "src" / "aiact" / "report_app" / "static"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="printing is set up in the page; needs Node")

# Loads report.js and report-md.js as the page does, with a report on screen holding three rows
# (one already open) and a reader's filters in local storage: the provider hidden, and only the
# duties in force now. Fires the two print events in turn and reports the page at each step.
_RUNNER = r"""
const fs = require("fs"), vm = require("vm");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const node = () => ({ setAttribute() {}, append() {}, addEventListener() {}, style: {}, dataset: {},
                      classList: { toggle() {} }, querySelectorAll: () => [] });
const rows = [{ open: false }, { open: true }, { open: false }];
const printedAt = { textContent: "" };
const report = { ...node(), hidden: input.reportHidden,
  querySelectorAll: (sel) => (sel === "details.item:not([open])" ? rows.filter((r) => !r.open)
    : sel === ".printed-at" ? [printedAt] : []),
  querySelector: () => null };
const storage = { "aiact-review:hidden-roles": JSON.stringify(["provider"]),
                  "aiact-review:when": JSON.stringify("now") };
const listeners = {};
const ctx = {
  document: { createElement: node, getElementById: (id) => (id === "report" ? report : node()),
              addEventListener() {}, documentElement: { dataset: {} }, body: node(),
              title: "AI Act Compliance Review" },
  window: { addEventListener: (type, fn) => { listeners[type] = fn; } },
  fetch: () => Promise.resolve({ ok: false, json: () => ({}) }),
  localStorage: { getItem: (k) => storage[k] ?? null, setItem() {}, removeItem() {} },
  queueMicrotask, setTimeout, console,
};
vm.createContext(ctx);
for (const file of ["report.js", "report-md.js"]) {
  vm.runInContext(fs.readFileSync(input.static + "/" + file, "utf8"), ctx, { filename: file });
}
ctx.input = input;
vm.runInContext(`last = { response: input.response, document: "" };`, ctx);
const state = () => vm.runInContext(`({
  printing,
  hiddenRoles: [...hiddenOf("roles")],
  title: document.title,
})`, ctx);
const out = { before: { ...state(), open: rows.map((r) => r.open) } };
vm.runInContext("beforePrint()", ctx);
out.during = { ...state(), open: rows.map((r) => r.open), printedAt: printedAt.textContent };
vm.runInContext("afterPrint()", ctx);
out.after = { ...state(), open: rows.map((r) => r.open) };
process.stdout.write(JSON.stringify(out));
"""

# The least of a response the print reads: the name and date its PDF is called after.
_RESPONSE = {
    "system_name": "Smart Screening",
    "demo": True,
    "report": {"generated_at": "2026-11-06T10:00:00"},
}


def _print(*, report_hidden: bool = False) -> dict:
    assert NODE is not None
    payload = {"static": str(STATIC), "response": _RESPONSE, "reportHidden": report_hidden}
    result = subprocess.run(
        [NODE, "-e", _RUNNER], input=json.dumps(payload), capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


# ---- the button ----------------------------------------------------------------------------------


def test_print_sits_beside_download_at_the_reports_head_and_end(client):
    """Where the download is, and before it: the download stays the rightmost pill, on the edge
    the floating one docks to. Never under the document, where it would act on the input."""
    page = client.get("/").text
    form = page.split('<form class="card input"')[1].split("</form>")[0]
    assert "Print" not in form and "print" not in form

    script = client.get("/static/report.js").text
    actions = 'el("div", { class: "report-actions" }, printButton(), exportButton())'
    header = script.split("function header(data)")[1].split("\n}\n")[0]
    assert actions in header
    render = script.split("function render(data)")[1].split("\n}\n")[0]
    assert actions in render
    assert render.index('class: "disclaimer"') < render.index('"card report-end"')
    # A short label that keeps its full name, and its own class: the floating row is placed by the
    # download buttons alone.
    assert 'class: "print-report"' in script
    assert '"aria-label": "Print report", onclick: () => window.print() }, "Print")' in script
    assert 'querySelectorAll(".export-md")' in script
    # The same pair floats while reading, Print first.
    assert 'aria-label="Print report"' in page and ">Print</button>" in page
    assert '$("print-float").addEventListener("click", () => window.print())' in script


def test_the_browsers_own_print_is_set_up_the_same_way(client):
    """Set up on the print events, not in the button: Ctrl/Cmd+P prints the same report."""
    script = client.get("/static/report.js").text
    assert 'window.addEventListener("beforeprint", beforePrint)' in script
    assert 'window.addEventListener("afterprint", afterPrint)' in script


# ---- what goes on paper --------------------------------------------------------------------------


@needs_node
def test_printing_lifts_the_filters_opens_every_row_and_puts_the_page_back():
    out = _print()
    # The reader's page: the provider filtered out, one row open.
    assert out["before"] == {
        "printing": False,
        "hiddenRoles": ["provider"],
        "title": "AI Act Compliance Review",
        "open": [False, True, False],
    }
    # On paper: nothing filtered out — the verdict follows the same set — every row open, the
    # moment of printing stamped, and the PDF named as the Markdown file is.
    during = out["during"]
    assert during["printing"] is True and during["hiddenRoles"] == []
    assert during["open"] == [True, True, True]
    assert during["printedAt"]
    assert during["title"] == "ai-act-report-smart-screening-2026-11-06-demo"
    # Afterwards, exactly as the reader left it: the row they had open stays open.
    assert out["after"] == out["before"]


@needs_node
def test_the_input_prints_as_it_is():
    """No report on screen — the editor is open — and nothing is changed for the print."""
    out = _print(report_hidden=True)
    assert out["during"]["printing"] is False
    assert out["during"]["hiddenRoles"] == ["provider"]
    assert out["during"]["open"] == [False, True, False]
    assert out["after"] == out["before"]


def test_paper_holds_the_report_alone_in_the_light_theme(client):
    styles = client.get("/static/report.css").text
    paper = styles.split("@media print {")[1]
    # The app around the report, and every button, stay on screen.
    for hidden in (
        ".topbar",
        ".modebar",
        ".floatbar",
        '#form[data-mode="view"]',
        ".report-actions",
        ".report-end",
        ".provisions > .filters",
    ):
        assert hidden in paper.split("{ display: none !important; }")[0]
    # The Act's text is left out, as in the Markdown file.
    assert ".act-says, details.ref > .law { display: none !important; }" in paper
    # Ink on white whatever the theme: the light tokens over both dark selectors.
    assert ':root, :root[data-theme="dark"], :root:not([data-theme="light"]) {' in paper
    # Block, not grid, for what runs across pages: a grid row does not grow when its content is
    # pushed onto the next page, and the disclaimer was drawn over the last provisions.
    assert "main, #report, .system, .verdict, .compliance, .item-body { display: block; }" in paper
    # The page number alone in the margins: a generated box at the top and at the foot stops
    # Chromium drawing its own header and footer (date, title, URL) there.
    page_rule = paper.split("@page {")[1].split("\n  }")[0]
    assert '@top-center { content: ""; }' in page_rule
    assert "@bottom-center { content: counter(page);" in page_rule
    # Only on paper: the report's title and the moment it was printed.
    assert "@media not print { .print-only { display: none !important; } }" in styles
    script = client.get("/static/report.js").text
    assert 'class: "print-only print-title"' in script and 'class: "printed-at"' in script
