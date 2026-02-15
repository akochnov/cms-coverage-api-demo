# Project Instructions

## Stack
- Python 3.12, FastAPI, Jinja2, Tailwind CDN, httpx (async)
- Runs on port 8000 via uvicorn
- Virtual env at `./venv/` (exe.dev requires venv, system Python is externally-managed)

## Running
```bash
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure
```
app/
  main.py              # FastAPI app entry point
  config.py            # Settings (API base URL, cache TTLs)
  api/cms_client.py    # Async CMS Coverage API client
  routes/search.py     # Home page + keyword search
  routes/details.py    # LCD, NCD, Article detail views
  utils/code_parser.py # CPT/HCPCS ↔ ICD-10 mapping parser
  templates/           # Jinja2 templates (base, index, results, detail pages)
  static/              # Static assets
```

## CMS API Notes
- Base URL: `https://api.coverage.cms.gov`
- Endpoints use hyphens, not slashes (e.g., `national-coverage-ncd`)
- License token must be Bearer auth header, not a query parameter
- Report endpoints return all data; keyword filtering is done client-side
- Article sub-endpoint responses are cached in-memory (1-hour TTL)
