# Agency OS — Local Deployment Guide

While the system is built to scale on Vercel and Supabase, you can run the entire OS locally for testing, development, and executing your automated workflows without deploying to the cloud.

## 🛠 Prerequisites

1. **Python 3.12+**
2. **Node.js 20+** (Required for Vercel CLI local dev)
3. **Redis** (Local or Cloud connection string via `redis.env`)
4. **CloakBrowser Manager** (Docker image running locally)

---

## 🚀 1. Local Environment Setup

First, install all Python dependencies:
```bash
pip install -r requirements.txt
pip install celery redis flask python-dotenv
```

Ensure your `.env` file contains your essential API keys:
```env
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-anon-jwt-key>
REDIS_URL=redis://127.0.0.1:6379/0  # Or your cloud Redis string
```

---

## 🖥 2. Start the Local API & Dashboard

You can run the old monolithic server using `python apps/kanban-board/server.py --port 8787`, **OR** you can run the modern Vercel serverless environment locally using the Vercel CLI.

To run the exact Vercel architecture locally:
```bash
npx vercel dev
```
*This will spin up a local development server (usually on `http://localhost:3000`) that mimics the Vercel Edge network, routing frontend requests to the static folder and `/api/*` requests to your Python Flask backend.*

---

## ⚙️ 3. Start the Background Task Worker

When you click "Approve" on the dashboard, the API pushes the task to your Redis queue. You need a worker running locally to process those jobs.

Open a **new terminal window** and run:
```bash
python worker.py
```
*Leave this window open. It will silently wait for commands from the dashboard and dispatch them.*

---

## 🤖 4. Start the CloakBrowser Agent

The background worker drops automation instructions (JSON files) into the `automations/cloakbrowser-runner/inbox/` directory.

To process those files and launch the actual browser agents, ensure your Dockerized **CloakBrowser Manager** is running and mounted to your repository folder.

Alternatively, to run the script loop manually on your host machine:
```bash
python automations/cloakbrowser-runner/run.py --client example-hvac-client
```

---

## 🎯 Full Local Workflow

1. Open `http://localhost:3000` (from `npx vercel dev`).
2. Log in using a mock JWT or a real Supabase user account.
3. Use the **God Mode Simulators** on the Deep Dive tab to visualize revenue pipeline.
4. Go to the Kanban Board and click **"Approve"** on a Draft work order.
5. Watch the `worker.py` terminal successfully pick up the task from Redis and drop the JSON file into the inbox.
6. Watch your CloakBrowser container wake up and autonomously execute the task in the browser!
