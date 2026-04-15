"""Fill [NEEDS CONTENT] gaps in curated knowledge files using extracted source data.

Scans curated *--knowledge.md files for [NEEDS CONTENT ...] placeholders,
resolves available data from the extraction pipeline, and replaces placeholders
with sourced content when confidence is sufficient.

Does NOT use LLM calls. Only deterministic source resolution via resolve_field().
Does NOT modify manually-written content. Only replaces placeholder lines.
"""

from __future__ import annotations

import json
import logging
import re

from ..config import CATALOG_ROOT, DATA_DIR
from ..extraction.enricher import (
    gather_sources,
    resolve_field,
)

logger = logging.getLogger(__name__)

# Map enrichment field names to markdown section headers in knowledge files.
FIELD_TO_SECTION: dict[str, str] = {
    "what_it_is": "What It Is",
    "sizing_specs": "Sizing/Specs",
    "indications": "Indications",
    "contraindications": "Contraindications",
    "compatible_with": "Compatible With",
    "use_notes": "Use Notes",
    "also_known_as": "Also Known As",
}

# Reverse mapping: section header -> field name (case-insensitive lookup).
_SECTION_TO_FIELD: dict[str, str] = {v.lower(): k for k, v in FIELD_TO_SECTION.items()}

# Pattern matching [NEEDS CONTENT ...] placeholders.
_PLACEHOLDER_RE = re.compile(r"\[NEEDS CONTENT[^\]]*\]")

# Minimum confidence to replace a placeholder.
_MIN_CONFIDENCE = 0.5

# Stop words for device-identity matching between filename stem and merged record.
_IDENTITY_STOP_WORDS: frozenset[str] = frozenset({
    "aspiration", "catheter", "system", "device", "medical",
    "the", "and", "for", "with", "inc", "llc",
})

# Content fields that must not leak across devices via mismatched merged records.
_CONTENT_FIELDS: tuple[str, ...] = (
    "what_it_is",
    "sizing_specs",
    "indications",
    "compatible_with",
    "use_notes",
    "also_known_as",
)


