"""Inventory legacy summaries and validate registered source artifacts."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import read_json
from .models import EvidenceDepth, SourceRecord, SourceStatus


HIGH_RISK_NEUROVASCULAR_CATEGORIES = {
    "aspiration",
    "balloon-catheter",
    "distal-access",
    "embolic-coil",
    "flow-diverter",
    "guide-catheter",
    "guidewire",
    "intracranial-stent",
    "intrasaccular",
    "liquid-embolic",
    "microcatheter",
    "stent-retriever",
    "thrombectomy",
}


@dataclass(frozen=True)
class ParsedName:
    category: str
    manufacturer: str
    product: str
    document_type: str

    @property
    def device_id(self) -> str:
        return "--".join((self.category, self.manufacturer, self.product))


def parse_catalog_filename(path: Path) -> ParsedName:
    parts = path.stem.split("--")
    if len(parts) < 4:
        raise ValueError(f"unexpected catalog filename: {path.name}")
    return ParsedName(
        category=parts[0],
        manufacturer=parts[1],
        product="--".join(parts[2:-1]),
        document_type=parts[-1],
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_pdf_text(path: Path, max_pages: int | None = None) -> tuple[str, str | None]:
    """Extract text for identity checks without adding a hard dependency.

    The whole document is read by default: a per-row source inside a multi-page
    comparison table names a product that may only appear on page 9, and an IFU's
    identity terms can sit in a late appendix. Pass ``max_pages`` to bound very large
    documents explicitly.
    """
    try:
        import fitz  # type: ignore[import-not-found]

        document = fitz.open(path)
        pages = document if max_pages is None else document[:max_pages]
        text = "\n".join(page.get_text() for page in pages)
        return text, None
    except (ImportError, RuntimeError, ValueError) as exc:
        command = ["pdftotext", str(path), "-"]
        if max_pages is not None:
            command = ["pdftotext", "-f", "1", "-l", str(max_pages), str(path), "-"]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout, None
        except (FileNotFoundError, subprocess.SubprocessError) as fallback_exc:
            return "", f"PDF text unavailable: {exc}; fallback: {fallback_exc}"


def _fold(value: str) -> str:
    """Whitespace- and punctuation-insensitive form for identity matching.

    PDF text extraction wraps table cells across lines and drops or re-encodes
    trademark glyphs, so "Wingman 35 CTO Crossing Catheter" may appear as
    "Wingman 35 CTO
