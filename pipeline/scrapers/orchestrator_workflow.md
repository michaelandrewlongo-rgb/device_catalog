# Catalog Consolidation Orchestrator Workflow

Guide for running the Opus orchestrator + Sonnet worker + Opus synthesizer agent pipeline to promote scraped product data into knowledge.md files.

## Architecture

```
Orchestrator (Opus)
  |
  |-- reads CATALOG_INDEX.md
  |-- selects candidates: scraped products not yet curated
  |-- dispatches Worker subagents (Sonnet) in batches of 5-8
  |     Each worker generates one knowledge.md draft
  |
  |-- collects worker results
  |-- dispatches Data Synthesizer (Opus)
        Reviews all drafts for cross-device consistency
        Rates each: PROMOTE / HOLD / REJECT
```

## Step 1: Generate the Index

```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
```

This produces `CATALOG_INDEX.md` at the repo root showing all devices with their status (curated vs scraped) and section counts.

## Step 2: Select Candidates

The orchestrator reads `CATALOG_INDEX.md` and selects scraped products to promote:

**Include:** status = "scraped" AND sections_populated >= 3
**Prioritize:** sections_populated >= 4 ("ready" tier) first, then 3 ("partial")
**Skip:** Already curated devices, accessories (syringe kits, tubing kits), unknown category

## Step 3: Dispatch Workers

Dispatch one Sonnet worker per product, in batches of 5-8. Each worker gets:

### Worker Prompt Template

```
You are a medical device catalog writer for a neurosurgical knowledge base.

## Your Task
Generate a knowledge.md file for: {device_name} ({manufacturer})

## Reference Style
Read this curated knowledge file for the same device category to match the format and clinical depth:
{path_to_reference_knowledge_file}

## Input Data (from manufacturer website scraping)
{contents_of_scraper_raw_json}

## Output Format
Write the knowledge.md file following this exact section structure:

# {Device Name}

**Manufacturer:** {Display Name}
**Category:** {Category display}

## What It Is
[Device description, mechanism of action, materials, key design features]

## Sizing/Specs
[Dimensions, configurations, materials. Use tables where appropriate]

## Indications
[FDA-approved clinical uses, patient population criteria]

## Contraindications
[Only include if data available; omit section entirely if not]

## Compatible With
[Only include if data available; omit section entirely if not]

## Use Notes
[Only include if data available; omit section entirely if not]

## Key Differences vs Competitors
[NEEDS CONTENT - head-to-head comparison with competing devices in same category]

## Also Known As
[Alternate names, abbreviations, legacy product names]

## Rules
- Use clinical terminology appropriate for neurosurgeons and interventional neuroradiologists
- Do NOT invent data. If the scraper JSON lacks a field, write [NEEDS CONTENT - hint]
- Preserve exact numbers from the source data (sizing, specs, product codes)
- Use the canonical device names from the catalog for compatible_with references
- Match the tone and depth of the reference file
- Do NOT add sections not listed above

## Save Location
Write the file to: pipeline/data/drafts/{filename_stem}--knowledge.md
```

### Worker Dispatch Command

```
Agent(
    description="Write {device_name} knowledge file",
    model="sonnet",
    prompt="{filled_worker_prompt}",
)
```

### Reference File Selection

For each worker, select one curated knowledge.md in the same category:

| Category | Reference File |
|----------|---------------|
| thrombectomy | thrombectomy--stryker--trevo-nxt--knowledge.md |
| flow-diverter | flow-diverter--medtronic--pipeline-flex-shield--knowledge.md |
| intracranial-stent | intracranial-stent--microvention--lvis--knowledge.md |
| embolic-coil | embolic-coil--stryker--target-detachable--knowledge.md |
| microcatheter | microcatheter--medtronic--echelon--knowledge.md |
| liquid-embolic | liquid-embolic--medtronic--onyx-les--knowledge.md |
| distal-access | distal-access--microvention--sofia--knowledge.md |
| balloon-catheter | balloon-catheter--microvention--scepter-c-xc--knowledge.md |
| intrasaccular | intrasaccular--microvention--web-embolization--knowledge.md |
| csf-shunt | csf-shunt--integra--certas-plus-valve--knowledge.md |
| aspiration | (no reference yet -- use distal-access reference) |
| guidewire | (no reference yet -- use microcatheter reference) |

## Step 4: Collect and Review Worker Outputs

After each batch completes:
1. Check that each draft was written to `pipeline/data/drafts/`
2. Verify file is valid markdown with expected sections
3. Log any workers that failed or produced empty output

## Step 5: Dispatch Synthesizer

After all workers complete, dispatch the Opus synthesizer with ALL generated drafts.

### Synthesizer Prompt Template

```
You are reviewing a batch of knowledge.md drafts for the medical device catalog.
Your role is cross-device consistency and quality control.

## All Drafts Generated This Session
{list_of_draft_file_paths}

## Existing Curated Devices (for cross-reference)
{list_of_curated_device_names_by_category}

## Tasks

1. **Compatible With cross-check:** For each draft that lists compatible devices,
   verify those devices exist in the catalog (either curated or in this batch).
   Fix any references to non-existent devices.

2. **Naming consistency:** Ensure the same device is referenced the same way
   across all drafts (e.g., "Solitaire X" not sometimes "Solitaire" and
   sometimes "Solitaire X Revascularization Device").

3. **Key Differences vs Competitors:** For devices in the same category,
   fill in comparative notes where possible. Example: if both Surpass Evolve
   and Pipeline Flex are flow diverters, note their differences.

4. **Also Known As normalization:** Remove duplicate entries, ensure legacy
   names are captured.

5. **Rate each draft:**
   - PROMOTE: Ready to move to catalog root (4+ sections with real content)
   - HOLD: Needs manual enrichment (has content but gaps in key sections)
   - REJECT: Too thin to be useful (1-2 sections only)

## Output
For each draft, report:
- Filename
- Rating: PROMOTE / HOLD / REJECT
- Changes made (if any)
- Notes for manual review (if HOLD)

Write updated drafts back to the same paths.
Write a promotion report to: pipeline/data/drafts/PROMOTION_REPORT.md
```

### Synthesizer Dispatch Command

```
Agent(
    description="Synthesize and review draft batch",
    model="opus",
    prompt="{filled_synthesizer_prompt}",
)
```

## Step 6: Promote Approved Drafts

After the synthesizer completes:

1. Read `pipeline/data/drafts/PROMOTION_REPORT.md`
2. For each PROMOTE-rated draft:
   - Copy from `pipeline/data/drafts/` to the catalog root
   - Verify the filename follows the naming convention
3. Regenerate the catalog index:
   ```bash
   PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
   ```

## Batch Size Guidelines

- **Per batch:** 5-8 workers (avoids overwhelming context)
- **Total candidates:** ~90 scraped products not yet curated
- **Estimated batches:** 12-18
- **Prioritize by manufacturer:**
  1. Cerenovus (8 products, all from Chrome MCP -- highest quality scraped data)
  2. Medtronic (9 products, Chrome MCP)
  3. Stryker (42 products, automated scraper)
  4. MicroVention (30 products, automated scraper)
  5. Balt (21 products, automated scraper)
  6. Penumbra (11 products, automated scraper)

## Rate Limiting

Workers read local JSON files (no network calls), so they can run in true parallel without rate limiting concerns. The only constraint is Claude Code's subagent concurrency limit.
