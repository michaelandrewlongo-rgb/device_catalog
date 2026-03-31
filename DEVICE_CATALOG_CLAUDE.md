# CLAUDE.md

This file provides guidance to Claude Code and other coding agents when working in this repository.

## Repository Purpose

Build a trusted, source-grounded catalog of neurosurgical and neurointerventional devices.

This repo is not just a scraper project. It is a clinical knowledge pipeline whose outputs must be accurate enough to use as a reference for device identification, sizing, indications, access requirements, and source lookup.

The catalog should prioritize:
- source traceability over speed
- clinical precision over coverage vanity metrics
- reusable structure over one-off scraping wins
- durable workflows over session-specific heroics

## Communication

Assume the user is a domain expert, not a full-time software engineer.
Explain what you are doing in plain English.
Do not hide state in the conversation.
Do not force the user to describe architecture correctly before you can help.

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

## Core Working Rule

The repo must remain understandable after context loss.

That means:
1. Read `STATE.md` first at the start of every session.
2. If `STATE.md` is missing or stale, reconstruct it from the repo before making major changes.
3. Update `STATE.md` at the end of any meaningful work session.

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

Do not replace it with a long narrative.

### `ROADMAP.md`
Use for medium-term priorities only.
Do not dump raw notes here.
Keep it ordered by expected leverage.

### `PRODUCT_GOAL.md`
Use for the durable north star of the repo.
Do not put day-to-day state here.

## Before Making Changes

At the start of a task, restate:
- the exact objective
- the files likely involved
- the success condition
- whether the task is discovery, scraping, consolidation, or promotion

If the objective is unclear, inspect the repo and infer the most likely current task from `STATE.md`, `CATALOG_INDEX.md`, `REVIEW_MANIFEST.md`, `pipeline/data/`, and recent docs.

## Current Project Shape

This project appears to have four main layers:

1. FDA and regulatory ingestion
   - openFDA 510(k) and PMA discovery
   - PDF download and normalized metadata capture

2. Manufacturer scraping
   - Python scrapers for supported manufacturers
   - Chrome MCP workflows for bot-protected or JS-heavy sites

3. Consolidation and promotion
   - merge FDA data and scraped manufacturer data
   - generate or promote `--knowledge.md` files

4. Catalog indexing and review
   - `CATALOG_INDEX.md`
   - `REVIEW_MANIFEST.md`
   - quality and coverage tracking

Treat these as separate stages. Do not blur them.

## Data Quality Rules

Never present scraped data as trusted clinical fact unless it is tied to a source artifact.
Prefer this hierarchy:

1. manufacturer IFU / operator manual / official product page
2. FDA summary / labeling / PMA or 510(k) record
3. structured manufacturer site content
4. scraped marketing copy
5. inferred text from sibling devices

If a field is missing, say it is missing.
Do not hallucinate specifications, catheter compatibility, dimensions, or indications.

## Scraper Discipline

When working in `pipeline/scrapers/`:
- prefer fixing extraction logic over adding brittle hardcoded fallbacks
- document any fallback URLs explicitly
- preserve raw outputs when possible
- save Chrome-derived outputs in the same shape expected by downstream merger logic
- log discovered API endpoints or network calls in a durable file

If a site is JS-heavy, tabbed, accordion-based, or bot-protected, Chrome MCP is preferred over pretending requests-based scraping is sufficient.

## Promotion Discipline

Do not promote a scraped product to a knowledge file unless the output is materially useful.
A promoted file should have enough substance to answer real device questions, not just exist for coverage.

Minimum bar for promotion:
- correct manufacturer
- correct category
- source traceability
- at least basic description or device role
- at least one meaningful technical or workflow detail
- no fabricated specifications

## Source of Truth Files

Read these before assuming project state:
- `CATALOG_INDEX.md`
- `pipeline/data/drafts/REVIEW_MANIFEST.md`
- `pipeline/config.py`
- `pipeline/scrapers/chrome_workflow.md`
- `pipeline/scrapers/orchestrator_workflow.md`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`

## Long-Running or Multi-Step Work

If a task spans multiple sessions, leave breadcrumbs.
At minimum update `STATE.md`.
If needed, also add a small status note in `docs/superpowers/plans/` or `pipeline/data/` explaining:
- what was attempted
- what succeeded
- what failed
- what remains

Do not rely on the chat history to preserve this.

## What Good Looks Like

A good change in this repo does one or more of the following:
- improves source acquisition for an important manufacturer or category
- upgrades many devices from scraped-only to curated or review-ready
- reduces brittle scraping behavior
- improves source traceability
- makes review and promotion easier
- makes the next session easier to resume

## What Not To Do

- Do not optimize for raw device count at the expense of accuracy
- Do not create big new abstractions without a clear bottleneck
- Do not scatter project state across random notes
- Do not silently fill missing specs with guesses
- Do not confuse FDA coverage with clinically useful catalog coverage

## End-of-Session Requirement

Before ending a substantial session:
1. update `STATE.md`
2. note any changed priorities in `ROADMAP.md` if needed
3. mention any new durable artifacts created
4. state the single best next action in plain English
