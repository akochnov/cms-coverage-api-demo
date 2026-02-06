"""Search routes for CMS Coverage."""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.cms_client import cms_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with search form."""
    states = cms_client.get_states()

    try:
        contract_types = await cms_client.get_contract_types()
    except Exception:
        contract_types = []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "states": states,
        "contract_types": contract_types
    })


@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    keyword: str = Query(default=""),
    doc_type: str = Query(default="all"),
    page: int = Query(default=1, ge=1)
):
    """Search for coverage documents."""
    results = {"lcds": [], "ncds": [], "articles": []}
    total_results = 0
    error = None

    # Need at least one search criterion
    if not keyword:
        states = cms_client.get_states()
        return templates.TemplateResponse("results.html", {
            "request": request,
            "results": results,
            "total_results": 0,
            "states": states,
            "filters": {
                "keyword": keyword,
                "doc_type": doc_type
            },
            "page": page,
            "error": "Please enter a keyword to search."
        })

    try:
        # Search based on document type selection
        if doc_type in ("all", "lcd"):
            lcd_response = await cms_client.search_lcds(
                keyword=keyword or None,
                page=page
            )
            results["lcds"] = lcd_response.get("data", [])
            total_results += lcd_response.get("totalResults", len(results["lcds"]))

        if doc_type in ("all", "ncd"):
            ncd_response = await cms_client.search_ncds(
                keyword=keyword or None,
                page=page
            )
            results["ncds"] = ncd_response.get("data", [])
            total_results += ncd_response.get("totalResults", len(results["ncds"]))

        if doc_type in ("all", "article"):
            article_response = await cms_client.search_articles(
                keyword=keyword or None,
                page=page
            )
            results["articles"] = article_response.get("data", [])
            total_results += article_response.get("totalResults", len(results["articles"]))

    except Exception as e:
        error = f"Error searching CMS API: {str(e)}"

    states = cms_client.get_states()

    return templates.TemplateResponse("results.html", {
        "request": request,
        "results": results,
        "total_results": total_results,
        "states": states,
        "filters": {
            "keyword": keyword,
            "doc_type": doc_type
        },
        "page": page,
        "error": error
    })
