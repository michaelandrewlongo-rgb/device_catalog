# PDF Extraction & Enrichment Pipeline - Design Spec

**Date:** 2026-03-30
**Goal:** Build a three-tier autonomous extraction pipeline that fills data gaps in device knowledge files using publicly available PDFs, FDA structured data APIs, and DeepSeek API, with staged checkpoints for human review.

**Constraint:** IFU PDFs are mostly HCP-gated. Pipeline is designed around public sources (FDA 510(k) summaries, brochures, technique guides, FDA UDI/MAUDE/Recall structured data, Endovascular Today device guide, NeuroSpine Product Review). IFUs are an optional enrichment layer when available.

**Key data sources by domain:**
- **Neurovascular/interventional:** EVToday Device Guide (301 devices, structured comparison tables)
- **Spine/cranial:** NeuroSpine Product Review (1,100+ devices, structured specs + hosted PDF brochures/technique guides)

**Out of scope:** Competitive comparison generation. That section remains manual-only.

---

## Architecture Overview

Four data source layers feed a three-tier extraction pipeline:

```
Sources:
  FDA 510(k) PDFs ──────────────┐
  Brochures / technique guides ──┤
  FDA UDI API (structured) ──────┤
  FDA MAUDE + Recalls API ───────┤──> Tier 1-2 extraction ──> Tier 3 enrichment ──> drafts
  EVToday Device Guide (web) ────┤
  NSPR (web + hosted PDFs) ──────┘
```

```
Tier 1 (deterministic):   FDA 510(k) PDFs + FDA APIs + EVToday + NSPR --> extracted/{source}/*.json
Tier 2 (Marker+DeepSeek): Brochures/technique guides (incl NSPR PDFs) --> extracted/documents/*.json
Tier 3 (DeepSeek):        Multi-source synthesis                       --> enriched/*.json
```

Each tier is a separate CLI command. Outputs are additive. You inspect between tiers.

## Directory Structure

```
pipeline/data/
  fda_raw/              # existing - FDA API JSON records
  scraper_raw/          # existing - Chrome/Python scraper JSON
  pdfs/                 # existing - downloaded 510(k) summary PDFs
  merged/               # existing - FDA + scraper merged JSON
  extracted/            # NEW
    fda_summaries/      # Tier 1A output (deterministic PDF)
    fda_structured/     # Tier 1B output (UDI API)
    fda_safety/         # Tier 1B output (MAUDE + Recalls)
    evtoday/            # Tier 1C output (device guide tables)
    nspr/               # Tier 1D output (NSPR structured specs + PDF URLs)
    documents/          # Tier 2 output (Marker + DeepSeek)
    skipped.json        # PDFs that failed extraction with reasons
  enriched/             # NEW - Tier 3 output (synthesis)
  drafts/               # existing - rendered markdown scaffolds
```

## Module Structure

```
pipeline/
  extraction/           # NEW package
    __init__.py
    fda_parser.py       # Tier 1A: Marker-based 510(k) PDF parser
    fda_structured.py   # Tier 1B: UDI, MAUDE, Recall API queries
    evtoday_scraper.py  # Tier 1C: Endovascular Today device guide scraper
    nspr_scraper.py     # Tier 1D: NeuroSpine Product Review scraper
    doc_extractor.py    # Tier 2: Marker + DeepSeek document extraction
    enricher.py         # Tier 3: multi-source synthesis
    deepseek.py         # DeepSeek API client (shared by Tier 2-3)
    pdf_utils.py        # Shared: Marker converter init, PDF validation
  run_extract.py        # NEW CLI entry point for Tiers 1-2
  run_enrich.py         # NEW CLI entry point for Tier 3
```

## CLI Commands

