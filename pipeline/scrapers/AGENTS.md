# Repository Guidelines

## Project Structure & Module Organization
`pipeline/` contains the end-to-end data pipeline. This `pipeline/scrapers/` package holds manufacturer-specific scrapers such as `penumbra.py`, `stryker.py`, and `medtronic.py`, plus shared logic in `base.py`. Use `run_scrapers.py` from `pipeline/` to execute one or all scrapers. `chrome_assisted.py` provides I/O utilities for Chrome MCP scraping sessions. Generated outputs go to `pipeline/data/scraper_raw/{manufacturer}/`.

## Build, Test, and Development Commands
From the repository root (`device_catalog/`), install dependencies with:
```powershell
python -m pip install -r pipeline/requirements.txt
```
List available scrapers:
```powershell
python -m pipeline.run_scrapers --list
```
Run a single manufacturer scraper:
```powershell
python -m pipeline.run_scrapers --manufacturer stryker
```
Run all scrapers and download linked PDFs:
```powershell
python -m pipeline.run_scrapers --download-pdfs
```
For Chrome-assisted scraping, see `chrome_workflow.md` for per-manufacturer navigation guides.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints, `snake_case` for functions and modules, and `PascalCase` for models/scraper classes like `StrykerScraper`. Keep scraper modules focused on one manufacturer each. Prefer small async methods, clear docstrings, and `pathlib.Path` over string paths. Match the existing JSON-writing pattern in `base.py` when adding new outputs.

## Testing Guidelines
There is no dedicated `tests/` suite in this checkout yet, so validate changes with targeted scraper runs. For new logic, add lightweight tests under a future `tests/` package using `pytest`, naming files `test_<module>.py`. Before opening a PR, run the relevant scraper and confirm expected JSON or failure logs are produced under the configured data/output directories.

## Commit & Pull Request Guidelines
Git history is not available in this snapshot, so use short imperative commit subjects such as `Add retry handling for Balt detail pages`. Keep commits scoped to one scraper or one shared behavior change. PRs should include: the scraper(s) affected, sample run commands, notable output changes, and any site-specific risks such as rate limits or brittle selectors. Include screenshots only when a browser-rendered flow or HTML structure change is central to the fix.

## Security & Configuration Tips
Respect `request_delay` and avoid removing throttling. Do not commit scraped PDFs, credentials, or large debug dumps unless they are intentionally curated fixtures. Keep manufacturer-specific endpoints, selectors, and parsing assumptions easy to audit in the relevant scraper module.
