// Coverage map: one row per article and annex, one column per pipeline stage.

const COLUMNS = [
  ["Text", "Segments with a settled disposition / all segments. Hover for the normative count."],
  ["Norms", "Norms extracted from this document (after filters). Red when normative text has no norm."],
  ["Approved", "Norms approved by a reviewer / all norms."],
  ["In scope", "Norms the product must act on (product_scope = in_scope)."],
  ["Decided", "In-scope norms with an implementation mode other than missing or unresolved."],
  ["Rules", "Policy rules citing this document (filtered by role when actors are selected)."],
  ["Cases", "Document-verifiable rules with a dev golden case / all document-verifiable rules. Held-out count on hover."],
  ["Guidance", "Norms with an interpretation link + rules with guidance refs."],
];
const GUIDE_COLORS = { used: "var(--ink)", not_followed: "var(--orange)", no_effect: "var(--faint)", awaiting: "transparent" };

const ruleFilter = (r) => pass(state.actors, r.roles);
const statusOf = (num, den) => (num >= den ? "ok" : num === 0 ? "bad" : "part");

function cell(num, den, { neutral = false, title } = {}) {
  if (den === 0) return el("div", { class: "cell na", title }, el("span", { class: "v" }, "—"));
  if (neutral) return el("div", { class: "cell", title }, el("span", { class: "v" }, String(num)));
  const pct = Math.round((100 * num) / den);
  return el("div", { class: "cell " + statusOf(num, den), title },
    el("span", { class: "v" }, String(num), el("span", { class: "of" }, ` / ${den}`)),
    el("div", { class: "bar" }, el("i", { style: `width:${pct}%` })));
}

function rowStats(doc, norms, rules) {
  const seg = doc.segments, segTotal = Object.values(seg).reduce((a, b) => a + b, 0);
  const normative = seg.normative || 0, needs = seg.needs_review || 0;
  const inScope = norms.filter((n) => n.scope === "in_scope");
  const verifiable = rules.filter((r) => r.document_verifiable);
  return {
    segTotal, normative, needs, norms: norms.length,
    approved: norms.filter((n) => n.status === "approved").length,
    inScope: inScope.length,
    decided: inScope.filter((n) => !UNDECIDED.has(n.mode)).length,
    rules: rules.length, verifiable: verifiable.length,
    casesDev: verifiable.filter((r) => r.cases_dev).length,
    casesHeld: verifiable.filter((r) => r.cases_heldout).length,
    guidance: norms.filter((n) => n.guidance).length + rules.filter((r) => r.guidance).length,
  };
}
function hasGap(s, unfilteredNorms) {
  return s.needs > 0 || (s.normative > 0 && unfilteredNorms === 0) || s.approved < s.norms
      || s.decided < s.inScope || s.casesDev < s.verifiable;
}
function cells(s, unfilteredNorms) {
  return [
    cell(s.segTotal - s.needs, s.segTotal, { title: `${s.normative} normative, ${s.needs} need review` }),
    s.normative > 0 && unfilteredNorms === 0
      ? cell(0, 1, { title: "Normative text with no norm" })
      : cell(s.norms, s.norms, { neutral: true }),
    cell(s.approved, s.norms),
    cell(s.inScope, s.inScope, { neutral: true }),
    cell(s.decided, s.inScope),
    cell(s.rules, s.rules, { neutral: true }),
    cell(s.casesDev, s.verifiable, { title: `held-out: ${s.casesHeld} / ${s.verifiable}` }),
    cell(s.guidance, s.guidance, { neutral: true }),
  ];
}

