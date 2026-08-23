"""Generate conservative category review artifacts from stored source records."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..config import CATALOG_ROOT
from .models import ReviewStatus, SourceRecord
from .storage import write_json


def build_category_review(
    category: str,
    records: list[SourceRecord],
    status: ReviewStatus = ReviewStatus.DRAFT,
) -> dict:
    by_device: dict[str, list[SourceRecord]] = defaultdict(list)
    for record in records:
        by_device[record.device_family or "unmatched"].append(record)
    return {
        "category": category,
        "status": status.value,
        "source_ids": [record.source_id for record in records],
        "devices": {
            device: {
                "source_count": len(device_records),
                "sources": [record.to_dict() for record in device_records],
            }
            for device, device_records in sorted(by_device.items())
        },
    }


def write_category_review(
    category: str,
    records: list[SourceRecord],
    output_root: Path = CATALOG_ROOT / "reviews",
) -> tuple[Path, Path]:
    review = build_category_review(category, records)
    review_dir = output_root / category
    json_path = write_json(review_dir / f"{category}-review.json", review)
    markdown_path = review_dir / f"{category}-review.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_review_markdown(review), encoding="utf-8")
    return json_path, markdown_path


def render_review_markdown(review: dict) -> str:
    lines = [
        f"# {review['category'].replace('-', ' ').title()} Review",
        "",
        f"Status: `{review['status']}`",
        "",
        "This review is generated from stored source records. PubMed entries are title/abstract only in V1.",
        "",
    ]
    for device, payload in review["devices"].items():
        lines.extend([
            f"## {device}",
            "",
            f"Source records: {payload['source_count']}",
            "",
        ])
        for source in payload["sources"]:
            lines.extend([
                f"### {source['title'] or source['source_id']}",
                "",
                f"- Source ID: `{source['source_id']}`",
                f"- Source type: `{source['source_type']}`",
                f"- Query: `{source.get('query_used', '')}`",
            ])
            raw = source.get("raw", {})
            abstract = raw.get("abstract")
            if abstract:
                lines.extend(["", abstract])
            lines.append("")
    return "\n".join(lines)
