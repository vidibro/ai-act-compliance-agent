// The report page: send a document to /api/review and draw the report it returns.
// Every value from the report is set as text, never as HTML: quotes and reasoning come from the
// reviewed document and the model.

const el = (tag, attrs = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid !== null && kid !== undefined && kid !== false) node.append(kid);
  return node;
};
const $ = (id) => document.getElementById(id);
const human = (v) => (v ? String(v).replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase()) : "");
const fmtDate = (d) => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

const RISK = {
  prohibited: "Prohibited practice",
  high_risk: "High risk",
  not_high_risk: "Not high risk",
  minimal: "Minimal risk",
  gpai_model: "General-purpose AI model",
  out_of_scope: "Outside the AI Act",
  needs_review: "Needs review",
};
const VERDICT = { pass: "Pass", gap: "Gap", inadequate: "Inadequate", needs_review: "Needs review", not_applicable: "N/a" };
const ROLE_ORDER = ["provider", "initial_provider", "prospective_provider", "sandbox_participant", "deployer",
                    "importer", "distributor", "authorised_representative", "gpai_provider"];
const NORM_GROUPS = [
  ["permissions", "Permitted routes"],
  ["rights", "Rights"],
  ["legal_consequences", "Legal effects"],
  ["conditional_applicability", "Scope limits"],
];

function citeSource(s) {
  if (!s) return "";
  if (s.article) return `Art. ${s.article}${s.paragraph ? `(${s.paragraph})` : ""}${s.point ? `(${s.point})` : ""}`;
  if (s.annex) return `Annex ${s.annex}${s.annex_point ? ` ${s.annex_point}` : ""}`;
  return s.instrument || "";
}

// ---- running a review ------------------------------------------------------------------------
let timer = null;

function setBusy(busy) {
  $("run").disabled = busy;
  const status = $("status");
  clearInterval(timer);
  if (!busy) { status.hidden = true; return; }
  const started = Date.now();
  const text = el("span", {}, "Reviewing… 0s");
  status.replaceChildren(el("span", { class: "spinner" }), text,
    el("span", { class: "muted small" }, "Classifying the system, then checking each obligation."));
  status.hidden = false;
  timer = setInterval(() => { text.textContent = `Reviewing… ${Math.round((Date.now() - started) / 1000)}s`; }, 1000);
}

function showError(message) {
  $("error").hidden = !message;
  $("error").textContent = message || "";
}

async function runReview(event) {
  event.preventDefault();
  showError("");
  setBusy(true);
  try {
    const response = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document: $("document").value, system_id: $("system-id").value.trim() || "system" }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail;
      throw new Error(detail || `The review failed (${response.status}).`);
    }
    render(body);
    $("report").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err.message);
  } finally {
    setBusy(false);
  }
}

// ---- the report ------------------------------------------------------------------------------
function render(data) {
  const report = data.report;
  const today = report.generated_at.slice(0, 10);
  const useCase = report.classification.use_cases[0]?.use_case_id;
  const ruleDate = (id) => data.rules[id]?.application_dates?.[useCase] ?? null;
  const isFuture = (d) => d !== null && d > today;

  const [first, later] = notes(data);
  $("report").replaceChildren(
    header(report),
    ...first,
    upcomingBanner(report, data, ruleDate, isFuture),
    tiles(report, data, ruleDate, isFuture),
    ...later,
    ...roles(report, data, ruleDate, isFuture),
    publicAuthority(report, data),
    el("footer", { class: "disclaimer" }, report.disclaimer),
  );
}

