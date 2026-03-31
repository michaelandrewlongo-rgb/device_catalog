# Spine Source Document Acquisition Plan

**Date:** 2026-03-30
**Status:** Approved
**Approach:** Hybrid (FDA pipeline + Chrome MCP IFU sessions)

---

## Context

The spine section of the device catalog was expanded to 30 devices (from 17) with all 7 core knowledge sections filled. However, the 13 new devices have zero paired source PDFs, and the enriched sections on existing devices were written from training data rather than verified against authoritative sources. This plan addresses both gaps.

### Current Source Document Coverage

- **17 original spine devices:** Each has 1-2 source PDFs (510(k) summaries, technique guides, brochures)
- **13 new spine devices:** Zero source PDFs
- **Enriched sections on all 30:** Derived from training data, not yet verified against IFUs

---

## Phase 1: FDA Pipeline Expansion

### What

Add 5 spine product codes to `pipeline/config.py` and run the existing FDA discovery + PDF download pipeline.

### Product Codes

| Code | Category | Description |
|---|---|---|
| `MAX` | pedicle-screw | Pedicle screw spinal systems |
| `NKB` | interbody-cage | Intervertebral body fusion devices |
| `MQP` | cervical-plate | Anterior cervical plates |
| `KWP` | corpectomy | Vertebral body replacement devices |
| `OUR` | sacroiliac-fusion | Sacroiliac joint fusion devices |

### Deferred Codes (Require Disambiguation or PMA Handling)

| Code | Category | Issue |
|---|---|---|
| `MNI` | cervical-disc | PMA pathway, needs `PMA_PRODUCT_CODES` addition + PMA scraper testing |
| `LMH` | navigation | Covers both spine and cranial navigation, needs disambiguation rules |
| `ODP` | pedicle-screw | Overlaps with interlaminar fixation, needs disambiguation |
| `OIT` | interbody-cage | Expandable subset, may overlap with `NKB` |

### Implementation

1. Add codes to `PRODUCT_CODE_MAP` in `pipeline/config.py`
2. Run: `python -m pipeline.run_fda --codes MAX NKB MQP KWP OUR --download-pdfs`
3. 510(k) summary PDFs land in `pipeline/data/pdfs/` with standard naming
4. Run: `python -m pipeline.run_pipeline --merge-only --all-drafts` to generate skeleton drafts for newly discovered devices

### Output

- Comprehensive registry of FDA-cleared spine devices in these categories (estimated 200+ records)
- 510(k) summary PDFs (2-5 pages each) for most records
- Skeleton draft knowledge files for devices not already in the catalog
- Automatic deduplication via `EXISTING_DEVICES` in config

### Estimated Effort

~30 minutes (config change + pipeline run)

---

## Phase 2: Chrome MCP IFU Acquisition

### What

Use Chrome MCP interactive sessions to download IFU and technique guide PDFs from manufacturer websites for the 13 new spine devices.

### Priority Tiers

| Tier | Manufacturer | Devices | Gating Level |
|---|---|---|---|
| 1 | SI-BONE | iFuse | Low (public site) |
| 2 | DePuy Synthes | CONCORDE LIFT | Moderate (some public docs) |
| 2 | Globus Medical | COALITION, CREO MIS, CoRoent | Moderate (some public docs) |
| 3 | Medtronic | CAPSTONE, Pyramesh, O-arm, Mazor X Stealth, Prestige LP, Reline | High (HCP portal) |
| 3 | Stryker | Tritanium TL, Reflex Hybrid | High (HCP portal) |

### Workflow Per Device

1. Open manufacturer product page in Chrome
2. Navigate to device resources/downloads section
3. Download IFU or technique guide PDF
4. Rename to catalog convention: `{category}--{manufacturer}--{product}--{doc-type}.pdf`
5. Place in catalog root alongside knowledge file

### Chrome Workflow Documentation

Update `pipeline/scrapers/chrome_workflow.md` with navigation instructions for spine manufacturer product/IFU pages:
- SI-BONE: si-bone.com product page
- DePuy Synthes: synthes.us or depuysynthes.com product catalog
- Globus Medical: globusmedical.com product pages
- Medtronic: medtronic.com/us-en/healthcare-professionals spine section
- Stryker: stryker.com/us/en/spine product pages

### Estimated Effort

~15-30 minutes per device in Chrome MCP. Full pass: 4-6 hours of interactive sessions.

---

## Phase 3: Post-Acquisition Integration

### Verification Pass

For each device where a source PDF is obtained:
1. Read the IFU/510(k) against the knowledge file
2. Correct any inaccuracies in training-data-derived sections
3. Fill in precise values (exact sizing tables, specific contraindication language, MRI safety status)
4. Mark the file as "IFU-verified" in tracking

### Source Tracking

Add source coverage tracking to `CATALOG_INDEX.md` regeneration (`pipeline/processing/indexer.py`). Per-device columns:
- Source documents present (510k, IFU, technique, brochure)
- Knowledge file verification status (verified, unverified, partial)

### Draft Backlog

The FDA pipeline will discover many spine devices beyond the current 30. These remain as skeleton drafts in `pipeline/data/drafts/` for future enrichment, following the same promotion workflow as neurovascular devices.

### Estimated Effort

~2-3 hours for verification pass across 30 spine devices.

---

## Summary

| Phase | What | Effort | Output |
|---|---|---|---|
| 1 - FDA Pipeline | Add 5 product codes, run discovery | ~30 min | 510(k) PDFs, device registry, skeleton drafts |
| 2 - Chrome MCP | Interactive IFU download sessions | 4-6 hours | IFU/technique PDFs for 13 new devices |
| 3 - Integration | Verify knowledge files against sources | 2-3 hours | IFU-verified knowledge files, source tracking |

Total estimated effort: ~7-10 hours across multiple sessions.
