# STATE.md

I was trying to:
Build and run the three-tier extraction/enrichment pipeline end-to-end.

The last thing I saw:
Pipeline ran successfully with all tiers:
- Tier 1A: 281 FDA 510(k) PDFs extracted (pdfplumber)
- Tier 1B: 242 UDI results, 592 safety records (MAUDE + Recalls)
- Tier 1C: 301 EVToday devices (10 neuro categories, already cached)
- Tier 1D: 1,122 NSPR products listed, 88 detail pages scraped
- Tier 2: 43/57 catalog root PDFs extracted (Marker + DeepSeek). 14 remaining are large files or reference chapters.
- Tier 3: 2,668 devices enriched from all sources
- Final: 196 drafts, 74% core sections filled (439/588), 552 remaining [NEEDS CONTENT] placeholders

Enrichment source breakdown: EVToday 1,070 fields, FDA UDI 938, scraper 319, NSPR 253.

I think the status is:
Pipeline is functional. Marker models are downloaded and working. The FDA structured API queries are still running in background (242/2610 devices queried so far). Document extraction (Tier 2) processed 43 of 57 PDFs before stalling on large files.

What I want next:
1. Let FDA structured queries finish (still running in background)
2. Re-run enrichment + drafts once FDA queries complete for maximum coverage
3. Visit NSPR detail pages with full browser navigation (not iframe) to get PDF URLs and full Livewire-rendered spec tags
4. Run `--nspr-download` to fetch technique guide PDFs
5. Spot-check enriched drafts and promote best ones to catalog root

Key CLI:
```
python -m pipeline.run_extract --all        # All extraction tiers
python -m pipeline.run_enrich               # Tier 3 enrichment
python -m pipeline.run_pipeline --merge-only # Regenerate drafts
```
