// Shared state, URL hash, filter panel and routing for every view.

const UNDECIDED = new Set(["missing", "unresolved"]);
let DATA;
const VIEWS = {};
const SETS = ["actors", "status", "scope", "kind", "source", "timing", "has", "rtype", "risk", "checks"];
const STRINGS = ["view", "q", "nq", "rq", "doc", "id", "rule", "asof"];
const state = { gaps: false };

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
const count = (items, key) => items.reduce((acc, item) => {
  for (const v of [].concat(item[key])) acc[v] = (acc[v] || 0) + 1; return acc; }, {});
// A value tag that names its field, so "presence" reads as "check: presence".
const ftag = (field, value, cls = "") => el("span", { class: `tag ${cls}`.trim() }, el("span", { class: "k" }, `${field}: `), value);
const chev = () => el("span", { class: "chev" });
const pass = (set, value) => !set.size || [].concat(value).some((v) => set.has(v));
const docLabel = (key) => {
  const [kind, number] = key.split(":");
  return (kind === "article" ? "Art. " : "Annex ") + (kind === "annex" ? number.toUpperCase() : number);
};

// ---- state <-> URL hash, so every view can be linked -------------------------------------------
function readHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  for (const k of STRINGS) state[k] = params.get(k) || "";
  for (const k of SETS) state[k] = new Set((params.get(k) || "").split(",").filter(Boolean));
  state.gaps = params.get("gaps") === "1";
  if (!VIEWS[state.view]) state.view = "rules";
}
function hashFor(overrides = {}) {
  const merged = { ...state, ...overrides };
  const params = new URLSearchParams();
  for (const k of STRINGS) if (merged[k] && !(k === "view" && merged[k] === "rules")) params.set(k, merged[k]);
  for (const k of SETS) if (merged[k].size) params.set(k, [...merged[k]].join(","));
  if (merged.gaps) params.set("gaps", "1");
  return "#" + params.toString();
}
function writeHash() { history.replaceState(null, "", hashFor()); }
function go(overrides) { location.hash = hashFor(overrides); }

// ---- filters -----------------------------------------------------------------------------------
const expanded = new Set();
function chipRow(label, key, counts, { fmt = (v) => v, limit = 12, order, extra } = {}) {
  const all = order ? order.filter((v) => v in counts) : Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
  const values = expanded.has(key) ? all : all.filter((v, i) => i < limit || state[key].has(v));
  const more = all.length - values.length;
  return el("div", { class: "frow" }, el("span", { class: "lbl" }, label),
    values.map((v) => el("button", {
      class: "chip" + (state[key].has(v) ? " on" : ""),
      onclick: () => { state[key].has(v) ? state[key].delete(v) : state[key].add(v); render(); },
    }, fmt(v), el("span", { class: "n" }, counts[v]))),
    more ? el("button", { class: "link", onclick: () => { expanded.add(key); renderFilters(); } }, `+${more} more`) : null,
    extra || null,
    state[key].size ? el("button", { class: "link", onclick: () => { state[key].clear(); render(); } }, "clear") : null);
}
function searchBox(key, placeholder) {
  const box = el("input", { type: "search", placeholder, value: state[key] });
  box.addEventListener("input", () => { state[key] = box.value; VIEWS[state.view].render(); writeHash(); });
  return box;
}
function activeFilters() {
  const view = VIEWS[state.view];
  const own = view.activeFilters?.() || 0;
  if (view.ownFilters) return own;
  return ["actors", "status", "scope", "kind", "source"].reduce((n, k) => n + state[k].size, 0) + own;
}
function renderFilters() {
  const view = VIEWS[state.view];
  const active = activeFilters();
  const reset = () => go({ q: "", nq: "", rq: "", doc: "", id: "", rule: "", asof: "", gaps: false,
    ...Object.fromEntries(SETS.map((k) => [k, new Set()])) });
  document.getElementById("filters").replaceChildren(
    el("summary", {}, chev(), "Filters", active ? el("span", { class: "badge" }, active) : null,
       active ? el("button", { class: "link", onclick: (e) => { e.preventDefault(); reset(); } }, "Reset all") : null),
    el("div", { class: "fbody" },
      view.filterHead(),
      view.ownFilters ? view.filterRows() : [
      chipRow("Actor", "actors", count(DATA.norms, "actors")),
      chipRow("Review", "status", count(DATA.norms, "status")),
      chipRow("Scope", "scope", count(DATA.norms, "scope")),
      chipRow("Norm kind", "kind", count(DATA.norms, "kind")),
      chipRow("Source", "source", count(DATA.documents, "kind"), { fmt: (v) => v + "s" }),
      view.filterRows?.() || []]),
  );
}
function normFilter(n) {
  return pass(state.actors, n.actors) && pass(state.status, n.status)
      && pass(state.scope, n.scope) && pass(state.kind, n.kind)
      && pass(state.source, n.doc.split(":")[0]);
}

