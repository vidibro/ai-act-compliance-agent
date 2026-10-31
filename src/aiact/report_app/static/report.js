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
const VERDICT = { pass: "Met", gap: "Not met", inadequate: "Partly met", needs_review: "Unclear", not_applicable: "N/a" };
const ROLE_ORDER = ["provider", "initial_provider", "prospective_provider", "sandbox_participant", "deployer",
                    "importer", "distributor", "authorised_representative", "gpai_provider"];
// Short enough to fit the tag column.
const NORM_KIND = { permission: "Permission", entitlement: "Right", legal_consequence: "Legal effect", power: "Power",
                    obligation: "Duty", prohibition: "Ban", recommendation: "Advice", applicability: "Limitation",
                    definition: "Definition" };
// The order of the Type filter, what the reader may do first.
const KIND_ORDER = ["permission", "entitlement", "legal_consequence", "applicability", "power", "obligation",
                    "prohibition", "recommendation", "definition"];
// The report's sections that list norms per role, rather than judge them.
const NORM_SECTIONS = ["permissions", "rights", "legal_consequences", "conditional_applicability"];

// ---- ordering by provision -----------------------------------------------------------------------
// Lists run in the order of the Act: articles before annexes, then article number, its letter
// (4 before 4a), and each paragraph and point in turn — numbers as numbers, so 9 comes before 10.
function citeKey(citation) {
  const text = String(citation || "");
  const annex = /^Annex/.test(text);
  const head = text.match(/(\d+)([a-z]*)/);
  const parts = [...text.slice(head ? head.index + head[0].length : 0).matchAll(/\(([^)]*)\)/g)].map((m) => m[1]);
  return [annex ? 1 : 0, head ? Number(head[1]) : Infinity, head ? head[2] : "", ...parts];
}

const ROMAN = /^[ivx]+$/;
function roman(text) {
  const value = { i: 1, v: 5, x: 10 };
  return [...text].reduce((sum, ch, i) => sum + (value[ch] < (value[text[i + 1]] || 0) ? -value[ch] : value[ch]), 0);
}

function byCitation(a, b) {
  const x = citeKey(a);
  const y = citeKey(b);
  for (let i = 0; i < Math.max(x.length, y.length); i += 1) {
    if (x[i] === undefined) return -1; // Art. 26 before Art. 26(7)
    if (y[i] === undefined) return 1;
    if (x[i] === y[i]) continue;
    const nx = Number.parseInt(x[i], 10);
    const ny = Number.parseInt(y[i], 10);
    if (!Number.isNaN(nx) && !Number.isNaN(ny) && nx !== ny) return nx - ny;
    // Sub-points (i), (ii) ... (ix) are Roman numerals: (v) before (ix).
    if (ROMAN.test(x[i]) && ROMAN.test(y[i])) return roman(x[i]) - roman(y[i]);
    return String(x[i]).localeCompare(String(y[i]));
  }
  return 0;
}

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
//
// EACH MODE HAS ITS OWN. Normal mode keeps its draft and report under the keys below, in local
// storage. Demo mode keeps its own IN MEMORY: it survives a mode switch within the page, not a
// reload — a demo document is a sample from the repository, one click away again, and not worth
// its half-megabyte of the storage quota. Switching mode swaps the whole workspace, so a demo
// document is never shown beside the "Run review" button, nor a real document under the banner.
const STORE = { last: "aiact-review:last", draft: "aiact-review:draft" };
const DEMO_STORE = { last: "aiact-review:demo:last", draft: "aiact-review:demo:draft" };
const OLD_REPORT_KEY = "aiact-review:last-report"; // a bare response, saved by an earlier version
const memory = new Map(); // the demo workspace
let maxChars = null; // the server's document limit
let last = null; // { response, document } of the report on screen

// The key for the workspace of the mode the page is in — or of a given report's mode.
const keyFor = (kind, inDemo = demo) => (inDemo ? DEMO_STORE : STORE)[kind];
const inMemory = (key) => Object.values(DEMO_STORE).includes(key);

function store(key, value) {
  if (inMemory(key)) { memory.set(key, value); return; }
  try { localStorage.setItem(key, JSON.stringify(value)); } catch {}
}

function restore(key) {
  if (inMemory(key)) return memory.get(key) ?? null;
  try { return JSON.parse(localStorage.getItem(key) || "null"); } catch { return null; }
}

function saveDraft() {
  store(keyFor("draft"), { document: $("document").value, editing: $("form").dataset.mode === "edit" });
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
    store(keyFor("last", Boolean(last.response.demo)), last);
    render(last.response);
  } catch {}
}

// ---- demo or normal --------------------------------------------------------------------------
// Normal mode sends the document to /api/review, where a model classifies it and judges each duty.
// Demo mode sends it to /api/demo/review, where keyword heuristics stand in for the model: no key,
// no cost, a second's wait, and a report that is illustrative rather than an assessment. The page
// says which mode it is in everywhere it can — the switch in the bar, the bar's colour, a banner,
// the run button — and every demo report carries the mark however it is shown later.
//
// The choice is kept in this browser. When the server has no model (AIACT_LLM_MODEL empty), demo
// is the only mode and the switch is locked on.
const DEMO_KEY = "aiact-review:demo";
const DEMO_NOTE = "This is a demo report: no model read the document, so the classification and the verdicts "
  + "come from keyword heuristics and illustrate the report rather than assess the system.";
const DEMO_ON_TEXT = "No model is called: keyword heuristics stand in for the classifier and the judge, so the "
  + "report is illustrative, not an assessment.";
// What /api/mode says: the server's AIACT_DEMO_MODE ("available" | "only" | "off"), and whether a
// live review can run at all — a model named, a key for it found. Until it answers, the page
// assumes the ordinary case.
let modeInfo = { demo_mode: "available", live_available: true, live_unavailable_because: null,
                 llm_model: null, demo_note: DEMO_NOTE };
let demo = false;
let workspaceLoaded = false; // false until the first mode is applied on page load

// Demo is the only mode where a live review cannot run (and demo is not switched off).
const demoLocked = () => modeInfo.demo_mode !== "off" && !modeInfo.live_available;