function header(report) {
  const c = report.classification;
  const risk = c.overall_risk_class;
  return el("section", { class: `card verdict ${risk}` },
    el("div", { class: "top" },
      el("span", { class: "risk" }, RISK[risk] || human(risk)),
      el("span", { class: "tag soft" }, `${c.confidence} confidence`)),
    el("p", { class: "reasoning" }, c.reasoning),
    c.triggered_by.length ? el("ul", { class: "basis" }, c.triggered_by.map((e) =>
      el("li", {}, el("b", {}, citeSource(e.source)), e.reasoning ? ` — ${e.reasoning}` : "",
        e.guidance?.length ? el("span", { class: "muted" }, " (rests on non-binding Commission guidance)") : null))) : null,
    el("div", { class: "meta" },
      el("span", {}, "System ", el("b", {}, report.system_id)),
      el("span", {}, "Act version ", el("b", {}, fmtDate(report.act_version_date))),
      el("span", {}, "Generated ", el("b", {}, new Date(report.generated_at).toLocaleString("en-GB")))),
  );
}

function note(kind, lead, text) {
  return el("section", { class: `note ${kind}` }, el("div", { class: "lead" }, lead), el("p", {}, text));
}

// Notes that change how the report reads go above the counts; context goes below them.
function notes(data) {
  const report = data.report;
  const out = [];
  const later = [];
  if (report.scope_note) {
    const stop = report.classification.overall_risk_class === "prohibited";
    out.push(note(stop ? "stop" : "warn", stop ? "Prohibited" : "What was not checked", report.scope_note));
  }
  const n = data.notes;
  if (n.provider_reallocation) out.push(note("warn", "Who is the provider", n.provider_reallocation));
  if (n.deployer_type) later.push(note("", "Deployer", n.deployer_type));
  if (n.real_world_testing) later.push(note("", "Real-world testing", n.real_world_testing));
  if (n.chapter_v_gate) later.push(note("", "General-purpose AI model", n.chapter_v_gate));
  // Art. 111 is relief the report cannot grant: it turns on the market placement date, which no
  // document states. Shown as advice, never as an exemption, and it changes no count.
  if (n.legacy_system) later.push(note("", "If the system is already on the market — check with your adviser", n.legacy_system));
  return [out, later];
}

function upcomingBanner(report, data, ruleDate, isFuture) {
  const dates = Object.entries(report.summary.upcoming);
  if (!dates.length) return null;
  const confirm = [...new Set(Object.values(report.not_document_verifiable).flat())]
    .filter((id) => isFuture(ruleDate(id))).length;
  const parts = dates.map(([d, s]) => `${plural(s.total_applicable, "obligation")} become required on ${fmtDate(d)}`);
  return note("warn", "Upcoming obligations",
    `${parts.join("; ")}${confirm ? `, plus ${confirm} to confirm separately` : ""}. ` +
    "They are checked now so you can prepare. A gap against one of them is not a breach today.");
}

function tile(cls, label, s) {
  return el("div", { class: `card tile ${cls}` },
    el("div", { class: "k" }, label),
    el("div", { class: "big" }, s.total_applicable, el("small", {}, "checked")),
    el("div", { class: "s" },
      el("span", {}, el("b", { class: s.gaps ? "red" : "" }, s.gaps), " gap"),
      el("span", {}, el("b", {}, s.inadequate), " inadequate"),
      el("span", {}, el("b", {}, s.needs_review), " needs review"),
      el("span", {}, el("b", {}, s.passed), " pass")));
}

function tiles(report, data, ruleDate, isFuture) {
  const s = report.summary;
  const outstanding = [...new Set(Object.values(report.not_document_verifiable).flat())];
  if (!s.total_applicable && !Object.keys(s.upcoming).length && !outstanding.length) return null;
  const confirmNow = outstanding.filter((id) => !isFuture(ruleDate(id))).length;
  return el("section", { class: "tiles" },
    tile("", "In force now", s),
    Object.entries(s.upcoming).map(([d, u]) => tile("future", `Required from ${fmtDate(d)}`, u)),
    el("div", { class: "card tile" },
      el("div", { class: "k" }, "To confirm separately"),
      el("div", { class: "big" }, outstanding.length, el("small", {}, "obligations")),
      el("div", { class: "s" }, `${confirmNow} in force now; a technical file cannot show them, so none counts as a pass`)));
}