// ---- summary tiles -----------------------------------------------------------------------------
function kpi(label, num, den, note) {
  const pct = den ? Math.round((100 * num) / den) : 0;
  return el("div", { class: "kpi " + (den ? statusOf(num, den) : "ok") },
    el("div", { class: "k" }, label),
    el("div", { class: "big" }, den ? `${pct}%` : "—", el("small", {}, `${num} / ${den}`)),
    el("div", { class: "s" }, note),
    el("div", { class: "bar" }, el("i", { style: `width:${pct}%` })));
}
function renderKpis(t) {
  const g = DATA.guidance.reduce((a, d) => ({ p: a.p + d.paragraphs, w: a.w + d.awaiting }), { p: 0, w: 0 });
  document.getElementById("kpis").replaceChildren(
    kpi("Text reviewed", (t.segTotal || 0) - (t.needs || 0), t.segTotal || 0, "segments with a settled disposition"),
    kpi("Norms approved", t.approved || 0, t.norms || 0, "signed off by a reviewer"),
    kpi("In-scope decided", t.decided || 0, t.inScope || 0, "implementation mode chosen"),
    kpi("Golden cases", t.casesDev || 0, t.verifiable || 0, `document-verifiable rules · held-out ${t.casesHeld || 0}`),
    kpi("Guidance read", g.p - g.w, g.p, `paragraphs decided · ${DATA.guidance.length} documents`),
  );
}

// ---- row detail --------------------------------------------------------------------------------
const normLink = (id) => el("a", { class: "mono idlink", href: hashFor({ view: "norms", id, doc: "" }) }, id);
function normTable(norms) {
  return el("table", {},
    el("tr", {}, ["Norm", "Action", "Kind", "Actors", "Scope", "Mode", "Review", "Implemented by"].map((h) => el("th", {}, h))),
    norms.map((n) => el("tr", {},
      el("td", {}, normLink(n.id)),
      el("td", {}, n.action),
      el("td", {}, n.kind),
      el("td", {}, n.actors.map((a) => el("span", { class: "tag" }, a))),
      el("td", {}, n.scope),
      el("td", {}, el("span", { class: UNDECIDED.has(n.mode) && n.scope === "in_scope" ? "tag bad" : "tag" }, n.mode)),
      el("td", {}, el("span", { class: n.status === "approved" ? "tag" : "tag part" }, n.status)),
      el("td", { class: "mono" }, n.refs.join(", ") || "—"))));
}
function ruleTable(rules) {
  return el("table", {},
    el("tr", {}, ["Rule", "Roles", "Document-verifiable", "Cases (dev / held-out)", "Guidance refs", "Effective"].map((h) => el("th", {}, h))),
    rules.map((r) => el("tr", {},
      el("td", { class: "mono" }, r.id),
      el("td", {}, r.roles.map((a) => el("span", { class: "tag" }, a))),
      el("td", {}, r.document_verifiable ? "yes" : "no"),
      el("td", {}, r.document_verifiable && !r.cases_dev
        ? el("span", { class: "tag bad" }, "none") : `${r.cases_dev} / ${r.cases_heldout}`),
      el("td", {}, String(r.guidance || "—")),
      el("td", {}, r.effective_date || "—"))));
}
function detailBody(doc, norms, rules) {
  const segs = Object.entries(doc.segments).map(([k, v]) => `${v} ${k.replace("_", " ")}`).join(" · ");
  return el("div", { class: "body" },
    el("div", { class: "segs" }, `Segments: ${segs}`,
      norms.length ? el("a", { class: "cta", href: hashFor({ view: "norms", doc: doc.key, id: "" }) }, `Open ${norms.length} norm cards →`) : null),
    el("details", { open: norms.length <= 12 ? "" : null },
      el("summary", {}, chev(), `Norms (${norms.length})`), norms.length ? normTable(norms) : el("div", { class: "muted" }, "None match the filters.")),
    el("details", { open: "" },
      el("summary", {}, chev(), `Rules (${rules.length})`), rules.length ? ruleTable(rules) : el("div", { class: "muted" }, "No rule cites this document.")));
}

