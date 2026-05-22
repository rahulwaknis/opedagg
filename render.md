Render deployment guide for Op-Ed Network

Overview

This file describes how to deploy the Op-Ed Network Flask app to Render using the `render.yaml` manifest included in the repo. The app uses SQLite (`opinion_articles.db`) and GitHub Actions rebuilds and commits the DB on a schedule.

Pre-requisites

- Git repository with the project pushed to GitHub
- A Render account (https://render.com)
- Optional: Render CLI installed (https://render.com/docs/cli)

Files of interest

- `render.yaml` — Render manifest defining the web service
- `Procfile` — start command for gunicorn (used by many hosts)
- `requirements.txt` — Python dependencies
- `rss_ingest.py` — feed fetcher; deletes the DB before rebuilding
- `.github/workflows/refresh.yml` — scheduled GitHub Actions workflow that rebuilds and commits `opinion_articles.db`
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
3. Render will read `render.yaml` and create the web service:
   - Web service uses `gunicorn api:app --bind 0.0.0.0:$PORT`
   - Note: do not manually override `PORT` in Render; the platform injects it automatically.
4. Enable auto-deploy so Render deploys when GitHub Actions commits a refreshed DB.
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

- DB persistence: `opinion_articles.db` is committed to GitHub and deployed with the app. Local writes on Render can be lost on redeploy.
- Rebuild behavior: The GitHub Actions refresh workflow deletes and recreates `opinion_articles.db` before each ingest, then commits the new file if it changed.
- Render scheduled jobs: Do not use a Render scheduled job for this SQLite-in-repo setup. Scheduled jobs run separately from the web service and will not reliably update the DB file served by the web app.
- Single-instance assumption: This manifest and approach assume a single web instance; scaling to multiple instances will not share the local SQLite DB.
- Secrets & environment variables: If you add API keys or secrets, put them into Render environment variables via the dashboard — do not check them into Git.

Verifying the scheduled refresh

- In GitHub, open Actions → `RSS Refresh` and inspect the latest run.
- Confirm the run created a commit named `Refresh RSS article database` when feed data changed.
- In Render, confirm auto-deploy started from that new commit.
- Hit `/api/health` and `/api/current-topics` on the deployed URL to confirm the app serves data.

Next steps you might want me to do

- Add a small healthcheck endpoint or improve `/api/health` output (already exists)
- Add a tiny `Makefile` with `deploy` and `refresh` helpers
- Replace SQLite with Postgres and update the `render.yaml` to include a managed Postgres instance


