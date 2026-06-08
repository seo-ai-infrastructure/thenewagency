# Search-Intelligence + MAGEO Engine — Implementation Plan

> **HISTORICAL — MAGEO removed.** Plan 2 (the MAGEO optimization engine) was removed from the
> project. This document is kept as the record of **Plan 1 — the Signals-ingestion foundation**,
> which remains in use (`lib/signals.py`, `integrations/{gsc,ga4,bing_webmaster,clarity,gbp_insights}`,
> `automations/search-signals-ingest`). Ignore the Plan-2 / MAGEO sections below.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data-ingestion foundation that pulls Google Search Console, GBP Insights (Zernio), Bing Webmaster, GA4, and Microsoft Clarity into one normalized per-client `Signals` snapshot — the input the MAGEO strategy/content engine consumes to plan daily/weekly/monthly SEO tactics that increase local conversions/calls.

**Architecture:** Five thin read-only API connectors (`integrations/<source>/client.py`), each returning a normalized dict. A `lib/signals.py` normalizer merges them into one dated snapshot per client (`clients/<id>/signals/<date>.json`). An `automations/search-signals-ingest/run.py` runner orchestrates the pull (degrading gracefully when a source is unconfigured). Everything is TDD with `pytest` + mocked HTTP — no live calls in tests.

**Tech Stack:** Python 3.12, `requests`, `pyyaml`, `google-auth` (service-account → bearer token for GSC/GA4), `pytest` + `unittest.mock`. Reuses the repo's `lib.env` auto-loader and the existing `clients/<id>/` layout.

---

## Scope check — this is 3 plans

| Plan | Subsystem | Ships on its own? |
|------|-----------|-------------------|
| **THIS PLAN** | Search-data ingestion → unified `Signals` store | ✅ yes — a runnable ingestion pipeline + tests |
| Plan 2 | **MAGEO engine** — Preference / Planner / Editor / Evaluator agents + Skill Bank + Fidelity Gate | depends on Plan 1's `Signals` |
| Plan 3 | **Cadence orchestrator** — daily/weekly/monthly tactic scheduler + content generation + CRO loop | depends on Plans 1 & 2 |

Plans 2 and 3 are architected at the end of this doc and must each get their own `writing-plans` pass before execution. This plan delivers Plan 1 in full.

---

## Whole-system file structure

```
integrations/
  bing_webmaster/client.py      # NEW  Bing Webmaster API (apikey)            [Plan 1]
  clarity/client.py             # NEW  Microsoft Clarity Data Export (Bearer) [Plan 1]
  google_auth.py                # NEW  service-account -> bearer token         [Plan 1]
  gsc/client.py                 # NEW  Google Search Console Search Analytics  [Plan 1]
  ga4/client.py                 # NEW  Google Analytics 4 Data API             [Plan 1]
  gbp_insights/client.py        # NEW  GBP insights via Zernio                 [Plan 1]
lib/
  signals.py                    # NEW  unified Signals model + normalize+store [Plan 1]
  mageo/                        # NEW  Plan 2: preference, planner, editor, evaluator, skill_bank
automations/
  search-signals-ingest/run.py  # NEW  ingestion runner                        [Plan 1]
  mageo-optimize/run.py         # NEW  Plan 2 runner
scripts/
  ingest_signals.py             # NEW  CLI for the ingestion runner            [Plan 1]
clients/<id>/
  config/sources.yaml           # NEW  which GSC site / GA4 property / Clarity project / Bing site [Plan 1]
  signals/<date>.json           # OUTPUT  normalized snapshot                  [Plan 1]
  mageo/preferences/<engine>.json  # Plan 2 output
playbooks/
  serp_feature_takeover.yaml    # EXISTS  becomes the seed of the MAGEO Skill Bank
tests/
  conftest.py                   # NEW  test harness                           [Plan 1]
  test_*.py                     # NEW  per-component tests                     [Plan 1]
requirements-dev.txt            # NEW  pytest                                  [Plan 1]
```

Each connector has ONE responsibility (one API), returns a plain normalized dict, and never writes files — the runner owns I/O. This keeps every file small enough to hold in context and testable in isolation.

---

## Task 0: Prerequisites (config + auth) — do this first

**Files:**
- Create: `requirements-dev.txt`
- Create: `clients/example-hvac-client/config/sources.yaml`
- Modify: `.env` (add a GSC/GA4 service-account path)

