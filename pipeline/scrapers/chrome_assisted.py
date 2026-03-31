"""Utilities for Chrome-assisted scraping sessions.

This module is NOT a scraper class. It provides I/O helpers that Claude calls
(via the Bash tool) during a Chrome MCP scraping session to write ScrapedProduct
JSON files and manage checkpointing.

Usage from Claude Code (Bash tool):
    python -c "
    from pipeline.scrapers.chrome_assisted import save_chrome_product
    save_chrome_product({
        'device_name': 'Pipeline Flex',
        'manufacturer': 'medtronic',
        'category_hint': 'flow-diverter',
        'what_it_is': '...',
        ...
    })
    "
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from slugify import slugify

from ..config import DATA_DIR


SCRAPER_RAW_DIR = DATA_DIR / "scraper_raw"


def save_chrome_product(data: dict, manufacturer: str | None = None) -> str:
    """Save a Chrome-scraped product as JSON.

    Args:
        data: Dict with ScrapedProduct fields plus optional 'chrome_api_endpoint'.
        manufacturer: Override manufacturer slug. If None, uses data['manufacturer'].

    Returns:
        Path to the written JSON file.
    """
    mfr = manufacturer or data.get("manufacturer", "unknown")
    device_name = data.get("device_name", "unnamed")

    out_dir = SCRAPER_RAW_DIR / mfr
    out_dir.mkdir(parents=True, exist_ok=True)

    fname = slugify(device_name, separator="-") + ".json"

    # Strip raw_html to keep files small
    output = {k: v for k, v in data.items() if k != "raw_html"}

    path = out_dir / fname
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def load_existing_stems(manufacturer: str) -> set[str]:
    """Return slugified device names already scraped for this manufacturer.

    Use this at session start to skip products that already have JSON files.
    """
    out_dir = SCRAPER_RAW_DIR / manufacturer
    if not out_dir.exists():
        return set()
    return {
        f.stem
        for f in out_dir.glob("*.json")
        if f.name not in ("failed_urls.txt", "discovered_apis.json")
    }


def save_discovered_apis(manufacturer: str, endpoints: list[dict]) -> str:
    """Log API endpoints discovered during a Chrome session.

    Args:
        manufacturer: Manufacturer slug.
        endpoints: List of dicts with 'url', 'method', 'description' keys.

    Returns:
        Path to the written JSON file.
    """
    out_dir = SCRAPER_RAW_DIR / manufacturer
    out_dir.mkdir(parents=True, exist_ok=True)

    path = out_dir / "discovered_apis.json"

    # Merge with existing discoveries
    existing: list[dict] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    seen_urls = {e.get("url") for e in existing}
    for ep in endpoints:
        if ep.get("url") not in seen_urls:
            existing.append(ep)
            seen_urls.add(ep.get("url"))

    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def print_session_status(manufacturer: str) -> None:
    """Print how many products have been scraped for a manufacturer."""
    stems = load_existing_stems(manufacturer)
    print(f"{manufacturer}: {len(stems)} products scraped")
    for stem in sorted(stems):
        print(f"  {stem}")


# CLI entry point for quick checks
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.scrapers.chrome_assisted <manufacturer>")
        print("       python -m pipeline.scrapers.chrome_assisted <manufacturer> save '<json_data>'")
        sys.exit(1)

    mfr = sys.argv[1]

    if len(sys.argv) >= 4 and sys.argv[2] == "save":
        data = json.loads(sys.argv[3])
        path = save_chrome_product(data, manufacturer=mfr)
        print(f"Saved: {path}")
    else:
        print_session_status(mfr)
