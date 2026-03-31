"""Tier 1C: Endovascular Today Device Guide scraper.

Scrapes structured comparison tables from evtoday.com/device-guide/us/.
Public, no auth required. Rate-limited to 3s between requests.
"""

from __future__ import annotations

import json
import logging
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "evtoday"
BASE_URL = "https://evtoday.com/device-guide/us"
REQUEST_DELAY = 3

CATEGORIES = {
    "cerebral-coils": "embolic-coil",
    "neurovascular-liquid-embolics": "liquid-embolic",
    "flow-diverters": "flow-diverter",
    "cerebral-stents": "intracranial-stent",
    "mechanical-thrombectomythrombolysis-neurovascular": "thrombectomy",
    "thrombus-aspiration-devices": "aspiration",
    "microcatheters-4": "microcatheter",
    "specialty-balloons-neuro": "balloon-catheter",
    "intrasaccular-flow-disruptor-1": "intrasaccular",
    "guiding-catheters": "guiding-catheter",
}


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_thead = False
        self.in_tbody = False
        self.in_th = False
        self.in_td = False
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "th":
            self.in_th = True
            self.current_cell = ""
        elif tag == "td":
            self.in_td = True
            self.current_cell = ""
        elif tag == "tr" and self.in_tbody:
            self.current_row = []

    def handle_endtag(self, tag):
        if tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "th":
            self.in_th = False
            self.headers.append(self.current_cell.strip())
        elif tag == "td":
            self.in_td = False
            self.current_row.append(self.current_cell.strip())
        elif tag == "tr" and self.in_tbody and self.current_row:
            self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_th or self.in_td:
            self.current_cell += data


def scrape_category(slug: str, category: str) -> dict | None:
    """Scrape a single EVToday category page. Returns parsed data or None."""
    url = f"{BASE_URL}/{slug}"
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        if resp.url.path.rstrip("/").endswith("/us"):
            return None
    except httpx.HTTPError:
        return None

    parser = _TableParser()
    parser.feed(resp.text)
    if not parser.rows:
        return None

    devices = []
    for row in parser.rows:
        entry = {}
        for i, header in enumerate(parser.headers):
            if i < len(row):
                entry[header] = row[i]
        devices.append(entry)

    return {
        "category": category,
        "source_url": url,
        "headers": parser.headers,
        "devices": devices,
    }


def scrape_all_categories() -> dict[str, int]:
    """Scrape all neuro-relevant EVToday categories. Save JSON, return slug->count."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for slug, category in CATEGORIES.items():
        logger.info("  EVToday: %s", slug)
        data = scrape_category(slug, category)
        if data is None:
            counts[slug] = 0
            continue
        (OUTPUT_DIR / f"{slug}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        counts[slug] = len(data["devices"])
        time.sleep(REQUEST_DELAY)
    logger.info("EVToday: %d devices total", sum(counts.values()))
    return counts
