"""Download 510(k) summary PDFs from FDA.gov and IFU PDFs from manufacturer sites."""

import asyncio
from pathlib import Path
import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .models import FDADeviceRecord
from ..config import DATA_DIR

console = Console()

PDF_DIR = DATA_DIR / "pdfs"
REQUEST_DELAY = 1.0  # Be polite to FDA servers
MAX_RETRIES = 2


async def download_pdf(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
) -> bool:
    """Download a single PDF. Returns True on success."""
    if dest.exists():
        return True  # Already downloaded

    for attempt in range(MAX_RETRIES):
        try:
            await asyncio.sleep(REQUEST_DELAY)
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "pdf" in content_type or "octet-stream" in content_type:
                    dest.write_bytes(resp.content)
                    return True
                # Some FDA URLs return HTML error pages with 200 status
                return False
            if resp.status_code == 404:
                return False
            if resp.status_code in (429, 500, 502, 503):
                await asyncio.sleep(2 ** attempt)
                continue
        except httpx.HTTPError:
            if attempt == MAX_RETRIES - 1:
                return False
            await asyncio.sleep(2 ** attempt)

    return False


async def download_fda_pdfs(
    devices: list[FDADeviceRecord],
    max_downloads: int | None = None,
) -> dict[str, bool]:
    """Download 510(k) summary PDFs for a list of devices.

    Args:
        devices: Devices with pdf_summary_url populated.
        max_downloads: Cap on number of PDFs to download (for testing).

    Returns:
        Dict mapping clearance_number to success/failure.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # Filter to devices with PDF URLs
    downloadable = [d for d in devices if d.pdf_summary_url]
    if max_downloads:
        downloadable = downloadable[:max_downloads]

    if not downloadable:
        console.print("[yellow]No PDF URLs to download.[/]")
        return {}

    console.print(f"[bold blue]Downloading {len(downloadable)} 510(k) summary PDFs...[/]")

    results: dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Downloading PDFs", total=len(downloadable))

            for device in downloadable:
                dest_name = f"{device.suggested_filename_stem}--510k.pdf"
                dest_path = PDF_DIR / dest_name

                success = await download_pdf(client, device.pdf_summary_url, dest_path)
                results[device.clearance_number] = success

                status = "ok" if success else "not found"
                progress.update(task, advance=1, description=f"{device.clearance_number} [{status}]")

    success_count = sum(1 for v in results.values() if v)
    console.print(
        f"[green]Downloaded {success_count}/{len(results)} PDFs[/] "
        f"to {PDF_DIR}"
    )

    # Log failures
    failures = [k for k, v in results.items() if not v]
    if failures:
        log_path = PDF_DIR / "download_failures.txt"
        log_path.write_text("\n".join(failures), encoding="utf-8")
        console.print(f"[yellow]{len(failures)} failures logged to {log_path}[/]")

    return results


async def download_manufacturer_pdf(
    url: str,
    filename_stem: str,
    doc_type: str = "ifu",
) -> bool:
    """Download a single manufacturer PDF (IFU, technique guide, etc.).

    Args:
        url: Direct URL to the PDF.
        filename_stem: Catalog filename stem (e.g., "thrombectomy--penumbra--jet-7").
        doc_type: Document type suffix (e.g., "ifu", "brochure", "technique").

    Returns:
        True on success.
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / f"{filename_stem}--{doc_type}.pdf"

    if dest.exists():
        return True

    async with httpx.AsyncClient(timeout=60.0) as client:
        return await download_pdf(client, url, dest)
