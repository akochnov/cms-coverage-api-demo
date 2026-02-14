"""CMS Coverage API client wrapper."""

import time
from typing import Any

import httpx

from app.config import settings


# US States for filtering (CMS API doesn't have a state metadata endpoint)
US_STATES = [
    {"code": "AL", "name": "Alabama"}, {"code": "AK", "name": "Alaska"},
    {"code": "AZ", "name": "Arizona"}, {"code": "AR", "name": "Arkansas"},
    {"code": "CA", "name": "California"}, {"code": "CO", "name": "Colorado"},
    {"code": "CT", "name": "Connecticut"}, {"code": "DE", "name": "Delaware"},
    {"code": "DC", "name": "District of Columbia"}, {"code": "FL", "name": "Florida"},
    {"code": "GA", "name": "Georgia"}, {"code": "HI", "name": "Hawaii"},
    {"code": "ID", "name": "Idaho"}, {"code": "IL", "name": "Illinois"},
    {"code": "IN", "name": "Indiana"}, {"code": "IA", "name": "Iowa"},
    {"code": "KS", "name": "Kansas"}, {"code": "KY", "name": "Kentucky"},
    {"code": "LA", "name": "Louisiana"}, {"code": "ME", "name": "Maine"},
    {"code": "MD", "name": "Maryland"}, {"code": "MA", "name": "Massachusetts"},
    {"code": "MI", "name": "Michigan"}, {"code": "MN", "name": "Minnesota"},
    {"code": "MS", "name": "Mississippi"}, {"code": "MO", "name": "Missouri"},
    {"code": "MT", "name": "Montana"}, {"code": "NE", "name": "Nebraska"},
    {"code": "NV", "name": "Nevada"}, {"code": "NH", "name": "New Hampshire"},
    {"code": "NJ", "name": "New Jersey"}, {"code": "NM", "name": "New Mexico"},
    {"code": "NY", "name": "New York"}, {"code": "NC", "name": "North Carolina"},
    {"code": "ND", "name": "North Dakota"}, {"code": "OH", "name": "Ohio"},
    {"code": "OK", "name": "Oklahoma"}, {"code": "OR", "name": "Oregon"},
    {"code": "PA", "name": "Pennsylvania"}, {"code": "PR", "name": "Puerto Rico"},
    {"code": "RI", "name": "Rhode Island"}, {"code": "SC", "name": "South Carolina"},
    {"code": "SD", "name": "South Dakota"}, {"code": "TN", "name": "Tennessee"},
    {"code": "TX", "name": "Texas"}, {"code": "UT", "name": "Utah"},
    {"code": "VT", "name": "Vermont"}, {"code": "VA", "name": "Virginia"},
    {"code": "VI", "name": "Virgin Islands"}, {"code": "WA", "name": "Washington"},
    {"code": "WV", "name": "West Virginia"}, {"code": "WI", "name": "Wisconsin"},
    {"code": "WY", "name": "Wyoming"}
]


