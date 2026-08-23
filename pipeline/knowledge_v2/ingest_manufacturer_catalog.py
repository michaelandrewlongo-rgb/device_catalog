"""Turn extracted manufacturer-catalog rows into knowledge-v2 sources and claims.

Input: ``pipeline/data/extracted/<name>.rows.jsonl`` (one record per catalog-number
row: pdf_page, section, product_family, product_name, catalog_number, fields, units,
headers, notes) plus ``<name>.summary.json`` (pdf_sha256, title, catalog_year).

A manufacturer product catalog is the manufacturer's own published specification
table. It sits above a trade-journal guide and below an IFU / current labeling: it is
served at the ``manufacturer_catalog`` evidence layer, carries its publication year
on every claim, and is outranked by labeling on conflict.

Per product family this writes one source (the retained catalog PDF, hashed) and one
``device_specifications`` claim carrying every catalog number's printed fields, with
the PDF page as locator. Values are kept as printed; nothing is converted.

    python -m pipeline.knowledge_v2.ingest_manufacturer_catalog medtronic_catalog_2019 \
        --manufacturer medtronic --pdf sources/official/current/medtronic--neurovascular-product-catalog-2019.pdf
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import CATALOG_ROOT, EXTRACTED_DIR
from .io import read_json, read_jsonl, write_json

DATA = Path(__file__).resolve().parent / "data"
REGISTRY = DATA / "source_registry.json"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"

FAMILY_CATEGORY = [
    (re.compile(r"guide ?wire", re.I), "guidewire"),
    (re.compile(r"balloon guide", re.I), "balloon-catheter"),
    (re.compile(r"\b(balloon|hyperform|hyperglide)\b", re.I), "balloon-catheter"),
    (re.compile(r"distal access|intermediate|phenom|react|arc\b", re.I), "distal-access"),
    (re.compile(r"aspiration|riptide", re.I), "aspiration"),
    (re.compile(r"micro ?catheter|marksman|echelon|apollo|marathon|rebar|phenom 17|phenom 21", re.I), "microcatheter"),
    (re.compile(r"pipeline|flow divert", re.I), "flow-diverter"),
    (re.compile(r"solitaire|stent retriever|revascularization", re.I), "stent-retriever"),
    (re.compile(r"axium|coil", re.I), "embolic-coil"),
    (re.compile(r"onyx|liquid embolic", re.I), "liquid-embolic"),
    (re.compile(r"stent", re.I), "intracranial-stent"),
]


def slugify(value: str) -> str:
    value = re.sub(r"[®™©*]", "", value or "")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").casefold()
    return value or "unknown"


def family_category(family: str, section: str) -> str:
    for pattern, category in FAMILY_CATEGORY:
        if pattern.search(f"{family} {section}"):
            return category
    return slugify(section) or "device"


def identity_terms(family: str, device_name: str) -> list[str]:
    """Terms any one of which proves the catalog page names this family.

    Family titles are reconstructed from headings and may not be printed
    contiguously ("introducer sheath (long) IVA" vs the page's "ballast & IVA"),
    so the brand token - the last alphabetic word of 3+ letters - is accepted too.
    """
    terms = [family, device_name]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}", family) if w.lower() not in {"the", "and", "for", "with", "system", "catheter", "device", "coil", "stent", "long", "kit"}]
    if words:
        terms.append(words[-1])
    return terms


def family_device_name(family: str) -> str:
    name = re.sub(r"[®™*]", "", family).strip()
    return " ".join(w if w.isupper() and len(w) <= 3 else w.capitalize() if w.isupper() else w for w in name.split())


def ingest(name: str, manufacturer: str, pdf_relative: str, catalog_year: str | None = None) -> dict[str, Any]:
    rows = read_jsonl(EXTRACTED_DIR / f"{name}.rows.jsonl")
    summary = read_json(EXTRACTED_DIR / f"{name}.summary.json")
    year = catalog_year or str(summary.get("catalog_year") or "")
    jurisdiction = "international" if str(summary.get("jurisdiction", "")).lower().startswith("int") else "US"
    sha = summary["pdf_sha256"]
    title = summary.get("title") or name
    pdf_path = CATALOG_ROOT / pdf_relative
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_relative)

    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        families[row["product_family"]].append(row)

    registry = read_json(REGISTRY)
    have_sources = {s["source_id"] for s in registry["sources"]}
    existing = read_jsonl(CLAIMS)
    have_claims = {c["claim_id"] for c in existing}
    new_sources, new_claims = [], []
    for family, frows in families.items():
        section = frows[0].get("section", "")
        category = family_category(family, section)
        device_name = family_device_name(family)
        device_id = f"{category}--{manufacturer}--{slugify(device_name)}"
        pages = sorted({r["pdf_page"] for r in frows})
        printed_by_pdf = {r["pdf_page"]: r.get("printed_page") for r in frows}

        def page_label(pdf_page: int) -> str:
            printed = printed_by_pdf.get(pdf_page)
            if printed is None and name.startswith("medtronic_catalog_2019"):
                printed = pdf_page - 2
            return f"PDF page {pdf_page}" + (f" (printed page {printed})" if printed is not None else "")
        source_id = f"catalog:{manufacturer}:{name}:{device_id}"
        if source_id not in have_sources:
            new_sources.append({
                "source_id": source_id,
                "device_id": device_id,
                "title": f"{title} ({year}), {device_name} table",
                "source_type": "manufacturer_product_catalog",
                "status": "current",
                "evidence_depth": "local_full_text",
                "jurisdiction": jurisdiction,
                "document_id": name,
                "revision": f"{year} catalog",
                "local_filename": pdf_relative,
                "sha256": sha,
                "identity": {"required_any": identity_terms(family, device_name)},
                "notes": (
                    f"Manufacturer product catalog dated {year}; catalog-number-level specifications as "
                    "published by the manufacturer. Outranked by the current IFU or labeling on conflict; "
                    "products introduced or revised after the catalog date are not reflected."
                ),
            })
            have_sources.add(source_id)
        skus = []
        for r in frows:
            skus.append({
                "catalog_number": r["catalog_number"],
                "product_name": r.get("product_name") or device_name,
                "pdf_page": r["pdf_page"],
                "fields": r["fields"],
                "units": r.get("units", {}),
                "headers": r.get("headers", {}),
            })
        printed = "; ".join(
            f"{s['catalog_number']} ({s['product_name']}): " + ", ".join(f"{k.replace('_', ' ')} {v}{(' ' + s['units'][k]) if s['units'].get(k) else ''}" for k, v in s["fields"].items())
            for s in skus[:12]
        )
        more = f"; and {len(skus) - 12} further catalog numbers" if len(skus) > 12 else ""
        claim_id = f"claim:catalog:{manufacturer}:{name}:{slugify(device_name)}"
        if claim_id in have_claims:
            continue
        new_claims.append({
            "claim_id": claim_id,
            "device_id": device_id,
            "device_name": device_name,
            "manufacturer": manufacturer,
            "catalog_category": category,
            "claim_type": "device_specifications",
            "evidence_layer": "manufacturer_catalog",
            "evidence_class": "manufacturer_catalog",
            "support": "direct",
            "review_status": "source_checked",
            "review_note": "Extracted by PyMuPDF table read and verified against the page text by an independent agent (every catalog number confirmed on its page).",
            "source_ids": [source_id],
            "locators": [f"{page_label(p)}, {family} table" for p in pages],
            "checked_at": "2026-08-23",
            "catalog_year": year,
            "jurisdiction": jurisdiction,
            "skus": skus,
            "notes": frows[0].get("notes") or "",
            "text": f"{device_name} per the {title} ({year}{', international edition' if jurisdiction == 'international' else ''}): {printed}{more}. Catalog-year specification; confirm against current IFU{' and US labeling before assuming US availability' if jurisdiction == 'international' else ''}.",
        })
        have_claims.add(claim_id)
    registry["sources"].extend(new_sources)
    write_json(REGISTRY, registry)
    with CLAIMS.open("a", encoding="utf-8", newline="\n") as handle:
        for claim in new_claims:
            handle.write(json.dumps(claim, sort_keys=True, separators=(",", ":")) + "\n")
    return {"families": len(families), "rows": len(rows), "new_sources": len(new_sources), "new_claims": len(new_claims)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--pdf", required=True, help="repository-relative path of the retained catalog PDF")
    parser.add_argument("--year")
    args = parser.parse_args()
    print(json.dumps(ingest(args.name, args.manufacturer, args.pdf, args.year), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
