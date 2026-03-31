"""Rate-limited async HTTP client for the openFDA device APIs."""

import asyncio
import httpx
from typing import Any

from .models import FDA510kRecord, FDAPMARecord

BASE_URL = "https://api.fda.gov/device"

# openFDA allows 240 requests/min without API key
REQUEST_DELAY = 0.3  # seconds between requests
MAX_RETRIES = 3
PAGE_LIMIT = 100  # max per openFDA page


class FDAClient:
    """Async client for openFDA device endpoints with rate limiting and retry."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict:
        """Make a rate-limited GET request with retry."""
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{BASE_URL}/{endpoint}.json"

        for attempt in range(MAX_RETRIES):
            await asyncio.sleep(REQUEST_DELAY)
            try:
                resp = await self._client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 404:
                    return {"results": []}
                if resp.status_code in (429, 500, 502, 503):
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
            except httpx.HTTPError:
                if attempt == MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(2 ** attempt)

        return {"results": []}

    async def search_510k(
        self,
        product_code: str,
        limit: int = PAGE_LIMIT,
        skip: int = 0,
    ) -> list[FDA510kRecord]:
        """Search 510(k) clearances by product code."""
        params = {
            "search": f'product_code:"{product_code}"',
            "limit": limit,
            "skip": skip,
        }
        data = await self._get("510k", params)
        results = data.get("results", [])
        return [
            FDA510kRecord(
                k_number=r.get("k_number", ""),
                applicant=r.get("applicant", ""),
                device_name=r.get("device_name", ""),
                product_code=r.get("product_code", ""),
                decision_date=r.get("decision_date", ""),
                decision_code=r.get("decision_code", ""),
                advisory_committee_description=r.get("advisory_committee_description", ""),
                statement_or_summary=r.get("statement_or_summary", ""),
            )
            for r in results
        ]

    async def search_510k_all(self, product_code: str) -> list[FDA510kRecord]:
        """Paginate through all 510(k) results for a product code."""
        all_records = []
        skip = 0
        while skip < 26000:  # openFDA max skip
            batch = await self.search_510k(product_code, limit=PAGE_LIMIT, skip=skip)
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < PAGE_LIMIT:
                break
            skip += PAGE_LIMIT
        return all_records

    async def search_pma(
        self,
        pma_number: str,
        limit: int = PAGE_LIMIT,
        skip: int = 0,
    ) -> list[FDAPMARecord]:
        """Search PMA approvals by PMA number (includes supplements)."""
        params = {
            "search": f'pma_number:"{pma_number}"',
            "limit": limit,
            "skip": skip,
            "sort": "decision_date:desc",
        }
        data = await self._get("pma", params)
        results = data.get("results", [])
        return [
            FDAPMARecord(
                pma_number=r.get("pma_number", ""),
                supplement_number=r.get("supplement_number", ""),
                applicant=r.get("applicant", ""),
                trade_name=r.get("trade_name", ""),
                generic_name=r.get("generic_name", ""),
                product_code=r.get("product_code", ""),
                decision_date=r.get("decision_date", ""),
                decision_code=r.get("decision_code", ""),
            )
            for r in results
        ]

    async def search_pma_all(self, pma_number: str) -> list[FDAPMARecord]:
        """Paginate through all PMA records (base + supplements)."""
        all_records = []
        skip = 0
        while skip < 26000:
            batch = await self.search_pma(pma_number, limit=PAGE_LIMIT, skip=skip)
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < PAGE_LIMIT:
                break
            skip += PAGE_LIMIT
        return all_records

    async def get_total_count(self, endpoint: str, product_code: str) -> int:
        """Get total result count for a product code query."""
        params = {
            "search": f'product_code:"{product_code}"',
            "limit": 1,
        }
        data = await self._get(endpoint, params)
        return data.get("meta", {}).get("results", {}).get("total", 0)
