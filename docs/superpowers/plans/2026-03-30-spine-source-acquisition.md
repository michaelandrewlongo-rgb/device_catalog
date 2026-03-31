# Spine Source Document Acquisition - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add spine product codes to the FDA pipeline, download 510(k) PDFs, update Chrome MCP workflow for spine IFU acquisition, and add source tracking to the catalog index.

**Architecture:** Three-phase approach. Phase 1 adds spine config to existing pipeline code (no new modules). Phase 2 extends the Chrome workflow doc with spine manufacturer navigation guides. Phase 3 adds a source-coverage column to the catalog index generator. Each phase produces independently useful output.

**Tech Stack:** Python 3.11+, openFDA API, Chrome MCP tools, existing pipeline modules (config.py, scraper_510k.py, indexer.py)

---

## File Map

- **Modify:** `pipeline/config.py:22-38` -- add 5 spine product codes to `PRODUCT_CODE_MAP`
- **Modify:** `pipeline/config.py:86-156` -- add spine manufacturer aliases (NuVasive, SI-BONE, DePuy spine variants)
- **Modify:** `pipeline/scrapers/chrome_workflow.md:106-305` -- add spine manufacturer sections
- **Modify:** `pipeline/processing/indexer.py:41-48` -- add source PDF tracking to `DeviceEntry`
- **Modify:** `pipeline/processing/indexer.py:164-268` -- add source column to index output

---

### Task 1: Add Spine Product Codes to Config

**Files:**
- Modify: `pipeline/config.py:22-38`

- [ ] **Step 1: Add spine product codes to PRODUCT_CODE_MAP**

Open `pipeline/config.py` and add these entries after the `MOF` guidewire line (line 37), before the closing brace:

```python
    # Spine
    "MAX": "pedicle-screw",        # Pedicle screw spinal systems
    "NKB": "interbody-cage",       # Intervertebral body fusion devices
    "MQP": "cervical-plate",       # Anterior cervical plates
    "KWP": "corpectomy",           # Vertebral body replacement devices
    "OUR": "sacroiliac-fusion",    # Sacroiliac joint fusion devices
```

- [ ] **Step 2: Verify config loads without errors**

Run:
```bash
PYTHONUTF8=1 python -c "from pipeline.config import PRODUCT_CODE_MAP; print(f'{len(PRODUCT_CODE_MAP)} codes loaded'); assert 'MAX' in PRODUCT_CODE_MAP; assert 'NKB' in PRODUCT_CODE_MAP; print('Spine codes OK')"
```

Expected: `16 codes loaded` and `Spine codes OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/config.py
git commit -m "feat: add 5 spine product codes to FDA pipeline config

Adds MAX (pedicle-screw), NKB (interbody-cage), MQP (cervical-plate),
KWP (corpectomy), OUR (sacroiliac-fusion) to PRODUCT_CODE_MAP."
```

---

### Task 2: Add Spine Manufacturer Aliases

**Files:**
- Modify: `pipeline/config.py:86-156`

- [ ] **Step 1: Add spine-specific manufacturer aliases**

In `MANUFACTURER_ALIASES` dict in `pipeline/config.py`, add these entries. Some spine manufacturers have FDA applicant strings not yet mapped:

```python
    # NuVasive (merged with Globus Medical 2023)
    "nuvasive, inc.": "nuvasive",
    "nuvasive": "nuvasive",
    "nuvasive specialized orthopedics, inc.": "nuvasive",
    # SI-BONE
    "si-bone, inc.": "si-bone",
    "si-bone inc.": "si-bone",
    # DePuy Synthes spine variants
    "depuy synthes products, llc": "depuy",
    "synthes usa, llc": "depuy",
    "synthes usa products, llc": "depuy",
    "synthes (usa)": "depuy",
    "depuy synthes spine, inc.": "depuy",
    # Stryker spine variants
    "stryker spine, inc.": "stryker",
    "k2m, inc.": "stryker",
    "k2m": "stryker",
    # Medtronic spine variants
    "medtronic sofamor danek, inc.": "medtronic",
    "sofamor danek usa, inc.": "medtronic",
    "medtronic spine llc": "medtronic",
    # Zimmer Biomet spine
    "zimmer biomet spine, inc.": "zimmer-biomet",
    "zimmer spine, inc.": "zimmer-biomet",
    "ldr spine usa, inc.": "zimmer-biomet",
    # Orthofix / Musculoskeletal
    "orthofix, inc.": "orthofix",
    "orthofix medical, inc.": "orthofix",
```

