// The report as a Markdown file: the "Download .md" button under the reviewed document.
//
// Written in the page rather than on the server, from the same response the page draws, because
// two things in the report exist only here: the checklist ticks, kept in this browser, and the
// verdict, which the ticks decide. The lists and the verdict come from the same functions the page
// uses (`reportRows`, `verdictOf`), so the file cannot say something the page does not.
//
// WHAT THE FILE HOLDS is the whole report, whatever the filters on screen show: every role, every
// result, every date. A compliance record that silently dropped a role's duties because a filter
// was on when it was saved would read as complete and not be. What it leaves out is the Act's own
// text — the paragraph behind every row, over a hundred of them — which is reference, not finding:
// each row keeps its citation, and the Act is one search away.
//
// A demo report says so in its title, at its top and on its verdict, as on the page.
//
// Loaded after report.js, whose helpers it uses.

// ---- escaping ------------------------------------------------------------------------------------
// Every value is text from the reviewed document, the model or the ruleset, and is written so that
// it reads as that text and nothing else: a quote holding "**" or "<script>" shows those characters
// rather than formatting the file or reaching a renderer as HTML. Whitespace is folded, as the page
// folds it.
function mdText(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim()
    .replace(/[\\`*[\]<~]/g, "\\$&")
    .replace(/&(?=#?\w+;)/g, "&amp;")
    // Emphasis by underscore needs a word boundary: snake_case stays as written.
    .replace(/(^|[^\p{L}\p{N}])_|_(?=[^\p{L}\p{N}]|$)/gu, (m) => m.replace("_", "\\_"))
    // What would open a block at the start of a line: a heading, quote, list or rule.
    .replace(/^([#>+=-])/, "\\$1")
    .replace(/^(\d+)([.)])/, "$1\\$2");
}

// Paragraphs kept, each escaped: for the few texts written in more than one.
const mdParagraphs = (value) => String(value ?? "").split(/\n\s*\n/).map(mdText).filter(Boolean);

// The rows of one list — duties, provisions, notes — each its own block with a rule between them,
// so a long row reads as finished where the rule is rather than where the next marker happens to
// be. None after the last: the next heading separates the lists. The blank line before the rule
// matters — "---" straight under a line of text would make that line a heading instead.
const mdRows = (items, render) => items.flatMap((item, i) => [...(i ? ["", "---", ""] : []), ...render(item)]);

// A block of lines under a list item, indented to stay inside it.
const indent = (lines, by = "  ") => lines.map((line) => (line ? by + line : line));

const roleNames = (roles) => (roles || []).map(human).join(", ");

// The parties and the date under a row's title, as a paragraph inside its list item; nothing where
// the row names neither.
const mdMeta = (...parts) => {
  const text = parts.filter(Boolean).join(" · ");
  return text ? [`  ${text}`, ""] : [];
};

// Provisions with their titles, the title once for a run of points under it:
// "Art. 2(13), 2(13)(a) (Scope)" rather than the title after every point.
function mdBasis(provisions) {
  const runs = [];
  for (const { citation, title } of provisions) {
    const run = runs.at(-1);
    if (run && run.title === (title || "")) run.citations.push(citation);
    else runs.push({ title: title || "", citations: [citation] });
  }
  return runs.map(({ title, citations }) => citations.join(", ") + (title ? ` (${title})` : "")).join("; ");
}

// ---- the parts of the report ---------------------------------------------------------------------
// Each returns a list of lines; blank lines separate blocks. A part with nothing to say returns [].

function mdHeader(data, exportedAt) {
  const report = data.report;
  const c = report.classification;
  const risk = c.overall_risk_class;
  const title = data.system_name ? `${mdText(data.system_name)} — AI Act compliance report` : "AI Act compliance report";
  const lines = [`# ${title}${data.demo ? " (demo)" : ""}`, ""];
  if (data.demo) {
    lines.push(`> **Demo report — illustrative.** ${mdText(data.demo_note || DEMO_NOTE)}`, "");
  }
  lines.push(...[
    `- **Classification:** ${mdText(RISK[risk] || human(risk))}`,
    `- **Act version:** Regulation (EU) 2024/1689 as of ${fmtDate(report.act_version_date)}`,
    `- **Generated:** ${fmtTime(report.generated_at)}`,
    data.model ? `- **Model:** ${mdText(data.model)}` : null,
    data.demo ? "- **Model:** none — keyword heuristics (demo mode)" : null,
    `- **Exported:** ${fmtTime(exportedAt)}`,
  ].filter(Boolean), "",
  );
  lines.push(
    "## The system",
    "",
    data.system_summary ? mdText(data.system_summary) : "_No summary could be written for this document._",
    "",
  );
  if (data.demo && data.system_summary) {
    lines.push("_Quoted from the document by the demo; a model would write this summary._", "");
  }
  lines.push(
    "## System classification",
    "",
    `**${mdText(RISK[risk] || human(risk))}** — ${mdText(c.confidence)} confidence`,
    "",
    ...(c.reasoning ? [mdText(c.reasoning), ""] : []),
  );
  if (c.triggered_by.length) {
    lines.push(...c.triggered_by.map((e) => `- **${mdText(citeSource(e.source))}**`
      + (e.reasoning ? ` — ${mdText(e.reasoning)}` : "")
      + (e.guidance?.length ? " _(rests on non-binding Commission guidance)_" : "")), "");
  }
  if (risk === "needs_review") {
    lines.push("Add the missing facts and run the review again. The guide (/guide in the report app) says what to write.", "");
  }
  return lines;
}

function mdVerdict(data, v) {
  const lines = [`## Verdict${data.demo ? " (demo)" : ""}: ${mdText(v.answer)}`, "", mdText(v.detail), ""];
  if (!v.statuses?.length) return lines;
  for (const s of v.statuses) {
    const text = s.checklist ? `${s.text}The list is under ${SECTIONS.duties[0]} below.` : s.text;
    lines.push(`- **${mdText(s.when)}:** ${mdText(text)}`);
    if (s.fixes) {
      lines.push(...s.fixes.map((f, i) => {
        const { what, why, cite } = fixParts(f, data);
        return `  ${i + 1}. ${mdText(what)} — ${mdText(why)}, ${mdText(cite)} · ${human(f.role)}`;
      }));
    }
  }
  return [...lines, ""];
}

// The notes that change how the report reads, as the page's alerts above the duties.
const mdAlerts = (data) => noteParts(data).alerts.flatMap(([, lead, text]) => [`> **${lead}.** ${mdText(text)}`, ""]);

// The notes that explain a condition on the duties, as the page's panel under the duties' heading.
function mdNotes(data) {
  const { later } = noteParts(data);
  if (!later.length) return [];
  return [`### ${NOTES_HEAD[0]} · ${later.length}`, "", `_${NOTES_HEAD[1]}_`, "",
    ...mdRows(later, ([title, hint, text]) => [`#### ${title}`, "", `_${hint}_`, "", mdText(text), ""]), ""];
}

// "**Label:** value" as a paragraph of its own, or nothing where there is no value.
const mdField = (label, value) => (value ? [`**${label}:** ${mdText(value)}`, ""] : []);

function mdFinding(f, data) {
  const rule = data.rules[f.rule_id];
  const verdict = VERDICT[f.verdict] || human(f.verdict);
  const cite = rule?.citation || citeSource(f.citation);
  const lines = [
    `#### ${verdict} — ${mdText(cite)} — ${mdText(rule?.action || rule?.requirement || f.rule_id)}`, "",
    `**Owed by:** ${roleNames([f.role])} · **Applies:** ${appliesFromText(f.applies_from ? "future" : "now", f.applies_from, rule?.deadline)}`, "",
    ...mdField("In plain words", rule?.explanation),
    ...mdField("Finding", findingText(f)),
    "**Evidence:**", "",
    f.evidence_quote ? `> ${mdText(f.evidence_quote)}` : "_No passage in the document was cited._", "",
  ];
  if (f.criteria.length) {
    lines.push("**Criteria:**", "");
    for (const c of f.criteria) {
      const criterion = rule?.criteria?.[c.norm_id];
      const title = criterion ? `**${mdText(criterion.citation)}** — ${mdText(criterion.action)}` : mdText(c.norm_id);
      lines.push(`- ${VERDICT[c.verdict] || human(c.verdict)} · ${title}${c.mandatory ? "" : " (not judged)"}`);
      if (c.mandatory && c.verdict !== "pass" && c.reasoning) lines.push(`  - ${mdText(c.reasoning)}`);
    }
    lines.push("");
  }
  return [
    ...lines,
    ...mdField("Applies to", rule?.activation_condition),
    ...mdField("Confidence", human(f.confidence)),
    ...(f.guidance.length ? mdField("Guidance", "Reached with non-binding Commission guidance in view.") : []),
    ...mdField("Date note", rule?.effective_date_note),
  ];
}

// A duty the reader confirms, as a task-list item: ticked where the reader ticked it on the page.
// `when` is "now", "future" or "unknown", as on the page, and `date` the day it starts.
function mdOutstanding({ kind, id, roles }, data, when, date, ticked) {
  const row = kind === "cond" ? data.norms[id] : data.rules[id];
  const cite = kind === "cond" ? normCites(row)[0] : row?.citation;
  const body = kind === "cond" ? [
    ...mdField("In plain words", row?.explanation),
    ...(row?.conditions ? mdField("Only if", unwrap(row.conditions)) : []),
    ...(row?.exceptions ? mdField("Except", unwrap(row.exceptions)) : []),
  ] : [
    ...mdField("In plain words", row?.explanation),
    ...mdField("What to check", row?.evidence_expected),
    ...mdField("Applies to", row?.activation_condition),
    ...mdField("Date note", row?.effective_date_note),
  ];
  return [
    `- [${ticked.has(id) ? "x" : " "}] **${mdText(cite || "")}** — ${mdText(row?.action || row?.requirement || id)}`, "",
    ...mdMeta(roleNames(roles), appliesFromText(when, date, kind === "rule" ? row?.deadline : null)),
    ...indent(body),
  ];
}

// A provision listed for information: a permission, right, legal effect or authority's power.
// Undated, as on the page.
function mdProvision({ id, roles }, data) {
  const norm = data.norms[id];
  const basis = norm?.basis?.length ? mdBasis(norm.basis) : normCites(norm).join(", ");
  return [
    `- **${NORM_KIND[norm?.kind] || human(norm?.kind || "norm")}** · **${mdText(normCites(norm)[0] || "")}** — ${mdText(norm?.action || id)}`,
    "", ...mdMeta(roleNames(roles)),
    ...indent([
      ...mdField("In plain words", norm?.explanation),
      ...(norm?.conditions ? mdField("Only if", unwrap(norm.conditions)) : []),
      ...(norm?.exceptions ? mdField("Except", unwrap(norm.exceptions)) : []),
      ...mdField("Basis", basis),
    ]),
  ];
}

// ---- the whole report ----------------------------------------------------------------------------

// The Markdown for one review response. `done` is the ids the reader has ticked off; `exportedAt`
// the moment of export. Pure: reads nothing from the page, so the same input gives the same file.
function reportMarkdown(data, { done = new Set(), exportedAt = new Date() } = {}) {
  const report = data.report;
  const today = report.generated_at.slice(0, 10);
  const useCase = report.classification.use_cases[0]?.use_case_id;
  const ruleDate = (id) => data.rules[id]?.application_dates?.[useCase] ?? null;
  const normDate = (id) => data.norms[id]?.application_dates?.[useCase] ?? null;
  const isFuture = (d) => d !== null && d > today;

  const rows = reportRows(report, data);
  const verdict = verdictOf(report, data, ruleDate, normDate, isFuture, new Set(), done);
  const lines = [...mdHeader(data, exportedAt), ...mdVerdict(data, verdict), ...mdAlerts(data)];

  const groupHead = ([title, hint], count) => [`### ${title} · ${count}`, "", ...(hint ? [`_${hint}_`, ""] : [])];
  const anyDuty = rows.checked.length || rows.outstanding.length || rows.unresolved.length;
  if (anyDuty) {
    lines.push(`## ${SECTIONS.duties[0]}`, "", `_${SECTIONS.duties[1]}_`, "", ...mdNotes(data));
    if (rows.checked.length) {
      lines.push(...groupHead(GROUPS.checked, rows.checked.length), ...mdRows(rows.checked, (f) => mdFinding(f, data)));
    }
    if (rows.outstanding.length) {
      lines.push(...groupHead(GROUPS.outstanding, rows.outstanding.length),
        "_A ticked box ([x]) is one the reader ticked off in the report app; the review did not check it._", "",
        ...mdRows(rows.outstanding, (row) => {
          const date = row.kind === "cond" ? normDate(row.id) : ruleDate(row.id);
          return mdOutstanding(row, data, isFuture(date) ? "future" : "now", date, done);
        }));
    }
    if (rows.unresolved.length) {
      lines.push(...groupHead(GROUPS.unresolved, rows.unresolved.length),
        ...mdRows(rows.unresolved, (row) => mdOutstanding(row, data, "unknown", null, done)));
    }
  }
  if (rows.others.length) {
    lines.push(`## ${SECTIONS.others[0]}`, "", `_${SECTIONS.others[1]}_`, "",
      ...mdRows(rows.others, (row) => mdProvision(row, data)));
  }
  // A heading, not a rule: with rules between rows, a rule here would read as one more row.
  lines.push("## Disclaimer", "", ...mdParagraphs(report.disclaimer).flatMap((p) => [`_${p}_`, ""]));
  // One blank line between blocks, and one newline at the end.
  return `${lines.join("\n").replace(/\n{3,}/g, "\n\n").trim()}\n`;
}

// "5 Nov 2026, 09:36 CET": a moment a reader elsewhere can place, which "05/11/2026" is not.
const fmtTime = (value) => new Date(value).toLocaleString("en-GB", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short",
});

// The file's name: the system, the date of the review, and whether it was a demo.
function markdownFilename(data) {
  const slug = String(data.system_name || data.report.system_id || "system").normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60)
    .replace(/-+$/, "") || "system";
  return `ai-act-report-${slug}-${data.report.generated_at.slice(0, 10)}${data.demo ? "-demo" : ""}.md`;
}

// Save the report on screen as a .md file.
function downloadMarkdown() {
  if (!last?.response) return;
  const data = last.response;
  const blob = new Blob([reportMarkdown(data, { done: doneSet() })], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: markdownFilename(data) });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
