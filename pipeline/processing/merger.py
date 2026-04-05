"""Merge FDA regulatory records with manufacturer-scraped product data."""

import json
from pathlib import Path
from dataclasses import dataclass, field

from rich.console import Console

from ..fda.models import FDADeviceRecord
from ..scrapers.base import ScrapedProduct

console = Console()


@dataclass
class MergedDeviceRecord:
    """Combined record from FDA + scraper data."""
    # Identity
    device_name: str = ""
    manufacturer: str = ""
    catalog_category: str = ""
    filename_stem: str = ""

    # FDA data
    clearance_type: str = ""
    clearance_number: str = ""
    clearance_date: str = ""
    device_class: int = 0
    device_name_fda: str = ""
    product_code: str = ""

    # Scraped data (knowledge file sections)
    what_it_is: str | None = None
    sizing_specs: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    compatible_with: str | None = None
    use_notes: str | None = None
    deployment_steps: str | None = None
    also_known_as: list[str] = field(default_factory=list)

    # PDF references
    pdf_summary_url: str = ""
    ifu_pdf_url: str | None = None
    source_url: str = ""

    # Quality metadata
    confidence_score: float = 0.0
    needs_review: bool = True
    data_sources: list[str] = field(default_factory=list)  # ["fda", "scraper"]


def _normalize_name(name: str) -> str:
    """Normalize a device name for matching."""
    return name.lower().strip().replace("-", " ").replace("  ", " ")


def _name_similarity(a: str, b: str) -> float:
    """Compute a simple word-overlap similarity between two names."""
    words_a = set(_normalize_name(a).split())
    words_b = set(_normalize_name(b).split())

    # Remove very common words
    stopwords = {"the", "a", "an", "and", "or", "for", "with", "system", "device"}
    words_a -= stopwords
    words_b -= stopwords

    if not words_a or not words_b:
        return 0.0

    overlap = words_a & words_b
    return len(overlap) / max(len(words_a), len(words_b))


def merge_records(
    fda_devices: list[FDADeviceRecord],
    scraped_products: list[ScrapedProduct],
    manual_matches_path: Path | None = None,
) -> list[MergedDeviceRecord]:
    """Pair FDA records with scraped products and create merged records.

    Matching strategy:
    1. Exact match on clearance number (if scraper found K-numbers on the page).
    2. Fuzzy match on manufacturer + device name similarity.
    3. Manual override from JSON file.
    4. Unmatched FDA records become FDA-only merged records.
    5. Unmatched scraped products become scraper-only merged records.
    """
    # Load manual matches if provided
    manual_matches: dict[str, str] = {}
    if manual_matches_path and manual_matches_path.exists():
        manual_matches = json.loads(manual_matches_path.read_text(encoding="utf-8"))

    merged: list[MergedDeviceRecord] = []
    matched_fda: set[str] = set()       # clearance_numbers matched
    matched_scraper: set[int] = set()   # indices of matched scraped products

    # Pass 1: Match by clearance number
    for si, sp in enumerate(scraped_products):
        for cn in sp.clearance_numbers:
            for fd in fda_devices:
                if fd.clearance_number.upper() == cn.upper() and fd.clearance_number not in matched_fda:
                    merged.append(_merge_pair(fd, sp, confidence=1.0))
                    matched_fda.add(fd.clearance_number)
                    matched_scraper.add(si)
                    break

    # Pass 2: Manual matches
    for scraper_name, fda_number in manual_matches.items():
        for si, sp in enumerate(scraped_products):
            if si in matched_scraper:
                continue
            if _normalize_name(sp.device_name) == _normalize_name(scraper_name):
                for fd in fda_devices:
                    if fd.clearance_number == fda_number and fd.clearance_number not in matched_fda:
                        merged.append(_merge_pair(fd, sp, confidence=0.9))
                        matched_fda.add(fd.clearance_number)
                        matched_scraper.add(si)
                        break

    # Pass 3: Fuzzy match on manufacturer + name
    for si, sp in enumerate(scraped_products):
        if si in matched_scraper:
            continue

        best_match: FDADeviceRecord | None = None
        best_sim = 0.0

        for fd in fda_devices:
            if fd.clearance_number in matched_fda:
                continue
            if fd.manufacturer_canonical != sp.manufacturer:
                continue

            sim = _name_similarity(fd.device_name_fda, sp.device_name)
            if sim > best_sim and sim >= 0.4:
                best_sim = sim
                best_match = fd

        if best_match:
            merged.append(_merge_pair(best_match, sp, confidence=best_sim))
            matched_fda.add(best_match.clearance_number)
            matched_scraper.add(si)

    # Pass 4: Unmatched FDA records -> FDA-only
    for fd in fda_devices:
        if fd.clearance_number in matched_fda:
            continue
        if fd.already_in_catalog:
            continue  # Skip devices already in the catalog
        merged.append(_from_fda_only(fd))

    # Pass 5: Unmatched scraped products -> scraper-only
    for si, sp in enumerate(scraped_products):
        if si in matched_scraper:
            continue
        merged.append(_from_scraper_only(sp))

    console.print(
        f"[bold]Merge complete:[/] {len(merged)} records "
        f"({sum(1 for m in merged if len(m.data_sources) == 2)} paired, "
        f"{sum(1 for m in merged if m.data_sources == ['fda'])} FDA-only, "
        f"{sum(1 for m in merged if m.data_sources == ['scraper'])} scraper-only)"
    )

    return merged


