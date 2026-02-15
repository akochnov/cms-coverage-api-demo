"""FastAPI application entry point for CMS Coverage Search Tool."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import search, details

app = FastAPI(
    title=settings.APP_TITLE,
    description="Search Medicare coverage policies using the CMS Coverage API",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(search.router)
app.include_router(details.router)


# Register custom Jinja2 filter to unescape CMS HTML entities
def unescape_cms_html(value):
    if not value:
        return ""
    return (value
        .replace('&lt;', '<').replace('&gt;', '>')
        .replace('&sol;', '/').replace('&amp;', '&').replace('&quot;', '"'))


for tpl in (search.templates, details.templates):
    tpl.env.filters["unescape_cms"] = unescape_cms_html


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
