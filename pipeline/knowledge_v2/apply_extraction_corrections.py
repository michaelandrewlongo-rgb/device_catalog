"""Apply reviewed correction records to extracted catalog rows, auditable and idempotent.

Correction records live in ``pipeline/data/extracted/corrections/<set>.corrections.jsonl``,
one JSON object per line:

- ``{"action": "shift_pdf_pages", "delta": 1, "evidence": "...", ...}`` —
  shift every row's ``pdf_page``; refused unless, after the shift, every
  catalog number is found in the text of its cited PDF page (so a re-run,
  which would double-shift, always refuses).
- ``{"action": "exclude_family", "product_family": "...", "evidence": "..."}`` —
  remove the family's rows; the removed rows and the evidence are preserved in
  ``<set>.excluded.jsonl`` so the exclusion stays reviewable.
- ``{"action": "update_fields", "match": {"product_family": ..., "catalog_number": ...,
  "pdf_page": ...}, "set": {...}, "evidence": "..."}`` — update exactly one row
  (refused on 0 or 2+ matches) and append the evidence to its ``notes``.

Every record must carry ``evidence`` (what the reopened PDF page showed) and
``decided_by``/``date``. Git history of the rows files is the change log.

    python -m pipeline.knowledge_v2.apply_extraction_corrections [--set NAME] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..config import CATALOG_ROOT, EXTRACTED_DIR
from .io import read_jsonl

CORRECTIONS_DIR = EXTRACTED_DIR / "corrections"

# extraction set -> retained catalog PDF, for shift verification
from .verify_suspects import SET_PDFS


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def verify_pages(set_name: str, rows: list[dict[str, Any]]) -> list[str]:
    """Catalog numbers not found in the text of their cited PDF page."""
    import fitz

    pdf_path = CATALOG_ROOT / SET_PDFS[set_name]
    missing = []
    with fitz.open(pdf_path) as doc:
        cache: dict[int, str] = {}

        def page_text(number: int) -> str:
            if number not in cache:
                cache[number] = doc[number - 1].get_text("text") if 1 <= number <= doc.page_count else ""
            return cache[number]

        for row in rows:
            number = (row.get("catalog_number") or "").strip()
            if number and number not in page_text(row["pdf_page"]):
                missing.append(f"{number} not on pdf_page {row['pdf_page']}")
    return missing


def apply_set(set_name: str, dry_run: bool = False) -> dict[str, Any]:
    corrections_path = CORRECTIONS_DIR / f"{set_name}.corrections.jsonl"
    rows_path = EXTRACTED_DIR / f"{set_name}.rows.jsonl"
    excluded_path = EXTRACTED_DIR / f"{set_name}.excluded.jsonl"
    corrections = read_jsonl(corrections_path)
    rows = read_jsonl(rows_path)
    excluded: list[dict[str, Any]] = read_jsonl(excluded_path)
    applied, skipped = [], []

    for record in corrections:
        action = record.get("action")
        if not record.get("evidence"):
            raise ValueError(f"{set_name}: correction without evidence: {record}")

        if action == "shift_pdf_pages":
            delta = int(record["delta"])
            shifted = [dict(row, pdf_page=row["pdf_page"] + delta) for row in rows]
            missing = verify_pages(set_name, shifted)
            if missing:
                # Either already applied (a second shift breaks verification) or wrong.
                if verify_pages(set_name, rows):
                    raise ValueError(f"{set_name}: shift_pdf_pages leaves unverified rows: {missing[:5]}")
                skipped.append({"action": action, "reason": "already applied (rows verify unshifted)"})
                continue
            rows = shifted
            applied.append({"action": action, "delta": delta, "rows": len(rows)})

        elif action == "exclude_family":
            family = record["product_family"]
            matched = [r for r in rows if r.get("product_family") == family]
            if not matched:
                skipped.append({"action": action, "family": family,
                                "reason": "no rows (already excluded?)"})
                continue
            rows = [r for r in rows if r.get("product_family") != family]
            for row in matched:
                excluded.append({"excluded_row": row, "evidence": record["evidence"],
                                 "decided_by": record.get("decided_by", ""),
                                 "date": record.get("date", "")})
            applied.append({"action": action, "family": family, "rows_removed": len(matched)})

        elif action == "update_fields":
            match = record["match"]
            matched = [r for r in rows
                       if all(r.get(k) == v for k, v in match.items())]
            if len(matched) != 1:
                if not matched and any(
                        all(r.get(k) == v for k, v in {**match, **record["set"]}.items())
                        for r in rows):
                    skipped.append({"action": action, "match": match, "reason": "already applied"})
                    continue
                raise ValueError(f"{set_name}: update_fields matched {len(matched)} rows for {match}")
            row = matched[0]
            row.update(record["set"])
            note = row.get("notes") or ""
            row["notes"] = (note + " | " if note else "") + f"Corrected: {record['evidence']}"
            applied.append({"action": action, "match": match})

        else:
            raise ValueError(f"{set_name}: unknown action {action!r}")

    if not dry_run and applied:
        write_rows(rows_path, rows)
        if excluded:
            write_rows(excluded_path, excluded)
    return {"set": set_name, "applied": applied, "skipped": skipped, "rows_now": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="sets", action="append",
                        help="extraction set name; default: every set with a corrections file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sets = args.sets or sorted(p.name.removesuffix(".corrections.jsonl")
                               for p in CORRECTIONS_DIR.glob("*.corrections.jsonl"))
    results = [apply_set(name, dry_run=args.dry_run) for name in sets]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
