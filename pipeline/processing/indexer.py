"""Catalog index generator.

Scans the curated catalog root for *--knowledge.md files and the scraper_raw
directory for manufacturer JSON files, then writes CATALOG_INDEX.md to the
repo root summarizing coverage by category and manufacturer.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import NamedTuple

from ..config import CATALOG_ROOT, DATA_DIR

# Sections we look for in knowledge files (heading text -> field key)
KNOWLEDGE_SECTIONS: list[tuple[str, str]] = [
    ("What It Is", "what_it_is"),
    ("Sizing", "sizing_specs"),
    ("Indications", "indications"),
    ("Contraindications", "contraindications"),
    ("Compatible With", "compatible_with"),
    ("Use Notes", "use_notes"),
    ("Also Known As", "also_known_as"),
]

# Fields we look for in scraper JSON records
SCRAPER_FIELDS: list[str] = [
    "what_it_is",
    "sizing_specs",
    "indications",
    "contraindications",
    "compatible_with",
    "use_notes",
    "also_known_as",
]


class DeviceEntry(NamedTuple):
    category: str
    manufacturer: str
    product: str
    status: str          # "curated" | "scraped"
    sections_populated: int
    sections_total: int
    source_pdfs: list[str]  # doc types found: "ifu", "510k", "technique", etc.


def _count_knowledge_sections(text: str) -> tuple[int, int]:
    """Return (populated, total) section count for a knowledge.md file."""
    populated = 0
    total = len(KNOWLEDGE_SECTIONS)
    for heading, _ in KNOWLEDGE_SECTIONS:
        # Look for ## heading (case-insensitive prefix match)
        marker = f"## {heading}"
        idx = text.find(marker)
        if idx == -1:
            # Try case-insensitive search
            lower = text.lower()
            idx = lower.find(marker.lower())
        if idx != -1:
            # Check the 500 chars after the heading for placeholder text
            snippet = text[idx: idx + 500]
            if "[NEEDS CONTENT" not in snippet:
                populated += 1
    return populated, total


def _load_curated() -> list[DeviceEntry]:
    """Scan catalog root for *--knowledge.md files and return DeviceEntry list."""
    entries: list[DeviceEntry] = []
    for f in sorted(CATALOG_ROOT.glob("*--knowledge.md")):
        stem = f.stem  # e.g. "flow-diverter--medtronic--pipeline-flex-shield--knowledge"
        # Remove trailing "--knowledge"
        stem = stem.replace("--knowledge", "")
        parts = stem.split("--")
        if len(parts) < 3:
            continue
        category = parts[0]
        manufacturer = parts[1]
        product = "--".join(parts[2:])
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        populated, total = _count_knowledge_sections(text)

        # Scan for paired source PDFs
        pdf_prefix = f.stem.replace("--knowledge", "")
        source_pdfs = []
        for pdf in sorted(CATALOG_ROOT.glob(f"{pdf_prefix}--*.pdf")):
            doc_type = pdf.stem.split("--")[-1]
            source_pdfs.append(doc_type)

        entries.append(DeviceEntry(
            category=category,
            manufacturer=manufacturer,
            product=product,
            status="curated",
            sections_populated=populated,
            sections_total=total,
            source_pdfs=source_pdfs,
        ))
    return entries


def _make_curated_key(entry: DeviceEntry) -> str:
    return f"{entry.category}--{entry.manufacturer}--{entry.product}"


def _load_scraped(curated_keys: set[str]) -> list[DeviceEntry]:
    """Scan scraper_raw for JSON files and return DeviceEntry list, skipping already-curated."""
    entries: list[DeviceEntry] = []
    scraper_dir = DATA_DIR / "scraper_raw"
    if not scraper_dir.exists():
        return entries

    for mfr_dir in sorted(scraper_dir.iterdir()):
        if not mfr_dir.is_dir():
            continue
        for f in sorted(mfr_dir.glob("*.json")):
            if f.name == "failed_urls.txt":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, OSError):
                continue

            device_name: str = data.get("device_name") or f.stem
            manufacturer: str = data.get("manufacturer") or mfr_dir.name
            category: str = data.get("category_hint") or "unknown"

            # Build a loose key to check against curated
            # Normalize product name to slug form for matching
            product_slug = device_name.lower().strip()
            product_slug = "".join(
                c if c.isalnum() else "-" for c in product_slug
            ).strip("-")
            # Collapse multiple dashes
            import re
            product_slug = re.sub(r"-{2,}", "-", product_slug)

            key = f"{category}--{manufacturer}--{product_slug}"
            if key in curated_keys:
                continue

            # Count populated scraper fields
            populated = 0
            total = len(SCRAPER_FIELDS)
            for field in SCRAPER_FIELDS:
                val = data.get(field)
                if val:
                    # Non-empty string or non-empty list
                    if isinstance(val, list):
                        if val:
                            populated += 1
                    else:
                        if str(val).strip():
                            populated += 1

            entries.append(DeviceEntry(
                category=category,
                manufacturer=manufacturer,
                product=device_name,
                status="scraped",
                sections_populated=populated,
                sections_total=total,
                source_pdfs=[],
            ))
    return entries


def generate_catalog_index() -> Path:
    """Scan the catalog and scraper data, write CATALOG_INDEX.md, return its path."""
    curated = _load_curated()
    curated_keys = {_make_curated_key(e) for e in curated}
    scraped = _load_scraped(curated_keys)

    all_entries = curated + scraped
    total_count = len(all_entries)
    curated_count = len(curated)
    scraped_count = len(scraped)

    # --- Aggregates by category ---
    cat_curated: dict[str, int] = defaultdict(int)
    cat_scraped: dict[str, int] = defaultdict(int)
    for e in curated:
        cat_curated[e.category] += 1
    for e in scraped:
        cat_scraped[e.category] += 1
    all_cats = sorted(set(cat_curated) | set(cat_scraped))

    # --- Aggregates by manufacturer ---
    mfr_curated: dict[str, int] = defaultdict(int)
    mfr_scraped: dict[str, int] = defaultdict(int)
    for e in curated:
        mfr_curated[e.manufacturer] += 1
    for e in scraped:
        mfr_scraped[e.manufacturer] += 1
    all_mfrs = sorted(set(mfr_curated) | set(mfr_scraped))

    # --- Build markdown ---
    lines: list[str] = []

    today = date.today().isoformat()
    lines += [
        f"# Device Catalog Index",
        f"",
        f"Generated: {today}  ",
        f"Total devices: **{total_count}** ({curated_count} curated, {scraped_count} scraped-only)",
        f"",
    ]

    # Coverage summary
    lines += [
        "## Coverage Summary",
        "",
        f"| Source | Count |",
        f"|--------|-------|",
        f"| Curated knowledge files | {curated_count} |",
        f"| Scraped-only (not yet curated) | {scraped_count} |",
        f"| **Total** | **{total_count}** |",
        "",
    ]

    # By category
    lines += [
        "## By Category",
        "",
        "| Category | Curated | Scraped | Total |",
        "|----------|---------|---------|-------|",
    ]
    for cat in all_cats:
        c = cat_curated.get(cat, 0)
        s = cat_scraped.get(cat, 0)
        lines.append(f"| {cat} | {c} | {s} | {c + s} |")
    lines.append("")

    # By manufacturer
    lines += [
        "## By Manufacturer",
        "",
        "| Manufacturer | Curated | Scraped | Total |",
        "|--------------|---------|---------|-------|",
    ]
    for mfr in all_mfrs:
        c = mfr_curated.get(mfr, 0)
        s = mfr_scraped.get(mfr, 0)
        lines.append(f"| {mfr} | {c} | {s} | {c + s} |")
    lines.append("")

    # Full device list grouped by category
    lines += [
        "## Full Device List",
        "",
    ]

    # Group entries by category, curated first then scraped, sorted by product
    by_cat: dict[str, list[DeviceEntry]] = defaultdict(list)
    for e in all_entries:
        by_cat[e.category].append(e)

    for cat in sorted(by_cat):
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| Device | Manufacturer | Status | Sections | Sources |")
        lines.append("|--------|--------------|--------|----------|---------|")
        cat_entries = sorted(by_cat[cat], key=lambda e: (e.status != "curated", e.manufacturer, e.product.lower()))
        for e in cat_entries:
            sources_str = ", ".join(e.source_pdfs) if e.source_pdfs else "--"
            lines.append(
                f"| {e.product} | {e.manufacturer} | {e.status} "
                f"| {e.sections_populated}/{e.sections_total} | {sources_str} |"
            )
        lines.append("")

    output_path = CATALOG_ROOT / "CATALOG_INDEX.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