function setDemo(on, { save = true } = {}) {
  const next = modeInfo.demo_mode !== "off" && (Boolean(on) || demoLocked());
  const changed = next !== demo || !workspaceLoaded;
  if (changed && workspaceLoaded) saveDraft(); // what is on screen belongs to the mode being left
  demo = next;
  if (demo) document.documentElement.dataset.demo = "1"; else delete document.documentElement.dataset.demo;
  const locked = demoLocked();
  const sw = $("demo-switch");
  sw.hidden = modeInfo.demo_mode === "off";
  sw.setAttribute("aria-checked", String(demo));
  sw.disabled = locked;
  sw.title = locked ? `${modeInfo.live_unavailable_because} Demo mode is the only mode.`
    : demo ? "Demo mode is on: no model is called. Click to switch to normal mode."
    : `Normal mode: reviews call ${modeInfo.llm_model || "the configured model"}. Click for demo mode.`;
  // The banner: why demo mode is on — by choice, or because nothing else can run. With demo mode
  // switched off AND no live review possible, the same bar says so, as a warning.
  const stuck = modeInfo.demo_mode === "off" && !modeInfo.live_available;
  $("modebar").hidden = !demo && !stuck;
  $("modebar").classList.toggle("stuck", stuck);
  $("modebar-badge").textContent = stuck ? "No review can run" : "Demo mode";
  $("modebar-text").textContent = stuck ? `${modeInfo.live_unavailable_because} Demo mode is switched off (AIACT_DEMO_MODE=off).`
    : locked ? `${modeInfo.live_unavailable_because} Only demo reviews can run.` : DEMO_ON_TEXT;
  $("modebar-off").hidden = locked || stuck;
  $("demo-float-off").hidden = locked;
  $("demo-float-sub").textContent = locked ? "The only mode on this server" : "Illustrative — no model is called";
  $("run").textContent = demo ? "Run demo review" : "Run review";
  $("run-hint").textContent = demo ? "No model is called; takes a second. Illustrative only."
    : "Makes model calls; takes a minute or two.";
  document.title = demo ? "AI Act Compliance Review — demo" : "AI Act Compliance Review";
  if (save) store(DEMO_KEY, demo);
  if (changed) loadWorkspace();
}

// Saves from earlier versions of this page: a bare response under its old key, a demo report
// saved under the normal key before the two modes kept separate workspaces, and a demo workspace
// saved to local storage before it moved to memory. The first moves to where this version looks
// for it; the demo ones are dropped — a sample is one click away.
function migrateSaved() {
  const old = restore(OLD_REPORT_KEY);
  if (old?.report && !restore(STORE.last)) {
    store(STORE.last, { response: old, document: restore(STORE.draft)?.document || "" });
  }
  const stale = [OLD_REPORT_KEY, ...Object.values(DEMO_STORE)];
  if (restore(STORE.last)?.response?.demo) stale.push(STORE.last, STORE.draft);
  for (const key of stale) { try { localStorage.removeItem(key); } catch {} }
}

// The document and report of the mode the page is now in — back where the reader left off in that
// mode, or a clean page where they have not used it yet. Nothing carries over from the other mode.
function loadWorkspace() {
  workspaceLoaded = true;
  showError("");
  markCase(null);
  const draft = restore(keyFor("draft"));
  last = restore(keyFor("last"));
  if (last && Boolean(last.response?.demo) !== demo) last = null; // the other mode's report
  $("report").replaceChildren();
  if (last) {
    try { render(last.response); } catch { last = null; try { localStorage.removeItem(keyFor("last")); } catch {} }
  }
  if (last) refreshSaved();
  if (last && !draft?.editing) {
    $("document").value = last.document;
    setMode("view");
    markCase(last.sample || null);
  } else {
    $("document").value = draft?.document || "";
    setMode("edit");
  }
  countChars();
}

// Sample documents from the repository — the golden set's reference files, the guide's worked
// example, the smoke check's vendor pages — so there is always something to run the review on.
const SAMPLE_GROUPS = [["system_card", "System cards — written to the guide"],
                       ["reference", "Technical files — complete and compliant"],
                       ["vendor_page", "Vendor pages — thin input"]];

async function loadSamples() {
  const select = $("sample");
  let list = [];
  try { list = await fetch("/api/samples").then((r) => (r.ok ? r.json() : [])); } catch {}
  if (!list.length) return;
  for (const [kind, label] of SAMPLE_GROUPS) {
    const items = list.filter((sample) => sample.kind === kind);
    if (!items.length) continue;
    select.append(el("optgroup", { label }, items.map((sample) =>
      el("option", { value: sample.id, title: sample.about }, sample.title))));
  }
  select.hidden = false;
  select.addEventListener("change", () => {
    const id = select.value;
    select.value = "";
    if (id) pickSample(id);
  });
  buildGallery(list);
}