- [ ] **Step 1: Add the dev requirement**

Create `requirements-dev.txt`:
```
pytest
```

- [ ] **Step 2: Install it**

Run: `pip install -r requirements-dev.txt`
Expected: `pytest` already satisfied (verified installed).

- [ ] **Step 3: Create the per-client source map**

Create `clients/example-hvac-client/config/sources.yaml`:
```yaml
version: 1
# Which property/site/project each search-data source should pull for this client.
gsc:
  site_url: "https://houseacrepair.com/"     # exact GSC property (URL-prefix) or "sc-domain:houseacrepair.com"
ga4:
  property_id: "REPLACE_GA4_NUMERIC_ID"      # GA4 Admin -> Property Settings -> Property ID (numeric)
bing:
  site_url: "https://houseacrepair.com/"     # verified Bing Webmaster site
clarity:
  enabled: true                              # uses MICROSOFT_CLARITY_API_TOKEN (project-scoped JWT)
gbp_insights:
  zernio_account_id: "6a1993762b2567671a6704b2"   # from integrations/google_business (Zernio account _id)
```

- [ ] **Step 4: Provision Google read access for GSC + GA4**

GSC and GA4 are read-only data sources (not the media generation that was removed). Create a Google Cloud service account with these scopes and grant it access:
1. In Google Cloud console, create a service account; download its JSON key to `C:\Users\brock\keys\seo-readonly.json`.
2. Enable APIs: **Search Console API** and **Google Analytics Data API**.
3. In **Search Console** → Settings → Users and permissions → add the service-account email as a **Full** (or Restricted) user on the property.
4. In **GA4** → Admin → Property Access Management → add the service-account email as **Viewer**.
5. Add to `.env`:
```
GSC_GA4_CREDENTIALS=C:\Users\brock\keys\seo-readonly.json
```
(We use a dedicated var, NOT `GOOGLE_APPLICATION_CREDENTIALS`, so this never re-enables any media path.)

- [ ] **Step 5: Commit the scaffolding**

```bash
git add requirements-dev.txt clients/example-hvac-client/config/sources.yaml
git commit -m "chore: search-data ingestion scaffolding (sources.yaml, pytest dep)"
```

---

## Task 1: pytest harness

**Files:**
- Create: `tests/conftest.py`
- Test: `tests/test_harness.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_harness.py`:
```python
def test_repo_root_on_path():
    import lib.env  # importable only if repo root is on sys.path
    assert hasattr(lib.env, "load_env")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_harness.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib'` (root not on path yet).

- [ ] **Step 3: Add the conftest that puts repo root on the path**

Create `tests/conftest.py`:
```python
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_harness.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_harness.py
git commit -m "test: pytest harness with repo root on path"
```

---

## Task 2: Bing Webmaster connector

**Files:**
- Create: `integrations/bing_webmaster/__init__.py` (empty)
- Create: `integrations/bing_webmaster/client.py`
- Test: `tests/test_bing_webmaster.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_bing_webmaster.py`:
```python
from unittest.mock import patch, MagicMock
from integrations.bing_webmaster.client import query_stats

def test_query_stats_parses_rows():
    fake = {"d": [
        {"Query": "ac repair fort lauderdale", "Impressions": 120, "Clicks": 9,
         "AvgImpressionPosition": 18, "AvgClickPosition": 6},
        {"Query": "ac tune up", "Impressions": 60, "Clicks": 2,
         "AvgImpressionPosition": 25, "AvgClickPosition": 11},
    ]}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch("integrations.bing_webmaster.client.requests.get", return_value=resp) as g:
        rows = query_stats("https://houseacrepair.com/", api_key="K")
    assert rows[0] == {"query": "ac repair fort lauderdale", "impressions": 120,
                       "clicks": 9, "avg_impression_position": 18, "avg_click_position": 6}
    assert len(rows) == 2
    # apikey + siteUrl must be sent
    assert g.call_args.kwargs["params"]["apikey"] == "K"
    assert g.call_args.kwargs["params"]["siteUrl"] == "https://houseacrepair.com/"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_bing_webmaster.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.bing_webmaster`.

- [ ] **Step 3: Write the connector**

Create `integrations/bing_webmaster/__init__.py` (empty file).

