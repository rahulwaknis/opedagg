# Op-Ed Network

## Deploying this app

This repository runs a Flask web app with a static frontend and a SQLite datastore.

### Files
- `api.py` - Flask application and static file server
- `rss_ingest.py` - RSS feed fetcher that populates `opinion_articles.db`
- `run_api.py` - local startup script
- `static/` - frontend assets
- `requirements.txt` - Python dependencies
- `Procfile` - production startup command for hosts like Heroku/Render/Railway

### Recommended deployment setup

1. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

2. Start the web app with a production WSGI server
   ```bash
   gunicorn api:app --bind 0.0.0.0:$PORT
   ```

3. Schedule RSS ingestion through GitHub Actions
   - `.github/workflows/refresh.yml` runs `python rss_ingest.py` every 6 hours
   - If `opinion_articles.db` changes, the workflow commits and pushes the new DB
   - Render auto-deploys that commit, so the web service starts with the latest data

### Rebuild behavior

- `rss_ingest.py` now deletes `opinion_articles.db` before recreating the database.
- Every refresh rebuilds the app data from scratch, so the site only serves the latest crawled feed data.
- This keeps the deployment lightweight and avoids growing history inside SQLite.

### Notes on SQLite

- The app writes data to `opinion_articles.db` in the same folder.
- Many cloud hosts treat local disk as ephemeral, so choose a host with persistent storage or migrate to a managed database later.
   - For Render, keep `opinion_articles.db` committed if GitHub is the deployment source of truth.
   - A Render scheduled job runs in its own environment and should not be relied on to update the web service's local SQLite file.

## Lightweight cloud deployment options

### 1. Render
- Simple app deploy from GitHub
- Use `requirements.txt` and `Procfile`
- Let GitHub Actions refresh and commit `opinion_articles.db`
- Good for low configuration

#### Render manifest

If you want a repeatable Render deploy, use `render.yaml` in the repo root.
It defines the web service. The RSS refresh workflow lives in `.github/workflows/refresh.yml`.

### 2. Railway
- Easy Python service deploy
- Supports `requirements.txt`
- Add a cron / scheduled job for ingestion

### 3. PythonAnywhere
- Very light setup for Flask apps
- Good for small projects
- Has built-in scheduled tasks for `rss_ingest.py`

### 4. Fly.io
- Can run without Docker using `fly launch`
- Slightly more config, but still lightweight

### 5. Azure App Service
- Good if you already use Azure
- Supports Python apps and startup commands

## Do we need containerization?

No, not if you use a simple Python app host like Render, Railway, or PythonAnywhere.

Containerization is optional and useful when:
- you want exact environment control
- you want to deploy to a host that prefers Docker
- you want to bundle dependencies and startup in one image

For a very light configuration, deploy directly with `requirements.txt` and `Procfile` instead of Docker.

## Best minimal path

- Push the repo to GitHub
- Connect it to Render/Railway
- Use `requirements.txt`
- Use `Procfile`
- Enable the GitHub Actions RSS refresh workflow
- Verify the app can read/write `opinion_articles.db`