// Paste a sample into the input — leaving a report on screen for the editor if need be — and,
// asked to (always, in demo mode), run the review on it straight away.
async function pickSample(id, run = false) {
  let text;
  try {
    const response = await fetch(`/api/samples/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error(response.statusText);
    text = (await response.json()).text;
  } catch {
    showError("The sample document could not be loaded.");
    return;
  }
  if ($("form").dataset.mode === "view") setMode("edit");
  const area = $("document");
  area.value = text;
  area.setSelectionRange(0, 0);
  area.scrollTop = 0; // read from the top, as a pasted document would be
  countChars();
  saveDraft();
  showError("");
  markCase(id);
  if (run) $("form").requestSubmit();
  else area.focus();
}

// ---- the case gallery --------------------------------------------------------------------------
// Demo mode's only way in: one card per sample, marked with the outcome the demo reaches on it, so
// the reader picks the case they want to see — a compliant file, a card with gaps, an Annex I
// product, a prohibited practice — and has its report in one click. There is no free text input
// in demo mode: the documents are the cases, whose outcomes are known, and a reader's own document
// belongs in a real review.
function buildGallery(list) {
  const grid = $("cases-grid");
  grid.replaceChildren(...list.map((s) => el("div", { class: `case o-${s.outcome}`, "data-sample": s.id },
    el("button", { type: "button", class: "case-pick", title: "Run the demo review on this document",
                   onclick: () => pickSample(s.id, true) },
      el("span", { class: "case-outcome" }, RISK[s.outcome] || human(s.outcome)),
      el("span", { class: "case-title" }, s.title.split(/\s+[—–-]\s+/)[0]),
      el("span", { class: "case-label" }, s.label),
      el("span", { class: "case-about" }, s.about),
      el("span", { class: "case-run", "aria-hidden": "true" }, "Run demo review →")))));
  $("cases-count").textContent = `· ${list.length} cases`;
  $("cases").hidden = false;
}

// The card whose document is in the input, if any — named in the folded panel's summary line and
// cleared when the text is edited. Picking a case folds the panel: the choice is made.
let currentSample = null; // the sample in the input, carried onto the report it produces

function markCase(id) {
  currentSample = id || null;
  let picked = "";
  for (const card of document.querySelectorAll(".case")) {
    const on = card.dataset.sample === id;
    card.classList.toggle("on", on);
    if (on) picked = card.querySelector(".case-title")?.textContent || id;
  }
  $("cases-picked").textContent = picked ? `${picked} reviewed` : "";
}

// ---- edit or view ----------------------------------------------------------------------------
// "edit": the document can be changed and run; the last report is hidden.
// "view": the report is shown under the read-only document it reviewed.
function setMode(mode) {
  $("form").dataset.mode = mode;
  $("document").readOnly = mode === "view";
  $("form-title").textContent = mode === "view" ? "Reviewed document" : demo ? "Pick a case" : "Review a system";
  $("cancel").hidden = !last;
  $("report").hidden = mode === "edit";
  // In demo mode the cases ARE the input: open while choosing, folded once a report is up, and
  // the reviewed document hidden behind its toggle until asked for.
  if (demo) $("cases").open = mode === "edit";
  showDocument(false);
  saveDraft();
}

// Demo mode's read-only view of the document a report was made from.
function showDocument(shown) {
  $("form").classList.toggle("doc-shown", shown);
  $("show-doc").textContent = shown ? "Hide the reviewed document" : "Show the reviewed document";
  $("show-doc").setAttribute("aria-expanded", String(shown));
}

// ---- running a review ------------------------------------------------------------------------
let timer = null;

function setBusy(busy) {
  $("run").disabled = busy;
  $("document").readOnly = busy || $("form").dataset.mode === "view";
  $("cancel").disabled = busy;
  // No mode switch while a run is in flight: its report belongs to the mode it was started in.
  $("demo-switch").disabled = busy || demoLocked();
  for (const id of ["modebar-off", "demo-float-off"]) $(id).disabled = busy;
  for (const b of document.querySelectorAll(".case-pick")) b.disabled = busy;
  const status = $("status");
  clearInterval(timer);
  if (!busy) { status.hidden = true; return; }
  const started = Date.now();
  const verb = demo ? "Running the demo review" : "Reviewing";
  const text = el("span", {}, `${verb}… 0s`);
  status.replaceChildren(el("span", { class: "spinner" }), text,
    el("span", { class: "muted small" }, demo
      ? "No model is called: keyword heuristics stand in for the classifier and the judge."
      : "Classifying the system, then checking each duty."));
  status.hidden = false;
  timer = setInterval(() => { text.textContent = `${verb}… ${Math.round((Date.now() - started) / 1000)}s`; }, 1000);
}

function showError(message) {
  $("error").hidden = !message;
  $("error").textContent = message || "";
}

async function runReview(event) {
  event.preventDefault();
  showError("");
  setBusy(true);
  const inDemo = demo; // the mode the run was started in, whatever the switch does meanwhile
  try {
    const response = await fetch(inDemo ? "/api/demo/review" : "/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document: $("document").value }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail;
      const hint = inDemo || response.status === 413 || response.status === 422 ? ""
        : "\n\nTo try the page without a model, switch on Demo mode in the bar above.";
      throw new Error((detail || `The review failed (${response.status}).`) + hint);
    }
    last = { response: body, document: $("document").value, sample: currentSample };
    store(keyFor("last", inDemo), last);
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
  const normDate = (id) => data.norms[id]?.application_dates?.[useCase] ?? null;
  const isFuture = (d) => d !== null && d > today;

  filters = []; // the bars of the report being replaced
  whenButtons = [];
  doneKey = (data.demo ? "demo:" : "") + (data.system_name || "system");
  refreshVerdict = () => $("report").querySelector(".compliance")
    ?.replaceWith(compliance(report, data, ruleDate, normDate, isFuture));
  const [first, later] = notes(data);
  const { duties, others } = provisions(report, data, ruleDate, normDate, isFuture);
  // A section with nothing to show is null; replaceChildren would print it as text.
  $("report").replaceChildren(...[
    data.demo ? note("demo", "Demo report — illustrative", data.demo_note || modeInfo.demo_note || DEMO_NOTE) : null,
    ...header(data),
    compliance(report, data, ruleDate, normDate, isFuture),
    ...first,
    duties ? el("div", { class: "section-head", id: "duties" },
      el("h2", {}, "Operator duties"),
      el("p", { class: "muted" }, "What the AI Act requires, and who must do it. Where a duty can be shown in writing, we checked whether your document covers it. The rest can't be verified from documentation, so you need to check them yourself.")) : null,
    duties ? later : null,
    duties,
    others ? el("div", { class: "section-head" },
      el("h2", {}, "Other provisions"),
      el("p", { class: "muted" }, "Permissions, rights and legal effects, and what authorities must or may do about your system. These aren't compared with your document — they're for your information.")) : null,
    others,
    el("footer", { class: "disclaimer" }, report.disclaimer),
  ].filter(Boolean));
}

// What the system is first, then how it is classified.
function header(data) {
  const report = data.report;
  const c = report.classification;
  const risk = c.overall_risk_class;
  const demoTag = () => (data.demo ? el("span", { class: "tag demo-tag" }, "Demo") : null);
  const system = el("section", { class: "card system" },
    data.system_name
      ? el("h2", {}, el("span", { class: "eyebrow" }, "The system", demoTag()), data.system_name)
      : el("div", { class: "eyebrow" }, "The system", demoTag()),
    data.system_summary
      ? el("p", { class: "summary" }, data.system_summary)
      : el("p", { class: "muted" }, "No summary could be written for this document."),
    data.demo && data.system_summary
      ? el("p", { class: "muted small" }, "Quoted from the document by the demo; a model would write this summary.") : null,
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

// ---- the checklist -----------------------------------------------------------------------------
// The duties a document can't show are the reader's to confirm. Each can be ticked off as done; the
// ticks are kept in this browser per reviewed system, so a re-run of the same system keeps them.
const DONE_KEY = "aiact-review:done";
let doneKey = "system"; // the reviewed system the ticks belong to
let refreshVerdict = null; // redraws the verdict after a tick

const doneSet = () => new Set((restore(DONE_KEY) || {})[doneKey] || []);

function setDone(id, on) {
  const all = restore(DONE_KEY) || {};
  const ids = new Set(all[doneKey] || []);
  if (on) ids.add(id); else ids.delete(id);
  all[doneKey] = [...ids];
  store(DONE_KEY, all);
}

// The row's tick box, in the Check result column: a checkbox with "Duty" beside it until the reader
// ticks it off, "Done" after. A click inside <summary> would also open the row, so it is cancelled
// and the tick handled here.
function doneToggle(id) {
  const on = doneSet().has(id);
  return el("button", {
    type: "button", class: `check${on ? " on" : ""}`, role: "checkbox", "aria-checked": String(on),
    title: on ? "Done — click to mark as not done" : "Tick off when you have done this",
    onclick: (e) => {
      e.preventDefault();
      e.stopPropagation();
      setDone(id, !on);
      const row = e.currentTarget.closest("details");
      row.dataset.result = on ? "check" : "done";
      const next = doneToggle(id);
      e.currentTarget.replaceWith(next);
      next.focus();
      applyFilters();
    },
  }, el("span", { class: "box", "aria-hidden": "true" }), el("span", { class: "lbl" }, on ? "Done" : "Duty"));
}

// ---- the short answer -------------------------------------------------------------------------
// What the review can say, and what is left to do. Only the duties a document can show are judged,
// so for a system the Act regulates the answer is about the documentation, never "compliant": it
// says whether the document meets the duties it was checked against, and the duties nobody checked
// follow straight under it.
const nDuties = (n) => `${n} ${n === 1 ? "duty" : "duties"}`;
const FIX = { gap: "Not covered in your document", inadequate: "Covered only in part", needs_review: "Unclear from your document" };

function compliance(report, data, ruleDate, normDate, isFuture) {
  const risk = report.classification.overall_risk_class;
  // Only the roles the Operator filter shows: a deployer reading with the provider hidden gets the
  // deployer's verdict, not one a provider's gap decides.
  const hidden = hiddenOf("roles");
  const shown = (roles) => !roles?.length || roles.some((r) => !hidden.has(r));
  const findings = report.findings.filter((f) => shown([f.role]));
  const open = findings.filter((f) => f.verdict in FIX);
  const openNow = open.filter((f) => !f.applies_from);
  // Every duty the reader checks themselves, by its start date: the unjudged rules and the duties
  // that bind only under a condition.
  const owners = {};
  const own = (id, role) => (owners[id] ||= new Set()).add(role);
  for (const [role, ids] of Object.entries(report.not_document_verifiable)) for (const id of ids) own(id, role);
  for (const t of report.timing_not_active.filter((t) => t.status === "upcoming")) own(t.rule_id, t.role);
  const conditional = new Set();
  for (const [role, ids] of Object.entries(report.conditional_duties || {})) {
    for (const id of ids) { own(id, role); conditional.add(id); }
  }
  const unchecked = Object.keys(owners).filter((id) => shown([...owners[id]]))
    .map((id) => [id, conditional.has(id) ? normDate(id) : ruleDate(id)]);
  const done = doneSet();
  const uncheckedNow = unchecked.filter(([, day]) => !isFuture(day));
  const doneNow = uncheckedNow.filter(([id]) => done.has(id)).length;
  const doneAll = unchecked.filter(([id]) => done.has(id)).length;
  // Compliant only on both halves: every duty a document can show that is in force is met, and
  // every other duty in force is ticked off by the reader.
  const inForce = findings.some((f) => !f.applies_from) || uncheckedNow.length;
  const compliant = !openNow.length && inForce && doneNow === uncheckedNow.length;

  let state, answer, detail;
  if (risk === "prohibited") {
    state = "stop"; answer = "Not allowed";
    detail = "Your system is a prohibited practice under Art. 5. It must not be placed on the EU market, put into service or used, so no other duty can make it compliant.";
  } else if (risk === "needs_review") {
    state = "warn"; answer = "Not enough information to classify";
    detail = "The document you provided doesn't say enough to classify your system, so the review can't tell which duties apply. Add the missing facts and run it again — the guide says what to write.";
  } else if (risk === "out_of_scope") {
    state = "ok"; answer = "Not covered by the AI Act";
    detail = "Your system falls outside the AI Act, judging by the document you provided, so the Act sets it no duties.";
  } else if (openNow.length) {
    state = "stop"; answer = "Documentation falls short";
    detail = "Judging by the document you provided:";
  } else if (compliant) {
    state = "ok"; answer = "Compliant";
    detail = findings.some((f) => !f.applies_from)
      ? "Every duty in force today is covered: your document shows the ones a document can show, and you've ticked off the rest."
      : "Every duty in force today is ticked off. None of the duties a document can show is in force yet.";
  } else if (findings.some((f) => !f.applies_from)) {
    state = "ok"; answer = "Documentation meets today's duties";
    detail = "Judging by the document you provided:";
  } else if (findings.length) {
    // Nothing a document can show is in force yet: the answer is about the first date that is.
    const first = findings.map((f) => f.applies_from).sort()[0];
    const ready = !findings.some((f) => f.applies_from === first && f.verdict in FIX);
    state = ready ? "ok" : "warn";
    answer = `Documentation ${ready ? "ready" : "not ready"} for ${fmtDate(first)}`;
    detail = "Judging by the document you provided:";
  } else {
    state = "ok"; answer = "No duties to verify from your document";
    detail = hidden.size
      ? "None of these roles' duties can be judged from a document. Tick them off in the list below as you do them."
      : "Your system's duties can't be judged from a document. Tick them off in the list below as you do them.";
  }
  const judged = !["prohibited", "needs_review", "out_of_scope"].includes(risk)
    && (findings.length || unchecked.length);

  // One line per point in time, each with what is wrong under it, then the duties nobody checked:
  // a single list, so the later dates read as part of the same answer.
  const fixes = (list) => el("ol", { class: "fixes" }, [...list].sort((a, b) =>
    byCitation(data.rules[a.rule_id]?.citation, data.rules[b.rule_id]?.citation)).map((f) => {
    const rule = data.rules[f.rule_id];
    return el("li", {},
      el("a", { href: `#${itemId(f)}`, onclick: (e) => { e.preventDefault(); reveal(itemId(f)); } },
        rule?.action || rule?.requirement || f.rule_id),
      el("span", { class: "muted" }, ` — ${FIX[f.verdict]}, ${rule?.citation || citeSource(f.citation)}`),
      roleTag(f.role));
  }));
  const line = (cls, when, text, list = null) => el("li", { class: `status ${cls}` },
    el("span", { class: "when" }, when), el("div", {}, el("span", {}, text), list));
  const checkedNow = findings.filter((f) => !f.applies_from);
  const later = groupBy(findings.filter((f) => f.applies_from), (f) => f.applies_from);
  const statuses = judged ? el("ul", { class: "statuses" },
    !checkedNow.length && findings.length ? line("ok", "Now", "No duty your document can show is in force yet.") : null,
    checkedNow.length ? line(openNow.length ? "stop" : "ok", "Now",
      checkedNow.length === 1 && openNow.length ? "The 1 duty in force today is not met. Fix now:"
        : openNow.length === checkedNow.length && openNow.length ? `None of the ${nDuties(checkedNow.length)} in force today is met. Fix now:`
        : openNow.length ? `${openNow.length} of ${nDuties(checkedNow.length)} in force today ${openNow.length === 1 ? "is" : "are"} not met. Fix now:`
        : checkedNow.length === 1 ? "The 1 duty in force today is met." : `All ${nDuties(checkedNow.length)} in force today are met.`,
      openNow.length ? fixes(openNow) : null) : null,
    Object.entries(later).sort().map(([d, list]) => {
      const notMet = list.filter((f) => f.verdict in FIX);
      return line(notMet.length ? "warn" : "ok", `From ${fmtDate(d)}`,
        list.length === 1 && notMet.length ? "The 1 duty that starts then isn't met yet. Fix before that date:"
          : notMet.length === list.length ? `None of the ${nDuties(list.length)} that start then is met yet. Fix before that date:`
          : notMet.length ? `${notMet.length} of ${nDuties(list.length)} that start then ${notMet.length === 1 ? "isn't" : "aren't"} met yet. Fix before that date:`
          : list.length === 1 ? "The 1 duty that starts then is already met." : `All ${nDuties(list.length)} that start then are already met.`,
        notMet.length ? fixes(notMet) : null);
    }),
    unchecked.length ? line(doneNow === uncheckedNow.length ? "ok" : "unchecked", "Checklist",
      [`${doneAll} of ${nDuties(unchecked.length)} a document can't show ${doneAll === 1 ? "is" : "are"} ticked off`
        + (uncheckedNow.length ? ` — ${doneNow} of the ${uncheckedNow.length} that already apply. ` : ". "),
        el("a", { href: "#duties", onclick: (e) => { e.preventDefault(); $("duties")?.scrollIntoView({ behavior: "smooth" }); } }, "See the list")]) : null,
  ) : null;

  const roles = [...new Set([...report.findings.map((f) => f.role), ...Object.values(owners).flatMap((o) => [...o])])];
  const visible = roles.filter((r) => !hidden.has(r));
  return el("section", { class: `card compliance ${state}` },
    el("div", { class: "eyebrow" }, "Verdict", data.demo ? el("span", { class: "tag demo-tag" }, "Demo") : null),
    el("div", { class: "answer" }, answer),
    el("p", {}, detail),
    hidden.size && visible.length < roles.length ? el("p", { class: "scope" }, "For ",
      visible.map((r, i) => [i ? ", " : "", roleTag(r)]), " only — as set in the Operator filter below.") : null,
    statuses,
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
function provisions(report, data, ruleDate, normDate, isFuture) {
  const present = new Set([
    ...report.findings.map((f) => f.role),
    ...Object.keys(report.not_document_verifiable),
    ...Object.keys(report.conditional_duties || {}),
    ...report.timing_not_active.map((t) => t.role),
    ...NORM_SECTIONS.flatMap((key) => Object.keys(report[key])),
  ]);
  const order = [...ROLE_ORDER.filter((r) => present.has(r)), ...[...present].filter((r) => !ROLE_ORDER.includes(r))];

  // Each unjudged item, keyed "<kind>:<id>", with the parties that owe it in role order.
  const owners = {};
  const add = (key, role) => { if (!(owners[key] ||= []).includes(role)) owners[key].push(role); };
  for (const role of order) {
    for (const id of report.not_document_verifiable[role] || []) add(`rule:${id}`, role);
    for (const id of report.conditional_duties?.[role] || []) add(`cond:${id}`, role);
    // A duty that starts later is listed with the others and its date; one whose date turns on an
    // unsettled Art. 6 route has a group of its own.
    for (const t of report.timing_not_active.filter((t) => t.role === role)) {
      add(`${t.status === "upcoming" ? "rule" : "route"}:${t.rule_id}`, role);
    }
    for (const key of NORM_SECTIONS) for (const id of report[key][role] || []) add(`${key}:${id}`, role);
  }
  const ids = (prefix) => Object.keys(owners).filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length));
  const partiesOf = (prefix) => (id) => owners[`${prefix}${id}`];
  const findings = [...report.findings].sort((a, b) => order.indexOf(a.role) - order.indexOf(b.role));

  const duties = dutyGroups({ outstanding: ids("rule:"), conditional: ids("cond:"), unresolved: ids("route:") },
    findings, { data, ruleDate, normDate, isFuture, partiesOf });
  // One list: the reader's permissions, rights and effects together with what authorities must or
  // may do, each tagged with who it names and labelled with its kind. The role filter separates
  // them, as it does the duties.
  const authorityIds = report.public_authority_statements.filter((id) => data.norms[id]);
  const authorities = [...new Set(authorityIds.flatMap((id) => data.norms[id].actors || []))];
  const rows = [
    ...NORM_SECTIONS.flatMap((key) => ids(`${key}:`).map((id) => [id, partiesOf(`${key}:`)(id)])),
    ...authorityIds.map((id) => [id, data.norms[id].actors || []]),
  ].sort(([a], [b]) => byCitation(normCites(data.norms[a])[0], normCites(data.norms[b])[0]));
  const others = rows.length ? [group("", null, null, rows.map(([id, roles]) => normItem(id, data, roles)))] : [];
  const card = (groups, facets, columns, ...bars) => (groups.length
    ? el("section", { class: "card provisions" }, el("div", { class: "filters" }, filterBars(groups, facets), ...bars),
      el("div", { class: "columns", "aria-hidden": "true" }, columns.map((c) => el("span", {}, c))), groups) : null);
  return {
    duties: card(duties, [["roles", roleOptions(order)], ["result", RESULT_OPTIONS]],
      ["Check result", "Article", "Duty", "Applies from"], whenFilter()),
    others: card(others, [["roles", roleOptions([...order, ...authorities]), authorities.length ? "Operator or authority:" : undefined],
      ["kind", KIND_OPTIONS()]],
      ["Type", "Article", "Provision", ""]),
  };
}