```bash
# New stages
python -m pipeline.run_extract --fda-summaries     # Tier 1A: PDFs only
python -m pipeline.run_extract --fda-structured     # Tier 1B: UDI + MAUDE + Recalls
python -m pipeline.run_extract --evtoday            # Tier 1C: EVToday device guide
python -m pipeline.run_extract --nspr               # Tier 1D: NSPR specs + PDF download
python -m pipeline.run_extract --documents          # Tier 2 only
python -m pipeline.run_extract --all                # All of the above
python -m pipeline.run_enrich                       # Tier 3

# Existing (modified to be enrichment-aware)
python -m pipeline.run_pipeline --merge-only        # Re-render drafts

# End-to-end
python -m pipeline.run_pipeline --extract --enrich  # New stages + regenerate
```

---

## Tier 1A: FDA 510(k) Summary Parser (Marker)

**File:** `pipeline/extraction/fda_parser.py`

**Input:** PDF files in `pipeline/data/pdfs/` named by K-number (e.g., `K201234.pdf`).

**Method:** Marker (`marker-pdf`) converts PDF to markdown, preserving table structure. Then regex-based section header matching extracts fields from the markdown output. Marker handles both text-based and scanned (OCR) PDFs.

**Marker configuration:**
- `output_format`: `"markdown"`
- `use_llm`: `False` for Tier 1 (FDA summaries are well-structured, tables are simple)
- `force_ocr`: `False` (auto-detect; Marker falls back to OCR when text extraction fails)

**Section-to-field mapping:**

| PDF Section | Target Field |
|---|---|
| Device Description | `what_it_is`, `sizing_specs` (if dimensions/tables present) |
| Indications for Use | `indications` |
| Contraindications | `contraindications` (when present) |
| Substantial Equivalence | `also_known_as` (predicate device names) |
| Materials/composition | `sizing_specs` (appended) |

**PDF-to-device matching:** Join on K-number. FDA downloader names files by clearance number. Merged records contain `clearance_number`.

**Output schema:**

```json
{
  "source_pdf": "K201234.pdf",
  "clearance_number": "K201234",
  "extraction_method": "marker_deterministic",
  "fields": {
    "what_it_is": "extracted text...",
    "indications": "extracted text...",
    "contraindications": "extracted text or null",
    "sizing_specs": "extracted markdown table or text...",
    "also_known_as": ["predicate device name"]
  },
  "confidence": {
    "what_it_is": 0.9,
    "indications": 0.95
  },
  "raw_sections": {
    "Device Description": "full markdown...",
    "Indications for Use": "full markdown..."
  }
}
```

**Confidence scoring:** Clean section header match = 0.9+. Positional inference = 0.5-0.8.

**Failure handling:**
- Corrupted PDFs (Marker raises exception): skip, log to `skipped.json`
- HTML-instead-of-PDF: detect via file header magic bytes, skip, log
- Empty extraction (< 50 chars output): skip, log

---

## Tier 1B: FDA Structured Data APIs

**File:** `pipeline/extraction/fda_structured.py`

Uses the existing `FDAClient` pattern (same base URL, pagination, rate limiting) to query three additional openFDA endpoints. No PDF parsing needed -- these return structured JSON.

### UDI Endpoint (`/device/udi.json`)

**Query:** Search by device brand name or product code: `?search=brand_name:"Tritanium"+AND+company_name:"Stryker"` or `?search=product_code:"MAX"`

**Fields extracted:**

| UDI Field | Target Field | Notes |
|---|---|---|
| `brand_name` | `also_known_as` | Append to existing aliases |
| `mri_safety` | `use_notes` | MR Safe / MR Conditional / MR Unsafe |
| `device_description` | `what_it_is` | Often more precise than website copy |
| `sterilization` | `use_notes` | Sterilization method (EtO, gamma, etc.) |
| `is_single_use` | `use_notes` | Single-use vs reusable |
| `is_rx` | (metadata) | Rx vs OTC |
| `gmdn_terms` | `also_known_as` | Standardized device nomenclature |
| `catalog_number`, `model_number` | `sizing_specs` | Part number references |

### MAUDE Endpoint (`/device/event.json`)

**Query:** Search by product code + brand name: `?search=product_code:"MAX"+AND+brand_name:"Solera"&count=event_type.exact`

