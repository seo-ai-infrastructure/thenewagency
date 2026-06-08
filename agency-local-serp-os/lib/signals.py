"""Unified search/behavior Signals snapshot for one client+date — the measurement layer the
cadence and reporting consume. Merges the connectors into one dict and derives the
conversion-focused headline metrics (calls, conversions, CRO flags)."""
import json, pathlib


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def build_snapshot(client, date, gsc=None, bing=None, gbp=None, ga4=None, clarity=None):
    gbp = gbp or {}
    organic_conv = None
    for row in (ga4 or []):
        if str(row.get("sessionDefaultChannelGroup", "")).lower().startswith("organic"):
            organic_conv = _int(row.get("conversions"))
            break
    clarity = clarity or {}
    return {
        "client": client, "date": date,
        "search": {"gsc": gsc or [], "bing": bing or []},
        "local": {"gbp": gbp},
        "behavior": {"ga4": ga4 or [], "clarity": clarity},
        "derived": {
            "gbp_calls": _int(gbp.get("calls")),
            "gbp_website_clicks": _int(gbp.get("website_clicks")),
            "organic_conversions": organic_conv,
            "cro_flags": {
                "rage_clicks": _int((clarity.get("RageClickCount") or {}).get("subTotal")),
                "dead_clicks": _int((clarity.get("DeadClickCount") or {}).get("subTotal")),
            },
        },
    }


def write_snapshot(root, snap):
    d = pathlib.Path(root) / "clients" / snap["client"] / "signals"
    d.mkdir(parents=True, exist_ok=True)
    out = d / f"{snap['date']}.json"
    out.write_text(json.dumps(snap, indent=2))
    return out
