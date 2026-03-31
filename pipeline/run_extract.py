"""CLI entry point for extraction Tiers 1-2.

Usage:
    python -m pipeline.run_extract --evtoday           # Tier 1C
    python -m pipeline.run_extract --nspr-download     # Tier 1D: download NSPR PDFs
    python -m pipeline.run_extract --fda-summaries     # Tier 1A
    python -m pipeline.run_extract --fda-structured    # Tier 1B
    python -m pipeline.run_extract --documents         # Tier 2
    python -m pipeline.run_extract --all               # Everything
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from rich.console import Console

from .config import DATA_DIR

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def cli():
    parser = argparse.ArgumentParser(description="Run extraction pipeline")
    parser.add_argument("--evtoday", action="store_true", help="Tier 1C: EVToday device guide")
    parser.add_argument("--nspr-download", action="store_true", help="Tier 1D: download NSPR PDFs")
    parser.add_argument("--fda-summaries", action="store_true", help="Tier 1A: parse 510(k) PDFs")
    parser.add_argument("--fda-structured", action="store_true", help="Tier 1B: UDI/MAUDE/Recalls")
    parser.add_argument("--documents", action="store_true", help="Tier 2: extract brochures/guides")
    parser.add_argument("--all", action="store_true", help="Run all tiers")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    if args.evtoday or args.all:
        console.rule("[bold]Tier 1C: EVToday Device Guide")
        from .extraction.evtoday_scraper import scrape_all_categories
        counts = scrape_all_categories()
        console.print(f"  [green]{sum(counts.values())}[/green] devices")

    if args.nspr_download or args.all:
        console.rule("[bold]Tier 1D: NSPR PDF Download")
        from .extraction.nspr_scraper import download_nspr_pdfs, print_nspr_status
        print_nspr_status()
        n = download_nspr_pdfs()
        console.print(f"  [green]{n}[/green] PDFs downloaded")

    if args.fda_summaries or args.all:
        console.rule("[bold]Tier 1A: FDA 510(k) Summary Extraction")
        from .extraction.fda_parser import extract_all_fda_summaries
        results = extract_all_fda_summaries()
        console.print(f"  [green]{len(results)}[/green] PDFs extracted")

    if args.fda_structured or args.all:
        console.rule("[bold]Tier 1B: FDA Structured Data")
        from .extraction.fda_structured import extract_all_structured
        devices = _load_device_list()
        udi, maude, recalls = extract_all_structured(devices)
        console.print(
            f"  [green]{len(udi)}[/green] UDI, "
            f"[green]{len(maude)}[/green] MAUDE, "
            f"[green]{len(recalls)}[/green] recalls"
        )

    if args.documents or args.all:
        console.rule("[bold]Tier 2: Document Extraction")
        from .extraction.doc_extractor import extract_all_documents
        results = extract_all_documents()
        console.print(f"  [green]{len(results)}[/green] documents")


def _load_device_list() -> list[dict]:
    """Load merged device records as simple dicts for FDA API queries."""
    merged_dir = DATA_DIR / "merged"
    devices = []
    if merged_dir.exists():
        for f in merged_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            devices.append({
                "device_name": data.get("device_name", ""),
                "manufacturer": data.get("manufacturer", ""),
                "product_code": data.get("product_code", ""),
                "filename_stem": f.stem,
            })
    return devices


if __name__ == "__main__":
    cli()
