"""Regenerate the flat neurointerventional catalog CSV from enriched records.

``exports/consolidated/device_catalog_neurointerventional_consolidated.csv`` is a
derived index: one row per ``artifacts/neurointerventional/*/*/enriched/*.json``
record with the structured ``sizing_specs.id_od`` block flattened into columns. It
is convenient for spreadsheet review and for the ``agent-textbooks`` identity-lead
search, and it carries no trust of its own - every cell traces back to the enriched
record, which traces back to its own source fields.

The column set is fixed so existing consumers keep working. Rebuild after any
enrichment change:

    python -m pipeline.export_consolidated_csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .config import CATALOG_ROOT

OUTPUT = CATALOG_ROOT / "exports" / "consolidated" / "device_catalog_neurointerventional_consolidated.csv"

COLUMNS = [
    "registry", "filename_stem", "device_name", "manufacturer", "catalog_category",
    "clearance_type", "clearance_number", "clearance_date", "device_class", "device_name_fda",
    "product_code", "what_it_is", "indications", "contraindications", "compatible_with",
    "use_notes", "deployment_steps", "also_known_as", "sizing_specs_raw", "spec_status",
    "id_od_units", "id_in", "id_mm", "id_fr", "id_note",
    "od_prox_in", "od_prox_mm", "od_prox_fr", "od_prox_note",
    "od_dist_in", "od_dist_mm", "od_dist_fr", "od_dist_note",
    "od_max_in", "od_max_mm", "od_max_fr", "od_max_note",
    "guidewire_max", "max_od_is_proximal", "id_od_verbatim_quote", "k_number",
    "source_url", "source_name", "source_type", "extraction_method", "extracted_date",
    "review_note", "pdf_summary_url", "ifu_pdf_url", "device_source_url",
    "confidence_score", "needs_review", "data_sources",
]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " | ".join(_text(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _measure(block: dict[str, Any] | None, unit: str) -> str:
    if not isinstance(block, dict):
        return ""
    return _text(block.get(unit, ""))


def flatten(record: dict[str, Any], registry: str, stem: str = "") -> dict[str, str]:
    sizing = record.get("sizing_specs")
    sizing_raw = ""
    spec_status = ""
    id_od: dict[str, Any] = {}
    if isinstance(sizing, dict):
        spec_status = _text(sizing.get("spec_status", ""))
        id_od = sizing.get("id_od") or {}
        sizing_raw = _text(sizing)
    elif sizing:
        sizing_raw = _text(sizing)
    row = {column: "" for column in COLUMNS}
    row.update({
        "registry": registry,
        "filename_stem": _text(record.get("filename_stem")) or stem,
        "device_name": _text(record.get("device_name")),
        "manufacturer": _text(record.get("manufacturer")),
        "catalog_category": _text(record.get("catalog_category")),
        "clearance_type": _text(record.get("clearance_type")),
        "clearance_number": _text(record.get("clearance_number")),
        "clearance_date": _text(record.get("clearance_date")),
        "device_class": _text(record.get("device_class")),
        "device_name_fda": _text(record.get("device_name_fda")),
        "product_code": _text(record.get("product_code")),
        "what_it_is": _text(record.get("what_it_is")),
        "indications": _text(record.get("indications")),
        "contraindications": _text(record.get("contraindications")),
        "compatible_with": _text(record.get("compatible_with")),
        "use_notes": _text(record.get("use_notes")),
        "deployment_steps": _text(record.get("deployment_steps")),
        "also_known_as": _text(record.get("also_known_as")),
        "sizing_specs_raw": sizing_raw,
        "spec_status": spec_status,
        "id_od_units": _text(id_od.get("units")),
        "id_in": _measure(id_od.get("id"), "in"),
        "id_mm": _measure(id_od.get("id"), "mm"),
        "id_fr": _measure(id_od.get("id"), "fr"),
        "id_note": _measure(id_od.get("id"), "note"),
        "od_prox_in": _measure(id_od.get("od_prox"), "in"),
        "od_prox_mm": _measure(id_od.get("od_prox"), "mm"),
        "od_prox_fr": _measure(id_od.get("od_prox"), "fr"),
        "od_prox_note": _measure(id_od.get("od_prox"), "note"),
        "od_dist_in": _measure(id_od.get("od_dist"), "in"),
        "od_dist_mm": _measure(id_od.get("od_dist"), "mm"),
        "od_dist_fr": _measure(id_od.get("od_dist"), "fr"),
        "od_dist_note": _measure(id_od.get("od_dist"), "note"),
        "od_max_in": _measure(id_od.get("od_max"), "in"),
        "od_max_mm": _measure(id_od.get("od_max"), "mm"),
        "od_max_fr": _measure(id_od.get("od_max"), "fr"),
        "od_max_note": _measure(id_od.get("od_max"), "note"),
        "guidewire_max": _text(id_od.get("guidewire_max")),
        "max_od_is_proximal": _text(id_od.get("max_od_is_proximal")),
        "id_od_verbatim_quote": _text(id_od.get("verbatim_quote")),
        "k_number": _text(id_od.get("k_number") or record.get("k_number")),
        "source_url": _text(id_od.get("source_url")),
        "source_name": _text(id_od.get("source_name")),
        "source_type": _text(id_od.get("source_type")),
        "extraction_method": _text(id_od.get("extraction_method")),
        "extracted_date": _text(id_od.get("extracted")),
        "review_note": _text(id_od.get("review_note")),
        "pdf_summary_url": _text(record.get("pdf_summary_url")),
        "ifu_pdf_url": _text(record.get("ifu_pdf_url")),
        "device_source_url": _text(record.get("source_url")),
        "confidence_score": _text(record.get("confidence_score")),
        "needs_review": _text(record.get("needs_review")),
        "data_sources": _text(record.get("data_sources")),
    })
    return row


def build(output: Path = OUTPUT) -> int:
    rows: list[dict[str, str]] = []
    for path in sorted(CATALOG_ROOT.glob("artifacts/neurointerventional/*/*/enriched/*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append(flatten(record, path.parents[2].name, path.stem))
    rows.sort(key=lambda r: (r["registry"], r["filename_stem"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    count = build()
    print(f"Wrote {count} rows to {OUTPUT.relative_to(CATALOG_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
