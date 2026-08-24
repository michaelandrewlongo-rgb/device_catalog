"""Deterministic validators for catalog rows, claims, and flat-CSV exports.

Each check returns a list of finding dicts ``{"check", "severity", "ref",
"detail"}`` so callers can decide whether to fail. ``severity`` is ``error``
(regeneration must stop) or ``warn`` (documented residual). Nothing here edits
data; the appliers in ``apply_extraction_corrections`` /
``apply_claim_corrections`` do that, driven by reviewed correction records.

Allowlists carry the evidence for every accepted exception, per the
wrong-is-worse-than-absent rule:
- ``data/catalog_number_allowlist.json`` — catalog numbers legitimately listed
  under more than one device (e.g. a catheter printed in both the access and
  aspiration sections of the same catalog).
- ``data/unit_inconsistency_allowlist.json`` — printed in/mm pairs that do not
  convert exactly *in the source itself* (verified against the PDF page).

    python -m pipeline.run_knowledge_v2 validate
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent / "data"
CATALOG_NUMBER_ALLOWLIST = DATA / "catalog_number_allowlist.json"
UNIT_INCONSISTENCY_ALLOWLIST = DATA / "unit_inconsistency_allowlist.json"

IN_MM_RE = re.compile(r"(\d*\.\d+)\s*(?:in|\")\s*\((\d+(?:\.\d+)?)\s*mm\)")
DECIMAL_COMMA_RE = re.compile(r"\d,\d")
YEAR_RE = re.compile(r"\b(19|20)\d\d\b")
NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")

DATED_LAYERS = {"manufacturer_catalog", "trade_journal_device_guide",
                "official_labeling", "official_specification"}

# Field keys that should never appear in a family of the given category; a hit
# is a strong table-bleed signal (values from a neighboring table landing under
# this family's catalog numbers).
CATEGORY_FORBIDDEN_FIELDS = {
    "intracranial-stent": {"coil_diameter", "vaclok_spheres", "vaclok_syringe_volume",
                           "balloon_diameter", "balloon_length"},
    "embolic-coil": {"balloon_diameter", "balloon_length", "vaclok_syringe_volume"},
    "guidewire": {"coil_diameter", "balloon_diameter", "stent_diameter"},
    "balloon-catheter": {"vaclok_syringe_volume", "stent_diameter", "stent_length"},
    "microcatheter": {"balloon_diameter", "stent_diameter", "vaclok_syringe_volume"},
}


def finding(check: str, severity: str, ref: str, detail: str) -> dict[str, str]:
    return {"check": check, "severity": severity, "ref": ref, "detail": detail}


def _load_allowlist(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def sku_shape(catalog_number: str) -> str:
    """Structural signature of a catalog number (letters/digits/dashes)."""
    return re.sub(r"[A-Z]+", "A", re.sub(r"\d+", "9", (catalog_number or "").upper()))


# ---------------------------------------------------------------------------
# Claim-level checks (reviewed_claims.v2.jsonl)
# ---------------------------------------------------------------------------

def find_duplicate_catalog_numbers(claims: list[dict[str, Any]],
                                   allowlist: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Same manufacturer + catalog number under two or more device_ids."""
    if allowlist is None:
        allowlist = _load_allowlist(CATALOG_NUMBER_ALLOWLIST)
    allowed = {(a["manufacturer"], a["catalog_number"]): set(a["device_ids"]) for a in allowlist}
    by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    for claim in claims:
        manufacturer = claim.get("manufacturer", "")
        for sku in claim.get("skus") or []:
            number = (sku.get("catalog_number") or "").strip()
            if number:
                by_key[(manufacturer, number)].add(claim["device_id"])
    findings = []
    for (manufacturer, number), device_ids in sorted(by_key.items()):
        if len(device_ids) < 2:
            continue
        if device_ids <= allowed.get((manufacturer, number), set()):
            continue
        findings.append(finding(
            "duplicate_catalog_number", "error", f"{manufacturer}/{number}",
            f"listed under {sorted(device_ids)}; verify against the PDF and either "
            "correct the extraction or add an evidenced allowlist entry"))
    return findings


def check_vendor_casing(rows: list[dict[str, Any]], ref_key: str = "claim_id") -> list[dict[str, str]]:
    """Manufacturer must be its canonical lowercase slug.

    Claims keep the manufacturer as printed by their source; the export
    normalizes via ``config.normalize_manufacturer``, so this runs on CSV rows
    (post-normalization it must be clean) rather than on the masters.
    """
    findings = []
    for row in rows:
        manufacturer = row.get("manufacturer", "")
        slug = re.sub(r"[^a-z0-9]+", "-", manufacturer.lower()).strip("-")
        if manufacturer and manufacturer != slug:
            findings.append(finding("vendor_casing", "error", row.get(ref_key, "?"),
                                    f"manufacturer {manufacturer!r} is not the canonical slug {slug!r}"))
    return findings