def _identity_tokens(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens from text, minus stop words."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t and t not in _IDENTITY_STOP_WORDS}


def _merged_matches_stem(stem: str, merged: dict) -> bool:
    """Check that merged record's device_name overlaps the stem's product slug.

    The stem format is ``{category}--{manufacturer}--{product-slug}``.
    Returns True when there is at least one meaningful token in common
    between the product slug and ``merged["device_name"]`` after removing
    generic stop words. Returns True when the merged record has no
    device_name to compare against (nothing to contaminate with).
    """
    parts = stem.split("--")
    if len(parts) < 3:
        return True
    slug_tokens = _identity_tokens(parts[2])
    name_tokens = _identity_tokens(merged.get("device_name") or "")
    if not slug_tokens or not name_tokens:
        return True
    return bool(slug_tokens & name_tokens)


def _parse_stem(filename: str) -> str:
    """Extract the stem (everything before --knowledge.md) from a filename."""
    return filename.replace("--knowledge.md", "")


def _find_section_for_line(lines: list[str], line_idx: int) -> str | None:
    """Scan upward from line_idx to find the nearest ## section header.

    Returns the header text (without ##) in lowercase, or None.
    """
    for i in range(line_idx, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("## "):
            return stripped[3:].strip().lower()
    return None


def _format_value(value: str | list, is_bullet: bool) -> str:
    """Format a resolved value for insertion into the knowledge file.

    Args:
        value: The resolved field value (string or list).
        is_bullet: True if the placeholder was on a bullet-point line.

    Returns:
        Formatted string ready for insertion.
    """
    if isinstance(value, list):
        # Format list items as bullet points.
        return "\n".join(f"- {item}" for item in value)

    text = str(value).strip()
    if is_bullet and "\n" not in text:
        # Single-line value on a bullet line: keep the bullet prefix.
        return text
    return text


def fill_gaps(dry_run: bool = False) -> dict:
    """Fill [NEEDS CONTENT] gaps in curated knowledge files.

    Returns dict with keys: files_scanned, files_updated, gaps_filled, gaps_unfilled.
    """
    merged_dir = DATA_DIR / "merged"

    stats = {
        "files_scanned": 0,
        "files_updated": 0,
        "gaps_filled": 0,
        "gaps_unfilled": 0,
    }

    knowledge_files = sorted(CATALOG_ROOT.glob("*--knowledge.md"))

    for kf in knowledge_files:
        text = kf.read_text(encoding="utf-8")
        if "[NEEDS CONTENT" not in text:
            continue

        stats["files_scanned"] += 1
        stem = _parse_stem(kf.name)

        # Load merged record if available; otherwise construct minimal dict.
        merged_path = merged_dir / f"{stem}.json"
        if merged_path.exists():
            merged = json.loads(merged_path.read_text(encoding="utf-8"))
        else:
            # Parse manufacturer and device name from stem.
            parts = stem.split("--")
            manufacturer = parts[1] if len(parts) > 1 else ""
            device_name = parts[2].replace("-", " ") if len(parts) > 2 else ""
            merged = {"device_name": device_name, "manufacturer": manufacturer}

        # Identity guard: if the merged record's device_name does not overlap
        # the filename stem, a cross-device pairing happened upstream in
        # merger.py. Strip scraper-derived content fields so they cannot leak
        # into this knowledge file via Priority 6 in resolve_field().
        if not _merged_matches_stem(stem, merged):
            logger.warning(
                "  Identity mismatch: %s merged device_name=%r — "
                "stripping content fields",
                kf.name,
                merged.get("device_name"),
            )
            for _field in _CONTENT_FIELDS:
                merged[_field] = None

        # Gather all available sources for this device.
        sources = gather_sources(stem, merged)

        lines = text.splitlines(keepends=True)
        file_changed = False

        for i, line in enumerate(lines):
            if "[NEEDS CONTENT" not in line:
                continue

            # Skip table cells (lines containing |).
            if "|" in line:
                logger.debug("  Skip table cell: %s line %d", kf.name, i + 1)
                stats["gaps_unfilled"] += 1
                continue

            # Determine which section this placeholder belongs to.
            section_header = _find_section_for_line(
                [ln.rstrip("\r\n") for ln in lines], i
            )
            if section_header is None:
                logger.debug(
                    "  No section header found for: %s line %d", kf.name, i + 1
                )
                stats["gaps_unfilled"] += 1
                continue

            field = _SECTION_TO_FIELD.get(section_header)
            if field is None:
                # Section does not map to a known content field (e.g.,
                # "Key Differences vs Competitors"). Skip.
                logger.debug(
                    "  Unmapped section '%s': %s line %d",
                    section_header,
                    kf.name,
                    i + 1,
                )
                stats["gaps_unfilled"] += 1
                continue

            # Resolve the best available value for this field.
            value, source_name, confidence = resolve_field(field, sources)

            if value is None or confidence < _MIN_CONFIDENCE:
                logger.info(
                    "  No data: %s | %s | field=%s | conf=%.2f",
                    kf.name,
                    section_header,
                    field,
                    confidence,
                )
                stats["gaps_unfilled"] += 1
                continue

            # Determine if the placeholder is on a bullet line.
            stripped = line.lstrip()
            is_bullet = stripped.startswith("- ")

            formatted = _format_value(value, is_bullet)

            # Replace the placeholder within the line.
            # Preserve leading whitespace and bullet prefix.
            if is_bullet:
                # Replace just the placeholder portion, keeping "- " prefix.
                new_line = _PLACEHOLDER_RE.sub(formatted, line)
            else:
                # Standalone placeholder line: replace entire content after
                # any leading whitespace.
                match = _PLACEHOLDER_RE.search(line)
                if match:
                    # Check if there's content before/after the placeholder.
                    pre = line[: match.start()]
                    post = line[match.end() :]
                    # If the placeholder has a bold prefix like "**Label:**",
                    # keep it and append the value.
                    new_line = pre + formatted + post
                else:
                    new_line = formatted + "\n"

            lines[i] = new_line
            file_changed = True
            stats["gaps_filled"] += 1

            logger.info(
                "  FILL: %s | ## %s | field=%s | source=%s | conf=%.2f",
                kf.name,
                section_header,
                field,
                source_name,
                confidence,
            )
            if dry_run:
                # Show a preview of the replacement.
                preview = formatted[:120].replace("\n", " | ")
                logger.info("    -> %s", preview)

        if file_changed:
            stats["files_updated"] += 1
            if not dry_run:
                kf.write_text("".join(lines), encoding="utf-8")
                logger.info("  Wrote: %s", kf.name)
            else:
                logger.info("  Would write: %s", kf.name)

    return stats
