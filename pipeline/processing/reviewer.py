"""Generate a human review manifest for drafted knowledge files."""

from pathlib import Path
from datetime import date

from .merger import MergedDeviceRecord
from ..config import DATA_DIR

DRAFTS_DIR = DATA_DIR / "drafts"


def count_populated_sections(record: MergedDeviceRecord) -> tuple[int, int]:
    """Count populated vs placeholder sections.

    Returns:
        (populated_count, total_count)
    """
    sections = [
        record.what_it_is,
        record.sizing_specs,
        record.indications,
        record.contraindications,
        record.compatible_with,
        record.use_notes,
        record.deployment_steps,
    ]
    total = len(sections)
    populated = sum(1 for s in sections if s)
    return populated, total


def quality_tier(populated: int) -> str:
    """Return quality tier based on populated section count."""
    if populated >= 4:
        return "ready"
    elif populated >= 1:
        return "partial"
    return "empty"


def generate_review_manifest(
    records: list[MergedDeviceRecord],
    generated_files: list[tuple[str, Path]],
) -> Path:
    """Generate REVIEW_MANIFEST.md summarizing all drafted files.

    Args:
        records: Merged records that were used to generate drafts.
        generated_files: List of (stem, path) from template generation.

    Returns:
        Path to the generated manifest file.
    """
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = DRAFTS_DIR / "REVIEW_MANIFEST.md"

    # Build lookup from stem to record
    stem_to_record: dict[str, MergedDeviceRecord] = {}
    for record in records:
        stem_to_record[record.filename_stem] = record

    # Group by category
    by_category: dict[str, list[tuple[str, Path, MergedDeviceRecord | None]]] = {}
    for stem, path in generated_files:
        record = stem_to_record.get(stem)
        category = record.catalog_category if record else "unknown"
        if category not in by_category:
            by_category[category] = []
        by_category[category].append((stem, path, record))

    lines: list[str] = []
    lines.append(f"# Review Manifest")
    lines.append(f"")
    lines.append(f"Generated: {date.today().isoformat()}")
    lines.append(f"Total drafts: {len(generated_files)}")
    lines.append(f"")

    # Summary counts
    needs_review_count = sum(
        1 for r in records if r.needs_review and r.catalog_category != "unknown"
    )
    fda_only = sum(1 for r in records if r.data_sources == ["fda"])
    scraper_only = sum(1 for r in records if r.data_sources == ["scraper"])
    paired = sum(1 for r in records if len(r.data_sources) == 2)

    lines.append(f"## Summary")
    lines.append(f"")
    lines.append(f"- **Paired (FDA + scraper):** {paired}")
    lines.append(f"- **FDA-only:** {fda_only}")
    lines.append(f"- **Scraper-only:** {scraper_only}")
    lines.append(f"- **Needs review:** {needs_review_count}")
    lines.append(f"")
    gen_stems = {stem for stem, _ in generated_files}
    gen_records = [r for r in records if r.filename_stem in gen_stems]
    ready = sum(1 for r in gen_records if quality_tier(count_populated_sections(r)[0]) == "ready")
    partial = sum(1 for r in gen_records if quality_tier(count_populated_sections(r)[0]) == "partial")
    empty = sum(1 for r in gen_records if quality_tier(count_populated_sections(r)[0]) == "empty")
    lines.append(f"- **Ready for review (4+ sections):** {ready}")
    lines.append(f"- **Partial (1-3 sections):** {partial}")
    lines.append(f"- **Empty (0 sections):** {empty}")
    lines.append(f"")

    # Per-category tables
    for category in sorted(by_category.keys()):
        entries = by_category[category]
        lines.append(f"## {category.replace('-', ' ').title()} ({len(entries)} devices)")
        lines.append(f"")
        lines.append(f"| File | Confidence | Sections | Quality | Sources | Review |")
        lines.append(f"|------|-----------|----------|---------|---------|--------|")

        for stem, path, record in sorted(entries, key=lambda x: x[0]):
            if record:
                pop, total = count_populated_sections(record)
                conf = f"{record.confidence_score:.1f}"
                sources = "+".join(record.data_sources)
                review = "REVIEW" if record.needs_review else "ok"
                tier = quality_tier(pop)
            else:
                pop, total = 0, 7
                conf = "?"
                sources = "?"
                review = "REVIEW"
                tier = "empty"

            lines.append(
                f"| `{path.name}` | {conf} | {pop}/{total} | {tier} | {sources} | {review} |"
            )

        lines.append(f"")

    # Instructions
    lines.append(f"## How to Review")
    lines.append(f"")
    lines.append(f"1. Open each draft file in `{DRAFTS_DIR}`")
    lines.append(f"2. Search for `[NEEDS CONTENT` to find placeholder sections")
    lines.append(f"3. Fill in clinical detail from IFU PDFs or other sources")
    lines.append(f"4. When satisfied, move the file to the catalog root directory")
    lines.append(f"5. Rename the paired PDF (if downloaded) to match the naming convention")

    content = "\n".join(lines) + "\n"
    manifest_path.write_text(content, encoding="utf-8")

    return manifest_path
