// Fractional Employees: one swimlane per CloakBrowser persona. Same drag rules as the main board.
const FR_COLS = [["queued","QUEUED"],["progress","IN PROGRESS"],["done","DONE"],["held","FAILED / HELD"]];
let FR_LAST = null;

async function refreshFractional(){
  if($("view-fr").classList.contains("mc-hide")) return;
  FR_LAST = await apiCall("/api/fractional"); renderFractional();
}
function renderFractional(){
  const s = FR_LAST; if(!s) return;
  const ids = s.identities || [];
  $("fr-sub").textContent = ids.length ? `· ${ids.length} personas` : "";
  $("fr-board").innerHTML = `
    <div class="fr-colhead"><div class="fr-lane-label"></div>${
      FR_COLS.map(([,n])=>`<div class="fr-ch">${esc(n)}</div>`).join("")}</div>` +
    (ids.length ? ids.map(laneHTML).join("")
      : '<div class="empty">No personas — add one in clients/&lt;client&gt;/browser/profiles.yaml</div>');
  wireFractionalDrag();
}
function laneHTML(lane){
  return `<div class="fr-lane${lane.paused?" paused":""}">
    <div class="fr-lane-label"><span class="who">${esc(initials(lane.profile_id))}</span>
      <div><b>${esc(lane.profile_id)}</b><div class="fr-client">${esc(lane.client)}${lane.paused?" · paused":""}</div></div></div>
    ${FR_COLS.map(([key])=>`<div class="fr-cell"><div class="cards" data-col="${key}">${
      (lane.columns[key]||[]).map(cardHTML).join("") || '<div class="empty">—</div>'}</div></div>`).join("")}
  </div>`;
}
function wireFractionalDrag(){
  document.querySelectorAll("#fr-board .cards").forEach(list=>{
    if(list._sortable) return;
    list._sortable = Sortable.create(list, {
      group:"fr", animation:150, draggable:".card[data-kind='wo']",
      filter:".acts, .acts *", preventOnFilter:false, ghostClass:"drag-ghost",
      onEnd: async (evt)=>{
        const card = evt.item; if(card.dataset.kind!=="wo") return;
        const fromCol = evt.from.dataset.col, toCol = evt.to.dataset.col;
        if(fromCol===toCol) return;                       // within-lane reorder = visual only here
        if(!(toCol in COL_FOLDER)){ refreshFractional(); return; }
        const r = await apiCall("/api/move",
          {automation:card.dataset.automation, filename:card.dataset.filename, to:COL_FOLDER[toCol]});
        if(!r || !r.ok) alert("Move failed: "+((r&&r.error)||"unknown"));
        refreshFractional();
      }});
  });
}
setInterval(refreshFractional, 3000);   // no-ops while the view is hidden