Create `integrations/bing_webmaster/client.py`:
```python
"""Bing Webmaster Tools API (read-only). Auth = apikey query param (BING_WEBMASTER_API_KEY)."""
import os, requests

BASE = "https://ssl.bing.com/webmaster/api.svc/json"


def query_stats(site_url, api_key=None):
    """GetQueryStats -> normalized rows [{query, impressions, clicks, avg_impression_position, avg_click_position}]."""
    api_key = api_key or os.environ["BING_WEBMASTER_API_KEY"]
    r = requests.get(f"{BASE}/GetQueryStats",
                     params={"apikey": api_key, "siteUrl": site_url}, timeout=30)
    r.raise_for_status()
    out = []
    for d in (r.json().get("d") or []):
        out.append({
            "query": d.get("Query"),
            "impressions": d.get("Impressions"),
            "clicks": d.get("Clicks"),
            "avg_impression_position": d.get("AvgImpressionPosition"),
            "avg_click_position": d.get("AvgClickPosition"),
        })
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_bing_webmaster.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add integrations/bing_webmaster/ tests/test_bing_webmaster.py
git commit -m "feat: Bing Webmaster query-stats connector"
```

---

## Task 3: Microsoft Clarity connector (CRO signals)

**Files:**
- Create: `integrations/clarity/__init__.py` (empty)
- Create: `integrations/clarity/client.py`
- Test: `tests/test_clarity.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_clarity.py`:
```python
from unittest.mock import patch, MagicMock
from integrations.clarity.client import live_insights

def test_live_insights_indexes_by_metric():
    fake = [
        {"metricName": "Traffic", "information": [{"totalSessionCount": "200", "distinctUserCount": "150"}]},
        {"metricName": "RageClickCount", "information": [{"subTotal": "12"}]},
        {"metricName": "DeadClickCount", "information": [{"subTotal": "5"}]},
        {"metricName": "ScrollDepth", "information": [{"averageScrollDepth": 41.2}]},
    ]
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch("integrations.clarity.client.requests.get", return_value=resp) as g:
        m = live_insights(token="JWT", num_days=3)
    assert m["Traffic"]["totalSessionCount"] == "200"
    assert m["RageClickCount"]["subTotal"] == "12"
    assert g.call_args.kwargs["headers"]["Authorization"] == "Bearer JWT"
    assert g.call_args.kwargs["params"]["numOfDays"] == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_clarity.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.clarity`.

- [ ] **Step 3: Write the connector**

Create `integrations/clarity/__init__.py` (empty file).

Create `integrations/clarity/client.py`:
```python
"""Microsoft Clarity Data Export API (read-only). Auth = Bearer MICROSOFT_CLARITY_API_TOKEN.
Returns CRO behavior signals: sessions, scroll depth, rage/dead clicks, etc.
NOTE: Clarity allows numOfDays in 1..3 and ~10 requests/day per project."""
import os, requests

URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"


def live_insights(token=None, num_days=3):
    """-> {metricName: information[0]} dict (first info row per metric)."""
    token = token or os.environ["MICROSOFT_CLARITY_API_TOKEN"]
    r = requests.get(URL, headers={"Authorization": f"Bearer {token}"},
                     params={"numOfDays": num_days}, timeout=30)
    r.raise_for_status()
    out = {}
    for m in (r.json() or []):
        info = m.get("information") or [{}]
        out[m.get("metricName")] = info[0] if info else {}
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_clarity.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add integrations/clarity/ tests/test_clarity.py
git commit -m "feat: Microsoft Clarity CRO-signals connector"
```

---

## Task 4: Google auth helper (service-account → bearer token)

**Files:**
- Create: `integrations/google_auth.py`
- Test: `tests/test_google_auth.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_google_auth.py`:
```python
from unittest.mock import patch, MagicMock
import integrations.google_auth as ga

def test_bearer_token_minted_from_service_account():
    creds = MagicMock(); creds.token = "ya29.fake"
    with patch.dict("os.environ", {"GSC_GA4_CREDENTIALS": "C:/k.json"}), \
         patch.object(ga.service_account.Credentials, "from_service_account_file", return_value=creds) as mk, \
         patch.object(ga, "Request", return_value="REQ"):
        tok = ga.bearer_token(["https://www.googleapis.com/auth/webmasters.readonly"])
    assert tok == "ya29.fake"
    creds.refresh.assert_called_once_with("REQ")
    assert mk.call_args.kwargs["scopes"] == ["https://www.googleapis.com/auth/webmasters.readonly"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_google_auth.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.google_auth`.