const roleTag = (role) => el("span", { class: `role-tag r-${role}` }, human(role));

// ---- filters -----------------------------------------------------------------------------------
// Each list has a bar of filters on top. A tag filter hides the rows carrying a value the reader
// switched off: a role (a row shows while any of its parties is on), a result or a provision type.
// A group with no row left showing is hidden. Choices are shared by every bar on the page and
// remembered in this browser.
const ROLES_KEY = "aiact-review:hidden-roles";
const FACETS = {
  roles: { key: ROLES_KEY, label: "Operator:", many: true },
  result: { key: "aiact-review:hidden-results", label: "Check result:" },
  kind: { key: "aiact-review:hidden-kinds", label: "Type:" },
};
let filters = []; // [{ groups, bars: [{ facet, buttons, reset }] }] for every list on the page

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

const hiddenOf = (facet) => new Set(restore(FACETS[facet].key) || []);

function applyFilters() {
  const hidden = Object.fromEntries(Object.keys(FACETS).map((f) => [f, hiddenOf(f)]));
  const when = restore(WHEN_KEY) || "all";
  for (const b of whenButtons) b.classList.toggle("on", b.dataset.when === when);
  const excluded = (item) => Object.keys(FACETS).some((facet) => {
    const value = item.dataset[facet];
    if (value === undefined) return false;
    return FACETS[facet].many ? value.split(",").every((v) => hidden[facet].has(v)) : hidden[facet].has(value);
  }) || (when !== "all" && item.dataset.when !== undefined && item.dataset.when !== when);
  for (const { groups, bars } of filters) {
    for (const g of groups) {
      let shown = 0;
      for (const item of g.querySelectorAll("details.item")) {
        item.hidden = excluded(item);
        if (!item.hidden) shown += 1;
      }
      g.hidden = !shown;
      const count = g.querySelector(".count");
      if (count) count.textContent = `· ${shown}`;
    }
    for (const { facet, buttons, reset } of bars) {
      for (const b of buttons) b.classList.toggle("off", hidden[facet].has(b.dataset.value));
      reset.hidden = !hidden[facet].size;
    }
  }
  refreshVerdict?.(); // the verdict follows the Operator filter
}

