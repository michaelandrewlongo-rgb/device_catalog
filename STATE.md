# STATE.md

I was trying to:
Execute PRODUCT_GOAL.md "next stage" objectives, then clean up noisy FDA boilerplate in promoted files via Tier 2 (Marker + DeepSeek).

The last thing I saw:
All 7 original plan tasks complete. Tier 2 FDA extraction running in background for 24 curated devices. Knowledge rewriter built and ready.

Current numbers (2026-03-31):
- 144 curated knowledge files (was 122 at session start)
- 109 scraped-only devices
- 253 total indexed
- 21 categories, 21 manufacturers
- 24 files with remaining gaps (29 [NEEDS CONTENT] instances)
- Section fill: What It Is 94%, Indications 97%, Use Notes 76%, Sizing 62%, Also Known As 81%

Key changes this session:
1. Gap-fill engine (pipeline/processing/gap_filler.py) -- deterministic placeholder fill from extracted data
2. Competitor filler (pipeline/processing/competitor_filler.py) -- 53/53 comparisons via DeepSeek
3. Knowledge rewriter (pipeline/processing/rewriter.py) -- detects/replaces FDA boilerplate with Tier 2 data
4. Fixed FDA summary lookup in enricher.py (stem-based fallback) -- unlocked 724 enrichment fields
5. NSPR re-scrape: 103 detail pages (89 with specs, 88 with descriptions, 0 PDFs - login required)
6. Promoted 7 guidewires (0->7) and 15 embolic coils (5->20) from enriched records
7. Added --fda-documents to doc_extractor.py for Tier 2 extraction of curated FDA PDFs

Extraction pipeline asset counts:
- Tier 1A: 281 FDA summaries (pdfplumber)
- Tier 1B: 245 UDI, 0 MAUDE, 592 recalls
- Tier 1C: 301 EVToday devices (10 neuro categories)
- Tier 1D: 1,122 NSPR listings, 103 detail pages, 84 PDFs downloaded (495MB technique guides)
- Tier 2: 76 document extractions (53 catalog + 23 FDA) + 84 NSPR running
- Tier 3: 2,668 enriched records
- Source PDFs: 57 catalog root + 283 FDA 510(k) + 84 NSPR technique guides
- Scraper raw: 163 products across 9 manufacturers

What I want next:
1. Wait for Tier 2 NSPR extraction to finish (84 technique guides running through Marker + DeepSeek)
2. Re-run enrichment with new NSPR Tier 2 data, then gap-fill and rewrite
3. Re-run FDA structured queries with rate limiting (hit 429s last time)
4. Promote more devices from enriched records (~30 candidates with 3+ FDA fields)
5. Stent-retriever category still at 0 curated

Key CLI:
```
python -m pipeline.run_extract --help            # All extraction options
python -m pipeline.run_extract --fda-documents   # Tier 2 on curated FDA PDFs
python -m pipeline.run_enrich                    # Tier 3 enrichment
python -m pipeline.run_enrich --gap-fill         # Fill [NEEDS CONTENT] gaps
python -m pipeline.run_enrich --competitor-fill  # DeepSeek competitor comparisons
python -m pipeline.run_enrich --rewrite          # Clean FDA boilerplate
python -m pipeline.run_pipeline --merge-only     # Regenerate drafts
python -m pipeline.run_pipeline --index-only     # Regenerate CATALOG_INDEX.md
```
