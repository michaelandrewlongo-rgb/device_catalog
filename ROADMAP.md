# ROADMAP.md

## Current Priority Order

### 1. Convert the highest-value existing scraped inventory into useful knowledge
Why this comes first:
- There are already many scraped-only devices
- The fastest leverage is to improve usefulness, not just discover more names
- Promotion discipline will reveal where source quality is still weak

Targets:
- run or refine the promotion pipeline for strong existing candidates
- focus first on categories with many scraped products and weak curated coverage
- use review manifests to separate ready, partial, and empty entries

Priority categories:
- aspiration
- distal access
- embolic coils
- guidewires
- flow diverters
- Penumbra and Balt families with thin curated coverage

### 2. Close the biggest manufacturer acquisition gaps
Why this comes second:
- Some manufacturers already have partial workflows but poor extraction quality
- A few manufacturers appear to have outsized payoff if completed

Priority manufacturers:
1. Medtronic neurovascular
   - move beyond hardcoded fallback URLs
   - capture the real product detail flow and any discoverable API behavior

2. Cerenovus
   - move past seed landing pages to actual product detail capture

3. Balt
   - stabilize acquisition using Chrome where Python scraping blocks or degrades

4. MicroVention and Penumbra
   - enrich tabs, specs, and technical tables that were missed by existing scrapers

### 3. Execute the spine source acquisition plan
Why this matters:
- spine coverage expanded, but source depth appears uneven
- source-backed spine entries are more valuable than lightly derived summaries

Goals:
- add the planned spine codes
- run FDA discovery cleanly
- acquire public IFUs and technique guides where available
- mark gated or missing materials clearly instead of pretending they were found

### 4. Strengthen durable workflow state
Why this matters:
- this repo is vulnerable to context loss
- the user works iteratively and does not want heavyweight process
- a small amount of durable project memory will prevent repeated re-analysis

Actions:
- keep `STATE.md` current
- keep `CATALOG_INDEX.md` and `REVIEW_MANIFEST.md` regenerated when major work lands
- record discovered APIs or manufacturer-specific scraping notes in a durable file

### 5. Improve quality metrics so they reflect clinical usefulness
Needed improvements:
- separate scraped-only from review-ready and truly curated
- track which entries have official PDFs or official source pages
- distinguish marketing-only entries from source-grounded ones

### 6. Only then expand into lower-priority data layers
Later opportunities:
- PMA SSED or deeper FDA labeling enrichment
- recalls or MAUDE linkage
- clinical trial evidence
- reimbursement mapping
- registry outcomes
- competitive analysis layers

## What To Ignore For Now

Do not let the project drift into:
- broad market research
- reimbursement plumbing
- registry analytics
- global variant completeness
- clever automation that does not improve source quality or catalog usefulness

## Decision Rule

When choosing between tasks, prefer the one that does the most to improve:
1. source trust
2. clinical usefulness
3. promotion throughput
4. resumeability between sessions

## Single Best Near-Term Outcomes

The best next outcomes would be:
1. a real Medtronic and Cerenovus acquisition pass that produces durable, reusable source capture
2. a meaningful jump in promoted high-value devices from existing scraped inventory
3. spine entries that are more clearly source-backed rather than merely present