// A bar of toggles for one facet, over the values the list's rows carry, in the order given.
// `options` is [[value, label, class]]; no bar when fewer than two values are present.
function tagFilter(facet, groups, options, label = FACETS[facet].label) {
  const present = new Set(groups.flatMap((g) => [...g.querySelectorAll(`[data-${facet}]`)]
    .flatMap((i) => (FACETS[facet].many ? i.dataset[facet].split(",") : [i.dataset[facet]]))));
  const shown = options.filter(([value]) => present.has(value));
  if (shown.length < 2) return null;
  const toggle = (value) => {
    const hidden = hiddenOf(facet);
    hidden.has(value) ? hidden.delete(value) : hidden.add(value);
    store(FACETS[facet].key, [...hidden]);
    applyFilters();
  };
  const buttons = shown.map(([value, label, cls]) => el("button", {
    type: "button", class: cls, "data-value": value, "data-define": facet === "roles" ? value : undefined,
    "aria-label": `Show or hide: ${label}`, onclick: () => toggle(value),
  }, label));
  const reset = el("button", { type: "button", class: "link", onclick: () => { store(FACETS[facet].key, []); applyFilters(); } }, "Show all");
  return { facet, buttons, reset, bar: el("div", { class: "role-filter" }, el("span", { class: "lbl" }, label), buttons, reset) };
}