// ---- one section per duty-holder -------------------------------------------------------------
function roles(report, data, ruleDate, isFuture) {
  const present = new Set([
    ...report.findings.map((f) => f.role),
    ...Object.keys(report.not_document_verifiable),
    ...report.timing_not_active.map((t) => t.role),
    ...NORM_GROUPS.flatMap(([key]) => Object.keys(report[key])),
  ]);
  const order = [...ROLE_ORDER.filter((r) => present.has(r)), ...[...present].filter((r) => !ROLE_ORDER.includes(r))];
  return order.map((role) => roleSection(role, report, data, ruleDate, isFuture));
}

function roleSection(role, report, data, ruleDate, isFuture) {
  const findings = report.findings.filter((f) => f.role === role);
  const now = findings.filter((f) => !f.applies_from);
  const byDate = groupBy(findings.filter((f) => f.applies_from), (f) => f.applies_from);
  const outstanding = report.not_document_verifiable[role] || [];
  const confirmNow = outstanding.filter((id) => !isFuture(ruleDate(id)));
  const confirmLater = outstanding.filter((id) => isFuture(ruleDate(id)));
  const unresolved = report.timing_not_active.filter((t) => t.role === role);
  const counts = report.summary.per_role?.[role];

  return el("section", { class: "card role" },
    el("h2", {}, human(role),
      counts ? el("span", { class: "n" }, `${counts.gaps} gap${counts.gaps === 1 ? "" : "s"} in force`) : null),
    now.length ? group("", "Checked — in force now", null, now.map((f) => findingItem(f, data))) : null,
    Object.entries(byDate).sort().map(([d, list]) =>
      group("future", `Checked — required from ${fmtDate(d)}`, "Not yet in force. A gap here is something to fix before this date.",
        list.map((f) => findingItem(f, data)))),
    confirmNow.length ? group("", "Confirm separately — in force now", "A technical file cannot show these. Confirm each one yourself.",
      confirmNow.map((id) => outstandingItem(id, data, ruleDate(id), false))) : null,
    confirmLater.length ? group("future", "Confirm separately — required later", "Not yet in force. A technical file cannot show these.",
      confirmLater.map((id) => outstandingItem(id, data, ruleDate(id), true))) : null,
    unresolved.length ? group("", "Date depends on the Art. 6 route", "Not checked: when these apply turns on how the system is classified.",
      unresolved.map((t) => outstandingItem(t.rule_id, data, null, false))) : null,
    NORM_GROUPS.map(([key, label]) => (report[key][role]?.length
      ? group("", label, null, report[key][role].map((id) => normItem(id, data))) : null)),
  );
}

function groupBy(list, key) {
  return list.reduce((acc, item) => { (acc[key(item)] ||= []).push(item); return acc; }, {});
}

function group(cls, title, hint, items) {
  return el("div", { class: `group ${cls}`.trim() },
    el("h3", {}, title, el("span", { class: "muted" }, `· ${items.length}`)),
    hint ? el("p", { class: "hint" }, hint) : null,
    items);
}

function kv(label, ...value) {
  return el("div", { class: "kv" }, el("div", { class: "l" }, label), el("div", {}, value));
}

