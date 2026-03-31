# CLAUDE.md

This file provides guidance to Claude Code and other coding agents when working in this repository.

## Repository Purpose

Flat-file knowledge catalog of neurosurgical and interventional neuroradiology medical devices. The catalog pairs manufacturer source PDFs with distilled markdown knowledge files and includes a Python pipeline (`pipeline/`) for discovering new devices via FDA APIs and manufacturer scraping.

This is not just a scraper repo. It is a clinical knowledge pipeline. Outputs must be accurate enough to support device identification, sizing/spec lookup, indications, access requirements, and source retrieval.

Priorities:
- source traceability over speed
- clinical precision over vanity coverage metrics
- reusable structure over one-off scraping wins
- durable workflows over session-specific heroics

## Communication

Assume the user is a domain expert, not a full-time software engineer.
Explain what you are doing in plain English.
Do not hide project state in the conversation.
Do not require the user to describe the architecture correctly before you can help.

When the user's description is vague, work from visible facts:
- exact file names
- exact command output
- exact error text
- exact product pages or PDFs
- exact JSON outputs

## Platform

This is a Windows development environment.
Prefer Windows-safe commands and paths.
Watch for quoting issues when mixing PowerShell, bash, and Chrome MCP workflows.
Set `PYTHONUTF8=1` on Windows when needed to avoid encoding issues with Rich console output.

## Core Working Rule

The repo must remain understandable after context loss.

That means:
1. Read `STATE.md` first at the start of every session.
2. If `STATE.md` is missing or stale, reconstruct it from the repo before making major changes.
3. Update `STATE.md` at the end of any meaningful work session.
4. Do not rely on chat history as the only source of project memory.

## Required Session Files

### `STATE.md`
Keep this file short and factual. It is the working memory for the project.

Use this structure:

```md
I was trying to:
The last thing I saw:
I think the problem is:
What I want next:
```

Paste commands, outputs, filenames, URLs, and errors whenever possible. Do not replace this with a long narrative.

### `ROADMAP.md`
Use for medium-term priorities only.
Keep it ordered by expected leverage.
Do not dump raw notes here.

### `PRODUCT_GOAL.md`
Use for the durable north star of the repo.
Do not put day-to-day state here.

### `MEMORY.md`
If present, treat it as durable project memory and prior decisions.
Use it to avoid repeating dead ends, but verify any operational claim against the current repo.

## Repository Purpose and Non-Goals

The goal is to build a trusted, source-grounded catalog of neurosurgical and neurointerventional devices.

The repo is not successful merely because it contains many device names. Success means the catalog is clinically useful and source-backed.

Non-goals:
- maximizing raw device count without useful content
- promoting thin FDA-only skeletons as if they were real knowledge files
- scraping pages that cannot be traced back to a durable source artifact
- inventing specifications, compatibility, or indications

## Current Catalog Snapshot

Last verified snapshot: 2026-03-30.
- 68 curated knowledge files
- about 120 scraped-only devices
- 188 total indexed devices
- 25 device categories
- 17 manufacturers

Pipeline inputs currently include openFDA 510(k)/PMA APIs plus manufacturer scraping for Stryker, MicroVention, Balt, Penumbra, Cerenovus, Medtronic, and Integra, with Chrome MCP used for harder sites when needed.

Treat these numbers as a useful state snapshot, not a guarantee that every downstream summary is current. Re-check `CATALOG_INDEX.md` before making coverage claims.

## File Naming Convention

All files follow this pattern:

```
{device-category}--{manufacturer}--{product-name}--{document-type}.{ext}
```

