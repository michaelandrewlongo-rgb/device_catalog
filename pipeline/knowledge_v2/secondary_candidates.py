"""Build secondary dimension candidates from extracted Endovascular Today guide rows.

Output: ``device_dimension_candidates.v2.jsonl`` records in the knowledge-v2.1 shape.
Each candidate bundles one guide row's observations for one product. Every
observation is labeled ``secondary_curated_catalog`` (quoted from the guide table) or
``derived_calculation`` (French-to-inch via ``inches = French / 76.2``) and carries
``review_status: catalog_only``. The bundle itself is ``review_required``.

These labels are the contract with ``agent-textbooks``: its sync rejects any
candidate whose observation claims an authoritative class or a reviewed status, and
its search returns candidates under a separate key with status
``secondary_candidates_only``. Nothing here can become an actionable claim; the path
to an actionable dimension is a reviewed claim against an IFU, FDA labeling, or a
510(k) technological-characteristics table.

Existing enriched records are joined by normalized manufacturer + product name only
to supply aliases and clearance metadata for discovery. A miss is recorded as
``device_entry: none``; no skeleton device files are created.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from ..config import CATALOG_ROOT, EXTRACTED_DIR
from .io import read_jsonl, write_jsonl

ROWS_DIR = EXTRACTED_DIR / "evt_guides"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "device_dimension_candidates.v2.jsonl"
REVIEW_DIR = CATALOG_ROOT / "pipeline" / "data" / "evt_guides"
FRENCH_PER_INCH = 76.2

# field name from evt_guide_pdf -> (dimension key, unit, meaning)
DIMENSION_FIELDS: dict[str, tuple[str, str, str]] = {
    "inner_diameter_in": ("inner_diameter", "inch", "inner (endhole) diameter as listed"),
    "proximal_od_fr": ("proximal_outer_diameter", "F", "proximal shaft outer diameter"),
    "middle_od_fr": ("middle_outer_diameter", "F", "middle shaft outer diameter"),
    "distal_od_fr": ("distal_outer_diameter", "F", "distal shaft outer diameter"),
    "od_fr": ("outer_diameter", "F", "outer diameter / catheter size as listed"),
    "working_length_cm": ("working_length", "cm", "working length"),
    "length_cm": ("working_length", "cm", "length as listed"),
    "guidewire_max_in": ("guidewire_compatibility", "inch", "recommended or maximum guidewire"),
    "guide_catheter_min_in": ("guide_catheter_compatibility", "inch", "recommended guide catheter ID"),
    "sheath_compatibility_fr": ("sheath_compatibility", "F", "sheath compatibility"),
    "introducer_size_fr": ("introducer_size", "F", "introducer size"),
    "stent_diameter_mm": ("stent_diameter", "mm", "stent diameter(s) as listed"),
    "stent_length_mm": ("stent_length", "mm", "stent length(s) as listed"),
    "tapered_stent_diameter_mm": ("tapered_stent_diameter", "mm", "tapered stent proximal/distal diameters"),
    "tapered_stent_length_mm": ("tapered_stent_length", "mm", "tapered stent lengths"),
    "device_diameter_mm": ("device_diameter", "mm", "device diameter(s) as listed"),
    "device_height_mm": ("device_height", "mm", "device height(s) as listed"),
    "balloon_diameter_mm": ("balloon_diameter", "mm", "balloon diameter(s) as listed"),
    "balloon_length_mm": ("balloon_length", "mm", "balloon length(s) as listed"),
    "tip_length_mm": ("tip_length", "mm", "tip length"),
    "delivery_system_length_cm": ("delivery_system_length", "cm", "delivery system length"),
    "wire_diameter_in": ("wire_diameter", "inch", "guidewire diameter(s) as listed"),
    "sizes_m": ("particle_size", "um", "particle size range(s) as listed"),
}

# Non-dimensional table columns carried as text attributes. "comments" is marketing
# copy supplied by the manufacturer and is deliberately not carried.
ATTRIBUTE_FIELDS = (
    "construction", "materials", "coil_type", "detachment", "indicated_use", "type",
    "mode_of_operation", "tip_type", "radiopaque_tip", "hydrophilic_coating", "cell_design",
    "delivery_system", "embolic_protection_device", "position", "color_coding",
)

NUMBER_RE = re.compile(r"(?<![A-Za-z])(\d+(?:\.\d+)?)")


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def slugify(value: str) -> str:
    value = re.sub(r"[®™©]", "", value or "")
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").casefold()
    return value or "unknown"


def manufacturer_slug(company: str) -> str:
    company = re.sub(r"\(.*?\)", "", company or "")
    company = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|gmbh|sa|ag|neurovascular|medical|technologies)\b\.?", "", company, flags=re.I)
    return slugify(company)


def parse_numbers(text: str) -> list[float]:
    return [float(match) for match in NUMBER_RE.findall(text or "")]


def load_enriched_index() -> dict[str, list[dict[str, Any]]]:
    """normalized product name -> enriched records (artifacts layout)."""
    index: dict[str, list[dict[str, Any]]] = {}
    for path in CATALOG_ROOT.glob("artifacts/neurointerventional/*/*/enriched/*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        names = [record.get("device_name") or ""]
        aka = record.get("also_known_as") or ""
        if isinstance(aka, str) and aka.startswith("["):
            try:
                aka = json.loads(aka.replace("'", '"'))
            except ValueError:
                aka = [aka]
        if isinstance(aka, str):
            aka = [part.strip() for part in aka.split("|")]
        names.extend(str(part) for part in aka if part)
        record["_registry"] = path.parents[2].name
        record["_device_id"] = path.parents[1].name
        for name in names:
            key = normalize(name)
            if len(key) >= 3:
                index.setdefault(key, []).append(record)
    return index


def match_enriched(index: dict[str, list[dict[str, Any]]], company: str, product: str) -> list[dict[str, Any]]:
    key = normalize(product)
    candidates = list(index.get(key, []))
    if not candidates:
        # Allow the guide's product name to be a prefix/suffix of the catalog name
        # (e.g. "Excelsior SL-10" vs "Excelsior SL-10 Microcatheter"), but require a
        # manufacturer agreement so "Q" cannot match every product containing "q".
        if len(key) >= 5:
            for index_key, records in index.items():
                if key in index_key or index_key in key:
                    candidates.extend(records)
    wanted = manufacturer_slug(company)
    filtered = [r for r in candidates if wanted and wanted.split("-")[0] in (r.get("manufacturer") or "")]
    return filtered or ([] if len(candidates) > 3 else candidates)


def observation(row: dict[str, Any], value: float | None, *, unit: str, meaning: str, quote: str,
                evidence_class: str = "secondary_curated_catalog", quoted: bool = True,
                derived_from: str | None = None) -> dict[str, Any]:
    item = {
        "value": value,
        "unit": unit,
        "meaning": meaning,
        "quoted": quoted,
        "quote": quote,
        "evidence_class": evidence_class,
        "review_status": "catalog_only",
        "source_locator": row["source_locator"],
        "source_title": row["guide_title"],
        "source_file": row["pdf_filename"],
        "source_sha256": row["pdf_sha256"],
        "pdf_page": row["pdf_page"],
    }
    if derived_from:
        item["derived_from"] = derived_from
        item["derivation"] = "inches = French / 76.2"
    return item


def build_candidate(row: dict[str, Any], index: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    fields = row["fields"]
    matches = match_enriched(index, row["company"], row["product"])
    dimensions: dict[str, list[dict[str, Any]]] = {}
    for field, (key, unit, meaning) in DIMENSION_FIELDS.items():
        raw = fields.get(field)
        if not raw:
            continue
        quote = f"{row['guide_title']}: {row['company']} {row['product']} - {row['raw_cells_header'].get(field, field)}: {raw}"
        numbers = parse_numbers(raw)
        # A single listed value is carried as a number; a list or range stays textual
        # so a later reader sees the exact list rather than one element of it.
        value = numbers[0] if len(numbers) == 1 else None
        entry = observation(row, value, unit=unit, meaning=meaning, quote=quote)
        if value is None and numbers:
            entry["values"] = numbers
        dimensions.setdefault(key, []).append(entry)
        if unit == "F" and value is not None:
            dimensions.setdefault(f"{key}_inch", []).append(
                observation(row, round(value / FRENCH_PER_INCH, 4), unit="inch", meaning=f"{meaning} (converted)",
                            quote=quote, evidence_class="derived_calculation", quoted=False, derived_from=key)
            )
    attributes = {}
    for field in ATTRIBUTE_FIELDS:
        if fields.get(field):
            attributes[field] = {
                "text": fields[field],
                "evidence_class": "secondary_curated_catalog",
                "review_status": "catalog_only",
                "source_locator": row["source_locator"],
            }
    aliases: list[str] = []
    clearance: list[dict[str, Any]] = []
    raw_ids: list[str] = []
    for record in matches:
        if record["_device_id"] in raw_ids:
            continue
        raw_ids.append(record["_device_id"])
        aliases.extend([record.get("device_name") or "", record["_device_id"], record.get("filename_stem") or ""])
        number = record.get("clearance_number") or record.get("k_number")
        if number:
            aliases.append(number)
            clearance.append({
                "clearance_number": number,
                "clearance_type": record.get("clearance_type") or "",
                "clearance_date": record.get("clearance_date") or "",
                "evidence_class": "fda_510k_or_pma",
                "provenance": "existing_enriched_record_join",
            })
    aliases = sorted({a for a in aliases if a})
    manufacturer = (matches[0].get("manufacturer") if matches else None) or manufacturer_slug(row["company"])
    device_id = raw_ids[0] if raw_ids else f"{row['catalog_category']}--{manufacturer}--{slugify(row['product'])}"
    return {
        "candidate_id": row["row_id"],
        "device_id": device_id,
        "device_entry": "existing" if raw_ids else "none",
        "device_name": row["product"],
        "manufacturer": manufacturer,
        "manufacturer_display": row["company"],
        "catalog_category": row["catalog_category"],
        "guide_slug": row["guide_slug"],
        "region": row["region"],
        "neuro_relevance": row["neuro_relevance"],
        "aliases": aliases,
        "clearance_metadata": clearance,
        "dimensions": dimensions,
        "attributes": attributes,
        "raw_record_count": len(raw_ids),
        "raw_record_ids": raw_ids,
        "review_status": "review_required",
        "size_variant": "dimensions-as-listed",
        "source_locator": row["source_locator"],
        "source_file": row["pdf_filename"],
        "source_sha256": row["pdf_sha256"],
    }


def iter_rows(rows_dir: Path = ROWS_DIR) -> Iterable[dict[str, Any]]:
    for path in sorted(rows_dir.glob("*.rows.jsonl")):
        for row in read_jsonl(path):
            # Map normalized field -> printed header for quotes.
            header_by_field: dict[str, str] = {}
            from ..extraction.evt_guide_pdf import normalize_header
            for printed in row.get("raw_cells", {}):
                header_by_field[normalize_header(printed)] = printed
            row["raw_cells_header"] = header_by_field
            yield row


def build_candidates(rows_dir: Path = ROWS_DIR, output: Path = DEFAULT_OUTPUT,
                     *, include_peripheral: bool = False) -> dict[str, Any]:
    index = load_enriched_index()
    candidates: list[dict[str, Any]] = []
    dropped = Counter()
    review_rows: dict[str, list[dict[str, Any]]] = {}
    for row in iter_rows(rows_dir):
        if row["neuro_relevance"] == "peripheral" and not include_peripheral:
            dropped["peripheral"] += 1
            continue
        candidate = build_candidate(row, index)
        if not candidate["dimensions"] and not candidate["attributes"]:
            dropped["empty"] += 1
            continue
        candidates.append(candidate)
        review_rows.setdefault(f"{row['region'].lower()}-{row['guide_slug']}", []).append({
            "candidate_id": candidate["candidate_id"],
            "device_name": candidate["device_name"],
            "manufacturer_display": candidate["manufacturer_display"],
            "device_entry": candidate["device_entry"],
            "matched_record_ids": candidate["raw_record_ids"],
            "neuro_relevance": candidate["neuro_relevance"],
            "dimension_keys": sorted(candidate["dimensions"]),
            "source_locator": candidate["source_locator"],
        })
    candidates.sort(key=lambda c: c["candidate_id"])
    write_jsonl(output, candidates)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in review_rows.items():
        write_jsonl(REVIEW_DIR / f"{name}.review.jsonl", rows)
    return {
        "candidates": len(candidates),
        "matched_existing": sum(c["device_entry"] == "existing" for c in candidates),
        "dropped": dict(dropped),
        "output": str(output),
    }


def main() -> int:
    summary = build_candidates()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