// The filter bars of one list, registered so a choice in any bar re-applies everywhere.
function filterBars(groups, facets) {
  const bars = facets.map(([facet, options, label]) => tagFilter(facet, groups, options, label)).filter(Boolean);
  filters.push({ groups, bars });
  queueMicrotask(applyFilters); // once the list is on the page
  return bars.map((b) => b.bar);
}

const roleOptions = (roles) => roles.map((r) => [r, human(r), `role-tag r-${r}`]);
const RESULT_OPTIONS = [...["gap", "inadequate", "needs_review", "pass"].map((v) => [v, VERDICT[v], `tag ${v}`]),
                        ["check", "Duty", "tag needs_review"], ["done", "Done", "tag pass"]];
const KIND_OPTIONS = () => KIND_ORDER.map((k) => [k, NORM_KIND[k], `tag soft kind-${k}`]);

function dutyGroups(parts, findings, { data, ruleDate, normDate, isFuture, partiesOf }) {
  // In the order of the Act; the date column and filter say when each applies.
  const ruleCite = (id) => data.rules[id]?.citation || "";
  const checked = [...findings].sort((a, b) => byCitation(ruleCite(a.rule_id), ruleCite(b.rule_id)));
  const rule = partiesOf("rule:");
  const route = partiesOf("route:");
  const cond = partiesOf("cond:");
  // The unjudged rules and the duties that bind only under a condition, together.
  const outstanding = [
    ...parts.outstanding.map((id) => [ruleCite(id), () => outstandingItem(id, data, ruleDate(id), isFuture(ruleDate(id)), rule(id))]),
    ...parts.conditional.map((id) => [normCites(data.norms[id])[0], () => conditionalDutyItem(id, data, normDate(id), isFuture(normDate(id)), cond(id))]),
  ].sort(([a], [b]) => byCitation(a, b));
  return [
    checked.length ? group("", "Checked against your document", null, checked.map((f) => findingItem(f, data))) : null,
    outstanding.length ? group("", "Not verifiable from documentation", "The review doesn't check these. Check each one yourself.",
      outstanding.map(([, item]) => item())) : null,
    parts.unresolved.length ? group("", "Date depends on the Art. 6 route", "Not checked: when these apply turns on how the system is classified.",
      [...parts.unresolved].sort((a, b) => byCitation(ruleCite(a), ruleCite(b)))
        .map((id) => outstandingItem(id, data, null, false, route(id), "unknown"))) : null,
  ].filter(Boolean);
}

