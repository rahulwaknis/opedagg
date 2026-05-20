Render deployment guide for Op-Ed Network

Overview

This file describes how to deploy the Op-Ed Network Flask app to Render using the `render.yaml` manifest included in the repo. The app uses SQLite (`opinion_articles.db`) and `rss_ingest.py` rebuilds the DB on every run (it deletes the DB before recreating it).

Pre-requisites

- Git repository with the project pushed to GitHub
- A Render account (https://render.com)
- Optional: Render CLI installed (https://render.com/docs/cli)

Files of interest

- `render.yaml` — Render manifest defining the web service and the scheduled job
- `Procfile` — start command for gunicorn (used by many hosts)
- `requirements.txt` — Python dependencies
- `rss_ingest.py` — feed fetcher; runs as a scheduled job and now deletes the DB before rebuilding
- `api.py` — Flask app that serves the SPA and API endpoints

Quick local test

Install deps and test the server locally:

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
# or: source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# run the local API for quick testing
python run_api.py

# or run with gunicorn (if installed)
gunicorn api:app --bind 127.0.0.1:5000

# run the RSS ingest script to populate opinion_articles.db
python rss_ingest.py
```

Deploying on Render (GUI)

1. Push the repo to GitHub and ensure `render.yaml` is at the repository root.
2. Sign in to Render and choose "New" → "From Render.yaml" (or "Create a new service" and point it to your repo).
3. Render will read `render.yaml` and create the web service and scheduled job:
   - Web service uses `gunicorn api:app --bind 0.0.0.0:$PORT`
   - Cron job runs `python rss_ingest.py` every hour (see `render.yaml`)
   - Note: do not manually override `PORT` in Render; the platform injects it automatically.
4. Enable auto-deploy if desired.
5. Add a custom domain in Render if you want a branded URL.

Deploying on Render (CLI)

If you prefer CLI, see Render docs. Common steps:

```bash
# login
render login

# create service from yaml (GUI is recommended for first-time)
# The Render CLI supports linking a repo and deploying; consult Render docs for exact commands.
```

Notes and caveats

- DB persistence: `opinion_articles.db` is stored on the instance disk. For a single small instance this is fine. If you scale to multiple instances or need durable storage beyond redeploys, migrate to Postgres or another managed DB.
- Rebuild behavior: The scheduled job deletes and recreates `opinion_articles.db` before each ingest. That keeps the instance lightweight but removes history.
- Single-instance assumption: This manifest and approach assume a single web instance; scaling to multiple instances will not share the local SQLite DB.
- Secrets & environment variables: If you add API keys or secrets, put them into Render environment variables via the dashboard — do not check them into Git.

Verifying the scheduled job

- After deployment, open the Render dashboard → Cron / Jobs → `rss-refresh` and inspect recent runs.
- Check the web service logs to ensure the ingest completed and `opinion_articles.db` was created.
- Hit `/api/health` and `/api/current-topics` on the deployed URL to confirm the app serves data.

Next steps you might want me to do

- Add a small healthcheck endpoint or improve `/api/health` output (already exists)
- Add a tiny `Makefile` with `deploy` and `refresh` helpers
- Replace SQLite with Postgres and update the `render.yaml` to include a managed Postgres instance


