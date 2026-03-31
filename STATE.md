# STATE.md

I was trying to:
Build extraction pipeline, run it end-to-end, fix cross-match accuracy, promote enriched drafts, initialize git, and clean up repo.

The last thing I saw:
All objectives completed successfully:
- Extraction pipeline operational (9 modules in `pipeline/extraction/`)
- 54 devices promoted to catalog root (68 -> 122 curated)
- EVToday cross-match bug fixed (manufacturer-verified matching, 0 mismatches)
- Git repo initialized with 3 commits
- Auto-improve: stale files removed, deps fixed, ROADMAP updated

Current numbers (from CATALOG_INDEX.md, 2026-03-31):
- 122 curated knowledge files
- 112 scraped-only devices
- 234 total indexed
- 27 device categories
- Enrichment sources: EVToday 189 fields, FDA UDI 942, scraper 389, NSPR 13

I think the status is:
Pipeline is stable and producing clean data. The biggest remaining opportunity is filling the 26% of still-empty core sections. Two approaches: (1) visit NSPR detail pages with full browser rendering to get PDF URLs and Livewire-rendered spec tags, (2) let the FDA structured API queries finish and re-enrich.

What I want next:
1. Re-run FDA structured queries (background process may have timed out): `python -m pipeline.run_extract --fda-structured`
2. Re-run enrichment and drafts: `python -m pipeline.run_enrich && python -m pipeline.run_pipeline --merge-only`
3. NSPR detail scraping with full browser navigation (not iframe) to get PDF URLs
4. Download NSPR technique guide PDFs: `python -m pipeline.run_extract --nspr-download`
5. Run Tier 2 on downloaded PDFs: `python -m pipeline.run_extract --documents`
6. Focus promotion on thin categories: guidewires (0 curated), embolic coils (5 curated), stent-retriever (0 curated)

Key CLI:
```
python -m pipeline.run_extract --help           # All extraction options
python -m pipeline.run_extract --fda-structured  # FDA UDI/MAUDE/Recall
python -m pipeline.run_extract --documents       # Marker + DeepSeek PDF extraction
python -m pipeline.run_extract --nspr-download   # Download NSPR-hosted PDFs
python -m pipeline.run_enrich                    # Tier 3 enrichment
python -m pipeline.run_pipeline --merge-only     # Regenerate drafts
python -m pipeline.run_pipeline --index-only     # Regenerate CATALOG_INDEX.md
```
