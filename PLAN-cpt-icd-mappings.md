# Implementation Plan: CPT/HCPCS to ICD-10 Code Mappings

## Goal
Add structured CPT/HCPCS ↔ ICD-10 code lookup to the CMS Coverage Search Tool, sourced from Article detail sub-endpoints in the CMS Coverage API.

---

## Phase 1: API Client — Article Code Sub-Endpoints

**File:** `app/api/cms_client.py`

Add methods to `CMSCoverageClient` for each article sub-endpoint:

```python
async def get_article_hcpc_codes(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_hcpc_code_groups(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_icd10_covered(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_icd10_covered_groups(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_icd10_noncovered(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_icd10_noncovered_groups(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_icd10_pcs_codes(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_hcpc_modifiers(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_bill_codes(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_revenue_codes(self, article_id: str, version: str = "1") -> list[dict]
async def get_article_related_documents(self, article_id: str, version: str = "1") -> list[dict]
```

All endpoints:
- Base path: `/v1/data/article/<sub-endpoint>`
- Query params: `articleid`, `ver`
- Require Bearer token (use existing `get_license_token()`)
- Return `response.json()["data"]`

### Endpoint Reference

| Sub-endpoint | Key fields returned |
|---|---|
| `hcpc-code` | `hcpc_code_id`, `hcpc_code_group`, `long_description`, `short_description` |
| `hcpc-code-group` | `hcpc_code_group`, `paragraph` (HTML) |
| `icd10-covered` | `icd10_code_id`, `icd10_covered_group`, `description`, `asterisk` |
| `icd10-covered-group` | `icd10_covered_group`, `paragraph` (HTML), `icd10_covered_ast` |
| `icd10-noncovered` | `icd10_code_id`, `icd10_noncovered_group`, `description` |
| `icd10-noncovered-group` | `icd10_noncovered_group`, `paragraph` |
| `icd10-pcs-code` | `icd10_pcs_code_id`, `icd10_pcs_code_group`, `description` |
| `hcpc-modifier` | `hcpc_modifier_code_id`, `hcpc_modifier_group`, `description` |
| `bill-codes` | `bill_code_id`, `description` |
| `revenue-code` | `revenue_code_id`, `description` |
| `related-documents` | `r_lcd_id`, `r_lcd_version` |

---

## Phase 2: Group-to-CPT Paragraph Parser

**File:** `app/utils/code_parser.py` (new)

The `icd10-covered-group` `paragraph` field contains HTML like:
> "CPT codes 81162-81167, 81212, 81215 are considered medically necessary for the following ICD-10-CM codes:"

Write a parser to extract CPT codes from these paragraphs:

```python
def extract_cpt_codes_from_paragraph(paragraph_html: str) -> list[str]:
    """
    Parse HTML paragraph text to extract referenced CPT/HCPCS codes.
    Handles patterns like:
    - "CPT code 81235"
    - "CPT codes 81162-81167, 81212, 81215"
    - "HCPCS code J9271"
    - "CPT/HCPCS codes 99201-99215"
    Returns list of individual code strings (ranges expanded).
    """

def build_cpt_icd10_mapping(
    hcpc_codes: list[dict],
    icd10_covered: list[dict],
    icd10_covered_groups: list[dict]
) -> dict:
    """
    Combine data from three sub-endpoints into a structured mapping:
    {
        "cpt_code": {
            "code": "81235",
            "description": "EGFR gene analysis",
            "icd10_codes": [
                {"code": "C34.10", "description": "Malignant neoplasm..."},
                ...
            ]
        },
        ...
    }
    Falls back to grouping all ICD-10 codes under all CPTs if paragraph
    parsing fails for a group.
    """
```

### Parsing Strategy
1. Unescape HTML entities in `paragraph`
2. Regex for patterns: `(?:CPT|HCPCS|CPT/HCPCS)\s+codes?\s+([\d,\s\-]+)`
3. Expand ranges (e.g., `81162-81167` → `81162, 81163, 81164, 81165, 81166, 81167`)
4. For each `icd10_covered_group` number, associate extracted CPTs with all `icd10_covered` entries sharing that group number
5. If no CPT codes found in paragraph text, associate that group's ICD-10 codes with ALL article HCPCS codes (safe fallback)

---

## Phase 3: Code Lookup Route

**File:** `app/routes/codes.py` (new)

### Routes

#### `GET /codes` — Code Search Page
- Search form with:
  - Code input (CPT/HCPCS or ICD-10)
  - Code type radio: "CPT/HCPCS → ICD-10" or "ICD-10 → CPT/HCPCS"
  - Optional keyword filter (searches article titles)