**Fields extracted:**

| MAUDE Field | Target Field | Notes |
|---|---|---|
| Event type counts (injury/malfunction/death) | `_safety` | Aggregated counts, not individual narratives |
| Top device problem codes | `_safety` | Most common failure modes |
| Date range of events | `_safety` | Temporal context |

Output goes to `extracted/fda_safety/{device}.json`. Not mapped directly to ScrapedProduct fields -- instead, Tier 3 uses safety data to inform `contraindications` and `use_notes` enrichment.

### Recall Endpoint (`/device/recall.json`)

**Query:** Search by product code or firm name: `?search=product_code:"MAX"+AND+recalling_firm:"Medtronic"`

**Fields extracted:**

| Recall Field | Target Field | Notes |
|---|---|---|
| `reason_for_recall` | `_safety` | Why the recall happened |
| `product_description` | (cross-ref) | Confirm device match |
| `status` | `_safety` | Ongoing vs Terminated |
| `event_date_initiated` | `_safety` | Recency |

**Rate limiting:** All three endpoints share the openFDA rate limit (240 req/min without key). Use existing `FDAClient` throttling. Batch by product code for efficiency.

**Output schema (UDI):**

```json
{
  "device_name": "Solera Spinal System",
  "manufacturer": "medtronic",
  "extraction_method": "fda_udi_api",
  "fields": {
    "what_it_is": "device description from UDI...",
    "sizing_specs": "catalog numbers, model numbers...",
    "use_notes": "MR Conditional. EtO sterilized. Single-use.",
    "also_known_as": ["brand names", "GMDN terms"]
  },
  "confidence": {
    "what_it_is": 0.85,
    "use_notes": 0.95
  }
}
```

---

## Tier 1C: Endovascular Today Device Guide

**File:** `pipeline/extraction/evtoday_scraper.py`

**Source:** `https://evtoday.com/device-guide/us/` -- publicly accessible, no login required.

**What it provides:** Structured comparison tables for interventional devices. Each device category page is a DataTable with columns specific to the device type (e.g., materials, coil type, detachment method, FDA indication, comments). Covers cerebral coils, liquid embolics, intrasaccular devices, embolization coils, vascular plugs, and more.

**Relevant categories for this catalog:**

| EVToday Category | Catalog Category | URL slug |
|---|---|---|
| Cerebral Coils | `embolic-coil` | `cerebral-coils` |
| Liquid Embolics | `liquid-embolic` | `liquid-embolics` |
| Intrasaccular Flow Disruptor | `intrasaccular` | (under embolization) |
| Embolization Coils | `embolic-coil` | `embolization-coils` |
| Vascular Plugs | (new category) | `vascular-plugs` |

**Method:** HTTP fetch + HTML table parsing. Each category page renders a `<table>` inside a DataTable widget. Parse with `BeautifulSoup` or `lxml`. No JavaScript rendering needed -- table data is in the initial HTML response.

**Field mapping (varies by category, common pattern):**

| EVToday Column | Target Field |
|---|---|
| Company Name | `manufacturer` (cross-reference) |
| Product Name | `device_name` (cross-reference) |
| Materials Used | `sizing_specs` (materials section) |
| US FDA Indicated Use | `indications` |
| Comments | `what_it_is` or `use_notes` (device-specific details) |
| Coil Type / Device Type | `what_it_is` (append) |
| Method of Detachment | `use_notes` (append) |
| Sizes / Configurations | `sizing_specs` |

**Device matching:** Match EVToday entries to existing catalog devices by manufacturer + product name fuzzy match (same word-overlap approach as merger.py). Unmatched EVToday entries are logged as potential new devices to investigate.

**Output schema:**

