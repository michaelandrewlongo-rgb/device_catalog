"""Evidence pipeline CLI for grounded device reviews."""

from __future__ import annotations

import argparse
import time

try:
    from rich.console import Console
except ModuleNotFoundError:
    Console = None

from .evidence.accessgudid import AccessGUDIDClient
from .evidence.claims import write_curated_claims
from .evidence.clinical_trials import ClinicalTrialsClient, build_trials_query
from .evidence.fda_sources import OpenFDAEvidenceClient
from .evidence.models import SourceHealth, SourceRecord, SourceType, utc_now_iso
from .evidence.pubmed import PubMedClient
from .evidence.registry import build_registry, detect_potential_duplicates, write_registry
from .evidence.review import write_category_review
from .evidence.storage import (
    FDA_MAUDE_DIR,
    FDA_RAW_DIR,
    FDA_RECALLS_DIR,
    GUDID_DIR,
    HEALTH_DIR,
    PUBMED_DIR,
    TRIALS_DIR,
    ensure_evidence_dirs,
    read_json,
    write_json,
)

console = Console() if Console else None


def _print(message: str) -> None:
    if console:
        console.print(message)
    else:
        print(message.replace("[green]", "").replace("[/]", ""))


def _mock_record(source_id: str, source_type: SourceType, title: str, device_family: str, query: str) -> SourceRecord:
    raw = {"title": title}
    if source_type == SourceType.PUBMED:
        raw["abstract"] = "Mock abstract used for offline pipeline verification."
    return SourceRecord(
        source_id=source_id,
        source_type=source_type,
        title=title,
        retrieved_at=utc_now_iso(),
        device_family=device_family,
        query_used=query,
        raw=raw,
    )


