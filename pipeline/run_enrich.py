"""CLI entry point for enrichment Tier 3.

Usage:
    python -m pipeline.run_enrich
"""

from __future__ import annotations

import logging

from rich.console import Console

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def cli():
    console.rule("[bold]Tier 3: Enrichment Synthesis")
    from .extraction.enricher import enrich_all
    results = enrich_all()
    console.print(f"  [green]{len(results)}[/green] devices enriched")

    source_counts: dict[str, int] = {}
    for r in results:
        for field, meta in r.get("_enrichment", {}).items():
            if field.startswith("_"):
                continue
            src = meta.get("source", "none")
            source_counts[src] = source_counts.get(src, 0) + 1

    if source_counts:
        console.print("\n  [bold]Sources:[/bold]")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            console.print(f"    {src}: {count}")


if __name__ == "__main__":
    cli()