```json
{
  "source": "evtoday",
  "source_url": "https://evtoday.com/device-guide/us/cerebral-coils",
  "device_name": "HydroFill Coils",
  "manufacturer": "terumo-neuro",
  "extraction_method": "evtoday_table",
  "fields": {
    "what_it_is": "Hydrogel core expands diameter of coil by 20% for efficient filling",
    "sizing_specs": "Materials: Hydrogel thread placed inside platinum coil",
    "indications": "Aneurysm, AVM, AVF, and peripheral vasculature embolization",
    "use_notes": "V-Grip controller with 0.75-second detachment"
  },
  "confidence": {
    "what_it_is": 0.8,
    "indications": 0.85
  },
  "evtoday_raw": {
    "Company Name": "Terumo Neuro",
    "Product Name": "HydroFill Coils",
    "Materials Used": "Hydrogel thread placed inside platinum coil",
    "Coil Type": "HydroCoil Embolic System, helical shape, for filling",
    "Method of Detachment": "V-Grip controller with 0.75-second detachment",
    "US FDA Indicated Use": "Aneurysm, AVM, AVF, and peripheral vasculature embolization",
    "Comments": "Hydrogel core expands diameter of coil by 20%"
  }
}
```

**Output directory:** `extracted/evtoday/{category-slug}.json` (one file per category, containing array of all devices in that category).

**Rate limiting:** 3-second delay between category page fetches. Respect robots.txt.

**Failure handling:** 500 errors on some category pages are known (observed during research). Skip and log. Retry once after 10s.

---

## Tier 2: Document Extraction via Marker + DeepSeek

**File:** `pipeline/extraction/doc_extractor.py`

**Input:** Non-FDA PDFs from two sources:
- Catalog root: `{category}--{manufacturer}--{product}--{doc-type}.pdf`
- Scraper-discovered URLs: `ifu_pdf_url` and `other_pdf_urls` from scraper_raw JSON

**PDF acquisition:** New utility `download_discovered_pdfs()` reads all scraper_raw JSON, collects PDF URLs, downloads to `pipeline/data/pdfs/{manufacturer}/`, skips already-downloaded.

**PDF-to-device matching:**
- Catalog root: filename stem maps directly to device
- Scraper URLs: parent scraper JSON contains the device name

**Method:** Two-pass extraction:

1. **Pass 1 (Marker):** Convert PDF to markdown with `use_llm=True`. This activates Marker's LLM table processor for complex sizing/spec tables. LLM backend: DeepSeek via OpenAI-compatible endpoint.

   Marker LLM config:
   ```python
   {
       "use_llm": True,
       "llm_service": "marker.services.openai.OpenAIService",
       "openai_api_key": DEEPSEEK_API_KEY,
       "openai_base_url": "https://api.deepseek.com/v1",
       "openai_model": "deepseek-chat",
       "output_format": "markdown"
   }
   ```

2. **Pass 2 (DeepSeek):** Send the Marker markdown output to DeepSeek for structured field extraction.

**DeepSeek extraction prompt:**

```
You are extracting structured medical device data from a manufacturer document
that has been converted to markdown.

Extract ONLY what is explicitly stated. Do not infer or add information.
Return null for any field not found in the document.
For sizing_specs, preserve any markdown tables exactly as they appear.

Target fields:
- what_it_is: Device description, mechanism, materials
- sizing_specs: Dimensions, sizes, configurations, materials table
- indications: Approved/intended clinical uses
- contraindications: Conditions where device should not be used
- compatible_with: Compatible devices, instruments, accessories
- use_notes: Clinical or procedural details, deployment steps
- also_known_as: Alternate names, abbreviations, legacy names

Document type: {brochure|technique|ifu}
Device: {device_name} by {manufacturer}

Respond in JSON matching the field names above.
```

**Cost controls:**
- Marker's LLM mode only fires on detected tables and complex blocks, not entire documents
- DeepSeek extraction uses the markdown output (smaller than raw PDF text)
- Truncate markdown to 15,000 tokens before sending to DeepSeek
- Use `deepseek-chat` (cheapest model)
- 1-second delay between API calls
- Batch by manufacturer for easy partial reruns

**Output schema:** Same structure as Tier 1 with `"extraction_method": "marker_deepseek"` and confidence 0.6-0.8.

---

