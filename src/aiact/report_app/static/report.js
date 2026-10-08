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

// A saved report keeps its verdicts and notes; its rule texts, actions and citations are rebuilt
// from the current rules, so a report saved before a rules change still reads like a new one.
async function refreshSaved() {
  const saved = last;
  try {
    const response = await fetch("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        use_cases: saved.response.report.classification.use_cases,
        rule_ids: Object.keys(saved.response.rules),
        norm_ids: Object.keys(saved.response.norms),
      }),
    });
    if (!response.ok || last !== saved) return;
    const fresh = await response.json();
    last = { ...saved, response: { ...saved.response, rules: fresh.rules, norms: fresh.norms } };
    store(STORE.last, last);
    render(last.response);
  } catch {}
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
    el("span", { class: "muted small" }, "Classifying the system, then checking each duty."));
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

  filters = []; // the bars of the report being replaced
  whenButtons = [];
  const [first, later] = notes(data);
  const { duties, others } = provisions(report, data, ruleDate, isFuture);
  // A section with nothing to show is null; replaceChildren would print it as text.
  $("report").replaceChildren(...[
    ...header(data),
    compliance(report, data, ruleDate, isFuture),
    ...first,
    duties ? el("div", { class: "section-head", id: "duties" },
      el("h2", {}, "Your duties"),
      el("p", { class: "muted" }, "What the AI Act requires, and who must do it. Where a duty can be shown in writing, we checked whether your document covers it. The rest can't be verified from documentation, so you need to check them yourself.")) : null,
    duties ? later : null,
    duties,
    others ? el("div", { class: "section-head" },
      el("h2", {}, "Permissions, rights and effects"),
      el("p", { class: "muted" }, "What the AI Act allows you, what you can claim, and what follows in law. Nothing here is checked.")) : null,
    others,
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
    risk === "needs_review" ? el("p", { class: "muted" }, "Add the missing facts and run the review again. ",
      el("a", { href: "/guide", target: "_blank", rel: "noopener" }, "The guide"), " says what to write.") : null,
  );
  return [system, classification];
}

function note(kind, lead, text) {
  return el("section", { class: `note ${kind}` }, el("div", { class: "lead" }, lead), el("p", {}, text));
}

// Notes that change how the report reads go above the counts as alerts. The rest explain a
// condition on the duties and go in one panel under the counts, one line each.
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
  if (n.deployer_type) later.push(["Who deploys the system",
    "Decides whether the impact assessment (Art. 27) and deployer registration (Art. 49(3)) apply.", n.deployer_type]);
  if (n.real_world_testing) later.push(["Live testing before release",
    "Decides whether the testing duties of Art. 60 and 61 apply.", n.real_world_testing]);
  if (n.chapter_v_gate) later.push(["General-purpose AI model",
    "Decides which Chapter V duties apply.", n.chapter_v_gate]);
  // Art. 111 is relief the report cannot grant: it turns on the market placement date, which no
  // document states. Shown as advice, never as an exemption, and it changes no count.
  if (n.legacy_system) later.push(["Systems already on the market",
    "May get more time under Art. 111. The review does not apply this — check with your adviser.", n.legacy_system]);
  return [out, later.length ? noteList(later) : null];
}

function noteList(items) {
  return el("section", { class: "card notes" },
    el("h3", {}, "Notes on these duties", el("span", { class: "muted" }, `· ${items.length}`)),
    el("p", { class: "hint" }, "Facts the review could not settle from your document, and what they change. Open a note for details."),
    items.map(([title, hint, text]) => el("details", { class: "item note-item" },
      el("summary", {}, el("span", { class: "cite" }, title), el("span", { class: "oneline" }, hint)),
      el("div", { class: "item-body" }, el("p", {}, text)))));
}

// ---- the short answer -------------------------------------------------------------------------
// Is the system compliant, and what is left to do. Only the duties a document can show are judged,
// so the answer never says "compliant" outright: it says the document meets what was checked, and
// points at the duties nobody checked.
const nDuties = (n) => `${n} ${n === 1 ? "duty" : "duties"}`;
const FIX = { gap: "Not covered in your document", inadequate: "Covered only in part", needs_review: "Unclear from your document" };

