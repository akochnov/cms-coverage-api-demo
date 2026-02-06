"""Detail view routes for CMS Coverage documents."""

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.cms_client import cms_client

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/lcd/{lcd_id}", response_class=HTMLResponse)
async def lcd_detail(
    request: Request,
    lcd_id: str,
    version: str = Query(default="1")
):
    """Display LCD detail page."""
    error = None
    lcd = None

    try:
        response = await cms_client.get_lcd_detail(lcd_id, version)
        lcd = response.get("data", {})
        if isinstance(lcd, list) and len(lcd) > 0:
            lcd = lcd[0]
    except Exception as e:
        error = f"Error fetching LCD details: {str(e)}"

    return templates.TemplateResponse("lcd_detail.html", {
        "request": request,
        "lcd": lcd,
        "error": error
    })


@router.get("/ncd/{ncd_id}", response_class=HTMLResponse)
async def ncd_detail(
    request: Request,
    ncd_id: str,
    version: str = Query(default="1")
):
    """Display NCD detail page."""
    error = None
    ncd = None

    try:
        response = await cms_client.get_ncd_detail(ncd_id, version)
        ncd = response.get("data", {})
        if isinstance(ncd, list) and len(ncd) > 0:
            ncd = ncd[0]
    except Exception as e:
        error = f"Error fetching NCD details: {str(e)}"

    return templates.TemplateResponse("ncd_detail.html", {
        "request": request,
        "ncd": ncd,
        "error": error
    })


@router.get("/article/{article_id}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: str,
    version: str = Query(default="1")
):
    """Display Article detail page."""
    error = None
    article = None

    try:
        response = await cms_client.get_article_detail(article_id, version)
        article = response.get("data", {})
        if isinstance(article, list) and len(article) > 0:
            article = article[0]
    except Exception as e:
        error = f"Error fetching Article details: {str(e)}"

    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article,
        "error": error
    })