function findingItem(f, data) {
  const rule = data.rules[f.rule_id];
  return el("details", { class: "item" },
    el("summary", {},
      el("span", {}, el("span", { class: `tag ${f.verdict}` }, VERDICT[f.verdict] || human(f.verdict))),
      el("span", { class: "cite" }, rule?.citation || citeSource(f.citation)),
      el("span", { class: "oneline" }, rule?.requirement || f.rule_id),
      el("span", { class: "when" }, f.applies_from ? el("span", { class: "tag date" }, `from ${fmtDate(f.applies_from)}`) : null)),
    el("div", { class: "item-body" },
      kv("Finding", f.reasoning),
      kv("Evidence", f.evidence_quote ? el("blockquote", {}, f.evidence_quote)
        : el("span", { class: "muted" }, "No passage in the document was cited.")),
      f.criteria.length ? kv("Criteria", el("ul", { class: "criteria" }, f.criteria.map((c) =>
        el("li", {}, el("span", {}, el("span", { class: `tag ${c.verdict}` }, VERDICT[c.verdict] || human(c.verdict))),
          el("span", {}, el("span", { class: "mono" }, c.norm_id), c.mandatory ? "" : " (not judged)",
            c.mandatory && c.verdict !== "pass" ? el("div", { class: "muted" }, c.reasoning) : null))))) : null,
      rule?.activation_condition ? kv("Applies to", rule.activation_condition) : null,
      kv("Confidence", human(f.confidence)),
      f.guidance.length ? kv("Guidance", "Reached with non-binding Commission guidance in view.") : null,
      rule?.effective_date_note ? kv("Date note", rule.effective_date_note) : null,
      kv("Rule", el("span", { class: "mono" }, f.rule_id))),
  );
}

function outstandingItem(id, data, date, future) {
  const rule = data.rules[id];
  return el("details", { class: "item" },
    el("summary", {},
      el("span", {}, el("span", { class: "tag needs_review" }, "Confirm")),
      el("span", { class: "cite" }, rule?.citation || ""),
      el("span", { class: "oneline" }, rule?.requirement || id),
      el("span", { class: "when" }, future ? el("span", { class: "tag date" }, `from ${fmtDate(date)}`) : null)),
    el("div", { class: "item-body" },
      rule ? kv("Confirm", rule.evidence_expected) : null,
      rule ? kv("Requirement", rule.requirement) : null,
      rule?.activation_condition ? kv("Applies to", rule.activation_condition) : null,
      rule?.effective_date_note ? kv("Date note", rule.effective_date_note) : null,
      kv("Rule", el("span", { class: "mono" }, id))),
  );
}

function normItem(id, data) {
  const norm = data.norms[id];
  return el("details", { class: "item" },
    el("summary", {},
      el("span", {}, el("span", { class: "tag soft" }, human(norm?.kind || "norm"))),
      el("span", { class: "cite" }, norm?.source_spans?.[0]?.replace(/^AIA-TEXT-/, "") || ""),
      el("span", { class: "oneline" }, norm?.action || id),
      el("span", {})),
    el("div", { class: "item-body" },
      norm ? kv("Means", norm.action) : null,
      norm?.conditions ? kv("If", norm.conditions) : null,
      norm?.exceptions ? kv("Except", norm.exceptions) : null,
      norm ? kv("Basis", el("span", { class: "mono" }, norm.source_spans.join(", "))) : null),
  );
}

function publicAuthority(report, data) {
  const ids = report.public_authority_statements;
  if (!ids.length) return null;
  return el("section", { class: "card role" },
    el("h2", {}, "Public authorities", el("span", { class: "n" }, "not your obligations; listed for context")),
    group("", "Duties and powers relevant to this system", null, ids.map((id) => normItem(id, data))));
}

// ---- page setup ------------------------------------------------------------------------------
function setTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try { theme === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", theme); } catch {}
  for (const b of document.querySelectorAll("#theme button")) b.classList.toggle("on", b.dataset.theme === theme);
}

function countChars() {
  const n = $("document").value.length;
  $("chars").textContent = n ? `${n.toLocaleString("en-GB")} characters` : "";
}

window.addEventListener("DOMContentLoaded", () => {
  for (const b of document.querySelectorAll("#theme button")) b.addEventListener("click", () => setTheme(b.dataset.theme));
  setTheme(document.documentElement.dataset.theme || "auto");
  $("form").addEventListener("submit", runReview);
  $("document").addEventListener("input", countChars);
  $("file").addEventListener("change", async () => {
    const file = $("file").files[0];
    if (!file) return;
    $("document").value = await file.text();
    $("system-id").value = file.name.replace(/\.[^.]+$/, "");
    countChars();
  });
});