## Tier 3: Enrichment Synthesis

**File:** `pipeline/extraction/enricher.py`

**Input per device:** Up to seven sources:
1. Merged record (`merged/*.json`)
2. Tier 1A extraction (`extracted/fda_summaries/*.json`) -- matched by K-number
3. Tier 1B UDI data (`extracted/fda_structured/*.json`) -- matched by device name + manufacturer
4. Tier 1B safety data (`extracted/fda_safety/*.json`) -- MAUDE + Recalls
5. Tier 1C EVToday data (`extracted/evtoday/*.json`) -- matched by manufacturer + product name
6. Tier 2 extraction (`extracted/documents/*.json`) -- matched by device
7. Existing curated knowledge file (catalog root `--knowledge.md`)

**Decision tree per field:**

```
curated content exists?                    --> keep, skip
Tier 1A data at 0.9+ confidence?          --> use, skip
Tier 1B UDI data at 0.85+ confidence?     --> use, skip
Tier 1C EVToday data at 0.8+ confidence?  --> use, skip
Tier 2 data at 0.6+ confidence?           --> use, skip
scraper data exists?                       --> use, skip
multiple low-confidence sources?           --> DeepSeek reconciliation
still empty?                               --> DeepSeek synthesis from all context
nothing available at all?                  --> [NEEDS CONTENT]
```

**Safety data integration:** MAUDE and recall data does not map directly to a ScrapedProduct field. Instead, Tier 3 uses it as context:
- If a device has active recalls, add a note to `use_notes`
- If MAUDE shows high adverse event counts for specific failure modes, mention in `contraindications` or `use_notes`
- Safety data is always tagged `[FDA MAUDE]` or `[FDA RECALL]` for traceability

**DeepSeek reconciliation prompt (only when needed):**

```
You are reconciling medical device data from multiple sources.
Do NOT invent information. If sources conflict, prefer the more specific/regulatory source.
If no source provides the information, return null.

Device: {device_name} by {manufacturer}
Field needed: {field_name}

Source 1 (FDA 510k summary): {text or "not available"}
Source 2 (FDA UDI database): {text or "not available"}
Source 3 (EVToday device guide): {text or "not available"}
Source 4 (manufacturer document): {text or "not available"}
Source 5 (manufacturer website): {text or "not available"}
Source 6 (FDA safety data): {text or "not available"}

Return the best value for this field, or null if insufficient data.
```

**Output schema:** Same as MergedDeviceRecord with added `_enrichment` metadata:

```json
{
  "indications": "FDA-approved indication text...",
  "use_notes": "MR Conditional at 3T. EtO sterilized. [FDA MAUDE] 12 malfunction reports 2020-2025, most common: screw loosening.",
  "_enrichment": {
    "indications": {"source": "fda_summary", "confidence": 0.95},
    "sizing_specs": {"source": "marker_deepseek", "confidence": 0.7},
    "use_notes": {"source": "fda_udi_api+fda_maude", "confidence": 0.85},
    "contraindications": {"source": "none", "confidence": 0}
  }
}
```

**Cost profile:** Most fields filled by Tier 1A/1B without DeepSeek calls. Tier 2 uses DeepSeek for table extraction and field mapping. Tier 3 only fires DeepSeek for remaining gaps. Estimate per device: 0-1 Tier 3 API calls (~$0.01), 1 Tier 2 call per PDF (~$0.02). Total for 40 spine devices: ~$1-2.

---

## Shared: PDF Utilities

**File:** `pipeline/extraction/pdf_utils.py`

Shared Marker converter initialization and PDF validation:

```python
def create_marker_converter(use_llm: bool = False) -> PdfConverter:
    """Initialize Marker with optional DeepSeek LLM backend."""

def validate_pdf(path: Path) -> str | None:
    """Return None if valid PDF, or error reason string."""
    # Check magic bytes (not HTML, not empty)
    # Check file size (> 1KB, < 100MB)

def pdf_to_markdown(path: Path, use_llm: bool = False) -> str | None:
    """Convert PDF to markdown via Marker. Returns None on failure."""
```