def _merge_pair(
    fda: FDADeviceRecord,
    scraper: ScrapedProduct,
    confidence: float,
) -> MergedDeviceRecord:
    """Create a merged record from both FDA and scraper data."""
    return MergedDeviceRecord(
        device_name=scraper.device_name or fda.device_name_fda,
        manufacturer=fda.manufacturer_canonical,
        catalog_category=fda.catalog_category or scraper.category_hint,
        filename_stem=fda.suggested_filename_stem,
        clearance_type=fda.clearance_type,
        clearance_number=fda.clearance_number,
        clearance_date=fda.clearance_date,
        device_class=fda.device_class,
        device_name_fda=fda.device_name_fda,
        product_code=fda.product_code,
        what_it_is=scraper.what_it_is,
        sizing_specs=scraper.sizing_specs,
        indications=scraper.indications,
        contraindications=scraper.contraindications,
        compatible_with=scraper.compatible_with,
        use_notes=scraper.use_notes,
        deployment_steps=scraper.deployment_steps,
        also_known_as=scraper.also_known_as,
        pdf_summary_url=fda.pdf_summary_url,
        ifu_pdf_url=scraper.ifu_pdf_url,
        source_url=scraper.source_url,
        confidence_score=confidence,
        needs_review=confidence < 0.8,
        data_sources=["fda", "scraper"],
    )


def _from_fda_only(fda: FDADeviceRecord) -> MergedDeviceRecord:
    """Create a merged record from FDA data only."""
    return MergedDeviceRecord(
        device_name=fda.device_name_fda,
        manufacturer=fda.manufacturer_canonical,
        catalog_category=fda.catalog_category,
        filename_stem=fda.suggested_filename_stem,
        clearance_type=fda.clearance_type,
        clearance_number=fda.clearance_number,
        clearance_date=fda.clearance_date,
        device_class=fda.device_class,
        device_name_fda=fda.device_name_fda,
        product_code=fda.product_code,
        pdf_summary_url=fda.pdf_summary_url,
        confidence_score=0.5,
        needs_review=True,
        data_sources=["fda"],
    )


def _from_scraper_only(scraper: ScrapedProduct) -> MergedDeviceRecord:
    """Create a merged record from scraper data only."""
    from .naming import make_filename_stem
    stem = make_filename_stem(
        scraper.category_hint or "unknown",
        scraper.manufacturer,
        scraper.device_name,
    )
    return MergedDeviceRecord(
        device_name=scraper.device_name,
        manufacturer=scraper.manufacturer,
        catalog_category=scraper.category_hint,
        filename_stem=stem,
        what_it_is=scraper.what_it_is,
        sizing_specs=scraper.sizing_specs,
        indications=scraper.indications,
        contraindications=scraper.contraindications,
        compatible_with=scraper.compatible_with,
        use_notes=scraper.use_notes,
        deployment_steps=scraper.deployment_steps,
        also_known_as=scraper.also_known_as,
        ifu_pdf_url=scraper.ifu_pdf_url,
        source_url=scraper.source_url,
        confidence_score=0.3,
        needs_review=True,
        data_sources=["scraper"],
    )
