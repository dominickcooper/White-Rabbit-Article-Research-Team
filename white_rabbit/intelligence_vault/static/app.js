"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const state = { graph: null, graphPayload: null, timeline: null, paths: null, investigations: new Set() };

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([key, value]) => {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value == null ? "" : String(value);
    else node.setAttribute(key, value);
  });
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child instanceof Node) node.appendChild(child);
    else if (child != null) node.appendChild(document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) { node.replaceChildren(); }
function fmt(value) { return value || "Unknown"; }
function toast(message) { const box = $("#toast"); box.textContent = message; box.classList.add("show"); setTimeout(() => box.classList.remove("show"), 2600); }
async function api(url) { const response = await fetch(url, { headers: { "Accept": "application/json" } }); const body = await response.json(); if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`); return body; }
async function writeApi(url, method, body) { const response = await fetch(url, { method, headers: { "Accept": "application/json", "Content-Type": "application/json" }, body: JSON.stringify(body) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`); return payload; }
function download(name, content, type) { const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob); const anchor = el("a", { href: url, download: name }); anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
function qp(values) { const query = new URLSearchParams(); Object.entries(values).forEach(([key, value]) => { if (value !== "" && value != null && value !== false) query.set(key, value); }); return query.toString(); }

function showView(name) {
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${name}`));
  $$(".nav button").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  if (name === "dashboard") loadDashboard();
  if (name === "investigations") loadInvestigations();
  if (name === "review") loadReview();
  if (name === "graph" && !state.graphPayload) loadGraph();
  if (name === "timeline" && !state.timeline) loadTimeline();
  history.replaceState(null, "", `#${name}`);
}

async function loadDashboard() {
  try {
    const stats = await api("/api/stats"); const grid = $("#stat-grid"); clear(grid);
    ["people", "organizations", "events", "places", "relationships", "documents"].forEach((label) => {
      const key = label === "people" ? "person" : label === "organizations" ? "organization" : label === "events" ? "event" : label === "places" ? "place" : label;
      grid.append(el("div", { class: "stat" }, [el("strong", { text: stats[key] || 0 }), el("span", { text: label })]));
    });
  } catch (error) { toast(error.message); }
}

function resultCard(item, kind) {
  const title = item.canonical_name || item.title || item.statement || item.id;
  const card = el("article", { class: "card" }, [el("h3", { text: title }), el("p", { class: "meta", text: `${kind} · ${item.id}` })]);
  if (kind === "entity") card.addEventListener("click", () => { showView("entities"); loadProfile(item.id); });
  return card;
}

async function runEvidenceSearch() {
  try {
    const data = await api(`/api/search?${qp({ q: $("#evidence-query").value })}`); const target = $("#evidence-results"); clear(target);
    [...data.documents.map((x) => [x, "document"]), ...data.claims.map((x) => [x, "claim"])].forEach(([item, kind]) => target.append(resultCard(item, kind)));
    if (!target.children.length) target.append(el("p", { class: "empty", text: "No matching accepted sources or claims." }));
  } catch (error) { toast(error.message); }
}

async function runEntitySearch(query = null) {
  try {
    const data = await api(`/api/search?${qp({ q: query ?? $("#entity-query").value, type: $("#entity-type").value })}`); const target = $("#entity-results"); clear(target);
    data.entities.forEach((item) => { const button = resultCard(item, "entity"); button.className = "list-item"; button.addEventListener("click", () => loadProfile(item.id)); target.append(button); });
    if (!data.entities.length) target.append(el("p", { class: "empty", text: "No matching accepted identities." }));
  } catch (error) { toast(error.message); }
}

function evidenceBlock(item) {
  return el("div", { class: "evidence" }, [el("strong", { text: item.document_title || "Source" }), el("p", { text: item.original_wording || "No passage stored." }), el("span", { class: "meta", text: `${fmt(item.locator)} · ${item.revision_id || ""}${item.attribution ? ` · Attribution: ${item.attribution}` : ""}` })]);
}