Marker model artifacts are loaded once and reused across all PDFs in a batch run (the `create_model_dict()` call is expensive, ~10s).

---

## DeepSeek Client

**File:** `pipeline/extraction/deepseek.py`

Lightweight OpenAI-compatible client using `httpx`. Shared by Tier 2 and Tier 3.

```python
def deepseek_extract(prompt: str, max_tokens: int = 4096) -> dict | None:
    """Send prompt to DeepSeek, parse JSON response. Returns None on failure."""
    # POST to https://api.deepseek.com/v1/chat/completions
    # Model: deepseek-chat
    # Retry 3x with exponential backoff (1s, 4s, 16s)
    # Timeout: 60s
    # Parse JSON from response (strip markdown fences if present)
```

API key loaded from `~/Desktop/master_env.txt` via `config.py`.

---

## Integration with Existing Pipeline

**Changes to existing code:**

- `config.py`: Add `DEEPSEEK_API_KEY` (loaded from `~/Desktop/master_env.txt`), `EXTRACTED_DIR`, `ENRICHED_DIR` path constants. Respect `PYTHONUTF8=1` for Windows Rich console output.
- `fda/client.py`: Add methods for UDI, MAUDE, and Recall queries. Same `_search()` pattern as existing 510(k)/PMA queries.
- `processing/template.py`: `generate_drafts()` prefers enriched records over merged records. If `enriched/{device}.json` exists, use it; else fall back to `merged/{device}.json`. No schema changes.
- `run_pipeline.py`: Add `--extract` and `--enrich` flags. Existing flags unchanged.

**New dependencies:**
- `marker-pdf` -- PDF to markdown conversion (includes PyTorch, OCR models)
- No new SDK for DeepSeek -- OpenAI-compatible API via `httpx`

**Install:**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121  # CUDA torch first
pip install marker-pdf
# or for CPU-only:
pip install torch
pip install marker-pdf
```

---

## Error Handling

**PDF failures:** Corrupted or HTML-instead-of-PDF files are skipped and logged to `extracted/skipped.json`. Marker handles scanned PDFs via OCR automatically.

**DeepSeek API:** Retry 3x with exponential backoff (1s, 4s, 16s). Malformed JSON: attempt lenient parsing (strip markdown fences). Timeout: 60s per call. All failures logged, device skipped.

**FDA API failures:** Use existing `FDAClient` retry logic. UDI queries that return no results are normal (not all devices are in GUDID). Log and continue.

**Data integrity:**
- Enriched records never overwrite curated knowledge files. Template renderer skips devices that already have a `--knowledge.md` in catalog root.
- Regulatory fields (K-numbers, clearance data) pass through from FDA source only, never fabricated.
- All DeepSeek-sourced fields tagged confidence < 0.8 for review manifest flagging.
- Safety data (MAUDE/recalls) always tagged with source for traceability.

**Idempotency:** Re-running any tier overwrites its own output only. Safe to run partially and resume.

---

## Full Pipeline Sequence

```
1. python -m pipeline.run_fda --codes ... --download-pdfs    # FDA discovery + PDF download
2. python -m pipeline.run_scrapers / Chrome MCP sessions      # Manufacturer website data
3. python -m pipeline.run_pipeline --merge-only               # Merge FDA + scraper data
4. python -m pipeline.run_extract --fda-summaries             # Tier 1A: parse 510(k) PDFs
5. python -m pipeline.run_extract --fda-structured            # Tier 1B: UDI + MAUDE + Recalls
6. python -m pipeline.run_extract --evtoday                   # Tier 1C: EVToday device guide
7. python -m pipeline.run_extract --documents                 # Tier 2: brochure/technique extraction
8. python -m pipeline.run_enrich                              # Tier 3: multi-source synthesis
9. python -m pipeline.run_pipeline --merge-only               # Regenerate drafts from enriched data
10. Review drafts/, promote approved files to catalog root
```
