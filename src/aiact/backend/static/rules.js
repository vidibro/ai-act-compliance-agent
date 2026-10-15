// Rules: what decides an outcome. Classification questions set the risk class; gap rules decide
// the gap report. Under each, the norms it rests on, read as sentences with their links.

const CHECKS = { verifiable: "document-verifiable", not_verifiable: "confirm separately",
                 has_cases: "has golden case", no_cases: "verifiable, no golden case", guidance: "uses guidance",
                 no_date: "no date recorded", no_norms: "no norm linked" };
const RULE_PAGE = 20;
const RULE_IDX = { norms: {} };
let RULE_IDX_READY = false;
ON_NEW_DATA.push(() => { RULE_IDX.norms = {}; RULE_IDX_READY = false; });

const human = (v) => cap(String(v).replaceAll("_", " "));

// ---- which norms each rule or question rests on ------------------------------------------------
function indexRules() {
  if (RULE_IDX_READY) return;
  const add = (target, normId, role) => {
    const list = (RULE_IDX.norms[target] ||= []);
    if (!list.some((x) => x.id === normId)) list.push({ id: normId, role });
  };
  for (const [id, rule] of Object.entries(CARDS.rules)) for (const n of rule.criteria) add(id, n, "judged");
  for (const norm of Object.values(CARDS.norms))
    for (const ref of norm.implementation_refs) add(ref, norm.norm_id, ref.startsWith("AIA-CQ-") ? "answers" : "implemented here");
  for (const rel of CARDS.relations)
    for (const ref of rel.target_rule_ids) add(ref, rel.source_norm_id, RELATIONS[rel.kind] ? `${RELATIONS[rel.kind]} this rule` : rel.kind);
  for (const link of CARDS.interpretations)
    for (const target of link.targets) for (const n of link.norm_ids) add(target, n, "read via guidance");
  RULE_IDX_READY = true;
}
function ruleItems() {
  const cases = Object.fromEntries(DATA.rules.map((r) => [r.id, r]));
  const questions = CARDS.questions.map((q) => ({ type: "classification", id: q.id, q,
    roles: [], risk: [], checks: q.guidance_refs.length ? ["guidance"] : [] }));
  const rules = Object.entries(CARDS.rules).map(([id, r]) => {
    const c = cases[id] || {};
    const checks = [r.document_verifiable ? "verifiable" : "not_verifiable"];
    if (c.cases_dev) checks.push("has_cases");
    else if (r.document_verifiable) checks.push("no_cases");
    if (r.guidance_refs.length) checks.push("guidance");
    if (!r.applies_from && !Object.keys(r.applies_from_by_route || {}).length) checks.push("no_date");
    return { type: "gap", id, r, c, roles: r.roles, risk: r.risk_classes, checks };
  });
  const all = [...questions, ...rules];
  for (const item of all) if (!(RULE_IDX.norms[item.id] || []).length) item.checks.push("no_norms");
  return all;
}
function itemMatches(item) {
  if (state.rule) return item.id === state.rule;
  if (!pass(state.rtype, item.type) || !pass(state.actors, item.roles)
      || !pass(state.risk, item.risk) || !pass(state.checks, item.checks)) return false;
  const q = state.rq.trim().toLowerCase();
  if (!q) return true;
  const text = item.q ? `${item.id} ${item.q.label} ${item.q.text} ${item.q.source}`
                      : `${item.id} ${item.r.action || ""} ${item.r.requirement} ${item.r.source} ${item.r.evidence_expected || ""}`;
  return text.toLowerCase().includes(q);
}

// ---- one rule ----------------------------------------------------------------------------------
const lineOf = (lead, ...body) => el("div", { class: "line" }, el("span", { class: "lead" }, lead), el("div", {}, body));
const tags = (field, xs, cls) => xs.map((x) => ftag(field, human(x), cls));