async function loadProfile(id, target = $("#entity-profile")) {
  try {
    const item = await api(`/api/profiles/${encodeURIComponent(id)}`); clear(target);
    target.append(el("p", { class: "eyebrow", text: item.entity_type }), el("h2", { text: item.canonical_name }), el("p", { text: item.description || "No narrative biography recorded." }), el("p", { class: "meta", text: item.id }));
    if (item.aliases.length) target.append(el("p", {}, ["Aliases: ", ...item.aliases.map((x) => el("span", { class: "pill", text: x }))]));
    const detail = item.details || {}; const populated = Object.entries(detail).filter(([key, value]) => key !== "entity_id" && value !== null && value !== "" && value !== "unknown");
    if (populated.length) { target.append(el("h3", { text: "Profile" })); populated.forEach(([key, value]) => target.append(el("p", {}, [el("strong", { text: `${key.replaceAll("_", " ")}: ` }), String(value)]))); }
    target.append(el("h3", { text: `Relationships (${item.relationships.length})` }));
    item.relationships.forEach((rel) => { const other = rel.subject_entity_id === id ? rel.object_name : rel.subject_name; const section = el("div", { class: "review-item" }, [el("strong", { text: `${rel.relationship_type.replaceAll("_", " ")} · ${other}` }), el("p", { class: "meta", text: `${fmt(rel.historical_start)} — ${fmt(rel.historical_end)} · ${rel.classification}` })]); rel.evidence.forEach((ev) => section.append(evidenceBlock(ev))); target.append(section); });
    target.append(el("h3", { text: `Claims (${item.claims.length})` })); item.claims.forEach((claim) => { const section = el("div", { class: "review-item" }, [el("strong", { text: claim.statement }), el("span", { class: "pill", text: claim.epistemic_status })]); claim.evidence.forEach((ev) => section.append(evidenceBlock(ev))); target.append(section); });
    target.append(el("h3", { text: "Investigations" })); if (item.investigations.length) item.investigations.forEach((inv) => target.append(el("span", { class: "pill", text: inv.name }))); else target.append(el("p", { class: "empty", text: "No explicit investigation memberships." }));
    if (item.identity_matches.length || item.conflicts.length) { target.append(el("h3", { text: "Unresolved review" }), el("p", { text: `${item.identity_matches.length} identity match suggestion(s); ${item.conflicts.length} claim conflict(s).` })); }
    const controls = el("div", { class: "button-row" }, [el("button", { text: "Open on graph" }), el("button", { text: "Export profile" })]); controls.children[0].addEventListener("click", () => { $("#graph-focus").value = id; showView("graph"); loadGraph(); }); controls.children[1].addEventListener("click", () => download(`${id}-profile.json`, JSON.stringify(item, null, 2), "application/json")); target.prepend(controls);
  } catch (error) { clear(target); target.append(el("p", { class: "danger", text: error.message })); }
}

function graphElements(payload) {
  const nodes = payload.nodes.map((n) => ({ data: { id: n.id, label: n.canonical_name, type: n.entity_type, record: n } }));
  const accepted = payload.edges.map((e) => ({ data: { id: e.id, source: e.subject_entity_id, target: e.object_entity_id, label: e.relationship_type.replaceAll("_", " "), kind: e.edge_kind, classification: e.classification_kind, directed: Boolean(e.directed), record: e } }));
  const candidates = payload.candidates.map((e) => ({ data: { id: e.id, source: e.subject_entity_id, target: e.object_entity_id, label: "candidate", kind: "candidate", classification: "exploratory_candidate", directed: false, record: e } }));
  return [...nodes, ...accepted, ...candidates];
}

const graphStyle = [
  { selector: "node", style: { "background-color": "#5b9bd5", label: "data(label)", color: "#eef1f5", "font-size": 11, "text-valign": "bottom", "text-margin-y": 7, "text-outline-color": "#0b0e12", "text-outline-width": 3, width: 34, height: 34 } },
  { selector: 'node[type="person"]', style: { "background-color": "#ba3d43", shape: "ellipse" } },
  { selector: 'node[type="organization"]', style: { "background-color": "#5b7fa8", shape: "round-rectangle" } },
  { selector: 'node[type="event"]', style: { "background-color": "#9a78c2", shape: "diamond" } },
  { selector: 'node[type="place"]', style: { "background-color": "#66a67a", shape: "hexagon" } },
  { selector: 'node[type="document"]', style: { "background-color": "#a6a19a", shape: "rectangle", width: 24, height: 30 } },
  { selector: "edge", style: { width: 2, "line-color": "#ba3d43", "target-arrow-color": "#ba3d43", "target-arrow-shape": "triangle", "curve-style": "bezier", label: "data(label)", color: "#bac3ce", "font-size": 8, "text-background-color": "#0b0e12", "text-background-opacity": .8, "text-background-padding": 2 } },
  { selector: "edge[!directed]", style: { "target-arrow-shape": "none" } },
  { selector: 'edge[kind="evidence_link"]', style: { "line-color": "#687382", "target-arrow-color": "#687382", "line-style": "dotted" } },
  { selector: 'edge[kind="candidate"]', style: { "line-color": "#d7a74d", "target-arrow-shape": "none", "line-style": "dashed", width: 2 } },
  { selector: ":selected", style: { "border-color": "#fff", "border-width": 3, "line-color": "#fff", "target-arrow-color": "#fff" } }
];