function compliance(report, data, ruleDate, isFuture) {
  const risk = report.classification.overall_risk_class;
  const open = report.findings.filter((f) => f.verdict in FIX);
  const openNow = open.filter((f) => !f.applies_from);
  const unchecked = [...new Set(Object.values(report.not_document_verifiable).flat())];
  const uncheckedNow = unchecked.filter((id) => !isFuture(ruleDate(id))).length;

  let state, answer, detail;
  if (risk === "prohibited") {
    state = "stop"; answer = "Not allowed";
    detail = "This is a prohibited practice under Art. 5. It must not be placed on the EU market, put into service or used, so no other duty can make it compliant.";
  } else if (risk === "needs_review") {
    state = "warn"; answer = "Can't tell yet";
    detail = "The review could not classify the system from your document, so it can't say what applies. Add the missing facts and run it again.";
  } else if (openNow.length) {
    state = "stop"; answer = "Not compliant today";
    detail = `${nDuties(openNow.length)} in force today ${openNow.length === 1 ? "is" : "are"} not met by your document.`;
  } else if (report.findings.length) {
    state = "ok"; answer = "Compliant today";
    detail = "Your document meets every duty in force today that it can show.";
  } else {
    state = "ok"; answer = "Nothing to check against your document";
    detail = "None of the duties that apply to this system can be shown in writing.";
  }

  // What to fix now, then what to meet by each later date.
  const later = groupBy(open.filter((f) => f.applies_from), (f) => f.applies_from);
  const todo = (title, cls, list) => el("div", { class: `todo ${cls}` },
    el("h3", {}, title),
    el("ol", {}, list.map((f) => {
      const rule = data.rules[f.rule_id];
      return el("li", {},
        el("a", { href: `#${itemId(f)}`, onclick: (e) => { e.preventDefault(); reveal(itemId(f)); } },
          rule?.action || rule?.requirement || f.rule_id),
        el("span", { class: "muted" }, ` — ${FIX[f.verdict]}, ${rule?.citation || citeSource(f.citation)}`),
        roleTag(f.role));
    })));
  return el("section", { class: `card compliance ${state}` },
    el("div", { class: "eyebrow" }, "Compliance"),
    el("div", { class: "answer" }, answer),
    el("p", {}, detail),
    risk !== "prohibited" && openNow.length ? todo("Fix now", "now", openNow) : null,
    risk !== "prohibited" ? Object.entries(later).sort().map(([d, list]) =>
      todo(`To stay compliant from ${fmtDate(d)}: ${nDuties(list.length)} to meet`, "later", list)) : null,
    unchecked.length && risk !== "prohibited" && risk !== "needs_review" ? el("p", { class: "also" },
      `Also check ${nDuties(unchecked.length)} yourself that can't be verified from documentation — ${uncheckedNow} already ${uncheckedNow === 1 ? "applies" : "apply"}. `,
      el("a", { href: "#duties", onclick: (e) => { e.preventDefault(); $("duties")?.scrollIntoView({ behavior: "smooth" }); } }, "See the list")) : null,
  );
}

const itemId = (f) => `finding-${f.rule_id}-${f.role}`;

// Open a duty in the list and bring it into view, showing it even if a filter hid it.
function reveal(id) {
  const item = $(id);
  if (!item) return;
  item.hidden = false;
  item.closest(".group").hidden = false;
  item.open = true;
  item.scrollIntoView({ behavior: "smooth", block: "center" });
}