Note: `"depuy synthes products, inc."` and `"depuy spine, inc."` already exist at lines 122-124. Do not duplicate them. Only add the new entries above.

- [ ] **Step 2: Verify aliases resolve correctly**

Run:
```bash
PYTHONUTF8=1 python -c "
from pipeline.config import normalize_manufacturer
tests = {
    'NuVasive, Inc.': 'nuvasive',
    'SI-BONE, Inc.': 'si-bone',
    'Synthes USA, LLC': 'depuy',
    'K2M, Inc.': 'stryker',
    'Medtronic Sofamor Danek, Inc.': 'medtronic',
}
for raw, expected in tests.items():
    result = normalize_manufacturer(raw)
    status = 'OK' if result == expected else f'FAIL (got {result})'
    print(f'  {raw} -> {result} [{status}]')
"
```

Expected: All entries show `OK`.

- [ ] **Step 3: Commit**

```bash
git add pipeline/config.py
git commit -m "feat: add spine manufacturer aliases for FDA normalization

Covers NuVasive, SI-BONE, DePuy Synthes spine, K2M/Stryker,
Sofamor Danek/Medtronic, Zimmer Biomet, and Orthofix."
```

---

### Task 3: Run FDA Discovery for Spine Codes

**Files:**
- No code changes. Pipeline execution only.

- [ ] **Step 1: Run FDA 510(k) discovery for spine codes**

Run:
```bash
PYTHONUTF8=1 python -m pipeline.run_fda --codes MAX NKB MQP KWP OUR
```

Expected: Discovery report printed with device counts per category. Records saved to `pipeline/data/fda_raw/{MAX,NKB,MQP,KWP,OUR}/`.

Record the total device count and new-device count from the summary table. This tells us how many spine devices the FDA knows about vs. what we already have.

- [ ] **Step 2: Review discovery report for data quality**

Run:
```bash
PYTHONUTF8=1 python -c "
import json
from pathlib import Path
for code in ['MAX', 'NKB', 'MQP', 'KWP', 'OUR']:
    d = Path(f'pipeline/data/fda_raw/{code}')
    if d.exists():
        files = list(d.glob('*.json'))
        print(f'{code}: {len(files)} records')
        if files:
            sample = json.loads(files[0].read_text(encoding='utf-8'))
            print(f'  Sample: {sample.get(\"device_name_fda\", \"?\")[:60]}')
            print(f'  Manufacturer: {sample.get(\"manufacturer_canonical\", \"?\")}')
            print(f'  Category: {sample.get(\"catalog_category\", \"?\")}')
    else:
        print(f'{code}: no directory (0 records)')
"
```

Check that:
- Categories resolve correctly (MAX -> pedicle-screw, NKB -> interbody-cage, etc.)
- Manufacturer names normalize to expected slugs
- No unexpected "unknown" categories

- [ ] **Step 3: Download 510(k) summary PDFs**

Run:
```bash
PYTHONUTF8=1 python -m pipeline.run_fda --codes MAX NKB MQP KWP OUR --download-pdfs
```

Expected: PDFs downloaded to `pipeline/data/pdfs/`. Some will fail (404, HTML-instead-of-PDF) -- that's normal. Log the success/failure counts.

- [ ] **Step 4: Generate skeleton drafts**

Run:
```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --merge-only --all-drafts
```

