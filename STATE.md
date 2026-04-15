# STATE.md

I was trying to:
Run systematic promotion across all catalog categories, then run competitor-fill and clean up category taxonomy.

The last thing I saw:
Session complete. 228 curated, 103 scraped-only, 331 total. 28 categories (guide-catheter consolidated from balloon-guide-catheter + guiding-catheter). 222/228 files have competitor comparisons.

## What was done this session

Promotions (15 new curated files):
- sacroiliac-fusion--si-bone--ifuse-3d
- interbody-cage--medtronic--pivox-olif
- interbody-cage--stryker--mojave-pl-3d
- interbody-cage--globus--sable-expandable
- interbody-cage--stryker--cascadia-tl-3d
- cervical-cage--stryker--cascadia-cervical-3d
- pedicle-screw--stryker--everest-deformity
- pedicle-screw--globus--creo
- intracranial-stent--stryker--wingspan
- (plus aspiration, distal-access, intracranial-stent, thrombectomy, microcatheter, cervical-plate already in root)

Competitor fill:
- 222/228 curated files filled via Gemini Flash 2.5 (OpenRouter)
- New pipeline/extraction/gemini.py created; competitor_filler.py updated
- 6 remaining unfilled: singletons or thin categories with no peers

Category merge:
- balloon-guide-catheter + guiding-catheter → guide-catheter
- Updated: scraper_raw, merged, enriched, drafts for BOBBY and Chaperon

## Held (need enrichment)

Spine: Catalyft PL, QUARTEX OCT, SI-LOK SELECT, iFuse INTRA Ti, ACP, Venture, Zevo (all thin)
Neuro: FlowGate 2 BGC, Surpass Evolve, Balt flow diverters, Stryker Target coil variants, Microvention coils

## Known issues

- _load_env_key() in config.py returns LAST match in master_env.txt, not first. Gemini client has its own first-match loader to work around this.
- Root cause of gap-filler contamination was merger.py fuzzy name matching (threshold 0.4). Defended against in gap_filler.py; merger.py itself still unfixed.

## Fixed this session

- Gap-filler cross-device contamination (Alembic/APRO → Riptide file). Added identity guard in `pipeline/processing/gap_filler.py` that strips scraper content fields when merged-record device_name shares no meaningful tokens with the filename stem. Cleaned the contaminated merged + enriched records for `aspiration--medtronic--riptide-aspiration-react-68-catheter`. Verified: `--gap-fill --dry-run` now shows zero APRO/Alembic content in any preview.

## What I want next

1. Chrome MCP enrichment for FlowGate 2 BGC (IFU URL in draft, 20-30 min to promote)
2. Chrome MCP for Surpass Evolve (EVToday has sizing; need indications from IFU)
3. Fix merger.py fuzzy matching threshold (root cause, requires re-running merge pass)

## Key CLI

```
PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
PYTHONUTF8=1 python -m pipeline.run_enrich --competitor-fill
PYTHONUTF8=1 python -m pipeline.run_enrich --gap-fill --dry-run   # review before running live
```
