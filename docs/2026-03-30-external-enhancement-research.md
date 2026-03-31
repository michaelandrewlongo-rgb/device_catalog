# Device Catalog: Repository Understanding & External Enhancement Opportunities

## What This Repo Is

A flat-file knowledge catalog of neurosurgical, spine, and neurointerventional medical devices. Each device gets a markdown knowledge file (clinically actionable, 100-300+ lines) paired with source PDFs (IFUs, 510(k) summaries, technique guides). A Python pipeline discovers new devices via FDA APIs, scrapes manufacturer websites, merges the data, and generates draft knowledge files for human curation.

**Current scale:** 68 curated knowledge files across 25 device categories and 17 manufacturers, plus ~120 scraped-only devices awaiting promotion. 188 total devices indexed.

**Two clinical domains:** Spine (pedicle screws, cages, plates, corpectomy, navigation, SI fusion) and Neurovascular/Interventional (flow diverters, stent retrievers, aspiration, coils, liquid embolics, microcatheters, intracranial stents, shunts, thrombectomy).

---

## Current Data Sources

| Source | What It Provides | Integration |
|---|---|---|
| openFDA 510(k) API | Clearance numbers, dates, applicant, product codes, PDF URLs | `pipeline/fda/scraper_510k.py` |
| openFDA PMA API | Class III approvals (Pipeline Flex, FRED, WEB, LVIS, Surpass) | `pipeline/fda/scraper_pma.py` |
| 7 manufacturer web scrapers | Device specs, sizing, indications, IFU URLs | `pipeline/scrapers/*.py` |
| Chrome MCP sessions | Bot-protected sites (Medtronic, Cerenovus) | `pipeline/scrapers/chrome_workflow.md` |
| Manual IFU PDF curation | Deep clinical content (procedures, troubleshooting, competitive comparisons) | Human-authored knowledge files |

---

## Coverage Gaps

**Under-covered categories:** Aspiration (10 devices, 0 curated), embolic coils (19 devices, 2 curated), distal-access (21 devices, 4 curated), guidewires (6 devices, 0 curated).

**Missing categories entirely:** Aneurysm clips, intrathecal pumps, cranial neuromonitoring, ventriculostomy/EVD systems.

**Manufacturer gaps:** Balt (21 scraped, 0 curated), Penumbra (11 scraped, 1 curated), NuVasive/Globus (spine, minimal), Zimmer Biomet (absent), Boston Scientific (absent), Rapid Medical (absent), Phenox (absent).

**Content gaps:** ~70 devices have no paired source PDFs. Tabbed/accordion content on manufacturer sites missed by Python scrapers. HCP-gated IFU PDFs inaccessible.

---

## External Resources That Could Meaningfully Improve the Catalog

### 1. FDA API Endpoints (Already Have the Client Pattern)

`FDAClient` in `pipeline/fda/client.py` already handles openFDA pagination, rate limiting, and retries. These endpoints use the identical API pattern:

| Endpoint | URL | What It Adds |
|---|---|---|
| **MAUDE (Adverse Events)** | `/device/event.json` | Safety signals per device -- event counts, injury/malfunction/death reports, manufacturer narratives. Could populate a "Post-Market Safety" section. |
| **Recalls** | `/device/recall.json` | Active/resolved recalls per product code. Critical safety context for clinical users. |
| **Enforcement** | `/device/enforcement.json` | FDA enforcement actions (2004-present, weekly updates). |
| **UDI (GUDID)** | `/device/udi.json` | Brand names, GMDN terms, device sizes/characteristics, MRI safety status, sterilization method, single-use labeling. Fills sizing gaps without scraping. |
| **Classification** | `/device/classification.json` | Programmatic product code lookup. Replace hardcoded `PRODUCT_CODE_MAP` with live data. |
| **Registration & Listing** | `/device/registrationlisting.json` | Which facilities manufacture which devices. Competitive intelligence. |

