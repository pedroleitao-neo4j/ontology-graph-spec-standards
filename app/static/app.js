// The crosswalk explorer. Routes, by the hash:
//   #/<crosswalk>/graph[/<node>]    every node of the crosswalk as a graph, a band per standard, and one of them picked
//   #/<crosswalk>/things[/<node>]   the things the crosswalk links, and one of them as every standard describes it
//   #/<crosswalk>/mappings          the crosswalk's mappings and the pairs of nodes the data links by each

const $ = (id) => document.getElementById(id);

// How a mapping reads from its subject to its object. SKOS's broadMatch says the object is the broader concept.
const PREDICATES = {
  exactMatch: { glyph: "≡", words: "same as" },
  closeMatch: { glyph: "≈", words: "close to" },
  broadMatch: { glyph: "⊂", words: "narrower than" },
  narrowMatch: { glyph: "⊃", words: "broader than" },
  relatedMatch: { glyph: "~", words: "related to" },
};

const state = { crosswalks: [], current: null, clusters: {}, graphs: {}, graph: null, search: "", searchTimer: null, thing: null };

function escape(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

async function api(path) {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(detail);
  }
  return response.json();
}

function notice(message) {
  $("notice").hidden = !message;
  $("notice").textContent = message || "";
}

function standardOf(prefix) {
  return state.current.standards.find((s) => s.prefix === prefix) || { name: prefix, color: "#8a909b" };
}

function shortName(crosswalk) {
  return crosswalk.name.split(":")[0];
}

function href(...parts) {
  return "#/" + parts.map(encodeURIComponent).join("/");
}

// ---- Routing --------------------------------------------------------------------------------------------------

function parseRoute() {
  const [id, view, node] = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  return { id, view: VIEWS.includes(view) ? view : "graph", node: node || null };
}

const VIEWS = ["graph", "things", "mappings"];

async function route() {
  const { id, view, node } = parseRoute();
  const crosswalk = state.crosswalks.find((c) => c.id === id);
  if (!crosswalk) {
    if (state.crosswalks.length) location.replace(href(state.crosswalks[0].id, "graph"));
    return;
  }
  const switched = state.current?.id !== crosswalk.id;
  state.current = crosswalk;
  renderMasthead();
  if (switched) {
    state.search = "";
    $("search").value = "";
    renderAbout();
  }
  for (const name of VIEWS) {
    $(`view-${name}`).href = href(crosswalk.id, name);
    $(`view-${name}`).setAttribute("aria-selected", String(view === name));
  }
  $("graph").hidden = view !== "graph";
  $("explorer").hidden = view !== "things";
  $("mappings").hidden = view !== "mappings";

  if (!crosswalk.loaded) {
    renderUnloaded(crosswalk);
    return;
  }
  try {
    notice(null);
    if (view === "mappings") {
      await renderMappings(crosswalk);
    } else if (view === "graph") {
      await renderGraph(crosswalk, node);
    } else {
      const clusters = await clustersOf(crosswalk);
      if (!node) {
        if (clusters.length) {
          location.replace(href(crosswalk.id, "things", clusters[0].id));
        } else {
          renderRail();
          renderEmptyConcordance();
        }
        return;
      }
      state.thing = node;
      if (switched || !$("things").children.length || state.search) renderRail();
      else markCurrent();
      await renderThing(crosswalk, node);
    }
  } catch (error) {
    notice(error.message);
  }
}

async function clustersOf(crosswalk) {
  if (!state.clusters[crosswalk.id]) {
    state.clusters[crosswalk.id] = (await api(`/crosswalks/${crosswalk.id}/clusters`)).clusters;
  }
  return state.clusters[crosswalk.id];
}

// ---- Masthead and the crosswalk's description -------------------------------------------------------------------

function renderMasthead() {
  const { view } = parseRoute();
  $("crosswalks").innerHTML = state.crosswalks.map((c) => `
    <a href="${href(c.id, view)}" ${c.id === state.current?.id ? 'aria-current="page"' : ""}>
      <span class="swatches" aria-hidden="true">${c.standards.map((s) => `<i style="--hue:${s.color}"></i>`).join("")}</span>
      ${escape(shortName(c))}
    </a>`).join("");
}

function renderAbout() {
  const c = state.current;
  $("about").innerHTML = `
    <h1>${c.standards.map((s) => `<span class="standard-name" style="--hue:${s.color}">${escape(s.name)}</span>`)
      .join('<span class="joiner" aria-hidden="true">⇄</span>')}</h1>
    <details>
      <summary>About this crosswalk · ${c.mappings} mappings</summary>
      <p>${escape(c.description)}</p>
    </details>`;
}