Expected: New skeleton drafts appear in `pipeline/data/drafts/` for spine devices not already in the catalog. These are FDA-only skeletons with `[NEEDS CONTENT]` placeholders.

- [ ] **Step 5: Regenerate catalog index**

Run:
```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
```

Expected: `CATALOG_INDEX.md` at repo root is updated with spine categories and their counts.

- [ ] **Step 6: Commit FDA data**

```bash
git add pipeline/data/fda_raw/ CATALOG_INDEX.md
git commit -m "data: FDA 510(k) discovery for spine product codes

Ran discovery for MAX (pedicle-screw), NKB (interbody-cage),
MQP (cervical-plate), KWP (corpectomy), OUR (sacroiliac-fusion).
[UPDATE WITH ACTUAL COUNTS]"
```

Note: Do NOT commit `pipeline/data/pdfs/` or `pipeline/data/drafts/` -- these are regenerable caches.

---

### Task 4: Add Spine Manufacturer Sections to Chrome Workflow

**Files:**
- Modify: `pipeline/scrapers/chrome_workflow.md`

- [ ] **Step 1: Add SI-BONE section**

Append to `pipeline/scrapers/chrome_workflow.md` before the "After the Session" section (before line 289):

```markdown
---

## Manufacturer: SI-BONE

**Priority**: Tier 1 (public site, minimal gating)

**Product URL**: `https://si-bone.com/providers/ifuse-implant-system`

**Strategy**: Direct navigation. SI-BONE is a single-product company (iFuse). The provider page has product details, technique guides, and clinical resources. No HCP gate for basic product info.

**Documents to find**:
- iFuse Implant System surgical technique guide (PDF)
- iFuse-3D product information (PDF)
- IFU / Directions for Use (may require HCP section)

**Category**: `sacroiliac-fusion`

**Known products**:
- iFuse Implant System (sacroiliac-fusion)
- iFuse-3D (sacroiliac-fusion, 3D-printed variant)
- iFuse TORQ (sacroiliac-fusion, threaded variant)
- iFuse Bedrock (supplemental iliac fixation)

**Naming convention**: `sacroiliac-fusion--si-bone--ifuse--{doc-type}.pdf`

---

## Manufacturer: DePuy Synthes (Spine)

**Priority**: Tier 2 (semi-public product catalog)

**Listing URLs**:
- `https://www.jnjmedtech.com/en-US/specialties/spine`
- `https://www.depuysynthes.com/products` (redirects to jnjmedtech)

**Strategy**: Navigate product listing, filter by spine category. Product pages have "Resources" or "Downloads" tabs with technique guides. IFUs may require HCP login on `synthes.us`.

**Documents to find for new devices**:
- CONCORDE LIFT Expandable: technique guide or IFU

**Category patterns**:
| Pattern | Category |
|---------|----------|
| expedium, viper, pedicle, screw system | pedicle-screw |
| zero-p, cervical cage, acdf cage | cervical-cage |
| vectra, cervical plate, anterior plate | cervical-plate |
| synmesh, corpectomy, vertebral body | corpectomy |
| concorde, interbody, tlif, plif, alif | interbody-cage |

**Known spine products (already curated, look for IFUs only)**:
- EXPEDIUM VERSE Spine System (pedicle-screw)
- VIPER PRIME (pedicle-screw)
- Zero-P (cervical-cage)
- VECTRA (cervical-plate)
- SYNMESH (corpectomy)
- CONCORDE LIFT (interbody-cage) -- **new, needs IFU**

**Naming convention**: `{category}--depuy--{product}--{doc-type}.pdf`

---

## Manufacturer: Globus Medical

**Priority**: Tier 2 (product pages semi-public)

**Listing URL**: `https://www.globusmedical.com/musculoskeletal-solutions/spine/`

**Strategy**: Navigate spine product listing. Globus product pages typically have downloadable brochures and technique guides without HCP gating. Some IFUs may require login.

