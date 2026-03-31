"""Entry point for Phase 1: FDA API scraping.

Usage:
    python -m pipeline.run_fda                      # All product codes
    python -m pipeline.run_fda --codes POL NRY      # Specific codes only
    python -m pipeline.run_fda --download-pdfs      # Also download 510(k) summary PDFs
    python -m pipeline.run_fda --max-pdfs 10        # Limit PDF downloads (for testing)
"""

import argparse
import asyncio
import json
from pathlib import Path

from rich.console import Console

from .config import PRODUCT_CODE_MAP, DATA_DIR
from .fda.scraper_510k import scrape_510k_all, print_discovery_report
from .fda.scraper_pma import scrape_pma_all, print_pma_report
from .fda.pdf_downloader import download_fda_pdfs

console = Console()


async def main(args: argparse.Namespace) -> None:
    all_devices = []

    # 510(k) scraping
    codes = args.codes if args.codes else None
    console.print("[bold]Phase 1a: Scraping FDA 510(k) database[/]\n")
    devices_510k = await scrape_510k_all(product_codes=codes)
    all_devices.extend(devices_510k)
    print_discovery_report(devices_510k)

    # PMA scraping
    if not args.codes:  # Only run PMA if not filtering by specific 510k codes
        console.print("\n[bold]Phase 1b: Scraping FDA PMA database[/]\n")
        devices_pma = await scrape_pma_all()
        all_devices.extend(devices_pma)
        print_pma_report(devices_pma)

    # Save combined discovery report
    report_path = DATA_DIR / "fda_raw" / "discovery_report.json"
    report_data = [d.model_dump() for d in all_devices]
    report_path.write_text(
        json.dumps(report_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"\n[bold green]Discovery report saved to {report_path}[/]")

    # Summary
    new_devices = [d for d in all_devices if not d.already_in_catalog]
    console.print(f"\n[bold]Total: {len(all_devices)} devices found, {len(new_devices)} new[/]")

    # PDF downloads
    if args.download_pdfs:
        console.print("\n[bold]Phase 1c: Downloading 510(k) summary PDFs[/]\n")
        # Only download PDFs for new devices (not already in catalog)
        download_targets = new_devices if not args.all_pdfs else all_devices
        await download_fda_pdfs(
            download_targets,
            max_downloads=args.max_pdfs,
        )


def cli() -> None:
    parser = argparse.ArgumentParser(description="Scrape FDA device databases")
    parser.add_argument(
        "--codes", nargs="+",
        help="Specific product codes to query (e.g., POL NRY). Default: all configured codes.",
    )
    parser.add_argument(
        "--download-pdfs", action="store_true",
        help="Download 510(k) summary PDFs from FDA.gov",
    )
    parser.add_argument(
        "--max-pdfs", type=int, default=None,
        help="Maximum number of PDFs to download (for testing)",
    )
    parser.add_argument(
        "--all-pdfs", action="store_true",
        help="Download PDFs for all devices, not just new ones",
    )
    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