// The "Applies from" cell: now, a later date, or unknown where the date turns on the Art. 6 route.
// A duty in force with a deadline the provision sets (Art. 111) shows that deadline instead of "Now".
function appliesFrom(when, date, by = null) {
  if (when === "future") return el("span", { class: "tag date" }, `from ${fmtDate(date)}`);
  if (when === "now" && by) return el("span", { class: "tag date" }, `by ${fmtDate(by)}`);
  return el("span", { class: "tag soft" }, when === "unknown" ? "Date unknown" : "Now");
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
    title ? el("h3", {}, title, el("span", { class: "muted count" }, `· ${items.length}`)) : null,
    hint ? el("p", { class: "hint" }, hint) : null,
    items);
}

function kv(label, ...value) {
  return el("div", { class: "kv" }, el("div", { class: "l" }, label), el("div", {}, value));
}

function findingItem(f, data) {
  const rule = data.rules[f.rule_id];
  return el("details", { class: "item", id: itemId(f), "data-roles": f.role, "data-result": f.verdict, "data-when": f.applies_from ? "future" : "now" },
    el("summary", {},
      el("span", {}, el("span", { class: `tag ${f.verdict}` }, VERDICT[f.verdict] || human(f.verdict))),
      el("span", { class: "cite" }, rule?.citation || citeSource(f.citation)),
      what(rule?.action || rule?.requirement || f.rule_id, [f.role]),
      el("span", { class: "when" }, appliesFrom(f.applies_from ? "future" : "now", f.applies_from, rule?.deadline))),
    el("div", { class: "item-body" },
      plainWords(rule),
      kv("Finding", findingText(f)),
      rule ? actSays(rule.requirement) : null,
      refersTo(rule?.references),
      kv("Evidence", f.evidence_quote ? el("blockquote", {}, f.evidence_quote)
        : el("span", { class: "muted" }, "No passage in the document was cited.")),
      f.criteria.length ? kv("Criteria", el("ul", { class: "criteria" }, f.criteria.map((c) =>
        el("li", {}, el("span", {}, el("span", { class: `tag ${c.verdict}` }, VERDICT[c.verdict] || human(c.verdict))),
          el("span", {}, criterionTitle(rule, c), c.mandatory ? "" : " (not judged)",
            c.mandatory && c.verdict !== "pass"
              ? el("div", { class: `why ${c.verdict}` }, el("span", { class: "why-icon", "aria-hidden": "true" }, "!"), el("span", {}, c.reasoning)) : null))))) : null,
      rule?.activation_condition ? kv("Applies to", rule.activation_condition) : null,
      kv("Confidence", human(f.confidence)),
      f.guidance.length ? kv("Guidance", "Reached with non-binding Commission guidance in view.") : null,
      rule?.effective_date_note ? kv("Date note", rule.effective_date_note) : null),
  );
}

function outstandingItem(id, data, date, future, roles, when = future ? "future" : "now") {
  const rule = data.rules[id];
  return el("details", { class: "item", "data-roles": roles.join(","), "data-result": doneSet().has(id) ? "done" : "check", "data-when": when },
    el("summary", {},
      el("span", {}, doneToggle(id)),
      el("span", { class: "cite" }, rule?.citation || ""),
      what(rule?.action || rule?.requirement || id, roles),
      el("span", { class: "when" }, appliesFrom(when, date, rule?.deadline))),
    el("div", { class: "item-body" },
      plainWords(rule),
      rule ? kv("What to check", rule.evidence_expected) : null,
      rule ? actSays(rule.requirement) : null,
      refersTo(rule?.references),
      rule?.activation_condition ? kv("Applies to", rule.activation_condition) : null,
      rule?.effective_date_note ? kv("Date note", rule.effective_date_note) : null),
  );
}

// A finding judged part by part carries a summary built from the parts' internal ids; the parts are
// listed in full below it, so the summary is said in words instead.
function findingText(f) {
  const judged = f.criteria.filter((c) => c.mandatory);
  if (!judged.length) return f.reasoning;
  const open = judged.filter((c) => c.verdict !== "pass").length;
  return open ? `${open} of ${judged.length} parts of this duty are not met. Each one is listed below.`
    : `All ${judged.length} parts of this duty are met.`;
}

// A criterion as its provision and what it requires. Reports saved before criteria were sent
// carry no titles; the refresh fills them in.
function criterionTitle(rule, c) {
  const criterion = rule?.criteria?.[c.norm_id];
  return criterion ? [el("b", {}, criterion.citation), ` — ${criterion.action}`] : "";
}

// A duty that binds only under a condition the review cannot settle: listed with that condition
// for the reader to check.
function conditionalDutyItem(id, data, date, future, roles) {
  const norm = data.norms[id];
  return el("details", { class: "item", "data-roles": roles.join(","), "data-result": doneSet().has(id) ? "done" : "check", "data-when": future ? "future" : "now" },
    el("summary", {},
      el("span", {}, doneToggle(id)),
      el("span", { class: "cite" }, normCites(norm)[0] || ""),
      what(norm?.action || id, roles),
      el("span", { class: "when" }, appliesFrom(future ? "future" : "now", date))),
    el("div", { class: "item-body" },
      plainWords(norm),
      norm?.law ? actSays(norm.law) : null,
      refersTo(norm?.references),
      norm?.conditions ? kv("Only if", unwrap(norm.conditions)) : null,
      norm?.exceptions ? kv("Except", unwrap(norm.exceptions)) : null,
      norm ? (norm.basis?.length ? refersTo(norm.basis, "Basis") : kv("Basis", normCites(norm).join(", "))) : null),
  );
}