**Documents to find for new devices**:
- COALITION cervical cage: technique guide or brochure
- CREO MIS: technique guide or brochure

**Category patterns**:
| Pattern | Category |
|---------|----------|
| revere, patriot, creo, pedicle, screw | pedicle-screw |
| coalition, cervical cage, acdf | cervical-cage |
| rise, caliber, interbody, tlif, plif | interbody-cage |
| excelsius, navigation, robot | navigation |

**Known spine products**:
- REVERE Addition Revision (pedicle-screw) -- existing, look for IFU
- RISE TLIF (interbody-cage) -- existing, has technique PDF
- COALITION (cervical-cage) -- **new, needs IFU**
- CREO MIS (pedicle-screw) -- **new, needs IFU**

**Naming convention**: `{category}--globus--{product}--{doc-type}.pdf`

---

## Manufacturer: NuVasive (now Globus Medical)

**Priority**: Tier 2 (legacy site may redirect)

**Listing URL**: `https://www.nuvasive.com/surgical-solutions/` (may redirect to Globus post-merger)

**Strategy**: NuVasive merged with Globus Medical in September 2023. Legacy product pages may redirect. Check both `nuvasive.com` and `globusmedical.com` for product information. If the NuVasive site is down, search Globus for the product names.

**Documents to find for new devices**:
- Reline Spinal Fixation System: technique guide
- CoRoent XL / XL-T: technique guide

**Known products**:
- Reline (pedicle-screw) -- **new, needs IFU**
- CoRoent XL / XL-T / STALIF (interbody-cage) -- **new, needs IFU**
- Precept (pedicle-screw) -- not in catalog yet but look for it

**Naming convention**: `{category}--nuvasive--{product}--{doc-type}.pdf`

---

## Manufacturer: Medtronic (Spine)

**Priority**: Tier 3 (HCP-gated, heavy JS)

**Listing URL**: `https://www.medtronic.com/us-en/healthcare-professionals/products/spinal-orthopaedic.html`

**Strategy**: Same SPA architecture as neurological products (see existing Medtronic section). Product data loads via React. Network interception may reveal API endpoints. Most IFUs require HCP login through `manuals.medtronic.com`.

**Documents to find for new devices**:
- CAPSTONE PEEK cage: IFU or technique guide
- Pyramesh titanium cage: IFU or technique guide
- O-arm O2: operator manual or clinical guide (capital equipment)
- Mazor X Stealth Edition: clinical guide (capital equipment)
- Prestige LP: IFU (PMA product, may have public SSED on FDA.gov)

**HCP gate workaround**: If user is authenticated in Chrome to Medtronic HCP portal, IFUs are accessible. If not, check FDA.gov for public SSEDs (Summary of Safety and Effectiveness Data) for PMA products like Prestige LP.

**Category patterns**:
| Pattern | Category |
|---------|----------|
| cd horizon, solera, pedicle, expedium | pedicle-screw |
| capstone, cervical cage, peek cage | cervical-cage |
| atlantis, cervical plate, vision elite | cervical-plate |
| pyramesh, corpectomy, vertebral body, mesh cage | corpectomy |
| elevate, clydesdale, interbody, expandable cage | interbody-cage |
| o-arm, imaging, cone beam | navigation |
| mazor, robot, stealth, navigation | navigation |
| prestige, disc replacement, arthroplasty | cervical-disc |

**Known spine products**:
- CD Horizon (pedicle-screw) -- existing
- Solera 5.5/6.0 (pedicle-screw) -- existing
- Atlantis Vision Elite (cervical-plate) -- existing
- Elevate Expandable (interbody-cage) -- existing
- CAPSTONE (cervical-cage) -- **new, needs IFU**
- Pyramesh (corpectomy) -- **new, needs IFU**
- O-arm O2 (navigation) -- **new, needs clinical guide**
- Mazor X Stealth (navigation) -- **new, needs clinical guide**
- Prestige LP (cervical-disc) -- **new, needs IFU/SSED**