- Segments are separated by double dashes (`--`), words within segments by single dashes (`-`).
- **device-category** examples: `flow-diverter`, `pedicle-screw`, `csf-shunt`, `microcatheter`, `cervical-cage`, `intracranial-stent`, `embolic-coil`, `liquid-embolic`, `thrombectomy`, `navigation`, `corpectomy`, `interbody-cage`, `dural-sealant`, `intrasaccular`, `balloon-catheter`, `distal-access`, `cervical-plate`, `aspiration`, `dural-substitute`, `guidewire`, `balloon-guide-catheter`, `stent-retriever`, `guiding-catheter`
- **manufacturer** examples: `medtronic`, `stryker`, `microvention`, `depuy`, `globus`, `integra`, `miethke`, `cordis`, `ev3`, `neo-medical`, `osimplant`, `choicespine`, `penumbra`, `balt`, `cerenovus`, `rapid-medical`, `phenox`, `imperative-care-inc`
- **document-type**: `knowledge` (md), `ifu`, `510k`, `technique`, `brochure`, `catalog`, `ssed`, `sspb`, `pocket-guide`, `safety-warnings`, `patient-leaflet`, `chapter` (pdf)
- Exception: `reference--viktors-notes--{topic}--chapter.pdf` files are textbook reference chapters, not device entries.

## Knowledge File Structure

Every `--knowledge.md` file should follow a consistent section layout:

1. **H1 title** (device name)
2. **Manufacturer/Category** metadata
3. **What It Is**
4. **Sizing/Specs**
5. **Indications**
6. **Contraindications** where applicable
7. **Compatible With**
8. **Use Notes**
9. **Key Differences vs Competitors** where applicable
10. **Also Known As**

Not every file will have every section. Additional sections are appropriate when warranted by source material, for example deployment steps, antiplatelet workflow, troubleshooting, or access notes.

## Source Hierarchy

Prefer sources in this order:
1. manufacturer IFU, operator manual, official product page
2. FDA summary, PMA, 510(k), labeling
3. structured manufacturer site content
4. scraped marketing copy
5. cross-device inference only as a clearly labeled hypothesis for follow-up, never as catalog fact

If a field is missing, say it is missing.
Do not hallucinate dimensions, compatibility, indications, access requirements, deployment steps, or contraindications.

## Working With This Catalog

- The PDF is the authoritative source. The knowledge file is the working summary.
- When adding a new device, create or preserve both the source artifact and a `--knowledge.md` file.
- Comparisons across competing devices belong inside the "Key Differences vs Competitors" section of the relevant knowledge files unless there is a deliberate reason to create a separate comparison artifact.
- The catalog spans two broad clinical domains: **spine** and **neurovascular/interventional**.
- FDA presence alone does not make an entry clinically useful.

## Before Making Changes

At the start of a task, restate:
- the exact objective
- the files likely involved
- the success condition
- whether the task is discovery, scraping, consolidation, promotion, or review

If the objective is unclear, inspect the repo and infer the most likely current task from:
- `STATE.md`
- `CATALOG_INDEX.md`
- `REVIEW_MANIFEST.md`
- `pipeline/data/`
- recent docs and notes

## Pipeline

The `pipeline/` directory contains the scraping and generation pipeline.

### Setup
```bash
pip install -r pipeline/requirements.txt
scrapling install
```

### Commands
```bash
# FDA API scraping
python -m pipeline.run_fda
python -m pipeline.run_fda --codes POL NRY
python -m pipeline.run_fda --download-pdfs

# Manufacturer scraping
python -m pipeline.run_scrapers --list
python -m pipeline.run_scrapers -m penumbra

# Full pipeline
python -m pipeline.run_pipeline --fda-only
python -m pipeline.run_pipeline --merge-only
python -m pipeline.run_pipeline --merge-only --all-drafts
python -m pipeline.run_pipeline --index-only
python -m pipeline.run_pipeline --download-pdfs
```

## Architecture

- `config.py` maps product codes, manufacturer aliases, disambiguation rules, and the `EXISTING_DEVICES` set derived from the catalog root.
- `fda/` contains the openFDA client, 510(k)/PMA logic, PDF downloader, and `FDADeviceRecord` models.
- `scrapers/` contains per-manufacturer scrapers. Each scraper extends `BaseScraper` and emits `ScrapedProduct` objects.
- `scrapers/chrome_assisted.py` contains Chrome MCP save/load utilities. It is not itself a scraper class.
- `scrapers/chrome_workflow.md` contains manufacturer-specific Chrome MCP guidance.
- `processing/merger.py` joins FDA and scraped data into `MergedDeviceRecord`.
- `processing/template.py` renders scaffold markdown.
- `processing/naming.py` enforces filename rules and collision handling.
- `processing/indexer.py` generates `CATALOG_INDEX.md`.
- `processing/reviewer.py` generates `REVIEW_MANIFEST.md` with quality tiers.
- `data/` contains intermediate storage, drafts, PDFs, and raw scraper/FDA outputs.
- `scrapers/orchestrator_workflow.md` documents the bulk-promotion workflow.