// ---- what a row means ---------------------------------------------------------------------------
// One to three plain sentences, written once per row and stored with the ruleset. An explanation the
// user has not reviewed yet says so.
function plainWords(row) {
  if (!row?.explanation) return null;
  return el("div", { class: "plain" },
    el("div", { class: "plain-head" }, "In plain words"),
    el("p", {}, row.explanation));
}

// ---- the Act's words, and what they point at ---------------------------------------------------
// Every row, duty or not, opens to the paragraph it comes from, and to the other articles and
// annexes that paragraph cites. A cited provision's text is fetched only when the reader opens it.
const actSays = (text) => kv("The Act says", el("div", { class: "law" }, text));

// A condition reads as a quoted fragment; its outer brackets add nothing on their own.
const unwrap = (text) => String(text).replace(/^\((.*)\)$/s, "$1");

function refersTo(references, label = "Refers to") {
  if (!references?.length) return null;
  return kv(label, el("div", { class: "refs" }, references.map((ref) => {
    const body = el("div", { class: "law" }, el("span", { class: "muted" }, "Loading…"));
    const item = el("details", { class: "ref" },
      el("summary", {}, el("b", {}, ref.citation), ref.title ? ` — ${ref.title}` : ""), body);
    item.addEventListener("toggle", async () => {
      if (!item.open || item.dataset.loaded) return;
      item.dataset.loaded = "1";
      try {
        const response = await fetch(`/api/provision/${encodeURIComponent(ref.key)}`);
        if (!response.ok) throw new Error(response.statusText);
        body.replaceChildren((await response.json()).text);
      } catch {
        delete item.dataset.loaded;
        body.replaceChildren(el("span", { class: "muted" }, "Could not load this provision. Close and open it to try again."));
      }
    });
    return item;
  })));
}

// Reports saved before citations were added carry only the segment ids.
const normCites = (norm) => norm?.citations || norm?.source_spans || [];

function normItem(id, data, roles = null) {
  const norm = data.norms[id];
  return el("details", { class: "item", "data-roles": roles ? roles.join(",") : undefined, "data-kind": norm?.kind },
    el("summary", {},
      el("span", {}, el("span", { class: `tag soft kind-${norm?.kind}` }, NORM_KIND[norm?.kind] || human(norm?.kind || "norm"))),
      el("span", { class: "cite" }, normCites(norm)[0] || ""),
      what(norm?.action || id, roles),
      el("span", {})),
    el("div", { class: "item-body" },
      plainWords(norm),
      norm?.law ? actSays(norm.law) : null,
      refersTo(norm?.references),
      norm?.conditions ? kv("Only if", unwrap(norm.conditions)) : null,
      norm?.exceptions ? kv("Except", unwrap(norm.exceptions)) : null,
      norm ? (norm.basis?.length ? refersTo(norm.basis, "Basis") : kv("Basis", normCites(norm).join(", "))) : null),
  );
}

// ---- role definitions --------------------------------------------------------------------------
// Hovering or focusing a role in a filter shows what the role means: the Act's Article 3 definition,
// or, for a role Article 3 does not define, a summary of where the Act sets it up. The definitions
// come from the server once; a page without them just shows no tooltip.
let roleDefinitions = {};
fetch("/api/roles").then((r) => (r.ok ? r.json() : {})).then((d) => { roleDefinitions = d; }).catch(() => {});

const tooltip = el("div", { class: "definition", role: "tooltip", hidden: true });

function showDefinition(target) {
  const def = roleDefinitions[target.dataset.define];
  if (!def) return;
  // replaceChildren would print a null as text.
  tooltip.replaceChildren(...[
    el("div", { class: "def-head" }, el("b", {}, human(target.dataset.define)), el("span", { class: "muted" }, def.citation)),
    el("p", {}, def.text),
    def.defined ? null : el("p", { class: "muted small" }, "Not defined in Art. 3 — a summary of where the Act sets this role up."),
  ].filter(Boolean));
  tooltip.hidden = false;
  const box = target.getBoundingClientRect();
  const width = Math.min(420, window.innerWidth - 32);
  tooltip.style.width = `${width}px`;
  tooltip.style.left = `${Math.max(16, Math.min(box.left, window.innerWidth - width - 16)) + window.scrollX}px`;
  tooltip.style.top = `${box.bottom + 8 + window.scrollY}px`;
}

function hideDefinition() { tooltip.hidden = true; }

for (const [event, handler] of [["mouseover", showDefinition], ["focusin", showDefinition]]) {
  document.addEventListener(event, (e) => { const t = e.target.closest?.("[data-define]"); if (t) handler(t); });
}
for (const event of ["mouseout", "focusout"]) {
  document.addEventListener(event, (e) => { if (e.target.closest?.("[data-define]")) hideDefinition(); });
}
window.addEventListener("scroll", hideDefinition, { passive: true });

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
  document.body.append(tooltip);
  for (const b of document.querySelectorAll("#theme button")) b.addEventListener("click", () => setTheme(b.dataset.theme));
  setTheme(document.documentElement.dataset.theme || "auto");
  $("form").addEventListener("submit", runReview);
  migrateSaved();
  // The saved choice first, so nothing flashes; then the server's word on whether a model exists.
  setDemo(restore(DEMO_KEY) === true, { save: false });
  $("demo-switch").addEventListener("click", () => setDemo(!demo));
  $("modebar-off").addEventListener("click", () => setDemo(false));
  $("demo-float-off").addEventListener("click", () => setDemo(false));
  $("show-doc").addEventListener("click", () => showDocument(!$("form").classList.contains("doc-shown")));
  fetch("/api/mode").then((r) => r.json()).then((info) => {
    modeInfo = { ...modeInfo, ...info };
    setDemo(demo, { save: false });
  }).catch(() => {});
  loadSamples();
  $("document").addEventListener("input", () => { countChars(); saveDraft(); markCase(null); });
  $("edit").addEventListener("click", () => { setMode("edit"); $("document").focus(); });
  $("new").addEventListener("click", () => {
    markCase(null);
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

  fetch("/api/limits").then((r) => r.json()).then((limits) => {
    maxChars = limits.max_document_chars || null;
    countChars();
  }).catch(() => {});
});
