/* LEIA Mission Control — read-only dashboard views (Command Center, Search Intelligence,
   AI Search). Renders /api/mc/* into #view-mc / #view-si / #view-ai. Vanilla JS; ApexCharts
   (vendored) for gauges/sparklines/heatmap, with plain-DOM fallbacks. One view active at a time. */
(function () {
  const esc = s => (s ?? "").toString().replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const $ = id => document.getElementById(id);
  const HAS_APEX = () => typeof window.ApexCharts !== "undefined";
  // Disable ALL ApexCharts animations globally so charts render to a stable frame immediately
  // (no demo flicker, and screenshot grabbers don't hang waiting for animation to settle).
  window.Apex = { chart: { animations: { enabled: false }, redrawOnWindowResize: false,
                           redrawOnParentResize: false },
                  states: { active: { filter: { type: "none" } } } };
  const OWN = { owned: 4, controlled: 3, influenced: 2, competitor: 1, unknown: 0 };
  const OWN_COLOR = { 0: "#1b2531", 1: "#f87171", 2: "#fbbf24", 3: "#38bdf8", 4: "#34d399" };
  const fmt = v => (v === null || v === undefined) ? "—" : v;

  const MC = { view: null, client: null, timer: null, charts: {} };
  window.MC = MC;
  function killCharts() { for (const k in MC.charts) { try { MC.charts[k].destroy(); } catch (e) {} } MC.charts = {}; }

  const ENDPOINT = { mc: "/api/mc/command_center", si: "/api/mc/search_intelligence", ai: "/api/mc/ai_search", ci: "/api/mc/competition_intell", ti: "/api/mc/threat_intelligence" };
  const SHELL = {}, RENDER = {};

  async function fetchView(view) {
    const q = MC.client ? `?client=${encodeURIComponent(MC.client)}` : "";
    const r = await fetch(ENDPOINT[view] + q); return r.json();
  }

  function deltaChip(d, goodDir = "up") {
    if (!d) return `<span class="delta muted">— no prior</span>`;
    const arrow = d.dir === "up" ? "▲" : d.dir === "down" ? "▼" : "—";
    const cls = d.dir === "flat" ? "flat" : (d.dir === goodDir ? "up" : "down");
    const pct = (d.pct === null || d.pct === undefined) ? "" : ` ${d.pct > 0 ? "+" : ""}${d.pct}%`;
    return `<span class="delta ${cls}">${arrow} ${esc(d.abs)}${pct}</span>`;
  }
  function clientSelect(id, clients, current) {
    const sel = $(id); if (!sel) return;
    const sig = (clients || []).join("|");
    if (sel.dataset.sig !== sig) {
      sel.innerHTML = (clients || []).map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("")
        || `<option value="">(no clients)</option>`;
      sel.dataset.sig = sig;
    }
    if (current) sel.value = current;
  }
  const gauge = (el, pct, color) => {
    if (!HAS_APEX()) { el.innerHTML = `<div style="font-size:28px;font-weight:700;text-align:center;padding-top:48px">${pct}%</div>`; return; }
    const ch = new ApexCharts(el, {
      chart: { type: "radialBar", height: 150, sparkline: { enabled: true } },
      series: [pct], colors: [color],
      plotOptions: { radialBar: { hollow: { size: "58%" }, track: { background: "#1b2531" },
        dataLabels: { name: { show: false }, value: { color: "#e6edf3", fontSize: "20px", fontWeight: 700, offsetY: 6, formatter: v => v + "%" } } } }
    });
    ch.render(); MC.charts[el.id] = ch;
  };

  /* ============================ COMMAND CENTER ============================ */
  SHELL.mc = function () {
    const host = $("view-mc"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls">
          <span class="mc-title" id="mc-title">Command Center</span>
          <select id="mc-client" class="mc-sel"></select>
          <span class="mc-spacer"></span>
          <button id="mc-csv" class="mc-btn" type="button" title="Download takeover data as CSV">⬇ CSV</button>
          <button id="mc-print" class="mc-btn" type="button" title="Print / save as PDF report">🖨 Report</button>
          <span id="mc-fresh" class="mc-chip">—</span><span id="mc-cost" class="mc-chip">—</span>
        </div>
        <div class="mc-health-band">
          <div class="panel hs-panel"><h3>Search health score <span class="h-accent"></span></h3>
            <div class="hs-wrap"><div class="hs-ring" id="mc-hs-ring"></div>
              <div class="hs-comps" id="mc-hs-comps"></div></div></div>
          <div class="panel"><h3>Intelligence briefing <span style="font-weight:400;color:var(--dim);font-size:11px;">— live, from your data</span> <span class="h-accent"></span></h3>
            <div id="mc-briefing" class="briefing"></div></div>
        </div>
        <div class="mc-hero">
          <div class="panel"><h3>SERP Saturation — multi-presence goal <span class="h-accent"></span></h3>
            <div class="mc-gaugewrap"><div id="mc-gauge" style="width:150px;height:150px"></div>
              <div class="mc-goal" style="flex:1"><div class="big" id="mc-goal-big">—</div>
                <div class="sub" id="mc-goal-sub"></div>
                <div class="mc-progress"><span id="mc-goal-bar" style="width:0%"></span></div>
                <div class="mc-lanes" id="mc-lanes"></div></div></div></div>
          <div class="panel"><h3>Headline KPIs <span class="h-accent"></span></h3><div class="mc-kpis" id="mc-kpis"></div></div>
        </div>
        <div class="mc-sources" id="mc-sources"></div>
        <div class="mc-grid">
          <div class="panel"><h3>Feature ownership — keyword × SERP feature <span class="h-accent"></span></h3>
            <div class="mc-heatmap" id="mc-heatmap"></div>
            <div class="legend-row"><span><i style="background:#34d399"></i>owned</span><span><i style="background:#38bdf8"></i>controlled</span><span><i style="background:#fbbf24"></i>influenced</span><span><i style="background:#f87171"></i>competitor</span><span><i style="background:#1b2531"></i>not present</span></div></div>
          <div class="panel"><h3>Cross-source action skyline <span class="h-accent"></span></h3><div class="sky" id="mc-sky"></div></div>
        </div>
        <div class="mc-grid even" style="margin-top:13px">
          <div class="panel"><h3>Takeover leaderboard — appearances per keyword <span class="h-accent"></span></h3>
            <div id="mc-leaderboard" style="height:260px;"></div></div>
          <div class="panel"><h3>SERP-feature share of voice <span class="h-accent"></span></h3>
            <div id="mc-sov" style="height:260px;"></div></div>
        </div>
        <div class="mc-grid" style="margin-top:13px">
          <div class="panel"><h3>Takeover trend — run over run <span class="h-accent"></span></h3>
            <div id="mc-trend" style="height:240px;"></div></div>
          <div class="panel"><h3>Top opportunities — biggest gaps × lead value <span class="h-accent"></span></h3>
            <div id="mc-opps"></div></div>
        </div>
      </div>`;
    $("mc-client").onchange = e => window.mcSetClient(e.target.value);
    $("mc-print").onclick = () => window.print();
    $("mc-csv").onclick = exportMcCsv;
    if (!MC.catalog) fetch("/api/catalog").then(r => r.json()).then(c => { MC.catalog = c; if (MC.view === "mc") refresh(); }).catch(() => {});
  };
  async function createWorkOrder(client, workflow_id, target, reason, btn) {
    btn.disabled = true; btn.textContent = "creating…";
    try {
      const r = await fetch("/api/create", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client, workflow_id, target, period: new Date().toISOString().slice(0, 10),
          task_params: { reason, source: "command-center" } }) });
      const j = await r.json();
      if (j.ok) { btn.textContent = "✓ " + String(j.work_order_id).slice(-10); btn.classList.add("wo-ok"); }
      else { btn.textContent = "✗ " + (j.error || "failed"); btn.disabled = false; }
    } catch (e) { btn.textContent = "✗ error"; btn.disabled = false; }
  }
  function downloadCSV(filename, headers, rows) {
    const q = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [headers.map(q).join(","), ...rows.map(r => r.map(q).join(","))].join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    a.download = filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function exportMcCsv() {
    const d = MC.last || {}, lb = ((d.analytics || {}).takeover_leaderboard) || [];
    const rows = lb.map(r => [r.keyword, r.appearances, r.meets_goal ? "yes" : "no", (r.features || []).join("; ")]);
    if (!rows.length) { alert("No takeover data to export yet."); return; }
    const client = (d.client || "client").replace(/[^a-z0-9]+/gi, "-");
    downloadCSV(`takeover-${client}.csv`, ["Keyword", "Appearances", "Meets goal", "Features held"], rows);
  }
  RENDER.mc = function (d) {
    $("mc-title").textContent = d.title || "Command Center";
    clientSelect("mc-client", d.clients, d.client);
    const f = d.freshness || {}, fc = $("mc-fresh");
    fc.textContent = f.signals_date ? `signals ${f.signals_date} · ${f.signals_age_days ?? "?"}d` : "no signals yet";
    fc.className = "mc-chip " + (f.stale ? "warn" : "ok");
    const c = d.cost || {}, cc = $("mc-cost");
    cc.textContent = c.circuit_open ? "DataForSEO circuit OPEN" : `last run $${fmt(c.last_run_cost)}`;
    cc.className = "mc-chip " + (c.circuit_open ? "bad" : "");

    // ---- Search health score + intelligence briefing ----
    const h = d.health || {}, hcolor = v => v >= 70 ? "#34d399" : v >= 40 ? "#fbbf24" : "#f87171";
    const ring = $("mc-hs-ring");
    if (ring) {
      if (HAS_APEX() && h.overall != null) {
        const ch = new ApexCharts(ring, {
          chart: { type: "radialBar", height: 190, sparkline: { enabled: true } },
          series: [h.overall], colors: [hcolor(h.overall)],
          plotOptions: { radialBar: { hollow: { size: "56%" }, track: { background: "#1b2531" },
            dataLabels: { name: { offsetY: 22, color: "#7d8a9a", fontSize: "12px", formatter: () => "GRADE " + (h.grade || "—") },
              value: { offsetY: -12, color: "#e6edf3", fontSize: "34px", fontWeight: 700, formatter: v => Math.round(v) } } } }
        });
        ch.render(); MC.charts.mc_hs_ring = ch;
      } else { ring.innerHTML = `<div style="font-size:40px;font-weight:700;text-align:center;padding-top:60px">${fmt(h.overall)}<div style="font-size:12px;color:var(--dim)">${esc(h.grade || "")}</div></div>`; }
    }
    $("mc-hs-comps").innerHTML = (h.components || []).map(cp => {
      const sc = cp.score, w = sc == null ? 0 : sc;
      return `<div class="hs-comp"><div class="hs-c-top"><span>${esc(cp.label)}</span><b style="color:${cp.score == null ? "var(--dim)" : hcolor(sc)}">${sc == null ? "n/a" : sc}</b></div>
        <div class="hs-bar"><span style="width:${w}%;background:${hcolor(w)}"></span></div>
        <div class="hs-c-detail">${esc(cp.detail)}</div></div>`;
    }).join("");
    const sevPill = { good: "ok", warn: "warn", info: "" };
    $("mc-briefing").innerHTML = ((d.briefing || {}).items || []).map(it =>
      `<div class="brief-item brief-${esc(it.severity)}"><span class="brief-cat">${esc(it.category)}</span>
        <span class="brief-text">${esc(it.text)}</span></div>`).join("")
      || `<div class="mc-empty">No briefing yet.</div>`;

    const s = d.saturation || {}, pct = Math.round((s.pct_meeting_goal || 0) * 100);
    $("mc-goal-big").innerHTML = `${fmt(s.n_meeting_goal)}<small>/${fmt(s.n_serps)} SERPs</small>`;
    $("mc-goal-sub").textContent = `appear ${fmt(s.goal_min)}–${fmt(s.goal_stretch)}+ times on the same SERP · avg ${fmt(s.avg_presence)} appearances/page (lanes unioned, AI citations counted)`;
    $("mc-goal-bar").style.width = pct + "%";
    $("mc-gauge").innerHTML = ""; gauge($("mc-gauge"), pct, "#34d399");
    const bl = s.by_lane || {};
    $("mc-lanes").innerHTML = Object.keys(bl).length ? Object.entries(bl).map(([ln, v]) => {
      const lp = Math.round((v.pct_meeting_goal || 0) * 100);
      return `<div class="lane"><div class="l-name">${esc(ln)}</div><div class="l-val">${lp}%</div><div class="l-bar"><span style="width:${lp}%"></span></div></div>`;
    }).join("") : `<div class="mc-empty">No SERP tracker history yet — run the tracker.</div>`;
    const dl = s.delta || {};
    $("mc-kpis").innerHTML = [
      { l: "SERPs at goal", v: `${fmt(s.n_meeting_goal)}<small>/${fmt(s.n_serps)}</small>`, d: dl.n_meeting_goal },
      { l: "Avg appearances / page", v: fmt(s.avg_presence), d: dl.avg_presence },
      { l: `% meeting ${fmt(s.goal_min)}+`, v: pct + "%", d: dl.pct_meeting_goal },
      { l: "Real SERPs tracked", v: fmt(s.n_serps), d: null },
    ].map(k => `<div class="kpi"><div class="k-label">${esc(k.l)}</div><div class="k-val">${k.v}</div>${deltaChip(k.d, "up")}</div>`).join("");

    const cards = d.source_cards || [];
    $("mc-sources").innerHTML = cards.length ? cards.map(c2 => {
      const h = c2.headline || {};
      const metrics = (c2.metrics || []).map(m => `<span>${esc(m.label)} <b>${fmt(m.value)}</b></span>`).join("");
      return `<div class="src"><div class="s-top"><span class="s-name">${esc(c2.label)}</span><span class="dot ${esc(c2.status)}"></span></div>
        <div class="s-head"><span class="s-val">${fmt(h.value)}</span><span class="s-unit">${esc(h.unit || "")}</span>${deltaChip(h.delta, "up")}</div>
        <div class="s-metrics">${metrics}</div><div class="s-spark" id="spark-${esc(c2.key)}"></div>
        ${c2.note ? `<div class="s-note">${esc(c2.note)}</div>` : ""}</div>`;
    }).join("") : `<div class="mc-empty">No connected data sources.</div>`;
    if (HAS_APEX()) cards.forEach(c2 => {
      if (!c2.sparkline || !c2.sparkline.length) return;
      const el = $("spark-" + c2.key); if (!el) return;
      const ch = new ApexCharts(el, { chart: { type: "area", height: 38, sparkline: { enabled: true } },
        stroke: { width: 2, curve: "smooth" }, colors: ["#38bdf8"], fill: { type: "gradient", gradient: { opacityFrom: .4, opacityTo: 0 } },
        series: [{ data: c2.sparkline }], tooltip: { enabled: false } });
      ch.render(); MC.charts["spark_" + c2.key] = ch;
    });

    const m = d.ownership_matrix || { features: [], rows: [] }, el = $("mc-heatmap");
    if (!m.rows.length) el.innerHTML = `<div class="mc-empty">No SERP feature data yet.</div>`;
    else if (!HAS_APEX()) el.innerHTML = `<div class="mc-empty">${m.rows.length} keywords × ${m.features.length} features.</div>`;
    else {
      const series = m.rows.map(r => ({ name: (r.keyword.length > 22 ? r.keyword.slice(0, 21) + "…" : r.keyword),
        data: m.features.map(ft => ({ x: ft, y: OWN[r.cells[ft]] ?? 0 })) }));
      const ch = new ApexCharts(el, { chart: { type: "heatmap", height: Math.max(220, 28 * series.length + 60), toolbar: { show: false }, background: "transparent" },
        theme: { mode: "dark" }, series, dataLabels: { enabled: false }, colors: ["#34d399"],
        xaxis: { labels: { style: { colors: "#7d8a9a", fontSize: "9px" }, rotate: -40 } },
        yaxis: { labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } }, grid: { borderColor: "#222c39" },
        plotOptions: { heatmap: { radius: 3, enableShades: false, colorScale: { ranges: [
          { from: 0, to: 0, color: OWN_COLOR[0] }, { from: 1, to: 1, color: OWN_COLOR[1] }, { from: 2, to: 2, color: OWN_COLOR[2] },
          { from: 3, to: 3, color: OWN_COLOR[3] }, { from: 4, to: 4, color: OWN_COLOR[4] }] } } }, tooltip: { theme: "dark" } });
      ch.render(); MC.charts.heatmap = ch;
    }
    const sky = d.action_skyline || [];
    $("mc-sky").innerHTML = sky.length ? sky.map(a => `<div class="act ${esc(a.severity)}">
      <div class="a-top"><span class="a-title">${esc(a.title)}</span><span class="a-metric">${esc(a.metric)}</span></div>
      <div class="a-detail">${esc(a.detail)}</div><div class="a-src">${esc(a.source)}</div></div>`).join("")
      : `<div class="mc-empty">Nothing urgent — every tracked SERP is at goal.</div>`;

    // ---- Real-data analytics (from the SERP tracker) ----
    const an = d.analytics || {};

    // Takeover leaderboard — appearances per keyword (green = at goal)
    const lb = an.takeover_leaderboard || [], lbEl = $("mc-leaderboard");
    if (HAS_APEX() && lb.length && lbEl) {
      const ch = new ApexCharts(lbEl, {
        chart: { type: "bar", height: 260, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [{ name: "Appearances", data: lb.map(r => r.appearances) }],
        plotOptions: { bar: { horizontal: true, borderRadius: 4, distributed: true, barHeight: "62%" } },
        colors: lb.map(r => r.meets_goal ? "#34d399" : "#f87171"),
        xaxis: { categories: lb.map(r => r.keyword.length > 26 ? r.keyword.slice(0, 25) + "…" : r.keyword), labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } },
        yaxis: { labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } },
        dataLabels: { enabled: true, style: { colors: ["#0d1117"] } },
        grid: { borderColor: "#222c39" }, legend: { show: false },
        annotations: { xaxis: [{ x: (lb[0] && lb[0].goal_min) || 2, borderColor: "#1f6feb", strokeDashArray: 3, label: { text: "goal", style: { color: "#7d8a9a", background: "#11171f" } } }] },
        tooltip: { theme: "dark", y: { formatter: (v, o) => { const r = lb[o.dataPointIndex] || {}; return v + " appearances" + (r.meets_goal ? " · goal met" : "") + (r.features && r.features.length ? " · " + r.features.join(", ") : ""); } } }
      });
      ch.render(); MC.charts.mc_leaderboard = ch;
    } else if (lbEl) lbEl.innerHTML = `<div class="mc-empty">No tracker data yet.</div>`;

    // SERP-feature share of voice — who owns each feature (100% stacked)
    const sov = (an.feature_sov || []).slice(0, 10), sovEl = $("mc-sov");
    if (HAS_APEX() && sov.length && sovEl) {
      const ch = new ApexCharts(sovEl, {
        chart: { type: "bar", height: 260, stacked: true, stackType: "100%", background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [
          { name: "You", data: sov.map(b => b.client) },
          { name: "Competitor", data: sov.map(b => b.competitor) },
          { name: "Aggregator", data: sov.map(b => b.aggregator) },
          { name: "Unmatched", data: sov.map(b => b.unmatched) },
        ],
        colors: ["#34d399", "#f87171", "#a78bfa", "#3a4656"],
        plotOptions: { bar: { horizontal: true, barHeight: "72%" } },
        xaxis: { categories: sov.map(b => b.feature), labels: { style: { colors: "#7d8a9a", fontSize: "9px" } } },
        yaxis: { labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } },
        legend: { position: "top", labels: { colors: "#7d8a9a" } },
        grid: { borderColor: "#222c39" }, dataLabels: { enabled: false },
        tooltip: { theme: "dark" }
      });
      ch.render(); MC.charts.mc_sov = ch;
    } else if (sovEl) sovEl.innerHTML = `<div class="mc-empty">No feature data yet.</div>`;

    // Takeover trend — run over run
    const tr = an.trend || [], trEl = $("mc-trend");
    if (HAS_APEX() && tr.length > 1 && trEl) {
      const ch = new ApexCharts(trEl, {
        chart: { type: "line", height: 240, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [
          { name: "% meeting goal", data: tr.map(t => Math.round((t.pct_meeting_goal || 0) * 100)) },
          { name: "avg appearances", data: tr.map(t => t.avg_presence) },
        ],
        colors: ["#34d399", "#38bdf8"], stroke: { width: 2.5, curve: "smooth" }, markers: { size: 3 },
        xaxis: { categories: tr.map(t => t.run.slice(0, 8)), labels: { style: { colors: "#7d8a9a", fontSize: "9px" }, rotate: -30 } },
        yaxis: { labels: { style: { colors: "#7d8a9a" }, formatter: v => Math.round(v) } },
        legend: { labels: { colors: "#7d8a9a" } }, grid: { borderColor: "#222c39" },
        tooltip: { theme: "dark" }
      });
      ch.render(); MC.charts.mc_trend = ch;
    } else if (trEl) trEl.innerHTML = `<div class="mc-empty">Need ≥2 tracker runs for a trend.</div>`;

    // Top opportunities — biggest gaps weighted by lead value (one-click → Kanban work order)
    const opps = an.opportunities || [];
    const wf = ((MC.catalog || {})[d.client] || {}).workflows || [];
    const wfOpts = wf.map(w => `<option value="${esc(w.id)}">${esc(w.id)}</option>`).join("");
    $("mc-opps").innerHTML = opps.length ? opps.map(o => {
      const reason = `Takeover gap ${o.gap} on “${o.keyword}” (${o.os}) — claim ${(o.unclaimed || []).join(", ") || "features"}`;
      const ctrl = wfOpts
        ? `<div class="wo-row"><select class="wo-pick mc-sel">${wfOpts}</select>
             <button class="mc-btn wo-go" data-kw="${esc(o.keyword)}" data-reason="${esc(reason)}">+ Work order</button></div>`
        : `<div class="a-src">priority score ${o.score}</div>`;
      return `<div class="act ${o.gap >= 2 ? "high" : "med"}">
        <div class="a-top"><span class="a-title">${esc(o.keyword)} <span style="color:var(--dim);font-size:10px">(${esc(o.os)})</span></span><span class="a-metric">gap ${o.gap} · ${esc(o.lead_value || "—")}</span></div>
        <div class="a-detail">holds ${o.appearances} — claim: ${esc((o.unclaimed || []).join(", ") || "extend placements")}</div>
        ${ctrl}</div>`;
    }).join("") : `<div class="mc-empty">Every tracked SERP is at goal 🎉</div>`;
    $("mc-opps").querySelectorAll(".wo-go").forEach(btn => btn.onclick = () => {
      const sel = btn.parentElement.querySelector(".wo-pick");
      createWorkOrder(d.client, sel.value, btn.dataset.kw, btn.dataset.reason, btn);
    });
  };

  /* ============================ SEARCH INTELLIGENCE ============================ */
  SHELL.si = function () {
    const host = $("view-si"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title">Search Intelligence</span>
          <select id="si-client" class="mc-sel"></select><span class="mc-spacer"></span></div>
        <div class="mc-hero">
          <div class="panel"><h3>Google Search Console <span class="h-accent"></span></h3><div class="mc-kpis" id="si-gsc-kpis"></div>
            <div id="si-gsc-table"></div></div>
          <div class="panel"><h3>Bing Webmaster <span class="h-accent"></span></h3><div class="mc-kpis" id="si-bing-kpis"></div>
            <div id="si-bing-table"></div></div>
        </div>
        <div class="mc-grid">
          <div class="panel"><h3>Striking distance — quick wins (pos 5–15) <span class="h-accent"></span></h3><div id="si-striking"></div></div>
          <div class="panel"><h3>Keyword rankings vs competitors <span class="h-accent"></span></h3><div id="si-ranks"></div></div>
        </div>
        <div class="panel" style="margin-top:13px">
          <h3>Daily performance trends <span style="font-weight:400;color:var(--dim);font-size:11px;" id="si-trend-meta"></span> <span class="h-accent"></span></h3>
          <div class="sub" style="margin-bottom:6px">Daily GSC clicks &amp; impressions with Google algorithm-update markers and z-score anomaly flags.</div>
          <div id="si-trend" style="min-height:320px"></div>
        </div>
        <div class="panel" style="margin-top:13px">
          <h3>Local map-pack geo-grid
            <select id="si-geo-kw" class="mc-sel" style="margin-left:8px;font-size:11px;padding:4px 8px"></select>
            <span style="font-weight:400;color:var(--dim);font-size:11px;" id="si-geo-meta">— Share of Local Voice across a rank grid</span> <span class="h-accent"></span></h3>
          <div id="si-geogrid"></div>
        </div>
        <div class="panel" style="margin-top:13px">
          <h3>GSC metric correlation matrix <span class="h-accent"></span></h3>
          <div class="sub" style="margin-bottom:8px">How your GSC metrics relate across queries — diagonal = each metric's distribution, off-diagonal = scatter with Pearson r.</div>
          <div class="corr-legend" id="si-corr-legend"></div>
          <div id="si-corr"></div>
        </div>
      </div>`;
    $("si-client").onchange = e => window.mcSetClient(e.target.value);
    $("si-geo-kw").onchange = e => { MC.geoKw = e.target.value; if (MC.lastGeo) drawGeoMap(MC.lastGeo); };
  };
  function perfKpis(p) {
    const t = (p && p.totals) || {};
    return [["Clicks", t.clicks], ["Impressions", t.impressions], ["CTR", t.ctr == null ? "—" : (Math.round(t.ctr * 1000) / 10) + "%"], ["Avg pos", t.avg_position]]
      .map(([l, v]) => `<div class="kpi"><div class="k-label">${l}</div><div class="k-val">${fmt(v)}</div></div>`).join("");
  }
  function table(headers, rows) {
    if (!rows.length) return `<div class="mc-empty">No data.</div>`;
    return `<table class="mc-table"><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  }
  RENDER.si = function (d) {
    clientSelect("si-client", d.clients, d.client);
    const sp = d.search_performance || {};
    $("si-gsc-kpis").innerHTML = perfKpis(sp.gsc);
    $("si-bing-kpis").innerHTML = perfKpis(sp.bing);
    const gsc = (sp.gsc && sp.gsc.rows) || [];
    $("si-gsc-table").innerHTML = sp.gsc && !sp.gsc.has_data
      ? `<div class="mc-empty">${sp.gsc.connected ? "Connected — no rows yet." : "Not configured in sources.yaml."}</div>`
      : table(["Query", "Clicks", "Impr", "Pos"], gsc.slice(0, 8).map(r =>
        [esc(r.query), fmt(r.clicks), fmt(r.impressions), fmt(r.position)]));
    const bing = (sp.bing && sp.bing.rows) || [];
    $("si-bing-table").innerHTML = sp.bing && !sp.bing.has_data
      ? `<div class="mc-empty">${sp.bing.connected ? "Connected — no rows yet." : "Not configured."}</div>`
      : table(["Query", "Clicks", "Impr", "Pos"], bing.slice(0, 8).map(r =>
        [esc(r.query), fmt(r.clicks), fmt(r.impressions), fmt(r.avg_impression_position)]));
    $("si-striking").innerHTML = table(["Query", "Pos", "Impr", "Clicks"],
      (d.striking_distance || []).map(r => [esc(r.query),
        `<span class="pill warn">${fmt(r.position)}</span>`, fmt(r.impressions), fmt(r.clicks)]));
    const kr = d.keyword_rankings || { local_finder: [], organic_mobile: [] };
    const rk = arr => table(["Keyword", "You", "Rank", "Comp", "Features"], (arr || []).slice(0, 12).map(r =>
      [esc(r.keyword), r.present ? `<span class="pill ok">in</span>` : `<span class="pill bad">out</span>`,
       fmt(r.best_rank), fmt(r.best_competitor_rank), esc((r.features_held || []).join(", ") || "—")]));
    $("si-ranks").innerHTML = `<div class="sub-h">Local Finder</div>${rk(kr.local_finder)}
      <div class="sub-h">Organic Mobile</div>${rk(kr.organic_mobile)}`;
    renderDailyTrend(d.daily_trend);
    renderGeoGrid(d.geo_grid);
    renderCorrelation(d.gsc_correlation);
  };
  const geoRankColor = v => v == null ? "#9ca3af" : v <= 3 ? "#34d399" : v <= 7 ? "#38bdf8" : v <= 10 ? "#fbbf24" : "#f87171";
  function renderGeoGrid(g) {
    MC.lastGeo = g;
    const host = $("si-geogrid"), sel = $("si-geo-kw");
    if (!host) return;
    const kws = (g && g.keywords) || [];
    if (sel) {                                   // populate the per-keyword dropdown
      sel.style.display = kws.length ? "" : "none";
      const sig = kws.join("|");
      if (sel.dataset.sig !== sig) {
        sel.innerHTML = kws.map(k => `<option value="${esc(k)}">${esc(k)}</option>`).join("");
        sel.dataset.sig = sig;
      }
      if (!MC.geoKw || !kws.includes(MC.geoKw)) MC.geoKw = kws[0];
      if (MC.geoKw) sel.value = MC.geoKw;
    }
    drawGeoMap(g);
  }
  function drawGeoMap(g) {
    const host = $("si-geogrid"), meta = $("si-geo-meta");
    if (!host) return;
    const kws = (g && g.keywords) || [];
    const kw = (MC.geoKw && kws.includes(MC.geoKw)) ? MC.geoKw : kws[0];
    const grid = (g && g.grids && kw) ? g.grids[kw] : null;
    if (!g || !g.available || !grid || !((grid.points || []).length || (grid.matrix || []).length)) {
      if (MC.geomap) { try { MC.geomap.remove(); } catch (e) {} MC.geomap = null; }
      MC.geomapSig = null;
      host.innerHTML = `<div class="mc-empty">No geo-grid pull yet — run <code>automations/geo-grid --all</code>.</div>`;
      if (meta) meta.textContent = "— Share of Local Voice across a rank grid"; return;
    }
    const sig = (g.pulled || "") + "|" + kw;
    if (MC.geomapSig === sig && MC.geomap && document.getElementById("si-geomap")) return;  // no-op on poll
    if (MC.geomap) { try { MC.geomap.remove(); } catch (e) {} MC.geomap = null; }

    const s = grid.solv || {};
    const kpiHtml = `<div class="mc-kpis" style="grid-template-columns:repeat(4,1fr);margin-bottom:12px">${
      [["SoLV", s.solv != null ? Math.round(s.solv * 100) + "%" : "—"],
       ["Ranked points", `${s.points_ranked ?? "—"}/${s.points_total ?? "—"}`],
       ["Top-3 points", s.top3_points ?? "—"], ["Avg rank", s.avg_rank ?? "—"]]
        .map(([l, v]) => `<div class="kpi"><div class="k-label">${esc(l)}</div><div class="k-val">${esc(v)}</div></div>`).join("")}</div>`;
    const legend = `<div class="legend-row" style="margin-top:8px"><span><i style="background:#34d399"></i>1–3</span><span><i style="background:#38bdf8"></i>4–7</span><span><i style="background:#fbbf24"></i>8–10</span><span><i style="background:#f87171"></i>11+</span><span><i style="background:#9ca3af"></i>absent</span></div>`;
    const pts = (grid.points || []).filter(p => p.lat != null && p.lng != null);

    if (window.L && pts.length) {
      host.innerHTML = kpiHtml + `<div id="si-geomap" class="geo-map"></div>` + legend;
      const map = L.map("si-geomap", { scrollWheelZoom: false });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { maxZoom: 19, attribution: "&copy; OpenStreetMap" }).addTo(map);
      pts.forEach(p => {
        const v = p.rank_absolute;
        const icon = L.divIcon({ className: "geo-pin-wrap", iconSize: [34, 34], iconAnchor: [17, 17],
          html: `<div class="geo-pin" style="background:${geoRankColor(v)}">${v == null ? "·" : v}</div>` });
        L.marker([p.lat, p.lng], { icon }).addTo(map).bindTooltip(v == null ? "absent" : "rank " + v);
      });
      try { map.fitBounds(pts.map(p => [p.lat, p.lng]), { padding: [28, 28] }); } catch (e) {}
      MC.geomap = map; MC.geomapSig = sig;
      setTimeout(() => { try { map.invalidateSize(); } catch (e) {} }, 150);
    } else {
      const cells = (grid.matrix || []).map(row => `<div class="geo-row">` + row.map(v =>
        `<div class="geo-cell" style="background:${geoRankColor(v)}" title="rank ${v == null ? "absent" : v}">${v == null ? "·" : v}</div>`).join("") + `</div>`).join("");
      host.innerHTML = kpiHtml + `<div class="geo-grid-wrap">${cells}</div>` + legend;
      MC.geomapSig = null;
    }
    if (meta) meta.textContent = `— “${kw}” · ${grid.size}×${grid.size} grid · ${g.location || ""}`;
  }
  function renderDailyTrend(dt) {
    const el = $("si-trend"), meta = $("si-trend-meta");
    if (!el) return;
    if (!dt || !dt.available || !(dt.days || []).length) {
      el.innerHTML = `<div class="mc-empty">No daily GSC pull yet — run <code>automations/gsc-daily-trend</code> to populate this.</div>`;
      if (meta) meta.textContent = ""; return;
    }
    const days = dt.days;
    if (!HAS_APEX()) { el.innerHTML = `<div class="mc-empty">${days.length} days loaded.</div>`; return; }
    const cats = days.map(d => d.date);
    const updColor = t => t === "spam" ? "#a78bfa" : t === "discover" ? "#34d399" : "#f59e0b";
    const xann = (dt.markers || []).map(m => ({ x: m.date, borderColor: updColor(m.type), strokeDashArray: 4,
      label: { text: m.label, orientation: "horizontal", style: { color: "#fff", background: updColor(m.type), fontSize: "8px" } } }));
    const pann = (dt.anomalies || []).map(a => ({ x: a.date, y: a.clicks,
      marker: { size: 5, fillColor: a.direction === "drop" ? "#f87171" : "#34d399", strokeColor: "#fff" },
      label: { text: (a.direction === "drop" ? "▼" : "▲"), style: { fontSize: "9px", color: "#fff", background: a.direction === "drop" ? "#f87171" : "#34d399" } } }));
    const ch = new ApexCharts(el, {
      chart: { type: "line", height: 320, background: "transparent", toolbar: { show: false } },
      theme: { mode: "dark" },
      series: [{ name: "Clicks", type: "area", data: days.map(d => d.clicks || 0) },
               { name: "Impressions", type: "line", data: days.map(d => d.impressions || 0) }],
      colors: ["#38bdf8", "#34d399"], stroke: { width: [2, 1.5], curve: "smooth" },
      fill: { type: ["gradient", "solid"], gradient: { opacityFrom: 0.4, opacityTo: 0.05 } },
      dataLabels: { enabled: false },
      xaxis: { categories: cats, tickAmount: 14, labels: { style: { colors: "#7d8a9a", fontSize: "9px" }, rotate: -40, hideOverlappingLabels: true } },
      yaxis: [{ seriesName: "Clicks", title: { text: "Clicks", style: { color: "#7d8a9a" } }, labels: { style: { colors: "#7d8a9a" } } },
              { seriesName: "Impressions", opposite: true, title: { text: "Impressions", style: { color: "#7d8a9a" } }, labels: { style: { colors: "#7d8a9a" } } }],
      grid: { borderColor: "#222c39" }, legend: { labels: { colors: "#7d8a9a" } },
      annotations: { xaxis: xann, points: pann }, tooltip: { theme: "dark", shared: true }
    });
    ch.render(); MC.charts.si_trend = ch;
    if (meta) meta.textContent = `${days.length} days · ${dt.anomalies.length} anomalies · ${(dt.markers || []).length} algorithm updates`;
  }
  function _hist(vals, n) {
    if (!vals.length) return new Array(n).fill(0);
    const mn = Math.min(...vals), mx = Math.max(...vals), w = (mx - mn) / n || 1;
    const counts = new Array(n).fill(0);
    vals.forEach(v => { let i = Math.floor((v - mn) / w); if (i >= n) i = n - 1; if (i < 0) i = 0; counts[i]++; });
    return counts;
  }
  const rColor = r => r >= 0.7 ? "#34d399" : r >= 0.4 ? "#fbbf24" : r > -0.4 ? "#7d8a9a" : r > -0.7 ? "#fb923c" : "#f87171";
  function renderCorrelation(c) {
    const host = $("si-corr"); if (!host) return;
    if (!c || !(c.points || []).length) { host.innerHTML = `<div class="mc-empty">No GSC rows to correlate.</div>`; return; }
    const M = c.metrics, LABEL = { clicks: "Clicks", impressions: "Impressions", ctr: "CTR %", position: "Avg Position" }, n = M.length;
    $("si-corr-legend").innerHTML = [["#34d399", "Strong + (≥0.7)"], ["#fbbf24", "Medium + (0.4–0.7)"],
      ["#7d8a9a", "Weak (−0.4–0.4)"], ["#fb923c", "Medium − (−0.7–−0.4)"], ["#f87171", "Strong − (≤−0.7)"]]
      .map(([col, t]) => `<span><i style="background:${col}"></i>${t}</span>`).join("");
    let html = `<div class="corr-grid" style="grid-template-columns:84px repeat(${n},1fr)"><div class="corr-corner"></div>`;
    M.forEach(m => html += `<div class="corr-head">${esc(LABEL[m])}</div>`);
    M.forEach((ry, ri) => { html += `<div class="corr-head corr-rhead">${esc(LABEL[ry])}</div>`;
      M.forEach((cx, ci) => html += `<div class="corr-cell" id="corr-${ri}-${ci}"></div>`); });
    host.innerHTML = html + `</div>`;
    if (!HAS_APEX()) return;
    M.forEach((ry, ri) => M.forEach((cx, ci) => {
      const el = $(`corr-${ri}-${ci}`); if (!el) return;
      if (ri === ci) {
        const ch = new ApexCharts(el, { chart: { type: "bar", height: 116, sparkline: { enabled: true } },
          series: [{ data: _hist(c.points.map(p => p[ry]), 12) }], colors: ["#38bdf8"],
          plotOptions: { bar: { columnWidth: "88%" } }, tooltip: { enabled: false } });
        ch.render(); MC.charts[`corr_${ri}_${ci}`] = ch;
        const tag = document.createElement("div"); tag.className = "corr-r"; tag.style.color = "#7d8a9a"; tag.textContent = "dist"; el.appendChild(tag);
      } else {
        const r = ((c.r[ry] || {})[cx]) ?? 0;
        const ch = new ApexCharts(el, { chart: { type: "scatter", height: 116, sparkline: { enabled: true } },
          series: [{ name: `${LABEL[cx]} × ${LABEL[ry]}`, data: c.points.map(p => [p[cx], p[ry]]) }],
          colors: [rColor(r)], markers: { size: 2.4 }, xaxis: { type: "numeric" },
          tooltip: { enabled: false }, grid: { show: false } });
        ch.render(); MC.charts[`corr_${ri}_${ci}`] = ch;
        const tag = document.createElement("div"); tag.className = "corr-r"; tag.style.color = rColor(r); tag.textContent = "r " + r; el.appendChild(tag);
      }
    }));
  }

  /* ============================ AI SEARCH ============================ */
  SHELL.ai = function () {
    const host = $("view-ai"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title">AI Search — citations &amp; AI surfaces</span>
          <select id="ai-client" class="mc-sel"></select><span class="mc-spacer"></span>
          <span class="mc-chip">scored by CITATION, not rank</span></div>
        <div class="mc-hero">
          <div class="panel"><h3>AI citation share <span class="h-accent"></span></h3>
            <div class="mc-gaugewrap"><div id="ai-gauge" style="width:150px;height:150px"></div>
              <div class="mc-goal" style="flex:1"><div class="big" id="ai-big">—</div>
                <div class="sub">of tracked AI queries cite you (AI Overviews + AI Mode)</div></div></div></div>
          <div class="panel"><h3>Who's winning the AI surface <span class="h-accent"></span></h3>
            <div><div class="sub-h">Sources cited</div><div id="ai-src"></div></div></div>
        </div>
        <div class="panel" style="margin-top:13px"><h3>AI queries — uncited first (the action list) <span class="h-accent"></span></h3>
          <div id="ai-queries"></div></div>

        <div class="panel" style="margin-top:13px"><h3>Multi-engine AI visibility <span style="font-weight:400;color:var(--dim);font-size:11px;" id="aiv-meta">— are you recommended by ChatGPT / Claude / Google AI?</span> <span class="h-accent"></span></h3>
          <div id="aiv-engines" class="aiv-engines"></div>
          <div id="aiv-matrix" style="margin-top:10px"></div></div>

        <!-- Threat Intelligence Report Section -->
        <div class="panel" style="margin-top:16px; border-color:#38bdf833;">
          <h3 style="color:#38bdf8;"><i class="fas fa-shield-alt" style="margin-right:6px;"></i> Active Threat Intel: houseacrepair.com <span class="h-accent"></span></h3>
          <div class="mc-controls" style="margin: 10px 0 14px;">
            <span class="mc-chip ok" id="ti-trace">crawl: —</span>
            <span class="mc-chip" id="ti-geo">Fort Lauderdale, FL (Primary GEO)</span>
            <span class="mc-chip warn" id="ti-pressure">Competitor pressure: —</span>
          </div>

          <div class="mc-kpis" style="margin-bottom:14px; grid-template-columns: repeat(5, 1fr);">
            <div class="kpi"><div class="k-label">AI bots probed</div><div class="k-val" style="font-size:22px;" id="ti-bots">—</div></div>
            <div class="kpi"><div class="k-label">Bots allowed</div><div class="k-val" style="font-size:22px;" id="ti-allowed">—</div></div>
            <div class="kpi"><div class="k-label">Bots blocked</div><div class="k-val" style="font-size:22px; color:#fca5a5;" id="ti-blocked">—</div></div>
            <div class="kpi"><div class="k-label">Entities found</div><div class="k-val" style="font-size:22px;" id="ti-entities">—</div></div>
            <div class="kpi"><div class="k-label">Content size</div><div class="k-val" style="font-size:22px;" id="ti-size">—</div></div>
          </div>

          <div class="panel" style="padding:14px; margin-bottom:13px; background:var(--card);">
            <h4 class="sub-h" style="margin-top:0; color:#38bdf8; margin-bottom:12px;">Competitor pressure &amp; ranking threats <span style="font-weight:400; color:var(--dim); font-size:11px;">— live DataForSEO SERP slots across the tracked keywords</span></h4>
            <div id="ai-ti-pressure-table" style="margin-top:8px;"></div>
          </div>

          <div style="text-align: center; font-size: 10px; color: var(--dim); border-top: 1px solid var(--line); padding-top: 12px; margin-top: 14px;" id="ti-foot">
            Sourced from the live Firecrawl AEO crawl and the DataForSEO SERP tracker. Competitor review sentiment lives on the Threat Intelligence tab.
          </div>
        </div>
      </div>`;
    $("ai-client").onchange = e => window.mcSetClient(e.target.value);
  };
  function leaderboard(items) {
    if (!items || !items.length) return `<div class="mc-empty">none</div>`;
    const max = Math.max(...items.map(i => i.count));
    return items.map(i => `<div class="lb"><span class="lb-d">${esc(i.domain)}</span>
      <span class="lb-bar"><span style="width:${Math.round(i.count / max * 100)}%"></span></span><b>${i.count}</b></div>`).join("");
  }
  function renderAiVisibility(av) {
    const eng = $("aiv-engines"), mx = $("aiv-matrix"), meta = $("aiv-meta");
    if (!eng || !mx) return;
    if (!av || !av.available) {
      eng.innerHTML = `<div class="mc-empty">No AI-visibility probe yet — run <code>automations/ai-visibility</code>.</div>`;
      mx.innerHTML = ""; return;
    }
    const rate = v => v >= 0.5 ? "#34d399" : v >= 0.2 ? "#fbbf24" : "#f87171";
    eng.innerHTML = (av.engines || []).map(e => {
      const p = Math.round((e.rate || 0) * 100);
      return `<div class="aiv-eng"><div class="aiv-eng-top"><span>${esc(e.label)}</span><b style="color:${rate(e.rate)}">${p}%</b></div>
        <div class="hs-bar"><span style="width:${p}%;background:${rate(e.rate)}"></span></div>
        <div class="hs-c-detail">${e.mentions}/${e.asked} queries recommend you</div></div>`;
    }).join("");
    const keys = av.engine_keys || [];
    const labels = {}; (av.engines || []).forEach(e => labels[e.engine] = e.label);
    mx.innerHTML = table(["Query", ...keys.map(k => labels[k] || k)],
      (av.matrix || []).map(row => [esc(row.keyword), ...keys.map(k => {
        const c = row.cells[k];
        if (!c) return "—";
        return c.mentioned ? `<span class="pill ok" title="${esc(c.snippet || "")}">recommended</span>` : `<span class="pill bad">absent</span>`;
      })]));
    if (meta) meta.textContent = `— overall ${Math.round((av.overall_rate || 0) * 100)}% of AI answers recommend you`;
  }
  RENDER.ai = function (d) {
    clientSelect("ai-client", d.clients, d.client);
    const pct = Math.round((d.citation_share || 0) * 100);
    $("ai-big").innerHTML = `${fmt(d.n_cited)}<small>/${fmt(d.n_queries)} AI queries</small>`;
    $("ai-gauge").innerHTML = ""; gauge($("ai-gauge"), pct, "#a78bfa");
    $("ai-src").innerHTML = leaderboard(d.cited_sources_leaderboard);
    $("ai-queries").innerHTML = table(["Keyword", "Lane", "Cite you", "Sources"],
      (d.queries || []).map(q => [esc(q.keyword), esc(q.query_class),
        q.client_cited ? `<span class="pill ok">yes</span>` : `<span class="pill bad">no</span>`,
        esc((q.cited_sources || []).join(", ") || "—")]));
    renderAiVisibility(d.ai_visibility);

    // ---- Active Threat Intel: REAL data only (strip + pressure table + review sentiment) ----
    const ti = d.threat_intel || {};
    const ct = ti.crawl_telemetry || {};
    const tiSet = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    tiSet("ti-trace", "crawl: " + (ct.trace || "not run"));
    tiSet("ti-pressure", "Competitor pressure: " + (ct.competitor_pressure || "—"));
    tiSet("ti-bots", ct.bots_probed != null ? ct.bots_probed : "—");
    tiSet("ti-allowed", ct.bots_allowed != null ? ct.bots_allowed : "—");
    tiSet("ti-blocked", ct.bots_blocked != null ? ct.bots_blocked : "—");
    tiSet("ti-entities", (ct.entities_found != null ? ct.entities_found : "—") + (ct.entities_total != null ? "/" + ct.entities_total : ""));
    tiSet("ti-size", ct.content_kb != null ? ct.content_kb + " KB" : "—");

    // Ranking-threats table — live DataForSEO SERP slot counts per rival domain across tracked keywords
    const threats = ti.ranking_threats || [];
    const tlBadge = lv => lv === "apex" ? `<span class='pill bad'>🔥 apex</span>`
                        : lv === "high" ? `<span class='pill warn'>⚠️ high</span>`
                        : `<span class='pill'>med</span>`;
    const ptEl = $("ai-ti-pressure-table");
    if (ptEl) ptEl.innerHTML = threats.length
      ? table(["Rival domain", "SERP slots", "Keywords", "Avg rank", "Threat"],
          threats.map(t => [`<strong>${esc(t.domain)}</strong>`, String(t.slots),
                            String(t.keywords), t.avg_rank != null ? String(t.avg_rank) : "—",
                            tlBadge(t.threat_level)]))
      : `<div class="mc-empty">no rival domains in the tracked SERPs yet</div>`;
    // (Competitor review sentiment moved to the Threat Intelligence tab.)
  };

  /* ============================ REAL-TIME FEEDBACK ============================ */
  SHELL.ci = function () {
    const host = $("view-ci"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title" id="ci-title">Real-Time Feedback</span>
          <select id="ci-client" class="mc-sel"></select><span class="mc-spacer"></span>
          <span id="ci-source" class="mc-chip ok">reviews loaded</span>
          <span id="ci-demo" class="mc-chip warn">directional demo</span></div>
        <div class="mc-kpis" id="ci-kpis"></div>
        <div class="ci-chart-grid">
          <div class="panel"><h3>Review Velocity Share <span class="h-accent"></span></h3><div id="ci-share" class="ci-chart"></div></div>
          <div class="panel"><h3>Rough Revenue Range <span class="h-accent"></span></h3><div id="ci-revenue" class="ci-chart"></div></div>
          <div class="panel"><h3>Profile Strength <span class="h-accent"></span></h3><div id="ci-strength" class="ci-chart"></div></div>
        </div>
        <div class="mc-grid">
          <div class="panel"><h3>Competitor Market Read <span class="h-accent"></span></h3><div id="ci-table"></div></div>
          <div class="panel"><h3>Negative Review Issues Into Marketing <span class="h-accent"></span></h3><div class="sky" id="ci-angles"></div></div>
        </div>
        <div class="mc-grid">
          <div class="panel"><h3>Hiring &amp; Growth Signals <span class="h-accent"></span></h3><div id="ci-hiring"></div></div>
          <div class="panel"><h3>Revenue Assumptions <span class="h-accent"></span></h3><div id="ci-benchmarks"></div></div>
        </div>
      </div>`;
    $("ci-client").onchange = e => window.mcSetClient(e.target.value);
  };
  const compactNum = v => (v || 0).toLocaleString();
  const moneyM = v => "$" + Number(v || 0).toFixed(1) + "M";
  function ciFallbackChart(id, headers, rows) { $(id).innerHTML = table(headers, rows); }
  RENDER.ci = function (d) {
    clientSelect("ci-client", d.clients, d.client);
    $("ci-title").textContent = d.title || "Real-Time Feedback";
    const sample = d.sample || {}, summary = d.summary || {}, comps = d.competitors || [];
    $("ci-source").textContent = `${sample.source || "review export"} / ${sample.sampled_reviews || 0} rows`;
    $("ci-demo").textContent = d.demo_note || "directional demo";
    $("ci-kpis").innerHTML = [
      ["Competitors", summary.competitors],
      ["Profile reviews", compactNum(summary.profile_reviews)],
      ["365d review velocity", compactNum(summary.review_velocity_365)],
      ["Market leader", summary.market_leader || "n/a"],
    ].map(([l, v]) => `<div class="kpi"><div class="k-label">${esc(l)}</div><div class="k-val">${esc(v)}</div></div>`).join("");

    const names = comps.map(c => c.short_name);
    if (!HAS_APEX()) {
      ciFallbackChart("ci-share", ["Competitor", "Share"], comps.map(c => [esc(c.short_name), `${c.review_velocity_share}%`]));
      ciFallbackChart("ci-revenue", ["Competitor", "Low", "High"], comps.map(c => [esc(c.short_name), moneyM(c.revenue_low_m), moneyM(c.revenue_high_m)]));
      ciFallbackChart("ci-strength", ["Competitor", "Reviews", "Rating"], comps.map(c => [esc(c.short_name), compactNum(c.profile_reviews), c.rating]));
    } else {
      let ch = new ApexCharts($("ci-share"), {
        chart: { type: "donut", height: 248, background: "transparent" }, theme: { mode: "dark" },
        labels: names, series: comps.map(c => c.review_velocity_share),
        colors: ["#38bdf8", "#34d399", "#fbbf24"],
        legend: { position: "bottom", labels: { colors: "#7d8a9a" } },
        dataLabels: { style: { colors: ["#0d1117"] } },
        tooltip: { theme: "dark", y: { formatter: v => v + "%" } },
        stroke: { colors: ["#0d1117"] },
      });
      ch.render(); MC.charts.ci_share = ch;

      ch = new ApexCharts($("ci-revenue"), {
        chart: { type: "rangeBar", height: 248, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" }, series: [{ data: comps.map(c => ({ x: c.short_name, y: [c.revenue_low_m, c.revenue_high_m] })) }],
        colors: ["#a78bfa"], plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: "56%" } },
        xaxis: { labels: { style: { colors: "#7d8a9a" }, formatter: moneyM } },
        yaxis: { labels: { style: { colors: "#7d8a9a" } } },
        grid: { borderColor: "#222c39" },
        tooltip: { theme: "dark", y: { formatter: (v, opts) => {
          const c = comps[opts.dataPointIndex]; return `${moneyM(c.revenue_low_m)} - ${moneyM(c.revenue_high_m)}`;
        } } },
      });
      ch.render(); MC.charts.ci_revenue = ch;

      ch = new ApexCharts($("ci-strength"), {
        chart: { type: "bar", height: 248, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [{ name: "Profile reviews", data: comps.map(c => c.profile_reviews) },
                 { name: "365d velocity", data: comps.map(c => c.sample_reviews_365) }],
        colors: ["#1f6feb", "#f59e0b"], plotOptions: { bar: { borderRadius: 4, columnWidth: "52%" } },
        xaxis: { categories: names, labels: { style: { colors: "#7d8a9a" } } },
        yaxis: { labels: { style: { colors: "#7d8a9a" } } },
        legend: { labels: { colors: "#7d8a9a" } }, grid: { borderColor: "#222c39" },
        tooltip: { theme: "dark" },
      });
      ch.render(); MC.charts.ci_strength = ch;
    }

    $("ci-table").innerHTML = table(["Competitor", "Rating", "Reviews", "365d", "Share", "Jobs", "Revenue"],
      comps.map(c => [esc(c.short_name), c.rating, compactNum(c.profile_reviews),
        compactNum(c.sample_reviews_365), `${c.review_velocity_share}%`,
        `${compactNum(c.estimated_jobs_low)}-${compactNum(c.estimated_jobs_high)}`,
        `${moneyM(c.revenue_low_m)}-${moneyM(c.revenue_high_m)}`]));
    $("ci-angles").innerHTML = (d.issue_angles || []).map(a => `<div class="act ${esc(a.severity)}">
      <div class="a-top"><span class="a-title">${esc(a.issue)}</span><span class="a-metric">${esc(a.severity)}</span></div>
      <div class="a-detail">${esc(a.angle)}</div><div class="a-src">${esc(a.signal)}</div></div>`).join("");
    const h = d.hiring_signals || {};
    $("ci-hiring").innerHTML = `<div class="ci-state ${esc(h.status || "pending")}">
        <div class="ci-state-title">${esc(h.current_export || "Job signal pending")}</div>
        <div class="ci-tags">${(h.tracked_when_available || []).map(x => `<span class="pill warn">${esc(x)}</span>`).join("")}</div>
      </div>`;
    $("ci-benchmarks").innerHTML = `<div class="ci-benchmarks">${(d.benchmarks || []).map(b =>
      `<div class="ci-bench"><span>${esc(b.label)}</span><b>${esc(b.value)}</b></div>`).join("")}
      <div class="ci-method">${esc(summary.revenue_method || "")}</div></div>`;
  };

  /* ============================ THREAT INTELLIGENCE ============================ */
  SHELL.ti = function () {
    const host = $("view-ti"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title" id="ti-title">Threat Intelligence</span>
          <select id="ti-client" class="mc-sel"></select><span class="mc-spacer"></span>
          <span id="ti-source" class="mc-chip ok">live competitive data</span></div>
        <div class="mc-kpis" id="ti-kpis"></div>
        <div class="mc-hero">
          <div class="panel"><h3>AIO vs Map Pack divergence — who owns which channel <span class="h-accent"></span></h3>
            <div id="ti-divergence" style="height:300px;"></div>
            <div class="sub" style="margin-top:6px">Map dominance = share of local-pack/finder slots · AI dominance = share of AI-surface citations · live SERP tracker.</div></div>
          <div class="panel"><h3>Competitor review sentiment <span class="h-accent"></span></h3>
            <div id="ti-sentiment" style="height:300px;"></div>
            <div class="sub" style="margin-top:6px">Negative reviews mined per competitor (live review watchdog).</div></div>
        </div>
        <div class="panel" style="margin-top:13px"><h3>Ranking threats — rival domains by SERP slots <span class="h-accent"></span></h3>
          <div id="ti-threats"></div></div>
        <div class="mc-grid" style="margin-top:13px">
          <div class="panel"><h3>Negative-review marketing angles <span class="h-accent"></span></h3>
            <div id="ti-angles"></div></div>
          <div class="panel"><h3>HVAC benchmarks <span style="font-size:10px;color:var(--dim);font-weight:400;">(external)</span> <span class="h-accent"></span></h3>
            <div id="ti-benchmarks"></div></div>
        </div>
      </div>`;
    $("ti-client").onchange = e => window.mcSetClient(e.target.value);
  };

  RENDER.ti = function (d) {
    clientSelect("ti-client", d.clients, d.client);
    $("ti-title").textContent = d.title || "Threat Intelligence";
    const src = $("ti-source");
    if (src) { const live = (d.data_source || "").startsWith("live"); src.textContent = live ? "live competitive data" : "no live review data"; src.className = "mc-chip " + (live ? "ok" : ""); }

    const k = d.kpis || {};
    $("ti-kpis").innerHTML = [
      ["Rivals tracked", k.rivals_tracked],
      ["Negative reviews mined", k.negatives_mined],
      ["Reviews sampled", k.reviews_sampled],
      ["Apex threats", k.apex_threats],
    ].map(([l, v]) => `<div class="kpi"><div class="k-label">${esc(l)}</div><div class="k-val">${fmt(v)}</div></div>`).join("");

    // AIO vs Map divergence — REAL (from the live tracker)
    const comps = d.divergence_matrix || [];
    const dv = $("ti-divergence");
    if (HAS_APEX() && comps.length && dv) {
      const ch = new ApexCharts(dv, {
        chart: { type: "scatter", height: 300, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: comps.map(c => ({ name: c.name, data: [[c.map_dominance, c.ai_dominance]] })),
        colors: comps.map(c => c.is_client ? "#34d399" : "#f87171"),
        markers: { size: comps.map(c => c.is_client ? 9 : 6) },
        xaxis: { min: 0, max: 1, tickAmount: 5, title: { text: "Map pack dominance", style: { color: "#7d8a9a", fontSize: "11px" } }, labels: { style: { colors: "#7d8a9a" } } },
        yaxis: { min: 0, max: 1, tickAmount: 5, title: { text: "AI citation dominance", style: { color: "#7d8a9a", fontSize: "11px" } }, labels: { style: { colors: "#7d8a9a" } } },
        grid: { borderColor: "#222c39" },
        legend: { position: "bottom", labels: { colors: "#7d8a9a" } },
        annotations: { xaxis: [{ x: 0.5, borderColor: "#1f6feb", strokeDashArray: 3 }], yaxis: [{ y: 0.5, borderColor: "#1f6feb", strokeDashArray: 3 }] },
        tooltip: { theme: "dark", custom: ({ seriesIndex }) => { const c = comps[seriesIndex] || {}; return `<div style="padding:8px;background:#161d27;border:1px solid #222c39;"><b>${esc(c.name)}</b><br/>Map ${c.map_dominance} · AI ${c.ai_dominance}<br/><i>${esc(c.quadrant)}</i></div>`; } }
      });
      ch.render(); MC.charts.ti_divergence = ch;
    } else if (dv) dv.innerHTML = `<div class="mc-empty">No SERP tracker data yet.</div>`;

    // Competitor review sentiment — REAL (live watchdog)
    const rs = d.review_sentiment || [];
    const se = $("ti-sentiment");
    if (HAS_APEX() && rs.length && se) {
      const ch = new ApexCharts(se, {
        chart: { type: "bar", height: 300, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [{ name: "Negative reviews mined", data: rs.map(r => r.negatives || 0) }],
        xaxis: { categories: rs.map(r => r.competitor), labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } },
        yaxis: { labels: { style: { colors: "#7d8a9a" } } },
        colors: ["#f87171"], plotOptions: { bar: { borderRadius: 4, columnWidth: "45%" } },
        dataLabels: { enabled: true, style: { colors: ["#e6edf3"] } }, grid: { borderColor: "#222c39" }, legend: { show: false },
        tooltip: { theme: "dark", y: { formatter: (v, o) => { const r = rs[o.dataPointIndex] || {}; return v + " negative · avg " + (r.avg_rating != null ? r.avg_rating + "★" : "—") + (r.top_theme ? " · " + r.top_theme : ""); } } }
      });
      ch.render(); MC.charts.ti_sentiment = ch;
    } else if (se) se.innerHTML = `<div class="mc-empty">No review data yet.</div>`;

    // Ranking threats — REAL (live DataForSEO SERP slots)
    const threats = d.ranking_threats || [];
    const tlBadge = lv => lv === "apex" ? `<span class='pill bad'>🔥 apex</span>` : lv === "high" ? `<span class='pill warn'>⚠️ high</span>` : `<span class='pill'>med</span>`;
    $("ti-threats").innerHTML = threats.length
      ? table(["Rival domain", "SERP slots", "Keywords", "Avg rank", "Threat"],
          threats.map(t => [`<strong>${esc(t.domain)}</strong>`, String(t.slots), String(t.keywords), t.avg_rank != null ? String(t.avg_rank) : "—", tlBadge(t.threat_level)]))
      : `<div class="mc-empty">no rival domains in the tracked SERPs yet</div>`;

    // Negative-review marketing angles — REAL (watchdog themes)
    const angles = d.marketing_angles || [];
    $("ti-angles").innerHTML = angles.length ? angles.map(a => `
      <div class="act low">
        <div class="a-top"><span class="a-title">${esc(a.issue)}</span></div>
        <div class="a-detail" style="color:#fcd34d">${esc(a.angle)}</div>
        <div class="a-src">${esc(a.signal)}</div></div>`).join("")
      : `<div class="mc-empty">No mined review themes yet — run the review watchdog.</div>`;

    // HVAC benchmarks — external references
    const bm = d.benchmarks || [];
    $("ti-benchmarks").innerHTML = bm.map(b => `
      <div class="ci-bench" style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px;padding:10px;">
        <div style="display:flex;justify-content:space-between;width:100%;font-size:12.5px;"><span>${esc(b.label)}</span><b style="color:#cfe1ff">${esc(b.val)}</b></div>
        <span style="font-size:10px;color:var(--dim);font-family:'JetBrains Mono',monospace;">Source: <a href="${esc(b.url)}" target="_blank" style="color:#38bdf8;text-decoration:none;">${esc(b.src)}</a></span>
      </div>`).join("");
  };

  /* ============================ controller ============================ */
  async function refresh() {
    if (!MC.view) return;
    try { const d = await fetchView(MC.view); killCharts(); RENDER[MC.view](d); MC.last = d; } catch (e) { /* keep last view */ }
  }
  window.mcSetClient = function (id) { MC.client = id; refresh(); };
  window.mcShow = function (view) {            // 'mc' | 'si' | 'ai' | null (none)
    killCharts(); MC.view = view;
    if (!view) { if (MC.timer) { clearInterval(MC.timer); MC.timer = null; } return; }
    SHELL[view](); refresh();
    if (!MC.timer) MC.timer = setInterval(refresh, 20000);
  };
  // back-compat shim used by older app.js: mcActive(true) -> show command center
  window.mcActive = on => window.mcShow(on ? "mc" : null);
})();
