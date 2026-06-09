// Main Kanban board: state poll, render, content calendar, order-creation modal.
let CATALOG = {};
let LAST = null, FILTER = "";
let TASKS = [], MODE = "create";

async function refresh(){
  if(document.getElementById("view-board").classList.contains("mc-hide")) return;  // skip while board hidden
  LAST = await apiCall("/api/state"); render();
}

function render(){
  const s = LAST; if(!s) return;
  const g = id => document.getElementById(id);
  g("gen").textContent = "updated "+new Date(s.generated).toLocaleTimeString();
  // client filter (rebuild options only when the client set changes)
  const sel = g("client-filter"), sig = (s.clients||[]).join("|");
  if(sel.dataset.sig !== sig){
    sel.innerHTML = '<option value="">All clients</option>' +
      (s.clients||[]).map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join("");
    sel.dataset.sig = sig;
  }
  sel.value = FILTER;
  const match = c => !FILTER || c.client===FILTER;
  const cols = s.columns.map(col=>({...col, cards:(col.cards||[]).filter(match)}));
  const need = (cols.find(c=>c.key==="approval")||{cards:[]}).cards.length;
  const b = g("banner"); b.className = "banner "+(need?"show":"ok show");
  b.textContent = need ? `${need} item(s) need your approval — they will not move until you sign off`
                       : (FILTER ? `nothing waiting on ${FILTER}` : "nothing waiting on you");
  g("board").innerHTML = cols.map(col=>`
    <section class="col" data-col="${esc(col.key)}" style="--accent:${col.accent}">
      <h2>${esc(col.name)}<span class="count">${col.cards.length}</span></h2>
      <div class="cards">${col.cards.length?col.cards.map(cardHTML).join(""):'<div class="empty">— clear —</div>'}</div>
    </section>`).join("");
  wireDrag();
  renderCalendar(s.calendar||[]);
}

function wireDrag(){
  document.querySelectorAll("#board .col .cards").forEach(list=>{
    if(list._sortable) return;                          // idempotent across 3s polls
    list._sortable = Sortable.create(list, {
      group: "board", animation: 150,
      draggable: ".card[data-kind='wo']",               // only work-orders move
      filter: ".acts, .acts *",                         // don't start a drag on the inline buttons/select
      preventOnFilter: false,
      ghostClass: "drag-ghost", onEnd: onDragEnd });
  });
}

async function onDragEnd(evt){
  const card = evt.item;
  if(card.dataset.kind !== "wo") return;
  const fromCol = evt.from.closest(".col").dataset.col;
  const toCol   = evt.to.closest(".col").dataset.col;
  if(!(toCol in COL_FOLDER)){ refresh(); return; }   // e.g. NEEDS APPROVAL — no folder, snap back (gate not bypassable)
  const automation = card.dataset.automation, filename = card.dataset.filename;
  if(fromCol !== toCol){
    const r = await apiCall("/api/move", {automation, filename, to: COL_FOLDER[toCol]});
    if(!r || !r.ok){ alert("Move failed: "+((r&&r.error)||"unknown")); }
    refresh(); return;
  }
  if(toCol === "queued"){                               // reorder persists order_index
    const order = [...evt.to.querySelectorAll(".card[data-kind='wo']")].map(el=>el.dataset.filename);
    const r = await apiCall("/api/reorder", {automation, order});
    if(!r || !r.ok){ alert("Reorder failed: "+((r&&r.error)||"unknown")); refresh(); }
  }
}

function renderCalendar(cal){
  const g = id => document.getElementById(id);
  const items = cal.filter(e=>!FILTER || e.client===FILTER);
  g("cal-sub").textContent = items.length ? `· ${items.length} scheduled` : "";
  if(!items.length){
    g("calendar").innerHTML = '<div class="empty">No scheduled content — generate a weekly batch with scripts/gen_gbp_posts.py</div>';
    return;
  }
  const byDate = {}; items.forEach(e=>{(byDate[e.date]=byDate[e.date]||[]).push(e);});
  const today = new Date().toISOString().slice(0,10);
  g("calendar").innerHTML = Object.keys(byDate).sort().map(d=>{
    const cls = d<today?"past":(d===today?"today":"future");
    return `<div class="cal-day ${cls}">
      <div class="cal-date">${esc(fmtDay(d))}${d===today?' <span class="cal-now">TODAY</span>':''}</div>
      ${byDate[d].map(e=>`<div class="cal-item st-${esc(e.status)}">
        <span class="cal-st">${esc(e.status)}</span> <b>${esc(e.client)}</b> · ${esc(e.title)}${e.cta?' <span class="cal-cta">+CTA</span>':''}
        ${e.preview?`<div class="cal-prev">${esc(e.preview)}…</div>`:''}</div>`).join("")}
    </div>`;
  }).join("");
}

function fmtDay(d){
  return new Date(d+"T00:00:00").toLocaleDateString(undefined,{weekday:"short",month:"short",day:"numeric"});
}

async function approve(client,area,scope,workflow,period){
  const edit = prompt("Approve "+workflow+" for "+scope+".\nEdit text (blank = keep draft as-is):", "");
  const body = {client,area,scope,workflow};
  if(period) body.period = period;        // honor the draft's declared period (e.g. GBP post date)
  if(edit) body.edit = edit;
  const r = await apiCall("/api/approve", body);
  alert(r.ok? `Approved (hash ${r.hash}…) — verify_approval-valid.` : "Error: "+r.error);
  refresh();
}
async function reject(client,area,scope,workflow,period){
  const reason = prompt("Reject "+workflow+" — reason:","") ?? "";
  const body = {client,area,scope,workflow,reason};
  if(period) body.period = period;
  const r = await apiCall("/api/reject", body);
  if(!r.ok) alert("Error: "+r.error); refresh();
}
async function move(automation,filename){
  const to = document.getElementById("mv_"+filename).value;
  if(!confirm(`Recovery move: ${filename} → ${to}? (logged as manual_override)`)) return;
  const r = await apiCall("/api/move", {automation,filename,to});
  if(!r.ok) alert("Error: "+r.error); refresh();
}

