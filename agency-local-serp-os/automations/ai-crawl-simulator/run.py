#!/usr/bin/env python3
"""AEO crawl simulator — crawls client + competitor sites AS AI bot user-agents via Firecrawl,
runs the crawlability audit and entity-coverage evaluation, writes a schema-validated history
doc and the client's agent snapshot, and generates entity-conquest recommendations.

Usage:
    python automations/ai-crawl-simulator/run.py [--client <id>] [--dry-run]

--dry-run: uses fixtures under automations/ai-crawl-simulator/fixtures/; no network, no API key.
"""
import sys
import json
import datetime
import pathlib
import yaml


def _root(start):
    for d in [start, *start.parents]:
        if (d / "lib" / "aeo_audit.py").exists():
            return d
    raise RuntimeError("repo root not found — could not locate lib/aeo_audit.py")


HERE = pathlib.Path(__file__).resolve().parent
ROOT = _root(HERE)
sys.path.insert(0, str(ROOT))

from integrations.firecrawl import client as fc
from lib import aeo_audit, aeo_evaluator, aeo_recs, schema
from lib.env import load_env
load_env()   # so a live run picks up FIRECRAWL_API_KEY from the repo-root .env (no-op for --dry-run)


def _parse_args():
    dry = "--dry-run" in sys.argv
    client_id = "example-hvac-client"
    if "--client" in sys.argv:
        idx = sys.argv.index("--client")
        if idx + 1 < len(sys.argv):
            client_id = sys.argv[idx + 1]
    return client_id, dry


def _load_config(client_id):
    cfg_path = ROOT / "clients" / client_id / "config" / "llm_directives.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def _dry_run_crawl(cfg, bot_names):
    """Read fixtures; no network calls."""
    fix = HERE / "fixtures"
    client_md = (fix / "client.md").read_text(encoding="utf-8")
    llms_txt_present = (fix / "llms.txt").exists()

    competitor_mds = {}
    for comp in cfg.get("competitors", []):
        domain = comp["domain"]
        fixture_file = fix / f"{domain}.md"
        if fixture_file.exists():
            competitor_mds[domain] = fixture_file.read_text(encoding="utf-8")
        # Missing competitor fixture -> silently skip

    bots = [{"bot": b, "accessible": True, "blocked_by_robots": False} for b in bot_names]
    return client_md, competitor_mds, llms_txt_present, bots


def _live_crawl(cfg, bot_names, primary_url):
    """Live HTTP crawl via Firecrawl; requires FIRECRAWL_API_KEY in env."""
    from urllib.parse import urljoin

    try:
        client_md = fc.scrape(primary_url)["markdown"]      # the client page is the subject -> fatal if it fails
    except Exception as exc:
        raise RuntimeError(f"client crawl failed for {primary_url}: {exc}") from exc

    bots = []
    for b in bot_names:
        try:
            r = fc.scrape(primary_url, bot=b)
            bots.append({"bot": b, "accessible": not r["blocked"], "blocked_by_robots": bool(r["blocked"])})
        except Exception as exc:
            print(f"[warn] bot probe failed for {b}: {exc}", file=sys.stderr)
            bots.append({"bot": b, "accessible": False, "blocked_by_robots": False})

    try:
        llms_r = fc.scrape(urljoin(primary_url, "llms.txt"))
        llms_txt_present = (not llms_r["blocked"]) and bool(llms_r["markdown"])
    except Exception:
        llms_txt_present = False

    competitor_mds = {}
    for comp in cfg.get("competitors", []):
        domain = comp.get("domain")
        try:                                                 # one competitor failing must not abort the audit
            competitor_mds[domain] = fc.scrape(comp["url"])["markdown"]
        except Exception as exc:
            print(f"[warn] skipping competitor {domain}: {exc}", file=sys.stderr)

    return client_md, competitor_mds, llms_txt_present, bots


def main():
    client_id, dry = _parse_args()
    cfg = _load_config(client_id)

    entities = cfg.get("entities", {})
    client_urls = cfg.get("client_urls") or []
    primary_url = client_urls[0] if client_urls else None     # only required by the live path
    bot_names = cfg.get("bots") or list(fc.AI_BOTS)

    if dry:
        client_md, competitor_mds, llms_txt_present, bots = _dry_run_crawl(cfg, bot_names)
    else:
        if not primary_url:
            raise RuntimeError(f"client '{client_id}' config is missing client_urls")
        client_md, competitor_mds, llms_txt_present, bots = _live_crawl(cfg, bot_names, primary_url)

    crawlability = aeo_audit.audit(client_md, entities, llms_txt_present, bots)
    evaluation = aeo_evaluator.evaluate(client_md, competitor_mds, entities)

    now = datetime.datetime.now(datetime.timezone.utc)
    run_id = "aeo_" + now.strftime("%Y%m%dT%H%M%SZ")
    generated_at = now.isoformat()

    doc = {
        "run_id": run_id,
        "generated_at": generated_at,
        "client": client_id,
        "crawlability": crawlability,
        "evaluation": evaluation,
    }

    schema.validate(doc, schema.AEO_AUDIT)

    # Write history doc
    hist_dir = HERE / "history"
    hist_dir.mkdir(exist_ok=True)
    hist_path = hist_dir / f"{run_id}.json"
    hist_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # Write client agent snapshot
    snap_dir = ROOT / "clients" / client_id / "facts"
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / "agent_snapshot.md").write_text(client_md, encoding="utf-8")

    # Generate and write entity-conquest recommendations
    recs = aeo_recs.entity_conquest_recs(evaluation, client_id)
    aeo_recs.write_recs(ROOT, recs)

    win_rate = evaluation.get("win_rate")
    n_missing = len(evaluation.get("missing_entities") or [])
    n_recs = len(recs)
    wr_str = f"{win_rate:.2f}" if win_rate is not None else "n/a"
    prefix = "DRY " if dry else ""
    print(
        f"[{prefix}aeo-crawl] {run_id}: win-rate {wr_str}, "
        f"{n_missing} missing entities, {n_recs} entity recs -> {hist_path.name}"
    )


if __name__ == "__main__":
    main()
