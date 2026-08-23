"""Core evidence models for direct-source records and derivative review data."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SourceType(StrEnum):
    CURATED_HUMAN_NOTES = "curated_human_notes"
    FDA = "fda"
    MANUFACTURER = "manufacturer"
    NSPR = "nspr"
    EVTODAY = "evtoday"
    EXTRACTED_PDF = "extracted_pdf"
    LLM_SYNTHESIS = "llm_synthesis"
    PUBMED = "pubmed"
    CLINICALTRIALS = "clinicaltrials"
    ACCESSGUDID = "accessgudid"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    SOURCE_CHECKED = "source_checked"
    CLINICIAN_REVIEWED = "clinician_reviewed"
    STALE = "stale"


@dataclass(frozen=True)
class ClaimRecord:
    """A claim-like unit extracted from an existing knowledge source."""

    claim_id: str
    device_id: str
    source_type: SourceType
    claim_text: str
    section: str = ""
    source_file: str = ""
    review_status: ReviewStatus = ReviewStatus.DRAFT
    extracted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRecord:
    """A raw or minimally normalized source record with explicit provenance."""

    source_id: str
    source_type: SourceType
    title: str
    retrieved_at: str
    device_family: str
    source_url: str = ""
    query_used: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PubMedArticle:
    """Bibliographic-only PubMed record for V1."""

    pmid: str
    title: str
    abstract: str
    journal: str = ""
    publication_date: str = ""
    doi: str = ""
    query_used: str = ""
    matched_device_family: str = ""
    source_retrieved_at: str = ""

    def to_source_record(self) -> SourceRecord:
        return SourceRecord(
            source_id=f"pubmed:{self.pmid}",
            source_type=SourceType.PUBMED,
            title=self.title,
            retrieved_at=self.source_retrieved_at or utc_now_iso(),
            device_family=self.matched_device_family,
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/",
            query_used=self.query_used,
            raw=asdict(self),
        )


@dataclass(frozen=True)
class DeviceIdentity:
    canonical_id: str
    category: str
    manufacturer: str
    display_name: str
    synonyms: list[str] = field(default_factory=list)
    editions: list[str] = field(default_factory=list)

    def search_terms(self) -> list[str]:
        terms = [self.display_name, *self.synonyms, *self.editions]
        seen: set[str] = set()
        unique: list[str] = []
        for term in terms:
            normalized = " ".join(term.split())
            key = normalized.lower()
            if normalized and key not in seen:
                unique.append(normalized)
                seen.add(key)
        return unique


@dataclass
class SourceHealth:
    """Per-query health record to distinguish empty results from errors."""

    source_type: str
    device_family: str
    query_used: str
    checked_at: str
    status: str  # "ok" | "empty" | "http_error" | "connection_error" | "unexpected_response"
    record_count: int = 0
    http_status: int | None = None  # None means no HTTP response received
    error_detail: str = ""
    fallback_used: bool = False  # True when a secondary query strategy fired

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceInterpretation:
    """LLM-derived helper output. Never treated as source truth."""

    interpretation_id: str
    task: str
    model: str
    prompt_hash: str
    created_at: str
    source_ids: list[str]
    status: ReviewStatus = ReviewStatus.DRAFT
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
