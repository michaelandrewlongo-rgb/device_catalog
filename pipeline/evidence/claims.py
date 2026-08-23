"""Backfill claim provenance from existing knowledge Markdown files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import CATALOG_ROOT
from .models import ClaimRecord, SourceType, utc_now_iso
from .registry import parse_knowledge_filename
from .storage import CLAIMS_DIR, write_json


def extract_claims_from_markdown(path: Path, text: str | None = None) -> list[ClaimRecord]:
    parsed = parse_knowledge_filename(path)
    if not parsed:
        return []
    category, manufacturer, product_slug = parsed
    device_id = f"{category}--{manufacturer}--{product_slug}"
    markdown = text if text is not None else path.read_text(encoding="utf-8", errors="replace")
    section = ""
    extracted_at = utc_now_iso()
    claims: list[ClaimRecord] = []
    table_buffer: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            table_buffer = []
            continue
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            table_buffer = []
            continue
        if set(line) <= {"|", "-", ":", " "}:
            continue
        if line.startswith("|") and line.endswith("|"):
            table_buffer.append(line)
            claim_text = line
        else:
            table_buffer = []
            claim_text = line.removeprefix("-").strip()
        if not claim_text:
            continue
        claims.append(
            ClaimRecord(
                claim_id=_claim_id(device_id, section, claim_text),
                device_id=device_id,
                source_type=SourceType.CURATED_HUMAN_NOTES,
                claim_text=claim_text,
                section=section,
                source_file=path.name,
                extracted_at=extracted_at,
            )
        )
    return claims


def backfill_curated_claims(catalog_root: Path = CATALOG_ROOT, category: str | None = None) -> list[ClaimRecord]:
    claims: list[ClaimRecord] = []
    for path in sorted(catalog_root.glob("*--knowledge.md")):
        parsed = parse_knowledge_filename(path)
        if not parsed:
            continue
        if category and parsed[0] != category:
            continue
        claims.extend(extract_claims_from_markdown(path))
    return claims


def write_curated_claims(category: str | None = None, catalog_root: Path = CATALOG_ROOT) -> Path:
    claims = backfill_curated_claims(catalog_root=catalog_root, category=category)
    suffix = category or "all"
    return write_json(CLAIMS_DIR / f"{suffix}-curated-claims.json", claims)


def _claim_id(device_id: str, section: str, claim_text: str) -> str:
    digest = hashlib.sha256(f"{device_id}\n{section}\n{claim_text}".encode("utf-8")).hexdigest()[:16]
    return f"claim:{digest}"
