"""Tier 1B: FDA UDI, MAUDE, and Recall API queries.

Uses the same openFDA REST API pattern as the existing FDAClient.
Synchronous (supplementary queries, not bulk discovery).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/device"
REQUEST_DELAY = 0.3
TIMEOUT = 30
MAX_RETRIES = 3

UDI_OUTPUT_DIR = EXTRACTED_DIR / "fda_structured"
SAFETY_OUTPUT_DIR = EXTRACTED_DIR / "fda_safety"


def _get(endpoint: str, params: dict) -> dict:
    """Synchronous GET with retry logic matching FDAClient pattern."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_DELAY)
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.get(url, params=params)
            if resp.status_code == 404:
                return {"results": []}
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            time.sleep(2 ** attempt)
    return {"results": []}


def query_udi(brand_name: str, company_name: str) -> dict | None:
    """Query openFDA UDI endpoint for device characteristics."""
    search = f'brand_name:"{brand_name}" AND company_name:"{company_name}"'
    data = _get("udi.json", {"search": search, "limit": 5})
    results = data.get("results", [])
    if not results:
        data = _get("udi.json", {"search": f'brand_name:"{brand_name}"', "limit": 5})
        results = data.get("results", [])
    if not results:
        return None

    rec = results[0]
    fields: dict = {}

    desc = rec.get("device_description")
    if desc:
        fields["what_it_is"] = desc

    parts = []
    if rec.get("catalog_number"):
        parts.append(f"Catalog: {rec['catalog_number']}")
    if rec.get("version_or_model_number"):
        parts.append(f"Model: {rec['version_or_model_number']}")
    if parts:
        fields["sizing_specs"] = "; ".join(parts)

    notes = []
    mri = rec.get("mri_safety")
    if mri:
        notes.append(f"MRI: {mri}")
    sterilization = rec.get("sterilization", {})
    if sterilization.get("is_sterile"):
        method = sterilization.get("sterilization_methods", "")
        notes.append(f"Sterilized: {method}" if method else "Pre-sterilized")
    if rec.get("is_single_use"):
        notes.append("Single-use")
    if notes:
        fields["use_notes"] = ". ".join(notes)

    aliases = []
    if rec.get("brand_name"):
        aliases.append(rec["brand_name"])
    for term in rec.get("gmdn_terms", []):
        if term.get("name"):
            aliases.append(term["name"])
    if aliases:
        fields["also_known_as"] = aliases

    if not fields:
        return None

    return {
        "source": "fda_udi",
        "brand_name": brand_name,
        "extraction_method": "fda_udi_api",
        "fields": fields,
        "confidence": {k: 0.85 for k in fields},
    }


def query_maude(product_code: str, brand_name: str | None = None) -> dict | None:
    """Query MAUDE adverse events. Returns safety summary."""
    search = f'product_code:"{product_code}"'
    if brand_name:
        search += f' AND brand_name:"{brand_name}"'
    data = _get("event.json", {"search": search, "count": "event_type.exact"})
    counts = {r["term"]: r["count"] for r in data.get("results", [])}
    if not counts:
        return None
    return {
        "source": "fda_maude",
        "product_code": product_code,
        "event_counts": counts,
        "total_events": sum(counts.values()),
    }


def query_recalls(product_code: str, firm_name: str | None = None) -> list[dict]:
    """Query FDA recall endpoint. Returns list of recall summaries."""
    search = f'product_code:"{product_code}"'
    if firm_name:
        search += f' AND recalling_firm:"{firm_name}"'
    data = _get("recall.json", {"search": search, "limit": 20})
    return [
        {
            "reason": r.get("reason_for_recall", ""),
            "status": r.get("status", ""),
            "date": r.get("event_date_initiated", ""),
            "product_description": r.get("product_description", ""),
        }
        for r in data.get("results", [])
    ]


def extract_all_structured(
    devices: list[dict],
) -> tuple[list, list, list]:
    """Run UDI, MAUDE, and Recall queries for a list of devices."""
    UDI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAFETY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    udi_results, maude_results, recall_results = [], [], []

    for device in devices:
        name = device.get("device_name", "")
        mfr = device.get("manufacturer", "")
        code = device.get("product_code", "")
        stem = device.get("filename_stem", name)

        logger.info("  FDA APIs: %s", name)

        udi = query_udi(name, mfr)
        if udi:
            (UDI_OUTPUT_DIR / f"{stem}.json").write_text(
                json.dumps(udi, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            udi_results.append(udi)

        if code:
            maude = query_maude(code, name)
            if maude:
                (SAFETY_OUTPUT_DIR / f"{stem}-maude.json").write_text(
                    json.dumps(maude, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                maude_results.append(maude)

            recalls = query_recalls(code, mfr)
            if recalls:
                (SAFETY_OUTPUT_DIR / f"{stem}-recalls.json").write_text(
                    json.dumps(recalls, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                recall_results.append({"stem": stem, "recalls": recalls})

    logger.info(
        "FDA: %d UDI, %d MAUDE, %d recall",
        len(udi_results), len(maude_results), len(recall_results),
    )
    return udi_results, maude_results, recall_results