## Key Design Decisions

- FDA data provides regulatory metadata. Manufacturer sources provide most clinical detail.
- Generated files go to `pipeline/data/drafts/`, never directly to the catalog root.
- Manual promotion is expected for high-trust catalog entries.
- Scaffold files can contain `[NEEDS CONTENT - ...]` placeholders when a source gap remains.
- Disambiguation rules in `config.py` are necessary because some FDA product codes span multiple real-world categories.
- `EXISTING_DEVICES` is derived from the catalog root to avoid overwriting hand-curated files.

## Chrome-Assisted Scraping

For manufacturers where automated scraping fails because of bot detection, JS-heavy interfaces, or gated content, use Claude Code plus Chrome DevTools MCP.

Workflow:
1. Read `pipeline/scrapers/chrome_workflow.md` for the target manufacturer.
2. Use Chrome MCP tools to inspect the live site and gather durable product data.
3. Save results via `save_chrome_product()` from `pipeline/scrapers/chrome_assisted.py`.
4. Run `python -m pipeline.run_pipeline --merge-only` to regenerate drafts.

If Chrome MCP reveals API endpoints or reusable patterns, record them in a durable repo file instead of leaving them in chat only.

## Scraper Discipline

When working in `pipeline/scrapers/`:
- prefer fixing extraction logic over adding brittle one-off fallbacks
- document fallback URLs explicitly
- preserve raw outputs when possible
- save Chrome-derived outputs in the same shape expected by merger logic
- keep manufacturer-specific hacks contained and documented

If a site is JS-heavy, tabbed, accordion-based, or bot-protected, Chrome MCP is preferred over pretending a simple requests-based scraper is enough.

## Promotion Discipline

Do not promote a scraped product into the curated catalog unless it is materially useful.

Minimum bar for promotion:
- correct manufacturer
- correct category
- source traceability
- a real device description or device role
- at least one meaningful technical, workflow, or compatibility detail
- no fabricated specifications

Good promotion work should upgrade usefulness, not just inventory count.

## Long-Running or Multi-Step Work

If a task spans multiple sessions, leave breadcrumbs.
At minimum update `STATE.md`.
If needed, also add a short note in a durable repo file explaining:
- what was attempted
- what succeeded
- what failed
- what remains

Do not rely on chat history to preserve this.

## Source-of-Truth Files

Read these before making assumptions:
- `STATE.md`
- `PRODUCT_GOAL.md`
- `ROADMAP.md`
- `CATALOG_INDEX.md`
- `REVIEW_MANIFEST.md`
- `pipeline/config.py`
- `pipeline/scrapers/chrome_workflow.md`
- `pipeline/scrapers/orchestrator_workflow.md`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`

## What Good Looks Like

A good change in this repo does one or more of the following:
- improves source acquisition for an important manufacturer or category
- upgrades many devices from scraped-only to review-ready or curated
- reduces brittle scraping behavior
- improves source traceability
- makes review and promotion easier
- makes the next session easier to resume

## What Not To Do

- Do not optimize for raw device count at the expense of accuracy.
- Do not create large new abstractions without a clear bottleneck.
- Do not scatter project state across random notes.
- Do not silently fill missing specs with guesses.
- Do not confuse FDA coverage with clinically useful catalog coverage.
- Do not claim a device is "done" merely because a draft file exists.

## End-of-Session Requirement

Before ending a substantial session:
1. update `STATE.md`
2. note changed priorities in `ROADMAP.md` if needed
3. mention any new durable artifacts created
4. state the single best next action in plain English