async function resolveFocus(value) {
  const raw = value.trim(); if (!raw) return { focus: "", query: "" }; if (raw.startsWith("ENT-")) return { focus: raw, query: "" };
  const found = await api(`/api/search?${qp({ q: raw })}`); if (found.entities.length === 1) return { focus: found.entities[0].id, query: "" }; return { focus: "", query: raw };
}

async function loadGraph() {
  try {
    const resolved = await resolveFocus($("#graph-focus").value); const params = { focus: resolved.focus, q: resolved.query, depth: $("#graph-depth").value, relationships: $("#graph-relationships").value, investigations: $("#graph-investigations").value, start: $("#graph-start").value, end: $("#graph-end").value, temporal: $("#graph-temporal").value, candidates: $("#graph-candidates").checked ? "1" : "", documents: $("#graph-documents").checked ? "1" : "", limit: 500 };
    state.graphPayload = await api(`/api/graph?${qp(params)}`);
    if (state.graph) state.graph.destroy();
    state.graph = cytoscape({ container: $("#cy"), elements: graphElements(state.graphPayload), style: graphStyle, layout: { name: $("#graph-layout").value, animate: false, padding: 35 }, minZoom: .08, maxZoom: 4 });
    state.graph.on("tap", "node", (event) => showGraphNode(event.target.data("record")));
    state.graph.on("tap", "edge", (event) => showGraphEdge(event.target.data("record")));
    if (!state.graphPayload.nodes.length) { clear($("#graph-detail")); $("#graph-detail").append(el("h2", { text: "Empty graph" }), el("p", { class: "empty", text: "No accepted relationships match these filters." })); }
  } catch (error) { toast(error.message); }
}

function showGraphNode(record) {
  const target = $("#graph-detail"); clear(target); target.append(el("p", { class: "eyebrow", text: record.entity_type }), el("h2", { text: record.canonical_name }), el("p", { text: record.description || "No description recorded." }), el("p", { class: "meta", text: record.id }));
  const buttons = el("div", { class: "button-row" }, [el("button", { text: "Profile" }), el("button", { text: "Focus network" }), el("button", { text: "Set path A" }), el("button", { text: "Set path B" })]);
  buttons.children[0].addEventListener("click", () => loadProfile(record.id, target)); buttons.children[1].addEventListener("click", () => { $("#graph-focus").value = record.id; loadGraph(); }); buttons.children[2].addEventListener("click", () => { $("#path-source").value = record.id; }); buttons.children[3].addEventListener("click", () => { $("#path-target").value = record.id; }); target.append(buttons);
  if (record.investigations?.length) target.append(el("h3", { text: "Investigations" }), ...record.investigations.map((x) => el("span", { class: "pill", text: x.name })));
}

async function showGraphEdge(record) {
  try {
    const detail = record.edge_kind === "accepted" ? await api(`/api/relationships/${encodeURIComponent(record.id)}/detail`) : record; const target = $("#graph-detail"); clear(target);
    const candidate = detail.edge_kind === "candidate"; target.append(el("span", { class: `pill ${candidate ? "candidate" : "accepted"}`, text: candidate ? "EXPLORATORY CANDIDATE" : detail.classification }), el("h2", { text: detail.relationship_type.replaceAll("_", " ") }));
    if (detail.subject_name || detail.object_name) target.append(el("p", { text: `${detail.subject_name || detail.subject_entity_id} → ${detail.object_name || detail.object_entity_id}` }));
    target.append(el("p", { class: "meta", text: `${fmt(detail.historical_start)} (${fmt(detail.historical_start_precision)}) — ${fmt(detail.historical_end)} (${fmt(detail.historical_end_precision)})` }));
    target.append(el("p", { text: detail.explanation || detail.interaction_warning }));
    if (detail.evidence?.length) { target.append(el("h3", { text: "Source evidence" })); detail.evidence.forEach((ev) => target.append(evidenceBlock(ev))); }
  } catch (error) { toast(error.message); }
}

