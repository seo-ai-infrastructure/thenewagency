"""AEO evaluator — deterministic, NO local model.

Pits the client's crawled Markdown against competitors' on EXPLICIT entity coverage (the facts an
AI agent needs to pick you: Service, Location, Price, Hours, Guarantee, ...). Produces:
  - client_coverage : fraction of required entities the client states explicitly
  - missing_entities: entities absent from the client's text (the fix list)
  - win_rate        : fraction of competitors the client matches-or-beats on coverage
  - entity_conquest : per entity a competitor states but the client does NOT -> the work-order list

The crawl (per AI bot user-agent, via Firecrawl) happens upstream; this is pure logic so it's
fully unit-testable. Reuses lib/aeo_audit.entity_clarity for the presence checks.
"""
from lib.aeo_audit import entity_clarity


def evaluate(client_md, competitor_mds, entities):
    client = entity_clarity(client_md, entities)
    comps = {d: entity_clarity(md, entities) for d, md in (competitor_mds or {}).items()}
    wins = sum(1 for c in comps.values() if client["clarity"] >= c["clarity"])
    win_rate = round(wins / len(comps), 4) if comps else None

    conquest = {}
    for name in (entities or {}):
        if not client["entities"].get(name):
            holders = [d for d, c in comps.items() if c["entities"].get(name)]
            if holders:
                conquest[name] = holders

    return {"client_coverage": client["clarity"],
            "missing_entities": client["missing"],
            "win_rate": win_rate, "wins": wins,
            "competitors": {d: c["clarity"] for d, c in comps.items()},
            "entity_conquest": conquest,
            "entity_matrix": {name: {"client": client["entities"].get(name, False),
                                     "competitors": {d: c["entities"].get(name, False)
                                                     for d, c in comps.items()}}
                              for name in (entities or {})}}
