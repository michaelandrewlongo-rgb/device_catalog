"""Entry point for the full pipeline: FDA scrape -> manufacturer scrape -> merge -> generate.

Usage:
    python -m pipeline.run_pipeline                    # Full pipeline
    python -m pipeline.run_pipeline --fda-only         # Just FDA + generate (no manufacturer scraping)
    python -m pipeline.run_pipeline --merge-only       # Just merge + generate from existing data
    python -m pipeline.run_pipeline --download-pdfs    # Also download PDFs
"""

import argparse
import asyncio
import json
from pathlib import Path

from rich.console import Console

from .config import DATA_DIR
from .fda.models import FDADeviceRecord
from .fda.scraper_510k import scrape_510k_all, print_discovery_report
from .fda.scraper_pma import scrape_pma_all, print_pma_report
from .fda.pdf_downloader import download_fda_pdfs
from .scrapers.base import ScrapedProduct
from .processing.merger import merge_records
from .processing.template import generate_drafts
from .processing.reviewer import generate_review_manifest
from .processing.indexer import generate_catalog_index

console = Console()


def load_fda_from_disk() -> list[FDADeviceRecord]:
    """Load previously scraped FDA records from data/fda_raw/."""
    devices = []
    fda_dir = DATA_DIR / "fda_raw"

    report_path = fda_dir / "discovery_report.json"
    if report_path.exists():
        data = json.loads(report_path.read_text(encoding="utf-8"))
        devices = [FDADeviceRecord(**d) for d in data]
        console.print(f"  Loaded {len(devices)} FDA records from discovery report")
        return devices

    # Fallback: load individual JSON files
    for code_dir in fda_dir.iterdir():
        if code_dir.is_dir() and code_dir.name != "pma":
            for f in code_dir.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                devices.append(FDADeviceRecord(**data))

    pma_dir = fda_dir / "pma"
    if pma_dir.exists():
        for f in pma_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            devices.append(FDADeviceRecord(**data))

    console.print(f"  Loaded {len(devices)} FDA records from individual files")
    return devices


def load_scraped_from_disk() -> list[ScrapedProduct]:
    """Load previously scraped manufacturer data from data/scraper_raw/."""
    products = []
    scraper_dir = DATA_DIR / "scraper_raw"

    if not scraper_dir.exists():
        return products

    for mfr_dir in scraper_dir.iterdir():
        if mfr_dir.is_dir():
            for f in mfr_dir.glob("*.json"):
                if f.name == "failed_urls.txt":
                    continue
                data = json.loads(f.read_text(encoding="utf-8"))
                products.append(ScrapedProduct(**data))

    console.print(f"  Loaded {len(products)} scraped products from disk")
    return products


