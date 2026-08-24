"""Strict records used between device_catalog and downstream consumers.

The records intentionally separate document currency, claim support, and human
review.  A claim is not actionable merely because its text exists in a legacy
``*-knowledge.md`` file.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import PurePosixPath
import re
from typing import Any


class SourceStatus(StrEnum):
    CURRENT = "current"
    HISTORICAL = "historical"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    UNAVAILABLE = "unavailable"


class EvidenceDepth(StrEnum):
    LOCAL_FULL_TEXT = "local_full_text"
    OFFICIAL_REMOTE_FULL_TEXT = "official_remote_full_text"
    METADATA_ONLY = "metadata_only"
    UNAVAILABLE = "unavailable"


class ClaimSupport(StrEnum):
    DIRECT = "direct"
    ADJACENT = "adjacent"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    SOURCE_CHECKED = "source_checked"
    CLINICIAN_REVIEWED = "clinician_reviewed"
    STALE = "stale"


class CompatibilityStatus(StrEnum):
    MANUFACTURER_LABELED = "manufacturer_labeled"
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    DIMENSIONAL_ONLY = "dimensional_only"
    REPORTED_OFF_LABEL = "reported_off_label"
    UNKNOWN = "unknown"


class EvidenceLayer(StrEnum):
    OFFICIAL_LABELING = "official_labeling"
    # FDA 510(k)/PMA technological-characteristics tables: official regulatory
    # evidence, actionable for dimensions, but not manufacturer IFU or current labeling.
    OFFICIAL_SPECIFICATION = "official_specification"
    # Endovascular Today device-guide tables: manufacturer-submitted, published,
    # retained as hashed PDFs and audited row by row. Actionable for listed
    # dimensions and stated indicated use; outranked by IFU/FDA labeling on conflict.
    TRADE_JOURNAL_DEVICE_GUIDE = "trade_journal_device_guide"
    # Manufacturer product catalogue: the manufacturer's own published specification
    # tables. Above a trade-journal guide, below current IFU/labeling; dated.
    MANUFACTURER_CATALOG = "manufacturer_catalog"
    # Manufacturer public product page, retained as a dated screenshot capture.
    # The manufacturer's own statement, but undated/revisable web content: below
    # a printed catalogue, above clinical context; outranked by IFU on conflict.
    MANUFACTURER_PRODUCT_PAGE = "manufacturer_product_page"
    CLINICAL_CONTEXT = "clinical_context"
    LEGACY_DERIVED_SUMMARY = "legacy_derived_summary"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    device_id: str
    title: str
    source_type: str
    status: SourceStatus
    evidence_depth: EvidenceDepth
    document_id: str | None = None
    revision: str | None = None
    jurisdiction: str | None = None
    official_url: str | None = None
    local_filename: str | None = None
    sha256: str | None = None
    checked_at: str | None = None
    superseded_by: str | None = None
    quarantine_reason: str | None = None
    notes: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.source_id or not self.device_id or not self.title:
            errors.append("source_id, device_id, and title are required")
        if self.status == SourceStatus.QUARANTINED and not self.quarantine_reason:
            errors.append("quarantined source requires quarantine_reason")
        if self.evidence_depth == EvidenceDepth.LOCAL_FULL_TEXT:
            if not self.local_filename:
                errors.append("local full text requires local_filename")
            if not self.sha256:
                errors.append("local full text requires sha256")
        if self.local_filename:
            normalized = self.local_filename.replace("\\", "/")
            if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
                errors.append("local_filename must be repository-relative")
            if ".." in PurePosixPath(normalized).parts:
                errors.append("local_filename must not traverse parent directories")
        if self.status == SourceStatus.SUPERSEDED and not self.superseded_by:
            errors.append("superseded source requires superseded_by")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return _without_none(asdict(self))


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    device_id: str
    claim_type: str
    text: str
    evidence_layer: EvidenceLayer
    support: ClaimSupport
    review_status: ReviewStatus
    source_ids: tuple[str, ...] = field(default_factory=tuple)
    locators: tuple[str, ...] = field(default_factory=tuple)
    compatibility_status: CompatibilityStatus | None = None
    checked_at: str | None = None
    notes: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.claim_id or not self.device_id or not self.text:
            errors.append("claim_id, device_id, and text are required")
        if self.support != ClaimSupport.UNSUPPORTED:
            if not self.source_ids:
                errors.append("supported claim requires at least one source_id")
            if not self.locators:
                errors.append("supported claim requires at least one locator")
        if self.review_status in {
            ReviewStatus.SOURCE_CHECKED,
            ReviewStatus.CLINICIAN_REVIEWED,
        } and self.support == ClaimSupport.UNSUPPORTED:
            errors.append("reviewed claim cannot be unsupported")
        if self.evidence_layer == EvidenceLayer.LEGACY_DERIVED_SUMMARY:
            if self.review_status != ReviewStatus.DRAFT:
                errors.append("legacy-derived claims must remain draft")
            if self.support != ClaimSupport.UNSUPPORTED:
                errors.append("legacy-derived claims must remain unsupported")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return _without_none(asdict(self))


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_without_none(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value