- [ ] **Step 3: Write the helper**

Create `integrations/google_auth.py`:
```python
"""Mint a read-only bearer token from a service-account JSON for GSC + GA4 ingestion.
Uses GSC_GA4_CREDENTIALS (a dedicated var, separate from any media credentials)."""
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request


def bearer_token(scopes):
    path = os.environ["GSC_GA4_CREDENTIALS"]
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    creds.refresh(Request())
    return creds.token
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_google_auth.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add integrations/google_auth.py tests/test_google_auth.py
git commit -m "feat: google service-account bearer-token helper"
```

---

## Task 5: Google Search Console connector

**Files:**
- Create: `integrations/gsc/__init__.py` (empty)
- Create: `integrations/gsc/client.py`
- Test: `tests/test_gsc.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gsc.py`:
```python
from unittest.mock import patch, MagicMock
from integrations.gsc import client as gsc

def test_search_analytics_normalizes_rows():
    fake = {"rows": [
        {"keys": ["ac repair fort lauderdale", "https://houseacrepair.com/"],
         "clicks": 14, "impressions": 230, "ctr": 0.06, "position": 7.2},
    ]}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(gsc, "bearer_token", return_value="TOK"), \
         patch.object(gsc.requests, "post", return_value=resp) as p:
        rows = gsc.search_analytics("https://houseacrepair.com/", "2026-05-01", "2026-05-28")
    assert rows[0] == {"query": "ac repair fort lauderdale", "page": "https://houseacrepair.com/",
                       "clicks": 14, "impressions": 230, "ctr": 0.06, "position": 7.2}
    assert p.call_args.kwargs["headers"]["Authorization"] == "Bearer TOK"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_gsc.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.gsc`.

- [ ] **Step 3: Write the connector**

Create `integrations/gsc/__init__.py` (empty file).

Create `integrations/gsc/client.py`:
```python
"""Google Search Console — Search Analytics API (read-only)."""
import urllib.parse, requests
from integrations.google_auth import bearer_token

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def search_analytics(site_url, start_date, end_date, dimensions=("query", "page"), row_limit=250):
    tok = bearer_token([SCOPE])
    enc = urllib.parse.quote(site_url, safe="")
    r = requests.post(
        f"https://www.googleapis.com/webmasters/v3/sites/{enc}/searchAnalytics/query",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"startDate": start_date, "endDate": end_date,
              "dimensions": list(dimensions), "rowLimit": row_limit}, timeout=60)
    r.raise_for_status()
    out = []
    for row in (r.json().get("rows") or []):
        rec = dict(zip(dimensions, row.get("keys", [])))
        rec.update({"clicks": row.get("clicks"), "impressions": row.get("impressions"),
                    "ctr": row.get("ctr"), "position": row.get("position")})
        out.append(rec)
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_gsc.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add integrations/gsc/ tests/test_gsc.py
git commit -m "feat: Google Search Console search-analytics connector"
```

---

## Task 6: GA4 connector (sessions + conversions/calls)

**Files:**
- Create: `integrations/ga4/__init__.py` (empty)
- Create: `integrations/ga4/client.py`
- Test: `tests/test_ga4.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ga4.py`:
```python
from unittest.mock import patch, MagicMock
from integrations.ga4 import client as ga4

def test_run_report_normalizes_conversions():
    fake = {"rows": [
        {"dimensionValues": [{"value": "google / organic"}],
         "metricValues": [{"value": "320"}, {"value": "11"}]},
    ], "rowCount": 1}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(ga4, "bearer_token", return_value="TOK"), \
         patch.object(ga4.requests, "post", return_value=resp) as p:
        rows = ga4.run_report("123456", "2026-05-01", "2026-05-28",
                              dimensions=["sessionDefaultChannelGroup"],
                              metrics=["sessions", "conversions"])
    assert rows[0] == {"sessionDefaultChannelGroup": "google / organic",
                       "sessions": "320", "conversions": "11"}
    assert "properties/123456:runReport" in p.call_args.args[0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_ga4.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.ga4`.

- [ ] **Step 3: Write the connector**

Create `integrations/ga4/__init__.py` (empty file).

