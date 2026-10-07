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
// Short enough to fit the tag column.
const NORM_KIND = { permission: "Permitted", entitlement: "Right", legal_consequence: "Effect", power: "Power",
                    obligation: "Duty", prohibition: "Ban", recommendation: "Advice", applicability: "Scope",
                    definition: "Definition" };
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

// ---- keeping work across reloads ---------------------------------------------------------------
// The last report (with the document it reviewed) and the input draft live in this browser's local
// storage, so a reload or a closed tab does not lose them. Storage can be full or blocked; the page
// works without it.
const STORE = { last: "aiact-review:last", draft: "aiact-review:draft" };
const OLD_REPORT_KEY = "aiact-review:last-report"; // a bare response, saved by an earlier version
let maxChars = null; // the server's document limit
let last = null; // { response, document } of the report on screen

function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

function restore(key) {
  try { return JSON.parse(localStorage.getItem(key) || "null"); } catch { return null; }
}

function saveDraft() {
  store(STORE.draft, { document: $("document").value, editing: $("form").dataset.mode === "edit" });
}

// ---- edit or view ----------------------------------------------------------------------------
// "edit": the document can be changed and run; the last report is hidden.
// "view": the report is shown under the read-only document it reviewed.
function setMode(mode) {
  $("form").dataset.mode = mode;
  $("document").readOnly = mode === "view";
  $("form-title").textContent = mode === "view" ? "Reviewed document" : "Review a system";
  $("cancel").hidden = !last;
  $("report").hidden = mode === "edit";
  saveDraft();
}

// ---- running a review ------------------------------------------------------------------------
let timer = null;

function setBusy(busy) {
  $("run").disabled = busy;
  $("document").readOnly = busy || $("form").dataset.mode === "view";
  $("cancel").disabled = busy;
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
      body: JSON.stringify({ document: $("document").value }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail;
      throw new Error(detail || `The review failed (${response.status}).`);
    }
    last = { response: body, document: $("document").value };
    store(STORE.last, last);
    render(body);
    setMode("view");
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
  const duties = roles(report, data, ruleDate, isFuture);
  // A section with nothing to show is null; replaceChildren would print it as text.
  $("report").replaceChildren(...[
    ...header(data),
    ...first,
    duties.length ? el("div", { class: "section-head" },
      el("h2", {}, "Obligations"),
      el("p", { class: "muted" }, "What the AI Act requires for this system, grouped by who owes it, and whether your document shows it."),
      roleFilter(duties)) : null,
    upcomingBanner(report, data, ruleDate, isFuture),
    tiles(report, data, ruleDate, isFuture),
    ...later,
    ...duties,
    publicAuthority(report, data),
    el("footer", { class: "disclaimer" }, report.disclaimer),
  ].filter(Boolean));
}

// What the system is first, then how it is classified.
function header(data) {
  const report = data.report;
  const c = report.classification;
  const risk = c.overall_risk_class;
  const system = el("section", { class: "card system" },
    data.system_name
      ? el("h2", {}, el("span", { class: "eyebrow" }, "The system"), data.system_name)
      : el("div", { class: "eyebrow" }, "The system"),
    data.system_summary
      ? el("p", { class: "summary" }, data.system_summary)
      : el("p", { class: "muted" }, "No summary could be written for this document."),
    el("div", { class: "meta" },
      el("span", {}, "Act version ", el("b", {}, fmtDate(report.act_version_date))),
      el("span", {}, "Generated ", el("b", {}, new Date(report.generated_at).toLocaleString("en-GB")))),
  );
  const classification = el("section", { class: `card verdict ${risk}` },
    el("div", { class: "eyebrow" }, "System classification"),
    el("div", { class: "top" },
      el("span", { class: "risk" }, RISK[risk] || human(risk)),
      el("span", { class: "tag soft" }, `${c.confidence} confidence`)),
    el("p", { class: "reasoning" }, c.reasoning),
    c.triggered_by.length ? el("ul", { class: "basis" }, c.triggered_by.map((e) =>
      el("li", {}, el("b", {}, citeSource(e.source)), e.reasoning ? ` — ${e.reasoning}` : "",
        e.guidance?.length ? el("span", { class: "muted" }, " (rests on non-binding Commission guidance)") : null))) : null,
  );
  return [system, classification];
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
    `${parts.join("; ")}${confirm ? `, plus ${confirm} to check yourself` : ""}. ` +
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
    s.total_applicable ? tile("", "In force now", s) : null, // nothing checked: no tile of zeros
    Object.entries(s.upcoming).map(([d, u]) => tile("future", `Required from ${fmtDate(d)}`, u)),
    outstanding.length ? el("div", { class: "card tile" },
      el("div", { class: "k" }, "Check yourself"),
      el("div", { class: "big" }, outstanding.length, el("small", {}, outstanding.length === 1 ? "obligation" : "obligations")),
      el("div", { class: "s" }, confirmText(outstanding.length, confirmNow))) : null);
}

