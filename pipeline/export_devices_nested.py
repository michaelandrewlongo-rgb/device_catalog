"""Regenerate the flat dimension CSV and the per-device nested JSON tree.

Deterministic replacement for the one-off manual "filled" CSV and the
``devices-nested`` folder: rows come straight from ``export_flat_dimensions
.build_rows()`` (validated before writing), then group strictly by
``device_id`` so a folder's slug always agrees with the identity of every row
inside it. Slug collisions between manufacturers within a category get a
``--<manufacturer>`` suffix.

    python -m pipeline.export_devices_nested \
        [--csv-out PATH] [--tree-out PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

from .export_flat_dimensions import COLUMNS, build_rows
from .knowledge_v2.validate_dimensions import summarize, validate_csv_rows

DEFAULT_CSV = Path.home() / "Downloads" / "device_dimensions_flat_filled.csv"
DEFAULT_TREE = Path.home() / "Downloads" / "devices-nested"


def device_slug(device_id: str) -> tuple[str, str, str]:
    bits = device_id.split("--")
    if len(bits) >= 3:
        return bits[0], bits[1], "--".join(bits[2:])
    if len(bits) == 2:
        return bits[0], "", bits[1]
    return "others", "", device_id


def build_tree(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """(category, folder-slug) -> device.json payload, collision-suffixed."""
    by_device: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_device[row["device_id"]].append(row)

    slug_owners: dict[tuple[str, str], list[str]] = defaultdict(list)
    for device_id in by_device:
        category, _, slug = device_slug(device_id)
        slug_owners[(category, slug)].append(device_id)

    tree: dict[tuple[str, str], dict] = {}
    for device_id, device_rows in sorted(by_device.items()):
        category, manufacturer, slug = device_slug(device_id)
        if len(slug_owners[(category, slug)]) > 1 and manufacturer:
            slug = f"{slug}--{manufacturer}"
        first = device_rows[0]
        tree[(category, slug)] = {
            "product_name": first.get("device_name", ""),
            "category": category,
            "vendor": first.get("manufacturer", ""),
            "rows": [{column: row.get(column, "") for column in COLUMNS}
                     for row in device_rows],
        }
    return tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--tree-out", type=Path, default=DEFAULT_TREE)
    args = parser.parse_args()

    rows = build_rows()
    findings = validate_csv_rows(rows)
    summary = summarize(findings)
    if summary["errors"]:
        for item in findings:
            if item["severity"] == "error":
                print(json.dumps(item))
        raise SystemExit(f"regeneration blocked: {summary['errors']} validation errors")

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    tree = build_tree(rows)
    if args.tree_out.exists():
        shutil.rmtree(args.tree_out)
    for (category, slug), payload in tree.items():
        folder = args.tree_out / category / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "device.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "rows": len(rows),
        "devices": len(tree),
        "categories": len({category for category, _ in tree}),
        "warnings": summary["warnings"],
        "csv": str(args.csv_out),
        "tree": str(args.tree_out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