async function openModal(){
  [CATALOG, TASKS] = await Promise.all([apiCall("/api/catalog"), apiCall("/api/tasks")]);
  const clients = Object.keys(CATALOG).map(c=>`<option>${esc(c)}</option>`).join("");
  $("c-client").innerHTML = clients; $("m-client").innerHTML = clients;
  $("c-task").innerHTML = TASKS.map(t=>`<option value="${esc(t.id)}">${esc(t.label)}</option>`).join("");
  updateTaskUI(); fillWorkflows(); setMode("create");
  $("modal").classList.remove("hidden");
}
function setMode(m){
  MODE = m;
  $("pane-create").classList.toggle("hidden", m!=="create");
  $("pane-publish").classList.toggle("hidden", m!=="publish");
  $("tab-create").classList.toggle("active", m==="create");
  $("tab-publish").classList.toggle("active", m==="publish");
  $("m-go").textContent = m==="create" ? "Create draft" : "Queue work order";
}
function updateTaskUI(){
  const t = TASKS.find(x=>x.id===$("c-task").value) || {};
  $("c-input-label").textContent = t.input_label || "Topic";
  $("c-input-wrap").style.display = t.needs_input===false ? "none" : "block";
  $("c-slug-wrap").style.display  = t.needs_slug ? "block" : "none";
  $("c-target-wrap").classList.toggle("hidden", !t.needs_target);   // comments (target) + pinterest (link)
  $("c-target-label").textContent = t.url_label || "Target URL";
}
function fillWorkflows(){
  const c = $("m-client").value, e = CATALOG[c]||{workflows:[]};
  $("m-workflow").innerHTML = e.workflows.map((w,i)=>`<option value="${i}">${esc(w.id)} · ${esc(w.execution_method)}${w.approval_required?" · needs approval":""}</option>`).join("");
  fillTargets();
}
function fillTargets(){
  const c = $("m-client").value, e = CATALOG[c]||{}, w = (e.workflows||[])[$("m-workflow").value];
  const WEB = ["wordpress_api","cloudflare_edge","castopod_api"];
  let opts = [];
  if(w){
    if(w.execution_method==="google_business_api") opts = e.locations||[];
    else if(WEB.includes(w.execution_method)) opts = e.web_scopes||[];   // content slugs awaiting publish
    else opts = (e.profiles||{})[w.area]||[];
  }
  $("m-target").innerHTML = opts.map(o=>`<option>${esc(o)}</option>`).join("") || '<option value="">(none configured)</option>';
  $("m-note").textContent = w&&w.approval_required ? "This workflow is gated — it will sit in QUEUED until approved." : "";
}
async function createContent(){
  const body = {client:$("c-client").value, task:$("c-task").value,
                topic:$("c-input").value.trim(), slug:$("c-slug").value.trim(), target:$("c-target").value.trim()};
  const go = $("m-go"), old = go.textContent; go.disabled = true; go.textContent = "Generating…";
  try{
    const r = await apiCall("/api/create_content", body);
    alert(r.ok? `Drafted: ${r.task}\n${r.output||""}\n→ approve it in NEEDS APPROVAL` : "Error: "+(r.error||r.output||"failed"));
  } finally { go.disabled = false; go.textContent = old; }
  $("modal").classList.add("hidden"); refresh();
}
async function create(){
  const c = $("m-client").value, e = CATALOG[c]||{}, w = (e.workflows||[])[$("m-workflow").value];
  if(!w){ alert("No workflow selected"); return; }
  let params = {};
  try{ if($("m-params").value.trim()) params = JSON.parse($("m-params").value); }
  catch(err){ alert("Task params must be valid JSON"); return; }
  const r = await apiCall("/api/create", {client:c, workflow_id:w.id, target:$("m-target").value,
                                      period:$("m-period").value.trim()||null, task_params:params});
  alert(r.ok? `Created ${r.work_order_id}\n→ ${r.inbox}` : "Error: "+r.error);
  $("modal").classList.add("hidden"); refresh();
}
async function publishApproved(client,area,workflow,scope,period){
  if(!confirm(`Queue a publish work order for ${workflow} (${scope})?`)) return;
  const r = await apiCall("/api/create", {client, workflow_id:workflow, target:scope, period:period||null});
  alert(r.ok? `Queued ${r.work_order_id}\n→ ${r.inbox}` : "Error: "+r.error);
  refresh();
}

$("add").onclick = openModal;
$("m-cancel").onclick = ()=>$("modal").classList.add("hidden");
$("m-go").onclick = ()=> MODE==="create" ? createContent() : create();
$("tab-create").onclick = ()=>setMode("create");
$("tab-publish").onclick = ()=>setMode("publish");
$("c-task").onchange = updateTaskUI;
$("m-client").onchange = fillWorkflows;
$("m-workflow").onchange = fillTargets;
$("client-filter").onchange = e => { FILTER = e.target.value; render(); };  // filter board + calendar by client

setInterval(refresh, 3000);    // board poll (no-ops while the board view is hidden)