// Obligations a document cannot show (a quality system, a registration): the review lists them
// and the reader checks them.
function confirmText(total, now) {
  const later = total - now;
  const when = !later ? (total === 1 ? "Already applies." : "All already apply.")
    : !now ? (total === 1 ? "Applies later." : "All apply later.")
    : `${now} already ${now === 1 ? "applies" : "apply"}, ${later} later.`;
  return `${when} A document can't show ${total === 1 ? "it" : "these"}, so the review doesn't check ${total === 1 ? "it" : "them"}.`;
}

// ---- one section per duty-holder -------------------------------------------------------------
// An unjudged item several parties owe (the Art. 5 ban, Art. 4 AI literacy, a fine) is listed
// once, in a section titled with exactly those parties. Findings stay with their role: each is its
// own verdict.
function roles(report, data, ruleDate, isFuture) {
  const present = new Set([
    ...report.findings.map((f) => f.role),
    ...Object.keys(report.not_document_verifiable),
    ...report.timing_not_active.map((t) => t.role),
    ...NORM_GROUPS.flatMap(([key]) => Object.keys(report[key])),
  ]);
  const order = [...ROLE_ORDER.filter((r) => present.has(r)), ...[...present].filter((r) => !ROLE_ORDER.includes(r))];

  const owners = {};
  const items = (role) => [
    ...(report.not_document_verifiable[role] || []).map((id) => `rule:${id}`),
    ...report.timing_not_active.filter((t) => t.role === role).map((t) => `route:${t.rule_id}`),
    ...NORM_GROUPS.flatMap(([key]) => (report[key][role] || []).map((id) => `${key}:${id}`)),
  ];
  for (const role of order) for (const key of items(role)) (owners[key] ||= []).push(role);
  const shared = (key) => owners[key].length > 1;

  // An item key is "<kind>:<id>"; turn a list of keys back into ids per kind.
  const partsOf = (keys) => {
    const ids = (prefix) => keys.filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length));
    return {
      outstanding: ids("rule:"),
      unresolved: ids("route:"),
      norms: Object.fromEntries(NORM_GROUPS.map(([key]) => [key, ids(`${key}:`)])),
    };
  };
  const ctx = { data, ruleDate, isFuture };
  const sections = [];
  const byParties = groupBy(Object.keys(owners).filter(shared), (key) => owners[key].join(","));
  // The widest group of parties first: it is what most readers owe.
  for (const [parties, keys] of Object.entries(byParties).sort((a, b) => b[0].split(",").length - a[0].split(",").length)) {
    sections.push(el("section", { class: "card role", "data-roles": parties },
      el("h2", {}, el("span", { class: "roles" }, parties.split(",").map(roleTag))),
      dutyGroups(partsOf(keys), [], ctx)));
  }
  for (const role of order) {
    const findings = report.findings.filter((f) => f.role === role);
    const parts = partsOf(items(role).filter((k) => !shared(k)));
    const groups = dutyGroups(parts, findings, ctx);
    if (!groups.length) continue;
    const counts = report.summary.per_role?.[role];
    sections.push(el("section", { class: "card role", "data-roles": role },
      el("h2", {}, roleTag(role),
        counts ? el("span", { class: "n" }, `${counts.gaps} gap${counts.gaps === 1 ? "" : "s"} in force`) : null),
      groups));
  }
  return sections;
}

