"""Rewrite noisy sections in curated knowledge files using Tier 2 DeepSeek extractions.

Detects FDA regulatory boilerplate in knowledge file sections and replaces with
cleaner Tier 2 structured extraction data when available.

Does NOT call DeepSeek or any LLM. Only reads existing Tier 2 JSON extractions
from pipeline/data/extracted/documents/.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import CATALOG_ROOT, EXTRACTED_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Boilerplate detection
# ---------------------------------------------------------------------------

BOILERPLATE_MARKERS = [
    "807.92", "PRA Staff", "AAMI", "SAL 10-6", "SUBMITTER",
    "Paperwork Reduction Act", "OMB number", "FORM FDA",
    "PSC Publishing", "EO sterilization", "ISO 10993",
    "Limulus amebocyte", "SAL of at least", "Kligman Maximization",
    "ASTM F1980", "SUBSTANTIAL EQUIVALENCE", "21 CFR",
    "Sterility assurance level", "shelf life", "shelf-life",
    "accelerated aging", "Non-cytotoxic", "Non-pyrogenic",
    "Hemocompatibility", "Rabbit Pyrogen", "Sensitization",
    "Intracutaneous Injection", "Acute Systemic Injection",
    "K243383", "K141751", "K022762",
]

# Lowercase versions for case-insensitive matching.
_MARKERS_LOWER = [m.lower() for m in BOILERPLATE_MARKERS]

# Sections that should never be rewritten (manually curated or special).
_PROTECTED_SECTIONS = {
    "key differences vs competitors",
    "also known as",
    "source",
}

# Section header -> Tier 2 JSON field name.
SECTION_TO_FIELD: dict[str, str] = {
    "what it is": "what_it_is",
    "sizing/specs": "sizing_specs",
    "indications": "indications",
    "contraindications": "contraindications",
    "compatible with": "compatible_with",
    "use notes": "use_notes",
}

# Maximum section body length before flagging as likely raw dump.
_LENGTH_THRESHOLDS: dict[str, int] = {
    "what it is": 2000,
    "sizing/specs": 3000,
}
_DEFAULT_LENGTH_THRESHOLD = 5000  # generous fallback; only markers usually trigger

# Tier 2 doc-type priority (lower index = higher priority).
_DOCTYPE_PRIORITY = ["ifu", "technique", "510k", "brochure"]


def _count_markers(text: str) -> int:
    """Count how many distinct boilerplate markers appear in text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for m in _MARKERS_LOWER if m in text_lower)


def _is_noisy(section_header: str, section_body: str) -> bool:
    """Return True if a section body contains regulatory boilerplate or is excessively long."""
    marker_count = _count_markers(section_body)
    if marker_count >= 2:
        return True
    threshold = _LENGTH_THRESHOLDS.get(section_header.lower(), _DEFAULT_LENGTH_THRESHOLD)
    if len(section_body) > threshold:
        return True
    return False