// ---- one list of provisions ---------------------------------------------------------------------
// Every provision once, tagged with the parties it applies to. A finding is one party's verdict, so
// it carries that party's tag; an unjudged item several parties owe (the Art. 5 ban, Art. 4 AI
// literacy, a fine) is listed once with all of their tags.
function provisions(report, data, ruleDate, isFuture) {
  const present = new Set([
    ...report.findings.map((f) => f.role),
    ...Object.keys(report.not_document_verifiable),
    ...report.timing_not_active.map((t) => t.role),
    ...NORM_GROUPS.flatMap(([key]) => Object.keys(report[key])),
  ]);
  const order = [...ROLE_ORDER.filter((r) => present.has(r)), ...[...present].filter((r) => !ROLE_ORDER.includes(r))];

  // Each unjudged item, keyed "<kind>:<id>", with the parties that owe it in role order.
  const owners = {};
  const add = (key, role) => { if (!(owners[key] ||= []).includes(role)) owners[key].push(role); };
  for (const role of order) {
    for (const id of report.not_document_verifiable[role] || []) add(`rule:${id}`, role);
    for (const t of report.timing_not_active.filter((t) => t.role === role)) add(`route:${t.rule_id}`, role);
    for (const [key] of NORM_GROUPS) for (const id of report[key][role] || []) add(`${key}:${id}`, role);
  }
  const ids = (prefix) => Object.keys(owners).filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length));
  const partiesOf = (prefix) => (id) => owners[`${prefix}${id}`];
  const findings = [...report.findings].sort((a, b) => order.indexOf(a.role) - order.indexOf(b.role));

  const duties = dutyGroups({ outstanding: ids("rule:"), unresolved: ids("route:") },
    findings, { data, ruleDate, isFuture, partiesOf });
  const others = NORM_GROUPS.map(([key, label]) => {
    const list = ids(`${key}:`);
    return list.length ? group("", label, null, list.map((id) => normItem(id, data, partiesOf(`${key}:`)(id)))) : null;
  }).filter(Boolean);
  const card = (groups, ...bars) => (groups.length
    ? el("section", { class: "card provisions" }, el("div", { class: "filters" }, ...bars, roleFilter(groups, order)), groups) : null);
  return { duties: card(duties, whenFilter()), others: card(others) };
}

const roleTag = (role) => el("span", { class: `role-tag r-${role}` }, human(role));

// ---- role filter -------------------------------------------------------------------------------
// The reader picks the roles they hold; a provision shows while any of its parties is picked, and a
// group with none left showing is hidden. Each list has its own bar on top; all bars share one
// choice, remembered in this browser.
const ROLES_KEY = "aiact-review:hidden-roles";
let filters = []; // [{ groups, buttons, reset }] for every bar on the page

// The reader also picks which duties to see by date: all, those in force now, or those that start
// later. A duty whose date turns on the Art. 6 route shows under "All" only.
const WHEN_KEY = "aiact-review:when";
const WHEN = [["all", "All"], ["now", "In force now"], ["future", "Starts later"]];
let whenButtons = [];

function whenFilter() {
  const pick = (value) => { store(WHEN_KEY, value); applyFilters(); };
  whenButtons = WHEN.map(([value, label]) => el("button", { type: "button", "data-when": value, onclick: () => pick(value) }, label));
  return el("div", { class: "when-filter" }, el("span", { class: "lbl" }, "Show duties:"),
    el("div", { class: "seg", role: "group", "aria-label": "Show duties by date" }, whenButtons));
}

function applyFilters() {
  const hidden = new Set(restore(ROLES_KEY) || []);
  const when = restore(WHEN_KEY) || "all";
  for (const b of whenButtons) b.classList.toggle("on", b.dataset.when === when);
  for (const { groups, buttons, reset } of filters) {
    for (const g of groups) {
      let shown = 0;
      for (const item of g.querySelectorAll("[data-roles]")) {
        item.hidden = item.dataset.roles.split(",").every((r) => hidden.has(r))
          || (when !== "all" && item.dataset.when !== undefined && item.dataset.when !== when);
        if (!item.hidden) shown += 1;
      }
      g.hidden = !shown;
      g.querySelector(".count").textContent = `· ${shown}`;
    }
    for (const b of buttons) b.classList.toggle("off", hidden.has(b.dataset.role));
    reset.hidden = !hidden.size;
  }
}

