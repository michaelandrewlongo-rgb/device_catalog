"""Autonomous post-extraction pipeline.

Runs after Tier 2 document extraction completes. Handles:
1. Cross-referencing NSPR Tier 2 outputs to device stems
2. Re-enrichment with new data
3. Gap-filling curated files
4. Rewriting noisy FDA boilerplate
5. Regenerating catalog index

Usage:
    python -m pipeline.run_post_extract
    python -m pipeline.run_post_extract --dry-run
    python -m pipeline.run_post_extract --skip-enrich   # Skip enrichment (if already done)
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

from rich.console import Console

from .config import CATALOG_ROOT, DATA_DIR, EXTRACTED_DIR

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _cross_reference_nspr_documents() -> int:
    """Map NSPR Tier 2 outputs to device stems so the enricher can find them.

    NSPR PDFs have opaque filenames (e.g., '300223-us-d-ifuse-c-arm-stm.pdf')
    that don't match catalog device stems. This step reads the pdfs_index.json
    to get device_name/manufacturer, fuzzy-matches to catalog stems, and creates
    copies with stem-based names in the documents/ directory.

    Returns number of files cross-referenced.
    """
    doc_dir = EXTRACTED_DIR / "documents"
    nspr_dir = EXTRACTED_DIR / "nspr"
    index_path = nspr_dir / "pdfs_index.json"

    if not index_path.exists():
        logger.info("  No NSPR PDF index found, skipping cross-reference")
        return 0

    index = json.loads(index_path.read_text(encoding="utf-8"))

    # Build a map: pdf_filename -> (device_name, manufacturer) from the index
    pdf_to_device: dict[str, tuple[str, str]] = {}
    for entry in index:
        fname = entry.get("filename", "")
        pdf_to_device[fname] = (
            entry.get("device_name", ""),
            entry.get("manufacturer", ""),
        )

    # Load NSPR detail pages for richer device matching
    nspr_details: dict[str, dict] = {}
    for f in nspr_dir.glob("*.json"):
        if f.name.startswith("_") or f.name == "pdfs_index.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for pdf_url in data.get("pdfs", []):
            pdf_fname = pdf_url.split("/")[-1]
            nspr_details[pdf_fname] = {
                "device_name": data.get("device_name", ""),
                "manufacturer": data.get("manufacturer", ""),
                "slug": f.stem,
            }

    # Build set of catalog stems for matching
    catalog_stems: dict[str, str] = {}  # lowercase product words -> stem
    for kf in CATALOG_ROOT.glob("*--knowledge.md"):
        stem = kf.name.replace("--knowledge.md", "")
        parts = stem.split("--")
        if len(parts) >= 3:
            product = parts[2].replace("-", " ").lower()
            catalog_stems[product] = stem

    # Also index merged records for broader matching
    merged_dir = DATA_DIR / "merged"
    merged_stems: dict[str, str] = {}  # lowercase device_name -> stem
    if merged_dir.exists():
        for f in merged_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            name = (data.get("device_name") or "").lower().strip()
            if name:
                merged_stems[name] = f.stem

    linked = 0
    for nspr_doc in sorted(doc_dir.glob("nspr--*.json")):
        pdf_fname = nspr_doc.stem.replace("nspr--", "") + ".pdf"

        # Get device info from index or detail pages
        dev_name = ""
        dev_mfr = ""
        if pdf_fname in nspr_details:
            dev_name = nspr_details[pdf_fname].get("device_name", "")
            dev_mfr = nspr_details[pdf_fname].get("manufacturer", "")
        elif pdf_fname in pdf_to_device:
            dev_name, dev_mfr = pdf_to_device[pdf_fname]

        if not dev_name:
            continue

        # Try to match to a catalog stem
        dev_lower = dev_name.lower().strip()
        matched_stem = None

        # Exact match in merged records
        if dev_lower in merged_stems:
            matched_stem = merged_stems[dev_lower]

        # Fuzzy match: check if product words overlap with catalog stems
        if not matched_stem:
            dev_words = set(dev_lower.split()) - {
                "system", "device", "spinal", "spine", "the", "and", "for",
                "with", "inc", "llc", "pedicle", "screw", "cage",
            }
            best_score = 0
            for product, stem in catalog_stems.items():
                prod_words = set(product.split()) - {
                    "system", "device", "spinal", "spine", "the", "and", "for",
                    "with", "inc", "llc", "pedicle", "screw", "cage",
                }
                overlap = len(dev_words & prod_words)
                if overlap >= 2 and overlap > best_score:
                    best_score = overlap
                    matched_stem = stem

        if matched_stem:
            # Copy the NSPR Tier 2 output with the device stem name
            dest = doc_dir / f"nspr-technique--{matched_stem}.json"
            if not dest.exists():
                shutil.copy2(nspr_doc, dest)
                linked += 1
                logger.info("  Linked: %s -> %s", nspr_doc.name, dest.name)

    return linked


def _run_enrichment() -> int:
    """Run Tier 3 enrichment. Returns count of enriched devices."""
    from .extraction.enricher import enrich_all

    results = enrich_all()
    return len(results)


def _run_gap_fill(dry_run: bool = False) -> dict:
    """Run gap-fill on curated files."""
    from .processing.gap_filler import fill_gaps

    return fill_gaps(dry_run=dry_run)


def _run_rewrite(dry_run: bool = False) -> dict:
    """Run boilerplate rewriter on curated files."""
    from .processing.rewriter import rewrite_noisy_files

    return rewrite_noisy_files(dry_run=dry_run)


def _regenerate_index():
    """Regenerate CATALOG_INDEX.md."""
    from .processing.indexer import generate_catalog_index

    generate_catalog_index()


def _count_gaps() -> tuple[int, int]:
    """Count files with gaps and total gap instances."""
    files_with_gaps = 0
    total_gaps = 0
    for f in sorted(CATALOG_ROOT.glob("*--knowledge.md")):
        text = f.read_text(encoding="utf-8")
        count = text.count("[NEEDS CONTENT")
        if count > 0:
            files_with_gaps += 1
            total_gaps += count
    return files_with_gaps, total_gaps


def cli():
    parser = argparse.ArgumentParser(description="Post-extraction autonomous pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip enrichment step")
    args = parser.parse_args()

    console.rule("[bold]Post-Extraction Pipeline")
    start = time.time()

    # Step 0: Pre-flight checks
    console.rule("[bold cyan]Step 0: Pre-flight")
    doc_dir = EXTRACTED_DIR / "documents"
    nspr_docs = list(doc_dir.glob("nspr--*.json")) if doc_dir.exists() else []
    console.print(f"  NSPR Tier 2 documents: {len(nspr_docs)}")

    curated = list(CATALOG_ROOT.glob("*--knowledge.md"))
    console.print(f"  Curated knowledge files: {len(curated)}")

    gap_files, gap_count = _count_gaps()
    console.print(f"  Files with gaps: {gap_files} ({gap_count} instances)")

    # Step 1: Cross-reference NSPR Tier 2 to device stems
    console.rule("[bold cyan]Step 1: Cross-reference NSPR documents")
    if not args.dry_run:
        linked = _cross_reference_nspr_documents()
        console.print(f"  [green]{linked}[/green] NSPR documents cross-referenced to device stems")
    else:
        console.print("  [yellow]DRY RUN[/yellow] -- skipping cross-reference")

    # Step 2: Re-run enrichment
    if not args.skip_enrich:
        console.rule("[bold cyan]Step 2: Enrichment")
        if not args.dry_run:
            try:
                enriched = _run_enrichment()
                console.print(f"  [green]{enriched}[/green] devices enriched")
            except Exception as exc:
                console.print(f"  [red]Enrichment failed: {exc}[/red]")
                console.print("  Continuing with remaining steps...")
        else:
            console.print("  [yellow]DRY RUN[/yellow] -- skipping enrichment")
    else:
        console.print("[dim]Step 2: Enrichment -- skipped[/dim]")

    # Step 3: Gap-fill
    console.rule("[bold cyan]Step 3: Gap-fill")
    try:
        gap_result = _run_gap_fill(dry_run=args.dry_run)
        console.print(
            f"  Scanned: {gap_result['files_scanned']}, "
            f"Filled: {gap_result['gaps_filled']}, "
            f"Unfilled: {gap_result['gaps_unfilled']}"
        )
    except Exception as exc:
        console.print(f"  [red]Gap-fill failed: {exc}[/red]")

    # Step 4: Rewrite noisy sections
    console.rule("[bold cyan]Step 4: Rewrite noisy sections")
    try:
        rewrite_result = _run_rewrite(dry_run=args.dry_run)
        console.print(
            f"  Scanned: {rewrite_result['files_scanned']}, "
            f"Rewritten: {rewrite_result['files_rewritten']}, "
            f"Sections replaced: {rewrite_result['sections_replaced']}"
        )
    except Exception as exc:
        console.print(f"  [red]Rewrite failed: {exc}[/red]")

    # Step 5: Regenerate index
    console.rule("[bold cyan]Step 5: Regenerate catalog index")
    if not args.dry_run:
        try:
            _regenerate_index()
            console.print("  [green]CATALOG_INDEX.md regenerated[/green]")
        except Exception as exc:
            console.print(f"  [red]Index generation failed: {exc}[/red]")
    else:
        console.print("  [yellow]DRY RUN[/yellow] -- skipping index")

    # Summary
    console.rule("[bold green]Pipeline Complete")
    elapsed = time.time() - start

    if not args.dry_run:
        new_gap_files, new_gap_count = _count_gaps()
        console.print(f"  Gaps: {gap_count} -> {new_gap_count} instances")
        console.print(f"  Files with gaps: {gap_files} -> {new_gap_files}")

    curated_now = len(list(CATALOG_ROOT.glob("*--knowledge.md")))
    console.print(f"  Curated files: {curated_now}")
    console.print(f"  Elapsed: {elapsed:.0f}s")


if __name__ == "__main__":
    cli()
