"""Extract product rows from retained Endovascular Today Device Guide PDFs.

The guides are manufacturer-submitted comparison tables published by Endovascular
Today. The live pages are scraped by ``evtoday_scraper``; this module instead reads
the PDF exports retained under ``sources/trade_journal/endovascular-today/<YYYY-MM>/``
so every row carries a hashable artifact, a PDF page, and a row index. That is what
lets a row be cited as a *secondary* observation with a locator a reader can reopen.

Nothing here decides trust. Rows are written to
``pipeline/data/extracted/evt_guides/<slug>.rows.jsonl`` and consumed by
``pipeline.knowledge_v2.secondary_candidates``, which labels every observation
``secondary_curated_catalog`` and never promotes it.

Usage:
    python -m pipeline.extraction.evt_guide_pdf            # all retained guides
    python -m pipeline.extraction.evt_guide_pdf cerebral-coils
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import guard only
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

from ..config import CATALOG_ROOT, EXTRACTED_DIR

SOURCE_ROOT = CATALOG_ROOT / "sources" / "trade_journal" / "endovascular-today"
OUTPUT_DIR = EXTRACTED_DIR / "evt_guides"

# Guide slug (from the PDF filename, region prefix stripped) -> catalog category.
# Mirrors and extends evtoday_scraper.CATEGORIES. Guides covering peripheral as well
# as neuro devices are admitted; row-level ``neuro_relevance`` decides what downstream
# steps keep.
GUIDE_CATEGORIES: dict[str, str] = {
    "cerebral-coils": "embolic-coil",
    "neurovascular-liquid-embolics": "liquid-embolic",
    "cerebral-stents": "intracranial-stent",
    "mechanical-thrombectomythrombolysis-neurovascular": "thrombectomy",
    "mechanical-thrombectomythrombolysis": "thrombectomy",
    "microcatheters-4": "microcatheter",
    "microcatheters-1": "microcatheter",
    "specialty-balloons-neuro": "balloon-catheter",
    "intrasaccular-flow-disruptor-1": "intrasaccular",
    "guiding-catheters": "guide-catheter",
    "hydrophilic-guidewires": "guidewire",
    "carotid-artery-stenting-systems": "carotid-stent",
    "self-expanding-stents": "peripheral-stent",
    "venous-stents": "venous-stent",
    "embolic-particlesbeads-2": "embolic-particle",
}

# Guides whose every row is neurovascular by construction. The generic microcatheter,
# guiding-catheter, and guidewire guides mix peripheral products (e.g. oncology
# microcatheters), so their rows are classified from their own text and otherwise
# left "unknown" - a discovery-only candidate is cheap, a wrong "neuro" tag is not.
NEURO_GUIDES = {
    "cerebral-coils",
    "neurovascular-liquid-embolics",
    "cerebral-stents",
    "mechanical-thrombectomythrombolysis-neurovascular",
    "specialty-balloons-neuro",
    "intrasaccular-flow-disruptor-1",
    "carotid-artery-stenting-systems",
}

# Printed header -> normalized field name. Unknown headers pass through as a slug.
HEADER_MAP: dict[str, str] = {
    "company name": "company",
    "product name": "product",
    "type of catheter construction": "construction",
    "proximal size (f)": "proximal_od_fr",
    "middle size (f)": "middle_od_fr",
    "distal size (f)": "distal_od_fr",
    "proximal od (f)": "proximal_od_fr",
    "distal od (f)": "distal_od_fr",
    "size (f)": "od_fr",
    "catheter working length (cm)": "working_length_cm",
    "working length (cm)": "working_length_cm",
    "length (cm)": "length_cm",
    "catheter endhole diameter id (inch)": "inner_diameter_in",
    "internal diameter (inch)": "inner_diameter_in",
    "recommended guidewire size (inch)": "guidewire_max_in",
    "guidewire compatibility (inch)": "guidewire_max_in",
    "recommended guide catheter size (inch)": "guide_catheter_min_in",
    "sheath compatibility (f)": "sheath_compatibility_fr",
    "introducer size (f)": "introducer_size_fr",
    "radiopaque tip (yes/no)": "radiopaque_tip",
    "radiopaque tip (yes/ no)": "radiopaque_tip",
    "hydrophilic coating (yes/no)": "hydrophilic_coating",
    "hydrophilic coating (yes/ no)": "hydrophilic_coating",
    "hydrophilic coated": "hydrophilic_coating",
    "materials used": "materials",
    "material used": "materials",
    "stent material": "materials",
    "composition": "materials",
    "coil type": "coil_type",
    "method of detachment": "detachment",
    "us fda indicated use": "indicated_use",
    "comments": "comments",
    "type": "type",
    "mode of operation": "mode_of_operation",
    "stent diameters (mm)": "stent_diameter_mm",
    "stent diameter (mm)": "stent_diameter_mm",
    "stent lengths (mm)": "stent_length_mm",
    "stent length (mm)": "stent_length_mm",
    "straight stent diameters (mm)": "stent_diameter_mm",
    "straight stent lengths (mm)": "stent_length_mm",
    "tapered stent diameters (proximal/ distal) (mm)": "tapered_stent_diameter_mm",
    "tapered stent lengths (mm)": "tapered_stent_length_mm",
    "device diameter (mm)": "device_diameter_mm",
    "device height (mm)": "device_height_mm",
    "balloon diameters (mm)": "balloon_diameter_mm",
    "balloon lengths (mm)": "balloon_length_mm",
    "tip length (mm)": "tip_length_mm",
    "delivery system length (cm)": "delivery_system_length_cm",
    "delivery system": "delivery_system",
    "diameter (inch)": "wire_diameter_in",
    "tip type": "tip_type",
    "cell design": "cell_design",
    "embolic protection device": "embolic_protection_device",
    "position": "position",
    "color coding": "color_coding",
}

DASH_VALUES = {"", "-", "–", "—", "n/a", "na", "none"}
NEURO_TERMS = re.compile(
    r"\b(neuro|intracranial|cerebral|cerebrovascular|aneurysm|carotid|vertebral|basilar|"
    r"middle cerebral|internal carotid|ischemic stroke|large vessel occlusion|cerebrospinal)",
    re.IGNORECASE,
)
PERIPHERAL_TERMS = re.compile(
    r"\b(peripheral|femoral|iliac|popliteal|pulmonary|coronary|dialysis|venous|biliary|"
    r"renal|mesenteric|deep vein|lower extremit)",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace(" ", " ")
    return re.sub(r"[ \t]*\n[ \t]*", " ", text).strip()


def is_blank(value: str) -> bool:
    return clean_cell(value).casefold() in DASH_VALUES


def normalize_header(header: str) -> str:
    key = re.sub(r"\s+", " ", clean_cell(header)).casefold()
    if key in HEADER_MAP:
        return HEADER_MAP[key]
    return re.sub(r"[^a-z0-9]+", "_", key).strip("_") or "column"


def guide_slug(pdf_path: Path) -> tuple[str, str]:
    """Return (region, slug) from a filename like EVT-US-cerebral-coils.pdf."""
    match = re.match(r"EVT-(US|EUROPEAN)-(.+)\.pdf$", pdf_path.name, re.IGNORECASE)
    if not match:
        raise ValueError(f"unrecognized EVT guide filename: {pdf_path.name}")
    return match.group(1).upper(), match.group(2)


def guide_title(doc: "fitz.Document") -> str:
    first = doc[0].get_text().splitlines() if doc.page_count else []
    for line in first:
        if line.strip().startswith("Endovascular Today"):
            return clean_cell(line)
    return "Endovascular Today Device Guide"


def neuro_relevance(slug: str, row: dict[str, str]) -> str:
    if slug in NEURO_GUIDES:
        return "neuro"
    haystack = " ".join(row.get(key, "") for key in ("indicated_use", "product", "type", "comments"))
    neuro = bool(NEURO_TERMS.search(haystack))
    peripheral = bool(PERIPHERAL_TERMS.search(haystack))
    if neuro and peripheral:
        return "both"
    if neuro:
        return "neuro"
    if peripheral:
        return "peripheral"
    return "unknown"


def extract_guide(pdf_path: Path) -> list[dict[str, Any]]:
    """One record per product row, with continuation rows merged into their parent."""
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required to extract EVT guide PDFs")
    region, slug = guide_slug(pdf_path)
    category = GUIDE_CATEGORIES.get(slug, "unknown")
    digest = sha256_file(pdf_path)
    relative = pdf_path.relative_to(CATALOG_ROOT).as_posix()
    records: list[dict[str, Any]] = []
    headers: list[str] | None = None
    raw_headers: list[str] | None = None
    with fitz.open(pdf_path) as doc:
        title = guide_title(doc)
        last_company = ""
        for page_index in range(doc.page_count):
            page = doc[page_index]
            pdf_page = page_index + 1
            for table_index, table in enumerate(page.find_tables().tables):
                rows = table.extract()
                if not rows:
                    continue
                first = [clean_cell(cell) for cell in rows[0]]
                body_start = 0
                if first and first[0].casefold().startswith("company"):
                    raw_headers = first
                    headers = [normalize_header(cell) for cell in first]
                    body_start = 1
                if headers is None:
                    continue
                for row_index, raw in enumerate(rows[body_start:], start=body_start):
                    cells = [clean_cell(cell) for cell in raw]
                    cells += [""] * (len(headers) - len(cells))
                    row = dict(zip(headers, cells))
                    company = row.get("company", "")
                    product = row.get("product", "")
                    if not product:
                        # Page-break continuation: a row with no product name is the tail
                        # of the previous row (a wrapped company name such as "USA, Inc."
                        # lands in the company cell). Append non-empty cells to the parent.
                        if records:
                            parent = records[-1]
                            for key, value in row.items():
                                if not value:
                                    continue
                                if key == "company":
                                    parent["company"] = f"{parent['company']} {value}".strip()
                                    parent["fields"]["company"] = parent["company"]
                                elif not is_blank(value):
                                    parent["fields"][key] = (parent["fields"].get(key, "") + " " + value).strip()
                            parent["continued_on"].append(pdf_page)
                        continue
                    if not company:
                        row["company"] = last_company
                    else:
                        last_company = company
                    fields = {key: value for key, value in row.items() if value and not is_blank(value)}
                    record = {
                        "guide_slug": slug,
                        "region": region,
                        "catalog_category": category,
                        "guide_title": title,
                        "pdf_filename": relative,
                        "pdf_sha256": digest,
                        "pdf_page": pdf_page,
                        "table_index": table_index,
                        "row_index": row_index,
                        "company": row["company"],
                        "product": product,
                        "fields": fields,
                        "raw_cells": dict(zip(raw_headers or headers, cells)),
                        "continued_on": [],
                    }
                    record["neuro_relevance"] = neuro_relevance(slug, fields)
                    records.append(record)
    for record in records:
        record["row_id"] = f"evt:{record['region'].lower()}-{slug}:{record['pdf_page']}:{record['table_index']}:{record['row_index']}"
        record["source_locator"] = (
            f"{title} ({pdf_path.name}), PDF page {record['pdf_page']}, "
            f"row '{record['company']} / {record['product']}'"
        )
    return records


def retained_guides(issue: str | None = None) -> list[Path]:
    folders = sorted(SOURCE_ROOT.glob("*")) if issue is None else [SOURCE_ROOT / issue]
    return [pdf for folder in folders if folder.is_dir() for pdf in sorted(folder.glob("EVT-*.pdf"))]


def extract_all(slugs: set[str] | None = None, issue: str | None = None) -> dict[str, int]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for pdf_path in retained_guides(issue):
        region, slug = guide_slug(pdf_path)
        if slugs and slug not in slugs:
            continue
        records = extract_guide(pdf_path)
        out = OUTPUT_DIR / f"{region.lower()}-{slug}.rows.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        counts[out.name] = len(records)
    return counts


def main(argv: list[str]) -> int:
    slugs = set(argv) or None
    counts = extract_all(slugs)
    for name, count in counts.items():
        print(f"{count:4d}  {name}")
    print(f"{sum(counts.values())} rows from {len(counts)} guides -> {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