Create `integrations/ga4/client.py`:
```python
"""Google Analytics 4 — Data API runReport (read-only). Track conversions/calls by channel/page."""
import requests
from integrations.google_auth import bearer_token

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def run_report(property_id, start_date, end_date, dimensions, metrics):
    tok = bearer_token([SCOPE])
    r = requests.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"dateRanges": [{"startDate": start_date, "endDate": end_date}],
              "dimensions": [{"name": d} for d in dimensions],
              "metrics": [{"name": m} for m in metrics]}, timeout=60)
    r.raise_for_status()
    out = []
    for row in (r.json().get("rows") or []):
        rec = {d: dv.get("value") for d, dv in zip(dimensions, row.get("dimensionValues", []))}
        rec.update({m: mv.get("value") for m, mv in zip(metrics, row.get("metricValues", []))})
        out.append(rec)
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_ga4.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add integrations/ga4/ tests/test_ga4.py
git commit -m "feat: GA4 Data API runReport connector"
```

---

## Task 7: GBP Insights via Zernio (discovery + connector)

**Files:**
- Create: `integrations/gbp_insights/__init__.py` (empty)
- Create: `integrations/gbp_insights/client.py`
- Test: `tests/test_gbp_insights.py`

- [ ] **Step 1: Discover the real Zernio insights endpoint (one-time, live, read-only)**

Run this probe (the Zernio account exposes `analyticsLastSyncedAt`, so an insights endpoint exists):
```bash
python -c "
import os, requests, sys; sys.path.insert(0,'.')
from lib.env import load_env; load_env()
H={'Authorization':'Bearer '+os.environ['ZERNIO_API_KEY']}
acct='6a1993762b2567671a6704b2'
for p in ['/accounts/%s/insights','/accounts/%s/analytics','/accounts/%s/gmb-insights','/accounts/%s/gmb-analytics']:
    r=requests.get('https://zernio.com/api/v1'+(p%acct), headers=H, timeout=20)
    print(p%acct, '->', r.status_code, r.text[:120])
"
```
Record the path that returns 200 as `INSIGHTS_PATH` and the JSON field names below. (If none return 200, the connector falls back to the metrics already present on `GET /accounts` — `analyticsLastSyncedAt`, `externalPostCount` — and this task narrows to parsing those.)

- [ ] **Step 2: Write the failing test (using the discovered shape)**

Create `tests/test_gbp_insights.py`:
```python
from unittest.mock import patch, MagicMock
from integrations.gbp_insights import client as gbp

def test_insights_normalized():
    fake = {"calls": 42, "directionRequests": 18, "websiteClicks": 30, "views": 1200}
    resp = MagicMock(status_code=200); resp.json.return_value = fake; resp.raise_for_status.return_value = None
    with patch.object(gbp.requests, "get", return_value=resp):
        m = gbp.insights("6a1993762b2567671a6704b2", token="T")
    assert m["calls"] == 42 and m["website_clicks"] == 30 and m["direction_requests"] == 18
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_gbp_insights.py -q`
Expected: FAIL — `ModuleNotFoundError: integrations.gbp_insights`.

- [ ] **Step 4: Write the connector (map fields from Step 1)**

Create `integrations/gbp_insights/__init__.py` (empty file).

Create `integrations/gbp_insights/client.py` — replace `INSIGHTS_PATH` and the key names with what Step 1 returned:
```python
"""GBP insights via Zernio (calls, direction requests, website clicks, views). Auth = Bearer ZERNIO_API_KEY."""
import os, requests

BASE = "https://zernio.com/api/v1"
INSIGHTS_PATH = "/accounts/{acct}/insights"   # <-- set to the path discovered in Step 1


def insights(account_id, token=None):
    token = token or os.environ["ZERNIO_API_KEY"]
    r = requests.get(BASE + INSIGHTS_PATH.format(acct=account_id),
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    d = r.json() or {}
    return {
        "calls": d.get("calls"),
        "direction_requests": d.get("directionRequests"),
        "website_clicks": d.get("websiteClicks"),
        "views": d.get("views"),
        "raw": d,
    }
```

- [ ] **Step 5: Run to verify it passes**

Run: `python -m pytest tests/test_gbp_insights.py -q`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add integrations/gbp_insights/ tests/test_gbp_insights.py
git commit -m "feat: GBP insights via Zernio connector"
```

---

## Task 8: Unified Signals model + normalizer

**Files:**
- Create: `lib/signals.py`
- Test: `tests/test_signals.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_signals.py`:
```python
from lib.signals import build_snapshot

