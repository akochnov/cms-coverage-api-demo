"""Detail view routes for CMS Coverage documents."""

import asyncio

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.cms_client import cms_client
from app.utils.code_parser import build_cpt_icd10_mapping, unescape_html

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
    """Display Article detail page with inline code data."""
    error = None
    article = None
    code_data: dict = {}

    try:
        response = await cms_client.get_article_detail(article_id, version)
        article = response.get("data", {})
        if isinstance(article, list) and len(article) > 0:
            article = article[0]

        # Fetch code sub-endpoints using actual version
        if article:
            actual_ver = str(article.get("article_version", version))
            try:
                (
                    hcpc_codes,
                    icd10_covered,
                    icd10_covered_groups,
                    icd10_noncovered,
                    icd10_noncovered_groups,
                    modifiers,
                    related_docs,
                ) = await asyncio.gather(
                    cms_client.get_article_hcpc_codes(article_id, actual_ver),
                    cms_client.get_article_icd10_covered(article_id, actual_ver),
                    cms_client.get_article_icd10_covered_groups(article_id, actual_ver),
                    cms_client.get_article_icd10_noncovered(article_id, actual_ver),
                    cms_client.get_article_icd10_noncovered_groups(article_id, actual_ver),
                    cms_client.get_article_hcpc_modifiers(article_id, actual_ver),
                    cms_client.get_article_related_documents(article_id, actual_ver),
                )

                mapping = build_cpt_icd10_mapping(hcpc_codes, icd10_covered, icd10_covered_groups)

                nc_groups = []
                for g in icd10_noncovered_groups:
                    nc_groups.append({**g, "paragraph": unescape_html(g.get("paragraph", ""))})

                code_data = {
                    "hcpc_codes": hcpc_codes,
                    "icd10_covered": icd10_covered,
                    "icd10_noncovered": icd10_noncovered,
                    "icd10_noncovered_groups": nc_groups,
                    "modifiers": modifiers,
                    "related_docs": related_docs,
                    "mapping": mapping,
                }
            except Exception:
                pass  # Code data is optional; page still renders without it

    except Exception as e:
        error = f"Error fetching Article details: {str(e)}"

    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article,
        "code_data": code_data,
        "error": error
    })
