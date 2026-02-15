# CMS Coverage Search

A web application for searching and browsing Medicare coverage policies from the [CMS Coverage API](https://api.coverage.cms.gov).

## Features

- **Keyword search** across LCDs (Local Coverage Determinations), NCDs (National Coverage Determinations), and billing Articles
- **Document detail views** for LCDs, NCDs, and Articles with full policy content
- **CPT/HCPCS and ICD-10 code tables** displayed inline on Article detail pages, showing covered/non-covered diagnosis codes and HCPCS modifiers
- **Code mapping** linking CPT/HCPCS procedure codes to their associated ICD-10 diagnosis codes via group-level parsing

## Tech Stack

- **Backend:** Python 3.12, FastAPI, httpx (async HTTP)
- **Frontend:** Jinja2 templates, Tailwind CSS (CDN)
- **API:** CMS Coverage API v1 (`api.coverage.cms.gov`)

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The app will be available at `http://localhost:8000`.

## Docker

```bash
docker build -t cms-coverage .
docker run -p 8000:8000 cms-coverage
```

## Project Structure

```
app/
  main.py              # FastAPI app, route registration, Jinja2 filters
  config.py            # Settings (API base URL, cache TTLs)
  api/
    cms_client.py      # Async CMS Coverage API client with token management
  routes/
    search.py          # Home page and keyword search endpoint
    details.py         # LCD, NCD, and Article detail views
  utils/
    code_parser.py     # CPT/HCPCS ↔ ICD-10 mapping parser
  templates/           # Jinja2 HTML templates
  static/              # Static assets
```

## API Notes

The app consumes the public [CMS Coverage API](https://api.coverage.cms.gov). No API key is required -- the app automatically obtains a license token from the `/v1/metadata/license-agreement` endpoint and uses it as a Bearer token for detail endpoints. Tokens and metadata are cached in-memory with a 1-hour TTL.
