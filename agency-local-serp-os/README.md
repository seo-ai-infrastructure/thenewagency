# Agency OS — Autonomous Local SEO Ecosystem

Agency OS is a multi-tenant SaaS platform that merges Local SEO tracking (DataForSEO), an interactive Kanban Command Center, and Autonomous Browser Agents (CloakBrowser) into a single scalable cloud infrastructure. 

It tracks Mobile SERP estates, identifies pipeline vulnerabilities, automatically generates hijack playbooks, and executes them headlessly in the cloud using persistent AI agents.

## 🚀 Architecture Overview
The system has been modernized from a local filesystem script into a full-stack SaaS:

- **Frontend:** HTML/JS Dashboard with ApexCharts (Command Center, AI Search Intel, Kanban Approvals) served by Vercel.
- **Backend API:** Serverless Python Flask API (`api/index.py`) hosted on Vercel Edge.
- **Database:** Supabase (PostgreSQL) for multi-tenant data storage and JWT Authentication.
- **Task Queue:** Celery + Redis (`worker.py`) for decoupling long-running agent workflows from the Vercel API.
- **Agent Orchestrator:** CloakBrowser Runner (`automations/cloakbrowser-runner/run.py`), typically deployed via Docker, polling for JSON work orders to execute UI actions.

## 🔑 Environment Variables
Your `.env` 
```

### The CloakBrowser Agent Pool
When the worker processes an automation, it drops a JSON payload into `automations/cloakbrowser-runner/inbox/`. 
Your Dockerized CloakBrowser Manager continuously watches this folder. When a file drops, it wakes up the specific persistent browser profile (e.g. `example-hvac-client-cb-agent`) and executes the task autonomously (e.g. Hijacking a PAA on Reddit).

## 📊 Core Subsystems
- **DataForSEO Tracks:** Local Finder, Organic Mobile, and AI Mode. 
- **PAA Velocity Trap (`lib/paa_velocity.py`):** Scans historical search data to automatically detect rising competitor keywords and issues "hijack" work orders.
- **Deep Dive "God Mode":** An interactive UI (`mission-control.js`) that visualizes Proximity Decay, Revenue Pipeline loss, and Reputation Shock (CTR exponential decay).

## 📂 Repository Layout
```text
api/index.py                        # Vercel Serverless Entrypoint (Flask)
apps/kanban-board/static/           # SaaS Frontend (HTML/JS/CSS)
automations/cloakbrowser-runner/    # Agent Orchestrator & Poller
clients/<id>/browser/               # Client profiles.yaml & workflows.yaml
lib/db.py                           # Supabase Postgres bridge
lib/tasks.py                        # Celery Application & Task definitions
scripts/migrate_to_supabase.py      # Migration tool from local JSON to Supabase
worker.py                           # Celery Worker Entrypoint
```


## Lanes (integrations/dataforseo/endpoints.yaml)
- Local Finder  /v3/serp/google/local_finder/live/advanced   (map-pack)
- Organic mobile /v3/serp/google/organic/live/advanced        (full feature stack + AIO)
- AI Mode       /v3/serp/google/ai_mode/live/advanced         (English-only, ~2x cost, monthly)

## What was fixed/upgraded vs the prior spec
2. AI Mode absence handled (English-only / location-limited) — recorded, not errored.
3. AI Overview vs AI Mode disambiguated by LANE (both arrive as an ai_overview item).
4. Coordinate format standardized (lat,lng,zoom) across lanes.
5. competition.yaml (structured) drives the 5-class ownership classifier.
6. AI citations captured: cited_sources + cited_competitors (who's winning the AI surface).
7. Cost controls: per-lane cadence + Standard (queued) method in endpoints.yaml;
   AI Mode monthly; minimal paid params to control cost. Raw responses archived to raw/ so you never re-pay to re-parse.
8. Schedule-collector idempotency via state/last_run.txt (not inbox/work-order).
9. Scoring: THREE separate lane scores (never blended), estate_share = ownership-weighted
   share of SERP slots, weighted by ownership class AND keyword lead_value.
10. AI surfaces scored by CITATION (influenced), not block ownership — being cited
    among several sources is not owning the slot.

## Run
```bash
pip install -r requirements.txt
python run_all_dry.py            # tracker (fixtures) -> estate scoring, end to end
# live: set DATAFORSEO_LOGIN/PASSWORD in env, fill clients/<id>/facts, drop --dry-run
```

## 🛠 Deployment & Execution

### 1. The Cloud SaaS (Vercel)
To deploy the dashboard and API to the public internet:
```bash
npx vercel --prod
```
Once deployed, users MUST log in via the Supabase Auth modal. The Vercel API validates the JWT token before serving any client data.

### 2. The Cloud Worker (Celery/Redis)
Vercel serverless functions timeout after 10-60 seconds. Therefore, when a client clicks "Approve" on a task, Vercel pushes a job to Redis. 
Run the background worker on a separate server (or locally) to process these AI tasks:
```bash
python worker.py
```

### 3. The CloakBrowser Agent Pool
When the worker processes an automation, it drops a JSON payload into `automations/cloakbrowser-runner/inbox/`. 
Your Dockerized CloakBrowser Manager continuously watches this folder. When a file drops, it wakes up the specific persistent browser profile (e.g. `example-hvac-client-cb-agent`) and executes the task autonomously (e.g. Hijacking a PAA on Reddit).

## 📊 Core Subsystems
- **DataForSEO Tracks:** Local Finder, Organic Mobile, and AI Mode. 
- **PAA Velocity Trap (`lib/paa_velocity.py`):** Scans historical search data to automatically detect rising competitor keywords and issues "hijack" work orders.
- **Deep Dive "God Mode":** An interactive UI (`mission-control.js`) that visualizes Proximity Decay, Revenue Pipeline loss, and Reputation Shock (CTR exponential decay).

## 📂 Repository Layout
```text
api/index.py                        # Vercel Serverless Entrypoint (Flask)
apps/kanban-board/static/           # SaaS Frontend (HTML/JS/CSS)
automations/cloakbrowser-runner/    # Agent Orchestrator & Poller
clients/<id>/browser/               # Client profiles.yaml & workflows.yaml
lib/db.py                           # Supabase Postgres bridge
lib/tasks.py                        # Celery Application & Task definitions
scripts/migrate_to_supabase.py      # Migration tool from local JSON to Supabase
worker.py                           # Celery Worker Entrypoint
```
