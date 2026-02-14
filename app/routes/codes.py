"""Code lookup routes for CPT/HCPCS ↔ ICD-10 mappings."""

import asyncio

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.cms_client import cms_client
from app.utils.code_parser import (
    build_cpt_icd10_mapping,
    unescape_html,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/codes", response_class=HTMLResponse)
async def codes_search_page(request: Request):
    """Render the code lookup search page."""
    return templates.TemplateResponse("codes_search.html", {"request": request})


@router.get("/codes/search", response_class=HTMLResponse)
async def codes_search(
    request: Request,
    code: str = Query(default=""),
    direction: str = Query(default="cpt_to_icd"),
    keyword: str = Query(default=""),
):
    """Search for CPT/HCPCS ↔ ICD-10 code mappings across articles."""
    code = code.strip().upper()
    error = None
    results: list[dict] = []

    if not code:
        return templates.TemplateResponse("codes_results.html", {
            "request": request,
            "results": [],
            "code": code,
            "direction": direction,
            "keyword": keyword,
            "error": "Please enter a code to search.",
        })

    try:
        # Fetch all articles
        article_resp = await cms_client.search_articles(keyword=keyword or None, page=1, page_size=5000)
        articles = article_resp.get("data", [])

        # Filter to billing/coding articles if possible
        billing_articles = [
            a for a in articles
            if "billing" in a.get("title", "").lower()
            or "coding" in a.get("title", "").lower()
        ]
        # Fall back to all if no billing articles match keyword
        search_articles = billing_articles if billing_articles else articles

        # Limit to avoid hammering the API — search first 50 articles
        search_articles = search_articles[:50]

        if direction == "cpt_to_icd":
            results = await _search_cpt_to_icd(code, search_articles)
        else:
            results = await _search_icd_to_cpt(code, search_articles)

    except Exception as e:
        error = f"Error searching codes: {e}"

    return templates.TemplateResponse("codes_results.html", {
        "request": request,
        "results": results,
        "code": code,
        "direction": direction,
        "keyword": keyword,
        "error": error,
    })


async def _search_cpt_to_icd(cpt_code: str, articles: list[dict]) -> list[dict]:
    """Find ICD-10 codes associated with a CPT/HCPCS code."""
    results = []

    # Fetch HCPC codes for all articles concurrently (batched)
    async def check_article(art: dict) -> dict | None:
        aid = str(art.get("document_id", ""))
        ver = str(art.get("document_version", "1"))
        try:
            hcpc_codes = await cms_client.get_article_hcpc_codes(aid, ver)
        except Exception:
            return None

        # Check if this article contains the CPT code
        matching = [h for h in hcpc_codes if h.get("hcpc_code_id", "").strip().upper() == cpt_code]
        if not matching:
            return None

        # Fetch ICD-10 data
        try:
            icd10_covered, icd10_groups = await asyncio.gather(
                cms_client.get_article_icd10_covered(aid, ver),
                cms_client.get_article_icd10_covered_groups(aid, ver),
            )
        except Exception:
            return None

        mapping = build_cpt_icd10_mapping(hcpc_codes, icd10_covered, icd10_groups)
        cpt_info = mapping["by_cpt"].get(cpt_code)
        if not cpt_info or not cpt_info["icd10_codes"]:
            return None

        return {
            "article_id": aid,
            "article_version": ver,
            "article_title": art.get("title", ""),
            "contractor": art.get("contractor_name_type", "").replace("\r\n", " / "),
            "cpt_code": cpt_code,
            "cpt_description": cpt_info["description"],
            "icd10_codes": cpt_info["icd10_codes"],
        }

    tasks = [check_article(a) for a in articles]
    checked = await asyncio.gather(*tasks)
    results = [r for r in checked if r is not None]
    return results


async def _search_icd_to_cpt(icd_code: str, articles: list[dict]) -> list[dict]:
    """Find CPT/HCPCS codes associated with an ICD-10 code."""
    results = []

    async def check_article(art: dict) -> dict | None:
        aid = str(art.get("document_id", ""))
        ver = str(art.get("document_version", "1"))
        try:
            icd10_covered = await cms_client.get_article_icd10_covered(aid, ver)
        except Exception:
            return None

        # Check if this article contains the ICD-10 code
        matching = [i for i in icd10_covered if i.get("icd10_code_id", "").strip().upper() == icd_code]
        if not matching:
            return None

        # Fetch HCPC and group data
        try:
            hcpc_codes, icd10_groups = await asyncio.gather(
                cms_client.get_article_hcpc_codes(aid, ver),
                cms_client.get_article_icd10_covered_groups(aid, ver),
            )
        except Exception:
            return None

        mapping = build_cpt_icd10_mapping(hcpc_codes, icd10_covered, icd10_groups)

        # Find which CPT codes map to this ICD-10 code
        matched_cpts = []
        for cpt_code, cpt_info in mapping["by_cpt"].items():
            if any(ic["code"].upper() == icd_code for ic in cpt_info["icd10_codes"]):
                matched_cpts.append({
                    "code": cpt_code,
                    "description": cpt_info["description"],
                })

        if not matched_cpts:
            return None

        icd_desc = matching[0].get("description", "")

        return {
            "article_id": aid,
            "article_version": ver,
            "article_title": art.get("title", ""),
            "contractor": art.get("contractor_name_type", "").replace("\r\n", " / "),
            "icd10_code": icd_code,
            "icd10_description": icd_desc,
            "cpt_codes": matched_cpts,
        }

    tasks = [check_article(a) for a in articles]
    checked = await asyncio.gather(*tasks)
    results = [r for r in checked if r is not None]
    return results


@router.get("/article/{article_id}/codes", response_class=HTMLResponse)
async def article_codes(
    request: Request,
    article_id: str,
    version: str = Query(default="1"),
):
    """Display all structured codes for a single article."""
    error = None
    article = None
    code_data: dict = {}

    try:
        # First fetch article detail to get the actual version
        article_resp = await cms_client.get_article_detail(article_id, version)
        article_data = article_resp.get("data", {})
        if isinstance(article_data, list) and article_data:
            article = article_data[0]
        else:
            article = article_data

        # Use the actual version from the article detail (API may return latest)
        actual_ver = str(article.get("article_version", version)) if article else version

        # Fetch all code sub-endpoints concurrently with the correct version
        (
            hcpc_codes,
            hcpc_groups,
            icd10_covered,
            icd10_covered_groups,
            icd10_noncovered,
            icd10_noncovered_groups,
            icd10_pcs,
            modifiers,
            bill_codes,
            revenue_codes,
            related_docs,
        ) = await asyncio.gather(
            cms_client.get_article_hcpc_codes(article_id, actual_ver),
            cms_client.get_article_hcpc_code_groups(article_id, actual_ver),
            cms_client.get_article_icd10_covered(article_id, actual_ver),
            cms_client.get_article_icd10_covered_groups(article_id, actual_ver),
            cms_client.get_article_icd10_noncovered(article_id, actual_ver),
            cms_client.get_article_icd10_noncovered_groups(article_id, actual_ver),
            cms_client.get_article_icd10_pcs_codes(article_id, actual_ver),
            cms_client.get_article_hcpc_modifiers(article_id, actual_ver),
            cms_client.get_article_bill_codes(article_id, actual_ver),
            cms_client.get_article_revenue_codes(article_id, actual_ver),
            cms_client.get_article_related_documents(article_id, actual_ver),
        )

        # Build the CPT→ICD-10 mapping
        mapping = build_cpt_icd10_mapping(hcpc_codes, icd10_covered, icd10_covered_groups)

        # Unescape group paragraphs for non-covered groups too
        nc_groups = []
        for g in icd10_noncovered_groups:
            nc_groups.append({
                **g,
                "paragraph": unescape_html(g.get("paragraph", "")),
            })

        code_data = {
            "hcpc_codes": hcpc_codes,
            "hcpc_groups": hcpc_groups,
            "icd10_covered": icd10_covered,
            "icd10_noncovered": icd10_noncovered,
            "icd10_noncovered_groups": nc_groups,
            "icd10_pcs": icd10_pcs,
            "modifiers": modifiers,
            "bill_codes": bill_codes,
            "revenue_codes": revenue_codes,
            "related_docs": related_docs,
            "mapping": mapping,
        }

    except Exception as e:
        error = f"Error fetching article codes: {e}"

    return templates.TemplateResponse("article_codes.html", {
        "request": request,
        "article": article,
        "code_data": code_data,
        "error": error,
    })
