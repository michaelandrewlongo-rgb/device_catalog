"""Audit and export source-grounded device knowledge.

Examples:
    python -m pipeline.run_knowledge_v2 audit
    python -m pipeline.run_knowledge_v2 build-candidates
    python -m pipeline.run_knowledge_v2 export --output-dir exports/agent-textbooks
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.knowledge_v2.audit import audit_registered_sources, inventory_legacy_knowledge
from pipeline.knowledge_v2.export import build_export_from_files
from pipeline.knowledge_v2.io import write_json, write_jsonl
from pipeline.knowledge_v2.official import scan_watchlist

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "knowledge_v2" / "data"


def run_audit(catalog_root: Path, output_dir: Path) -> int:
    sources, findings = audit_registered_sources(
        catalog_root,
        DATA_DIR / "source_registry.json",
        output_dir / "official_watch_report.v2.json",
    )
    legacy = inventory_legacy_knowledge(catalog_root)
    write_jsonl(output_dir / "source_records.v2.jsonl", (record.to_dict() for record in sources))
    write_jsonl(output_dir / "legacy_inventory.v2.jsonl", legacy)
    write_json(output_dir / "audit_findings.v2.json", {"findings": findings})
    failures = sum(bool(item["validation_errors"]) for item in findings)
    quarantined = sum(item["observed_status"] == "quarantined" for item in findings)
    print(
        f"Audited {len(sources)} registered sources and {len(legacy)} high-risk legacy summaries; "
        f"quarantined={quarantined}, schema_failures={failures}."
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--catalog-root", type=Path, default=REPO_ROOT)
    audit_parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reviews" / "knowledge_v2")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument(
        "--source-records",
        type=Path,
        default=REPO_ROOT / "reviews" / "knowledge_v2" / "source_records.v2.jsonl",
    )
    export_parser.add_argument(
        "--claims",
        type=Path,
        default=DATA_DIR / "reviewed_claims.v2.jsonl",
    )
    export_parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "exports" / "agent-textbooks",
    )
    export_parser.add_argument(
        "--candidates",
        type=Path,
        default=DATA_DIR / "device_dimension_candidates.v2.jsonl",
        help="Secondary dimension candidates (discovery-only; never actionable).",
    )

    candidates_parser = subparsers.add_parser(
        "build-candidates",
        help="Extract retained Endovascular Today guide PDFs and rebuild secondary dimension candidates.",
    )
    candidates_parser.add_argument("--include-peripheral", action="store_true")

    official_parser = subparsers.add_parser("official-scan")
    official_parser.add_argument(
        "--watchlist",
        type=Path,
        default=DATA_DIR / "official_watchlist.json",
    )
    official_parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "reviews" / "knowledge_v2" / "official_watch_report.v2.json",
    )
    official_parser.add_argument("--timeout", type=float, default=20.0)

    args = parser.parse_args()
    if args.command == "audit":
        return run_audit(args.catalog_root, args.output_dir)

    if args.command == "official-scan":
        report = scan_watchlist(args.watchlist, args.output, timeout=args.timeout)
        counts: dict[str, int] = {}
        for finding in report["findings"]:
            status = finding["status"]
            counts[status] = counts.get(status, 0) + 1
        print(f"Official-source scan complete: {counts}")
        return 0 if counts.get("identity_mismatch", 0) == 0 else 2

    if args.command == "build-candidates":
        from pipeline.extraction.evt_guide_pdf import extract_all
        from pipeline.knowledge_v2.secondary_candidates import build_candidates

        counts = extract_all()
        summary = build_candidates(include_peripheral=args.include_peripheral)
        print(f"Extracted {sum(counts.values())} guide rows from {len(counts)} PDFs; {summary}")
        return 0

    manifest = build_export_from_files(args.source_records, args.claims, args.output_dir, args.candidates)
    print(
        f"Exported {manifest['source_count']} sources, "
        f"{manifest['accepted_claim_count']} actionable claims, and "
        f"{manifest['secondary_dimension_candidate_count']} secondary candidates; "
        f"rejected={manifest['rejected_claim_count']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