function normsSection(target, title, openByDefault) {
  const entries = (RULE_IDX.norms[target] || []).filter((e) => CARDS.norms[e.id]);
  if (!entries.length) return el("div", { class: "nonorms" }, "No norm points to this rule yet.");
  const body = el("div", { class: "secbody nblocks" });
  const sec = el("details", { class: "sec", open: openByDefault ? "" : null },
    el("summary", {}, chev(), title, el("span", { class: "n" }, entries.length)), body);
  const fill = () => {
    if (body.childElementCount) return;
    body.append(...entries.map((e) => normBlock(CARDS.norms[e.id], e.role)));
  };
  if (openByDefault) fill();
  sec.addEventListener("toggle", () => sec.open && fill());
  return sec;
}
function guidanceRefsSection(refs) {
  if (!refs.length) return null;
  return section("Guidance", refs.length, refs.map((ref) => {
    const s = CARDS.snippets[ref];
    return el("details", { class: "sub" }, el("summary", {}, chev(), s ? `${s.document} · ${s.topic}` : ref),
      s ? el("div", { class: "secbody" }, el("div", { class: "muted" }, s.locator, s.binding ? "" : " · not binding"),
        el("blockquote", {}, s.body)) : null);
  }));
}
function requirementText(text) {
  const box = el("div", { class: "req clamp" }, text);
  if (text.length > 320) {
    const more = el("button", { class: "link", onclick: () => {
      box.classList.toggle("clamp"); more.textContent = box.classList.contains("clamp") ? "Show full text" : "Show less"; } }, "Show full text");
    return [box, more];
  }
  return box;
}
const ruleLink = (id, text) => el("a", { class: "idlink mono", href: hashFor({ view: "rules", rule: id }) }, text || id);

function questionCard(q, step) {
  return el("article", { class: "rcard", id: q.id },
    el("header", {},
      el("span", { class: "kind cls" }, "classification"),
      el("span", { class: "muted" }, `Step ${step}`),
      ruleLink(q.id),
      el("span", { class: "muted" }, q.source),
      el("span", { class: "spacer" }),
      ftag("answer", human(q.answer_type))),
    el("div", { class: "rtitle" }, q.label),
    el("div", { class: "lines" }, lineOf("asks", el("span", { class: "quote" }, q.text))),
    el("div", { class: "secs" },
      normsSection(q.id, "Norms answered here", Boolean(state.rule)),
      guidanceRefsSection(q.guidance_refs)));
}
function whenLine(r) {
  const parts = [];
  if (r.applies_from) parts.push(`Applies from ${fmtDate(r.applies_from)}`);
  const routes = Object.entries(r.applies_from_by_route || {});
  if (routes.length) parts.push("Applies from " + routes.map(([k, d]) => `${fmtDate(d)} (${ROUTES[k] || human(k)})`).join(" or "));
  if (r.deadline) parts.push(`to be met by ${fmtDate(r.deadline)}`);
  if (r.effective_date_note) parts.push(r.effective_date_note);
  return lineOf("when", parts.length ? parts.join("; ") : el("span", { class: "warn" }, "No date recorded on this rule."));
}
function gapCard(item) {
  const { r, c } = item;
  const cases = r.document_verifiable
    ? ftag("golden cases", `${c.cases_dev || 0} dev · ${c.cases_heldout || 0} held-out`, c.cases_dev ? "" : "bad")
    : null;
  const scope = [
    r.route ? ftag("route", ROUTES[r.route] || human(r.route)) : null,
    ...tags("transparency duty", r.transparency_duties), ...tags("Annex III area", r.annex_iii_areas), ...tags("Annex I product", r.annex_i_products || []),
    ...tags("prohibited practice", r.prohibited_practices),
    r.requires_provider_reallocation ? el("span", { class: "tag part" }, "only after provider reallocation") : null,
    r.requires_real_world_testing ? el("span", { class: "tag part" }, "only with real-world testing") : null,
  ];
  return el("article", { class: "rcard", id: item.id },
    el("header", {},
      el("span", { class: "kind" }, "gap rule"),
      ruleLink(item.id),
      el("span", { class: "muted" }, r.source),
      el("span", { class: "spacer" }),
      tags("risk class", r.risk_classes, "risk"),
      ftag("check", r.check_type),
      ftag("docs", r.document_verifiable ? "verifiable" : "confirm separately"),
      cases),
    r.action
      ? el("div", { class: "rtitle" }, r.action)
      : el("div", { class: "rtitle" }, el("span", { class: "subj" }, joinAnd(r.roles.map(actorName))), " ",
          el("span", { class: "modal" }, "must meet"), " ", r.source),
    el("div", { class: "lines" },
      r.action ? lineOf("owed by", joinAnd(r.roles.map(actorName))) : null,
      lineOf("requires", requirementText(r.requirement)),
      scope.some(Boolean) ? lineOf("applies to", scope) : null,
      r.activation_condition ? lineOf("only if", r.activation_condition) : null,
      r.qualified_by.length ? lineOf("qualified by", r.qualified_by.join("; ")) : null,
      whenLine(r)),
    el("div", { class: "secs" },
      normsSection(item.id, "Norms this rule rests on", Boolean(state.rule)),
      r.evidence_expected ? section("Evidence expected", null, el("div", { class: "req" }, r.evidence_expected)) : null,
      guidanceRefsSection(r.guidance_refs)));
}

