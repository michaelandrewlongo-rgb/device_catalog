# ROADMAP.md

## Current Priority Order

### 0. Prototype — user-facing catalog viewer
Status: **In progress** (image pipeline added 2026-04-02)

- Static HTML prototype built on branch `feat/catalog-prototype`
- Split-panel layout: search + browse (domain tree) on left, device detail + comparison on right
- Build: `python pipeline/build_site.py` → `site/index.html` (opens in any browser, no server needed)
- 213 root-level curated devices loaded; Fuse.js fuzzy search; marked.js markdown rendering

#### Image pipeline (partial — paused 2026-04-02)
- `pipeline/fetch_images.py` — fetches og:image from manufacturer pages, saves to `site/images/`
- Template updated: images render in device detail panel with onerror fallback
- 4 images downloaded: Balt aspiration (ballast, carrier, hybrid, raptor) as .webp
- **Blocked:** Medtronic CDN requires real browser — Chrome MCP bridge approach needed
  - og:image URLs extracted and documented in STATE.md, ready to resume
- **Next step:** Resume Medtronic download, then run full catalog pass
- After images complete: merge to main

### 1. Clean FDA boilerplate in newly promoted files
Status: **Ready**

- 54 noisy sections detected in 24 enriched-from-FDA files (raw 510(k) language)
- Rewriter skips these because no Tier 2 extraction data exists for neurovascular devices
- Need: targeted DeepSeek rewrite pass, or acquire source IFU/brochure PDFs first
- CLI: `python -m pipeline.run_enrich --rewrite` (after acquiring Tier 2 data)

### 2. Promote more devices from enriched records
Status: **Largely complete for current data**

Completed:
- 30 devices promoted on 2026-04-01 (6 from drafts, 24 from enriched)
- 22 devices promoted on 2026-03-31
- 15 additional devices promoted 2026-04-14/15 (spine sacroiliac batch + pedicle-screw batch 2 + neurovascular):
  - sacroiliac-fusion: iFuse 3D
  - interbody-cage: Pivox OLIF, Mojave PL 3D, SABLE Expandable, Cascadia TL 3D
  - cervical-cage: Cascadia Cervical 3D
  - pedicle-screw: Everest Deformity, CREO (full system)
  - intracranial-stent: Wingspan
  - (plus several already in root from prior sessions)

Remaining scraped pool:
- 103 scraped-only devices remain; most are thin (1-2 sections) or have scraper artifacts
- Promotable with Chrome MCP: FlowGate 2 BGC, Surpass Evolve, Balt flow diverters, Stryker Target coil variants
- HOLD (need IFU): Catalyft PL, QUARTEX OCT, SI-LOK SELECT, iFuse INTRA Ti

### 3. Fill remaining content gaps
Status: **Partially Complete** (48 gaps remain in 38 files)

Gap-fill engine is operational but remaining gaps lack source data.

### 4. Acquire neurovascular IFU/brochure PDFs
Status: **Not started**

- Neurovascular devices lack Tier 2 extractions (NSPR covers spine only)
- Priority targets: flow diverters, intracranial stents, liquid embolics, thrombectomy devices
- Source: manufacturer sites via Chrome MCP, or FDA FOIA downloads
- These PDFs would unlock rewriter cleanup and gap-fill for neurovascular files

### 5. Close manufacturer acquisition gaps
Status: **Partially Complete**

Strong coverage (5+ curated): Medtronic (29+), Stryker (30+), Cerenovus (17), MicroVention (13+), Balt (11), Penumbra (8+), Globus (8+), SI-BONE (6), DePuy (6)

Remaining:
- Balt: stabilize acquisition using Chrome (bot detection)
- Penumbra: enrich tabs and technical tables
- MicroVention: capture specification tabs missed by Python scraper
- Asahi Intecc: only 2 curated (enriched records available)
- New manufacturers from promotions: Aesculap, Collagen Matrix, Nurami, NeuroDx, Phasor, MIVI, Q'Apel, Scientia, Perfuze

### 6. Re-run FDA structured queries
Status: **Blocked** (429 rate limits)

- UDI/MAUDE/Recall APIs hit rate limits on prior run
- Need longer delays between requests
- 245 UDI, 592 recalls already captured; MAUDE at 0

### 7. Improve data quality metrics
Status: **Partially addressed**

Current section fill rates (228 curated files, as of 2026-04-15):
- Key Differences vs Competitors: 222/228 filled (97%) via Gemini Flash 2.5 competitor-fill pass
- [NEEDS CONTENT] gaps: 44 files, 58 instances remaining
- Competitor filler uses OpenRouter → Gemini Flash 2.5 (swapped from DeepSeek 2026-04-15)
- Gap-filler has cross-device contamination issue — do not run without reviewing dry-run output first

### 8. Expand into lower-priority data layers
Status: **Later**

- Clinical trial evidence
- Reimbursement mapping
- Registry outcomes

## Decision Rule

When choosing between tasks, prefer the one that does the most to improve:
1. source trust
2. clinical usefulness
3. promotion throughput
4. resumability between sessions