- Template: `codes_search.html`

#### `GET /codes/search` — Code Search Results
- Query params: `code`, `direction` (cpt_to_icd | icd_to_cpt), `keyword`
- Logic:
  1. Fetch all articles from report endpoint (cached)
  2. Filter to "Billing and Coding" articles (keyword match on title if provided)
  3. For matching articles, fetch `hcpc-code` sub-endpoint
  4. If direction=cpt_to_icd: find articles containing the queried HCPCS code, then fetch `icd10-covered` + `icd10-covered-group` for those articles
  5. If direction=icd_to_cpt: fetch `icd10-covered` for articles, find which contain the queried ICD-10 code, return the article's HCPCS codes
  6. Build and return the mapping using parser from Phase 2
- Template: `codes_results.html`

#### `GET /article/{id}/codes` — Article Code Detail Page
- Fetch all code sub-endpoints for a single article
- Display organized tables: HCPCS codes, covered ICD-10, non-covered ICD-10, PCS codes, modifiers, bill types, revenue codes
- Show the CPT↔ICD-10 mapping with group context
- Template: `article_codes.html`

### Caching Strategy
- Cache article report list (already done, reuse existing)
- Cache individual article code sub-endpoint responses with 1-hour TTL (same as token)
- Use in-memory dict keyed by `(article_id, sub_endpoint)`

---

## Phase 4: Enhanced Article Detail Page

**File:** `app/templates/article_detail.html` (modify existing)

- Add a "Codes" tab/section to the existing article detail page
- Show structured code tables instead of (or alongside) raw HTML content
- Add link to full `/article/{id}/codes` view

---

## Phase 5: Templates

### `app/templates/codes_search.html`
- Search form with code input, direction toggle, optional keyword
- Quick examples: "Enter a CPT code like 93880 or an ICD-10 code like G45.0"

### `app/templates/codes_results.html`
- Results grouped by article (LCD context)
- For each match:
  - Article title + link to parent LCD
  - Contractor/jurisdiction info
  - Table of mapped codes (CPT → ICD-10 or ICD-10 → CPT)
  - Coverage status (covered vs non-covered)

### `app/templates/article_codes.html`
- Full code breakdown for a single article
- Sections: HCPCS Codes, Covered ICD-10 Codes, Non-Covered ICD-10 Codes, PCS Codes, Modifiers, Bill Types, Revenue Codes
- Group headers showing coverage context from `paragraph` fields
- Sortable/filterable tables

---

## Phase 6: Navigation Updates

**Files:** `app/templates/base.html`, `app/templates/index.html`

- Add "Code Lookup" link to main navigation
- Add code search as a quick-link section on the home page
- Register new router in `app/main.py`

---

## File Summary

| File | Action |
|---|---|
| `app/api/cms_client.py` | Add 11 new methods for article sub-endpoints + caching |
| `app/utils/__init__.py` | New empty init |
| `app/utils/code_parser.py` | New — paragraph parser + mapping builder |
| `app/routes/codes.py` | New — 3 routes for code lookup |
| `app/templates/codes_search.html` | New — search form |
| `app/templates/codes_results.html` | New — search results |
| `app/templates/article_codes.html` | New — article code detail |
| `app/templates/article_detail.html` | Modify — add codes section |
| `app/templates/base.html` | Modify — add nav link |
| `app/templates/index.html` | Modify — add quick link |
| `app/main.py` | Modify — register codes router |

---

## Known Limitations

1. **CPT↔ICD group linkage requires paragraph parsing** — the API has no structured field for this; mapping quality depends on regex accuracy
2. **No reverse-lookup API** — searching "all articles containing CPT code X" requires scanning all articles' HCPCS code lists
3. **Rate limiting** — fetching codes for many articles in parallel may need throttling
4. **CPT code ranges** — range expansion (81162-81167) assumes sequential numeric codes, which is true for CPT but may need validation
5. **Version handling** — articles have versions; need to decide whether to always fetch latest or respect specific versions
6. **~2,169 articles total** — initial full scan is expensive; consider background indexing or lazy loading

---

## Implementation Order

1. Phase 1 (API client methods) — foundation, no UI needed yet
2. Phase 2 (parser) — can unit test independently
3. Phase 3 (routes) + Phase 5 (templates) — together, delivers the feature
4. Phase 4 (article detail enhancement) — polish
5. Phase 6 (navigation) — final integration
