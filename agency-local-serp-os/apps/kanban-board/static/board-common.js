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
