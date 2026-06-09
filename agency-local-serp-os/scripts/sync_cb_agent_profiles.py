#!/usr/bin/env python3
"""Sync Agency OS browser personas with CB Agent Crew persistent profiles.

Dry-run by default: reads clients/<client>/browser/cb_agent_profiles.yaml,
ensures each mapped CB profile exists through CB Agent Crew, audits readiness,
and prints the result. Pass --write to persist discovered cb_profile_id values.
"""
import argparse, json, os, pathlib, sys
from urllib import request, error

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _json(method, url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method=method, headers={"Accept": "application/json"})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} returned {exc.code}: {detail[:300]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc


def _profile_by_name(api_base, name):
    profiles = _json("GET", f"{api_base}/api/profiles")
    for profile in profiles:
        if profile.get("name") == name:
            return profile
    return None


def _ensure_profile(api_base, mapping):
    profile = _profile_by_name(api_base, mapping["cb_profile_name"])
    if profile:
        return profile
    return _json("POST", f"{api_base}/api/profiles", {
        "niche": mapping["niche"],
        "market": str(mapping["market"]).replace("_", " "),
        "role": mapping.get("cb_role", "executor"),
        "assignedAgent": f"Agency OS {mapping['os_profile_id']}",
        "tags": ["agency-os", mapping["os_profile_id"]],
    })


def _audit_profile(api_base, profile_id):
    return _json("GET", f"{api_base}/api/profiles/{profile_id}/identity-audit")


def _ready(audit):
    return (
        bool(audit.get("persistent"))
        and bool(audit.get("proxyAssigned"))
        and bool(audit.get("fingerprintSeed"))
    )


def sync(client, *, api_base, write=False):
    path = ROOT/"clients"/client/"browser"/"cb_agent_profiles.yaml"
    if not path.exists():
        raise SystemExit(f"missing {path.relative_to(ROOT)}")
    data = yaml.safe_load(path.read_text()) or {"version": 1, "profiles": []}
    changed = False
    failures = []
    results = []
    for mapping in data.get("profiles", []):
        profile = _ensure_profile(api_base, mapping)
        profile_id = profile.get("id")
        if not profile_id:
            raise RuntimeError(f"CB profile {mapping['cb_profile_name']} returned no id")
        audit = _audit_profile(api_base, profile_id)
        ready = _ready(audit)
        if write and mapping.get("cb_profile_id") != profile_id:
            mapping["cb_profile_id"] = profile_id
            changed = True
        result = {
            "os_profile_id": mapping["os_profile_id"],
            "cb_profile_name": mapping["cb_profile_name"],
            "cb_profile_id": profile_id,
            "ready": ready,
            "persistent": audit.get("persistent"),
            "proxyAssigned": audit.get("proxyAssigned"),
            "fingerprintSeed": audit.get("fingerprintSeed"),
            "fingerprintPinned": audit.get("fingerprintPinned"),
        }
        results.append(result)
        if not ready:
            failures.append(result)
    if write and changed:
        path.write_text(yaml.safe_dump(data, sort_keys=False))
    print(json.dumps({"client": client, "write": write, "profiles": results}, indent=2))
    if failures:
        raise SystemExit("one or more mapped CB profiles are not persistent/fingerprinted/proxy-ready")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="example-hvac-client")
    parser.add_argument("--api-base", default=os.environ.get("CB_CREW_API_BASE", "http://127.0.0.1:8010"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    sync(args.client, api_base=args.api_base.rstrip("/"), write=args.write)


if __name__ == "__main__":
    main()
