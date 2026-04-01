# STATE.md

I was trying to:
Complete Tier 2 NSPR extraction, promote 30 devices, consolidate all data, and push to GitHub.

The last thing I saw:
All consolidation steps complete. 174 curated files, 281 total indexed, all drafts regenerated with enriched overlays.

Current numbers (2026-04-01):
- 174 curated knowledge files (was 144 at session start)
- 107 scraped-only devices
- 281 total indexed
- 22 categories, 31 manufacturers
- 23 files with remaining gaps (30 [NEEDS CONTENT] instances)
- 2,668 enriched records
- 175 document extractions (84 NSPR + 80 catalog root + 11 FDA)
- 2,583 draft knowledge files (with enriched overlays)

Section fill rates:
- What It Is: 98% (was 94%)
- Indications: 97%
- Also Known As: 86%
- Sizing/Specs: 82% (was 62%)
- Use Notes: 79% (was 76%)
- Key Differences: 71% (was 65%)
- Compatible With: 46% (was 51% -- denominator grew)
- Contraindications: 30% (was 35% -- denominator grew)

What I want next:
1. Clean FDA boilerplate in 24 enriched-from-FDA files (54 noisy sections)
2. ~415 more candidates with 3+ fields available for future promotion
3. Neurovascular IFU acquisition for remaining gap fills
4. Re-run FDA structured queries with longer delays (hit 429 rate limits)
5. Stent-retriever category still at 0 curated

Key CLI:
```
python -m pipeline.run_enrich --gap-fill         # Fill [NEEDS CONTENT] gaps
python -m pipeline.run_enrich --competitor-fill  # DeepSeek competitor comparisons
python -m pipeline.run_enrich --rewrite          # Clean FDA boilerplate
python -m pipeline.run_post_extract              # Full post-extraction pipeline
python -m pipeline.run_pipeline --merge-only     # Regenerate drafts
python -m pipeline.run_pipeline --index-only     # Regenerate CATALOG_INDEX.md
```