# ---------------------------------------------------------------------------
# Knowledge file parsing
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _parse_knowledge_file(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse a knowledge file into a preamble and list of (header, body) sections.

    The preamble includes everything before the first ## header (H1 title,
    manufacturer/category metadata, 510(k) line, etc.).

    Returns:
        (preamble, [(section_header, section_body), ...])
    """
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return text, []

    preamble = text[:matches[0].start()]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        header = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        sections.append((header, body))
    return preamble, sections


def _reassemble(preamble: str, sections: list[tuple[str, str]]) -> str:
    """Reassemble a knowledge file from preamble + sections."""
    parts = [preamble]
    for header, body in sections:
        parts.append(f"## {header}{body}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Tier 2 extraction lookup
# ---------------------------------------------------------------------------

def _find_tier2_data(stem: str) -> dict[str, str | None]:
    """Load and merge Tier 2 extraction data for a device stem.

    Searches pipeline/data/extracted/documents/ for JSON files whose name
    starts with the device stem. Merges fields with doc-type priority:
    ifu > technique > 510k > brochure.

    Returns a dict of field_name -> value (or None if not available).
    """
    docs_dir = EXTRACTED_DIR / "documents"
    if not docs_dir.is_dir():
        return {}

    # Collect matching JSON files grouped by doc type.
    matches: dict[str, Path] = {}
    for json_path in docs_dir.glob(f"{stem}--*.json"):
        # Extract doc type from filename: stem--{doctype}.json
        suffix_part = json_path.stem[len(stem) + 2:]  # after stem--
        matches[suffix_part] = json_path

    if not matches:
        return {}

    # Sort by priority.
    sorted_doctypes = sorted(
        matches.keys(),
        key=lambda dt: _DOCTYPE_PRIORITY.index(dt) if dt in _DOCTYPE_PRIORITY else len(_DOCTYPE_PRIORITY),
    )

    # Merge fields: first non-null wins (highest priority doc type).
    merged: dict[str, str | None] = {}
    for dt in sorted_doctypes:
        try:
            data = json.loads(matches[dt].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read %s: %s", matches[dt], exc)
            continue

        fields = data.get("fields", {})
        for field_name, value in fields.items():
            if field_name not in merged or merged[field_name] is None:
                if value is not None and str(value).strip():
                    merged[field_name] = str(value).strip()

    return merged


# ---------------------------------------------------------------------------
# Main rewrite logic
# ---------------------------------------------------------------------------

def rewrite_noisy_files(dry_run: bool = False) -> dict:
    """Rewrite noisy sections in curated knowledge files.

    Scans all *--knowledge.md files in the catalog root for sections containing
    FDA regulatory boilerplate. When Tier 2 extraction data is available for the
    noisy section, replaces the section body with the cleaner extracted content.

    Args:
        dry_run: If True, print what would change without modifying files.

    Returns:
        dict with keys: files_scanned, files_rewritten, sections_replaced,
        sections_skipped_no_data.
    """
    stats = {
        "files_scanned": 0,
        "files_rewritten": 0,
        "sections_replaced": 0,
        "sections_skipped_no_data": 0,
    }

    knowledge_files = sorted(CATALOG_ROOT.glob("*--knowledge.md"))
    stats["files_scanned"] = len(knowledge_files)

    for kf_path in knowledge_files:
        stem = kf_path.stem.replace("--knowledge", "")
        text = kf_path.read_text(encoding="utf-8")
        preamble, sections = _parse_knowledge_file(text)

        if not sections:
            continue

        tier2 = None  # lazy-load only if needed
        file_changed = False
        new_sections: list[tuple[str, str]] = []

        for header, body in sections:
            header_lower = header.lower()

            # Never touch protected sections.
            if header_lower in _PROTECTED_SECTIONS:
                new_sections.append((header, body))
                continue

            # Check if this section is noisy.
            if not _is_noisy(header_lower, body):
                new_sections.append((header, body))
                continue

            # Section is noisy. Look up the corresponding Tier 2 field.
            field_name = SECTION_TO_FIELD.get(header_lower)
            if field_name is None:
                # Unmapped section header; leave as-is.
                new_sections.append((header, body))
                continue

            # Lazy-load Tier 2 data.
            if tier2 is None:
                tier2 = _find_tier2_data(stem)

            replacement = tier2.get(field_name)
            if not replacement:
                # No Tier 2 data available; keep original noisy content.
                stats["sections_skipped_no_data"] += 1
                if dry_run:
                    logger.info(
                        "  [skip] %s :: %s -- noisy (%d markers, %d chars) but no Tier 2 data",
                        kf_path.name, header, _count_markers(body), len(body),
                    )
                new_sections.append((header, body))
                continue

            # Replace the section body.
            old_len = len(body.strip())
            new_body = f"\n\n{replacement}\n\n"
            new_len = len(replacement)

            if dry_run:
                logger.info(
                    "  [rewrite] %s :: %s -- %d chars -> %d chars (%d markers)",
                    kf_path.name, header, old_len, new_len, _count_markers(body),
                )
            else:
                logger.info(
                    "  Rewrote %s :: %s (%d -> %d chars)",
                    kf_path.name, header, old_len, new_len,
                )

            new_sections.append((header, new_body))
            stats["sections_replaced"] += 1
            file_changed = True

        if file_changed:
            stats["files_rewritten"] += 1
            if not dry_run:
                new_text = _reassemble(preamble, new_sections)
                kf_path.write_text(new_text, encoding="utf-8")

    return stats
