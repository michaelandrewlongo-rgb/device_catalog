"""Scrape PMA approvals from openFDA for Class III neurovascular devices."""

import json
from rich.console import Console
from rich.table import Table
from slugify import slugify

from .client import FDAClient
from .models import FDAPMARecord, FDADeviceRecord
from ..config import (
    PMA_NUMBERS,
    DATA_DIR,
    EXISTING_DEVICES,
    normalize_manufacturer,
)

console = Console()


def _make_pma_filename_stem(category: str, manufacturer: str, family_name: str) -> str:
    """Generate filename stem for a PMA device."""
    product_slug = slugify(family_name, separator="-", lowercase=True)
    return f"{category}--{manufacturer}--{product_slug}"


def _check_already_in_catalog(stem: str) -> bool:
    """Check if a device with a similar filename stem already exists."""
    if stem in EXISTING_DEVICES:
        return True
    parts = stem.split("--")
    if len(parts) >= 3:
        prefix = f"{parts[0]}--{parts[1]}"
        product_start = parts[2].split("-")[0] if parts[2] else ""
        for existing in EXISTING_DEVICES:
            if existing.startswith(prefix) and product_start and product_start in existing:
                return True
    return False


def normalize_pma(
    records: list[FDAPMARecord],
    category: str,
    manufacturer_canonical: str,
    family_name: str,
) -> list[FDADeviceRecord]:
    """Convert PMA records (base + supplements) into FDADeviceRecords.

    Groups supplements under the same device family. Returns one record per
    unique trade name (some PMA supplements introduce new device variants).
    """
    # Deduplicate by trade_name to capture distinct device variants
    seen_names: dict[str, FDAPMARecord] = {}
    for r in records:
        name = r.trade_name.strip()
        if not name:
            name = family_name
        # Keep the most recent record for each trade name
        if name not in seen_names or r.decision_date > seen_names[name].decision_date:
            seen_names[name] = r

    devices = []
    for trade_name, record in seen_names.items():
        stem = _make_pma_filename_stem(category, manufacturer_canonical, trade_name)

        devices.append(FDADeviceRecord(
            clearance_type="pma",
            clearance_number=record.pma_number,
            clearance_date=record.decision_date,
            device_class=3,
            manufacturer_canonical=manufacturer_canonical,
            manufacturer_raw=record.applicant,
            catalog_category=category,
            device_name_fda=trade_name,
            product_code=record.product_code,
            product_code_description=record.generic_name,
            already_in_catalog=_check_already_in_catalog(stem),
            suggested_filename_stem=stem,
        ))

    return devices


async def scrape_pma_all() -> list[FDADeviceRecord]:
    """Scrape all configured PMA numbers and return normalized records."""
    all_devices: list[FDADeviceRecord] = []
    output_dir = DATA_DIR / "fda_raw" / "pma"
    output_dir.mkdir(parents=True, exist_ok=True)

    async with FDAClient() as client:
        for pma_number, category, manufacturer, family_name in PMA_NUMBERS:
            console.print(
                f"[bold blue]Querying PMA {pma_number} "
                f"({family_name}, {manufacturer})...[/]"
            )

            records = await client.search_pma_all(pma_number)
            console.print(f"  Retrieved {len(records)} records (base + supplements)")

            # Filter to approved decisions only
            approved = [r for r in records if r.decision_code in ("APPR", "APPRVD", "")]
            if len(approved) < len(records):
                console.print(f"  Filtered to {len(approved)} approved records")

            normalized = normalize_pma(approved, category, manufacturer, family_name)

            # Save raw JSON
            for device in normalized:
                fname = f"{device.clearance_number}--{slugify(device.device_name_fda)}.json"
                (output_dir / fname).write_text(
                    device.model_dump_json(indent=2), encoding="utf-8"
                )

            new_count = sum(1 for d in normalized if not d.already_in_catalog)
            console.print(
                f"  [green]{new_count} new device variants[/] / "
                f"{len(normalized) - new_count} already in catalog"
            )

            all_devices.extend(normalized)

    return all_devices


def print_pma_report(devices: list[FDADeviceRecord]) -> None:
    """Print a summary of PMA device discoveries."""
    table = Table(title="FDA PMA Discovery Report")
    table.add_column("Category", style="cyan")
    table.add_column("Manufacturer", style="green")
    table.add_column("Device / Trade Name", style="white")
    table.add_column("PMA Number", style="dim")
    table.add_column("Date", style="dim")
    table.add_column("Status", style="bold")

    for d in sorted(devices, key=lambda x: (x.already_in_catalog, x.catalog_category)):
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