async def main(args: argparse.Namespace) -> None:
    fda_devices: list[FDADeviceRecord] = []
    scraped_products: list[ScrapedProduct] = []

    if args.index_only:
        index_path = generate_catalog_index()
        console.print(f"[bold green]Catalog index: {index_path}[/]")
        return

    if args.merge_only:
        # Load from disk
        console.print("[bold]Loading existing data from disk...[/]")
        fda_devices = load_fda_from_disk()
        scraped_products = load_scraped_from_disk()
    else:
        # Phase 1: FDA
        console.print("[bold]Phase 1: FDA API Scraping[/]\n")
        fda_510k = await scrape_510k_all()
        fda_devices.extend(fda_510k)
        print_discovery_report(fda_510k)

        fda_pma = await scrape_pma_all()
        fda_devices.extend(fda_pma)
        print_pma_report(fda_pma)

        # Save discovery report
        report_path = DATA_DIR / "fda_raw" / "discovery_report.json"
        report_path.write_text(
            json.dumps([d.model_dump() for d in fda_devices], indent=2),
            encoding="utf-8",
        )

        # Phase 1c: PDF downloads
        if args.download_pdfs:
            console.print("\n[bold]Downloading 510(k) summary PDFs...[/]\n")
            new_devices = [d for d in fda_devices if not d.already_in_catalog]
            await download_fda_pdfs(new_devices)

        # Phase 2: Manufacturer scraping (unless fda-only)
        if not args.fda_only:
            console.print("\n[bold]Phase 2: Manufacturer Website Scraping[/]\n")
            from .scrapers.penumbra import PenumbraScraper
            from .scrapers.stryker import StrykerScraper
            from .scrapers.medtronic import MedtronicScraper
            from .scrapers.cerenovus import CerenovusScraper
            from .scrapers.microvention import MicroVentionScraper
            from .scrapers.balt import BaltScraper
            from .scrapers.integra import IntegraScraper

            for ScraperClass in [
                PenumbraScraper, StrykerScraper, MedtronicScraper,
                CerenovusScraper, MicroVentionScraper, BaltScraper, IntegraScraper,
            ]:
                scraper = ScraperClass()
                console.print(f"\n[bold]Scraping {scraper.manufacturer}...[/]")
                products = await scraper.run()
                scraped_products.extend(products)

                # Download IFU PDFs from manufacturer pages
                if args.download_pdfs:
                    from .fda.pdf_downloader import download_manufacturer_pdf
                    from .processing.naming import make_filename_stem
                    for p in products:
                        if p.ifu_pdf_url:
                            stem = make_filename_stem(
                                p.category_hint or "unknown", p.manufacturer, p.device_name
                            )
                            await download_manufacturer_pdf(p.ifu_pdf_url, stem, "ifu")

    # Phase 3: Merge and generate
    console.print("\n[bold]Phase 3: Merging and Generating Drafts[/]\n")

    manual_matches_path = DATA_DIR / "manual_matches.json"
    merged = merge_records(
        fda_devices,
        scraped_products,
        manual_matches_path=manual_matches_path if manual_matches_path.exists() else None,
    )

    # Save merged records
    merged_dir = DATA_DIR / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    for record in merged:
        if record.filename_stem:
            fname = f"{record.filename_stem}.json"
            (merged_dir / fname).write_text(
                json.dumps(record.__dict__, indent=2, default=str),
                encoding="utf-8",
            )

    # Generate drafts
    generated = generate_drafts(merged, skip_fda_only=not args.all_drafts)

    fda_only_count = sum(1 for r in merged if r.data_sources == ["fda"])
    if not args.all_drafts:
        console.print(f"  [dim]Skipped {fda_only_count} FDA-only records (use --all-drafts to include)[/]")
    console.print(f"\n[bold green]Generated {len(generated)} draft knowledge files[/]")

    # Generate review manifest
    manifest_path = generate_review_manifest(merged, generated)
    console.print(f"[bold]Review manifest: {manifest_path}[/]")

    index_path = generate_catalog_index()
    console.print(f"[bold]Catalog index: {index_path}[/]")

    # Final summary
    console.print(f"\n{'=' * 60}")
    console.print(f"[bold]Pipeline Complete[/]")
    console.print(f"  FDA devices found: {len(fda_devices)}")
    console.print(f"  Scraped products: {len(scraped_products)}")
    console.print(f"  Merged records: {len(merged)}")
    console.print(f"  Drafts generated: {len(generated)}")
    console.print(f"  Output directory: {DATA_DIR / 'drafts'}")
    console.print(f"\n[dim]Review drafts and move approved files to the catalog root.[/]")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run the full device catalog pipeline")
    parser.add_argument(
        "--fda-only", action="store_true",
        help="Skip manufacturer scraping, generate from FDA data only",
    )
    parser.add_argument(
        "--merge-only", action="store_true",
        help="Skip scraping, merge and generate from existing data on disk",
    )
    parser.add_argument(
        "--download-pdfs", action="store_true",
        help="Download available PDFs (510k summaries + manufacturer IFUs)",
    )
    parser.add_argument(
        "--all-drafts", action="store_true",
        help="Generate drafts for all records including FDA-only skeletons",
    )
    parser.add_argument(
        "--index-only", action="store_true",
        help="Only regenerate the catalog index (no scraping or merging)",
    )
    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