// ---- routing -----------------------------------------------------------------------------------
function render() {
  for (const tab of document.querySelectorAll("#tabs a"))
    tab.classList.toggle("on", tab.dataset.view === state.view);
  for (const node of document.querySelectorAll("[data-for]"))
    node.hidden = node.dataset.for !== state.view;
  renderFilters();
  if (state.id || state.rule) document.getElementById("filters").open = false;
  VIEWS[state.view].render();
  writeHash();
  // After a live data refresh, keep the reader where they were once the view has drawn.
  if (pendingScroll !== null && (state.view === "map" || CARDS)) {
    window.scrollTo(0, pendingScroll);
    pendingScroll = null;
  }
}

// ---- theme -------------------------------------------------------------------------------------
function setTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try { theme === "auto" ? localStorage.removeItem("theme") : localStorage.setItem("theme", theme); } catch {}
  for (const b of document.querySelectorAll("#theme button")) b.classList.toggle("on", b.dataset.theme === theme);
}

// ---- live data -----------------------------------------------------------------------------------
// Views register a reset for anything they cached from the payloads.
const ON_NEW_DATA = [];
let pendingScroll = null;

function loadCoverage() {
  return fetch("/api/coverage").then((r) => {
    if (!r.ok) return r.json().then((body) => Promise.reject(new Error(body.detail || r.statusText)));
    return r.json();
  }).then((data) => {
    DATA = data;
    for (const reset of ON_NEW_DATA) reset();
    document.getElementById("meta").replaceChildren(
      el("span", {}, "Act version ", el("b", {}, data.act_version_date)),
      el("span", {}, el("b", {}, data.norms.length), " norms"),
      el("span", {}, el("b", {}, data.rules.length), " rules"));
  });
}

function showError(message) {
  const banner = document.getElementById("banner");
  banner.hidden = !message;
  banner.textContent = message ? `The data on disk does not load, so this page shows the last good version. ${message}` : "";
}

// Polls the server; new data is fetched in place, new page files reload the page.
function watch() {
  let seen = null, busy = false;
  setInterval(async () => {
    if (busy) return;
    busy = true;
    try {
      const version = await fetch("/api/version").then((r) => r.json());
      showError(version.error);
      if (seen && version.page !== seen.page) location.reload();
      else if (seen && version.data !== seen.data && !version.error) {
        pendingScroll = window.scrollY;
        await loadCoverage();
        render();
      }
      seen = version;
    } catch {
      // The server is restarting after a code change; try again on the next tick.
    } finally {
      busy = false;
    }
  }, 3000);
}

window.addEventListener("DOMContentLoaded", () => {
  for (const b of document.querySelectorAll("#theme button")) b.addEventListener("click", () => setTheme(b.dataset.theme));
  setTheme(document.documentElement.dataset.theme || "auto");
  for (const tab of document.querySelectorAll("#tabs a"))
    tab.addEventListener("click", (e) => { e.preventDefault(); go({ view: tab.dataset.view }); });
  loadCoverage().then(() => {
    readHash(); render();
    window.addEventListener("hashchange", () => { readHash(); render(); window.scrollTo(0, 0); });
  }).catch((err) => { document.getElementById("meta").textContent = "Failed to load: " + err.message; });
  watch();
});
