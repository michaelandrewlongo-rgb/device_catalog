"""Reopen catalog PDF pages for every suspect extraction row and emit evidence.

Read-only. For each suspect (bleed candidate, cross-device duplicate catalog
number, in/mm mismatch, decimal-comma cell) this opens the retained catalog PDF
at the cited page (and its neighbors), extracts the page text and detected
tables, and writes a side-by-side report a reviewer turns into correction
records for ``apply_extraction_corrections``. Nothing is auto-applied.

The PDF is trusted only after its sha256 matches the extraction summary's
``pdf_sha256``.

    python -m pipeline.knowledge_v2.verify_suspects
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from ..config import CATALOG_ROOT, EXTRACTED_DIR
from .audit import sha256_file
from .io import read_json, read_jsonl
from .validate_dimensions import (
    DECIMAL_COMMA_RE,
    find_bleed_candidates,
    find_duplicate_catalog_numbers,
    check_in_mm_consistency,
)

DATA = Path(__file__).resolve().parent / "data"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"
DEFAULT_OUT = CATALOG_ROOT / "reviews" / "remediation"

# extraction set -> retained catalog PDF (repository-relative)
SET_PDFS = {
    "stryker_catalog_2024": "sources/official/current/stryker--neurovascular-product-catalogue-2024.pdf",
    "microvention_catalog_2019_intl": "sources/official/current/microvention--international-product-catalog-2019.pdf",
    "medtronic_catalog_2019": "sources/official/current/medtronic--neurovascular-product-catalog-2019.pdf",
    "balt_catalog_2020_intl": "sources/official/current/balt--international-product-catalogue-2020.pdf",
    "penumbra_brochure_2025": "sources/official/current/penumbra--penumbra-system-red-72-silver-label-brochure-2025.pdf",
}


def load_rows_by_set() -> dict[str, list[dict[str, Any]]]:
    return {name: read_jsonl(EXTRACTED_DIR / f"{name}.rows.jsonl") for name in SET_PDFS}


def page_evidence(pdf_path: Path, pdf_page: int, needle: str) -> dict[str, Any]:
    """Text and tables of the cited page and its neighbors, needle highlighted."""
    import fitz

    evidence: dict[str, Any] = {"pages": {}}
    with fitz.open(pdf_path) as doc:
        for number in (pdf_page - 1, pdf_page, pdf_page + 1):
            if not 1 <= number <= doc.page_count:
                continue
            page = doc[number - 1]
            text = page.get_text("text")
            tables = []
            try:
                for table in page.find_tables():
                    tables.append(table.extract())
            except Exception as exc:  # find_tables can fail on odd geometry
                tables.append([[f"<table extraction failed: {exc}>"]])
            evidence["pages"][number] = {
                "cited": number == pdf_page,
                "needle_found": bool(needle) and needle in text,
                "text": text,
                "tables": tables,
            }
    return evidence


def rows_matching(rows: list[dict[str, Any]], catalog_number: str | None = None,
                  family: str | None = None) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if catalog_number and (row.get("catalog_number") or "").strip() != catalog_number:
            continue
        if family and row.get("product_family") != family:
            continue
        out.append(row)
    return out


def collect_suspects(rows_by_set: dict[str, list[dict[str, Any]]],
                     claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One suspect record per (set, catalog_number or cell) needing PDF review."""
    suspects: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(set_name: str, kind: str, catalog_number: str, family: str, detail: str) -> None:
        key = (set_name, catalog_number or detail)
        if key in seen:
            return
        seen.add(key)
        suspects.append({"set": set_name, "kind": kind, "catalog_number": catalog_number,
                         "family": family, "detail": detail})

    for item in find_bleed_candidates(rows_by_set):
        parts = item["ref"].split(":")
        set_name, number = parts[0], parts[-1]
        family = parts[1] if len(parts) == 3 else ""
        add(set_name, item["check"], number, family, item["detail"])

    # Cross-device duplicates from the claims master: map each back to the
    # extraction set named inside the claim_id (claim:catalog:<mfr>:<set>:...).
    for item in find_duplicate_catalog_numbers(claims, allowlist=[]):
        manufacturer, number = item["ref"].split("/", 1)
        for claim in claims:
            if claim.get("manufacturer") != manufacturer:
                continue
            for sku in claim.get("skus") or []:
                if (sku.get("catalog_number") or "").strip() != number:
                    continue
                match = re.match(r"claim:catalog:[^:]+:([^:]+):", claim["claim_id"])
                if match and match.group(1) in SET_PDFS:
                    add(match.group(1), "duplicate_catalog_number", number,
                        claim.get("device_name", ""), item["detail"])

    for item in check_in_mm_consistency(rows_by_set, allowlist=[]):
        set_name, number, field = item["ref"].split(":", 2)
        add(set_name, "in_mm_mismatch", number, "", item["detail"])

    for set_name, rows in rows_by_set.items():
        for row in rows:
            for key, value in (row.get("fields") or {}).items():
                if isinstance(value, str) and DECIMAL_COMMA_RE.search(value):
                    add(set_name, "decimal_comma", (row.get("catalog_number") or "").strip(),
                        row.get("product_family", ""), f"{key}={value!r} (verbatim check only)")
                    break
    return suspects


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--kinds", nargs="*", help="limit to these suspect kinds")
    args = parser.parse_args()

    rows_by_set = load_rows_by_set()
    claims = read_jsonl(CLAIMS)

    for name, pdf_relative in SET_PDFS.items():
        pdf_path = CATALOG_ROOT / pdf_relative
        summary = read_json(EXTRACTED_DIR / f"{name}.summary.json")
        actual = sha256_file(pdf_path)
        if actual != summary["pdf_sha256"]:
            raise SystemExit(f"{name}: PDF sha256 {actual} != extraction summary "
                             f"{summary['pdf_sha256']}; refusing to verify against a different file")

    suspects = collect_suspects(rows_by_set, claims)
    if args.kinds:
        suspects = [s for s in suspects if s["kind"] in args.kinds]

    report: list[dict[str, Any]] = []
    for suspect in suspects:
        rows = rows_by_set[suspect["set"]]
        matched = rows_matching(rows, suspect["catalog_number"] or None,
                                suspect["family"] or None)
        pages = sorted({r["pdf_page"] for r in matched}) or []
        entry = dict(suspect)
        entry["extracted_rows"] = matched
        entry["evidence"] = {}
        pdf_path = CATALOG_ROOT / SET_PDFS[suspect["set"]]
        for page in pages:
            entry["evidence"][str(page)] = page_evidence(pdf_path, page, suspect["catalog_number"])
        report.append(entry)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "suspect_evidence.json"
    json_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n",
                         encoding="utf-8")

    md_lines = ["# Suspect extraction rows vs. source PDF pages", ""]
    for entry in report:
        md_lines.append(f"## [{entry['kind']}] {entry['set']} — "
                        f"{entry['catalog_number'] or entry['detail'][:60]}")
        md_lines.append(f"- detail: {entry['detail']}")
        for row in entry["extracted_rows"]:
            md_lines.append(f"- extracted: family={row.get('product_family')!r} "
                            f"pdf_page={row.get('pdf_page')} fields={json.dumps(row.get('fields', {}), ensure_ascii=False)}")
        for page, ev in entry["evidence"].items():
            for number, data in ev["pages"].items():
                flag = "cited" if data["cited"] else "neighbor"
                md_lines.append(f"- page {number} ({flag}): needle_found={data['needle_found']}, "
                                f"tables={len(data['tables'])}")
        md_lines.append("")
    (args.out_dir / "suspect_evidence.md").write_text("\n".join(md_lines) + "\n",
                                                      encoding="utf-8")
    print(json.dumps({"suspects": len(report),
                      "kinds": sorted({s['kind'] for s in report}),
                      "out": str(json_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
