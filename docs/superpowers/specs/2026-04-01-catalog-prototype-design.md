# Device Catalog Prototype — Design Spec

**Date:** 2026-04-01  
**Status:** Approved  
**Scope:** Read-only, user-facing prototype for device lookup and side-by-side comparison

---

## Overview

A static HTML prototype that compiles the catalog's curated knowledge files into a searchable, browsable web app. No server required at runtime. A single Python build script regenerates the site when files change.

**Primary use cases:**
1. Quick device lookup by name or alias ("pipeline", "ace 68", "trevo")
2. Side-by-side comparison of two devices

**Target users:** The catalog maintainer and other clinicians/trainees — no explanation of the data model required.

---

## Architecture

### Build script: `pipeline/build_site.py`

Reads all `*--knowledge.md` files from the catalog root (not `pipeline/data/drafts/`). For each file:

1. Parses the filename: `{category}--{manufacturer}--{slug}--knowledge.md` → structured fields
2. Parses the markdown body: H2 headings become section keys, content below each heading becomes section value (raw markdown string preserved)
3. Extracts "Also Known As" aliases into a dedicated field for search boosting

Writes two output files to `site/`:
- `catalog.json` — array of device objects (see Data Model below)
- `index.html` — single-file app with embedded JS/CSS, references `catalog.json`

**Run command:**
```bash
python pipeline/build_site.py
```

**Output:**
```
site/
  index.html
  catalog.json
```

Open `site/index.html` in any browser. No server needed.

---

## Data Model

Each device in `catalog.json`:

```json
{
  "id": "flow-diverter--medtronic--pipeline-flex-shield",
  "name": "Pipeline Flex Embolization Device",
  "category": "flow-diverter",
  "domain": "neurovascular",
  "manufacturer": "medtronic",
  "manufacturer_display": "Medtronic",
  "aliases": ["Pipeline", "PED", "Pipeline Flex", "Pipeline Shield"],
  "sections": {
    "What It Is": "Braided, multi-alloy mesh...",
    "Sizing": "| Diameter | ...",
    "Indications": "...",
    "Contraindications": "...",
    "Compatible With": "...",
    "Use Notes": "...",
    "Key Differences vs Competitors": "..."
  }
}
```

The `domain` field is derived from `category` using a static mapping defined in the build script (see Domain Mapping below).

---

## Domain Mapping

Three top-level domains with subcategories:

**Neurovascular**
- flow-diverter, microcatheter, aspiration, aspiration-catheter, distal-access, embolic-coil, intracranial-stent, stent-retriever, thrombectomy, intrasaccular, liquid-embolic, balloon-catheter, balloon-guide-catheter, guidewire, guiding-catheter, delivery-catheter

**Spine**
- pedicle-screw, interbody-cage, cervical-cage, cervical-plate, corpectomy, sacroiliac-fusion, cervical-disc

**Cranial**
- csf-shunt, dural-sealant, dural-substitute, navigation

Devices with category `unknown`, `accessory`, or unrecognized categories fall under a fourth bucket (`Other`) which appears at the bottom of the browse tree and is hidden if empty.

---

## UI Layout

### Top bar
- Logo: "NeuroDevice Catalog"
- Search input (full-width, live fuzzy search via Fuse.js)
- Device count stat ("213 curated")

### Left panel (300px fixed width)
Two modes, toggled by tabs at the top of the panel: **Search** and **Browse**.

**Search mode (default):**
- Results list updates live as the user types
- Each row: device name, manufacturer, category pill
- Result count shown above list
- Clicking a row loads the device in the right detail panel

**Browse mode:**
- Collapsible domain tree: Neurovascular / Spine / Cranial / Other
- Each domain expands to show subcategory rows with device counts
- Clicking a subcategory filters the results list below the tree
- Active subcategory is highlighted; clicking again deselects (shows all in domain)
- Category and domain names display in human-readable form (e.g. "flow-diverter" → "Flow Diverter")

### Right panel (flex remainder)
**Single device view (default):**
- Device header: category + domain label, device name (H1), manufacturer
- "Compare with..." button below header
- Sections rendered in order: What It Is, Sizing, Indications, Contraindications, Compatible With, Use Notes, Key Differences vs Competitors, plus any additional sections present in the file
- Markdown rendered to HTML via marked.js (tables, bold, lists, code all supported)
- Sections not present in the file are omitted (no empty headings)
- "Also Known As" rendered as inline tags

**Comparison view (triggered by "Compare with..."):**
- A search input appears at the top of the right panel
- User types and selects a second device from a dropdown of matches
- Panel splits into two equal columns, each showing one device
- Section labels are aligned: same section heading appears at the same vertical position in both columns when both devices have that section; sections present in only one device are shown in that column only
- "Exit comparison" button (top of either column) collapses back to single view

---

## Search

**Library:** Fuse.js (loaded from CDN, ~24KB)

**Indexed fields with weights:**
- `name` (weight: 1.0)
- `aliases` (weight: 0.9)
- `manufacturer_display` (weight: 0.6)
- `category` (weight: 0.5)
- Section content text (weight: 0.3)

**Behavior:**
- Search triggers on every keystroke with 150ms debounce
- Empty search shows all devices (or all in active browse filter)
- Search and browse filter compose: searching while a subcategory is active searches within that subcategory
- Minimum match threshold set to allow partial/fuzzy matches (Fuse.js `threshold: 0.4`)

---

## Libraries

All loaded from CDN (no local bundling required for prototype):
- **Fuse.js** v7 — client-side fuzzy search
- **marked.js** v12 — markdown to HTML rendering

No build toolchain (no npm, no webpack). The build script generates plain HTML/CSS/JS.

---

## File Layout

```
pipeline/
  build_site.py       ← new build script
site/                 ← generated output (add to .gitignore or commit)
  index.html
  catalog.json
```

The build script lives in `pipeline/` alongside the existing pipeline scripts. It does not modify any pipeline internals.

---

## Out of Scope (v1)

- Editing or updating knowledge files from the UI
- Authentication or access control
- Mobile layout optimization
- Hosting / deployment (local use only for prototype)
- Scraped-only devices (build script reads curated `--knowledge.md` files only)
- Printing or export
