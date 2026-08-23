"""Tier 1A: Deterministic extraction from FDA 510(k) summary PDFs.

Parses predictable FDA summary format: extract text via pdfplumber/Marker,
then regex-based section header matching.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import EXTRACTED_DIR, FDA_510K_DIR
from .pdf_utils import pdf_to_text, validate_pdf

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "fda_summaries"

# Section header patterns (case-insensitive, allow markdown headings)
SECTION_PATTERNS = {
    "Device Description": re.compile(
        r"(?:^|\n)#{0,3}\s*(?:device\s+description|description\s+of\s+(?:the\s+)?device)",
        re.IGNORECASE,
    ),
    "Indications for Use": re.compile(
        r"(?:^|\n)#{0,3}\s*indications?\s+(?:for\s+)?use",
        re.IGNORECASE,
    ),
    "Contraindications": re.compile(
        r"(?:^|\n)#{0,3}\s*contraindications?",
        re.IGNORECASE,
    ),
    "Substantial Equivalence": re.compile(
        r"(?:^|\n)#{0,3}\s*(?:substantial\s+equivalence|predicate\s+device|comparison\s+with\s+predicate)",
        re.IGNORECASE,
    ),
}

K_NUMBER_PATTERN = re.compile(r"\b(K\d{6})\b")


def extract_fda_summary(pdf_path: Path) -> dict | None:
    """Extract structured fields from a single FDA 510(k) summary PDF."""
    error = validate_pdf(pdf_path)
    if error:
        return None

    text = pdf_to_text(pdf_path)
    if not text:
        return None

    k_number = pdf_path.stem.upper()
    # Normalize K-number from filename (may be like "aspiration--alembic--apro-45--510k")
    k_match = K_NUMBER_PATTERN.search(k_number)
    if k_match:
        k_number = k_match.group(1)
    else:
        # Try to find K-number inside the text
        k_match = K_NUMBER_PATTERN.search(text[:2000])
        k_number = k_match.group(1) if k_match else pdf_path.stem

    sections = _find_sections(text)
    fields = _map_sections(sections)
    confidence = _compute_confidence(sections)

    return {
        "source_pdf": pdf_path.name,
        "clearance_number": k_number,
        "extraction_method": "pdfplumber_deterministic",
        "fields": fields,
        "confidence": confidence,
        "raw_sections": sections,
    }


def extract_all_fda_summaries() -> list[dict]:
    """Extract from all PDFs in the categorized 510k directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    skipped = []

    # Collect all PDFs, deduplicate by name
    pdfs_dir = FDA_510K_DIR
    if not pdfs_dir.exists():
        logger.warning("No FDA 510k directory found: %s", pdfs_dir)
        return []

    seen: set[str] = set()
    pdf_files: list[Path] = []
    for p in sorted(pdfs_dir.rglob("*.pdf")):
        if p.name not in seen:
            seen.add(p.name)
            pdf_files.append(p)

    logger.info("Processing %d FDA summary PDFs", len(pdf_files))

    for pdf_path in pdf_files:
        result = extract_fda_summary(pdf_path)
        if result is None:
            skipped.append({"file": pdf_path.name, "reason": "extraction_failed"})
            continue

        # Only save if we got at least one useful field
        field_count = sum(1 for v in result["fields"].values() if v is not None)
        if field_count == 0:
            skipped.append({"file": pdf_path.name, "reason": "no_fields_extracted"})
            continue

        out_file = _parsed_output_dir(pdf_path) / f"{pdf_path.stem}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        results.append(result)
        logger.info(
            "  Extracted: %s (%d fields)", pdf_path.name, field_count
        )

    # Save skipped manifest
    _save_skipped(skipped)

    logger.info(
        "FDA summary extraction: %d extracted, %d skipped",
        len(results), len(skipped),
    )
    return results


def _parsed_output_dir(pdf_path: Path) -> Path:
    """Return the category-local parsed output directory for a 510(k) PDF."""
    try:
        relative = pdf_path.relative_to(FDA_510K_DIR)
    except ValueError:
        return OUTPUT_DIR
    category = relative.parts[0] if relative.parts else "_uncategorized"
    return FDA_510K_DIR / category / "parsed" / "fda_summaries"


def _find_sections(text: str) -> dict[str, str]:
    """Find and extract text between section headers."""
    matches: list[tuple[int, str]] = []
    for name, pattern in SECTION_PATTERNS.items():
        m = pattern.search(text)
        if m:
            matches.append((m.start(), name))

    if not matches:
        return {}

    matches.sort(key=lambda x: x[0])

    sections: dict[str, str] = {}
    for i, (start, name) in enumerate(matches):
        # Find end of the header line
        newline_pos = text.find("\n", start)
        if newline_pos == -1:
            content_start = len(text)
        else:
            content_start = newline_pos + 1

        # Content ends at next section or end of document
        if i + 1 < len(matches):
            content_end = matches[i + 1][0]
        else:
            content_end = len(text)

        section_text = text[content_start:content_end].strip()
        if section_text:
            sections[name] = section_text

    return sections


def _map_sections(sections: dict[str, str]) -> dict:
    """Map extracted sections to ScrapedProduct-compatible fields."""
    fields: dict = {
        "what_it_is": None,
        "indications": None,
        "contraindications": None,
        "sizing_specs": None,
        "also_known_as": None,
    }

    if "Device Description" in sections:
        fields["what_it_is"] = sections["Device Description"]
        # Check if description contains dimensional data
        if _has_dimensions(sections["Device Description"]):
            fields["sizing_specs"] = sections["Device Description"]

    if "Indications for Use" in sections:
        fields["indications"] = sections["Indications for Use"]

    if "Contraindications" in sections:
        fields["contraindications"] = sections["Contraindications"]

    if "Substantial Equivalence" in sections:
        predicates = _extract_predicates(sections["Substantial Equivalence"])
        if predicates:
            fields["also_known_as"] = predicates

    return fields


def _has_dimensions(text: str) -> bool:
    """Check if text contains dimensional data."""
    return bool(
        re.search(r"\d+\s*(?:mm|cm|fr|french|inch|gauge|mL)", text, re.IGNORECASE)
    )


def _extract_predicates(text: str) -> list[str] | None:
    """Extract predicate device K-numbers from Substantial Equivalence section."""
    k_numbers = K_NUMBER_PATTERN.findall(text)
    return k_numbers if k_numbers else None


def _compute_confidence(sections: dict[str, str]) -> dict[str, float]:
    """Assign confidence scores based on section detection quality."""
    confidence: dict[str, float] = {}
    if "Indications for Use" in sections:
        confidence["indications"] = 0.95
    if "Device Description" in sections:
        confidence["what_it_is"] = 0.9
    if "Contraindications" in sections:
        confidence["contraindications"] = 0.9
    if "Substantial Equivalence" in sections:
        confidence["also_known_as"] = 0.7
    return confidence


def _save_skipped(skipped: list[dict]) -> None:
    """Append to the extraction skipped manifest."""
    skip_path = EXTRACTED_DIR / "skipped.json"
    existing: list[dict] = []
    if skip_path.exists():
        try:
            existing = json.loads(skip_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    existing.extend(skipped)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    skip_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"
    )