Crossing Catheter" or "Wingman 35 CTO Crossing Catheter(tm)".
    Identity is about the name, not its typography.
    """
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _contains_any(text: str, terms: list[str]) -> bool:
    folded = _fold(text)
    return any(_fold(term) in folded for term in terms if _fold(term))


def _contains_all(text: str, terms: list[str]) -> bool:
    folded = _fold(text)
    return all(_fold(term) in folded for term in terms if _fold(term))


def catalog_data_roots(catalog_root: Path) -> list[Path]:
    candidates = [catalog_root, catalog_root / "pipeline" / "data" / "data_by_device"]
    return [path for path in candidates if path.is_dir()]


def locate_catalog_artifact(catalog_root: Path, relative: str) -> tuple[Path | None, list[Path]]:
    normalized = Path(relative.replace("\\", "/"))
    candidates = [root / normalized for root in catalog_data_roots(catalog_root)]
    existing = [path for path in candidates if path.is_file()]
    return (existing[0] if existing else None), existing


def _remote_sha256(entry: dict[str, Any], official: dict[str, Any] | None) -> str | None:
    """Hash for a remote-only source: the latest reviewable scan, else the pinned value."""
    if official and official.get("status") == "reviewable" and official.get("content_sha256"):
        return official["content_sha256"]
    return entry.get("sha256")


def audit_registered_sources(
    catalog_root: Path,
    registry_path: Path,
    official_report_path: Path | None = None,
) -> tuple[list[SourceRecord], list[dict[str, Any]]]:
    registry = read_json(registry_path)
    official_findings: dict[str, dict[str, Any]] = {}
    if official_report_path and official_report_path.exists():
        report = read_json(official_report_path)
        official_findings = {row["source_id"]: row for row in report.get("findings", [])}
    records: list[SourceRecord] = []
    findings: list[dict[str, Any]] = []

    for entry in registry["sources"]:
        filename = entry.get("local_filename")
        source_path, source_candidates = (
            locate_catalog_artifact(catalog_root, filename) if filename else (None, [])
        )
        configured_status = SourceStatus(entry["status"])
        status = configured_status
        reason = entry.get("quarantine_reason")
        text = ""
        extraction_error: str | None = None
        digest: str | None = None
        checked_at = registry.get("checked_at")

        if source_path and source_path.exists():
            digest = sha256_file(source_path)
            text, extraction_error = extract_pdf_text(source_path)
        elif source_path:
            status = SourceStatus.UNAVAILABLE
            reason = "registered local source is missing"

        identity = entry.get("identity", {})
        required_any = identity.get("required_any", [])
        required_all = identity.get("required_all", [])
        forbidden_any = identity.get("forbidden_any", [])
        identity_failures: list[str] = []
        if text:
            if required_any and not _contains_any(text, required_any):
                identity_failures.append("none of the expected identity terms were found")
            if required_all and not _contains_all(text, required_all):
                identity_failures.append("not all required identity terms were found")
            if forbidden_any and _contains_any(text, forbidden_any):
                identity_failures.append("a forbidden cross-product identity term was found")
        elif source_path and source_path.exists():
            identity_failures.append("document identity could not be checked because text extraction failed")

        if identity_failures:
            status = SourceStatus.QUARANTINED
            reason = "; ".join(identity_failures)

        candidate_hashes = {sha256_file(path) for path in source_candidates}
        if len(candidate_hashes) > 1:
            status = SourceStatus.QUARANTINED
            reason = "multiple catalog artifacts resolve to this source with different hashes"
        expected_hash = entry.get("expected_sha256")
        if digest and expected_hash and digest != expected_hash:
            status = SourceStatus.QUARANTINED
            reason = "local artifact hash differs from the pinned reviewed hash"

        official = official_findings.get(entry["source_id"])
        if official and official.get("status") == "reviewable":
            remote_hash = official.get("content_sha256")
            if digest and remote_hash and digest != remote_hash:
                status = SourceStatus.QUARANTINED
                reason = "local artifact hash differs from the current official URL"
            elif not digest or not remote_hash or digest == remote_hash:
                checked_at = official.get("checked_at", checked_at)
        elif official and official.get("status") == "identity_mismatch":
            status = SourceStatus.QUARANTINED
            reason = "current official source failed its configured identity check"
        elif official and official.get("status") in {"unavailable", "blocked"} and status == SourceStatus.CURRENT:
            status = SourceStatus.UNAVAILABLE
            reason = "current official source could not be revalidated in the latest scan"

        resolved_filename = None
        if source_path and source_path.exists():
            resolved_filename = source_path.relative_to(catalog_root).as_posix()

        record = SourceRecord(
            source_id=entry["source_id"],
            device_id=entry["device_id"],
            title=entry["title"],
            source_type=entry.get("source_type", "manufacturer_ifu"),
            status=status,
            evidence_depth=(
                EvidenceDepth.LOCAL_FULL_TEXT
                if source_path and source_path.exists()
                else EvidenceDepth(entry.get("evidence_depth", "metadata_only"))
            ),
            document_id=entry.get("document_id"),
            revision=entry.get("revision"),
            jurisdiction=entry.get("jurisdiction"),
            official_url=entry.get("official_url"),
            local_filename=resolved_filename,
            sha256=digest or _remote_sha256(entry, official),
            checked_at=checked_at,
            superseded_by=entry.get("superseded_by"),
            quarantine_reason=reason,
            notes=entry.get("notes"),
        )
        records.append(record)
        findings.append(
            {
                "source_id": record.source_id,
                "local_filename": filename,
                "configured_status": configured_status.value,
                "observed_status": record.status.value,
                "identity_failures": identity_failures,
                "extraction_error": extraction_error,
                "validation_errors": record.validate(),
                "official_scan_status": official.get("status") if official else "not_watched",
            }
        )

    return records, findings


def inventory_legacy_knowledge(catalog_root: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    paths = [path for root in catalog_data_roots(catalog_root) for path in root.glob("*--knowledge.md")]
    for path in sorted(paths):
        try:
            parsed = parse_catalog_filename(path)
        except ValueError:
            continue
        if parsed.category not in HIGH_RISK_NEUROVASCULAR_CATEGORIES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        digest = sha256_file(path)
        identity = (parsed.device_id, digest)
        if identity in seen:
            continue
        seen.add(identity)
        urls = re.findall(r"https?://[^\s)>]+", text)
        source_markers = re.findall(
            r"(?im)^\s*(?:sources?|references?|ifu|fda)\s*:",
            text,
        )
        inventory.append(
            {
                "device_id": parsed.device_id,
                "filename": path.relative_to(catalog_root).as_posix(),
                "sha256": digest,
                "legacy_status": "legacy_derived_summary",
                "review_status": "draft",
                "claim_support": "unsupported",
                "url_count": len(urls),
                "source_marker_count": len(source_markers),
                "has_companion_ifu": any(
                    (root / path.name.replace("--knowledge.md", "--ifu.pdf")).exists()
                    for root in catalog_data_roots(catalog_root)
                ),
            }
        )
    return inventory