def _precise_terms(identity, limit: int) -> list[str]:
    terms: list[str] = []
    for term in identity.search_terms():
        compact = "".join(ch for ch in term if ch.isalnum())
        if len(compact) <= 3 and compact.upper() == compact:
            continue
        terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def _collect_pubmed(
    category: str, limit: int, mock_network: bool, health_log: list[SourceHealth]
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    identities = build_registry(category=category)
    client = PubMedClient()
    for identity in identities:
        query = " OR ".join(f'"{term}"' for term in _precise_terms(identity, 5))
        if mock_network:
            device_records = [
                _mock_record(
                    f"pubmed:mock:{identity.canonical_id}",
                    SourceType.PUBMED,
                    f"Mock PubMed result for {identity.display_name}",
                    identity.canonical_id,
                    query,
                )
            ]
        else:
            articles = client.search(
                query, limit=limit, device_family=identity.canonical_id, health_log=health_log
            )
            device_records = [article.to_source_record() for article in articles]
        write_json(PUBMED_DIR / f"{identity.canonical_id}.json", device_records)
        records.extend(device_records)
    return records


def _collect_trials(
    category: str, limit: int, mock_network: bool, health_log: list[SourceHealth]
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    identities = build_registry(category=category)
    # 1-second delay between devices keeps us well under ClinicalTrials rate limits
    client = ClinicalTrialsClient(request_delay=1.0)
    for i, identity in enumerate(identities):
        # Use quoted terms so phrase matching works in query.intr field
        query = build_trials_query(_precise_terms(identity, 3))
        if mock_network:
            device_records = [
                _mock_record(
                    f"clinicaltrials:mock:{identity.canonical_id}",
                    SourceType.CLINICALTRIALS,
                    f"Mock ClinicalTrials.gov result for {identity.display_name}",
                    identity.canonical_id,
                    query,
                )
            ]
        else:
            device_records = client.search(
                query, limit=limit, device_family=identity.canonical_id, health_log=health_log
            )
        write_json(TRIALS_DIR / f"{identity.canonical_id}.json", device_records)
        records.extend(device_records)
        if not mock_network and i < len(identities) - 1:
            time.sleep(client.request_delay)
    return records


def _collect_fda(
    category: str, limit: int, mock_network: bool, health_log: list[SourceHealth]
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    identities = build_registry(category=category)
    client = OpenFDAEvidenceClient()
    for identity in identities:
        query = " OR ".join(f'brand_name:"{term}"' for term in _precise_terms(identity, 3))
        if mock_network:
            maude_records = [
                _mock_record(
                    f"fda:event:mock:{identity.canonical_id}",
                    SourceType.FDA,
                    f"Mock MAUDE result for {identity.display_name}",
                    identity.canonical_id,
                    query,
                )
            ]
            recall_records = [
                _mock_record(
                    f"fda:recall:mock:{identity.canonical_id}",
                    SourceType.FDA,
                    f"Mock recall result for {identity.display_name}",
                    identity.canonical_id,
                    query,
                )
            ]
            udi_records: list[SourceRecord] = []
        else:
            maude_records = client.maude(query, limit=limit, device_family=identity.canonical_id)
            recall_records = client.recalls(query, limit=limit, device_family=identity.canonical_id)
            udi_records = client.udi(query, limit=limit, device_family=identity.canonical_id)
            checked_at = utc_now_iso()
            for source_type, recs in [
                ("fda_maude", maude_records),
                ("fda_recalls", recall_records),
                ("fda_udi", udi_records),
            ]:
                health_log.append(SourceHealth(
                    source_type=source_type,
                    device_family=identity.canonical_id,
                    query_used=query,
                    checked_at=checked_at,
                    status="ok" if recs else "empty",
                    record_count=len(recs),
                ))
        write_json(FDA_MAUDE_DIR / f"{identity.canonical_id}.json", maude_records)
        write_json(FDA_RECALLS_DIR / f"{identity.canonical_id}.json", recall_records)
        write_json(FDA_RAW_DIR / f"{identity.canonical_id}-udi.json", udi_records)
        records.extend(maude_records)
        records.extend(recall_records)
        records.extend(udi_records)
    return records


def _collect_gudid(
    category: str, limit: int, mock_network: bool, health_log: list[SourceHealth]
) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    identities = build_registry(category=category)
    client = AccessGUDIDClient()
    for identity in identities:
        query = identity.display_name
        if mock_network:
            device_records = [
                _mock_record(
                    f"accessgudid:mock:{identity.canonical_id}",
                    SourceType.ACCESSGUDID,
                    f"Mock AccessGUDID result for {identity.display_name}",
                    identity.canonical_id,
                    query,
                )
            ]
        else:
            device_records = client.search(
                query, limit=limit, device_family=identity.canonical_id, health_log=health_log
            )
        write_json(GUDID_DIR / f"{identity.canonical_id}.json", device_records)
        records.extend(device_records)
    return records


def _load_stored_records(category: str) -> list[SourceRecord]:
    records: list[SourceRecord] = []
    for directory in [PUBMED_DIR, TRIALS_DIR, FDA_MAUDE_DIR, FDA_RECALLS_DIR, FDA_RAW_DIR, GUDID_DIR]:
        if not directory.exists():
            continue
        for path in sorted(directory.glob(f"{category}--*.json")):
            payload = read_json(path)
            items = payload if isinstance(payload, list) else [payload]
            for item in items:
                if not isinstance(item, dict) or "source_id" not in item:
                    continue
                item["source_type"] = SourceType(item["source_type"])
                records.append(SourceRecord(**item))
    return records


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run evidence collection and category review tasks")
    subparsers = parser.add_subparsers(dest="command", required=True)
    registry_parser = subparsers.add_parser("build-registry")
    registry_parser.add_argument("--category")
    provenance_parser = subparsers.add_parser("build-provenance")
    provenance_parser.add_argument("--category")
    for name in ["pubmed", "trials", "fda-safety", "gudid", "review", "all-pilot"]:
        sub = subparsers.add_parser(name)
        sub.add_argument("--category", default="flow-diverter")
        sub.add_argument("--limit", type=int, default=20)
        sub.add_argument("--mock-network", action="store_true")
    args = parser.parse_args()
    ensure_evidence_dirs()
    if args.command == "build-registry":
        path = write_registry(category=args.category)
        _print(f"[green]Wrote registry:[/] {path}")
        identities = build_registry(category=args.category)
        dupes = detect_potential_duplicates(identities)
        if dupes:
            _print(f"[yellow]Potential duplicate pairs:[/] {len(dupes)}")
            for pair in dupes[:5]:
                _print(f"  {pair['a']} <-> {pair['b']} ({pair['reason']})")
        return
    if args.command == "build-provenance":
        path = write_curated_claims(category=args.category)
        _print(f"[green]Wrote curated claim provenance:[/] {path}")
        return
    health_log: list[SourceHealth] = []
    records: list[SourceRecord] = []
    if args.command in {"pubmed", "all-pilot"}:
        records.extend(_collect_pubmed(args.category, args.limit, args.mock_network, health_log))
    if args.command in {"trials", "all-pilot"}:
        records.extend(_collect_trials(args.category, args.limit, args.mock_network, health_log))
    if args.command in {"fda-safety", "all-pilot"}:
        records.extend(_collect_fda(args.category, args.limit, args.mock_network, health_log))
    if args.command in {"gudid", "all-pilot"}:
        records.extend(_collect_gudid(args.category, args.limit, args.mock_network, health_log))
    if health_log and not args.mock_network:
        health_path = write_json(
            HEALTH_DIR / f"{args.category}-{args.command}-health.json",
            [h.to_dict() for h in health_log],
        )
        empty_count = sum(1 for h in health_log if h.status == "empty")
        error_count = sum(1 for h in health_log if h.status in {"http_error", "connection_error"})
        _print(
            f"[green]Health log:[/] {len(health_log)} queries, "
            f"{empty_count} empty, {error_count} errors -> {health_path}"
        )
    if args.command in {"review", "all-pilot"}:
        if args.command == "review":
            records = _load_stored_records(args.category)
        json_path, markdown_path = write_category_review(args.category, records)
        _print(f"[green]Wrote review JSON:[/] {json_path}")
        _print(f"[green]Wrote review Markdown:[/] {markdown_path}")
    elif records:
        _print(f"[green]Collected {len(records)} source records[/]")


if __name__ == "__main__":
    cli()
