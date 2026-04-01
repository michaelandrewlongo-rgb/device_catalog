# ROADMAP.md

## Current Priority Order

### 1. Clean up noisy FDA boilerplate in curated files
Status: **In Progress** (Tier 2 FDA extraction running, rewriter built)

- 14 sections detected as noisy (raw regulatory text in knowledge files)
- Mostly in recently promoted guidewires and embolic coils
- Run `--fda-documents` then `--rewrite` to apply clean Tier 2 extractions

### 2. Fill remaining content gaps
Status: **Partially Complete** (29 gaps remain)

Completed:
- Gap-fill engine operational (pipeline/processing/gap_filler.py)
- 53/53 competitor comparisons filled via DeepSeek
- 5 deterministic gaps filled from extracted sources

Remaining 29 gaps:
- 8 alternate names (no source data)
- 8 sizing/specs (need IFU documents)
- 5 competitor comparisons (custom format, not batch-fillable)
- 3 indications (need FDA data)
- 5 IFU-specific details (need actual IFU PDFs)

### 3. Acquire NSPR technique guide PDFs
Status: **Complete** (84 PDFs downloaded, Tier 2 extraction running)

- 103 NSPR detail pages with 84 PDF URLs captured (authenticated session)
- 84 technique guide PDFs downloaded (495MB) to pipeline/data/extracted/nspr/pdfs/
- Tier 2 (Marker + DeepSeek) extraction running on all 84 PDFs
- Next: re-enrich after Tier 2 completes, then gap-fill spine device files

### 4. Promote more devices from enriched records
Status: **Ready**

- 2,668 enriched records, ~30 candidates with 3+ FDA-sourced fields
- Categories to target: other neurovascular (flow diverters, intracranial stents), spine
- Stent-retriever still at 0 curated (ERIC by MicroVention is the only candidate)

### 5. Close manufacturer acquisition gaps
Status: **Partially Complete**

Completed:
- Medtronic (29 curated), Stryker (30 curated), Cerenovus (15), MicroVention (13)
- Balt (10), Penumbra (8), Globus (8), SI-BONE (6), DePuy (6)

Remaining:
- Balt: stabilize acquisition using Chrome (bot detection)
- Penumbra: enrich tabs and technical tables
- MicroVention: capture specification tabs missed by Python scraper
- Asahi Intecc: only 2 curated (8 enriched records available)

### 6. Improve data quality metrics
Status: **Partially addressed**

- Enrichment `_enrichment` metadata tracks source and confidence per field
- Review manifest grades devices by section fill rate
- Section fill rates now tracked: What It Is 94%, Indications 97%, Sizing 62%
- Need: distinguish marketing-only entries from source-grounded ones

### 7. Expand into lower-priority data layers
Status: **Partially started**

Started:
- MAUDE adverse event integration (event counts, but API rate-limited)
- FDA recall integration (592 recall records, active recalls annotated in use_notes)

Later:
- Clinical trial evidence
- Reimbursement mapping
- Registry outcomes

## Decision Rule

When choosing between tasks, prefer the one that does the most to improve:
1. source trust
2. clinical usefulness
3. promotion throughput
4. resumability between sessions