def test_build_snapshot_merges_and_derives():
    snap = build_snapshot(
        client="example-hvac-client", date="2026-06-06",
        gsc=[{"query": "ac repair fort lauderdale", "page": "/", "clicks": 14,
              "impressions": 230, "ctr": 0.06, "position": 7.2}],
        bing=[{"query": "ac repair", "impressions": 50, "clicks": 2,
               "avg_impression_position": 20, "avg_click_position": 8}],
        gbp={"calls": 42, "direction_requests": 18, "website_clicks": 30, "views": 1200},
        ga4=[{"sessionDefaultChannelGroup": "Organic Search", "sessions": "320", "conversions": "11"}],
        clarity={"RageClickCount": {"subTotal": "12"}, "DeadClickCount": {"subTotal": "5"}},
    )
    assert snap["client"] == "example-hvac-client" and snap["date"] == "2026-06-06"
    assert snap["search"]["gsc"][0]["clicks"] == 14
    assert snap["local"]["gbp"]["calls"] == 42
    # derived: total calls/conversions surfaced for the conversion goal
    assert snap["derived"]["gbp_calls"] == 42
    assert snap["derived"]["organic_conversions"] == 11
    assert snap["derived"]["cro_flags"]["rage_clicks"] == 12
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_signals.py -q`
Expected: FAIL — `ModuleNotFoundError: lib.signals`.

- [ ] **Step 3: Write the model + normalizer**

Create `lib/signals.py`:
```python
"""Unified search/behavior Signals snapshot for one client+date — the input MAGEO consumes.
Merges the connectors into one dict and derives the conversion-focused headline metrics."""
import json, pathlib


def _int(v):
    try: return int(float(v))
    except (TypeError, ValueError): return None


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_signals.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add lib/signals.py tests/test_signals.py
git commit -m "feat: unified Signals snapshot model + normalizer"
```

---

## Task 9: Ingestion runner (graceful when a source is unconfigured)

**Files:**
- Create: `automations/search-signals-ingest/run.py`
- Test: `tests/test_ingest_runner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_runner.py`:
```python
import json, pathlib
from unittest.mock import patch
import importlib.util

def _load_runner():
    p = pathlib.Path("automations/search-signals-ingest/run.py").resolve()
    spec = importlib.util.spec_from_file_location("ingest_run", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_runner_writes_snapshot_with_available_sources(tmp_path):
    run = _load_runner()
    sources = {"bing": {"site_url": "https://x/"}, "clarity": {"enabled": True}}
    with patch.object(run, "bing_query_stats", return_value=[{"query": "q", "impressions": 1, "clicks": 0,
                       "avg_impression_position": 1, "avg_click_position": 1}]), \
         patch.object(run, "clarity_live_insights", return_value={"RageClickCount": {"subTotal": "3"}}):
        snap = run.ingest("example-hvac-client", "2026-06-06", sources, root=str(tmp_path))
    assert snap["search"]["bing"][0]["query"] == "q"
    assert snap["derived"]["cro_flags"]["rage_clicks"] == 3
    written = tmp_path / "clients" / "example-hvac-client" / "signals" / "2026-06-06.json"
    assert json.loads(written.read_text())["client"] == "example-hvac-client"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_ingest_runner.py -q`
Expected: FAIL — file `automations/search-signals-ingest/run.py` does not exist.

- [ ] **Step 3: Write the runner**

Create `automations/search-signals-ingest/run.py`:
```python
#!/usr/bin/env python3
"""Pull every configured search-data source for a client+date into one Signals snapshot.
Each source is optional: a missing key/config is skipped (logged), not fatal.

  python scripts/ingest_signals.py --client example-hvac-client [--date YYYY-MM-DD]"""
import sys, datetime, pathlib, yaml
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
from lib.env import load_env; load_env()
from lib.signals import build_snapshot, write_snapshot
from integrations.bing_webmaster.client import query_stats as bing_query_stats
from integrations.clarity.client import live_insights as clarity_live_insights
from integrations.gbp_insights.client import insights as gbp_insights
from integrations.gsc.client import search_analytics as gsc_search_analytics
from integrations.ga4.client import run_report as ga4_run_report


def _safe(label, fn, default):
    try:
        return fn()
    except Exception as e:
        print(f"  [skip] {label}: {type(e).__name__}: {e}")
        return default


def ingest(client, date, sources, root=None):
    root = root or str(ROOT)
    start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=28)).isoformat()
    gsc = bing = gbp = ga4 = clarity = None
    if sources.get("gsc", {}).get("site_url"):
        gsc = _safe("gsc", lambda: gsc_search_analytics(sources["gsc"]["site_url"], start, date), [])
    if sources.get("bing", {}).get("site_url"):
        bing = _safe("bing", lambda: bing_query_stats(sources["bing"]["site_url"]), [])
    if sources.get("gbp_insights", {}).get("zernio_account_id"):
        gbp = _safe("gbp", lambda: gbp_insights(sources["gbp_insights"]["zernio_account_id"]), {})
    if sources.get("ga4", {}).get("property_id", "").isdigit():
        ga4 = _safe("ga4", lambda: ga4_run_report(sources["ga4"]["property_id"], start, date,
                    ["sessionDefaultChannelGroup"], ["sessions", "conversions"]), [])
    if sources.get("clarity", {}).get("enabled"):
        clarity = _safe("clarity", lambda: clarity_live_insights(), {})
    snap = build_snapshot(client, date, gsc=gsc, bing=bing, gbp=gbp, ga4=ga4, clarity=clarity)
    write_snapshot(root, snap)
    return snap


