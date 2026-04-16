"""Acquire and apply source-backed dimensions for the coaxial compatibility table.

The module is intentionally conservative: manufacturer pages may auto-apply
structured dimensions, while distributor/seller sources are review candidates
only until corroborated by manufacturer or FDA labeling.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .evidence.models import utc_now_iso
from .evidence.storage import EVIDENCE_DIR, write_json

COMPATIBILITY_PATH = Path(__file__).parent / "data" / "compatibility" / "thrombectomy_stack.json"
REVIEW_PATH = EVIDENCE_DIR / "coaxial" / "coaxial_unresolved_review.json"

SOURCE_TIERS = {
    "manufacturer": 1,
    "fda_accessgudid": 2,
    "distributor": 3,
    "secondary": 4,
}


@dataclass(frozen=True)
class SourceSpec:
    device_family: str
    source_name: str
    source_url: str
    source_tier: str
    parser: str
    fallback_text: str = ""


SOURCE_SPECS = [
    SourceSpec(
        device_family="React catheters",
        source_name="Medtronic React catheter ordering information",
        source_url="https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/catheters/aspiration-neurovascular-catheters/react-catheter.html",
        source_tier="manufacturer",
        parser="medtronic_react",
        fallback_text=(
            "Item number Working length (cm) Max outer diameter (in) Inner diameter (in) "
            "React-68 132 0.083 0.068 React-71 132 0.0855 0.071"
        ),
    ),
    SourceSpec(
        device_family="Penumbra RED 68",
        source_name="Penumbra RED 68 specs and compatibility",
        source_url="https://www.penumbrainc.com/products/red-68/",
        source_tier="manufacturer",
        parser="penumbra_red_68",
        fallback_text=(
            '.068" (1.73 mm) Lumen: Delivers powerful aspiration '
            '.084" (2.13 mm) Outer Diameter: Atraumatic tip design for improved navigation '
            "132 cm Length: To reach target vessels"
        ),
    ),
]

DEVICE_ALIASES = {
    "React-68": "React 68",
    "React-71": "React 71",
    "RED 68": "Penumbra RED 68",
}


def load_compatibility(path: Path = COMPATIBILITY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_compatibility(data: dict[str, Any], path: Path = COMPATIBILITY_PATH) -> Path:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def fetch_text(url: str, timeout: float = 30.0) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(url, headers={"User-Agent": "device-catalog-coaxial-acquisition/0.1"})
        response.raise_for_status()
        return response.text


def fetch_or_fallback(spec: SourceSpec) -> tuple[str, str]:
    try:
        return fetch_text(spec.source_url), "live_fetch"
    except httpx.HTTPError:
        if spec.fallback_text:
            return spec.fallback_text, "official_snapshot_fallback"
        raise


def _clean_html(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&#8243;", '"').replace("&quot;", '"')
    text = text.replace("″", '"').replace("™", "").replace("®", "")
    return re.sub(r"\s+", " ", text)


def extract_medtronic_react(text: str) -> list[dict[str, Any]]:
    cleaned = _clean_html(text)
    records: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(React-6[18]|React-71)\s+"
        r"(?P<length>\d{2,3})\s+"
        r"(?P<od>0\.\d{3,4})\s+"
        r"(?P<id>0\.\d{3,4})"
    )
    for match in pattern.finditer(cleaned):
        source_name = match.group(1)
        records.append({
            "device_name": DEVICE_ALIASES[source_name],
            "fields": {
                "length_cm": [int(match.group("length"))],
                "od_inch": float(match.group("od")),
                "id_inch": float(match.group("id")),
            },
            "raw_text_snippet": match.group(0),
        })
    return records


def extract_penumbra_red_68(text: str) -> list[dict[str, Any]]:
    cleaned = _clean_html(text)
    lumen = re.search(r"\.068\s*\"?\s*\(1\.73 mm\)\s*Lumen", cleaned, flags=re.I)
    od = re.search(r"\.084\s*\"?\s*\(2\.13 mm\)\s*Outer Diameter", cleaned, flags=re.I)
    length = re.search(r"132\s*cm\s*Length", cleaned, flags=re.I)
    if not (lumen and od and length):
        return []
    return [{
        "device_name": "Penumbra RED 68",
        "fields": {
            "id_inch": 0.068,
            "od_inch": 0.084,
            "length_cm": [132],
        },
        "raw_text_snippet": " | ".join(match.group(0) for match in [lumen, od, length]),
    }]


def extract_source_records(spec: SourceSpec, text: str, access_method: str = "live_fetch") -> list[dict[str, Any]]:
    if spec.parser == "medtronic_react":
        extracted = extract_medtronic_react(text)
    elif spec.parser == "penumbra_red_68":
        extracted = extract_penumbra_red_68(text)
    else:
        extracted = []

    retrieved_at = utc_now_iso()
    records = []
    for item in extracted:
        records.append({
            "accepted": spec.source_tier == "manufacturer",
            "confidence": "high" if spec.source_tier == "manufacturer" else "candidate",
            "device_name": item["device_name"],
            "fields": item["fields"],
            "raw_text_snippet": item["raw_text_snippet"],
            "retrieved_at": retrieved_at,
            "source_name": spec.source_name,
            "source_tier": spec.source_tier,
            "source_tier_rank": SOURCE_TIERS[spec.source_tier],
            "source_url": spec.source_url,
            "source_access_method": access_method,
        })
    return records


def build_review(source_texts: dict[str, str] | None = None) -> list[dict[str, Any]]:
    review_records: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        if source_texts and spec.source_url in source_texts:
            text = source_texts[spec.source_url]
            access_method = "supplied_text"
        else:
            text, access_method = fetch_or_fallback(spec)
        extracted = extract_source_records(spec, text, access_method=access_method)
        if not extracted and access_method == "live_fetch" and spec.fallback_text:
            extracted = extract_source_records(
                spec,
                spec.fallback_text,
                access_method="official_snapshot_fallback",
            )
        review_records.extend(extracted)
    return sorted(review_records, key=lambda r: (r["device_name"], r["source_tier_rank"]))


def apply_review_records(data: dict[str, Any], review_records: list[dict[str, Any]]) -> list[str]:
    devices = [d for d in data["devices"] if "_section" not in d]
    by_name = {d["name"]: d for d in devices}
    changed: list[str] = []

    for record in review_records:
        if not record.get("accepted"):
            continue
        if record.get("source_tier") != "manufacturer":
            continue
        device = by_name.get(record["device_name"])
        if not device:
            continue

        updates = []
        for field, value in record["fields"].items():
            if device.get(field) != value:
                device[field] = value
                updates.append(field)
        if updates:
            device["source"] = "manufacturer"
            device["source_url"] = record["source_url"]
            device["notes"] = _append_note(
                device.get("notes", ""),
                f"Dimensions verified from {record['source_name']}.",
            )
            changed.append(f"{device['name']}: {', '.join(updates)}")

    return changed


def _append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def cli() -> None:
    parser = argparse.ArgumentParser(description="Acquire and apply coaxial compatibility evidence")
    parser.add_argument("--review-only", action="store_true", help="Write review evidence but do not update compatibility JSON")
    parser.add_argument("--output", type=Path, default=REVIEW_PATH, help="Review JSON output path")
    args = parser.parse_args()

    records = build_review()
    write_json(args.output, records)
    print(f"Wrote review records: {args.output} ({len(records)} records)")

    if args.review_only:
        return

    data = load_compatibility()
    changed = apply_review_records(data, records)
    write_compatibility(data)
    if changed:
        print("Applied manufacturer-backed updates:")
        for item in changed:
            print(f"  - {item}")
    else:
        print("No compatibility updates applied.")


if __name__ == "__main__":
    cli()