function buildSvg() {
  if (!state.graph) return ""; const box = state.graph.elements().boundingBox(); const width = Math.max(800, box.w + 120), height = Math.max(600, box.h + 120); const ox = 60 - box.x1, oy = 60 - box.y1;
  const escape = (x) => String(x).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;"); let body = "";
  state.graph.edges().forEach((edge) => { const a = edge.source().position(), b = edge.target().position(), candidate = edge.data("kind") === "candidate"; body += `<line x1="${a.x + ox}" y1="${a.y + oy}" x2="${b.x + ox}" y2="${b.y + oy}" stroke="${candidate ? "#d7a74d" : "#ba3d43"}" stroke-width="2" ${candidate ? 'stroke-dasharray="7 5"' : ""}/>`; });
  state.graph.nodes().forEach((node) => { const p = node.position(), color = { person: "#ba3d43", organization: "#5b7fa8", event: "#9a78c2", place: "#66a67a", document: "#a6a19a" }[node.data("type")] || "#5b9bd5"; body += `<circle cx="${p.x + ox}" cy="${p.y + oy}" r="17" fill="${color}"/><text x="${p.x + ox}" y="${p.y + oy + 31}" text-anchor="middle" fill="#eef1f5" font-family="sans-serif" font-size="11">${escape(node.data("label"))}</text>`; });
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><rect width="100%" height="100%" fill="#0b0e12"/>${body}</svg>`;
}

async function findPaths() {
  try { state.paths = await api(`/api/paths?${qp({ source: $("#path-source").value, target: $("#path-target").value, depth: $("#path-depth").value, relationships: $("#path-relationships").value, directed: $("#path-direction").checked ? "1" : "" })}`); const target = $("#path-results"); clear(target); if (!state.paths.paths.length) return target.append(el("p", { class: "empty", text: "No accepted path was found within this depth." })); state.paths.paths.forEach((path, index) => { const box = el("div", { class: `path ${path.temporal_compatibility.state === "temporally_incompatible" ? "incompatible" : ""}` }, [el("p", { class: "chain", text: path.nodes.map((n) => n.canonical_name).join(" → ") }), el("p", { text: path.edges.map((e) => e.relationship_type.replaceAll("_", " ")).join(" · ") }), el("p", { class: "meta", text: `${path.temporal_compatibility.state.replaceAll("_", " ")} — ${path.temporal_compatibility.explanation}` }), el("p", { class: "meta", text: path.meaning_boundary })]); target.append(box); }); } catch (error) { toast(error.message); }
}

function dateNumber(value, fallback) { if (!value) return fallback; const parts = value.split("-").map(Number); return parts[0] + ((parts[1] || 1) - 1) / 12 + ((parts[2] || 1) - 1) / 366; }
async function loadTimeline() {
  try {
    const params = { start: $("#timeline-start").value, end: $("#timeline-end").value, entity: $("#timeline-entity").value, event_type: $("#timeline-event-type").value, country: $("#timeline-country").value, investigations: $("#timeline-investigations").value, source: $("#timeline-source").value, limit: 500 }; state.timeline = await api(`/api/timeline?${qp(params)}`); renderTimeline();
  } catch (error) { toast(error.message); }
}

function renderTimeline() {
  const canvas = $("#timeline-canvas"), zoom = Number($("#timeline-zoom").value), start = dateNumber(state.timeline.window.start, 0), end = dateNumber(state.timeline.window.end, start + 1), span = Math.max(end - start, .01), width = Math.max(1000, span * 12 * zoom); clear(canvas); canvas.style.width = `${width}px`; canvas.style.height = `${Math.max(420, 55 + state.timeline.items.length * 36)}px`;
  const axis = el("div", { class: "timeline-axis" }); const ticks = Math.min(30, Math.max(2, Math.round(width / 140))); for (let i = 0; i <= ticks; i++) { const year = start + (span * i / ticks); const tick = el("span", { class: "timeline-tick", text: String(Math.floor(year)) }); tick.style.left = `${i / ticks * 100}%`; axis.append(tick); } canvas.append(axis);
  state.timeline.items.forEach((item, index) => { const a = dateNumber(item.historical_start, start), b = dateNumber(item.historical_end, a + Math.max(.04, span / width * 10)), left = Math.max(0, (a - start) / span * width), itemWidth = Math.max(7, (b - a) / span * width); const uncertain = item.temporal_overlap !== "definite_overlap" || item.historical_start_precision === "approximate" || ["possible", "uncertain", "unknown"].includes(item.historical_start_certainty); const button = el("button", { class: `timeline-item ${!item.historical_start ? "undated" : uncertain ? "possible" : ""}`, text: item.label, title: item.label }); button.style.left = `${left}px`; button.style.top = `${46 + index * 36}px`; button.style.width = `${Math.min(Math.max(itemWidth, 130), 600)}px`; button.addEventListener("click", () => showTimelineDetail(item)); canvas.append(button); });
  if (!state.timeline.items.length) canvas.append(el("p", { class: "empty", text: "No accepted dated records match this window." }));
}

function showTimelineDetail(item) { const target = $("#timeline-detail"); clear(target); target.append(el("span", { class: `pill ${item.temporal_overlap === "possible_overlap" ? "candidate" : "accepted"}`, text: item.temporal_overlap.replaceAll("_", " ") }), el("h2", { text: item.label }), el("p", { text: `${fmt(item.historical_start)} (${fmt(item.historical_start_precision)}, ${fmt(item.historical_start_certainty)}) — ${fmt(item.historical_end)} (${fmt(item.historical_end_precision)}, ${fmt(item.historical_end_certainty)})` })); if (item.evidence?.length) { target.append(el("h3", { text: "Evidence" })); item.evidence.forEach((ev) => target.append(evidenceBlock(ev))); } const button = el("button", { text: "Open in graph" }); button.addEventListener("click", () => { $("#graph-focus").value = item.subject_entity_id || item.id; showView("graph"); loadGraph(); }); target.append(button); }

async function loadInvestigations() { try { const data = await api(`/api/investigations?${qp({ selected: [...state.investigations].join(",") })}`); const list = $("#investigation-list"); clear(list); data.investigations.forEach((inv) => { const input = el("input", { type: "checkbox" }); input.checked = state.investigations.has(inv.id); input.addEventListener("change", () => { if (input.checked) state.investigations.add(inv.id); else state.investigations.delete(inv.id); loadInvestigations(); }); list.append(el("label", { class: "card" }, [input, " ", el("strong", { text: inv.name }), el("p", { text: inv.description || "No description." }), el("span", { class: "meta", text: `${inv.entity_count} explicit identity membership(s)` })])); }); const shared = $("#investigation-shared"); clear(shared); shared.append(el("h2", { text: "Shared identities" })); if (data.shared_entities.length) data.shared_entities.forEach((item) => { const button = el("button", { text: `${item.canonical_name} · ${item.entity_type}` }); button.addEventListener("click", () => { showView("entities"); loadProfile(item.id); }); shared.append(button); }); else shared.append(el("p", { class: "empty", text: "Select at least two investigations. Only explicit stored memberships are compared." })); shared.append(el("h2", { text: "Shared source documents" })); if (data.shared_documents.length) data.shared_documents.forEach((item) => shared.append(el("p", { text: `${item.title} · ${item.id}` }))); else shared.append(el("p", { class: "empty", text: "No explicitly shared document memberships." })); } catch (error) { toast(error.message); } }

async function loadReview() { try { const data = await api("/api/review"), target = $("#review-results"); clear(target); [["Identity matches", data.merge_suggestions], ["Claim conflicts", data.conflicts]].forEach(([title, items]) => { const group = el("section", { class: "panel review-group" }, [el("h2", { text: `${title} (${items.length})` })]); items.forEach((item) => group.append(el("div", { class: "review-item" }, [el("code", { text: item.id }), el("p", { text: item.reason || "Review required" })]))); if (!items.length) group.append(el("p", { class: "empty", text: "Queue clear." })); target.append(group); }); } catch (error) { toast(error.message); } }

function extractionPayload() { return { provider: $("#extract-provider").value, manual_results: $("#extract-results").value || null, allow_cloud: $("#extract-cloud").checked }; }
function showExtraction(value) { $("#extract-output").textContent = JSON.stringify(value, null, 2); if (value.job_id) $("#extract-job").value = value.job_id; }
async function extractionAction(action) { try { const job = encodeURIComponent($("#extract-job").value); let result; if (action === "start") result = await writeApi("/api/extractions", "POST", { document: $("#extract-document").value, ...extractionPayload() }); else if (action === "status") result = await api(`/api/extractions/${job}`); else if (action === "review") result = await api(`/api/extractions/${job}/review`); else if (action === "retry") result = await writeApi(`/api/extractions/${job}/retry`, "POST", extractionPayload()); else if (action === "commit") result = await writeApi(`/api/extractions/${job}/commit`, "POST", {}); showExtraction(result); } catch (error) { showExtraction({ error: error.message }); } }
async function decideExtraction(action) { try { const job = encodeURIComponent($("#extract-job").value), proposal = encodeURIComponent($("#extract-proposal").value); const result = await writeApi(`/api/extractions/${job}/proposals/${proposal}`, "PATCH", { action, known_entity_id: $("#extract-known").value || null }); showExtraction(result); } catch (error) { showExtraction({ error: error.message }); } }

$$('.nav button').forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
$$('[data-go]').forEach((button) => button.addEventListener("click", () => showView(button.dataset.go)));
$("#global-search-button").addEventListener("click", () => { $("#entity-query").value = $("#global-search").value; showView("entities"); runEntitySearch($("#global-search").value); });
$("#evidence-search-button").addEventListener("click", runEvidenceSearch); $("#entity-search-button").addEventListener("click", () => runEntitySearch());
$("#new-entity-add").addEventListener("click", async () => { try { const result = await writeApi("/api/entities", "POST", { entity_type: $("#new-entity-type").value, name: $("#new-entity-name").value, aliases: $("#new-entity-aliases").value.split(",").map((value) => value.trim()).filter(Boolean) }); toast(`Created ${result.id}`); $("#new-entity-name").value = ""; $("#new-entity-aliases").value = ""; runEntitySearch(); } catch (error) { toast(error.message); } });
$("#graph-load").addEventListener("click", loadGraph); $("#graph-fit").addEventListener("click", () => state.graph?.fit(undefined, 35)); $("#graph-layout").addEventListener("change", () => state.graph?.layout({ name: $("#graph-layout").value, animate: false, padding: 35 }).run());
$("#graph-json").addEventListener("click", () => state.graphPayload && download("vault-subgraph.json", JSON.stringify(state.graphPayload, null, 2), "application/json")); $("#graph-svg").addEventListener("click", () => download("vault-subgraph.svg", buildSvg(), "image/svg+xml")); $("#graph-png").addEventListener("click", () => { if (!state.graph) return; const anchor = el("a", { href: state.graph.png({ full: true, scale: 2, bg: "#0b0e12" }), download: "vault-subgraph.png" }); anchor.click(); });
$("#path-find").addEventListener("click", findPaths); $("#path-export").addEventListener("click", () => state.paths && download("relationship-path-report.json", JSON.stringify(state.paths, null, 2), "application/json"));
$("#timeline-load").addEventListener("click", loadTimeline); $("#timeline-zoom").addEventListener("input", () => state.timeline && renderTimeline()); $("#timeline-json").addEventListener("click", () => state.timeline && download("vault-timeline.json", JSON.stringify(state.timeline, null, 2), "application/json")); $("#timeline-csv").addEventListener("click", () => location.href = `/api/exports/timeline.csv?${qp({ start: $("#timeline-start").value, end: $("#timeline-end").value, entity: $("#timeline-entity").value, event_type: $("#timeline-event-type").value, country: $("#timeline-country").value, investigations: $("#timeline-investigations").value, source: $("#timeline-source").value })}`);
$("#extract-start").addEventListener("click", () => extractionAction("start")); $("#extract-status").addEventListener("click", () => extractionAction("status")); $("#extract-review").addEventListener("click", () => extractionAction("review")); $("#extract-retry").addEventListener("click", () => extractionAction("retry")); $("#extract-commit").addEventListener("click", () => extractionAction("commit")); $("#extract-approve").addEventListener("click", () => decideExtraction("approve")); $("#extract-reject").addEventListener("click", () => decideExtraction("reject"));
const initial = location.hash.slice(1); showView(["dashboard", "evidence", "entities", "timeline", "graph", "investigations", "review"].includes(initial) ? initial : "dashboard");
