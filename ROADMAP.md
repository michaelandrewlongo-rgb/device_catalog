# ROADMAP.md

## Current Priority Order

### 1. Convert the highest-value existing scraped inventory into useful knowledge
Status: **In Progress** (batch promotion from 68 to 122 curated files completed 2026-03-31)

Remaining:
- 90+ enriched devices scored ready but lack draft files (need merger re-run to generate drafts)
- Review promoted files for accuracy, especially EVToday-sourced sizing data
- Priority categories still thin: guidewires (0 curated), embolic coils (5 curated)

### 2. Close the biggest manufacturer acquisition gaps
Status: **Partially Complete**

Completed:
- Medtronic spine (12 products) and neurovascular (9 products) via Chrome MCP + Academy
- Cerenovus (9 products) via Chrome MCP
- Stryker spine (7 products) via Chrome MCP
- Globus Medical (12 products) via Chrome MCP
- SI-BONE (7 products) via Chrome MCP

Remaining:
- Balt: stabilize acquisition using Chrome where Python scraping blocks
- Penumbra: enrich tabs and technical tables
- MicroVention: capture specification tabs missed by Python scraper

### 3. Extraction pipeline (NEW - built 2026-03-30/31)
Status: **Operational**

Built `pipeline/extraction/` with 9 modules:
- Tier 1A: FDA 510(k) PDF parsing (281 PDFs extracted via pdfplumber, Marker available)
- Tier 1B: FDA UDI/MAUDE/Recall API queries (242 UDI, 592 safety records)
- Tier 1C: EVToday device guide scraper (301 neurovascular devices, 10 categories)
- Tier 1D: NSPR spine/cranial harvester (1,122 listings across 7 categories, 88 detail pages)
- Tier 2: Marker + DeepSeek PDF extraction (43/57 catalog PDFs processed)
- Tier 3: Multi-source enrichment with manufacturer-verified matching

Remaining:
- Download NSPR-hosted technique guide PDFs (need full browser rendering for PDF URLs)
- Complete Tier 2 for remaining 14 catalog PDFs (large files)
- Let FDA structured queries finish (still running for remaining ~2,400 devices)

### 4. Strengthen durable workflow state
Status: **Improved**

Completed:
- Git repo initialized with baseline commit
- STATE.md updated with current pipeline commands
- .gitignore added for regenerable data
- CLAUDE.md expanded with priorities, source hierarchy, session rules

Remaining:
- Keep STATE.md current after each work session
- Keep CATALOG_INDEX.md regenerated when major work lands

### 5. Improve quality metrics so they reflect clinical usefulness
Status: **Partially addressed by enrichment pipeline**

The enrichment `_enrichment` metadata tracks source and confidence per field.
Review manifest grades devices by section fill rate.

Remaining:
- Track which entries have official PDFs or source pages
- Distinguish marketing-only entries from source-grounded ones

### 6. Only then expand into lower-priority data layers
Status: **Partially started**

Started:
- MAUDE adverse event integration (event counts per device)
- FDA recall integration (active recalls annotated in use_notes)

Later:
- Clinical trial evidence (MCP tools available but not pipelined)
- Reimbursement mapping
- Registry outcomes

## Decision Rule

When choosing between tasks, prefer the one that does the most to improve:
1. source trust
2. clinical usefulness
3. promotion throughput
4. resumability between sessions
