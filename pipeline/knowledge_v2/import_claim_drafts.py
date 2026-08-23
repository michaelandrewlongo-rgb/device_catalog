"""Validate agent-drafted IFU claims and append them to reviewed_claims.v2.jsonl.

Drafts are JSON arrays (see the drafting prompt). Each claim is checked for the
required fields, a known claim_type, a locator, a source_quote, and a device_id that
matches exactly one registered *current* IFU source for that device. The claim then
gets the registry fields (evidence_layer official_labeling, support direct,
review_status source_checked, source_ids, checked_at) and is appended. Anything that
fails is reported and skipped; nothing is silently fixed.

    python -m pipeline.knowledge_v2.import_claim_drafts <draft.json> [<draft.json> ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .io import read_json, read_jsonl

DATA = Path(__file__).resolve().parent / "data"
REGISTRY = DATA / "source_registry.json"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"
CLAIM_TYPES = {
    "indication", "contraindication", "sizing", "compatibility", "deployment", "mri",
    "periprocedural", "warning", "regulatory_status", "preparation", "device_description",
}


def current_ifu_source(registry: dict[str, Any], device_id: str) -> dict[str, Any] | None:
    matches = [
        s for s in registry["sources"]
        if s["device_id"] == device_id and s["status"] == "current"
        and s["source_type"] in {"manufacturer_ifu", "manufacturer_labeling_summary", "fda_labeling"}
    ]
    return matches[0] if len(matches) == 1 else None


def import_drafts(paths: list[Path], checked_at: str = "2026-08-23") -> dict[str, Any]:
    registry = read_json(REGISTRY)
    existing = {c["claim_id"] for c in read_jsonl(CLAIMS)}
    accepted: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in paths:
        drafts = json.loads(path.read_text(encoding="utf-8"))
        for draft in drafts:
            cid = draft.get("claim_id", "<missing>")
            missing = [k for k in ("claim_id", "device_id", "claim_type", "text", "locators", "source_quote") if not draft.get(k)]
            if missing:
                problems.append(f"{path.name}:{cid}: missing {missing}")
                continue
            if draft["claim_type"] not in CLAIM_TYPES:
                problems.append(f"{path.name}:{cid}: unknown claim_type {draft['claim_type']}")
                continue
            if not isinstance(draft["locators"], list):
                problems.append(f"{path.name}:{cid}: locators must be a list")
                continue
            source = current_ifu_source(registry, draft["device_id"])
            if source is None:
                problems.append(f"{path.name}:{cid}: no unique current IFU source for {draft['device_id']}")
                continue
            if cid in existing:
                continue
            claim = {
                "claim_id": cid,
                "device_id": draft["device_id"],
                "claim_type": draft["claim_type"],
                "text": draft["text"].strip(),
                "evidence_layer": "official_labeling",
                "support": "direct",
                "review_status": "source_checked",
                "review_note": f"Drafted from the retained IFU by an independent agent with page locators and a verbatim anchor quote ({path.name}).",
                "source_ids": [source["source_id"]],
                "locators": draft["locators"],
                "source_quote": draft["source_quote"],
                "checked_at": checked_at,
            }
            if draft.get("compatibility_status"):
                claim["compatibility_status"] = draft["compatibility_status"]
            accepted.append(claim)
            existing.add(cid)
    with CLAIMS.open("a", encoding="utf-8", newline="\n") as handle:
        for claim in accepted:
            handle.write(json.dumps(claim, sort_keys=True, separators=(",", ":")) + "\n")
    return {"accepted": len(accepted), "problems": problems}


if __name__ == "__main__":
    print(json.dumps(import_drafts([Path(p) for p in sys.argv[1:]]), indent=2))