**Effort:** Low. Same `search=field:term` syntax, same JSON response format, same rate limits (240 req/min, no key needed).

### 2. AccessGUDID (NIH/NLM) -- Device Characteristics Database

**API:** `https://accessgudid.nlm.nih.gov/api/v2/`

Three REST APIs (JSON responses, no auth):
- Device Lookup API -- query by Device Identifier (DI) or record key
- Device History API -- change tracking
- Parse UDI API -- barcode decomposition

**Bulk downloads** (CSV/pipe-delimited, daily updates) at `https://accessgudid.nlm.nih.gov/download`, including an implant-specific subset.

**What it adds that you don't have:** Brand names, GMDN standardized terms, company contacts, device sizes/characteristics as structured data, MRI safety classification, latex content, sterilization methods. Highly complementary to 510(k)/PMA regulatory metadata.

### 3. GitHub Repositories

| Repo | What It Provides | Relevance |
|---|---|---|
| **[interestng/medkit](https://github.com/interestng/medkit)** | Unified Python SDK wrapping OpenFDA + PubMed + ClinicalTrials.gov. Pydantic V2, connection pooling, rate limiting, clinical synthesis with evidence scoring. `pip install medkit-sdk` | Could replace custom `FDAClient` and add PubMed + ClinicalTrials.gov in one dependency. |
| **[wcedmisten/510k.fyi](https://github.com/wcedmisten/510k.fyi)** | Predicate device dependency graph visualization. Live at 510k.fyi. | Understand predicate ancestry of catalog devices. See which clearances a device was built on. |
| **[tsbischof/fda](https://github.com/tsbischof/fda)** | Recursive predicate device tracer. Parses 510(k) PDFs (including OCR) to find predicate references. | Enrich knowledge files with predicate lineage. |
| **[calebho/medical-devices](https://github.com/calebho/medical-devices)** | Lightweight Python library for downloading from multiple FDA databases. | Reference implementation for additional FDA endpoint integration. |
| **[FDA/openfda](https://github.com/FDA/openfda)** | Official FDA repo. Python/Luigi pipelines for processing all public FDA datasets. Includes MAUDE pipeline reference. | Architecture reference for building MAUDE/recall integration. |
| **[rlwadh/fda-predicate-finder](https://github.com/rlwadh/fda-predicate-finder)** | Free tool for searching 510(k) clearances and finding predicate devices. | Cross-reference tool for catalog enrichment. |

### 4. PDF-to-Markdown Extraction (IFU Automation)

Currently IFU PDFs are manually read and distilled into knowledge files. These tools could semi-automate extraction:

| Tool | Install | Why It Fits |
|---|---|---|
| **[Marker](https://github.com/datalab-to/marker)** | `pip install marker-pdf` | Outputs Markdown directly (matches knowledge file format). `--use_llm` flag handles complex sizing/spec tables. Handles both text-based and scanned PDFs. 10x faster than Nougat. Chandra OCR model surpasses GPT-4o on table accuracy. |
| **[Docling](https://github.com/docling-project/docling)** | `pip install docling` | IBM Research project. 97.9% accuracy on complex tables. Multiple output formats. LangChain/LlamaIndex integration. |
| **[pdfplumber](https://github.com/jsvine/pdfplumber)** | `pip install pdfplumber` | Lightweight, excellent for targeted table extraction from text-based PDFs. Good for sizing/spec tables specifically. |

**Best fit:** Marker for full IFU-to-markdown conversion. pdfplumber for targeted table extraction when you only need sizing data.

### 5. Clinical Evidence Integration

| Source | Access | What It Adds |
|---|---|---|
| **ClinicalTrials.gov** | Free API v2, no auth. Also available via `mcp__claude_ai_Clinical_Trials__search_trials` MCP tool. Python: `pip install pytrials`. | Active/completed trials per device, enrollment, endpoints, results. "Clinical Evidence" sections. |
| **PubMed** | Free Entrez API (3 req/sec, 10 with key). Also via `mcp__claude_ai_PubMed__search_articles` MCP tool. Python: `biopython` or `entrezpy`. | Peer-reviewed efficacy studies, comparative analyses, case series. Evidence base for each device. |
| **bioRxiv/medRxiv** | Free API. Also via `mcp__claude_ai_bioRxiv__search_preprints` MCP tool. | Pre-publication research on newer devices. |

### 6. Competitive Intelligence & Reference Sources

| Source | URL | What It Adds |
|---|---|---|
| **Endovascular Today Device Guide** | `evtoday.com/device-guide/us` | Searchable US/EU device listings with specs, configurations, manufacturer comparisons. Cross-reference for completeness. |
| **FDA TPLC Database** | `accessdata.fda.gov/scripts/cdrh/cfdocs/cfTPLC/tplc.cfm` | Unified lifecycle view per product code (classification + PMA + 510(k) + MAUDE + recalls). Also on data.gov via Socrata API. |
| **ICD-10-PCS** | Available via `mcp__claude_ai_ICD-10_Codes__search_codes` MCP tool. | Link devices to procedure codes. Map flow diverters to intracranial vessel procedure codes, etc. |

### 7. Specialty Society Guidelines (Free via PubMed/PMC)

| Society | Coverage |
|---|---|
| **SNIS** (Society of NeuroInterventional Surgery, formerly ASITN) | Neurointerventional practice standards. `snisonline.org/standards/` |
| **ASNR** (American Society of Neuroradiology) | Practice guidelines for cervicocerebral procedures. `asnr.org/practice-guidelines/` |
| **AANS/CNS** Cerebrovascular Section | Stroke management, carotid/vertebral disease guidelines. `cvsection.org/education/` |
| **AHA/ASA** | Acute ischemic stroke management guidelines (directly relevant to thrombectomy devices). Published in Circulation/Stroke journals. |

Most guidelines are open-access journal articles discoverable via PubMed MCP tools.

### 8. MCP Tools Already Available (Zero Integration Effort)

These MCP servers are already connected. They require no code changes -- just invoke during Chrome sessions or knowledge file authoring:

- `mcp__claude_ai_Clinical_Trials__*` -- Search device trials, analyze endpoints, find investigators
- `mcp__claude_ai_PubMed__*` -- Search articles, get full text, find related articles
- `mcp__claude_ai_bioRxiv__*` -- Search preprints, get details
- `mcp__claude_ai_ICD-10_Codes__*` -- Link devices to procedure codes
- `mcp__claude_ai_ChEMBL__*` -- Drug/compound data (relevant for anticoagulation protocol sections)

---

## Prioritized Enhancement Roadmap

### Tier 1: High Value, Low Effort (extend existing patterns)

1. **Add GUDID/UDI queries to FDAClient** -- Same API pattern. Fills sizing, MRI safety, sterilization data without scraping manufacturer sites.
2. **Add MAUDE adverse event queries** -- Same API pattern. Safety signal counts per device.
3. **Add Recall/Enforcement queries** -- Same API pattern. Critical safety context.
4. **Use MCP tools during knowledge file authoring** -- PubMed + ClinicalTrials.gov searches during curation sessions. Zero code.

### Tier 2: High Value, Moderate Effort (new integrations)

5. **Install Marker for IFU PDF extraction** -- Semi-automate the most time-consuming step (manual PDF reading).
6. **Evaluate medkit-sdk** -- Could unify FDA + PubMed + ClinicalTrials.gov under one SDK, replacing custom client code.
7. **Integrate AccessGUDID bulk download** -- Structured device characteristics for entire catalog at once.

### Tier 3: Strategic Value, Higher Effort

8. **Build predicate device graph** (inspired by 510k.fyi) -- Visualize clearance ancestry.
9. **Scrape Endovascular Today Device Guide** -- Cross-reference for completeness gaps.
10. **Build TPLC aggregator** -- Combine all FDA endpoints per product code into unified lifecycle view.