function renderUnloaded(crosswalk) {
  const message = state.connected
    ? `<p>${escape(crosswalk.name)} isn't in the database yet.</p>
       <p>Load it with <code>python3 app/load.py ${escape(crosswalk.id)}</code>, then reload this page.</p>`
    : `<p>The explorer can't reach the database: ${escape(state.error || "no connection")}.</p>
       <p>Check <code>NEO4J_URI</code>, <code>NEO4J_USERNAME</code> and <code>NEO4J_PASSWORD</code> in
       <code>.env</code>, then restart the server.</p>`;
  $("things").innerHTML = "";
  $("rail-note").textContent = "";
  $("concordance").innerHTML = `<div class="empty">${message}</div>`;
  $("mappings").innerHTML = `<div class="empty">${message}</div>`;
  $("graph-panel").innerHTML = `<div class="empty">${message}</div>`;
  $("graph-svg").innerHTML = "";
  $("graph-legend").innerHTML = "";
  state.graph = null;
}

// ---- The rail: linked things, or search results ------------------------------------------------------------------

function dots(standards) {
  return `<span class="dots" aria-hidden="true">${state.current.standards.map((s) =>
    `<i class="${standards.includes(s.prefix) ? "on" : ""}" style="--hue:${s.color}"></i>`).join("")}</span>`;
}

function renderRail(results) {
  const c = state.current;
  const clusters = state.clusters[c.id] || [];
  if (results) {
    $("rail-note").textContent = results.length
      ? `${results.length} ${results.length === 1 ? "node" : "nodes"} matching “${state.search}”`
      : `Nothing in ${shortName(c)} matches “${state.search}”. Try a tag, an identifier or part of a name.`;
    $("things").innerHTML = results.map((r) => `
      <li><a href="${href(c.id, "things", r.id)}" data-id="${escape(r.id)}" data-cluster="${escape(r.cluster || "")}">
        <span class="thing-name">${escape(r.name)}</span>
        <span class="thing-meta"><i class="dot" style="--hue:${standardOf(r.standard).color}"></i>
          ${escape(r.labels[0] || "")}${r.cluster ? "" : ' · <em>not linked</em>'}</span>
      </a></li>`).join("");
  } else {
    $("rail-note").textContent = `${clusters.length} things linked across standards`;
    $("things").innerHTML = clusters.map((t) => `
      <li><a href="${href(c.id, "things", t.id)}" data-id="${escape(t.id)}" data-cluster="${escape(t.id)}">
        <span class="thing-name">${escape(t.name)}</span>
        <span class="thing-meta">${dots(t.standards)} ${escape(t.label)}</span>
      </a></li>`).join("");
  }
  markCurrent();
}

function markCurrent() {
  for (const a of $("things").querySelectorAll("a")) {
    const current = a.dataset.id === state.thing || (a.dataset.cluster && a.dataset.cluster === state.cluster);
    if (current) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
  }
}

$("search").addEventListener("input", (event) => {
  clearTimeout(state.searchTimer);
  state.search = event.target.value.trim();
  state.searchTimer = setTimeout(async () => {
    if (!state.current?.loaded) return;
    if (!state.search) { renderRail(); return; }
    const query = state.search;
    try {
      const { results } = await api(`/crosswalks/${state.current.id}/search?q=${encodeURIComponent(query)}`);
      if (query === state.search) renderRail(results);
    } catch (error) { notice(error.message); }
  }, 220);
});

// ---- The concordance: one thing, a column per standard -----------------------------------------------------------

function renderEmptyConcordance() {
  $("concordance").innerHTML = `<div class="empty"><p>The data links nothing in this crosswalk yet.
    Search for a node on the left to see it in its own standard.</p></div>`;
}

