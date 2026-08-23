"""ClinicalTrials.gov API v2 client."""

from __future__ import annotations

import time

import httpx

from .models import SourceHealth, SourceRecord, SourceType, utc_now_iso

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_429_RETRY_DELAYS = (2.0, 5.0, 10.0)  # seconds between retries on 429


class ClinicalTrialsClient:
    def __init__(self, timeout: float = 30.0, request_delay: float = 1.0):
        self.timeout = timeout
        self.request_delay = request_delay  # seconds between per-device calls

    def search(
        self,
        query: str,
        limit: int = 20,
        device_family: str = "",
        health_log: list[SourceHealth] | None = None,
    ) -> list[SourceRecord]:
        """Search ClinicalTrials.gov using the intervention field (query.intr).

        Falls back to full-text (query.term) if the intervention query returns
        no results, so broad acronym-only terms still get a chance.
        """
        checked_at = utc_now_iso()
        records, err_status = self._fetch(query, limit, device_family, field="query.intr")
        fallback_used = False
        if not records:
            records, err_status2 = self._fetch(query, limit, device_family, field="query.term")
            fallback_used = bool(records)
            # Prefer the fallback's error status if intr had none
            if err_status is None:
                err_status = err_status2
        if err_status is not None:
            # Request failed — distinguish from genuine empty
            status = "connection_error" if err_status == 0 else "http_error"
            _log(health_log, "clinicaltrials", device_family, query, checked_at,
                 status, 0, err_status if err_status != 0 else None)
        else:
            status = "ok" if records else "empty"
            _log(health_log, "clinicaltrials", device_family, query, checked_at,
                 status, len(records), fallback_used=fallback_used)
        return records

    def _fetch(
        self,
        query: str,
        limit: int,
        device_family: str,
        field: str,
    ) -> tuple[list[SourceRecord], int | None]:
        """Return (records, http_status_if_error).

        http_status is set only when the request failed (no records due to an
        HTTP error or connection problem). None means the request succeeded.
        """
        params = {
            field: query,
            "pageSize": min(limit, 1000),
            "format": "json",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = self._get_with_retry(client, params)
                if response.status_code in {400, 403, 404}:
                    return [], response.status_code
                if response.status_code == 429:
                    return [], 429  # retries exhausted
                response.raise_for_status()
                payload = response.json()
        except httpx.RequestError:
            return [], 0  # 0 = connection-level failure (no HTTP status)
        except httpx.HTTPStatusError as exc:
            return [], exc.response.status_code

        retrieved_at = utc_now_iso()
        records: list[SourceRecord] = []
        for study in payload.get("studies", []):
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            status_mod = protocol.get("statusModule", {})
            nct_id = identification.get("nctId", "")
            title = identification.get("briefTitle") or identification.get("officialTitle") or nct_id
            records.append(
                SourceRecord(
                    source_id=f"clinicaltrials:{nct_id}",
                    source_type=SourceType.CLINICALTRIALS,
                    title=title,
                    retrieved_at=retrieved_at,
                    device_family=device_family,
                    source_url=f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
                    query_used=query,
                    raw={
                        "nct_id": nct_id,
                        "title": title,
                        "overall_status": status_mod.get("overallStatus", ""),
                        "search_field": field,
                        "raw": study,
                    },
                )
            )
        return records, None  # None = no error; success


    def _get_with_retry(self, client: httpx.Client, params: dict) -> httpx.Response:
        """GET with exponential backoff on 429 responses."""
        response = client.get(
            BASE_URL,
            params=params,
            headers={"User-Agent": "device-catalog-evidence/0.1"},
        )
        for delay in _429_RETRY_DELAYS:
            if response.status_code != 429:
                break
            time.sleep(delay)
            response = client.get(
                BASE_URL,
                params=params,
                headers={"User-Agent": "device-catalog-evidence/0.1"},
            )
        return response


def build_trials_query(terms: list[str]) -> str:
    """Build a quoted OR query from a list of search terms."""
    return " OR ".join(f'"{term}"' for term in terms)


def _log(
    health_log: list[SourceHealth] | None,
    source_type: str,
    device_family: str,
    query_used: str,
    checked_at: str,
    status: str,
    record_count: int,
    http_status: int | None = None,
    error_detail: str = "",
    fallback_used: bool = False,
) -> None:
    if health_log is None:
        return
    health_log.append(
        SourceHealth(
            source_type=source_type,
            device_family=device_family,
            query_used=query_used,
            checked_at=checked_at,
            status=status,
            record_count=record_count,
            http_status=http_status,
            error_detail=error_detail,
            fallback_used=fallback_used,
        )
    )
