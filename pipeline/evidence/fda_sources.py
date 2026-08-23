"""Direct FDA source clients for raw safety and regulatory records."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from .models import SourceRecord, SourceType, utc_now_iso

OPENFDA_BASE = "https://api.fda.gov/device"


class OpenFDAEvidenceClient:
    def __init__(self, api_key: str | None = None, timeout: float = 30.0):
        self.api_key = api_key
        self.timeout = timeout

    def search_endpoint(
        self,
        endpoint: str,
        search: str,
        limit: int = 20,
        device_family: str = "",
    ) -> list[SourceRecord]:
        params = {"search": search, "limit": limit}
        if self.api_key:
            params["api_key"] = self.api_key
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{OPENFDA_BASE}/{endpoint}.json", params=params)
            if response.status_code in {400, 404}:
                return []
            response.raise_for_status()
            payload = response.json()
        retrieved_at = utc_now_iso()
        records: list[SourceRecord] = []
        for idx, raw in enumerate(payload.get("results", []), start=1):
            source_id = _fda_source_id(endpoint, raw, idx)
            records.append(
                SourceRecord(
                    source_id=source_id,
                    source_type=SourceType.FDA,
                    title=_fda_title(endpoint, raw, source_id),
                    retrieved_at=retrieved_at,
                    device_family=device_family,
                    source_url=f"https://api.fda.gov/device/{endpoint}.json?search={quote(search)}",
                    query_used=search,
                    raw=raw,
                )
            )
        return records

    def maude(self, search: str, limit: int = 20, device_family: str = "") -> list[SourceRecord]:
        return self.search_endpoint("event", search, limit=limit, device_family=device_family)

    def recalls(self, search: str, limit: int = 20, device_family: str = "") -> list[SourceRecord]:
        return self.search_endpoint("recall", search, limit=limit, device_family=device_family)

    def enforcement(self, search: str, limit: int = 20, device_family: str = "") -> list[SourceRecord]:
        return self.search_endpoint("enforcement", search, limit=limit, device_family=device_family)

    def udi(self, search: str, limit: int = 20, device_family: str = "") -> list[SourceRecord]:
        return self.search_endpoint("udi", search, limit=limit, device_family=device_family)

    def classification(self, search: str, limit: int = 20, device_family: str = "") -> list[SourceRecord]:
        return self.search_endpoint("classification", search, limit=limit, device_family=device_family)


def _fda_source_id(endpoint: str, raw: dict, idx: int) -> str:
    for key in [
        "mdr_report_key",
        "res_event_number",
        "recall_number",
        "event_id",
        "k_number",
        "pma_number",
        "udi_di",
        "product_code",
    ]:
        value = raw.get(key)
        if value:
            return f"fda:{endpoint}:{value}"
    return f"fda:{endpoint}:record-{idx}"


def _fda_title(endpoint: str, raw: dict, fallback: str) -> str:
    device = raw.get("device")
    device_brand = ""
    if isinstance(device, list) and device:
        device_brand = device[0].get("brand_name", "")
    openfda_name = ""
    if isinstance(raw.get("openfda"), dict):
        names = raw["openfda"].get("device_name", [])
        if names:
            openfda_name = names[0]
    fields = [
        device_brand,
        raw.get("product_description"),
        raw.get("device_name"),
        raw.get("brand_name"),
        openfda_name,
    ]
    title = next((str(field).strip() for field in fields if field), "")
    return title or fallback.replace("fda:", "FDA ").replace(":", " ")
