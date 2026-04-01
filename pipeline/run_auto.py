"""Autonomous pipeline: wait for Tier 2 extraction, then run post-processing.

Monitors pipeline/data/extracted/documents/ for new NSPR Tier 2 outputs.
Once extraction appears complete (no new files for 60 seconds), runs the
full post-extraction pipeline.

Usage:
    python -m pipeline.run_auto
    python -m pipeline.run_auto --no-wait   # Skip monitoring, run immediately
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console

console = Console()

DOCS_DIR = Path("pipeline/data/extracted/documents")
NSPR_PDFS_DIR = Path("pipeline/data/extracted/nspr/pdfs")


def _count_nspr_docs() -> int:
    """Count NSPR Tier 2 output files."""
    if not DOCS_DIR.exists():
        return 0
    return len(list(DOCS_DIR.glob("nspr--*.json")))


def _count_nspr_pdfs() -> int:
    """Count NSPR source PDFs (the target)."""
    if not NSPR_PDFS_DIR.exists():
        return 0
    return len(list(NSPR_PDFS_DIR.glob("*.pdf")))


def monitor_extraction(timeout_minutes: int = 120, stable_seconds: int = 60):
    """Wait for Tier 2 extraction to stabilize.

    Polls every 15 seconds. Considers extraction complete when no new
    files appear for stable_seconds.
    """
    target = _count_nspr_pdfs()
    console.print(f"[bold]Monitoring Tier 2 extraction[/bold]")
    console.print(f"  NSPR PDFs to extract: {target}")
    console.print(f"  Timeout: {timeout_minutes} min, stable threshold: {stable_seconds}s")
    console.print()

    last_count = _count_nspr_docs()
    last_change = time.time()
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > timeout_minutes * 60:
            console.print(f"\n[yellow]Timeout after {timeout_minutes} min[/yellow]")
            break

        current = _count_nspr_docs()
        if current != last_count:
            last_count = current
            last_change = time.time()
            console.print(
                f"  [{time.strftime('%H:%M:%S')}] "
                f"NSPR docs: {current}/{target} "
                f"({current * 100 // max(target, 1)}%)"
            )

        since_change = time.time() - last_change
        if since_change >= stable_seconds and current > 0:
            console.print(
                f"\n[green]Extraction stable for {stable_seconds}s "
                f"at {current}/{target} docs[/green]"
            )
            break

        time.sleep(15)

    return _count_nspr_docs()


def run_post_extract():
    """Run the post-extraction pipeline as a subprocess."""
    console.rule("[bold]Running Post-Extraction Pipeline")
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.run_post_extract"],
        env={**__import__("os").environ, "PYTHONUTF8": "1"},
    )
    return result.returncode


def cli():
    parser = argparse.ArgumentParser(description="Autonomous extraction + post-processing")
    parser.add_argument("--no-wait", action="store_true", help="Skip monitoring, run post-extract immediately")
    parser.add_argument("--timeout", type=int, default=120, help="Monitoring timeout in minutes")
    args = parser.parse_args()

    if not args.no_wait:
        count = monitor_extraction(timeout_minutes=args.timeout)
        console.print(f"\n  Final NSPR Tier 2 count: {count}")
    else:
        console.print("[dim]Skipping extraction monitoring[/dim]")

    rc = run_post_extract()
    if rc != 0:
        console.print(f"[red]Post-extraction pipeline exited with code {rc}[/red]")
        sys.exit(rc)

    console.print("\n[bold green]Autonomous pipeline complete.[/bold green]")


if __name__ == "__main__":
    cli()
