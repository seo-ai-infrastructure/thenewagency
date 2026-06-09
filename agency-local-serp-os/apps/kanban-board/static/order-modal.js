// Rich order-editor modal: WO JSON / history / logs / attachments, plus inline draft review.
let WO_CTX = null;   // {automation, filename}
let DRAFT_CTX = null;

async function openWO(automation, filename){
  WO_CTX = {automation, filename};
  const token = localStorage.getItem("sb-token");
  const d = await fetch(`/api/wo?automation=${encodeURIComponent(automation)}&filename=${encodeURIComponent(filename)}`,
    {headers: token ? {Authorization:`Bearer ${token}`} : {}}).then(r=>r.json());
  if(d.error){ alert("Open failed: "+d.error); return; }
  $("wo-title").textContent = (d.wo.work_order_id||filename) + "  ·  " + d.folder;
  $("wo-json").value = JSON.stringify(d.wo, null, 2);
  const ro = !d.editable;
  $("wo-json").readOnly = ro;
  $("wo-save").disabled = ro;
  $("wo-ro-note").classList.toggle("hidden", !ro);
  renderHistory(d.history||[]);
  $("wo-logs").textContent = d.logs || "— no log records —";
  renderAtts(d.attachments||[]);
  woTab("overview");
  $("wo-modal").classList.remove("hidden");
}

function woTab(name){
  ["overview","history","logs","attach"].forEach(t=>
    $("wo-pane-"+t).classList.toggle("hidden", t!==name));
  document.querySelectorAll(".wo-tab").forEach(b=>b.classList.toggle("active", b.dataset.tab===name));
}
function renderHistory(h){
  $("wo-pane-history").innerHTML = h.length ? h.map(r=>`<div class="hist-row">
      <span class="hist-st st-${esc(r.status||'')}">${esc(r.status||'?')}</span>
      <span class="hist-ts">${esc(r.ts||'')}</span>
      ${r.reason?`<div class="hist-reason">${esc(r.reason)}</div>`:""}</div>`).join("")
    : '<div class="empty">— no history yet —</div>';
}
function renderAtts(atts){
  $("wo-atts").innerHTML = atts.length ? atts.map(a=>`<div class="att-row">
      <a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.label||a.url)}</a></div>`).join("")
    : '<div class="empty">— no attachments —</div>';
}

async function saveWO(){
  let wo;
  try { wo = JSON.parse($("wo-json").value); }
  catch(e){ alert("Invalid JSON: "+e.message); return; }
  const r = await apiCall("/api/wo/save", {...WO_CTX, wo});
  if(!r || !r.ok){ alert("Save failed: "+((r&&r.error)||"unknown")); return; }
  alert("Saved → "+r.file); refresh();
}
async function addAtt(){
  const label = $("wo-att-label").value.trim();
  const url   = $("wo-att-url").value.trim();
  if(!url){ alert("URL required"); return; }
  const r = await apiCall("/api/wo/attach", {...WO_CTX, label, url});
  if(!r || !r.ok){ alert("Attach failed: "+((r&&r.error)||"unknown")); return; }
  $("wo-att-label").value=""; $("wo-att-url").value="";
  renderAtts(r.attachments);
}

// ---- inline draft review (replaces the old prompt()/alert() approve/reject) ----
function openDraft(client, area, scope, workflow, period){
  DRAFT_CTX = {client, area, scope, workflow, period};
  $("draft-edit").value = "";
  $("draft-reason").value = "";
  $("draft-modal").classList.remove("hidden");
}
async function approveDraft(){
  const c = DRAFT_CTX, body = {client:c.client, area:c.area, scope:c.scope, workflow:c.workflow};
  if(c.period) body.period = c.period;
  const edit = $("draft-edit").value; if(edit) body.edit = edit;
  const r = await apiCall("/api/approve", body);
  alert(r && r.ok ? `Approved (hash ${r.hash}…)` : "Error: "+((r&&r.error)||"failed"));
  $("draft-modal").classList.add("hidden"); refresh();
}
async function rejectDraft(){
  const c = DRAFT_CTX, body = {client:c.client, area:c.area, scope:c.scope, workflow:c.workflow,
                               reason: $("draft-reason").value || ""};
  if(c.period) body.period = c.period;
  const r = await apiCall("/api/reject", body);
  if(!r || !r.ok) alert("Error: "+((r&&r.error)||"failed"));
  $("draft-modal").classList.add("hidden"); refresh();
}

$("wo-close").onclick = ()=>$("wo-modal").classList.add("hidden");
$("wo-save").onclick  = saveWO;
$("wo-att-add").onclick = addAtt;
document.querySelectorAll(".wo-tab").forEach(b=>b.onclick=()=>woTab(b.dataset.tab));
$("draft-close").onclick  = ()=>$("draft-modal").classList.add("hidden");
$("draft-approve").onclick = approveDraft;
$("draft-reject").onclick  = rejectDraft;