const roleTag = (role) => el("span", { class: `role-tag r-${role}` }, human(role));

// ---- role filter -------------------------------------------------------------------------------
// The reader picks the roles they hold; a section shows while any of its roles is picked. The
// choice is remembered in this browser.
const ROLES_KEY = "aiact-review:hidden-roles";

function roleFilter(sections) {
  const present = [...new Set(sections.flatMap((s) => (s.dataset.roles || "").split(",").filter(Boolean)))];
  if (present.length < 2) return null;
  const hidden = new Set(restore(ROLES_KEY) || []);
  const apply = () => {
    for (const s of sections) {
      if (!s.dataset.roles) continue;
      s.hidden = s.dataset.roles.split(",").every((r) => hidden.has(r));
    }
    for (const b of buttons) b.classList.toggle("off", hidden.has(b.dataset.role));
    reset.hidden = !hidden.size;
    store(ROLES_KEY, [...hidden]);
  };
  const buttons = present.map((role) => el("button", {
    type: "button", class: `role-tag r-${role}`, "data-role": role, title: "Show or hide this role's obligations",
    onclick: () => { hidden.has(role) ? hidden.delete(role) : hidden.add(role); apply(); },
  }, human(role)));
  const reset = el("button", { type: "button", class: "link", onclick: () => { hidden.clear(); apply(); } }, "Show all");
  const bar = el("div", { class: "role-filter" }, el("span", { class: "lbl" }, "Show obligations for:"), buttons, reset);
  apply();
  return bar;
}

// The groups of one section.
function dutyGroups(parts, findings, { data, ruleDate, isFuture }) {
  const now = findings.filter((f) => !f.applies_from);
  const byDate = groupBy(findings.filter((f) => f.applies_from), (f) => f.applies_from);
  const confirmNow = parts.outstanding.filter((id) => !isFuture(ruleDate(id)));
  const confirmLater = parts.outstanding.filter((id) => isFuture(ruleDate(id)));
  return [
    now.length ? group("", "Checked — in force now", null, now.map((f) => findingItem(f, data))) : null,
    ...Object.entries(byDate).sort().map(([d, list]) =>
      group("future", `Checked — required from ${fmtDate(d)}`, "Not yet in force. A gap here is something to fix before this date.",
        list.map((f) => findingItem(f, data)))),
    confirmNow.length ? group("", "Check yourself — applies now", "A document can't show these, so the review doesn't check them. Check each one yourself.",
      confirmNow.map((id) => outstandingItem(id, data, ruleDate(id), false))) : null,
    confirmLater.length ? group("future", "Check yourself — applies later", "Not yet in force. A document can't show these, so check each one yourself before its date.",
      confirmLater.map((id) => outstandingItem(id, data, ruleDate(id), true))) : null,
    parts.unresolved.length ? group("", "Date depends on the Art. 6 route", "Not checked: when these apply turns on how the system is classified.",
      parts.unresolved.map((id) => outstandingItem(id, data, null, false))) : null,
    ...NORM_GROUPS.map(([key, label]) => (parts.norms[key].length
      ? group("", label, null, parts.norms[key].map((id) => normItem(id, data))) : null)),
  ].filter(Boolean);
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
      el("span", { class: "oneline" }, rule?.action || rule?.requirement || f.rule_id),
      el("span", { class: "when" }, f.applies_from ? el("span", { class: "tag date" }, `from ${fmtDate(f.applies_from)}`) : null)),
    el("div", { class: "item-body" },
      kv("Finding", f.reasoning),
      rule ? kv("The Act says", el("div", { class: "law" }, rule.requirement)) : null,
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
      el("span", {}, el("span", { class: "tag needs_review" }, "Check")),
      el("span", { class: "cite" }, rule?.citation || ""),
      el("span", { class: "oneline" }, rule?.action || rule?.requirement || id),
      el("span", { class: "when" }, future ? el("span", { class: "tag date" }, `from ${fmtDate(date)}`) : null)),
    el("div", { class: "item-body" },
      rule ? kv("What to check", rule.evidence_expected) : null,
      rule ? kv("The Act says", el("div", { class: "law" }, rule.requirement)) : null,
      rule?.activation_condition ? kv("Applies to", rule.activation_condition) : null,
      rule?.effective_date_note ? kv("Date note", rule.effective_date_note) : null,
      kv("Rule", el("span", { class: "mono" }, id))),
  );
}

