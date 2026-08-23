"""Promote audited Endovascular Today guide rows to actionable claims.

A secondary candidate becomes a claim only when an audit record says its row was
reopened in the retained PDF and every observation matched the cell. The audit
results live in ``pipeline/knowledge_v2/data/evt_guide_audit.jsonl`` (one record per
candidate_id: grade PASS/FAIL, auditor, date, failures). Rows without a PASS stay in
``device_dimension_candidates.v2.jsonl`` as secondary observations.

For each PASS candidate this writes:

- a source record per (guide PDF, device) - the schema ties a source to one device
  and the downstream gate requires ``source.device_id == claim.device_id`` - with
  ``source_type: trade_journal_device_guide``, ``local_full_text``, and the PDF hash;
- one ``claim_type: device_specifications`` claim at the
  ``trade_journal_device_guide`` evidence layer carrying the listed dimensions (as
  printed: single values, lists, ranges, or prose quotes), the non-marketing
  attributes, a page/row locator, and ``review_status: source_checked``.

Derived French-to-inch values are never promoted; they stay in the candidate file as
``derived_calculation``.

    python -m pipeline.knowledge_v2.promote_guide_rows
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl, write_json, write_jsonl

DATA = Path(__file__).resolve().parent / "data"
CANDIDATES = DATA / "device_dimension_candidates.v2.jsonl"
AUDIT = DATA / "evt_guide_audit.jsonl"
REGISTRY = DATA / "source_registry.json"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"
GUIDE_URLS = {
    "US": "https://evtoday.com/device-guide/us/{slug}",
    "EUROPEAN": "https://evtoday.com/device-guide/european/{slug}",
}


def load_audit() -> dict[str, dict[str, Any]]:
    return {row["candidate_id"]: row for row in read_jsonl(AUDIT)}


def source_for(candidate: dict[str, Any]) -> dict[str, Any]:
    region = candidate["region"]
    slug = candidate["guide_slug"]
    obs = next(iter(candidate["dimensions"].values()))[0] if candidate["dimensions"] else {}
    title = obs.get("source_title") or candidate["source_locator"].split(" (")[0]
    return {
        "source_id": f"evt:{region.lower()}-{slug}:2026-08:{candidate['device_id']}",
        "device_id": candidate["device_id"],
        "title": f"{title} (2026-08 export), row for {candidate['manufacturer_display']} / {candidate['device_name']}",
        "source_type": "trade_journal_device_guide",
        "status": "current",
        "evidence_depth": "local_full_text",
        "jurisdiction": "EU" if region == "EUROPEAN" else "US",
        "document_id": f"EVT-{region}-{slug}",
        "revision": "2026-08 export",
        "official_url": GUIDE_URLS[region].format(slug=slug),
        "local_filename": candidate["source_file"],
        "sha256": candidate["source_sha256"],
        "identity": {"required_any": [candidate["device_name"]]},
        "notes": (
            "Endovascular Today device-guide comparison table; manufacturer-submitted data retained as a "
            "hashed PDF and audited row by row. Outranked by an IFU, FDA labeling, or manufacturer "
            "specification on conflict. evtoday.com is not on the official-domain allowlist, so currency "
            "is revalidated by re-exporting the guide."
        ),
    }


def describe(dimension: str, items: list[dict[str, Any]]) -> str:
    parts = []
    for item in items:
        if item.get("evidence_class") != "secondary_curated_catalog":
            continue
        unit = item.get("unit", "")
        if item.get("parse") == "list":
            values = item.get("values") or ([item["value"]] if item.get("value") is not None else [])
            parts.append(f"{dimension.replace('_', ' ')}: {', '.join(f'{v:g}' for v in values)} {unit}".strip())
        elif item.get("parse") == "range":
            lo, hi = item["range"]
            parts.append(f"{dimension.replace('_', ' ')}: {lo:g}-{hi:g} {unit} (range as printed)")
        elif item.get("parse") == "pairs":
            pairs = ", ".join(f"{a:g}/{b:g}" for a, b in item["pairs"])
            parts.append(f"{dimension.replace('_', ' ')}: {pairs} {unit} (pairs as printed)")
        else:
            cell = item["quote"].split(": ", 2)[-1]
            parts.append(f"{dimension.replace('_', ' ')} as printed: \"{cell}\"")
    return "; ".join(parts)


def claim_for(candidate: dict[str, Any], source: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    dims: dict[str, Any] = {}
    for key, items in candidate["dimensions"].items():
        kept = [
            {k: v for k, v in item.items() if k in ("value", "values", "range", "pairs", "unit", "unit_conflict", "header_unit", "parse", "meaning", "quote", "pdf_page")}
            for item in items
            if item.get("evidence_class") == "secondary_curated_catalog"
        ]
        if kept:
            dims[key] = kept
    attributes = {k: v["text"] for k, v in candidate.get("attributes", {}).items()}
    summary = "; ".join(filter(None, [describe(k, v) for k, v in candidate["dimensions"].items()]))
    attr_text = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in attributes.items())
    text = f"{candidate['manufacturer_display']} {candidate['device_name']} as listed in the {source['title'].split(' (')[0]}"
    if summary:
        text += f" - {summary}"
    if attr_text:
        text += f". {attr_text}"
    return {
        "claim_id": f"claim:evt-guide:{candidate['candidate_id'].split(':', 1)[1]}",
        "device_id": candidate["device_id"],
        "device_name": candidate["device_name"],
        "manufacturer": candidate["manufacturer"],
        "catalog_category": candidate["catalog_category"],
        "claim_type": "device_specifications",
        "evidence_layer": "trade_journal_device_guide",
        "evidence_class": "trade_journal_device_guide",
        "support": "direct",
        "review_status": "source_checked",
        "review_note": f"Row reopened in the retained PDF by {audit.get('auditor', 'independent auditor')} on {audit.get('date', '')}; every observation matched the cell.",
        "source_ids": [source["source_id"]],
        "locators": [candidate["source_locator"]],
        "checked_at": audit.get("date", "2026-08-23"),
        "jurisdiction": source["jurisdiction"],
        "dimensions": dims,
        "attributes": attributes,
        "aliases": candidate.get("aliases", []),
        "size_variant": candidate.get("size_variant", "dimensions-as-listed"),
        "text": text,
    }


def promote() -> dict[str, int]:
    audit = load_audit()
    candidates = read_jsonl(CANDIDATES)
    registry = read_json(REGISTRY)
    have_sources = {s["source_id"] for s in registry["sources"]}
    existing_claims = read_jsonl(CLAIMS)
    have_claims = {c["claim_id"] for c in existing_claims}
    promoted = 0
    remaining: list[dict[str, Any]] = []
    new_sources: list[dict[str, Any]] = []
    new_claims: list[dict[str, Any]] = []
    for candidate in candidates:
        verdict = audit.get(candidate["candidate_id"])
        if not verdict or verdict.get("grade") != "PASS" or not (candidate["dimensions"] or candidate.get("attributes")):
            remaining.append(candidate)
            continue
        source = source_for(candidate)
        if source["source_id"] not in have_sources:
            new_sources.append(source)
            have_sources.add(source["source_id"])
        claim = claim_for(candidate, source, verdict)
        if claim["claim_id"] not in have_claims:
            new_claims.append(claim)
            have_claims.add(claim["claim_id"])
        candidate = dict(candidate)
        candidate["promoted_claim_id"] = claim["claim_id"]
        promoted += 1
        # Keep the derived (French-to-inch) observations discoverable as candidates;
        # drop the quoted ones, which now live in the claim.
        derived = {k: [i for i in v if i.get("evidence_class") == "derived_calculation"] for k, v in candidate["dimensions"].items()}
        candidate["dimensions"] = {k: v for k, v in derived.items() if v}
        if candidate["dimensions"]:
            remaining.append(candidate)
    registry["sources"].extend(new_sources)
    write_json(REGISTRY, registry)
    with CLAIMS.open("a", encoding="utf-8", newline="\n") as handle:
        for claim in new_claims:
            handle.write(json.dumps(claim, sort_keys=True, separators=(",", ":")) + "\n")
    write_jsonl(CANDIDATES, remaining)
    return {"promoted": promoted, "new_sources": len(new_sources), "new_claims": len(new_claims), "candidates_remaining": len(remaining)}


if __name__ == "__main__":
    print(json.dumps(promote(), indent=2))
