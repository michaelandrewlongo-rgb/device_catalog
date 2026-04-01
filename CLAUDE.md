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

Last verified snapshot: 2026-03-31.
- 144 curated knowledge files (21 categories, 21 manufacturers)
- 109 scraped-only devices
- 253 total indexed devices
- 21 curated categories, strongest: embolic-coil (20), microcatheter (16), distal-access (14), pedicle-screw (14)
- Two clinical domains: spine (pedicle screws, cages, plates, corpectomy, SI fusion, navigation, disc replacement) and neurovascular/interventional (flow diverters, stent retrievers, aspiration, coils, liquid embolics, microcatheters, intracranial stents, shunts, thrombectomy, guidewires)
- Section fill: What It Is 94%, Indications 97%, Use Notes 76%, Sizing 62%, Compatible With 51%, Contraindications 35%
- 24 files still have [NEEDS CONTENT] gaps (29 total instances)

Pipeline inputs include openFDA 510(k)/PMA APIs (281 summaries, 245 UDI, 592 recalls), manufacturer scraping (9 scrapers, 163 products), Chrome MCP for gated sites, EVToday device guide (301 neuro devices), NeuroSpine Product Review (103 detail pages), and Marker+DeepSeek document extraction (53 PDFs).

Treat these numbers as a state snapshot. Re-check `CATALOG_INDEX.md` before making coverage claims.

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

# Full pipeline (merge + draft generation)
python -m pipeline.run_pipeline --merge-only
python -m pipeline.run_pipeline --merge-only --all-drafts
python -m pipeline.run_pipeline --index-only

# Extraction pipeline (Tiers 1-2)
python -m pipeline.run_extract --fda-summaries     # Tier 1A: parse 510(k) PDFs
python -m pipeline.run_extract --fda-structured     # Tier 1B: UDI/MAUDE/Recall APIs
python -m pipeline.run_extract --evtoday            # Tier 1C: EVToday device guide
python -m pipeline.run_extract --nspr-download      # Tier 1D: download NSPR PDFs
python -m pipeline.run_extract --documents          # Tier 2: Marker + DeepSeek on catalog PDFs
python -m pipeline.run_extract --fda-documents      # Tier 2: Marker + DeepSeek on curated FDA PDFs
python -m pipeline.run_extract --all                # All of the above

# Enrichment (Tier 3)
python -m pipeline.run_enrich                       # Multi-source synthesis

# Post-processing
python -m pipeline.run_enrich --gap-fill             # Fill [NEEDS CONTENT] from extracted data
python -m pipeline.run_enrich --gap-fill --dry-run   # Preview gap fills
python -m pipeline.run_enrich --competitor-fill       # DeepSeek competitor comparisons
python -m pipeline.run_enrich --rewrite              # Clean noisy FDA boilerplate
python -m pipeline.run_enrich --rewrite --dry-run    # Preview rewrites
```

## Architecture

- `config.py` maps product codes, manufacturer aliases, disambiguation rules, `EXISTING_DEVICES`, and loads `DEEPSEEK_API_KEY`.
- `fda/` contains the openFDA client, 510(k)/PMA logic, PDF downloader, and `FDADeviceRecord` models.
- `scrapers/` contains per-manufacturer scrapers. Each scraper extends `BaseScraper` and emits `ScrapedProduct` objects.
- `scrapers/chrome_assisted.py` contains Chrome MCP save/load utilities for manufacturer scraping.
- `scrapers/chrome_workflow.md` contains manufacturer-specific Chrome MCP guidance.
- `extraction/` contains the three-tier extraction/enrichment pipeline:
  - `evtoday_scraper.py` -- Tier 1C: EVToday device guide structured table scraper
  - `nspr_scraper.py` -- Tier 1D: NSPR Chrome MCP helpers and PDF downloader
  - `fda_parser.py` -- Tier 1A: FDA 510(k) PDF parsing with pdfplumber/Marker
  - `fda_structured.py` -- Tier 1B: FDA UDI/MAUDE/Recall API queries
  - `doc_extractor.py` -- Tier 2: Marker + DeepSeek structured extraction from brochures/IFUs
  - `enricher.py` -- Tier 3: multi-source synthesis with manufacturer-verified matching
  - `deepseek.py` -- DeepSeek API client (OpenAI-compatible, shared by Tiers 2-3)
  - `pdf_utils.py` -- PDF validation and text extraction (pdfplumber + Marker fallback)
- `processing/merger.py` joins FDA and scraped data into `MergedDeviceRecord`.
- `processing/template.py` renders scaffold markdown. Overlays enriched data when available.
- `processing/naming.py` enforces filename rules and collision handling.
- `processing/indexer.py` generates `CATALOG_INDEX.md`.
- `processing/reviewer.py` generates `REVIEW_MANIFEST.md` with quality tiers.
- `processing/gap_filler.py` fills [NEEDS CONTENT] placeholders in curated files from extracted data.
- `processing/competitor_filler.py` generates competitor comparisons via DeepSeek using catalog-grounded data.
- `processing/rewriter.py` detects and replaces FDA boilerplate in curated files with clean Tier 2 extractions.
- `data/` contains intermediate storage:
  - `fda_raw/`, `scraper_raw/` -- raw input data
  - `merged/` -- FDA + scraper merged records
  - `extracted/` -- Tier 1-2 extraction outputs (evtoday/, nspr/, fda_summaries/, fda_structured/, fda_safety/, documents/)
  - `enriched/` -- Tier 3 enriched records with `_enrichment` metadata
  - `drafts/` -- rendered knowledge file scaffolds
  - `pdfs/` -- downloaded FDA 510(k) summary PDFs

## Key Design Decisions

- FDA data provides regulatory metadata. Manufacturer sources provide most clinical detail.
- Generated files go to `pipeline/data/drafts/`, never directly to the catalog root.
- Manual promotion is expected for high-trust catalog entries. Batch promotion is acceptable when quality scoring confirms readiness.
- Scaffold files can contain `[NEEDS CONTENT - ...]` placeholders when a source gap remains.
- Disambiguation rules in `config.py` are necessary because some FDA product codes span multiple real-world categories.
- `EXISTING_DEVICES` is derived from the catalog root to avoid overwriting hand-curated files.
- Extraction pipeline uses staged checkpoints: each tier writes to its own directory. Inspect between tiers.
- EVToday and NSPR cross-matching requires manufacturer name verification (not just product name word overlap) to prevent false positives.
- DeepSeek API (not Claude API) is used for LLM extraction to minimize cost. Key loaded from `~/Desktop/master_env.txt`.
- Marker PDF-to-markdown is preferred for complex tables. pdfplumber is the fallback for simple text-based PDFs.
- Enriched records never overwrite curated knowledge files. The enricher skips any device with an existing `--knowledge.md` in catalog root.

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
- `STATE.md` -- current working state and next steps
- `PRODUCT_GOAL.md` -- durable north star
- `ROADMAP.md` -- medium-term priorities with status
- `CATALOG_INDEX.md` -- current coverage numbers (regenerate with `--index-only`)
- `pipeline/config.py` -- product codes, manufacturer aliases, paths, API keys
- `pipeline/scrapers/chrome_workflow.md` -- manufacturer-specific Chrome MCP guidance
- `pipeline/scrapers/orchestrator_workflow.md` -- bulk promotion workflow
- `docs/superpowers/specs/2026-03-30-pdf-extraction-pipeline-design.md` -- extraction pipeline design spec
- `docs/superpowers/plans/2026-03-30-pdf-extraction-pipeline.md` -- extraction pipeline implementation plan

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
