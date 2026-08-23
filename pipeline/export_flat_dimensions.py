"""Export one flat device x dimension CSV across every evidence layer.

Reads the knowledge-v2 masters (claims + source registry) and emits one row per
specification line: a catalog SKU, an EVT-guide dimension set, or a labeled
IFU statement (sizing / compatibility / indication ... kept as prose in
``labeled_statement`` -- prose is never re-parsed into numbers here).

Values are kept exactly as printed in the source; where the source table
carried a unit for a column it is appended to the value ("2.4 mm"). Columns
that do not apply to a row are left empty. ``other_fields`` holds any printed
field that has no canonical column, as JSON.

    python -m pipeline.export_flat_dimensions [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

EXPORT = Path(__file__).resolve().parent / "knowledge_v2" / "data"
DEFAULT_OUT = Path.home() / "Downloads" / "device_dimensions_flat.csv"

# canonical column <- printed field keys (sku "fields") and guide "dimensions" keys
CANON = {
    "inner_diameter": {"id", "inner_diameter", "distal_proximal_id_fr", "distal_proximal_id",
                       "inner_diameter_in", "id_in", "id_inches", "lumen"},
    "outer_diameter": {"od", "outer_diameter", "outer_diameter_inch", "profile", "crossing_profile",
                       "unconstrained_stent_od_mm", "od_in", "od_fr"},
    "distal_outer_diameter": {"distal_od", "distal_od_fr", "distal_od_in", "distal_od_mm",
                              "distal_outer_diameter", "distal_outer_diameter_inch"},
    "proximal_outer_diameter": {"proximal_od", "proximal_od_in", "proximal_od_mm", "proximal_od_fr",
                                "proximal_outer_diameter", "proximal_outer_diameter_inch"},
    "middle_outer_diameter": {"middle_outer_diameter", "middle_outer_diameter_inch"},
    "length": {"length", "length_cm", "length_mm", "length_in", "total_length", "total_length_cm",
               "working_length", "usable_length", "catheter_length", "catheter_working_length",
               "length_in_introducer", "tip_length"},
    "wire_diameter": {"wire_diameter", "guidewire_diameter", "wire_od"},
    "coil_diameter": {"coil_diameter", "progressive_coil_diameter", "large_loop_diameter",
                      "diameter_mm", "secondary_diameter"},
    "implant_size": {"implant_size", "diameter_x_length", "size", "stent_size"},
    "stent_diameter": {"stent_diameter", "tapered_stent_diameter", "unconstrained_stent_diameter",
                       "height_mm"},
    "stent_length": {"stent_length", "stent_length_nominal_mm", "unconstrained_stent_length_mm",
                     "tapered_stent_length"},
    "vessel_diameter": {"vessel_od_mm", "recommended_vessel_diameter", "vessel_diameter",
                        "reference_vessel_diameter"},
    "balloon_diameter": {"balloon_diameter"},
    "balloon_length": {"balloon_length"},
    "guidewire_compatibility": {"guidewire", "guidewire_compatibility", "wire_compatibility",
                                "max_guidewire", "guide_wire"},
    "catheter_compatibility": {"delivery_catheters", "recommended_catheter",
                               "compatible_delivery_catheter", "delivery_catheter",
                               "recommended_microcatheter", "microcatheter_id",
                               "sheath_compatibility", "guide_catheter_compatibility",
                               "min_delivery_id", "catheter_id_compatibility"},
    "diameter": {"diameter"},
}
FIELD_TO_COL = {f: col for col, fields in CANON.items() for f in fields}

COLUMNS = [
    "device_id", "device_name", "manufacturer", "category", "catalog_number", "product_name",
    "diameter", "inner_diameter", "outer_diameter", "distal_outer_diameter",
    "proximal_outer_diameter", "middle_outer_diameter", "length", "wire_diameter",
    "coil_diameter", "implant_size", "stent_diameter", "stent_length", "vessel_diameter",
    "balloon_diameter", "balloon_length", "guidewire_compatibility", "catheter_compatibility",
    "other_fields", "labeled_statement", "claim_type", "evidence_layer", "jurisdiction",
    "source_year", "source_id", "claim_id", "locator", "source_title",
]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def with_unit(value, unit) -> str:
    text = str(value).strip()
    if unit and str(unit).lower() not in text.lower():
        return f"{text} {unit}"
    return text


def device_parts(device_id: str, claim: dict) -> tuple:
    bits = device_id.split("--")
    category = bits[0] if len(bits) >= 2 else ""
    manufacturer = claim.get("manufacturer") or (bits[1] if len(bits) >= 3 else "")
    name = claim.get("device_name") or (bits[-1].replace("-", " ").title() if bits else device_id)
    return name, manufacturer, category


def base_row(claim: dict, source) -> dict:
    name, manufacturer, category = device_parts(claim["device_id"], claim)
    return {
        "device_id": claim["device_id"],
        "device_name": name,
        "manufacturer": manufacturer,
        "category": claim.get("catalog_category") or category,
        "claim_type": claim.get("claim_type", ""),
        "evidence_layer": claim.get("evidence_layer", ""),
        "jurisdiction": claim.get("jurisdiction") or (source or {}).get("jurisdiction", ""),
        "source_year": claim.get("catalog_year") or claim.get("source_year", ""),
        "source_id": (claim.get("source_ids") or [""])[0],
        "claim_id": claim["claim_id"],
        "locator": "; ".join(claim.get("locators") or []),
        "source_title": (source or {}).get("title", ""),
    }


def quote_tail(entry: dict) -> str:
    quote = entry.get("quote", "")
    return quote.rsplit(": ", 1)[-1] if ": " in quote else quote


def render_entry(entry) -> str:
    """One structured dimension entry -> a printed-value string."""
    if not isinstance(entry, dict):
        return str(entry)
    unit = entry.get("unit") or ""
    if entry.get("range"):
        lo, hi = entry["range"]
        text = f"{lo}-{hi} {unit} (range)"
    elif entry.get("values"):
        text = "/".join(str(v) for v in entry["values"]) + (f" {unit}" if unit else "")
    elif entry.get("pairs"):
        text = "; ".join("/".join(str(x) for x in p) for p in entry["pairs"]) + (f" {unit}" if unit else "")
    elif entry.get("value") is not None:
        text = f"{entry['value']} {unit}".strip()
    else:
        text = quote_tail(entry)  # prose cells: serve the printed text, never a parsed number
    if entry.get("evidence_class") == "derived_calculation":
        text = f"(= {text}, derived {entry.get('derivation', '')})".replace(", derived )", ")")
    if entry.get("unit_conflict"):
        text += f" [header said {entry.get('header_unit')}]"
    return text.strip()


def render_value(value) -> str:
    entries = value if isinstance(value, list) else [value]
    return "; ".join(t for t in (render_entry(e) for e in entries) if t)


def fold_fields(fields: dict, units: dict) -> tuple:
    """Split printed fields into canonical columns and the JSON remainder."""
    row, other = {}, {}
    for key, value in fields.items():
        if key in {"product_number", "part_no", "product_description", "description",
                   "reorder_number", "ref", "order_number", "model_number", "catalog_number",
                   "upn", "gtin"}:
            continue
        col = FIELD_TO_COL.get(key)
        if isinstance(value, (dict, list)):
            text = render_value(value)
        else:
            text = with_unit(value, units.get(key))
        if col:
            row[col] = f"{row[col]}; {text}" if row.get(col) else text
        else:
            other[key] = text
    return row, other


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    claims = read_jsonl(EXPORT / "reviewed_claims.v2.jsonl")
    registry = json.loads((EXPORT / "source_registry.json").read_text(encoding="utf-8"))
    sources = {s["source_id"]: s for s in registry["sources"]}

    rows = []
    for claim in claims:
        source = sources.get((claim.get("source_ids") or [""])[0])
        if claim.get("skus"):
            for sku in claim["skus"]:
                row = base_row(claim, source)
                row["catalog_number"] = sku.get("catalog_number", "")
                row["product_name"] = sku.get("product_name", "")
                folded, other = fold_fields(sku.get("fields", {}), sku.get("units") or {})
                row.update(folded)
                if other:
                    row["other_fields"] = json.dumps(other, sort_keys=True, ensure_ascii=False)
                if sku.get("pdf_page"):
                    row["locator"] = f"PDF page {sku['pdf_page']}"
                rows.append(row)
        elif claim.get("dimensions"):
            row = base_row(claim, source)
            row["product_name"] = claim.get("device_name", "")
            folded, other = fold_fields(claim["dimensions"], {})
            row.update(folded)
            if other:
                row["other_fields"] = json.dumps(other, sort_keys=True, ensure_ascii=False)
            rows.append(row)
        else:
            row = base_row(claim, source)
            row["labeled_statement"] = claim.get("text", "").strip()
            rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "devices": len({r["device_id"] for r in rows}),
                      "out": str(args.out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
