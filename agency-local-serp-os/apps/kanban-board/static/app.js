const SYS = {duoplus:["DUOPLUS","#38bdf8"],zernio:["ZERNIO","#a78bfa"],
             cloakbrowser:["CLOAK","#fbbf24"],approval:["DRAFT","#34d399"],
             wordpress:["WP","#21759b"],edge:["EDGE","#f38020"],podcast:["POD","#8b5cf6"]};
const esc = s => (s??"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let CATALOG = {};
let LAST = null, FILTER = "";

async function apiCall(path, body=null) {
  const headers = {"Content-Type":"application/json"};
  const token = localStorage.getItem("sb-token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  
  const opts = body ? {method:"POST", headers, body:JSON.stringify(body)} : {headers};
  const r = await fetch(path, opts);
  if (r.status === 401) {
    document.getElementById("auth-modal").classList.remove("mc-hide");
    return null;
  }
  return r.json();
}

function cardHTML(c){
  const [label,color] = SYS[c.system]||["?","#888"];
  const meta = [c.period, c.age+" old"].filter(Boolean).join(" · ");
  let acts = "";
  if(c.kind==="draft"){
    acts = `<div class="acts">
      <button class="btn ok" onclick="approve('${esc(c.client)}','${esc(c.area)}','${esc(c.scope)}','${esc(c.workflow)}','${esc(c.period)}')">Approve</button>
      <button class="btn bad" onclick="reject('${esc(c.client)}','${esc(c.area)}','${esc(c.scope)}','${esc(c.workflow)}','${esc(c.period)}')">Reject</button></div>`;
  } else if(c.kind==="wo"){
    acts = `<div class="acts"><select id="mv_${esc(c.filename)}">
      <option value="inbox">inbox</option><option value="working">working</option>
      <option value="done">done</option><option value="failed">failed</option></select>
      <button class="btn" onclick="move('${esc(c.automation)}','${esc(c.filename)}')">Move</button></div>`;
  } else if(c.kind==="approved" && c.workflow){
    acts = `<div class="acts"><button class="btn ok" onclick="publishApproved('${esc(c.client)}','${esc(c.area)}','${esc(c.workflow)}','${esc(c.scope)}','${esc(c.period)}')">Publish →</button></div>`;
  }
  return `<div class="card" style="--sys:${color}">
    <div class="card-top"><span class="tag">${label}${c.manual?" ·man":""}</span><span class="client">${esc(c.client)}</span></div>
    <div class="title">${esc(c.title)}</div><div class="sub">${esc(c.sub)}</div>
    ${c.preview?`<div class="preview">${esc(c.preview)}</div>`:""}
    ${c.reason?`<div class="reason">${esc(c.reason)}</div>`:""}
    <div class="meta">${esc(meta)}</div>${acts}</div>`;
}

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
    <section class="col" style="--accent:${col.accent}">
      <h2>${esc(col.name)}<span class="count">${col.cards.length}</span></h2>
      <div class="cards">${col.cards.length?col.cards.map(cardHTML).join(""):'<div class="empty">— clear —</div>'}</div>
    </section>`).join("");
  renderCalendar(s.calendar||[]);
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

// ---- order modal: Create content (run a creator) + Queue work order (publish) ----
const $ = id => document.getElementById(id);
let TASKS = [], MODE = "create";

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

// ---- top-level view switch: Command Center / Search Intelligence / AI Search / Kanban Board ----
function setView(v){
  const isBoard = v === "board";
  $("view-mc").classList.toggle("mc-hide", v !== "mc");
  $("view-si").classList.toggle("mc-hide", v !== "si");
  $("view-ai").classList.toggle("mc-hide", v !== "ai");
  $("view-ci").classList.toggle("mc-hide", v !== "ci");
  $("view-ti").classList.toggle("mc-hide", v !== "ti");
  $("view-board").classList.toggle("mc-hide", !isBoard);
  $("nav-mc").classList.toggle("active", v === "mc");
  $("nav-si").classList.toggle("active", v === "si");
  $("nav-ai").classList.toggle("active", v === "ai");
  $("nav-ci").classList.toggle("active", v === "ci");
  $("nav-ti").classList.toggle("active", v === "ti");
  $("nav-board").classList.toggle("active", isBoard);
  document.querySelectorAll(".board-only").forEach(el => el.classList.toggle("mc-hide", !isBoard));
  if(window.mcShow) window.mcShow(isBoard ? null : v);   // start/stop the active dashboard poll
  if(isBoard) refresh();                                  // board just became visible -> pull state now
}
$("nav-mc").onclick = () => setView("mc");
$("nav-si").onclick = () => setView("si");
$("nav-ai").onclick = () => setView("ai");
$("nav-ci").onclick = () => setView("ci");
$("nav-ti").onclick = () => setView("ti");
$("nav-board").onclick = () => setView("board");

setInterval(refresh, 3000);    // board poll (no-ops while the board view is hidden)
setView("mc");                 // Command Center is the main / default landing view
