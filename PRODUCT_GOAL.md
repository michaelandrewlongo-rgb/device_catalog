# PRODUCT_GOAL.md

## North Star

Build the most trusted, source-grounded device reference layer for neurosurgical and neurointerventional practice.

This repository should become the evidence and source backbone for answering practical device questions such as:
- what is this device
- who makes it
- what category it belongs to
- how it is delivered or used
- what sizes or compatibility details matter
- where the source documents and official references live

## What This Repo Is

This repo is a device knowledge and source-acquisition engine.

It should:
- discover devices from regulatory and manufacturer sources
- consolidate structured device records
- preserve source traceability
- generate clinically useful knowledge files
- expose catalog coverage and review status clearly

## What This Repo Is Not

This repo is not:
- a vanity scraper that maximizes product counts
- a substitute for formal IFU review when critical decisions are being made
- a general medical encyclopedia
- a place to hide uncertain or inferred specs as if they were verified

## Product Goal

Create a catalog that is good enough to power downstream clinician-facing tools:
- device search and lookup
- case prep support
- procurement and inventory understanding
- teaching and trainee reference
- competitive and category analysis
- future retrieval and AI layers

## Success Criteria

The repository is succeeding when:

1. Important device families are present
   - neurovascular and core spine categories have meaningful coverage
   - major manufacturers are not missing or represented only by skeletons

2. The source chain is trustworthy
   - each useful entry can be traced to FDA records, official manufacturer pages, PDFs, or clearly labeled scraped content

3. The catalog is clinically useful
   - entries answer real questions about device role, access platform, compatibility, indications, and major sizing or workflow facts when available

4. The workflow scales
   - scraped data can be reviewed and promoted without heroic manual effort
   - a new session can resume work without reconstructing everything from memory

5. Coverage metrics mean something
   - counts distinguish scraped-only, partial, and curated knowledge
   - the project measures usefulness, not just inventory

## Near-Term Strategic Objective

Move the catalog from “many partially captured products” to “materially useful device reference.”

Progress as of 2026-03-31: catalog grew from 68 to 122 curated knowledge files via extraction pipeline + batch promotion. Extraction pipeline now harvests from 6 sources (FDA APIs, manufacturer scrapers, EVToday, NSPR, Marker PDF extraction, DeepSeek synthesis).

The next stage is:
- filling remaining gaps in promoted files (26% of core sections still empty)
- acquiring NSPR-hosted technique guide PDFs for spine devices
- promoting remaining enriched drafts that meet quality threshold
- enriching thin categories: guidewires (0 curated), stent-retriever (0 curated), embolic coils (5 curated)

## Non-Goals

Do not optimize first for:
- adding every obscure regional variant
- exhaustive global market coverage
- reimbursement and trial outcomes
- long-tail categories that do not meaningfully improve the catalog's clinical utility

Those may matter later, but they are not the core goal now.

## Practical Definition of Done

A device catalog entry is strong when it has:
- correct manufacturer
- correct category
- clear device role
- at least one source-backed technical or workflow detail
- clear source provenance
- enough substance to be genuinely useful to a clinician or reviewer

## Bottom Line

The end goal is not a pile of scraped pages.

The end goal is a trusted device reference backbone that can support real clinical, educational, and product workflows.
