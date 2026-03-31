"""Scrape 510(k) clearances from openFDA and normalize to FDADeviceRecords."""

import json
from pathlib import Path
from slugify import slugify
import sys
import io

# Force UTF-8 output on Windows to avoid encoding errors with Rich tables
if sys.platform == "win32" and not isinstance(sys.stdout, io.TextIOWrapper):
    pass  # Already wrapped
elif sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table

from .client import FDAClient
from .models import FDA510kRecord, FDADeviceRecord
from ..config import (
    PRODUCT_CODE_MAP,
    PMA_PRODUCT_CODES,
    DATA_DIR,
    EXISTING_DEVICES,
    disambiguate_category,
    normalize_manufacturer,
    is_neuro_applicant,
)

console = Console()


def _make_filename_stem(category: str, manufacturer: str, device_name: str) -> str:
    """Generate a catalog filename stem from device metadata.

    Produces: {category}--{manufacturer}--{product-slug}
    """
    # Extract a short product name from the FDA device name
    # Remove manufacturer name and generic descriptors
    name = device_name
    # Strip common suffixes/prefixes
    for strip_word in [
        "system", "device", "catheter system", "embolization system",
        "revascularization device", "retriever", "neurovascular",
    ]:
        name = name.lower().replace(strip_word, "")

    product_slug = slugify(name.strip(), separator="-", lowercase=True)

    # Trim overly long slugs (keep first 4 segments)
    parts = product_slug.split("-")
    if len(parts) > 5:
        product_slug = "-".join(parts[:5])

    return f"{category}--{manufacturer}--{product_slug}"


def _check_already_in_catalog(stem: str) -> bool:
    """Check if a device with a similar filename stem already exists."""
    if stem in EXISTING_DEVICES:
        return True
    # Fuzzy: check if the category--manufacturer prefix plus first product word match
    parts = stem.split("--")
    if len(parts) >= 3:
        prefix = f"{parts[0]}--{parts[1]}"
        product_start = parts[2].split("-")[0] if parts[2] else ""
        for existing in EXISTING_DEVICES:
            if existing.startswith(prefix) and product_start and product_start in existing:
                return True
    return False


def normalize_510k(record: FDA510kRecord) -> FDADeviceRecord:
    """Convert a raw 510(k) record to a normalized FDADeviceRecord."""
    manufacturer = normalize_manufacturer(record.applicant)
    category = disambiguate_category(record.product_code, record.device_name)
    stem = _make_filename_stem(category, manufacturer, record.device_name)

    # Construct potential PDF summary URL
    # Pattern: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
    pdf_url = ""
    if record.k_number:
        k_num = record.k_number.upper()
        # Extract year digits: K201234 -> 20, K991234 -> 99
        if len(k_num) >= 4 and k_num[0] == "K":
            year_part = k_num[1:3]
            pdf_url = f"https://www.accessdata.fda.gov/cdrh_docs/pdf{year_part}/{k_num}.pdf"

    return FDADeviceRecord(
        clearance_type="510k",
        clearance_number=record.k_number,
        clearance_date=record.decision_date,
        device_class=2,
        manufacturer_canonical=manufacturer,
        manufacturer_raw=record.applicant,
        catalog_category=category,
        device_name_fda=record.device_name,
        product_code=record.product_code,
        product_code_description=record.advisory_committee_description,
        already_in_catalog=_check_already_in_catalog(stem),
        suggested_filename_stem=stem,
        pdf_summary_url=pdf_url,
    )


async def scrape_510k_all(
    product_codes: list[str] | None = None,
) -> list[FDADeviceRecord]:
    """Scrape all 510(k) records for the configured product codes.

    Args:
        product_codes: Optional subset of codes to query. Defaults to all
                       non-PMA codes in PRODUCT_CODE_MAP.

    Returns:
        List of normalized FDADeviceRecords.
    """
    if product_codes is None:
        product_codes = [
            code for code in PRODUCT_CODE_MAP
            if code not in PMA_PRODUCT_CODES
        ]

    all_devices: list[FDADeviceRecord] = []
    output_dir = DATA_DIR / "fda_raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    async with FDAClient() as client:
        for code in product_codes:
            category = PRODUCT_CODE_MAP[code]
            console.print(f"[bold blue]Querying 510(k) for product code {code} ({category})...[/]")

            total = await client.get_total_count("510k", code)
            console.print(f"  Found {total} total records")

            records = await client.search_510k_all(code)
            console.print(f"  Retrieved {len(records)} records")

            # Filter guidewires to neuro applicants only
            if code == "MOF":
                before = len(records)
                records = [r for r in records if is_neuro_applicant(r.applicant)]
                console.print(f"  Filtered MOF to neuro applicants: {before} -> {len(records)}")

            # Normalize
            normalized = [normalize_510k(r) for r in records]

            # Save raw JSON per product code
            code_dir = output_dir / code
            code_dir.mkdir(exist_ok=True)
            for device in normalized:
                fname = f"{device.clearance_number}.json"
                (code_dir / fname).write_text(
                    device.model_dump_json(indent=2), encoding="utf-8"
                )

            new_count = sum(1 for d in normalized if not d.already_in_catalog)
            console.print(f"  [green]{new_count} new devices[/] / {len(normalized) - new_count} already in catalog")

            all_devices.extend(normalized)

    return all_devices


def print_discovery_report(devices: list[FDADeviceRecord]) -> None:
    """Print a summary table of discovered devices."""
    table = Table(title="FDA 510(k) Discovery Report")
    table.add_column("Category", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Device Name", style="white")
    table.add_column("K-Number", style="dim")
    table.add_column("Date", style="dim")
    table.add_column("Status", style="bold")

    # Sort: new devices first, then by category
    sorted_devices = sorted(
        devices,
        key=lambda d: (d.already_in_catalog, d.catalog_category, d.manufacturer_canonical),
    )

    for d in sorted_devices:
        status = "[dim]exists[/]" if d.already_in_catalog else "[bold green]NEW[/]"
        table.add_row(
            d.catalog_category,
            d.manufacturer_canonical,
            d.device_name_fda[:50],
            d.clearance_number,
            d.clearance_date[:10] if d.clearance_date else "",
            status,
        )

    console.print(table)

    # Summary counts
    by_category: dict[str, dict[str, int]] = {}
    for d in devices:
        cat = d.catalog_category
        if cat not in by_category:
            by_category[cat] = {"new": 0, "existing": 0}
        if d.already_in_catalog:
            by_category[cat]["existing"] += 1
        else:
            by_category[cat]["new"] += 1

    summary = Table(title="Summary by Category")
    summary.add_column("Category")
    summary.add_column("New", style="green")
    summary.add_column("Existing", style="dim")
    summary.add_column("Total")
    for cat in sorted(by_category):
        counts = by_category[cat]
        summary.add_row(
            cat,
            str(counts["new"]),
            str(counts["existing"]),
            str(counts["new"] + counts["existing"]),
        )
    console.print(summary)
