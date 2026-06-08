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

  const ENDPOINT = { mc: "/api/mc/command_center", si: "/api/mc/search_intelligence", ai: "/api/mc/ai_search", aeo: "/api/mc/aeo", ci: "/api/mc/competition_intell", ti: "/api/mc/threat_intelligence" };
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
          <span id="mc-fresh" class="mc-chip">—</span><span id="mc-cost" class="mc-chip">—</span>
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
      </div>`;
    $("mc-client").onchange = e => window.mcSetClient(e.target.value);
  };
  RENDER.mc = function (d) {
    $("mc-title").textContent = d.title || "Command Center";
    clientSelect("mc-client", d.clients, d.client);
    const f = d.freshness || {}, fc = $("mc-fresh");
    fc.textContent = f.signals_date ? `signals ${f.signals_date} · ${f.signals_age_days ?? "?"}d` : "no signals yet";
    fc.className = "mc-chip " + (f.stale ? "warn" : "ok");
    const c = d.cost || {}, cc = $("mc-cost");
    cc.textContent = c.circuit_open ? "DataForSEO circuit OPEN" : `last run $${fmt(c.last_run_cost)}`;
    cc.className = "mc-chip " + (c.circuit_open ? "bad" : "");

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
      { l: "% meeting 4–6+", v: pct + "%", d: dl.pct_meeting_goal },
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
      </div>`;
    $("si-client").onchange = e => window.mcSetClient(e.target.value);
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
  };

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
            <div class="ai-cols"><div><div class="sub-h">Competitors cited</div><div id="ai-comp"></div></div>
              <div><div class="sub-h">Sources cited</div><div id="ai-src"></div></div></div></div>
        </div>
        <div class="panel" style="margin-top:13px"><h3>AI queries — uncited first (the action list) <span class="h-accent"></span></h3>
          <div id="ai-queries"></div></div>

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

          <div class="kpi" style="padding:14px; margin-bottom:8px;">
            <h4 class="sub-h" style="margin-top:0; color:#38bdf8;">Competitor review sentiment <span style="font-weight:400; color:var(--dim); font-size:11px;">— negative reviews mined per competitor (live watchdog)</span></h4>
            <div id="ai-ti-sentiment" style="height:260px; margin-top:10px;"></div>
          </div>

          <div style="text-align: center; font-size: 10px; color: var(--dim); border-top: 1px solid var(--line); padding-top: 12px; margin-top: 14px;" id="ti-foot">
            Sourced from the live Firecrawl AEO crawl, the DataForSEO SERP tracker, and the competitor-review watchdog. No synthetic figures.
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
  RENDER.ai = function (d) {
    clientSelect("ai-client", d.clients, d.client);
    const pct = Math.round((d.citation_share || 0) * 100);
    $("ai-big").innerHTML = `${fmt(d.n_cited)}<small>/${fmt(d.n_queries)} AI queries</small>`;
    $("ai-gauge").innerHTML = ""; gauge($("ai-gauge"), pct, "#a78bfa");
    $("ai-comp").innerHTML = leaderboard(d.cited_competitors_leaderboard);
    $("ai-src").innerHTML = leaderboard(d.cited_sources_leaderboard);
    $("ai-queries").innerHTML = table(["Keyword", "Lane", "Cite you", "Competitors cited", "Sources"],
      (d.queries || []).map(q => [esc(q.keyword), esc(q.query_class),
        q.client_cited ? `<span class="pill ok">yes</span>` : `<span class="pill bad">no</span>`,
        esc((q.cited_competitors || []).join(", ") || "—"), esc((q.cited_sources || []).join(", ") || "—")]));

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

    // Review-sentiment chart — negative reviews mined per competitor (live watchdog)
    const rs = ti.review_sentiment || [];
    const sentEl = $("ai-ti-sentiment");
    if (HAS_APEX() && rs.length && sentEl) {
      const ch = new ApexCharts(sentEl, {
        chart: { type: "bar", height: 260, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [{ name: "Negative reviews mined", data: rs.map(r => r.negatives || 0) }],
        xaxis: { categories: rs.map(r => r.competitor), labels: { style: { colors: "#7d8a9a", fontSize: "10px" } } },
        yaxis: { labels: { style: { colors: "#7d8a9a" } } },
        colors: ["#f87171"],
        plotOptions: { bar: { borderRadius: 4, columnWidth: "45%" } },
        dataLabels: { enabled: true, style: { colors: ["#e6edf3"] } },
        grid: { borderColor: "#222c39" },
        legend: { show: false },
        tooltip: { theme: "dark", y: { formatter: (v, opts) => { const r = rs[opts.dataPointIndex] || {}; return v + " negative · avg " + (r.avg_rating != null ? r.avg_rating + "★" : "—") + (r.top_theme ? " · " + r.top_theme : ""); } } }
      });
      ch.render(); MC.charts.ai_ti_sentiment = ch;
    } else if (sentEl) {
      sentEl.innerHTML = `<div class="mc-empty">no review data yet</div>`;
    }
  };

  /* ============================ AEO ============================ */
  SHELL.aeo = function () {
    const host = $("view-aeo"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title">AEO — Answer Engine Optimization</span>
          <select id="aeo-client" class="mc-sel"></select><span class="mc-spacer"></span>
          <span id="aeo-crawl" class="mc-chip">crawl: not run</span></div>
        <div class="mc-hero">
          <div class="panel"><h3>AEO win-rate vs competitors <span class="h-accent"></span></h3>
            <div class="mc-gaugewrap"><div id="aeo-gauge" style="width:150px;height:150px"></div>
              <div class="mc-goal" style="flex:1"><div class="big" id="aeo-big">—</div>
                <div class="sub" id="aeo-sub">explicit-entity coverage vs competitors</div>
                <div id="aeo-missing" class="legend-row"></div></div></div></div>
          <div class="panel"><h3>Crawlability — what AI bots retrieve <span class="h-accent"></span></h3>
            <div class="mc-kpis" id="aeo-crawlkpis"></div><div id="aeo-bots"></div></div>
        </div>
        <div class="panel" style="margin-top:13px">
          <h3>Citation &amp; aggregator conquest → Kanban <span class="h-accent"></span></h3>
          <div class="sky" id="aeo-queue"></div></div>
      </div>`;
    $("aeo-client").onchange = e => window.mcSetClient(e.target.value);
  };
  RENDER.aeo = function (d) {
    clientSelect("aeo-client", d.clients, d.client);
    const cr = $("aeo-crawl");
    cr.textContent = d.crawl_run ? `crawl ${(d.crawl_generated_at || "").slice(0, 10)}` : "crawl: not run";
    cr.className = "mc-chip " + (d.crawl_run ? "ok" : "");

    const ev = d.evaluation;
    if (ev && ev.win_rate !== null && ev.win_rate !== undefined) {
      const pct = Math.round(ev.win_rate * 100);
      $("aeo-big").innerHTML = `${pct}%<small> win-rate</small>`;
      $("aeo-sub").textContent = `you cover ${Math.round((ev.client_coverage || 0) * 100)}% of key entities · beat/tie ${ev.wins}/${Object.keys(ev.competitors || {}).length} competitors`;
      $("aeo-gauge").innerHTML = ""; gauge($("aeo-gauge"), pct, "#f59e0b");
      $("aeo-missing").innerHTML = (ev.missing_entities || []).length
        ? `<span style="color:var(--dim)">missing:</span> ` + ev.missing_entities.map(m => `<span class="pill bad">${esc(m)}</span>`).join(" ")
        : `<span class="pill ok">all key entities present</span>`;
    } else {
      $("aeo-big").textContent = "—";
      $("aeo-sub").textContent = "Run the crawl simulator to score entity coverage vs competitors.";
      $("aeo-gauge").innerHTML = ""; $("aeo-missing").innerHTML = "";
    }

    const c = d.crawlability;
    if (c) {
      const mp = c.markdown_purity || {}, ec = c.entity_clarity || {};
      $("aeo-crawlkpis").innerHTML = [
        ["Markdown purity", Math.round((mp.purity || 0) * 100) + "%"],
        ["Entity clarity", Math.round((ec.clarity || 0) * 100) + "%"],
        ["llms.txt", c.llms_txt_present ? "yes" : "no"],
      ].map(([l, v]) => `<div class="kpi"><div class="k-label">${l}</div><div class="k-val">${v}</div></div>`).join("");
      $("aeo-bots").innerHTML = table(["AI bot", "Access", "Robots-blocked"],
        (c.bots || []).map(b => [esc(b.bot),
          b.accessible ? `<span class="pill ok">ok</span>` : `<span class="pill bad">blocked</span>`,
          b.blocked_by_robots ? `<span class="pill warn">yes</span>` : "no"]));
    } else {
      $("aeo-crawlkpis").innerHTML = "";
      $("aeo-bots").innerHTML = `<div class="mc-empty">No crawl yet — run automations/ai-crawl-simulator.</div>`;
    }

    const q = d.conquest_queue || { citation: [], aggregator: [] };
    const items = [...(q.citation || []).map(x => ({ ...x, sev: "high" })),
                   ...(q.aggregator || []).map(x => ({ ...x, sev: "med" }))];
    $("aeo-queue").innerHTML = items.length ? items.map(a => `<div class="act ${a.sev}">
      <div class="a-top"><span class="a-title">${esc((a.gap || {}).keyword)}</span><span class="a-metric">${esc(a.subsystem)}</span></div>
      <div class="a-detail">${esc(a.suggested_action)}</div><div class="a-src">${esc(a.kind)}</div></div>`).join("")
      : `<div class="mc-empty">No AI-citation or aggregator gaps right now.</div>`;
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
          <span id="ti-source" class="mc-chip ok">Threat intelligence monitor active</span>
          <span id="ti-demo" class="mc-chip warn">directional threat-intel simulation</span></div>
        <div class="mc-kpis" id="ti-kpis"></div>
        <div class="ci-chart-grid">
          <div class="panel"><h3>AIO vs Map Divergence Matrix <span class="h-accent"></span></h3><div id="ti-divergence" class="ci-chart"></div></div>
          <div class="panel"><h3>Fake Review Assassin Risk <span class="h-accent"></span></h3><div id="ti-assassin" class="ci-chart"></div></div>
          <div class="panel"><h3>Local Grid Heatmap (5x5) <span class="h-accent"></span></h3><div id="ti-heatmap" class="ci-chart"></div></div>
        </div>
        <div class="mc-grid">
          <div class="panel"><h3>GBP Taxonomy Diff Timeline <span class="h-accent"></span></h3><div class="sky" id="ti-diffs"></div></div>
          <div class="panel"><h3>Offer Order Book <span class="h-accent"></span></h3><div id="ti-offers"></div></div>
        </div>
        <div class="mc-grid">
          <div class="panel"><h3>Competitor GBP Freshness <span class="h-accent"></span></h3><div id="ti-freshness"></div></div>
          <div class="panel"><h3>Rank Correlation &amp; Velocity <span class="h-accent"></span></h3><div id="ti-correlation"></div></div>
        </div>
        <div class="panel" style="margin-top:13px">
          <h3>Competitive Intel, Hiring Signals &amp; Benchmarks <span class="h-accent"></span></h3>
          <div id="ti-signals-notes"></div>
        </div>
      </div>`;
    $("ti-client").onchange = e => window.mcSetClient(e.target.value);
  };

  RENDER.ti = function (d) {
    clientSelect("ti-client", d.clients, d.client);
    $("ti-title").textContent = d.title || "Threat Intelligence";
    const comps = d.divergence_matrix.competitors || [];
    const timeline = d.gbp_timeline || [];
    const offers = d.offers || [];
    const review_integrity = d.review_integrity || { competitors: [], spikes: [] };
    const geo_grid = d.geo_grid || { client_rankings: [] };
    const review_correlation = d.review_correlation || [];
    const freshness = d.freshness || { competitor_freshness: [] };

    // KPIs row
    const alertCount = review_integrity.competitors.filter(c => c.status === "red").length;
    const gapCount = timeline.filter(t => t.gap).length;
    $("ti-kpis").innerHTML = [
      ["Competitors Monitored", comps.length - 1], // exclude client
      ["High-Value Gaps", gapCount],
      ["Integrity Alerts", alertCount],
      ["Scan Status", "Active / Weekly"]
    ].map(([l, v]) => `<div class="kpi"><div class="k-label">${esc(l)}</div><div class="k-val">${esc(v)}</div></div>`).join("");

    // DIVERGENCE CHART
    if (!HAS_APEX()) {
      ciFallbackChart("ti-divergence", ["Competitor", "Map Dom", "AI Dom"], comps.map(c => [esc(c.name), c.map_dominance, c.ai_dominance]));
    } else {
      const chDivergence = new ApexCharts($("ti-divergence"), {
        chart: { type: "scatter", height: 248, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: comps.map(c => ({
          name: c.name,
          data: [[c.map_dominance, c.ai_dominance]]
        })),
        colors: ["#fbbf24", "#38bdf8", "#f87171", "#34d399"],
        xaxis: { min: 0, max: 1.0, tickAmount: 4, labels: { style: { colors: "#7d8a9a" } }, title: { text: "Map Dominance", style: { color: "#7d8a9a", fontSize: "10px" } } },
        yaxis: { min: 0, max: 1.0, tickAmount: 4, labels: { style: { colors: "#7d8a9a" } }, title: { text: "AI Dominance", style: { color: "#7d8a9a", fontSize: "10px" } } },
        grid: { borderColor: "#222c39" },
        legend: { position: "bottom", labels: { colors: "#7d8a9a" } },
        annotations: {
          xaxis: [{ x: 0.5, borderColor: "#1f6feb", strokeDashArray: 3, label: { text: "Map Threshold", style: { color: "#7d8a9a", background: "#11171f" } } }],
          yaxis: [{ y: 0.5, borderColor: "#1f6feb", strokeDashArray: 3, label: { text: "AI Threshold", style: { color: "#7d8a9a", background: "#11171f" } } }]
        },
        tooltip: { theme: "dark", custom: function({ series, seriesIndex, dataPointIndex, w }) {
          const comp = comps[seriesIndex];
          return `<div style="padding: 8px; background: #161d27; border: 1px solid #222c39;">
            <b>${esc(comp.name)}</b><br/>
            Map Dominance: ${comp.map_dominance}<br/>
            AI Dominance: ${comp.ai_dominance}<br/>
            <i>${esc(comp.details)}</i>
          </div>`;
        }}
      });
      chDivergence.render();
      MC.charts.ti_divergence = chDivergence;
    }

    // FAKE REVIEW ASSASSIN
    if (!HAS_APEX()) {
      ciFallbackChart("ti-assassin", ["Competitor", "Integrity Score"], review_integrity.competitors.map(c => [esc(c.name), c.score]));
    } else {
      const chAssassin = new ApexCharts($("ti-assassin"), {
        chart: { type: "bar", height: 248, background: "transparent", toolbar: { show: false } },
        theme: { mode: "dark" },
        series: [{ name: "Integrity Score", data: review_integrity.competitors.map(c => c.score) }],
        colors: [function({ value }) {
          if (value < 30) return "#f87171";
          if (value < 65) return "#fbbf24";
          return "#34d399";
        }],
        plotOptions: { bar: { borderRadius: 4, columnWidth: "40%", distributed: true } },
        xaxis: { categories: review_integrity.competitors.map(c => c.name), labels: { style: { colors: "#7d8a9a" } } },
        yaxis: { min: 0, max: 100, labels: { style: { colors: "#7d8a9a" } } },
        grid: { borderColor: "#222c39" },
        legend: { show: false },
        tooltip: { theme: "dark", y: { formatter: (v, opts) => {
          const c = review_integrity.competitors[opts.dataPointIndex];
          return `${v} / 100 - ${esc(c.details)}`;
        }}}
      });
      chAssassin.render();
      MC.charts.ti_assassin = chAssassin;
    }

    // GEO-GRID OVERLAY (Local Falcon style)
    const gridData = geo_grid.client_rankings || [];
    let gridHtml = `<div style="position: relative; width: 100%; height: 248px; background-image: url('/map_bg.png'); background-size: cover; background-position: center; border-radius: 8px; border: 1px solid var(--line); overflow: hidden;">`;
    
    if (gridData.length) {
      gridData.forEach((row, rIdx) => {
        row.forEach((val, cIdx) => {
          // Center the 5x5 grid in the view (percentage positions: 12%, 31%, 50%, 69%, 88%)
          const xPct = 12 + cIdx * 19;
          const yPct = 12 + rIdx * 19;
          
          let bgColor = "#f87171"; // rank 11+ (red)
          if (val <= 3) bgColor = "#34d399";      // rank 1-3 (green)
          else if (val <= 7) bgColor = "#38bdf8"; // rank 4-7 (blue)
          else if (val <= 10) bgColor = "#fbbf24"; // rank 8-10 (yellow)
          
          gridHtml += `
            <div class="geo-dot" 
                 style="position: absolute; left: ${xPct}%; top: ${yPct}%; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: #0d1117; background: ${bgColor}; border: 2px solid rgba(255,255,255,0.7); transform: translate(-50%, -50%); cursor: pointer; transition: all 0.2s;"
                 title="Grid Point [${rIdx+1}, ${cIdx+1}]: Rank ${val}">
              ${val}
            </div>
          `;
        });
      });
    } else {
      gridHtml += `<div class="mc-empty" style="padding:20px;">No grid ranking data found.</div>`;
    }
    
    gridHtml += `
      <div style="position: absolute; bottom: 8px; right: 8px; padding: 4px 8px; background: rgba(13, 17, 23, 0.85); border-radius: 4px; border: 1px solid var(--line); font-size: 10px; font-family: 'JetBrains Mono', monospace; color: var(--dim);">
        Center: Fort Lauderdale, FL
      </div>
      <div style="position: absolute; bottom: 8px; left: 8px; display: flex; gap: 8px; padding: 4px 8px; background: rgba(13, 17, 23, 0.85); border-radius: 4px; border: 1px solid var(--line); font-size: 9px; font-family: 'JetBrains Mono', monospace;">
        <span><i style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#34d399; margin-right:3px; vertical-align:middle;"></i>1-3</span>
        <span><i style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#38bdf8; margin-right:3px; vertical-align:middle;"></i>4-7</span>
        <span><i style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#fbbf24; margin-right:3px; vertical-align:middle;"></i>8-10</span>
        <span><i style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#f87171; margin-right:3px; vertical-align:middle;"></i>11+</span>
      </div>
    </div>`;
    
    $("ti-heatmap").innerHTML = gridHtml;

    // TIMELINE DIFFS
    $("ti-diffs").innerHTML = timeline.length ? timeline.map(t => `
      <div class="act ${t.color === 'green' ? 'low' : (t.color === 'red' ? 'high' : 'flat')}">
        <div class="a-top">
          <span class="a-title"><b>${esc(t.competitor)}</b>: ${esc(t.type)} — “${esc(t.item)}”</span>
          <span class="pill ${t.color === 'green' ? 'ok' : (t.color === 'red' ? 'bad' : 'warn')}">${esc(t.badge)}</span>
        </div>
        <div class="a-detail">${esc(t.details)}</div>
        <div class="a-src">${esc(t.date)}</div>
      </div>
    `).join("") : `<div class="mc-empty">No competitor taxonomy updates found.</div>`;

    // OFFERS table
    $("ti-offers").innerHTML = table(
      ["Competitor", "Active Offer / Promo", "Price / Discount", "Detected Source", "Date"],
      offers.map(o => [esc(o.competitor), esc(o.offer), `<b>${esc(o.price)}</b>`, esc(o.source), esc(o.detected)])
    );

    // FRESHNESS table
    $("ti-freshness").innerHTML = table(
      ["Competitor", "GBP Post Recency", "Freshness Status"],
      freshness.competitor_freshness.map(f => [
        esc(f.competitor),
        `${f.last_post_days} days ago`,
        f.status === "fresh" ? `<span class="pill ok">fresh</span>` : (f.status === "stale" ? `<span class="pill warn">stale</span>` : `<span class="pill bad">critical</span>`)
      ])
    );

    // CORRELATION table
    $("ti-correlation").innerHTML = table(
      ["Competitor", "Rank/Velocity Correlation", "365d reviews", "Avg Rank Change"],
      review_correlation.map(c => [
        esc(c.competitor),
        `<b>${c.correlation}</b>`,
        esc(c.velocity_365),
        `<span style="color:${c.avg_rank_change.startsWith('+') ? '#86efac' : '#fca5a5'}">${esc(c.avg_rank_change)}</span>`
      ])
    );

    const notes = d.hiring_intel_notes || {};
    const anglesHtml = (notes.marketing_angles || []).map(a => `
      <div style="margin-bottom: 12px; border-bottom: 1px solid var(--line); padding-bottom: 8px;">
        <span style="font-family:'JetBrains Mono',monospace; font-size:10px; color:var(--dim); text-transform:uppercase;">Theme: ${esc(a.issue)}</span><br/>
        <span style="font-size:12px; color:#fcd34d; font-weight:600; display:inline-block; margin-top:2px;">Marketing Angle: ${esc(a.angle)}</span>
      </div>
    `).join("");

    const benchmarksHtml = (notes.benchmarks || []).map(b => `
      <div class="ci-bench" style="display:flex; flex-direction:column; gap:4px; align-items:flex-start; margin-bottom:10px; padding:10px;">
        <div style="display:flex; justify-content:space-between; width:100%; font-size:12.5px;">
          <span>${esc(b.label)}</span>
          <b style="color:#cfe1ff">${esc(b.val)}</b>
        </div>
        <span style="font-size:10px; color:var(--dim); font-family:'JetBrains Mono',monospace; margin-top:2px;">Source: <a href="${esc(b.url)}" target="_blank" style="color:#38bdf8; text-decoration:none;">${esc(b.src)}</a></span>
      </div>
    `).join("");

    const hiringHtml = `
      <div class="ci-state bad" style="border-left-color:#f87171; background:rgba(248,113,113,.04); padding:14px; border-radius:10px; height:100%;">
        <div class="ci-state-title" style="color:#fca5a5; font-weight:700; font-family:'JetBrains Mono',monospace; font-size:11.5px; text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px;">Indeed / Hiring Signals Export Matcher</div>
        <div style="font-size:12px; margin-bottom:12px; color:var(--ink); line-height:1.4;">${esc(notes.indeed_status)}</div>
        <div style="font-size:10.5px; font-weight:700; text-transform:uppercase; color:var(--dim); font-family:'JetBrains Mono',monospace; margin-bottom:8px; letter-spacing:.05em;">Signals Scrape Scope:</div>
        <div style="display:flex; flex-wrap:wrap; gap:6px;">
          ${(notes.pending_signals || []).map(tag => `<span class="pill warn" style="border-color:#fbbf2444; color:#fcd34d; background:rgba(251,191,36,.06); font-size:10px; padding:2px 8px;">${esc(tag)}</span>`).join("")}
        </div>
      </div>
    `;

    $("ti-signals-notes").innerHTML = `
      <div style="display:grid; grid-template-columns: 1.2fr 1.2fr 1fr; gap:14px; margin-top:8px;">
        <div class="panel" style="background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin:0;">
          <h4 style="font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase; color:var(--dim); margin-bottom:12px; letter-spacing:.04em; border-bottom:1px solid var(--line); padding-bottom:6px;">Negative Review marketing angles</h4>
          <div>${anglesHtml}</div>
        </div>
        <div class="panel" style="background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; margin:0;">
          <h4 style="font-family:'JetBrains Mono',monospace; font-size:11px; text-transform:uppercase; color:var(--dim); margin-bottom:12px; letter-spacing:.04em; border-bottom:1px solid var(--line); padding-bottom:6px;">HVAC benchmarks &amp; tickets</h4>
          <div class="ci-benchmarks">${benchmarksHtml}</div>
        </div>
        <div style="margin:0;">
          ${hiringHtml}
        </div>
      </div>
    `;
  };

  /* ============================ DEEP DIVE SIMULATOR ============================ */
  SHELL.dd = function () {
    const host = $("view-dd"); if (host.dataset.built) return; host.dataset.built = "1";
    host.innerHTML = `
      <div class="mc-wrap">
        <div class="mc-controls"><span class="mc-title">Interactive Deep Dive: "God Mode" Simulators</span></div>
        <div class="ci-chart-grid" style="grid-template-columns: 1fr;">
          
          <!-- Proximity Decay Curve -->
          <div class="panel">
            <h3>Local Map Pack Proximity Decay Curve <span class="h-accent"></span></h3>
            <div style="display:flex; gap: 2rem; margin-top: 1rem;">
              <div style="flex:1;">
                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Asset Optimization Level (0-100)</label>
                <input type="range" id="dd-opt" min="0" max="100" value="85" style="width:100%;">
                <div style="display:flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 1.5rem;">
                  <span>Basic (0)</span><span id="dd-opt-val">85</span><span>Hyper-optimized (100)</span>
                </div>

                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Competitor Density</label>
                <select id="dd-comp" class="mc-sel" style="width:100%; margin-bottom: 1.5rem;">
                  <option value="1">Low Density (Rural/Suburbs)</option>
                  <option value="3" selected>Medium Density (City limits)</option>
                  <option value="5">High Density (Downtown Core)</option>
                </select>

                <div class="mc-chip warn" style="margin-top: 2rem;">
                  Proximity Math: SoV = Opt Level / (Distance ^ (Competitor Density * 0.5))
                </div>
              </div>
              <div style="flex:2;">
                <div id="dd-chart" class="ci-chart" style="height: 350px;"></div>
              </div>
            </div>
          </div>

          <!-- Pipeline Revenue Calculator -->
          <div class="panel">
            <h3>Pipeline Revenue Calculator <span class="h-accent"></span></h3>
            <div style="display:flex; gap: 2rem; margin-top: 1rem;">
              <div style="flex:1;">
                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Target Search Volume (Monthly)</label>
                <input type="number" id="dd-rev-sv" value="5000" class="mc-sel" style="width:100%; margin-bottom: 1.5rem;">

                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Average Lead Value ($)</label>
                <input type="number" id="dd-rev-val" value="500" class="mc-sel" style="width:100%; margin-bottom: 1.5rem;">

                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Current Share of Voice (%)</label>
                <input type="range" id="dd-rev-csov" min="0" max="100" value="15" style="width:100%;">
                <div style="display:flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 1.5rem;">
                  <span>0%</span><span id="dd-rev-csov-val">15%</span><span>100%</span>
                </div>

                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Target Share of Voice (%)</label>
                <input type="range" id="dd-rev-tsov" min="0" max="100" value="45" style="width:100%;">
                <div style="display:flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 1.5rem;">
                  <span>0%</span><span id="dd-rev-tsov-val">45%</span><span>100%</span>
                </div>
              </div>
              <div style="flex:2;">
                <div id="dd-rev-chart" class="ci-chart" style="height: 300px;"></div>
                <div id="dd-rev-delta" style="text-align:center; font-size: 1.5rem; font-weight: 700; color: #10b981; margin-top: 1rem;"></div>
              </div>
            </div>
          </div>

          <!-- Reputation Shock Simulator -->
          <div class="panel">
            <h3>Reputation Shock Simulator <span class="h-accent"></span></h3>
            <div style="display:flex; gap: 2rem; margin-top: 1rem;">
              <div style="flex:1;">
                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Current Star Rating</label>
                <input type="range" id="dd-rep-curr" min="30" max="50" value="48" style="width:100%;">
                <div style="display:flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 1.5rem;">
                  <span>3.0</span><span id="dd-rep-curr-val">4.8</span><span>5.0</span>
                </div>

                <label style="display:block; margin-bottom: 0.5rem; font-weight: 600;">Projected Star Rating (Post-Attack)</label>
                <input type="range" id="dd-rep-proj" min="30" max="50" value="41" style="width:100%;">
                <div style="display:flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 1.5rem;">
                  <span>3.0</span><span id="dd-rep-proj-val">4.1</span><span>5.0</span>
                </div>

                <div class="mc-chip alert" style="margin-top: 2rem;">
                  Reputation Math: Map Pack CTR drops exponentially below 4.5 stars.
                </div>
              </div>
              <div style="flex:2;">
                <div id="dd-rep-chart" class="ci-chart" style="height: 350px;"></div>
              </div>
            </div>
          </div>

        </div>
      </div>
    `;

    // Render interactive charts
    if (HAS_APEX) {
      
      // 1. Proximity Curve
      const renderCurve = () => {
        const opt = parseInt($("dd-opt").value);
        $("dd-opt-val").innerText = opt;
        const comp = parseFloat($("dd-comp").value);
        
        let dataPoints = [];
        let categories = [];
        for (let d = 1; d <= 25; d++) {
          let sov = (opt / Math.pow(d, comp * 0.4)).toFixed(1);
          sov = Math.min(100, Math.max(0, sov)); // Cap 0-100
          dataPoints.push(sov);
          categories.push(d + "m");
        }

        if (window.ddChartInstance) {
          window.ddChartInstance.updateSeries([{ data: dataPoints }]);
        } else {
          const opts = Object.assign({}, baseChartOpts, {
            chart: { type: 'area', height: 350, toolbar: { show: false }, background: 'transparent' },
            colors: ['#8b5cf6'],
            stroke: { curve: 'smooth', width: 2 },
            fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.7, opacityTo: 0.1, stops: [0, 100] } },
            series: [{ name: 'Share of Voice (%)', data: dataPoints }],
            xaxis: { categories: categories, title: { text: 'Distance from Centroid (Miles)', style: { color: '#64748b' } } },
            yaxis: { max: 100, title: { text: 'Share of Voice (%)', style: { color: '#64748b' } } }
          });
          window.ddChartInstance = new ApexCharts($("dd-chart"), opts);
          window.ddChartInstance.render();
        }
      };

      // 2. Revenue Calculator
      const renderRev = () => {
        const sv = parseInt($("dd-rev-sv").value) || 0;
        const val = parseInt($("dd-rev-val").value) || 0;
        const csov = parseInt($("dd-rev-csov").value);
        const tsov = parseInt($("dd-rev-tsov").value);
        
        $("dd-rev-csov-val").innerText = csov + "%";
        $("dd-rev-tsov-val").innerText = tsov + "%";

        const currRev = (sv * (csov/100) * 0.10 * val).toFixed(0); // assume 10% conversion of captured clicks
        const tarRev = (sv * (tsov/100) * 0.10 * val).toFixed(0);
        const delta = tarRev - currRev;

        $("dd-rev-delta").innerText = delta >= 0 ? `Projected Gain: +$${Number(delta).toLocaleString()}/mo` : `Projected Loss: -$${Math.abs(delta).toLocaleString()}/mo`;
        $("dd-rev-delta").style.color = delta >= 0 ? '#10b981' : '#ef4444';

        if (window.ddRevChartInstance) {
          window.ddRevChartInstance.updateSeries([{ data: [currRev, tarRev] }]);
        } else {
          const opts = Object.assign({}, baseChartOpts, {
            chart: { type: 'bar', height: 300, toolbar: { show: false }, background: 'transparent' },
            colors: ['#38bdf8', '#10b981'],
            plotOptions: { bar: { borderRadius: 4, distributed: true, horizontal: false } },
            series: [{ name: 'Pipeline ($)', data: [currRev, tarRev] }],
            xaxis: { categories: ['Current Pipeline', 'Target Pipeline'], labels: { style: { colors: '#fff' } } },
            yaxis: { title: { text: 'Monthly Revenue ($)', style: { color: '#64748b' } } }
          });
          window.ddRevChartInstance = new ApexCharts($("dd-rev-chart"), opts);
          window.ddRevChartInstance.render();
        }
      };

      // 3. Reputation Shock
      const renderRep = () => {
        const curr = parseInt($("dd-rep-curr").value) / 10;
        const proj = parseInt($("dd-rep-proj").value) / 10;
        
        $("dd-rep-curr-val").innerText = curr.toFixed(1);
        $("dd-rep-proj-val").innerText = proj.toFixed(1);

        let dataPoints = [];
        let categories = [];
        // Simulate rating drop from 5.0 to 3.0
        for (let r = 50; r >= 30; r--) {
          let rating = r / 10;
          let ctr = 100;
          if (rating < 4.5) ctr = ctr * Math.pow(0.7, (4.5 - rating)*10); // exponential decay below 4.5
          dataPoints.push(ctr.toFixed(1));
          categories.push(rating.toFixed(1));
        }

        // Add annotations for curr and proj
        const annotations = {
          xaxis: [
            { x: curr.toFixed(1), borderColor: '#38bdf8', label: { style: { color: '#fff', background: '#38bdf8' }, text: 'Current' } },
            { x: proj.toFixed(1), borderColor: '#ef4444', label: { style: { color: '#fff', background: '#ef4444' }, text: 'Projected' } }
          ]
        };

        if (window.ddRepChartInstance) {
          window.ddRepChartInstance.updateOptions({ annotations: annotations });
          window.ddRepChartInstance.updateSeries([{ data: dataPoints }]);
        } else {
          const opts = Object.assign({}, baseChartOpts, {
            chart: { type: 'area', height: 350, toolbar: { show: false }, background: 'transparent' },
            colors: ['#fbbf24'],
            stroke: { curve: 'stepline', width: 2 },
            fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.7, opacityTo: 0.1, stops: [0, 100] } },
            series: [{ name: 'Relative CTR (%)', data: dataPoints }],
            xaxis: { categories: categories, title: { text: 'Star Rating', style: { color: '#64748b' } } },
            yaxis: { max: 100, title: { text: 'Relative CTR (%)', style: { color: '#64748b' } } },
            annotations: annotations
          });
          window.ddRepChartInstance = new ApexCharts($("dd-rep-chart"), opts);
          window.ddRepChartInstance.render();
        }
      };

      $("dd-opt").addEventListener("input", renderCurve);
      $("dd-comp").addEventListener("change", renderCurve);
      $("dd-rev-sv").addEventListener("input", renderRev);
      $("dd-rev-val").addEventListener("input", renderRev);
      $("dd-rev-csov").addEventListener("input", renderRev);
      $("dd-rev-tsov").addEventListener("input", renderRev);
      $("dd-rep-curr").addEventListener("input", renderRep);
      $("dd-rep-proj").addEventListener("input", renderRep);
      
      setTimeout(() => { renderCurve(); renderRev(); renderRep(); }, 100);
    }
  };

  RENDER.dd = function(d) {
    // DD simulator is purely client-side interactive, no data binding required
  };

  /* ============================ controller ============================ */
  async function refresh() {
    if (!MC.view) return;
    try { const d = await fetchView(MC.view); killCharts(); RENDER[MC.view](d); } catch (e) { /* keep last view */ }
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