# ---------------------------------------------------------------------------
# Extraction-level checks (pipeline/data/extracted/<set>.rows.jsonl)
# ---------------------------------------------------------------------------

# extraction set -> manufacturer, for allowlist lookups on raw rows
SET_MANUFACTURERS = {
    "stryker_catalog_2024": "stryker",
    "microvention_catalog_2019_intl": "microvention",
    "medtronic_catalog_2019": "medtronic",
    "balt_catalog_2020_intl": "balt",
    "penumbra_brochure_2025": "penumbra",
}


def find_bleed_candidates(rows_by_set: dict[str, list[dict[str, Any]]],
                          allowlist: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Rows likely contaminated by a neighboring catalog table.

    Signals, per extraction set:
    a) the same catalog number under two or more product families;
    b) a catalog number whose structural shape is unique in its family but is
       the dominant shape of another family in the same set;
    c) field keys forbidden for the family's category (a syringe-kit column
       under a stent family).
    """
    from .ingest_manufacturer_catalog import family_category

    if allowlist is None:
        allowlist = _load_allowlist(CATALOG_NUMBER_ALLOWLIST)
    allowed_numbers = {(a["manufacturer"], a["catalog_number"]) for a in allowlist}

    findings = []
    for set_name, rows in rows_by_set.items():
        manufacturer = SET_MANUFACTURERS.get(set_name, "")
        families: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            families[row.get("product_family", "")].append(row)

        number_families: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            number = (row.get("catalog_number") or "").strip()
            if number:
                number_families[number].add(row.get("product_family", ""))
        for number, fams in sorted(number_families.items()):
            if len(fams) > 1 and (manufacturer, number) not in allowed_numbers:
                findings.append(finding(
                    "bleed_shared_catalog_number", "error", f"{set_name}:{number}",
                    f"catalog number appears under families {sorted(fams)}"))

        shape_by_family = {
            family: {sku_shape(r.get("catalog_number", "")) for r in frows}
            for family, frows in families.items()
        }
        dominant = {}
        for family, frows in families.items():
            counts: dict[str, int] = defaultdict(int)
            for r in frows:
                counts[sku_shape(r.get("catalog_number", ""))] += 1
            if counts:
                dominant[family] = max(counts, key=lambda s: counts[s])
        for family, frows in families.items():
            if len(frows) < 3:
                continue
            counts: dict[str, int] = defaultdict(int)
            for r in frows:
                counts[sku_shape(r.get("catalog_number", ""))] += 1
            for r in frows:
                shape = sku_shape(r.get("catalog_number", ""))
                if counts[shape] > 1 or shape == dominant.get(family):
                    continue
                donors = [f for f, s in dominant.items() if f != family and s == shape]
                if donors:
                    # Review lead only: legitimate one-off references (accessory
                    # cables, docking wires) routinely have singleton shapes.
                    findings.append(finding(
                        "bleed_shape_outlier", "warn",
                        f"{set_name}:{family}:{r.get('catalog_number')}",
                        f"catalog-number shape {shape!r} is a singleton here but the dominant "
                        f"shape of {donors}; pdf_page {r.get('pdf_page')}"))

        for family, frows in families.items():
            category = family_category(family, frows[0].get("section", ""))
            forbidden = CATEGORY_FORBIDDEN_FIELDS.get(category, set())
            if not forbidden:
                continue
            for r in frows:
                hit = forbidden & set(r.get("fields", {}))
                if hit:
                    findings.append(finding(
                        "bleed_implausible_fields", "error",
                        f"{set_name}:{family}:{r.get('catalog_number')}",
                        f"category {category} row carries {sorted(hit)}; pdf_page {r.get('pdf_page')}"))
    return findings


def check_in_mm_consistency(rows_by_set: dict[str, list[dict[str, Any]]],
                            allowlist: list[dict[str, Any]] | None = None,
                            tolerance_mm: float = 0.1) -> list[dict[str, str]]:
    """Printed ``X in (Y mm)`` pairs must convert within tolerance.

    A confirmed printed-in-source inconsistency belongs in the allowlist with
    the PDF evidence, never silently corrected: the value is what the source
    printed.
    """
    if allowlist is None:
        allowlist = _load_allowlist(UNIT_INCONSISTENCY_ALLOWLIST)
    allowed = {(a["set"], a["catalog_number"], a["field"]) for a in allowlist}
    findings = []
    for set_name, rows in rows_by_set.items():
        for row in rows:
            for key, value in (row.get("fields") or {}).items():
                if not isinstance(value, str):
                    continue
                for match in IN_MM_RE.finditer(value):
                    inches, mm = float(match.group(1)), float(match.group(2))
                    # A source that prints one decimal has rounded; compare at
                    # the printed precision before calling it inconsistent.
                    decimals = len(match.group(2).split(".")[1]) if "." in match.group(2) else 0
                    if abs(round(inches * 25.4, decimals) - mm) <= tolerance_mm:
                        continue
                    ref = (set_name, row.get("catalog_number", ""), key)
                    if ref in allowed:
                        continue
                    findings.append(finding(
                        "in_mm_mismatch", "error", ":".join(ref),
                        f"{value!r}: {inches} in = {inches * 25.4:.2f} mm, printed {mm} mm; "
                        f"pdf_page {row.get('pdf_page')}"))
    return findings


# ---------------------------------------------------------------------------
# CSV-row checks (flat export rows, before writing)
# ---------------------------------------------------------------------------

DIMENSION_COLUMNS = [
    "diameter", "inner_diameter", "outer_diameter", "distal_outer_diameter",
    "proximal_outer_diameter", "middle_outer_diameter", "length", "wire_diameter",
    "coil_diameter", "implant_size", "stent_diameter", "stent_length",
    "vessel_diameter", "balloon_diameter", "balloon_length",
]

MM_RE = re.compile(r"([\d.]+)\s*mm\b")
INCH_RE = re.compile(r"([\d.]+)\s*(?:in\b|\")")


def _single_mm(text: str) -> float | None:
    """The cell's value in mm, only when the cell is one unambiguous number."""
    text = (text or "").strip()
    mm = MM_RE.findall(text)
    inch = INCH_RE.findall(text)
    if len(mm) == 1 and not text.count(";") and not text.count("/"):
        return float(mm[0])
    if not mm and len(inch) == 1 and not text.count(";") and not text.count("/"):
        return float(inch[0]) * 25.4
    return None