function value(v) {
  if (Array.isArray(v)) return v.map(value).join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function card(node, focus, shared, linksOf) {
  const s = standardOf(node.standard);
  const [label, ...also] = node.labels;
  const description = node.descriptions[label] || "";
  const props = Object.entries(node.properties).sort(([a], [b]) =>
    (shared.has(b) - shared.has(a)) || (node.key.includes(b) - node.key.includes(a)) || a.localeCompare(b));
  const rels = node.relationships.map((r) => `
    <li><span class="dir" aria-label="${r.outgoing ? "outgoing" : "incoming"}">${r.outgoing ? "→" : "←"}</span>
      <span class="rel-type">${escape(r.type)}</span>
      <span class="rel-end"><a href="${href(state.current.id, "things", r.node.id)}" class="${r.node.linked ? "linked" : ""}"
         title="${escape(r.node.label)}${r.node.linked ? ", linked to other standards" : ""}">${escape(r.node.name)}</a>
      <span class="rel-label">${escape(r.node.label)}</span></span></li>`).join("");
  const more = node.total > node.relationships.length ? `<p class="more">and ${node.total - node.relationships.length} more</p>` : "";
  const links = linksOf(node.id);
  return `
    <article class="card${node.id === focus ? " focus" : ""}" id="card-${CSS.escape(node.id)}" data-id="${escape(node.id)}"
             style="--hue:${s.color}" tabindex="-1">
      <header>
        <p class="eyebrow"><span class="label" title="${escape(description)}">${escape(label || "")}</span></p>
        <h2>${escape(node.name)}</h2>
        ${also.length ? `<p class="also" title="${escape(also.join(", "))}">also ${also.slice(0, 3).map(escape).join(", ")}${
          also.length > 3 ? ` and ${also.length - 3} more` : ""}</p>` : ""}
      </header>
      <dl class="props">${props.map(([k, v]) => `
        <div class="${shared.has(k) ? "shared" : ""}${node.key.includes(k) ? " key" : ""}">
          <dt>${escape(k)}${shared.has(k) ? '<span class="shared-mark" title="Linked nodes share this value">⇄</span>' : ""}</dt>
          <dd>${escape(value(v))}</dd></div>`).join("")}
      </dl>
      ${links.length ? `<ul class="links" aria-label="Links to other standards">${links.map((l) => `
        <li><span class="glyph" title="${escape(l.words)}">${l.glyph}</span> ${escape(l.type)}
          <a href="#card-${CSS.escape(l.other.id)}" data-jump="${escape(l.other.id)}">${escape(l.other.name)}</a>
          <span class="rel-label">${escape(standardOf(l.other.standard).name)}</span></li>`).join("")}</ul>` : ""}
      <section class="relationships">
        <h3>In ${escape(s.name)} <span>${node.total} ${node.total === 1 ? "relationship" : "relationships"}</span></h3>
        <ul>${rels}</ul>${more}
      </section>
    </article>`;
}

// The properties each node of a thing shares with a node it is linked to, by the link's mapping
function sharedProperties(data) {
  const shared = Object.fromEntries(data.nodes.map((n) => [n.id, new Set()]));
  for (const link of data.links) {
    const mapping = data.mappings[link.mapping];
    if (!mapping) continue;
    for (const [ours, theirs] of Object.entries(mapping.properties)) {
      shared[link.from]?.add(ours);
      shared[link.to]?.add(theirs);
    }
  }
  return shared;
}

async function renderThing(crosswalk, nodeId) {
  const data = await api(`/crosswalks/${crosswalk.id}/nodes/${encodeURIComponent(nodeId)}`);
  if (parseRoute().node !== nodeId) return; // the reader has moved on
  state.cluster = data.cluster;
  markCurrent();
  const byId = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  const shared = sharedProperties(data);
  const linksOf = (id) => data.links.filter((l) => l.from === id || l.to === id).map((l) => {
    const predicate = PREDICATES[data.mappings[l.mapping]?.predicate] || { glyph: "·", words: "" };
    return { ...l, ...predicate, other: byId[l.from === id ? l.to : l.from] };
  }).filter((l) => l.other);

  const columns = crosswalk.standards.map((s) => {
    const nodes = data.nodes.filter((n) => n.standard === s.prefix);
    const body = nodes.length
      ? nodes.map((n) => card(n, data.focus, shared[n.id], linksOf)).join("")
      : `<p class="absent">Not described in ${escape(s.name)}${data.cluster ? "" : ", or not linked to it"}.</p>`;
    return `<div class="column" style="--hue:${s.color}">
      <p class="column-head"><span>${escape(s.name)}</span></p>${body}</div>`;
  }).join("");
  $("concordance").innerHTML = `
    <p class="concordance-tools"><a href="${href(crosswalk.id, "graph", nodeId)}">See where this sits in the graph →</a></p>
    <div class="columns" style="--columns:${crosswalk.standards.length}">${columns}
      <svg class="stitches" aria-hidden="true"></svg>
    </div>
    ${data.cluster ? "" : `<p class="unlinked-note">This node isn't linked to another standard. Its mappings may still
      cover its kind: see <a href="${href(crosswalk.id, "mappings")}">Mappings</a>.</p>`}`;
  state.lastThing = data; // kept so a resize can redraw its stitches
  stitch(data);
  // On a narrow screen the columns stack below the rail, so bring the thing the reader picked into view
  const focus = document.getElementById(`card-${CSS.escape(data.focus)}`);
  if (state.picked && focus && window.matchMedia("(max-width: 899px)").matches) focus.scrollIntoView({ block: "start" });
  state.picked = false;
}

// The signature of the explorer: each link drawn as a stitch between the cards it joins, in the gutters between
// the columns. The cards sit above the stitches, so a link that skips a standard passes behind its column.
function stitch(data) {
  const columns = $("concordance").querySelector(".columns");
  const svg = columns?.querySelector(".stitches");
  if (!svg) return;
  const frame = columns.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${frame.width} ${frame.height}`);
  svg.setAttribute("width", frame.width);
  svg.setAttribute("height", frame.height);
  const anchor = (id) => {
    const el = document.getElementById(`card-${CSS.escape(id)}`);
    if (!el) return null;
    const box = el.querySelector("header").getBoundingClientRect();
    const whole = el.getBoundingClientRect();
    return { left: whole.left - frame.left, right: whole.right - frame.left, y: box.top - frame.top + 30 };
  };
  const parts = [];
  for (const link of data.links) {
    const a = anchor(link.from), b = anchor(link.to);
    if (!a || !b) continue;
    const forwards = a.left < b.left;
    const x1 = forwards ? a.right : a.left, x2 = forwards ? b.left : b.right;
    const bend = Math.max(36, Math.abs(x2 - x1) * 0.35) * (forwards ? 1 : -1);
    const d = `M ${x1} ${a.y} C ${x1 + bend} ${a.y}, ${x2 - bend} ${b.y}, ${x2} ${b.y}`;
    const predicate = PREDICATES[data.mappings[link.mapping]?.predicate];
    const gx = forwards ? x1 + 6 : x1 - 6;
    parts.push(`
      <path class="stitch ${link.type === "SAME_AS" ? "same" : "other"}" d="${d}" pathLength="1"/>
      <circle class="knot" cx="${x1}" cy="${a.y}" r="3.5"/><circle class="knot" cx="${x2}" cy="${b.y}" r="3.5"/>
      <text class="stitch-label" x="${gx}" y="${a.y - 8}" text-anchor="${forwards ? "start" : "end"}">${
        predicate ? predicate.glyph + " " : ""}${escape(link.type)}</text>`);
  }
  svg.innerHTML = parts.join("");
}

window.addEventListener("resize", () => {
  clearTimeout(state.resizeTimer);
  state.resizeTimer = setTimeout(() => { if (state.lastThing) stitch(state.lastThing); }, 120);
});
document.fonts?.ready.then(() => { if (state.lastThing) stitch(state.lastThing); });

$("things").addEventListener("click", (event) => {
  if (event.target.closest("a")) state.picked = true;
});

$("concordance").addEventListener("click", (event) => {
  const jump = event.target.closest("[data-jump]");
  if (!jump) return;
  event.preventDefault();
  const target = document.getElementById(`card-${CSS.escape(jump.dataset.jump)}`);
  target?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
  target?.focus({ preventScroll: true });
});

// ---- The graph: every node of the crosswalk, a band per standard, and the links that bridge them ----------------

const D3 = "https://cdn.jsdelivr.net/npm/d3@7/+esm";

async function renderGraph(crosswalk, nodeId) {
  if (state.graph?.id !== crosswalk.id) {
    state.graph = null;
    $("graph-svg").innerHTML = "";
    $("graph-tip").hidden = true;
    $("graph-panel").innerHTML = "";
    state.d3 ||= await import(D3);
    if (!state.graphs[crosswalk.id]) state.graphs[crosswalk.id] = await api(`/crosswalks/${crosswalk.id}/graph`);
    if (parseRoute().id !== crosswalk.id) return; // the reader has moved on
    state.graph = drawGraph(state.d3, crosswalk, state.graphs[crosswalk.id]);
  }
  state.graph.select(nodeId);
}

function drawGraph(d3, crosswalk, data) {
  const order = crosswalk.standards.map((s) => s.prefix);
  const nodes = data.nodes.map((n) => ({ ...n }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges = data.edges.map((e) => ({ ...e, source: byId.get(e.from), target: byId.get(e.to) }));
  const neighbours = new Map(nodes.map((n) => [n.id, new Set()]));
  for (const e of edges) { neighbours.get(e.from).add(e.to); neighbours.get(e.to).add(e.from); }
  const members = new Map(); // the nodes of each linked thing, by its cluster
  for (const n of nodes) {
    n.degree = neighbours.get(n.id).size;
    if (n.cluster) members.set(n.cluster, [...(members.get(n.cluster) || []), n.id]);
  }
  const band = order.length > 2 ? 440 : 560; // the width of a standard's band, in the graph's own units
  const bandX = (n) => (order.indexOf(n.standard) + 0.5) * band;
  const height = Math.max(640, Math.sqrt(nodes.length / order.length) * 72, members.size * 40);
  const radius = (n) => Math.min(12, 4 + Math.sqrt(n.degree) * 1.4) + (n.cluster ? 2 : 0);

  // Each node starts on a spiral in its standard's band, so the layout comes out the same on every load
  const seen = {};
  for (const n of nodes) {
    const k = seen[n.standard] = (seen[n.standard] ?? -1) + 1;
    const r = 9 * Math.sqrt(k + 0.5), a = k * 2.39996;
    n.x = bandX(n) + r * Math.cos(a);
    n.y = height / 2 + r * Math.sin(a);
  }
  // A link pulls its ends level across the gap between their bands, so each bridge reads as one
  const bridges = edges.filter((e) => e.link);
  const level = (alpha) => {
    for (const e of bridges) {
      const dy = (e.target.y - e.source.y) * 0.45 * alpha;
      e.source.vy += dy;
      e.target.vy -= dy;
    }
  };
  const simulation = d3.forceSimulation(nodes)
    .force("inside", d3.forceLink(edges.filter((e) => !e.link)).distance(34))
    .force("level", level)
    .force("charge", d3.forceManyBody().strength(-60).distanceMax(240))
    .force("band", d3.forceX(bandX).strength(0.14))
    .force("middle", d3.forceY(height / 2).strength(0.035))
    .force("collide", d3.forceCollide((n) => radius(n) + 2))
    .stop();
  for (let i = 0; i < 150; i++) simulation.tick();
  // Then each linked thing gets a row of its own, in the order the layout found, so the bridges read as a ladder
  const rows = [...members.values()]
    .map((ids) => ({ ids, y: d3.mean(ids, (id) => byId.get(id).y) }))
    .sort((a, b) => a.y - b.y);
  const gap = Math.min(56, (height * 0.8) / Math.max(1, rows.length - 1));
  const row = new Map();
  rows.forEach((r, i) => r.ids.forEach((id) => row.set(id, height / 2 + (i - (rows.length - 1) / 2) * gap)));
  simulation.force("row", d3.forceY((n) => row.get(n.id) ?? height / 2).strength((n) => row.has(n.id) ? 0.6 : 0))
    .alpha(0.6);
  for (let i = 0; i < 300; i++) simulation.tick();

  const svg = d3.select("#graph-svg");
  svg.selectAll("*").remove();
  const view = svg.append("g");
  const top = d3.min(nodes, (n) => n.y) - 70, bottom = d3.max(nodes, (n) => n.y) + 30;
  const bands = view.append("g").selectAll("g").data(crosswalk.standards).join("g")
    .attr("class", "band").attr("style", (s) => `--hue:${s.color}`);
  bands.append("rect")
    .attr("x", (s, i) => i * band + 14).attr("width", band - 28)
    .attr("y", top).attr("height", bottom - top).attr("rx", 18);
  bands.append("text").attr("class", "band-name")
    .attr("x", (s, i) => i * band + 34).attr("y", top + 36).text((s) => s.name);
  bands.append("text").attr("class", "band-count")
    .attr("x", (s, i) => i * band + 34).attr("y", top + 54)
    .text((s) => `${nodes.filter((n) => n.standard === s.prefix).length} nodes`);

  const hue = (e) => `--hue:${standardOf(e.source.standard).color}`;
  const inside = view.append("g").selectAll("line").data(edges.filter((e) => !e.link)).join("line")
    .attr("class", "edge").attr("style", hue);
  const across = view.append("g").selectAll("line").data(edges.filter((e) => e.link)).join("line")
    .attr("class", (e) => `xlink ${e.type === "SAME_AS" ? "same" : "other"}`);
  across.append("title").text((e) => `${e.type}${PREDICATES[e.predicate] ? `: ${PREDICATES[e.predicate].words}` : ""}`);
  const edgeNames = view.append("g").selectAll("text").data(edges).join("text")
    .attr("class", (e) => `edge-name${e.link ? " xlink-name" : ""}`)
    .text((e) => e.link && PREDICATES[e.predicate] ? `${PREDICATES[e.predicate].glyph} ${e.type}` : e.type);
  const circles = view.append("g").selectAll("circle").data(nodes).join("circle")
    .attr("class", (n) => `node${n.cluster ? " linked" : ""}`)
    .attr("style", (n) => `--hue:${standardOf(n.standard).color}`)
    .attr("r", radius);
  const names = view.append("g").selectAll("text").data(nodes).join("text")
    .attr("class", (n) => `name ${n.cluster ? "major" : "minor"}`)
    .text((n) => n.name.length > 34 ? n.name.slice(0, 32) + "…" : n.name);

  function draw() {
    for (const lines of [inside, across]) {
      lines.attr("x1", (e) => e.source.x).attr("y1", (e) => e.source.y)
        .attr("x2", (e) => e.target.x).attr("y2", (e) => e.target.y);
    }
    edgeNames.attr("x", (e) => (e.source.x + e.target.x) / 2).attr("y", (e) => (e.source.y + e.target.y) / 2 - 3);
    circles.attr("cx", (n) => n.x).attr("cy", (n) => n.y);
    names.attr("x", (n) => n.x + radius(n) + 4).attr("y", (n) => n.y + 4);
  }
  draw();
  simulation.on("tick", draw);

  const zoom = d3.zoom().scaleExtent([0.15, 6]).on("zoom", (event) => {
    view.attr("transform", event.transform);
    svg.classed("close", event.transform.k > 1.7);
  });
  svg.call(zoom).on("dblclick.zoom", null);
  const motion = () => matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 650;
  function fit(ids) {
    const stage = $("graph-stage");
    const width = stage.clientWidth, tall = stage.clientHeight - 110; // clear of the tools above and the legend below
    let x0 = 0, x1 = order.length * band, y0 = top, y1 = bottom;
    if (ids?.length) {
      const picked = ids.map((id) => byId.get(id));
      x0 = d3.min(picked, (n) => n.x) - 90; x1 = d3.max(picked, (n) => n.x) + 160;
      y0 = d3.min(picked, (n) => n.y) - 70; y1 = d3.max(picked, (n) => n.y) + 70;
    }
    const k = Math.min(ids?.length ? 1.5 : 2.4, 0.94 * Math.min(width / (x1 - x0), tall / (y1 - y0)));
    const transform = d3.zoomIdentity.translate(width / 2, 60 + tall / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    svg.transition().duration(motion()).call(zoom.transform, transform);
  }

  circles.call(d3.drag()
    .on("start", (event, n) => { if (!event.active) simulation.alphaTarget(0.06).restart(); n.fx = n.x; n.fy = n.y; })
    .on("drag", (event, n) => { n.fx = event.x; n.fy = event.y; })
    .on("end", (event, n) => { if (!event.active) simulation.alphaTarget(0); n.fx = null; n.fy = null; }));
  circles.on("click", (event, n) => {
    event.stopPropagation();
    location.hash = href(crosswalk.id, "graph", n.id);
  });
  svg.on("click", () => { if (parseRoute().node) location.hash = href(crosswalk.id, "graph"); });

  const tip = $("graph-tip");
  circles.on("mouseenter mousemove", (event, n) => {
    const frame = $("graph-stage").getBoundingClientRect();
    const others = n.cluster ? members.get(n.cluster).length - 1 : 0;
    tip.innerHTML = `<strong>${escape(n.name)}</strong>
      <span><i class="dot" style="--hue:${standardOf(n.standard).color}"></i>${escape(n.label)} in ${escape(standardOf(n.standard).name)}</span>
      ${others ? `<span>Linked to ${others} ${others === 1 ? "node" : "nodes"} in other standards</span>` : ""}`;
    tip.style.left = `${event.clientX - frame.left + 14}px`;
    tip.style.top = `${event.clientY - frame.top + 14}px`;
    tip.hidden = false;
    edgeNames.classed("hover", (e) => e.from === n.id || e.to === n.id);
    names.classed("hover", (m) => m.id === n.id || neighbours.get(n.id).has(m.id));
  }).on("mouseleave", () => {
    tip.hidden = true;
    edgeNames.classed("hover", false);
    names.classed("hover", false);
  });

  $("graph-legend").innerHTML = `
    ${crosswalk.standards.map((s) => `<span><i class="dot" style="--hue:${s.color}"></i>${escape(s.name)}</span>`).join("")}
    <span><i class="ring"></i>Linked across standards</span>
    <span><svg width="26" height="8"><line class="xlink same" x1="1" y1="4" x2="25" y2="4"/></svg>Crosswalk link</span>
    <span><svg width="26" height="8"><line class="xlink other" x1="1" y1="4" x2="25" y2="4"/></svg>Other link</span>
    <span><svg width="26" height="8"><line class="edge sample" x1="1" y1="4" x2="25" y2="4"/></svg>Within a standard</span>`;

  // Picking a node lights up the thing it is in every standard, and every node next to one of them
  function select(id) {
    const focus = byId.get(id);
    const picked = focus ? (focus.cluster ? members.get(focus.cluster) : [focus.id]) : [];
    const near = new Set(picked);
    for (const p of picked) for (const other of neighbours.get(p)) near.add(other);
    const touches = (e) => picked.includes(e.from) || picked.includes(e.to);
    svg.classed("focused", !!focus);
    circles.classed("on", (n) => near.has(n.id)).classed("focus", (n) => picked.includes(n.id));
    names.classed("on", (n) => near.has(n.id)).classed("focus", (n) => picked.includes(n.id));
    inside.classed("on", touches);
    across.classed("on", touches);
    edgeNames.classed("on", touches);
    if (focus) fit([...near]); else if (state.graph) fit();
    renderGraphPanel(crosswalk, id && focus ? id : null, { nodes, edges });
  }

  $("graph-find").value = "";
  $("graph-find").oninput = (event) => {
    const text = event.target.value.trim().toLowerCase();
    svg.classed("finding", !!text);
    circles.classed("match", (n) => text && n.name.toLowerCase().includes(text));
    names.classed("match", (n) => text && n.name.toLowerCase().includes(text));
    const count = text ? circles.filter(".match").size() : 0;
    $("graph-found").textContent = !text ? "" : count ? `${count} ${count === 1 ? "match" : "matches"} · Enter to pick`
      : "No node by that name";
  };
  $("graph-find").onkeydown = (event) => {
    if (event.key === "Escape") { event.target.value = ""; event.target.oninput(event); }
    if (event.key !== "Enter") return;
    const text = event.target.value.trim().toLowerCase();
    const found = nodes.filter((n) => text && n.name.toLowerCase().includes(text))
      .sort((a, b) => (!a.cluster - !b.cluster) || (b.degree - a.degree))[0];
    if (!found) return;
    event.target.value = "";
    event.target.oninput(event);
    location.hash = href(crosswalk.id, "graph", found.id);
  };
  $("graph-fit").onclick = () => fit();
  $("graph-names").onchange = (event) => svg.classed("all-names", event.target.checked);
  svg.classed("all-names", $("graph-names").checked);

  fit();
  return { id: crosswalk.id, select };
}

async function renderGraphPanel(crosswalk, nodeId, graph) {
  const panel = $("graph-panel");
  if (!nodeId) {
    const clusters = await clustersOf(crosswalk);
    const links = graph.edges.filter((e) => e.link).length;
    panel.innerHTML = `
      <p class="panel-kicker">How to read this graph</p>
      <h2>The same world, as ${crosswalk.standards.length} standards record it</h2>
      <ul class="guide">
        ${crosswalk.standards.map((s) => {
          const count = graph.nodes.filter((n) => n.standard === s.prefix).length;
          const inside = graph.edges.filter((e) => !e.link && e.source.standard === s.prefix).length;
          return `<li><i class="dot" style="--hue:${s.color}"></i><span><b>${escape(s.name)}</b>
            ${count} nodes and ${inside} relationships, in its own vocabulary</span></li>`;
        }).join("")}
        <li><svg width="22" height="10"><line class="xlink same" x1="1" y1="5" x2="21" y2="5"/></svg><span>
          <b>${links} crosswalk links</b> bridge the bands. Each joins two nodes that describe the same thing,
          following one of the crosswalk's <a href="${href(crosswalk.id, "mappings")}">${crosswalk.mappings} mappings</a>.</span></li>
        <li><i class="ring"></i><span><b>${clusters.length} things</b> are described by more than one standard.
          They're ringed and named.</span></li>
      </ul>
      <p class="hint">Click a node to see it in every standard. Drag to rearrange, scroll to zoom, click the background to
        step back.</p>
      ${clusters.length ? `<h3>Try one</h3><ul class="picks">${clusters.slice(0, 10).map((c) => `
        <li><a href="${href(crosswalk.id, "graph", c.id)}">${dots(c.standards)}<span>${escape(c.name)}</span>
          <span class="rel-label">${escape(c.label)}</span></a></li>`).join("")}</ul>` : ""}`;
    return;
  }
  const data = await api(`/crosswalks/${crosswalk.id}/nodes/${encodeURIComponent(nodeId)}`);
  if (parseRoute().node !== nodeId || parseRoute().view !== "graph") return; // the reader has moved on
  const shared = sharedProperties(data);
  const byId = Object.fromEntries(data.nodes.map((n) => [n.id, n]));
  const lead = byId[data.focus] || data.nodes[0];
  const standards = new Set(data.nodes.map((n) => n.standard));
  const term = (n) => `<span class="term-inline" style="--hue:${standardOf(n.standard).color}">${escape(standardOf(n.standard).name)}
    <b>${escape(n.labels[0] || "")}</b></span>`;
  const bridges = data.links.filter((l) => byId[l.from] && byId[l.to]).map((l) => {
    const p = PREDICATES[data.mappings[l.mapping]?.predicate];
    return `<li>${term(byId[l.from])} <span class="glyph" title="${escape(l.type)}">${p ? p.glyph : "·"}</span>
      ${p ? escape(p.words) : escape(l.type)} ${term(byId[l.to])}</li>`;
  }).join("");
  const mini = (n) => {
    const props = Object.entries(n.properties).sort(([a], [b]) =>
      (shared[n.id].has(b) - shared[n.id].has(a)) || (n.key.includes(b) - n.key.includes(a)) || a.localeCompare(b));
    return `<article class="mini" style="--hue:${standardOf(n.standard).color}">
      <p class="eyebrow">${escape(standardOf(n.standard).name)} · <span class="label" title="${escape(n.descriptions[n.labels[0]] || "")}">${
        escape(n.labels[0] || "")}</span></p>
      <h4>${escape(n.name)}</h4>
      <dl class="props">${props.slice(0, 6).map(([k, v]) => `
        <div class="${shared[n.id].has(k) ? "shared" : ""}"><dt>${escape(k)}${
          shared[n.id].has(k) ? '<span class="shared-mark" title="Linked nodes share this value">⇄</span>' : ""}</dt>
          <dd>${escape(value(v))}</dd></div>`).join("")}</dl>
      <p class="more">${props.length > 6 ? `${props.length - 6} more properties · ` : ""}${n.total} ${
        n.total === 1 ? "relationship" : "relationships"} in ${escape(standardOf(n.standard).name)}</p>
    </article>`;
  };
  panel.innerHTML = `
    <p class="panel-kicker">${standards.size > 1 ? `One thing, described by ${standards.size} standards`
      : `Described by ${escape(standardOf(lead.standard).name)} alone`}</p>
    <h2>${escape(lead.name)}</h2>
    ${bridges ? `<ul class="bridges">${bridges}</ul>` : `<p class="hint">Nothing links this node to another standard.
      It sits in the graph only through its relationships in its own.</p>`}
    ${data.nodes.map(mini).join("")}
    ${Object.values(shared).some((s) => s.size) ? `<p class="hint">Values marked ⇄ are the ones the mapping says both
      standards must agree on.</p>` : ""}
    <p><a class="panel-action" href="${href(crosswalk.id, "things", nodeId)}">Compare side by side →</a></p>`;
}

// ---- Mappings ------------------------------------------------------------------------------------------------------

async function renderMappings(crosswalk) {
  const { mappings } = await api(`/crosswalks/${crosswalk.id}/mappings`);
  const side = (end) => `<span class="term" style="--hue:${standardOf(end.standard).color}">
    <span class="term-standard">${escape(standardOf(end.standard).name)}</span>${escape(end.label)}</span>`;
  $("mappings").innerHTML = `
    <p class="mappings-intro">Each mapping says how a kind of node in one standard corresponds to a kind in another,
      and which link joins their data. Linked nodes must agree on the properties a mapping names.</p>
    <details class="diagram">
      <summary>See the mappings as a diagram</summary>
      <img src="/api/crosswalks/${encodeURIComponent(crosswalk.id)}/diagram.svg" loading="lazy"
           alt="The kinds of node each mapping joins, a colour per standard">
    </details>
    <ol class="mapping-list">${mappings.map((m) => {
      const p = PREDICATES[m.predicate] || { glyph: "·", words: m.predicate };
      const props = Object.entries(m.properties);
      return `<li class="mapping">
        <div class="mapping-row">
          ${side(m.subject)}
          <span class="predicate"><span class="glyph" aria-hidden="true">${p.glyph}</span>${escape(p.words)}</span>
          ${side(m.object)}
          <span class="mapping-link">${escape(m.link)} · ${m.pairs.length} ${m.pairs.length === 1 ? "pair" : "pairs"}</span>
        </div>
        <details>
          <summary>Why, and the linked pairs</summary>
          ${m.comment ? `<p>${escape(m.comment)}</p>` : ""}
          ${props.length ? `<p class="shared-props">Linked nodes share ${props.map(([a, b]) =>
            `<code>${escape(a)}</code>${a === b ? "" : ` = <code>${escape(b)}</code>`}`).join(", ")}.</p>` : ""}
          ${m.source ? `<p class="source">Source: <a href="${escape(m.source)}" rel="noopener" target="_blank">${escape(m.source)}</a></p>` : ""}
          ${m.pairs.length ? `<ul class="pairs">${m.pairs.map((pair) => `<li>
            <a href="${href(crosswalk.id, "things", pair.from.id)}">${escape(pair.from.name)}</a>
            <span aria-hidden="true">⇄</span>
            <a href="${href(crosswalk.id, "things", pair.to.id)}">${escape(pair.to.name)}</a></li>`).join("")}</ul>`
            : `<p class="absent">The sample data links no pair by this mapping.</p>`}
        </details>
      </li>`;
    }).join("")}</ol>`;
}

// ---- Start -----------------------------------------------------------------------------------------------------

async function start() {
  try {
    const data = await api("/crosswalks");
    state.crosswalks = data.crosswalks;
    state.connected = data.connected;
    state.error = data.error;
    if (!data.connected) notice(`Not connected to the database: ${data.error}`);
  } catch (error) {
    notice(`The explorer's server didn't answer: ${error.message}`);
    return;
  }
  window.addEventListener("hashchange", route);
  route();
}

start();