def main():
    a = sys.argv
    client = a[a.index("--client") + 1] if "--client" in a else "example-hvac-client"
    date = a[a.index("--date") + 1] if "--date" in a else datetime.date.today().isoformat()
    sources = yaml.safe_load((ROOT / "clients" / client / "config" / "sources.yaml").read_text())
    snap = ingest(client, date, sources)
    d = snap["derived"]
    print(f"[signals] {client} {date}: gbp_calls={d['gbp_calls']} organic_conversions={d['organic_conversions']} "
          f"rage_clicks={d['cro_flags']['rage_clicks']} -> clients/{client}/signals/{date}.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_ingest_runner.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add automations/search-signals-ingest/run.py tests/test_ingest_runner.py
git commit -m "feat: search-signals ingestion runner (graceful per-source)"
```

---

## Task 10: CLI shim

**Files:**
- Create: `scripts/ingest_signals.py`
- Test: `tests/test_ingest_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ingest_cli.py`:
```python
import pathlib

def test_cli_delegates_to_runner():
    src = pathlib.Path("scripts/ingest_signals.py").read_text()
    assert "search-signals-ingest" in src and "run.py" in src
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_ingest_cli.py -q`
Expected: FAIL — file does not exist.

- [ ] **Step 3: Write the CLI shim**

Create `scripts/ingest_signals.py`:
```python
#!/usr/bin/env python3
"""Thin CLI -> automations/search-signals-ingest/run.py. See that file for flags."""
import sys, runpy, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.argv[0] = str(ROOT / "automations" / "search-signals-ingest" / "run.py")
runpy.run_path(sys.argv[0], run_name="__main__")
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_ingest_cli.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Full suite + live smoke**

Run: `python -m pytest -q`
Expected: all tests PASS.
Then a live smoke (Bing + Clarity work today; GSC/GA4 skip until Task 0 Step 4 is done):
Run: `python scripts/ingest_signals.py --client example-hvac-client`
Expected: prints a `[signals] ...` line and writes `clients/example-hvac-client/signals/<today>.json`; any unconfigured source prints `[skip] ...` and is omitted.

- [ ] **Step 6: Commit**

```bash
git add scripts/ingest_signals.py tests/test_ingest_cli.py
git commit -m "feat: ingest_signals CLI + full ingestion pipeline"
```

---

# Plan 2 (architecture only — needs its own writing-plans pass): MAGEO engine

Maps the paper's 4-agent swarm onto this repo. Engines = the surfaces we optimize for: **Google AI Overview, Google organic, Google local pack, ChatGPT, Perplexity** (the last two via the DataForSEO AI-visibility / LLM-scraper endpoints already available).

```
lib/mageo/
  preference.py   # A_pref: reads Signals + AI-visibility samples -> clients/<id>/mageo/preferences/<engine>.json
                  #   profile = {formatting, statistical_density, rhetorical_patterns, citation_style}
  skill_bank.py   # load/append validated tactics; seeds from playbooks/serp_feature_takeover.yaml
                  #   -> clients/<id>/mageo/skill_bank.json  (tactic = {id, engine, trigger, edit, evidence_win_rate})
  planner.py      # A_plan: (engine profile + current page + Signals) -> ranked tactic list from skill bank
  editor.py       # A_edit: parallel-sample N content variants applying the tactic, facts unchanged
  evaluator.py    # A_eval: LLM-as-judge -> {visibility_score, dsv_cf} ; Fidelity Gate rejects if dsv_cf < KAPPA
automations/mageo-optimize/run.py   # orchestrates pref->plan->edit->eval per target page; gated by lib/approvals
```

Key interfaces (lock these in the Plan-2 writing pass):
- `preference.build_profile(client, engine, signals, samples) -> dict`
- `skill_bank.select(profile, page, signals) -> list[tactic]`  (Planner)
- `editor.sample_variants(page, tactic, n=4) -> list[str]`
- `evaluator.judge(original, variant, engine_profile) -> {"visibility": float, "dsv_cf": float}` with `KAPPA = 0.85`
- Fidelity Gate: accept the highest-visibility variant whose `dsv_cf >= KAPPA`; else keep original. Accepted variants flow into the EXISTING approval gate (`lib/approvals`) before publishing.
- Skill distillation (the paper's "experience → skill"): after a tactic wins (ranking/visibility/conversion lift confirmed in a later `Signals` snapshot), bump its `evidence_win_rate` and promote it in the bank.

# Plan 3 (architecture only — needs its own writing-plans pass): Cadence orchestrator + content + CRO loop

Goal-driven by **local conversions/calls** (GBP calls + GA4 conversions), not rankings alone.

```
automations/seo-cadence/
  daily.py     # ingest signals delta -> post_daily_gbp (existing) -> MAGEO micro-edits on 1 priority page
  weekly.py    # re-cluster (keyword-clusters) -> gen content batch (content_template + content-writer + media)
               #   -> MAGEO editor on the week's content cluster -> queue 5-7 GBP posts (gen_gbp_posts, existing)
  monthly.py   # full re-audit -> refresh preference profiles -> skill-bank distillation -> strategy re-plan
lib/cro.py     # turn Clarity rage/dead-click + GA4 conversion + GBP call signals into prioritized CTA/page fixes
```
- Reuses existing pieces: `scripts/gen_gbp_posts.py`, `scripts/post_daily_gbp.py`, `scripts/content_template.py`, `integrations/higgsfield_media`, the gated publishers.
- Scheduling: Windows Task Scheduler wrappers (daily/weekly/monthly) — a `ops/win/` install script (mirror of `ops/launchd/`).
- Conversion attribution: each published asset stamped with a UTM + a `Signals` baseline so the monthly distillation can prove which tactics lifted calls.

---

## Self-review (against the spec)

- **GSC** → Task 5 ✅ · **GBP insights (Zernio)** → Task 7 ✅ · **Bing Webmaster** → Task 2 ✅ · **GA4** → Task 6 ✅ · **Microsoft Clarity (CRO)** → Task 3 ✅ — all five input sources covered, normalized into one `Signals` snapshot (Task 8) by a graceful runner (Task 9) + CLI (Task 10).
- **MAGEO 4 agents (Preference/Planner/Editor/Evaluator) + Skill Bank + Fidelity Gate (κ)** → architected in Plan 2 with concrete file map + interfaces; flagged for its own detailed plan (correct per scope check).
- **Daily/weekly/monthly tactics + all content forms + conversion goal** → architected in Plan 3, reusing the already-built content + publishing pipeline.
- **Placeholder scan:** the only deliberately-deferred value is the Zernio insights endpoint, handled by an explicit live **discovery step** (Task 7 Step 1) rather than a hard-coded guess.
- **Type consistency:** connector return shapes (`query`, `impressions`, `clicks`, `position`, `calls`, `website_clicks`) are used identically in `lib/signals.build_snapshot` and its test.

## Notes / decisions
- GSC + GA4 use a **dedicated** `GSC_GA4_CREDENTIALS` var, never `GOOGLE_APPLICATION_CREDENTIALS`, so the removed media path stays removed. These are read-only analytics, not generation.
- Clarity's 1–3 day window + ~10 req/day quota means the daily cadence (Plan 3) should pull Clarity once/day and cache into the snapshot.