def check_other_fields_json(csv_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for row in csv_rows:
        raw = row.get("other_fields") or ""
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            findings.append(finding("other_fields_json", "error", row.get("claim_id", "?"),
                                    f"not JSON: {raw[:80]!r}"))
            continue
        if not isinstance(parsed, dict):
            findings.append(finding("other_fields_json", "error", row.get("claim_id", "?"),
                                    "parses but is not an object"))
    return findings


def check_source_year(csv_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for row in csv_rows:
        if row.get("evidence_layer") in DATED_LAYERS and not str(row.get("source_year") or "").strip():
            findings.append(finding("source_year_missing", "warn",
                                    row.get("claim_id", "?"),
                                    f"{row.get('evidence_layer')} row has no source_year"))
    return findings


def check_inner_le_outer(csv_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for row in csv_rows:
        inner = _single_mm(row.get("inner_diameter", ""))
        outer = (_single_mm(row.get("outer_diameter", ""))
                 or _single_mm(row.get("distal_outer_diameter", "")))
        if inner is not None and outer is not None and inner > outer + 1e-9:
            findings.append(finding("inner_gt_outer", "error",
                                    f"{row.get('claim_id', '?')}:{row.get('catalog_number', '')}",
                                    f"ID {row.get('inner_diameter')!r} exceeds OD "
                                    f"{row.get('outer_diameter') or row.get('distal_outer_diameter')!r}"))
    return findings


def find_decimal_commas(csv_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    findings = []
    for row in csv_rows:
        for column in DIMENSION_COLUMNS:
            value = str(row.get(column) or "")
            if DECIMAL_COMMA_RE.search(value):
                findings.append(finding("decimal_comma", "error",
                                        f"{row.get('claim_id', '?')}:{column}",
                                        f"unnormalized decimal comma in {value!r}"))
    return findings


def validate_csv_rows(csv_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """All CSV-level checks; exporters call this before writing."""
    findings = []
    findings += check_other_fields_json(csv_rows)
    findings += check_source_year(csv_rows)
    findings += check_inner_le_outer(csv_rows)
    findings += find_decimal_commas(csv_rows)
    findings += check_vendor_casing(csv_rows)
    return findings


def validate_all(claims: list[dict[str, Any]],
                 rows_by_set: dict[str, list[dict[str, Any]]]) -> list[dict[str, str]]:
    findings = []
    findings += find_duplicate_catalog_numbers(claims)
    findings += find_bleed_candidates(rows_by_set)
    findings += check_in_mm_consistency(rows_by_set)
    return findings


def summarize(findings: list[dict[str, str]]) -> dict[str, Any]:
    by_check: dict[str, int] = defaultdict(int)
    for item in findings:
        by_check[item["check"]] += 1
    return {
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warn" for f in findings),
        "by_check": dict(sorted(by_check.items())),
    }
