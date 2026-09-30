// Norm cards: each norm as one readable sentence, with its sources, timing, links and rules.

let CARDS = null, CARDS_LOADING = false;
const IDX = { out: {}, in: {}, interp: {}, sum: {} };
const PAGE = 25;
let shown = PAGE;

const ACTOR_NAMES = {
  ai_office: "AI Office", gpai_provider: "GPAI provider", board: "Board", commission: "Commission",
  council: "Council", european_parliament: "European Parliament",
  european_data_protection_supervisor: "European Data Protection Supervisor",
  court_of_justice_of_the_european_union: "Court of Justice of the EU",
};
const ROUTES = { annex_i: "Annex I route", annex_iii: "Annex III route" };
const RELATIONS = {
  conditional_on_norms: "provided that",
  relies_on_norms: "relying on",
  carried_by_norms: "carried out through",
  parallel_norms: "together with",
  alternative_norms: "or alternatively",
  allocates_duty_to_policy_rules: "duty checked by",
  carried_by_policy_rules: "carried by rules",
  subject_to_external_requirements: "subject to",
  national_law_regulation: "national law decides",
  interpreted_by_commission_guidance: "interpreted by",
  unresolved_dependency: "unresolved",
  missing_dependency: "missing",
};
const TIMING = { in_force: "in force", upcoming: "upcoming", by_route: "depends on route",
                 expired: "expired", undated: "no start date" };
const HAS = { conditions: "conditions", exceptions: "exceptions", links: "linked norms",
              rules: "rules", guidance: "guidance", mandatory: "mandatory content" };

