"""Apply reviewed correction records to the claims master, auditable and idempotent.

For claims that have no upstream extraction master (EVT-guide promotions,
product-page captures), corrections land directly in
``pipeline/knowledge_v2/data/reviewed_claims.v2.jsonl``, driven by
``data/claim_corrections.jsonl``:

    {"match": {"claim_id": "..."}, "set": {"evidence_layer": "..."},
     "evidence": "...", "decided_by": "...", "date": "..."}

A record whose ``set`` values already hold is skipped (idempotent); a record
matching no claim is an error. Git history of the claims file is the change log.

    python -m pipeline.knowledge_v2.apply_claim_corrections [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .io import read_jsonl

DATA = Path(__file__).resolve().parent / "data"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"
CORRECTIONS = DATA / "claim_corrections.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    corrections = read_jsonl(CORRECTIONS)
    claims = read_jsonl(CLAIMS)
    by_id = {c["claim_id"]: c for c in claims}
    applied, skipped = [], []

    for record in corrections:
        if not record.get("evidence"):
            raise ValueError(f"correction without evidence: {record}")
        claim_id = record["match"]["claim_id"]
        claim = by_id.get(claim_id)
        if claim is None:
            raise ValueError(f"correction matches no claim: {claim_id}")
        if all(claim.get(k) == v for k, v in record["set"].items()):
            skipped.append({"claim_id": claim_id, "reason": "already applied"})
            continue
        claim.update(record["set"])
        note = claim.get("notes") or ""
        claim["notes"] = (note + " | " if note else "") + f"Corrected: {record['evidence']}"
        applied.append({"claim_id": claim_id, "set": record["set"]})

    if not args.dry_run and applied:
        with CLAIMS.open("w", encoding="utf-8", newline="\n") as handle:
            for claim in claims:
                handle.write(json.dumps(claim, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"applied": applied, "skipped": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