class CMSCoverageClient:
    """Async client for the CMS Coverage API."""

    def __init__(self):
        self.base_url = settings.CMS_API_BASE_URL
        self._license_token: str | None = None
        self._token_expires_at: float = 0
        self._contract_types_cache: list[dict] | None = None
        self._contract_types_cached_at: float = 0
        self._code_cache: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}
        self._CODE_CACHE_TTL = 3600  # 1 hour

    def _get_client(self, token: str | None = None) -> httpx.AsyncClient:
        """Create an async HTTP client."""
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers=headers
        )

    async def get_license_token(self) -> str:
        """Get or refresh the license agreement token."""
        current_time = time.time()

        if self._license_token and current_time < self._token_expires_at:
            return self._license_token

        async with self._get_client() as client:
            response = await client.get("/v1/metadata/license-agreement")
            response.raise_for_status()
            data = response.json()

            # Token is in data[0].Token
            token_data = data.get("data", [])
            if token_data and len(token_data) > 0:
                self._license_token = token_data[0].get("Token", "")
            else:
                self._license_token = ""

            self._token_expires_at = current_time + settings.LICENSE_TOKEN_TTL
            return self._license_token

    def get_states(self) -> list[dict]:
        """Get list of US states (hardcoded since API doesn't provide this)."""
        return US_STATES

    async def get_contract_types(self) -> list[dict]:
        """Get list of contract types from metadata."""
        current_time = time.time()

        if self._contract_types_cache and (current_time - self._contract_types_cached_at) < settings.METADATA_CACHE_TTL:
            return self._contract_types_cache

        async with self._get_client() as client:
            response = await client.get("/v1/metadata/contract-type")
            response.raise_for_status()
            data = response.json()

            self._contract_types_cache = data.get("data", [])
            self._contract_types_cached_at = current_time

            return self._contract_types_cache

    async def search_lcds(
        self,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 50
    ) -> dict[str, Any]:
        """Search for Local Coverage Determinations."""
        params: dict[str, Any] = {}

        if keyword:
            params["keyword"] = keyword

        async with self._get_client() as client:
            response = await client.get("/v1/reports/local-coverage-final-lcds", params=params)
            response.raise_for_status()
            result = response.json()

            # Filter locally if keyword is provided (basic title matching)
            data = result.get("data", [])
            if keyword:
                keyword_lower = keyword.lower()
                data = [item for item in data if keyword_lower in item.get("title", "").lower()]

            # Apply pagination
            start = (page - 1) * page_size
            end = start + page_size
            paginated_data = data[start:end]

            return {
                "data": paginated_data,
                "totalResults": len(data),
                "page": page,
                "pageSize": page_size
            }

    async def get_lcd_detail(self, lcd_id: str, version: str = "1") -> dict[str, Any]:
        """Get detailed information for a specific LCD."""
        token = await self.get_license_token()

        async with self._get_client(token) as client:
            response = await client.get(
                "/v1/data/lcd",
                params={"lcdid": lcd_id, "lcdver": version}
            )
            response.raise_for_status()
            return response.json()

    async def search_ncds(
        self,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 50
    ) -> dict[str, Any]:
        """Search for National Coverage Determinations."""
        params: dict[str, Any] = {}

        async with self._get_client() as client:
            response = await client.get("/v1/reports/national-coverage-ncd", params=params)
            response.raise_for_status()
            result = response.json()

            # Filter locally if keyword is provided
            data = result.get("data", [])
            if keyword:
                keyword_lower = keyword.lower()
                data = [item for item in data if keyword_lower in item.get("title", "").lower()]

            # Apply pagination
            start = (page - 1) * page_size
            end = start + page_size
            paginated_data = data[start:end]

            return {
                "data": paginated_data,
                "totalResults": len(data),
                "page": page,
                "pageSize": page_size
            }

    async def get_ncd_detail(self, ncd_id: str, version: str = "1") -> dict[str, Any]:
        """Get detailed information for a specific NCD."""
        async with self._get_client() as client:
            response = await client.get(
                "/v1/data/ncd",
                params={"ncdid": ncd_id, "ncdver": version}
            )
            response.raise_for_status()
            return response.json()

    async def search_articles(
        self,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 50
    ) -> dict[str, Any]:
        """Search for Articles."""
        params: dict[str, Any] = {}

        async with self._get_client() as client:
            response = await client.get("/v1/reports/local-coverage-articles", params=params)
            response.raise_for_status()
            result = response.json()

            # Filter locally if keyword is provided
            data = result.get("data", [])
            if keyword:
                keyword_lower = keyword.lower()
                data = [item for item in data if keyword_lower in item.get("title", "").lower()]

            # Apply pagination
            start = (page - 1) * page_size
            end = start + page_size
            paginated_data = data[start:end]

            return {
                "data": paginated_data,
                "totalResults": len(data),
                "page": page,
                "pageSize": page_size
            }

    async def get_article_detail(self, article_id: str, version: str = "1") -> dict[str, Any]:
        """Get detailed information for a specific Article."""
        token = await self.get_license_token()

        async with self._get_client(token) as client:
            response = await client.get(
                "/v1/data/article",
                params={"articleid": article_id, "articlever": version}
            )
            response.raise_for_status()
            return response.json()

    async def _get_article_sub(self, sub_endpoint: str, article_id: str, version: str = "1") -> list[dict]:
        """Fetch an article sub-endpoint with caching."""
        cache_key = (sub_endpoint, article_id, version)
        now = time.time()
        cached = self._code_cache.get(cache_key)
        if cached and (now - cached[0]) < self._CODE_CACHE_TTL:
            return cached[1]

        token = await self.get_license_token()
        async with self._get_client(token) as client:
            response = await client.get(
                f"/v1/data/article/{sub_endpoint}",
                params={"articleid": article_id, "ver": version}
            )
            response.raise_for_status()
            data = response.json().get("data", [])

        self._code_cache[cache_key] = (now, data)
        return data

    async def get_article_hcpc_codes(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("hcpc-code", article_id, version)

    async def get_article_hcpc_code_groups(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("hcpc-code-group", article_id, version)

    async def get_article_icd10_covered(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("icd10-covered", article_id, version)

    async def get_article_icd10_covered_groups(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("icd10-covered-group", article_id, version)

    async def get_article_icd10_noncovered(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("icd10-noncovered", article_id, version)

    async def get_article_icd10_noncovered_groups(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("icd10-noncovered-group", article_id, version)

    async def get_article_icd10_pcs_codes(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("icd10-pcs-code", article_id, version)

    async def get_article_hcpc_modifiers(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("hcpc-modifier", article_id, version)

    async def get_article_bill_codes(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("bill-codes", article_id, version)

    async def get_article_revenue_codes(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("revenue-code", article_id, version)

    async def get_article_related_documents(self, article_id: str, version: str = "1") -> list[dict]:
        return await self._get_article_sub("related-documents", article_id, version)


# Global client instance
cms_client = CMSCoverageClient()
