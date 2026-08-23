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

Progress as of 2026-04-04: catalog at 213 curated knowledge files across 22 categories and 40 manufacturers. 317 total indexed devices. Extraction pipeline harvests from 6 sources (FDA APIs, manufacturer scrapers, EVToday, NSPR, Marker PDF extraction, DeepSeek synthesis).

Completed (2026-03-30 -- 2026-04-01):
- Extraction pipeline built: three-tier (FDA/EVToday/NSPR -> Marker+DeepSeek -> multi-source synthesis)
- 84 NSPR technique guide PDFs extracted via pdfplumber + DeepSeek (spine devices)
- 80 catalog-root PDFs extracted (brochures, IFUs, technique guides)
- Gap-fill engine: deterministic placeholder fill from extracted data
- Competitor comparison filler: 83/83 comparisons via DeepSeek
- Knowledge rewriter: FDA boilerplate cleanup (14 sections cleaned)
- 30 devices promoted in latest batch (thrombectomy, CSF shunts, dural substitutes, microcatheters, aspiration, distal access, embolic coils, flow diverter, interbody cage, cervical plate)
- Section fill improved: What It Is 98%, Sizing 82%, Key Differences 71%, Also Known As 86%
- [NEEDS CONTENT] reduced from 90 to 48 instances (47% reduction)
- Pipeline reliability fixes: DeepSeek timeout/token limits, Marker LLM hang fix, truncated JSON repair

The next stage is:
- Clean FDA boilerplate in newly promoted neurovascular files (54 noisy sections)
- Promote from remaining ~415 candidates with 3+ enriched fields
- Acquire neurovascular IFU PDFs to fill remaining gaps (sizing, use notes)
- Re-run FDA structured queries with rate limiting
- Stent-retriever category remains at 0 curated

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