// ---- list --------------------------------------------------------------------------------------
function renderRules() {
  const box = document.getElementById("rules");
  if (!ensureCards(box)) return;
  indexRules();
  const items = ruleItems().filter(itemMatches);
  const steps = Object.fromEntries(CARDS.questions.map((q, i) => [q.id, i + 1]));
  const groups = [
    ["Classification questions", "decide the risk class, in cascade order", items.filter((i) => i.type === "classification")],
    ["Gap rules", "decide what the gap report asks the documentation for", items.filter((i) => i.type === "gap")],
  ];
  const nodes = [];
  if (state.rule) nodes.push(el("button", { class: "link back", onclick: () => go({ rule: "" }) }, "← All rules"));
  for (const [title, note, list] of groups) {
    if (!list.length) continue;
    const holder = el("div", { class: "cardlist" });
    const more = el("button", { class: "morebtn" });
    let shownRules = RULE_PAGE;
    const fill = () => {
      holder.append(...list.slice(holder.children.length, shownRules).map((i) =>
        i.type === "classification" ? questionCard(i.q, steps[i.id]) : gapCard(i)));
      more.hidden = shownRules >= list.length;
      more.textContent = `Show ${Math.min(RULE_PAGE, list.length - shownRules)} more of ${list.length - shownRules}`;
    };
    more.addEventListener("click", () => { shownRules += RULE_PAGE; fill(); });
    fill();
    nodes.push(el("div", { class: "section-title" }, el("h2", {}, title), el("span", { class: "muted" }, `${list.length} · ${note}`)), holder, more);
  }
  if (!items.length) nodes.push(el("div", { class: "empty" }, "No rules match these filters."));
  box.replaceChildren(...nodes);
}

VIEWS.rules = {
  ownFilters: true,
  activeFilters: () => ["rtype", "actors", "risk", "checks"].reduce((n, k) => n + state[k].size, 0)
    + (state.rq ? 1 : 0) + (state.rule ? 1 : 0),
  filterHead: () => el("div", { class: "frow" }, el("span", { class: "lbl" }, "Find"),
    searchBox("rq", "Search rule id, requirement or article"),
    state.rule ? el("button", { class: "chip on", onclick: () => go({ rule: "" }) }, state.rule.replace(/^AIA-(RULE-)?/, ""), el("span", { class: "n" }, "×")) : null),
  filterRows: () => {
    if (!CARDS) return [];
    indexRules();
    const items = ruleItems();
    return [
      chipRow("Type", "rtype", count(items, "type"), { fmt: (v) => (v === "gap" ? "gap rules" : "classification questions") }),
      chipRow("Actor", "actors", count(items, "roles"), { fmt: actorName }),
      chipRow("Risk class", "risk", count(items, "risk"), { fmt: human }),
      chipRow("Checks", "checks", count(items, "checks"), { order: Object.keys(CHECKS), fmt: (v) => CHECKS[v] }),
    ];
  },
  render: renderRules,
};