function roleFilter(groups, roles) {
  const tagged = new Set(groups.flatMap((g) => [...g.querySelectorAll("[data-roles]")].flatMap((i) => i.dataset.roles.split(","))));
  const present = roles.filter((r) => tagged.has(r));
  if (present.length < 2) return null;
  const toggle = (role) => {
    const hidden = new Set(restore(ROLES_KEY) || []);
    hidden.has(role) ? hidden.delete(role) : hidden.add(role);
    store(ROLES_KEY, [...hidden]);
    applyFilters();
  };
  const buttons = present.map((role) => el("button", {
    type: "button", class: `role-tag r-${role}`, "data-role": role, title: "Show or hide what applies to this role",
    onclick: () => toggle(role),
  }, human(role)));
  const reset = el("button", { type: "button", class: "link", onclick: () => { store(ROLES_KEY, []); applyFilters(); } }, "Show all");
  filters.push({ groups, buttons, reset });
  queueMicrotask(applyFilters); // once the list is on the page
  return el("div", { class: "role-filter" }, el("span", { class: "lbl" }, "Show for:"), buttons, reset);
}

function dutyGroups(parts, findings, { data, ruleDate, isFuture, partiesOf }) {
  // In force first, then by the date each starts.
  const byDate = (date) => date || "";
  const checked = [...findings].sort((a, b) => byDate(a.applies_from).localeCompare(byDate(b.applies_from)));
  const outstanding = [...parts.outstanding].sort((a, b) =>
    byDate(isFuture(ruleDate(a)) ? ruleDate(a) : null).localeCompare(byDate(isFuture(ruleDate(b)) ? ruleDate(b) : null)));
  const rule = partiesOf("rule:");
  const route = partiesOf("route:");
  return [
    checked.length ? group("", "Checked against your document", null, checked.map((f) => findingItem(f, data))) : null,
    outstanding.length ? group("", "Not verifiable from documentation", "The review doesn't check these. Check each one yourself.",
      outstanding.map((id) => outstandingItem(id, data, ruleDate(id), isFuture(ruleDate(id)), rule(id)))) : null,
    parts.unresolved.length ? group("", "Date depends on the Art. 6 route", "Not checked: when these apply turns on how the system is classified.",
      parts.unresolved.map((id) => outstandingItem(id, data, null, false, route(id), "unknown"))) : null,
  ].filter(Boolean);
}

// The action, with the parties it applies to under it.
function what(text, roles) {
  return el("span", { class: "what" }, el("span", { class: "oneline" }, text),
    roles?.length ? el("span", { class: "parties" }, roles.map(roleTag)) : null);
}

function groupBy(list, key) {
  return list.reduce((acc, item) => { (acc[key(item)] ||= []).push(item); return acc; }, {});
}

function group(cls, title, hint, items) {
  return el("div", { class: `group ${cls}`.trim() },
    el("h3", {}, title, el("span", { class: "muted count" }, `· ${items.length}`)),
    hint ? el("p", { class: "hint" }, hint) : null,
    items);
}

function kv(label, ...value) {
  return el("div", { class: "kv" }, el("div", { class: "l" }, label), el("div", {}, value));
}

function findingItem(f, data) {
  const rule = data.rules[f.rule_id];
  return el("details", { class: "item", id: itemId(f), "data-roles": f.role, "data-when": f.applies_from ? "future" : "now" },
    el("summary", {},
      el("span", {}, el("span", { class: `tag ${f.verdict}` }, VERDICT[f.verdict] || human(f.verdict))),
      el("span", { class: "cite" }, rule?.citation || citeSource(f.citation)),
      what(rule?.action || rule?.requirement || f.rule_id, [f.role]),
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

function outstandingItem(id, data, date, future, roles, when = future ? "future" : "now") {
  const rule = data.rules[id];
  return el("details", { class: "item", "data-roles": roles.join(","), "data-when": when },
    el("summary", {},
      el("span", {}, el("span", { class: "tag needs_review" }, "Check")),
      el("span", { class: "cite" }, rule?.citation || ""),
      what(rule?.action || rule?.requirement || id, roles),
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

function normItem(id, data, roles = null) {
  const norm = data.norms[id];
  return el("details", roles ? { class: "item", "data-roles": roles.join(",") } : { class: "item" },
    el("summary", {},
      el("span", {}, el("span", { class: `tag soft kind-${norm?.kind}` }, NORM_KIND[norm?.kind] || human(norm?.kind || "norm"))),
      el("span", { class: "cite" }, normCites(norm)[0] || ""),
      what(norm?.action || id, roles),
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
    el("h2", {}, "Public authorities", el("span", { class: "n" }, "not your duties; listed for context")),
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
  if (last) refreshSaved();
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