const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const actorName = (ref) => ACTOR_NAMES[ref] || cap(ref.replaceAll("_", " "));
const joinAnd = (xs) => (xs.length <= 1 ? xs[0] || "" : `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}`);
const fmtDate = (d) => new Date(d + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const asOf = () => state.asof || new Date().toISOString().slice(0, 10);
const cardLink = (id, text) => el("a", { class: "idlink mono", href: hashFor({ view: "norms", id, doc: "" }) }, text || id);

// ---- indexes -----------------------------------------------------------------------------------
function indexCards() {
  for (const r of CARDS.relations) {
    (IDX.out[r.source_norm_id] ||= []).push(r);
    for (const t of r.target_norm_ids) (IDX.in[t] ||= []).push(r);
  }
  for (const link of CARDS.interpretations) for (const id of link.norm_ids) (IDX.interp[id] ||= []).push(link);
  for (const n of DATA.norms) IDX.sum[n.id] = n;
}
function timingOf(norm) {
  const r = CARDS.regimes[norm.temporal_regime_id];
  if (!r) return "undated";
  const day = asOf();
  if (r.application_end && r.application_end < day) return "expired";
  if (r.application_start) return r.application_start <= day ? "in_force" : "upcoming";
  if (r.application_routes?.length) {
    const started = r.application_routes.filter((x) => x.application_start <= day).length;
    return started === r.application_routes.length ? "in_force" : started ? "by_route" : "upcoming";
  }
  return "undated";
}
function featuresOf(norm) {
  const out = [];
  if (norm.conditions) out.push("conditions");
  if (norm.exceptions) out.push("exceptions");
  if ((IDX.out[norm.norm_id] || []).some((r) => r.target_norm_ids.length)) out.push("links");
  if (norm.implementation_refs.length) out.push("rules");
  if (IDX.interp[norm.norm_id]) out.push("guidance");
  if (norm.mandatory_content.length) out.push("mandatory");
  return out;
}

// ---- source chips ------------------------------------------------------------------------------
function segLabel(id) {
  const seg = CARDS.segments[id];
  const tail = id.split("-").slice(3).join("-");
  return seg ? `${docLabel(`${seg.kind}:${seg.document.toLowerCase()}`)}${tail ? " · " + tail : ""}` : id.replace("AIA-TEXT-", "");
}
function segChips(ids) {
  return [...new Set(ids || [])].map((id) => el("button", {
    class: "seg", title: "Show source text",
    onclick: (e) => {
      e.preventDefault(); e.stopPropagation();
      const host = e.currentTarget.closest("li, .line, .src, .rel");
      const open = host.querySelector(`:scope > blockquote[data-seg="${id}"]`);
      if (open) { open.remove(); e.currentTarget.classList.remove("on"); return; }
      e.currentTarget.classList.add("on");
      host.append(el("blockquote", { "data-seg": id },
        el("div", { class: "qhead mono" }, segLabel(id)), CARDS.segments[id]?.text || "Text not available."));
    },
  }, segLabel(id)));
}

// ---- the readable sentence ---------------------------------------------------------------------
function subjectOf(norm) {
  if (norm.actors === "none") return null;
  if (!norm.actors.length) return "Everyone";
  return joinAnd(norm.actors.map((a) => actorName(a.actor_ref)));
}
function phrase(norm) {
  const a = norm.action, s = subjectOf(norm);
  let m;
  switch (norm.kind) {
    case "obligation": return [s, "must", a];
    case "prohibition":
      if ((m = a.match(/^do not (.*)/i))) return [s, "must not", m[1]];
      if ((m = a.match(/^prohibit (.*)/i))) return [s || "Everyone", "is prohibited from", m[1]];
      if (/^(refrain|perform no|not |never )/i.test(a)) return [s, "must", a];
      return [s, "must not", a];
    case "permission": case "power": return [s, "may", a];
    case "entitlement": return [s, "is entitled to", a];
    case "recommendation": return [s, "should", a.replace(/^should /i, "")];
    case "definition":
      return norm.targets.length ? [null, "Defines", `“${norm.targets[0].target_ref}”`] : [null, null, cap(a)];
    default: return s ? [s, "—", a] : [null, null, cap(a)];
  }
}
function headline(norm) {
  let [s, modal, action] = phrase(norm);
  // A norm that assigns no actor reads as a plain statement, not a modal without a subject.
  if (!s && modal && modal !== "Defines") [modal, action] = [null, cap(action)];
  return [s ? el("span", { class: "subj" }, s) : null, s ? " " : null,
          modal ? el("span", { class: "modal" }, modal) : null, modal ? " " : null, action];
}

const connector = (expr) => (expr.operator === "all_of" ? "AND" : "OR");
function exprItem(op) {
  // A nested group of one adds nothing, so it reads as its single member.
  while (op.operator && op.operands.length === 1) op = op.operands[0];
  return op.operator
    ? el("div", { class: "group" }, exprList(op))
    : el("span", {}, op.text, " ", segChips(op.basis_segment_ids));
}
function exprList(expr) {
  return el("ul", { class: "expr" }, expr.operands.flatMap((op, i) => [
    i ? el("li", { class: "conn" }, connector(expr)) : null,
    (() => { const item = exprItem(op); return el("li", { class: item.classList.contains("group") ? "grp" : null }, item); })(),
  ]));
}
function exprLine(lead, expr) {
  if (!expr) return null;
  let top = expr;
  while (top.operator && top.operands.length === 1 && top.operands[0].operator) top = top.operands[0];
  const single = top.operands.length === 1;
  return el("div", { class: "line" }, el("span", { class: "lead" }, lead),
    el("div", {}, single ? exprItem(top.operands[0]) : exprList(top)));
}
function timingLine(norm) {
  const r = CARDS.regimes[norm.temporal_regime_id];
  if (!r) return el("div", { class: "line" }, el("span", { class: "lead" }, "when"), el("div", { class: "muted" }, "No timing recorded."));
  const parts = [];
  if (r.application_start) parts.push(`Applies from ${fmtDate(r.application_start)}`);
  if (r.application_routes?.length) parts.push("Applies from " + r.application_routes.map((x) =>
    `${fmtDate(x.application_start)} (${ROUTES[x.route] || x.route})`).join(" or "));
  if (r.application_end) parts.push(`until ${fmtDate(r.application_end)}`);
  if (r.deadline) parts.push(`deadline ${fmtDate(r.deadline)}`);
  if (r.relative_deadline) {
    const d = r.relative_deadline, unit = d.unit.replace("_", " ") + (d.quantity > 1 ? "s" : "");
    parts.push(`within ${d.quantity} ${unit}${d.trigger ? ` of: ${d.trigger}` : ""}`);
  }
  if (r.qualitative_deadline) {
    const d = r.qualitative_deadline;
    parts.push(d.kind.replaceAll("_", " ") + (d.trigger ? ` (${d.trigger})` : ""));
  }
  parts.push(...(r.timing_conditions || []));
  const status = timingOf(norm);
  return el("div", { class: "line" }, el("span", { class: "lead" }, "when"),
    el("div", {}, cap(parts.join("; ")) || "No start date recorded.", " ",
      el("span", { class: "tag " + (status === "in_force" ? "" : status === "expired" ? "bad" : "part") }, TIMING[status]),
      " ", segChips(r.legal_basis_spans)));
}
function relationLine(rel, depth) {
  const content = [];
  if (rel.target_norm_ids.length) content.push(el("ul", { class: "expr" }, rel.target_norm_ids.map((id) => {
    const target = CARDS.norms[id];
    return el("li", {}, target ? miniSentence(target, depth + 1) : id);
  })));
  if (rel.target_rule_ids.length) content.push(el("div", {}, rel.target_rule_ids.map((id) => el("span", { class: "tag mono" }, id))));
  if (rel.external_requirements.length) content.push(el("div", {}, rel.external_requirements.join("; ")));
  if (rel.detail) content.push(el("div", { class: "muted" }, rel.detail));
  const bad = rel.kind === "unresolved_dependency" || rel.kind === "missing_dependency";
  return el("div", { class: "line rel" + (bad ? " badline" : "") },
    el("span", { class: "lead" }, RELATIONS[rel.kind] || rel.kind.replaceAll("_", " ")),
    el("div", {}, content, segChips(rel.legal_basis_spans)));
}
function miniSentence(norm, depth) {
  // Linked norms read inline, one level deep; deeper links open their own card.
  const nested = depth < 2 ? (IDX.out[norm.norm_id] || []).filter((r) => r.target_norm_ids.length) : [];
  return el("div", { class: "mini" },
    el("div", {}, headline(norm), " ", cardLink(norm.norm_id, "↗")),
    exprLine("if", norm.conditions), exprLine("unless", norm.exceptions),
    nested.map((r) => relationLine(r, depth)));
}

// ---- collapsible sections ----------------------------------------------------------------------
const section = (title, n, ...body) => el("details", { class: "sec" },
  el("summary", {}, chev(), title, n !== null ? el("span", { class: "n" }, n) : null), el("div", { class: "secbody" }, body));

function highlighted(text, needle) {
  const at = text.indexOf(needle);
  if (at < 0 || !needle) return text;
  return [text.slice(0, at), el("mark", {}, needle), text.slice(at + needle.length)];
}
function sourceSection(norm) {
  const src = (id, full) => el("div", { class: "src" }, el("div", { class: "qhead mono" }, segLabel(id)),
    el("div", { class: "srctext" }, full ? highlighted(CARDS.segments[id]?.text || "", norm.norm_text) : CARDS.segments[id]?.text || ""));
  const extra = [...norm.qualifier_spans, ...norm.definition_spans];
  return section("Source text", norm.primary_spans.length + extra.length,
    norm.primary_spans.map((id) => src(id, true)),
    extra.length ? el("details", { class: "sub" }, el("summary", {}, chev(), `Qualifying and definition text (${extra.length})`),
      extra.map((id) => src(id, false))) : null);
}
function ruleBlock(id, normId) {
  const rule = CARDS.rules[id];
  if (!rule) return el("div", { class: "rule" }, el("span", { class: "tag mono" }, id),
    id.startsWith("AIA-CQ-") ? el("span", { class: "muted" }, " classification question") : null);
  const others = rule.criteria.filter((c) => c !== normId);
  return el("div", { class: "rule" },
    el("div", { class: "rulehead" }, el("span", { class: "mono b" }, id),
      el("span", { class: "tag" }, rule.check_type), rule.document_verifiable ? el("span", { class: "tag" }, "document-verifiable") : null,
      rule.effective_date ? el("span", { class: "muted" }, `effective ${fmtDate(rule.effective_date)}`) : null),
    el("div", { class: "req" }, rule.requirement),
    rule.activation_condition ? el("div", { class: "kv" }, el("b", {}, "Activates when "), rule.activation_condition) : null,
    rule.qualified_by.length ? el("div", { class: "kv" }, el("b", {}, "Qualified by "), rule.qualified_by.join("; ")) : null,
    others.length ? el("div", { class: "kv" }, el("b", {}, `Also judges ${others.length} norm${others.length > 1 ? "s" : ""} `),
      others.map((c) => cardLink(c, c.replace("AIA-NORM-", "")))) : null,
    rule.guidance_refs.length ? el("div", { class: "kv" }, el("b", {}, "Guidance "), rule.guidance_refs.map((g) => el("span", { class: "tag" }, g))) : null,
    rule.evidence_expected ? el("details", { class: "sub" }, el("summary", {}, chev(), "Evidence expected"),
      el("div", { class: "secbody" }, rule.evidence_expected)) : null);
}
function implementationSection(norm) {
  return section("Implementation", norm.implementation_refs.length || null,
    el("div", { class: "kv" }, el("b", {}, "Mode "), el("span", { class: "tag" }, norm.implementation_mode),
      " ", el("b", {}, "Verification "), el("span", { class: "tag" }, norm.verification_mode)),
    norm.implementation_reason ? el("div", { class: "kv muted" }, norm.implementation_reason) : null,
    norm.implementation_refs.map((id) => ruleBlock(id, norm.norm_id)));
}
function guidanceSection(links) {
  return section("Guidance", links.length, links.map((link) => el("div", { class: "rule" },
    el("div", { class: "rulehead" }, el("span", { class: "tag part" }, link.effect.replaceAll("_", " ")),
      el("span", { class: "tag" }, link.status), link.targets.map((t) => el("span", { class: "tag mono" }, t))),
    el("div", { class: "req" }, link.explanation),
    link.snippet_refs.map((ref) => {
      const s = CARDS.snippets[ref];
      return el("details", { class: "sub" }, el("summary", {}, chev(), s ? `${s.document} · ${s.topic}` : ref),
        s ? el("div", { class: "secbody" }, el("div", { class: "muted" }, s.locator, s.binding ? "" : " · not binding"),
          el("blockquote", {}, s.body)) : null);
    }))));
}
function referencedSection(rels) {
  return section("Referenced by", rels.length, el("ul", { class: "expr" }, rels.map((r) => {
    const src = CARDS.norms[r.source_norm_id];
    return el("li", {}, el("span", { class: "op" }, RELATIONS[r.kind] || r.kind), " ",
      src ? headline(src) : r.source_norm_id, " ", cardLink(r.source_norm_id, "↗"));
  })));
}
function reviewSection(norm) {
  const r = norm.review;
  return section("Review", null,
    el("div", { class: "kv" }, el("b", {}, "Status "), el("span", { class: "tag" + (r.status === "approved" ? "" : " part") }, r.status),
      r.verified_by ? [" verified by ", el("b", {}, r.verified_by)] : " not yet verified"),
    el("div", { class: "kv" }, el("b", {}, "Extracted by "), r.extracted_by, el("span", { class: "muted" }, ` · ${r.review_run_id}`)),
    el("div", { class: "kv" }, el("b", {}, "Product scope "), el("span", { class: "tag" }, norm.product_scope),
      norm.product_scope_reason ? el("span", { class: "muted" }, " " + norm.product_scope_reason) : null));
}

function normLines(norm) {
  return el("div", { class: "lines" },
    norm.targets.length && norm.kind !== "definition" ? el("div", { class: "line" }, el("span", { class: "lead" }, "concerning"),
      el("div", {}, norm.targets.map((t) => el("div", {}, t.target_ref, " ", segChips(t.basis_segment_ids))))) : null,
    norm.kind === "definition" ? el("div", { class: "line" }, el("span", { class: "lead" }, "means"),
      el("div", { class: "quote" }, norm.norm_text)) : null,
    exprLine("if", norm.conditions),
    exprLine("unless", norm.exceptions),
    timingLine(norm),
    (IDX.out[norm.norm_id] || []).map((r) => relationLine(r, 0)));
}
function normBlock(norm, role) {
  // A norm as it reads under a rule: the card's sentence and lines, without its sections.
  const sum = IDX.sum[norm.norm_id];
  return el("div", { class: "nblock" },
    el("div", { class: "nbhead" },
      el("span", { class: "kind" }, norm.kind.replaceAll("_", " ")),
      role ? el("span", { class: "tag role" }, role) : null,
      el("a", { class: "doclink", href: hashFor({ view: "norms", doc: sum.doc, id: "" }) }, docLabel(sum.doc)),
      cardLink(norm.norm_id),
      el("span", { class: "spacer" }),
      norm.review.status === "approved" ? null : el("span", { class: "tag part" }, norm.review.status)),
    el("div", { class: "sentence" }, headline(norm), " ",
      segChips(norm.actors === "none" ? [] : norm.actors.flatMap((a) => a.basis_segment_ids))),
    normLines(norm));
}
function card(norm) {
  const sum = IDX.sum[norm.norm_id];
  const incoming = IDX.in[norm.norm_id] || [];
  const guidance = IDX.interp[norm.norm_id] || [];
  return el("article", { class: "ncard", id: norm.norm_id },
    el("header", {},
      el("span", { class: "kind" }, norm.kind.replaceAll("_", " ")),
      el("a", { class: "doclink", href: hashFor({ view: "norms", doc: sum.doc, id: "" }) }, docLabel(sum.doc)),
      cardLink(norm.norm_id),
      el("span", { class: "spacer" }),
      el("span", { class: "tag" + (norm.review.status === "approved" ? "" : " part") }, norm.review.status),
      el("span", { class: "tag" }, norm.product_scope.replaceAll("_", " "))),
    el("div", { class: "sentence" }, headline(norm), " ",
      segChips(norm.actors === "none" ? [] : norm.actors.flatMap((a) => a.basis_segment_ids))),
    normLines(norm),
    el("div", { class: "secs" },
      sourceSection(norm),
      norm.mandatory_content.length ? section("Mandatory content", norm.mandatory_content.length,
        el("ol", { class: "mc" }, norm.mandatory_content.map((m) => el("li", {}, m)))) : null,
      implementationSection(norm),
      guidance.length ? guidanceSection(guidance) : null,
      incoming.length ? referencedSection(incoming) : null,
      reviewSection(norm)));
}

// ---- list --------------------------------------------------------------------------------------
function matches(sum) {
  if (state.id) return sum.id === state.id;
  if (!normFilter(sum)) return false;
  if (state.doc && sum.doc !== state.doc) return false;
  const norm = CARDS.norms[sum.id];
  if (!pass(state.timing, timingOf(norm)) || !pass(state.has, featuresOf(norm))) return false;
  const q = state.nq.trim().toLowerCase();
  return !q || `${sum.id} ${norm.action} ${norm.norm_text}`.toLowerCase().includes(q);
}
function ensureCards(box) {
  if (CARDS) return true;
  box.replaceChildren(el("div", { class: "empty" }, "Loading…"));
  if (!CARDS_LOADING) {
    CARDS_LOADING = true;
    fetch("/api/norms").then((r) => r.json()).then((data) => { CARDS = data; indexCards(); render(); });
  }
  return false;
}
function renderCards() {
  const box = document.getElementById("cards");
  if (!ensureCards(box)) return;
  const hits = DATA.norms.filter(matches);
  document.getElementById("normcount").textContent = state.id ? "" : `${hits.length} of ${DATA.norms.length} norms`;
  shown = PAGE;
  const list = el("div", { class: "cardlist" });
  const more = el("button", { class: "morebtn" });
  const fill = () => {
    list.append(...hits.slice(list.children.length, shown).map((s) => card(CARDS.norms[s.id])));
    more.hidden = shown >= hits.length;
    more.textContent = `Show ${Math.min(PAGE, hits.length - shown)} more of ${hits.length - shown}`;
  };
  more.addEventListener("click", () => { shown += PAGE; fill(); });
  fill();
  box.replaceChildren(...[
    state.id ? el("button", { class: "link back", onclick: () => go({ id: "" }) }, "← All norm cards") : null,
    hits.length ? list : el("div", { class: "empty" }, "No norms match these filters."), more].filter(Boolean));
  if (state.id) list.querySelectorAll("details.sec").forEach((d) => { d.open = true; });
}

VIEWS.norms = {
  activeFilters: () => (state.nq ? 1 : 0) + (state.doc ? 1 : 0) + (state.id ? 1 : 0)
    + state.timing.size + state.has.size,
  filterHead: () => el("div", { class: "frow" }, el("span", { class: "lbl" }, "Find"),
    searchBox("nq", "Search norm id, action or text"),
    state.doc ? el("button", { class: "chip on", onclick: () => go({ doc: "" }) }, docLabel(state.doc), el("span", { class: "n" }, "×")) : null,
    state.id ? el("button", { class: "chip on", onclick: () => go({ id: "" }) }, state.id.replace("AIA-NORM-", ""), el("span", { class: "n" }, "×")) : null),
  filterRows: () => {
    if (!CARDS) return [];
    const norms = DATA.norms.map((s) => CARDS.norms[s.id]);
    const timing = count(norms.map((n) => ({ t: timingOf(n) })), "t");
    const has = count(norms.map((n) => ({ f: featuresOf(n) })), "f");
    const date = el("input", { type: "date", class: "date", value: asOf(), title: "Timing is judged on this date" });
    date.addEventListener("change", () => { state.asof = date.value; render(); });
    return [
      chipRow("Timing", "timing", timing, { order: Object.keys(TIMING), fmt: (v) => TIMING[v],
        extra: el("span", { class: "muted small" }, "on ", date) }),
      chipRow("Has", "has", has, { order: Object.keys(HAS), fmt: (v) => HAS[v] }),
    ];
  },
  render: renderCards,
};