// Reports saved before citations were added carry only the segment ids.
const normCites = (norm) => norm?.citations || norm?.source_spans || [];

function normItem(id, data) {
  const norm = data.norms[id];
  return el("details", { class: "item" },
    el("summary", {},
      el("span", {}, el("span", { class: "tag soft" }, NORM_KIND[norm?.kind] || human(norm?.kind || "norm"))),
      el("span", { class: "cite" }, normCites(norm)[0] || ""),
      el("span", { class: "oneline" }, norm?.action || id),
      el("span", {})),
    el("div", { class: "item-body" },
      norm ? kv("Means", norm.action) : null,
      norm?.conditions ? kv("If", norm.conditions) : null,
      norm?.exceptions ? kv("Except", norm.exceptions) : null,
      norm ? kv("Basis", normCites(norm).join(", ")) : null),
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
  const over = maxChars !== null && n > maxChars;
  $("chars").textContent = maxChars !== null
    ? `${n.toLocaleString("en-GB")} / ${maxChars.toLocaleString("en-GB")} characters`
    : `${n.toLocaleString("en-GB")} characters`;
  $("chars").classList.toggle("over", over);
  $("run").disabled = over;
}

window.addEventListener("DOMContentLoaded", () => {
  for (const b of document.querySelectorAll("#theme button")) b.addEventListener("click", () => setTheme(b.dataset.theme));
  setTheme(document.documentElement.dataset.theme || "auto");
  $("form").addEventListener("submit", runReview);
  $("document").addEventListener("input", () => { countChars(); saveDraft(); });
  $("edit").addEventListener("click", () => { setMode("edit"); $("document").focus(); });
  $("new").addEventListener("click", () => {
    $("document").value = "";
    countChars();
    setMode("edit");
    $("document").focus();
  });
  $("cancel").addEventListener("click", () => {
    $("document").value = last.document;
    countChars();
    setMode("view");
  });
  $("file").addEventListener("change", async () => {
    const file = $("file").files[0];
    if (!file) return;
    $("document").value = await file.text();
    countChars();
    saveDraft();
  });

  const draft = restore(STORE.draft);
  last = restore(STORE.last);
  const old = restore(OLD_REPORT_KEY);
  if (!last && old?.report) {
    last = { response: old, document: draft?.document || "" };
    store(STORE.last, last);
  }
  try { localStorage.removeItem(OLD_REPORT_KEY); } catch {}
  if (last) {
    try { render(last.response); } catch { last = null; try { localStorage.removeItem(STORE.last); } catch {} }
  }
  // Back where the reader left off: editing a draft, or reading the last report.
  if (last && !draft?.editing) {
    $("document").value = last.document;
    setMode("view");
  } else {
    $("document").value = draft?.document || "";
    setMode("edit");
  }
  countChars();
  fetch("/api/limits").then((r) => r.json()).then((limits) => {
    maxChars = limits.max_document_chars || null;
    countChars();
  }).catch(() => {});
});
