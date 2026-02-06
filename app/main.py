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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