**Naming convention**: `{category}--medtronic--{product}--{doc-type}.pdf`

---

## Manufacturer: Stryker (Spine)

**Priority**: Tier 3 (HCP-gated)

**Listing URL**: `https://www.stryker.com/us/en/spine.html`

**Strategy**: Stryker spine products are on the main stryker.com domain (separate from neurosurgical.stryker.com). Product pages have "Resources" sections. Most IFUs require HCP login.

**Documents to find for new devices**:
- Tritanium TL: technique guide (may be alongside existing Tritanium C docs)
- Reflex Hybrid: technique guide

**Category patterns**:
| Pattern | Category |
|---------|----------|
| xia, pedicle, deformity | pedicle-screw |
| tritanium c, cervical cage, acdf | cervical-cage |
| tritanium tl, tlif, posterior lumbar | interbody-cage |
| reflex, cervical plate, hybrid | cervical-plate |
| spinemap, navigation | navigation |

**Known spine products**:
- Xia 3 Deformity (pedicle-screw) -- existing
- Tritanium C (cervical-cage) -- existing, has IFU
- SpineMap 3D (navigation) -- existing
- Tritanium TL (interbody-cage) -- **new, needs IFU**
- Reflex Hybrid (cervical-plate) -- **new, needs technique guide**

**Naming convention**: `{category}--stryker--{product}--{doc-type}.pdf`
```

- [ ] **Step 2: Verify markdown renders correctly**

Read the file back and check that all tables render, no broken pipes, section headers are correct.

- [ ] **Step 3: Commit**

```bash
git add pipeline/scrapers/chrome_workflow.md
git commit -m "docs: add spine manufacturer sections to Chrome MCP workflow

Covers SI-BONE, DePuy Synthes spine, Globus Medical, NuVasive,
Medtronic spine, and Stryker spine with navigation URLs, category
patterns, known products, and document priorities."
```

---

### Task 5: Add Source PDF Tracking to Catalog Index

**Files:**
- Modify: `pipeline/processing/indexer.py:41-48` (DeviceEntry)
- Modify: `pipeline/processing/indexer.py:70-96` (_load_curated)
- Modify: `pipeline/processing/indexer.py:243-267` (Full Device List output)

- [ ] **Step 1: Add source_pdfs field to DeviceEntry**

In `pipeline/processing/indexer.py`, change the `DeviceEntry` NamedTuple to add a `source_pdfs` field:

```python
class DeviceEntry(NamedTuple):
    category: str
    manufacturer: str
    product: str
    status: str          # "curated" | "scraped"
    sections_populated: int
    sections_total: int
    source_pdfs: list[str]  # doc types found: "ifu", "510k", "technique", etc.
```

- [ ] **Step 2: Scan for paired PDFs in _load_curated**

In the `_load_curated` function, after building the `stem` variable (around line 78), add PDF scanning:

```python
        # Scan for paired source PDFs
        pdf_prefix = f.stem.replace("--knowledge", "")
        source_pdfs = []
        for pdf in sorted(CATALOG_ROOT.glob(f"{pdf_prefix}--*.pdf")):
            # Extract doc type from filename: {stem}--{doc-type}.pdf
            doc_type = pdf.stem.split("--")[-1]
            source_pdfs.append(doc_type)
```

Then pass `source_pdfs=source_pdfs` to the `DeviceEntry` constructor. For scraped entries in `_load_scraped`, pass `source_pdfs=[]`.

- [ ] **Step 3: Add Sources column to Full Device List table**

In the `generate_catalog_index` function, update the Full Device List table (around line 257) to include a Sources column:

Change:
```python
        lines.append("| Device | Manufacturer | Status | Sections |")
        lines.append("|--------|--------------|--------|----------|")
```

To:
```python
        lines.append("| Device | Manufacturer | Status | Sections | Sources |")
        lines.append("|--------|--------------|--------|----------|---------|")
