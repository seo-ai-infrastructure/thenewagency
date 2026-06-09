// Shared helpers for the board + fractional views.
const SYS = {duoplus:["DUOPLUS","#38bdf8"],zernio:["ZERNIO","#a78bfa"],
             cloakbrowser:["CLOAK","#fbbf24"],approval:["DRAFT","#34d399"],
             wordpress:["WP","#21759b"],edge:["EDGE","#f38020"],podcast:["POD","#8b5cf6"]};
const COL_FOLDER = {queued:"inbox", progress:"working", done:"done", held:"failed"};
const esc = s => (s??"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const initials = s => (s||"?").split(/[-_ .]/).filter(Boolean).slice(0,2).map(w=>w[0].toUpperCase()).join("") || "?";
const $ = id => document.getElementById(id);

async function apiCall(path, body=null) {
  const headers = {"Content-Type":"application/json"};
  const token = localStorage.getItem("sb-token");
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const opts = body ? {method:"POST", headers, body:JSON.stringify(body)} : {headers};
  const r = await fetch(path, opts);
  if (r.status === 401) { document.getElementById("auth-modal").classList.remove("mc-hide"); return null; }
  return r.json();
}

function cardHTML(c){
  const [label,color] = SYS[c.system]||["?","#888"];
  const meta = [c.period, c.age && c.age+" old"].filter(Boolean).join(" · ");
  const chip = c.profile_id ? `<span class="who" title="${esc(c.profile_id)}">${esc(initials(c.profile_id))}</span>` : "";
  let acts = "", data, open = "";
  if(c.kind==="wo"){
    data = `data-kind="wo" data-automation="${esc(c.automation)}" data-filename="${esc(c.filename)}" data-col="${esc(c.col)}"`;
    open = `onclick="openWO('${esc(c.automation)}','${esc(c.filename)}')"`;
  } else if(c.kind==="draft"){
    data = `data-kind="draft"`;
    open = `onclick="openDraft('${esc(c.client)}','${esc(c.area)}','${esc(c.scope)}','${esc(c.workflow)}','${esc(c.period||'')}')"`;
  } else if(c.kind==="approved" && c.workflow){
    data = `data-kind="approved"`;
    acts = `<div class="acts"><button class="btn ok" onclick="publishApproved('${esc(c.client)}','${esc(c.area)}','${esc(c.workflow)}','${esc(c.scope)}','${esc(c.period)}')">Publish →</button></div>`;
  } else {
    data = `data-kind="${esc(c.kind)}"`;
  }
  return `<div class="card${open?' clickable':''}" ${data} style="--sys:${color}" ${open}>
    <div class="card-top"><span class="tag">${label}${c.manual?" ·man":""}</span><span class="client">${chip}${esc(c.client)}</span></div>
    <div class="title">${esc(c.title)}</div><div class="sub">${esc(c.sub)}</div>
    ${c.preview?`<div class="preview">${esc(c.preview)}</div>`:""}
    ${c.reason?`<div class="reason">${esc(c.reason)}</div>`:""}
    <div class="meta">${esc(meta)}</div>${acts}</div>`;
}
