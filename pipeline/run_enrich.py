"""CLI entry point for enrichment Tier 3 and gap-fill.

Usage:
    python -m pipeline.run_enrich                          # standard enrichment
    python -m pipeline.run_enrich --gap-fill               # fill gaps in curated files
    python -m pipeline.run_enrich --gap-fill --dry-run     # preview only
    python -m pipeline.run_enrich --competitor-fill         # fill competitor comparisons
    python -m pipeline.run_enrich --competitor-fill --dry-run --limit 5
"""

from __future__ import annotations

import argparse
import logging

from rich.console import Console

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def cli():
    parser = argparse.ArgumentParser(
        description="Tier 3 enrichment and gap-fill for curated knowledge files."
    )
    parser.add_argument(
        "--gap-fill",
        action="store_true",
        help="Fill [NEEDS CONTENT] gaps in curated knowledge files",
    )
    parser.add_argument(
        "--competitor-fill",
        action="store_true",
        help="Fill competitor comparison gaps using DeepSeek synthesis",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Rewrite noisy FDA boilerplate sections using Tier 2 extractions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files (used with --gap-fill or --competitor-fill)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N files (for testing, used with --competitor-fill)",
    )
    args = parser.parse_args()

    if args.gap_fill:
        console.rule("[bold]Gap-Fill: Curated Knowledge Files")
        from .processing.gap_filler import fill_gaps

        result = fill_gaps(dry_run=args.dry_run)

        mode = "[yellow]DRY RUN[/yellow] " if args.dry_run else ""
        console.print(f"\n  {mode}[bold]Summary:[/bold]")
        console.print(f"    Files scanned:      {result['files_scanned']}")
        console.print(
            f"    Files updated:      [green]{result['files_updated']}[/green]"
        )
        console.print(
            f"    Gaps filled:        [green]{result['gaps_filled']}[/green]"
        )
        console.print(
            f"    Gaps unfilled:      [red]{result['gaps_unfilled']}[/red]"
        )
    elif args.competitor_fill:
        console.rule("[bold]Competitor Comparison Fill")
        from .processing.competitor_filler import fill_competitors

        result = fill_competitors(dry_run=args.dry_run, limit=args.limit)

        mode = "[yellow]DRY RUN[/yellow] " if args.dry_run else ""
        console.print(f"\n  {mode}[bold]Summary:[/bold]")
        console.print(f"    Files scanned:      {result['files_scanned']}")
        console.print(
            f"    Files updated:      [green]{result['files_updated']}[/green]"
        )
        console.print(
            f"    Gaps filled:        [green]{result['gaps_filled']}[/green]"
        )
        console.print(
            f"    Gaps skipped:       [red]{result['gaps_skipped']}[/red]"
        )
        console.print(f"    API calls:          {result['api_calls']}")
    elif args.rewrite:
        console.rule("[bold]Rewrite: Noisy FDA Boilerplate Sections")
        from .processing.rewriter import rewrite_noisy_files

        result = rewrite_noisy_files(dry_run=args.dry_run)

        mode = "[yellow]DRY RUN[/yellow] " if args.dry_run else ""
        console.print(f"\n  {mode}[bold]Summary:[/bold]")
        console.print(f"    Files scanned:      {result['files_scanned']}")
        console.print(
            f"    Files rewritten:    [green]{result['files_rewritten']}[/green]"
        )
        console.print(
            f"    Sections replaced:  [green]{result['sections_replaced']}[/green]"
        )
        console.print(
            f"    Skipped (no data):  [red]{result['sections_skipped_no_data']}[/red]"
        )
    else:
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
            for src, count in sorted(
                source_counts.items(), key=lambda x: -x[1]
            ):
                console.print(f"    {src}: {count}")


if __name__ == "__main__":
    cli()
