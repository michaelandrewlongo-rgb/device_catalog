"""Entry point for Phase 2: Manufacturer website scraping.

Usage:
    python -m pipeline.run_scrapers                          # All manufacturers
    python -m pipeline.run_scrapers --manufacturer penumbra  # Single manufacturer
    python -m pipeline.run_scrapers --list                   # List available scrapers
"""

import argparse
import asyncio

from rich.console import Console

from .scrapers.penumbra import PenumbraScraper
from .scrapers.stryker import StrykerScraper
from .scrapers.medtronic import MedtronicScraper
from .scrapers.cerenovus import CerenovusScraper
from .scrapers.microvention import MicroVentionScraper
from .scrapers.balt import BaltScraper
from .scrapers.integra import IntegraScraper

console = Console()

# Registry of available scrapers
SCRAPERS = {
    "penumbra": PenumbraScraper,
    "stryker": StrykerScraper,
    "medtronic": MedtronicScraper,
    "cerenovus": CerenovusScraper,
    "microvention": MicroVentionScraper,
    "balt": BaltScraper,
    "integra": IntegraScraper,
}


async def _download_product_pdfs(products) -> None:
    from .fda.pdf_downloader import download_manufacturer_pdf
    from .processing.naming import make_filename_stem

    tasks = []
    for product in products:
        stem = make_filename_stem(
            product.category_hint or "unknown",
            product.manufacturer,
            product.device_name,
        )
        if product.ifu_pdf_url:
            console.print(f"  Downloading IFU: {product.device_name}")
            tasks.append(download_manufacturer_pdf(product.ifu_pdf_url, stem, "ifu"))

        for doc_type, pdf_url in product.other_pdf_urls.items():
            console.print(f"  Downloading {doc_type}: {product.device_name}")
            tasks.append(download_manufacturer_pdf(pdf_url, stem, doc_type))

    if tasks:
        await asyncio.gather(*tasks)


async def _run_manufacturer(name: str, download_pdfs: bool) -> tuple[str, list]:
    console.print(f"\n[bold]Scraping {name}...[/]\n")
    scraper = SCRAPERS[name]()
    products = await scraper.run()
    console.print(f"\n[bold green]{name}: {len(products)} products scraped[/]")

    if download_pdfs:
        await _download_product_pdfs(products)

    return name, products


async def main(args: argparse.Namespace) -> None:
    if args.list:
        console.print("[bold]Available manufacturer scrapers:[/]")
        for name in sorted(SCRAPERS):
            console.print(f"  - {name}")
        return

    if args.manufacturer:
        names = [args.manufacturer]
    else:
        names = list(SCRAPERS.keys())

    invalid_names = [name for name in names if name not in SCRAPERS]
    for name in invalid_names:
        console.print(f"[red]Unknown manufacturer: {name}[/]")
        console.print(f"Available: {', '.join(sorted(SCRAPERS))}")
    names = [name for name in names if name in SCRAPERS]
    if not names:
        return

    semaphore = asyncio.Semaphore(max(1, args.max_concurrent))

    async def _bounded_run(manufacturer_name: str):
        async with semaphore:
            return await _run_manufacturer(manufacturer_name, args.download_pdfs)

    results = await asyncio.gather(*[_bounded_run(name) for name in names])

    console.print("\n[bold]Summary[/]")
    for name, products in results:
        console.print(f"  - {name}: {len(products)} products")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Scrape manufacturer product pages")
    parser.add_argument(
        "--manufacturer", "-m",
        help="Scrape a single manufacturer (e.g., penumbra, stryker)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available manufacturer scrapers",
    )
    parser.add_argument(
        "--download-pdfs", action="store_true",
        help="Download IFU/brochure PDFs found on product pages",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=len(SCRAPERS),
        help="Maximum number of manufacturer scrapers to run in parallel",
    )
    args = parser.parse_args()
    asyncio.run(main(args))


if __name__ == "__main__":
    cli()