```

And update the row output:
```python
        for e in cat_entries:
            sources_str = ", ".join(e.source_pdfs) if e.source_pdfs else "--"
            lines.append(
                f"| {e.product} | {e.manufacturer} | {e.status} "
                f"| {e.sections_populated}/{e.sections_total} | {sources_str} |"
            )
```

- [ ] **Step 4: Verify index generates without errors**

Run:
```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
```

Expected: `CATALOG_INDEX.md` regenerated. Spot-check a few spine entries to confirm the Sources column shows correct doc types (e.g., Tritanium C should show `ifu`, Expedium Verse should show `510k`).

- [ ] **Step 5: Commit**

```bash
git add pipeline/processing/indexer.py CATALOG_INDEX.md
git commit -m "feat: add source PDF tracking to catalog index

Each device now shows which source document types (ifu, 510k,
technique, brochure, etc.) are paired in the catalog root."
```

---

### Task 6: Chrome MCP Session - SI-BONE (Tier 1)

**Files:**
- No code changes. Interactive Chrome MCP session.

- [ ] **Step 1: Load Chrome MCP tools**

```
ToolSearch: select:mcp__claude-in-chrome__tabs_context_mcp
ToolSearch: select:mcp__claude-in-chrome__navigate
ToolSearch: select:mcp__claude-in-chrome__get_page_text
ToolSearch: select:mcp__claude-in-chrome__read_page
ToolSearch: select:mcp__claude-in-chrome__javascript_tool
ToolSearch: select:mcp__claude-in-chrome__tabs_create_mcp
```

- [ ] **Step 2: Navigate to SI-BONE provider page**

```
tabs_context_mcp(createIfEmpty=true)
tabs_create_mcp(url="https://si-bone.com/providers")
```

Look for links to:
- iFuse Implant System product page
- Surgical technique downloads
- IFU / Directions for Use

- [ ] **Step 3: Download available PDFs**

For each PDF found, download and rename to:
- `sacroiliac-fusion--si-bone--ifuse--ifu.pdf` (if IFU found)
- `sacroiliac-fusion--si-bone--ifuse--technique.pdf` (if technique guide found)
- `sacroiliac-fusion--si-bone--ifuse--brochure.pdf` (if brochure found)

Place in catalog root: `C:\Users\Michael\documents\device_catalog\`

- [ ] **Step 4: Verify knowledge file against source**

Read the downloaded PDF and compare against `sacroiliac-fusion--si-bone--ifuse--knowledge.md`. Update any sections where the IFU provides more precise information (exact sizing, specific contraindication language, MRI safety status).

- [ ] **Step 5: Commit**

```bash
git add sacroiliac-fusion--si-bone--ifuse--*.pdf sacroiliac-fusion--si-bone--ifuse--knowledge.md
git commit -m "data: add SI-BONE iFuse source PDFs and verify knowledge file"
```

---

### Task 7: Chrome MCP Session - DePuy / Globus / NuVasive (Tier 2)

**Files:**
- No code changes. Interactive Chrome MCP sessions.

- [ ] **Step 1: DePuy Synthes - CONCORDE LIFT**

Navigate to JNJ MedTech spine products. Find CONCORDE LIFT product page. Download technique guide or IFU. Rename to `interbody-cage--depuy--concorde-lift--technique.pdf` (or `--ifu.pdf`). Verify knowledge file against source.

- [ ] **Step 2: Globus Medical - COALITION**

Navigate to Globus Medical spine products. Find COALITION cervical cage. Download available PDFs. Rename to `cervical-cage--globus--coalition--{doc-type}.pdf`. Verify knowledge file.

- [ ] **Step 3: Globus Medical - CREO MIS**

Find CREO MIS on Globus site. Download available PDFs. Rename to `pedicle-screw--globus--creo-mis--{doc-type}.pdf`. Verify knowledge file.

- [ ] **Step 4: NuVasive - Reline and CoRoent**

Check nuvasive.com (may redirect to Globus). Find Reline and CoRoent product pages. Download available PDFs:
- `pedicle-screw--nuvasive--reline--{doc-type}.pdf`
- `interbody-cage--nuvasive--coroent--{doc-type}.pdf`

Verify knowledge files.

- [ ] **Step 5: Commit all Tier 2 PDFs**

```bash
git add interbody-cage--depuy--concorde-lift--*.pdf interbody-cage--depuy--concorde-lift--knowledge.md
git add cervical-cage--globus--coalition--*.pdf cervical-cage--globus--coalition--knowledge.md
git add pedicle-screw--globus--creo-mis--*.pdf pedicle-screw--globus--creo-mis--knowledge.md
git add pedicle-screw--nuvasive--reline--*.pdf pedicle-screw--nuvasive--reline--knowledge.md
git add interbody-cage--nuvasive--coroent--*.pdf interbody-cage--nuvasive--coroent--knowledge.md
git commit -m "data: add Tier 2 spine source PDFs (DePuy, Globus, NuVasive)"
```

---

### Task 8: Chrome MCP Session - Medtronic / Stryker (Tier 3)

**Files:**
- No code changes. Interactive Chrome MCP sessions.

- [ ] **Step 1: Medtronic - Prestige LP (check FDA.gov for public SSED first)**

Before navigating Medtronic's site, check FDA.gov for the Prestige LP PMA (P060018). The SSED is public:
Navigate to `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P060018`

Download the SSED PDF. Rename to `cervical-disc--medtronic--prestige-lp--ssed.pdf`.

- [ ] **Step 2: Medtronic spine products (HCP portal)**

Navigate to Medtronic spine/orthopaedic product listing. For each new device (CAPSTONE, Pyramesh, O-arm, Mazor X), attempt to find and download technique guides or IFUs. If gated, note which URLs require login.

Expected PDFs:
- `cervical-cage--medtronic--capstone--{doc-type}.pdf`
- `corpectomy--medtronic--pyramesh--{doc-type}.pdf`
- `navigation--medtronic--o-arm--{doc-type}.pdf`
- `navigation--medtronic--mazor-x-stealth--{doc-type}.pdf`

- [ ] **Step 3: Stryker spine products (HCP portal)**

Navigate to Stryker spine product listing. For Tritanium TL and Reflex Hybrid, attempt to find and download technique guides. If gated, note which URLs require login.

Expected PDFs:
- `interbody-cage--stryker--tritanium-tl--{doc-type}.pdf`
- `cervical-plate--stryker--reflex-hybrid--{doc-type}.pdf`

- [ ] **Step 4: Verify knowledge files against any obtained sources**

For each PDF successfully downloaded, compare against the corresponding knowledge file and update precise values.

- [ ] **Step 5: Commit all Tier 3 PDFs**

```bash
git add cervical-disc--medtronic--prestige-lp--*.pdf
git add cervical-cage--medtronic--capstone--*.pdf
git add corpectomy--medtronic--pyramesh--*.pdf
git add navigation--medtronic--o-arm--*.pdf
git add navigation--medtronic--mazor-x-stealth--*.pdf
git add interbody-cage--stryker--tritanium-tl--*.pdf
git add cervical-plate--stryker--reflex-hybrid--*.pdf
git add *--knowledge.md
git commit -m "data: add Tier 3 spine source PDFs (Medtronic, Stryker)"
```

---

### Task 9: Final Index Regeneration and Verification

**Files:**
- No code changes. Pipeline execution and verification.

- [ ] **Step 1: Regenerate catalog index with source tracking**

```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --index-only
```

- [ ] **Step 2: Verify spine coverage in CATALOG_INDEX.md**

Check that:
- All 30 spine devices appear in the index
- Source columns show correct doc types for devices with paired PDFs
- Section counts are accurate (should be 6/7 or 7/7 for all spine devices)

- [ ] **Step 3: Commit final index**

```bash
git add CATALOG_INDEX.md
git commit -m "data: regenerate catalog index with spine source coverage"
```
