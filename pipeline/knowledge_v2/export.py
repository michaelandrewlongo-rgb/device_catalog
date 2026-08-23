"""Build a sanitized, fail-closed export for agent-textbooks."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from .io import read_jsonl, write_json, write_jsonl

ACTIONABLE_SOURCE_STATUSES = {"current"}
ACTIONABLE_SOURCE_DEPTHS = {"local_full_text", "official_remote_full_text"}
ACTIONABLE_REVIEW_STATES = {"source_checked", "clinician_reviewed"}
ACTIONABLE_SUPPORT_STATES = {"direct"}
KNOWN_SOURCE_STATUSES = {"current", "historical", "superseded", "quarantined", "unavailable"}
KNOWN_SOURCE_DEPTHS = {"local_full_text", "official_remote_full_text", "metadata_only", "unavailable"}


def _safe_relative_filename(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    return not (
        path.is_absolute()
        or normalized.startswith("//")
        or re.match(r"^[A-Za-z]:/", normalized)
        or ".." in path.parts
    )


def _source_schema_errors(source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not all(source.get(key) for key in ("source_id", "device_id", "title", "source_type")):
        errors.append("missing required source identity")
    if source.get("status") not in KNOWN_SOURCE_STATUSES:
        errors.append("unknown source status")
    if source.get("evidence_depth") not in KNOWN_SOURCE_DEPTHS:
        errors.append("unknown evidence depth")
    local_filename = source.get("local_filename")
    if local_filename is not None and not _safe_relative_filename(local_filename):
        errors.append("local_filename is not a safe repository-relative path")
    if source.get("evidence_depth") == "local_full_text" and not source.get("sha256"):
        errors.append("local full text is missing sha256")
    return errors


def _public_source(source: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "source_id",
        "device_id",
        "title",
        "source_type",
        "status",
        "evidence_depth",
        "document_id",
        "revision",
        "jurisdiction",
        "official_url",
        "local_filename",
        "sha256",
        "checked_at",
        "superseded_by",
        "quarantine_reason",
        "notes",
    }
    return {key: value for key, value in source.items() if key in allowed}


def build_export(
    source_rows: list[dict[str, Any]],
    claim_rows: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    invalid_sources = {
        row.get("source_id", "<missing>"): errors
        for row in source_rows
        if (errors := _source_schema_errors(row))
    }
    if invalid_sources:
        raise ValueError(f"invalid source records: {invalid_sources}")
    source_by_id = {row["source_id"]: row for row in source_rows}
    accepted_claims: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for claim in claim_rows:
        reasons: list[str] = []
        if not claim.get("claim_id") or not claim.get("device_id") or not claim.get("text"):
            reasons.append("claim is missing a required identifier or text")
        if not isinstance(claim.get("source_ids"), list):
            reasons.append("source_ids must be a list")
        if not isinstance(claim.get("locators"), list):
            reasons.append("locators must be a list")
        if claim.get("evidence_layer") not in {"official_labeling", "clinical_context"}:
            reasons.append("claim has an invalid or non-actionable evidence layer")
        if claim.get("review_status") not in ACTIONABLE_REVIEW_STATES:
            reasons.append("claim is not source_checked or clinician_reviewed")
        if claim.get("support") not in ACTIONABLE_SUPPORT_STATES:
            reasons.append("claim is not directly supported")
        source_ids = claim.get("source_ids", []) if isinstance(claim.get("source_ids"), list) else []
        sources = [source_by_id.get(source_id) for source_id in source_ids]
        if not source_ids or any(source is None for source in sources):
            reasons.append("claim references a missing source")
        else:
            if any(source.get("device_id") != claim.get("device_id") for source in sources if source):
                reasons.append("claim device_id does not match its source")
            if any(source.get("status") not in ACTIONABLE_SOURCE_STATUSES for source in sources if source):
                reasons.append("claim source is not current")
            if any(source.get("evidence_depth") not in ACTIONABLE_SOURCE_DEPTHS for source in sources if source):
                reasons.append("claim source lacks verified full text")
        if not claim.get("locators"):
            reasons.append("claim has no source locator")

        if reasons:
            rejected.append({"claim_id": claim.get("claim_id"), "reasons": reasons})
        else:
            accepted_claims.append(claim)

    public_sources = [_public_source(row) for row in source_rows]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "device_sources.v2.jsonl", public_sources)
    write_jsonl(output_dir / "device_claims.v2.jsonl", accepted_claims)
    write_jsonl(output_dir / "rejected_claims.v2.jsonl", rejected)

    manifest = {
        "schema_version": "2.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "policy": "fail_closed_current_full_text_direct_support",
        "source_count": len(public_sources),
        "accepted_claim_count": len(accepted_claims),
        "rejected_claim_count": len(rejected),
        "source_status_counts": dict(Counter(row.get("status", "missing") for row in public_sources)),
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def build_export_from_files(source_path: Path, claim_path: Path, output_dir: Path) -> dict[str, Any]:
    return build_export(read_jsonl(source_path), read_jsonl(claim_path), output_dir)
