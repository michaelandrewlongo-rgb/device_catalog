"""Tier 3: Multi-source enrichment synthesis.

For each device, merge data from all available sources (scraper, FDA summary,
UDI, EVToday, NSPR, document extraction) and fill remaining gaps via DeepSeek.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import CATALOG_ROOT, DATA_DIR, EXTRACTED_DIR, ENRICHED_DIR
from .deepseek import deepseek_extract

logger = logging.getLogger(__name__)

CONTENT_FIELDS = [
    "what_it_is",
    "sizing_specs",
    "indications",
    "contraindications",
    "compatible_with",
    "use_notes",
    "also_known_as",
]

RECONCILIATION_PROMPT = """You are reconciling medical device data from multiple sources.
Do NOT invent information. If sources conflict, prefer the more specific/regulatory source.
If no source provides the information, return null.

Device: {device_name} by {manufacturer}
Field needed: {field_name}

Source 1 (FDA 510k summary): {src_fda}
Source 2 (FDA UDI database): {src_udi}
Source 3 (EVToday device guide): {src_evtoday}
Source 4 (NSPR product review): {src_nspr}
Source 5 (manufacturer document): {src_doc}
Source 6 (manufacturer website): {src_scraper}
Source 7 (FDA safety data): {src_safety}

Return a JSON object with one key "{field_name}" containing the best value, or null."""


def enrich_all() -> list[dict]:
    """Run enrichment across all merged device records."""
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)

    merged_dir = DATA_DIR / "merged"
    if not merged_dir.exists():
        logger.error("No merged directory. Run --merge-only first.")
        return []

    results = []
    for f in sorted(merged_dir.glob("*.json")):
        merged = json.loads(f.read_text(encoding="utf-8"))
        stem = f.stem

        # Skip devices that already have curated knowledge files
        if (CATALOG_ROOT / f"{stem}--knowledge.md").exists():
            logger.info("  Skip (curated): %s", stem)
            continue

        enriched = _enrich_device(stem, merged)
        out_file = ENRICHED_DIR / f"{stem}.json"
        out_file.write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        results.append(enriched)

    logger.info("Enriched: %d devices", len(results))
    return results


def _enrich_device(stem: str, merged: dict) -> dict:
    """Enrich a single device by merging all available sources."""
    sources = gather_sources(stem, merged)
    enrichment_log: dict = {}

    for field in CONTENT_FIELDS:
        value, source_name, confidence = resolve_field(field, sources)
        if value is not None:
            merged[field] = value
            enrichment_log[field] = {"source": source_name, "confidence": confidence}
        else:
            enrichment_log[field] = {"source": "none", "confidence": 0}

    # Safety annotations
    safety = sources.get("safety")
    if safety:
        annotate_safety(merged, safety)
        enrichment_log["_safety"] = {
            "source": "fda_maude+recalls",
            "confidence": 0.85,
        }

    merged["_enrichment"] = enrichment_log
    return merged


def gather_sources(stem: str, merged: dict) -> dict:
    """Gather all available data sources for a device."""
    sources: dict = {"merged": merged}

    # Tier 1A: FDA summary extraction
    k = merged.get("clearance_number", "")
    if k:
        fda_path = EXTRACTED_DIR / "fda_summaries" / f"{k}.json"
        if fda_path.exists():
            sources["fda_summary"] = json.loads(
                fda_path.read_text(encoding="utf-8")
            )
    # Also check by stem (fda_parser saves as {stem}--510k.json)
    if "fda_summary" not in sources:
        stem_fda = EXTRACTED_DIR / "fda_summaries" / f"{stem}--510k.json"
        if stem_fda.exists():
            sources["fda_summary"] = json.loads(
                stem_fda.read_text(encoding="utf-8")
            )

    # Tier 1B: UDI structured data
    udi_path = EXTRACTED_DIR / "fda_structured" / f"{stem}.json"
    if udi_path.exists():
        sources["udi"] = json.loads(udi_path.read_text(encoding="utf-8"))

    # Tier 1B: Safety data
    safety: dict = {}
    maude_path = EXTRACTED_DIR / "fda_safety" / f"{stem}-maude.json"
    recalls_path = EXTRACTED_DIR / "fda_safety" / f"{stem}-recalls.json"
    if maude_path.exists():
        safety["maude"] = json.loads(maude_path.read_text(encoding="utf-8"))
    if recalls_path.exists():
        safety["recalls"] = json.loads(recalls_path.read_text(encoding="utf-8"))
    if safety:
        sources["safety"] = safety

    # Tier 1C: EVToday
    evt_match = find_evtoday_match(stem, merged)
    if evt_match:
        sources["evtoday"] = evt_match

    # Tier 1D: NSPR
    nspr_match = find_nspr_match(stem, merged)
    if nspr_match:
        sources["nspr"] = nspr_match

    # Tier 2: Document extraction
    doc_dir = EXTRACTED_DIR / "documents"
    if doc_dir.exists():
        for doc_file in doc_dir.glob(f"*{stem}*"):
            sources["document"] = json.loads(
                doc_file.read_text(encoding="utf-8")
            )
            break

    return sources


def resolve_field(
    field: str, sources: dict
) -> tuple[str | list | None, str, float]:
    """Walk priority chain to resolve a field value."""
    # Priority 1: Tier 1A FDA summary (0.9+)
    fda = sources.get("fda_summary", {})
    fda_fields = fda.get("fields", {})
    fda_conf = fda.get("confidence", {})
    if fda_fields.get(field) and fda_conf.get(field, 0) >= 0.9:
        return fda_fields[field], "fda_summary", fda_conf[field]

    # Priority 2: Tier 1B UDI (0.85+)
    udi = sources.get("udi", {})
    udi_fields = udi.get("fields", {})
    udi_conf = udi.get("confidence", {})
    if udi_fields.get(field) and udi_conf.get(field, 0) >= 0.85:
        return udi_fields[field], "fda_udi", udi_conf[field]

    # Priority 3: Tier 1D NSPR (0.8)
    nspr = sources.get("nspr", {})
    nspr_fields = nspr.get("fields", {})
    if nspr_fields.get(field):
        return nspr_fields[field], "nspr", 0.8

    # Priority 4: Tier 1C EVToday (0.8)
    evt = sources.get("evtoday", {})
    evt_fields = evt.get("fields", {})
    if evt_fields.get(field):
        return evt_fields[field], "evtoday", 0.8

    # Priority 5: Tier 2 document extraction (0.6+)
    doc = sources.get("document", {})
    doc_fields = doc.get("fields", {})
    doc_conf = doc.get("confidence", {})
    if doc_fields.get(field) and doc_conf.get(field, 0) >= 0.6:
        return doc_fields[field], "document", doc_conf[field]

    # Priority 6: Existing scraper/merged data
    merged_val = sources.get("merged", {}).get(field)
    if merged_val:
        return merged_val, "scraper", 0.5

    # Priority 7: Any lower-confidence data from any source
    for src_key, src_data in [
        ("fda_summary", fda_fields),
        ("udi", udi_fields),
        ("document", doc_fields),
    ]:
        if src_data.get(field):
            return src_data[field], src_key, 0.3

    return None, "none", 0


# Manufacturer alias mapping for cross-source matching
_MFR_ALIASES: dict[str, set[str]] = {
    "medtronic": {"medtronic", "medtronic neurovascular", "ev3"},
    "stryker": {"stryker", "stryker neurovascular", "stryker-k2m", "k2m"},
    "microvention": {"microvention", "terumo neuro", "terumo"},
    "penumbra": {"penumbra", "penumbra, inc.", "penumbra, inc. (neuro)"},
    "cerenovus": {"cerenovus", "j&j", "johnson & johnson"},
    "balt": {"balt", "balt usa"},
    "phenox": {"phenox"},
    "integra": {"integra", "integra lifesciences"},
    "depuy": {"depuy", "depuy synthes", "j&j medtech (depuy synthes)"},
    "globus": {"globus", "globus medical", "nuvasive (globus)"},
    "nuvasive": {"nuvasive", "nuvasive (globus)", "globus medical"},
    "si-bone": {"si-bone", "si-bone, inc", "si-bone, inc."},
    "rapid-medical": {"rapid medical", "rapid"},
    "boston-scientific": {"boston scientific", "boston scientific corporation"},
    "cordis": {"cordis"},
    "imperative-care-inc": {"imperative care", "imperative care (stroke)"},
}


def manufacturer_matches(our_mfr: str, external_co: str) -> bool:
    """Check if our canonical manufacturer slug matches an external company name."""
    external_lower = external_co.lower().strip()

    # Direct substring check
    if our_mfr in external_lower or external_lower in our_mfr:
        return True

    # Check alias table
    aliases = _MFR_ALIASES.get(our_mfr, set())
    for alias in aliases:
        if alias in external_lower or external_lower in alias:
            return True

    return False


def find_evtoday_match(stem: str, merged: dict) -> dict | None:
    """Find matching EVToday device entry.

    Requires manufacturer match plus product name similarity to avoid
    cross-category false positives (e.g., aspiration catheter matching
    a balloon catheter entry on generic words like 'system').
    """
    evtoday_dir = EXTRACTED_DIR / "evtoday"
    if not evtoday_dir.exists():
        return None

    device_name = (merged.get("device_name") or "").lower()
    manufacturer = (merged.get("manufacturer") or "").lower()

    # Stop words that shouldn't count as meaningful overlap
    stop_words = {
        "system", "device", "catheter", "medical", "the", "and", "for",
        "with", "inc", "llc", "ltd", "coil", "stent", "balloon",
        "aspiration", "revascularization", "detachable", "embolization",
    }

    best_match = None
    best_score = 0

    for cat_file in evtoday_dir.glob("*.json"):
        data = json.loads(cat_file.read_text(encoding="utf-8"))
        for entry in data.get("devices", []):
            entry_name = (entry.get("Product Name") or "").lower()
            entry_co = (entry.get("Company Name") or "").lower()

            # Require manufacturer match
            if not manufacturer_matches(manufacturer, entry_co):
                continue

            # Score by meaningful word overlap (excluding stop words)
            name_words = set(device_name.split()) - stop_words
            entry_words = set(entry_name.split()) - stop_words
            overlap = len(name_words & entry_words)

            if overlap >= 2 and overlap > best_score:
                best_score = overlap
                best_match = entry

    if best_match:
        return {"fields": map_evtoday(best_match)}
    return None


def find_nspr_match(stem: str, merged: dict) -> dict | None:
    """Find matching NSPR product detail.

    Requires manufacturer match plus product name similarity.
    """
    nspr_dir = EXTRACTED_DIR / "nspr"
    if not nspr_dir.exists():
        return None

    device_name = (merged.get("device_name") or "").lower()
    manufacturer = (merged.get("manufacturer") or "").lower()

    stop_words = {
        "system", "device", "spinal", "spine", "medical", "the", "and",
        "for", "with", "inc", "llc", "pedicle", "screw", "cage",
        "interbody", "spacer", "plate", "fixation",
    }

    best_match = None
    best_score = 0

    for f in nspr_dir.glob("*.json"):
        if f.name.startswith("_") or f.name == "pdfs_index.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        nspr_name = (data.get("device_name") or data.get("name") or "").lower()
        nspr_co = (data.get("manufacturer") or data.get("company") or "").lower()

        # Require manufacturer match
        if not manufacturer_matches(manufacturer, nspr_co):
            continue

        name_words = set(device_name.split()) - stop_words
        nspr_words = set(nspr_name.split()) - stop_words
        overlap = len(name_words & nspr_words)

        if overlap >= 2 and overlap > best_score:
            best_score = overlap
            best_match = data

    if best_match:
        return {"fields": map_nspr(best_match)}

    return None


def map_evtoday(entry: dict) -> dict:
    """Map EVToday table columns to ScrapedProduct fields."""
    fields: dict = {}

    ind = entry.get("US FDA Indicated Use")
    if ind:
        fields["indications"] = ind

    sizing_parts = []
    sizing_keys = [
        "Stent Diameters (mm)", "Stent Lengths (mm)", "Stent Diameter (mm)",
        "Stent Length (mm)", "Device Diameter (mm)", "Device Height (mm)",
        "Size (F)", "Length (cm)", "Internal Diameter (inch)",
        "Proximal Size (F)", "Distal Size (F)", "Catheter Working Length (cm)",
        "Balloon Diameters (mm)", "Balloon Lengths (mm)",
        "Maximum Tip Diameter (mm)", "Catheter Length (cm)",
        "Sheath Compatibility (F)", "Working Length (cm)",
        "Proximal OD (F)", "Distal OD (F)",
    ]
    for key in sizing_keys:
        val = entry.get(key)
        if val:
            sizing_parts.append(f"{key}: {val}")
    mat = entry.get("Materials Used")
    if mat:
        sizing_parts.append(f"Materials: {mat}")
    if sizing_parts:
        fields["sizing_specs"] = "\n".join(sizing_parts)

    cmt = entry.get("Comments")
    if cmt:
        fields["what_it_is"] = cmt

    notes_parts = []
    for key in ["Mode of Operation", "Method of Detachment", "Coil Type", "Type"]:
        val = entry.get(key)
        if val:
            notes_parts.append(f"{key}: {val}")
    if notes_parts:
        fields["use_notes"] = "\n".join(notes_parts)

    return fields


def map_nspr(data: dict) -> dict:
    """Map NSPR product detail to ScrapedProduct fields."""
    fields: dict = {}

    desc = data.get("description")
    if desc:
        fields["what_it_is"] = desc

    specs = data.get("specs", {})
    sizing_parts = []
    if specs.get("BY MATERIAL"):
        sizing_parts.append(f"Material: {specs['BY MATERIAL']}")
    if specs.get("FEATURES"):
        sizing_parts.append(f"Features: {specs['FEATURES']}")
    if sizing_parts:
        fields["sizing_specs"] = "\n".join(sizing_parts)

    if specs.get("BY PROCEDURE TYPE"):
        fields["use_notes"] = f"Procedures: {specs['BY PROCEDURE TYPE']}"

    features = data.get("features")
    if features:
        existing = fields.get("what_it_is", "")
        if existing:
            existing += "\n\n"
        fields["what_it_is"] = (
            existing + "Features:\n" + "\n".join(f"- {f}" for f in features)
        )

    return fields


def annotate_safety(merged: dict, safety: dict) -> None:
    """Add safety annotations to use_notes from MAUDE/recall data."""
    notes = merged.get("use_notes") or ""

    maude = safety.get("maude")
    if maude and maude.get("total_events", 0) > 0:
        counts = maude["event_counts"]
        summary = ", ".join(f"{k}: {v}" for k, v in counts.items())
        notes += (
            f"\n\n[FDA MAUDE] {maude['total_events']} adverse event reports"
            f" ({summary})."
        )

    recalls = safety.get("recalls")
    if recalls:
        active = [r for r in recalls if r.get("status") != "Terminated"]
        if active:
            notes += f"\n\n[FDA RECALL] {len(active)} active recall(s)."
            for r in active[:2]:
                reason = r.get("reason", "")[:200]
                notes += f"\n  - {reason}"

    if notes != (merged.get("use_notes") or ""):
        merged["use_notes"] = notes.strip()