// ---- map ---------------------------------------------------------------------------------------
function renderMap() {
  const q = state.q.trim().toLowerCase();
  const byDocNorms = {}, byDocAll = {}, byDocRules = {};
  for (const n of DATA.norms) {
    byDocAll[n.doc] = (byDocAll[n.doc] || 0) + 1;
    if (normFilter(n)) (byDocNorms[n.doc] ||= []).push(n);
  }
  for (const r of DATA.rules) if (ruleFilter(r)) (byDocRules[r.doc] ||= []).push(r);
  const normFiltersOn = state.actors.size || state.status.size || state.scope.size || state.kind.size;

  const rows = [], totals = {};
  for (const doc of DATA.documents) {
    if (!pass(state.source, doc.kind)) continue;
    const label = docLabel(doc.key);
    if (q && !`${label} ${doc.number} ${doc.title}`.toLowerCase().includes(q)) continue;
    const norms = byDocNorms[doc.key] || [], rules = byDocRules[doc.key] || [];
    if (normFiltersOn && !norms.length && !rules.length) continue;
    const s = rowStats(doc, norms, rules), all = byDocAll[doc.key] || 0;
    if (state.gaps && !hasGap(s, all)) continue;
    for (const [k, v] of Object.entries(s)) totals[k] = (totals[k] || 0) + v;
    const row = el("details", { class: "doc", id: doc.key },
      el("summary", { class: "grid" },
        el("div", { class: "docid mono" }, chev(), label),
        el("div", { class: "title", title: doc.title }, doc.title),
        cells(s, all)));
    row.addEventListener("toggle", () => {
      if (row.open && row.children.length === 1) row.append(detailBody(doc, norms, rules));
    });
    rows.push(row);
  }

  const head = el("div", { class: "grid head" }, el("div", {}, "Doc"), el("div", {}, "Title"),
    COLUMNS.map(([name, help]) => el("div", { title: help }, name)));
  const total = rows.length ? el("div", { class: "grid total" },
    el("div", {}, "Total"), el("div", { class: "muted" }, `${rows.length} documents`), cells(totals, 1)) : null;
  document.getElementById("map").replaceChildren(head, total || el("div", { class: "empty" }, "No documents match these filters."), ...rows);
  document.getElementById("rowcount").textContent = `${rows.length} of ${DATA.documents.length} documents`;
  renderKpis(totals);
}

function renderGuidance() {
  const kinds = ["used", "not_followed", "no_effect", "awaiting"];
  document.getElementById("gdocs").replaceChildren(...DATA.guidance.map((g) => {
    const decided = g.paragraphs - g.awaiting;
    return el("div", { class: "gdoc" },
      el("div", { class: "top" },
        el("div", {}, el("b", {}, g.document), el("div", { class: "muted" }, `${decided} of ${g.paragraphs} paragraphs decided`)),
        el("div", { class: "pct" }, `${Math.round((100 * decided) / g.paragraphs)}%`)),
      el("div", { class: "stack" }, kinds.map((k) => g[k] && GUIDE_COLORS[k] !== "transparent"
        ? el("i", { style: `width:${(100 * g[k]) / g.paragraphs}%;background:${GUIDE_COLORS[k]}`, title: `${k.replace("_", " ")}: ${g[k]}` }) : null)),
      el("div", { class: "legend" }, kinds.map((k) =>
        el("span", {}, el("i", { class: "dot", style: `background:${k === "awaiting" ? "var(--track)" : GUIDE_COLORS[k]}` }), `${k.replace("_", " ")} ${g[k] || 0}`))));
  }));
}

VIEWS.map = {
  activeFilters: () => (state.q ? 1 : 0) + (state.gaps ? 1 : 0),
  filterHead: () => el("div", { class: "frow" }, el("span", { class: "lbl" }, "Find"),
    searchBox("q", "Search article, annex or title"),
    el("button", { class: "toggle" + (state.gaps ? " on" : ""),
      onclick: () => { state.gaps = !state.gaps; render(); } }, el("span", { class: "sw" }), "Only rows with gaps")),
  render: () => { renderMap(); renderGuidance(); },
};
