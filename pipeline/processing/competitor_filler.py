"""Fill competitor comparison gaps using DeepSeek synthesis from catalog data.

Groups curated knowledge files by category, extracts factual content from each,
and asks DeepSeek to write grounded comparisons using ONLY the provided data.

Does NOT invent specifications. Instructs DeepSeek to state "not specified"
for any missing data. Only replaces the exact competitor comparison placeholder.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from pathlib import Path

from ..config import CATALOG_ROOT
from ..extraction.deepseek import deepseek_extract

logger = logging.getLogger(__name__)

# The exact placeholder text to find and replace.
_COMPETITOR_PLACEHOLDER = (
    "[NEEDS CONTENT - head-to-head comparison with competing devices in same category]"
)

# Sections to extract from knowledge files for comparison context.
_EXTRACT_SECTIONS = [
    "What It Is",
    "Sizing/Specs",
    "Indications",
    "Compatible With",
    "Use Notes",
]

# Maximum competitor summaries to include when category is large.
_MAX_COMPETITORS = 8

# Word limit per competitor summary for large categories.
_WORDS_PER_COMPETITOR_LARGE = 150

# Word limit per competitor summary for normal categories.
_WORDS_PER_COMPETITOR_NORMAL = 200

# Threshold for "large" category triggering truncation.
_LARGE_CATEGORY_THRESHOLD = 10


def _parse_category(filename: str) -> str:
    """Extract category (first segment) from a knowledge filename."""
    return filename.split("--")[0]


def _parse_manufacturer(filename: str) -> str:
    """Extract manufacturer (second segment) from a knowledge filename."""
    parts = filename.split("--")
    return parts[1] if len(parts) > 1 else ""


def _extract_device_info(filepath: Path) -> dict | None:
    """Read a knowledge file and extract structured section content.

    Returns dict with keys: name, manufacturer, category, sections, filepath.
    Returns None if the file cannot be read.
    """
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read %s: %s", filepath.name, exc)
        return None

    lines = text.splitlines()

    # Extract H1 title (device name).
    name = filepath.stem.split("--")[2].replace("-", " ") if len(filepath.stem.split("--")) > 2 else ""
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            name = line[2:].strip()
            break

    manufacturer = _parse_manufacturer(filepath.name)
    category = _parse_category(filepath.name)

    # Extract section content.
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            # Save previous section.
            if current_section and current_lines:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    # Save last section.
    if current_section and current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    # Filter to only the sections we care about.
    relevant = {}
    for sec_name in _EXTRACT_SECTIONS:
        if sec_name in sections:
            content = sections[sec_name]
            # Skip sections that are just placeholders.
            if content and "[NEEDS CONTENT" not in content:
                relevant[sec_name] = content

    return {
        "name": name,
        "manufacturer": manufacturer,
        "category": category,
        "sections": relevant,
        "filepath": filepath,
        "has_placeholder": _COMPETITOR_PLACEHOLDER in text,
    }


def _truncate_text(text: str, max_words: int) -> str:
    """Truncate text to approximately max_words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def _build_competitor_summary(device: dict, max_words: int) -> str:
    """Build a concise summary of a device for the comparison prompt."""
    parts = [f"**{device['name']}** by {device['manufacturer']}"]
    for sec_name, content in device["sections"].items():
        truncated = _truncate_text(content, max_words // max(len(device["sections"]), 1))
        parts.append(f"  {sec_name}: {truncated}")
    return "\n".join(parts)


def _build_target_sections(device: dict) -> str:
    """Build the target device's section text for the prompt."""
    if not device["sections"]:
        return "(No detailed sections available for this device.)"
    parts = []
    for sec_name, content in device["sections"].items():
        parts.append(f"{sec_name}:\n{content}")
    return "\n\n".join(parts)


def _select_competitors(
    target: dict, category_devices: list[dict]
) -> list[dict]:
    """Select and order competitors for the prompt.

    For large categories (10+), pick up to _MAX_COMPETITORS:
    same-manufacturer devices first, then alphabetical.
    """
    others = [d for d in category_devices if d["filepath"] != target["filepath"]]

    if len(others) <= _MAX_COMPETITORS:
        return others

    # Prioritize same manufacturer, then alphabetical.
    same_mfr = [d for d in others if d["manufacturer"] == target["manufacturer"]]
    diff_mfr = [d for d in others if d["manufacturer"] != target["manufacturer"]]
    diff_mfr.sort(key=lambda d: d["name"].lower())

    selected = same_mfr[:_MAX_COMPETITORS]
    remaining = _MAX_COMPETITORS - len(selected)
    if remaining > 0:
        selected.extend(diff_mfr[:remaining])

    return selected


def _build_prompt(target: dict, competitors: list[dict], category: str) -> str:
    """Build the DeepSeek prompt for competitor comparison."""
    is_large = len(competitors) >= _LARGE_CATEGORY_THRESHOLD
    words_limit = _WORDS_PER_COMPETITOR_LARGE if is_large else _WORDS_PER_COMPETITOR_NORMAL

    target_sections = _build_target_sections(target)

    competitor_summaries = []
    for comp in competitors:
        summary = _build_competitor_summary(comp, words_limit)
        competitor_summaries.append(summary)

    competitors_text = "\n\n".join(competitor_summaries)

    return f"""You are comparing medical devices in the {category} category.

TARGET DEVICE: {target['name']} by {target['manufacturer']}
Target device details:
{target_sections}

OTHER DEVICES IN THIS CATEGORY:
{competitors_text}

Write a concise comparison section for the target device's knowledge file.
Format as 3-5 bullet points highlighting key differences vs competitors.
Use ONLY the data provided above. If a spec is not available for a device, say "not specified" rather than guessing.
Do not invent dimensions, materials, indications, or compatibility details.
Keep the comparison factual and clinically relevant.

Return JSON: {{"comparison": "the markdown text"}}"""


def fill_competitors(
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    """Fill competitor comparison gaps using DeepSeek synthesis.

    Args:
        dry_run: If True, print what would be generated but don't write
                 files or call DeepSeek.
        limit: If set, process only the first N files (for testing).

    Returns:
        dict with keys: files_scanned, files_updated, gaps_filled,
        gaps_skipped, api_calls.
    """
    stats = {
        "files_scanned": 0,
        "files_updated": 0,
        "gaps_filled": 0,
        "gaps_skipped": 0,
        "api_calls": 0,
    }

    # Step a: Glob all curated knowledge files and group by category.
    all_knowledge = sorted(CATALOG_ROOT.glob("*--knowledge.md"))
    logger.info("Found %d curated knowledge files", len(all_knowledge))

    # Extract device info from all files.
    devices: list[dict] = []
    for kf in all_knowledge:
        info = _extract_device_info(kf)
        if info:
            devices.append(info)

    # Group by category.
    by_category: dict[str, list[dict]] = defaultdict(list)
    for d in devices:
        by_category[d["category"]].append(d)

    # Find files with the competitor placeholder.
    targets = [d for d in devices if d["has_placeholder"]]
    logger.info(
        "Found %d files with competitor comparison placeholder across %d categories",
        len(targets),
        len({t["category"] for t in targets}),
    )

    # Skip categories with < 2 devices (can't compare).
    eligible = []
    for t in targets:
        cat_count = len(by_category[t["category"]])
        if cat_count < 2:
            logger.info(
                "  SKIP (only %d device in category): %s",
                cat_count,
                t["filepath"].name,
            )
            stats["gaps_skipped"] += 1
        else:
            eligible.append(t)

    stats["files_scanned"] = len(targets)

    if limit is not None:
        eligible = eligible[:limit]
        logger.info("Limited to first %d eligible files", limit)

    # Process each eligible target.
    for i, target in enumerate(eligible):
        category = target["category"]
        category_devices = by_category[category]
        competitors = _select_competitors(target, category_devices)

        if dry_run:
            logger.info(
                "  [DRY RUN] %s | category=%s | competitors=%d",
                target["filepath"].name,
                category,
                len(competitors),
            )
            continue

        # Build prompt and call DeepSeek.
        prompt = _build_prompt(target, competitors, category)
        stats["api_calls"] += 1

        logger.info(
            "  [%d/%d] Calling DeepSeek for %s (%d competitors)",
            i + 1,
            len(eligible),
            target["filepath"].name,
            len(competitors),
        )

        result = deepseek_extract(prompt, max_tokens=1024)

        if result is None or not result.get("comparison"):
            logger.warning("  Empty response for %s, skipping", target["filepath"].name)
            stats["gaps_skipped"] += 1
        else:
            comparison_text = result["comparison"].strip()
            _replace_placeholder(target["filepath"], comparison_text)
            stats["gaps_filled"] += 1
            stats["files_updated"] += 1
            logger.info("  Filled: %s", target["filepath"].name)

        # Rate limiting: 1-second delay between API calls.
        if i < len(eligible) - 1:
            time.sleep(1)

    return stats


def _replace_placeholder(filepath: Path, replacement: str) -> None:
    """Replace the competitor comparison placeholder in a file.

    Only replaces the exact _COMPETITOR_PLACEHOLDER string.
    Does not modify any other content.
    """
    text = filepath.read_text(encoding="utf-8")
    if _COMPETITOR_PLACEHOLDER not in text:
        logger.warning("Placeholder not found in %s", filepath.name)
        return

    new_text = text.replace(_COMPETITOR_PLACEHOLDER, replacement)
    filepath.write_text(new_text, encoding="utf-8")
