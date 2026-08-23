"""AccessGUDID API client.

Verified endpoint: https://accessgudid.nlm.nih.gov/devices/search.json
Response shape:
  {
    "search_results": {
      "number_results": "...",
      "result": [
        {
          "deviceIdentifier": "<uuid>",
          "brandName": "...",
          "companyName": "...",
          "modelNumber": "...",
          "gmdnTerms": [{"termName": "...", ...}],
          "ID": [{"deviceId": "...", "type": "Primary"}]
        },
        ...
      ]
    }
  }
"""

from __future__ import annotations

import httpx

from .models import SourceHealth, SourceRecord, SourceType, utc_now_iso

BASE_URL = "https://accessgudid.nlm.nih.gov/devices/search.json"
DEVICE_URL = "https://accessgudid.nlm.nih.gov/devices/"


class AccessGUDIDClient:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def search(
        self,
        query: str,
        limit: int = 20,
        device_family: str = "",
        health_log: list[SourceHealth] | None = None,
    ) -> list[SourceRecord]:
        params = {"query": query, "pageNumber": 1, "pageSize": min(limit, 100)}
        checked_at = utc_now_iso()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    BASE_URL,
                    params=params,
                    headers={"User-Agent": "device-catalog-evidence/0.1"},
                )
                if response.status_code in {403, 404}:
                    _log(health_log, "accessgudid", device_family, query, checked_at,
                         "http_error", 0, response.status_code)
                    return []
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            _log(health_log, "accessgudid", device_family, query, checked_at,
                 "http_error", 0, exc.response.status_code, str(exc))
            return []
        except httpx.RequestError as exc:
            _log(health_log, "accessgudid", device_family, query, checked_at,
                 "connection_error", 0, None, str(exc))
            return []

        retrieved_at = utc_now_iso()
        records: list[SourceRecord] = []

        result_list = payload.get("search_results", {}).get("result", [])
        if payload and not isinstance(result_list, list):
            _log(health_log, "accessgudid", device_family, query, checked_at,
                 "unexpected_response", 0,
                 error_detail=f"unrecognized payload keys: {list(payload.keys())[:5]}")
            return []

        for raw in result_list:
            device_uuid = raw.get("deviceIdentifier", "")
            # Primary DI from the ID list
            id_list = raw.get("ID", [])
            primary_di = next(
                (entry["deviceId"] for entry in id_list if entry.get("type") == "Primary"),
                id_list[0]["deviceId"] if id_list else "",
            )
            source_id = f"accessgudid:{primary_di or device_uuid}"
            brand = raw.get("brandName") or ""
            company = raw.get("companyName") or ""
            title = f"{brand} ({company})" if brand and company else brand or source_id
            source_url = f"{DEVICE_URL}{device_uuid}" if device_uuid else BASE_URL
            records.append(
                SourceRecord(
                    source_id=source_id,
                    source_type=SourceType.ACCESSGUDID,
                    title=title,
                    retrieved_at=retrieved_at,
                    device_family=device_family,
                    source_url=source_url,
                    query_used=query,
                    raw=raw,
                )
            )

        status = "ok" if records else "empty"
        _log(health_log, "accessgudid", device_family, query, checked_at, status, len(records))
        return records


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
        )
    )
