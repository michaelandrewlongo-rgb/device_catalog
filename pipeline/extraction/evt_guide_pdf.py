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


NAME_SUFFIX_RE = re.compile(r"^(?:inc|llc|ltd|corp|co|gmbh|sa|ag|usa|medical|systems?|catheter|device|\(?neuro\)?)[.,)]*$", re.I)


def is_continuation_fragment(row: dict[str, str], headers: list[str], *, first_body: bool) -> bool:
    """Detect a wrapped row whose name cells are fragments rather than names.

    Only the first body row of a page can wrap from the previous page. A real
    product row carries a multi-word company or product and at least some spec
    cells; a fragment row has one-token name cells such as "Inc." or "Catheter"
    and mostly empty cells.
    """
    if not first_body:
        return False
    company, product = row.get("company", ""), row.get("product", "")
    spec_keys = [h for h in headers if h not in ("company", "product")]
    empty = sum(1 for key in spec_keys if is_blank(row.get(key, "")))
    fragmentary = all(len(name.split()) <= 2 and NAME_SUFFIX_RE.match(name.split()[-1]) for name in (company, product) if name)
    if fragmentary and empty >= len(spec_keys) / 2:
        return True
    # A company cell that is nothing but a corporate suffix ("Corporation", "Inc")
    # is the wrapped tail of the previous row's company, whatever else the row holds.
    if company and re.fullmatch(r"(?:inc|llc|ltd|corp|corporation|co|gmbh|usa)[.,]?(?:\s*\(neuro\))?", company, re.I):
        return True
    # A wrapped row may re-print the company and carry the tail of the product
    # name, but its prose cells then begin mid-sentence (lowercase) and its
    # numeric spec cells are empty. A real row starts its prose with a capital.
    numeric_keys = [k for k in spec_keys if k.endswith(("_fr", "_in", "_cm", "_mm"))]
    numeric_empty = all(is_blank(row.get(k, "")) for k in numeric_keys)
    prose = [row.get(k, "") for k in spec_keys if row.get(k, "") and len(row.get(k, "")) > 20]
    mid_sentence = any(text[0].islower() for text in prose)
    return bool(numeric_keys) and numeric_empty and mid_sentence


def page_geometry(page: "fitz.Page", columns: list[tuple[float, float]] | None):
    """Column x-bounds and row y-bands for one guide page.

    ``find_tables`` on these guides returns only the shaded rows: the unshaded
    rows between them have no drawn border, so half of every table was dropped.
    Rows are therefore built geometrically. Column bounds come from the header row
    (the one table cell-row ``find_tables`` does see, or the header words); row
    bands are the shaded rectangles plus the gaps between them, down to the last
    word inside the column span.
    """
    words = page.get_text("words")
    header_y1 = None
    header_text: list[str] | None = None
    for table in page.find_tables().tables:
        rows = table.extract()
        first = [clean_cell(c) for c in rows[0]] if rows else []
        if first and first[0].casefold().startswith("company"):
            columns = [(cell[0], cell[2]) for cell in table.rows[0].cells]
            header_y1 = table.rows[0].bbox[3]
            header_text = first
            break
    if columns is None:
        return None, None, None, []
    if header_y1 is None:
        header_words = [w for w in words if w[4] in ("Company", "Name") and w[0] < columns[0][1]]
        header_y1 = max(w[3] for w in header_words) + 2 if header_words else 0
    shades = [
        d["rect"] for d in page.get_drawings()
        if d.get("fill") and len(d["fill"]) >= 3 and 0.85 < d["fill"][0] < 0.99 and d["rect"].height > 6
    ]
    bands: list[tuple[float, float]] = []
    for y0, y1 in sorted({(round(r.y0, 1), round(r.y1, 1)) for r in shades if r.y0 > header_y1 - 2}):
        if bands and y0 <= bands[-1][1] + 0.5:
            bands[-1] = (bands[-1][0], max(bands[-1][1], y1))
        else:
            bands.append((y0, y1))
    body = [w for w in words if w[1] >= header_y1 - 1 and w[0] >= columns[0][0] - 2 and w[2] <= columns[-1][1] + 2]
    if not body:
        return columns, header_y1, header_text, []
    edges = sorted({header_y1, *(y for band in bands for y in band), max(w[3] for w in body) + 1})
    row_bands = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] - edges[i] > 4]
    rows: list[list[str]] = []
    for y0, y1 in row_bands:
        cells: list[list[tuple]] = [[] for _ in columns]
        in_band = [w for w in body if y0 - 0.5 <= (w[1] + w[3]) / 2 <= y1 + 0.5]
        if not in_band:
            continue
        for w in in_band:
            xc = (w[0] + w[2]) / 2
            for i, (cx0, cx1) in enumerate(columns):
                if cx0 - 1 <= xc <= cx1 + 1:
                    cells[i].append(w)
                    break
        texts = []
        for col in cells:
            lines: dict[int, list[tuple]] = {}
            for w in col:
                lines.setdefault(round(w[1]), []).append(w)
            texts.append(" ".join(" ".join(x[4] for x in sorted(ws, key=lambda x: x[0])) for _, ws in sorted(lines.items())).strip())
        rows.append(texts)
    return columns, header_y1, header_text, rows


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
        columns = None
        for page_index in range(doc.page_count):
            page = doc[page_index]
            pdf_page = page_index + 1
            columns, header_y1, header_text, page_rows = page_geometry(page, columns)
            if columns is None:
                continue
            if header_text and header_text != raw_headers:
                raw_headers = header_text
                headers = [normalize_header(h) for h in raw_headers]
            if headers is None:
                continue
            for ordinal, cells in enumerate(page_rows):
                cells = [clean_cell(cell) for cell in cells]
                cells += [""] * (len(headers) - len(cells))
                row = dict(zip(headers, cells))
                company = row.get("company", "")
                product = row.get("product", "")
                if not product or is_continuation_fragment(row, headers, first_body=(ordinal == 0 and pdf_page > 1)):
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
                    "row_ordinal": ordinal,
                    "company": row["company"],
                    "product": product,
                    "fields": fields,
                    "raw_cells": dict(zip(raw_headers, cells)),
                    "continued_on": [],
                }
                record["neuro_relevance"] = neuro_relevance(slug, fields)
                records.append(record)
    for record in records:
        record["row_id"] = f"evt:{record['region'].lower()}-{slug}:{record['pdf_page']}:r{record['row_ordinal']}"
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
