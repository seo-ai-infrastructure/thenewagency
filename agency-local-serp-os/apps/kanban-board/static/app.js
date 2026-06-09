// Top-level view switch (Command Center / dashboards / Kanban board).
function setView(v){
  const isBoard = v === "board";
  $("view-mc").classList.toggle("mc-hide", v !== "mc");
  $("view-si").classList.toggle("mc-hide", v !== "si");
  $("view-ai").classList.toggle("mc-hide", v !== "ai");
  $("view-ci").classList.toggle("mc-hide", v !== "ci");
  $("view-ti").classList.toggle("mc-hide", v !== "ti");
  $("view-board").classList.toggle("mc-hide", !isBoard);
  $("view-fr").classList.toggle("mc-hide", v !== "fr");
  $("nav-fr").classList.toggle("active", v === "fr");
  $("nav-mc").classList.toggle("active", v === "mc");
  $("nav-si").classList.toggle("active", v === "si");
  $("nav-ai").classList.toggle("active", v === "ai");
  $("nav-ci").classList.toggle("active", v === "ci");
  $("nav-ti").classList.toggle("active", v === "ti");
  $("nav-board").classList.toggle("active", isBoard);
  document.querySelectorAll(".board-only").forEach(el => el.classList.toggle("mc-hide", !isBoard));
  if(window.mcShow) window.mcShow(isBoard ? null : v);   // start/stop the active dashboard poll
  if(isBoard) refresh();                                  // board just became visible -> pull state now
  if(v === "fr") refreshFractional();
  try { if (location.hash !== "#" + v) history.replaceState(null, "", "#" + v); } catch(e){}  // deep-linkable
}
const VALID_VIEWS = ["mc","si","ai","ci","ti","board","fr"];
$("nav-mc").onclick = () => setView("mc");
$("nav-si").onclick = () => setView("si");
$("nav-ai").onclick = () => setView("ai");
$("nav-ci").onclick = () => setView("ci");
$("nav-ti").onclick = () => setView("ti");
$("nav-board").onclick = () => setView("board");
$("nav-fr").onclick = () => setView("fr");
window.addEventListener("hashchange", () => {
  const h = (location.hash || "").replace("#","");
  if (VALID_VIEWS.includes(h)) setView(h);
});

const _initial = (location.hash || "").replace("#","");   // open the deep-linked tab if present
setView(VALID_VIEWS.includes(_initial) ? _initial : "mc"); // else Command Center (default landing)
