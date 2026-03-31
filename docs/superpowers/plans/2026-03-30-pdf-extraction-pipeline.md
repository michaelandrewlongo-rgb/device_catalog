# PDF Extraction & Enrichment Pipeline - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a harvest-first extraction pipeline that fills device knowledge file gaps using two major structured sources (EVToday for neurovascular, NSPR for spine/cranial), supplemented by FDA APIs and LLM-assisted PDF extraction.

**Architecture:** Phase 1 harvests structured data from EVToday and NSPR (covers ~1,400 devices, fills 70-80% of gaps). Phase 2 downloads and extracts NSPR-hosted PDFs plus FDA 510(k) summaries. Phase 3 uses DeepSeek to synthesize remaining gaps. Each phase writes to its own directory with checkpoints.

**Tech Stack:** Python 3.11+, httpx, marker-pdf (Phase 2), DeepSeek API (Phase 3), Chrome DevTools tools (NSPR auth), existing pipeline modules

**Spec:** `docs/superpowers/specs/2026-03-30-pdf-extraction-pipeline-design.md`

---

## File Map

**Phase 1 (Harvest):**
- Create: `pipeline/extraction/__init__.py`
- Create: `pipeline/extraction/evtoday_scraper.py` -- EVToday table scraper (done, needs module packaging)
- Create: `pipeline/extraction/nspr_scraper.py` -- NSPR listing + detail page scraper
- Create: `pipeline/extraction/nspr_chrome.py` -- Chrome DevTools helper for authenticated NSPR scraping
- Create: `pipeline/extraction/fda_structured.py` -- FDA UDI/MAUDE/Recall API queries

**Phase 2 (Extract):**
- Create: `pipeline/extraction/pdf_utils.py` -- Marker wrapper, PDF validation
- Create: `pipeline/extraction/fda_parser.py` -- FDA 510(k) PDF parser
- Create: `pipeline/extraction/doc_extractor.py` -- Brochure/technique guide extractor
- Create: `pipeline/extraction/deepseek.py` -- DeepSeek API client

**Phase 3 (Enrich):**
- Create: `pipeline/extraction/enricher.py` -- Multi-source synthesis

**Integration:**
- Create: `pipeline/run_extract.py` -- CLI entry point
- Create: `pipeline/run_enrich.py` -- CLI entry point
- Modify: `pipeline/config.py` -- new paths, API keys
- Modify: `pipeline/processing/template.py` -- prefer enriched records
- Modify: `pipeline/run_pipeline.py` -- new flags
- Modify: `requirements.txt` -- marker-pdf

---

### Task 1: Config and Dependencies

**Files:**
- Modify: `pipeline/config.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add new path constants and API key to config.py**

Add after the `DATA_DIR` line:

```python
EXTRACTED_DIR = DATA_DIR / "extracted"
ENRICHED_DIR = DATA_DIR / "enriched"

def _load_env_key(filename: str, key: str) -> str | None:
    """Load a key from a simple KEY=VALUE env file."""
    path = Path.home() / "Desktop" / filename
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None

DEEPSEEK_API_KEY: str | None = _load_env_key("master_env.txt", "DEEPSEEK_API_KEY")
```

- [ ] **Step 2: Add marker-pdf to requirements.txt**

Append:
```
marker-pdf>=1.0
```

- [ ] **Step 3: Create extraction package init**

Create `pipeline/extraction/__init__.py`:
```python
"""Extraction pipeline: harvest structured data, parse PDFs, enrich via LLM."""
```

- [ ] **Step 4: Verify config loads**

```bash
PYTHONUTF8=1 python -c "from pipeline.config import EXTRACTED_DIR, ENRICHED_DIR, DEEPSEEK_API_KEY; print(f'EXTRACTED: {EXTRACTED_DIR}'); print(f'ENRICHED: {ENRICHED_DIR}'); print(f'KEY: {DEEPSEEK_API_KEY[:8]}...' if DEEPSEEK_API_KEY else 'KEY: None')"
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/config.py requirements.txt pipeline/extraction/__init__.py
git commit -m "feat: add extraction pipeline config (paths, DeepSeek key, marker-pdf dep)"
```

---

### Task 2: EVToday Scraper Module

EVToday data is already scraped and saved to `pipeline/data/extracted/evtoday/`. This task packages the scraper as a reusable module.

**Files:**
- Create: `pipeline/extraction/evtoday_scraper.py`

- [ ] **Step 1: Create evtoday_scraper.py**

```python
"""Tier 1C: Endovascular Today Device Guide scraper.

Scrapes structured comparison tables from evtoday.com/device-guide/us/.
Public, no auth required. Rate-limited to 3s between requests.
"""

from __future__ import annotations

import json
import logging
import time
from html.parser import HTMLParser
from pathlib import Path

import httpx

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "evtoday"
BASE_URL = "https://evtoday.com/device-guide/us"
REQUEST_DELAY = 3

CATEGORIES = {
    "cerebral-coils": "embolic-coil",
    "neurovascular-liquid-embolics": "liquid-embolic",
    "flow-diverters": "flow-diverter",
    "cerebral-stents": "intracranial-stent",
    "mechanical-thrombectomythrombolysis-neurovascular": "thrombectomy",
    "thrombus-aspiration-devices": "aspiration",
    "microcatheters-4": "microcatheter",
    "specialty-balloons-neuro": "balloon-catheter",
    "intrasaccular-flow-disruptor-1": "intrasaccular",
    "guiding-catheters": "guiding-catheter",
}


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_thead = False
        self.in_tbody = False
        self.in_th = False
        self.in_td = False
        self.headers: list[str] = []
        self.rows: list[list[str]] = []
        self.current_row: list[str] = []
        self.current_cell = ""

    def handle_starttag(self, tag, attrs):
        if tag == "thead": self.in_thead = True
        elif tag == "tbody": self.in_tbody = True
        elif tag == "th": self.in_th = True; self.current_cell = ""
        elif tag == "td": self.in_td = True; self.current_cell = ""
        elif tag == "tr" and self.in_tbody: self.current_row = []

    def handle_endtag(self, tag):
        if tag == "thead": self.in_thead = False
        elif tag == "tbody": self.in_tbody = False
        elif tag == "th": self.in_th = False; self.headers.append(self.current_cell.strip())
        elif tag == "td": self.in_td = False; self.current_row.append(self.current_cell.strip())
        elif tag == "tr" and self.in_tbody and self.current_row: self.rows.append(self.current_row)

    def handle_data(self, data):
        if self.in_th or self.in_td: self.current_cell += data


def scrape_category(slug: str, category: str) -> dict | None:
    url = f"{BASE_URL}/{slug}"
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        if resp.url.path.rstrip("/").endswith("/us"):
            return None
    except httpx.HTTPError:
        return None

    parser = _TableParser()
    parser.feed(resp.text)
    if not parser.rows:
        return None

    devices = []
    for row in parser.rows:
        entry = {}
        for i, header in enumerate(parser.headers):
            if i < len(row): entry[header] = row[i]
        devices.append(entry)

    return {"category": category, "source_url": url, "headers": parser.headers, "devices": devices}


def scrape_all_categories() -> dict[str, int]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    counts = {}
    for slug, category in CATEGORIES.items():
        logger.info("  EVToday: %s", slug)
        data = scrape_category(slug, category)
        if data is None:
            counts[slug] = 0
            continue
        (OUTPUT_DIR / f"{slug}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        counts[slug] = len(data["devices"])
        time.sleep(REQUEST_DELAY)
    logger.info("EVToday: %d devices total", sum(counts.values()))
    return counts
```

- [ ] **Step 2: Verify existing data loads**

```bash
PYTHONUTF8=1 python -c "
from pathlib import Path; import json
d = Path('pipeline/data/extracted/evtoday')
total = sum(len(json.loads(f.read_text(encoding='utf-8'))['devices']) for f in d.glob('*.json'))
print(f'EVToday: {total} devices already scraped')
"
```

Expected: `EVToday: 301 devices already scraped`

- [ ] **Step 3: Commit**

```bash
git add pipeline/extraction/evtoday_scraper.py
git commit -m "feat: add EVToday device guide scraper module"
```

---

### Task 3: NSPR Chrome-Assisted Scraper

NSPR requires authentication (session cookie). We scrape via Chrome DevTools for the initial data harvest, then save structured JSON to `extracted/nspr/`. This module provides helpers that the agent calls during Chrome DevTools sessions, similar to `chrome_assisted.py` for manufacturer scrapers.

**Files:**
- Create: `pipeline/extraction/nspr_scraper.py`

- [ ] **Step 1: Create nspr_scraper.py**

```python
"""NSPR (NeuroSpine Product Review) scraper.

Chrome DevTools-assisted scraper for neurospineproductreview.com.
Requires authenticated browser session. Provides:
- save_nspr_listing(): save product cards from a category listing page
- save_nspr_detail(): save full product detail data
- save_nspr_pdf_index(): save discovered PDF URLs for later download
- print_nspr_status(): show scraping progress

Data saved to extracted/nspr/{category}/ and extracted/nspr/pdfs_index.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from slugify import slugify

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "nspr"

# NSPR categories that map to our catalog categories
NSPR_CATEGORIES = {
    "screws": "pedicle-screw",
    "intervertebral-cages": "interbody-cage",
    "plates": "cervical-plate",
    "corpectomy-cage": "corpectomy",
    "si-joint": "sacroiliac-fusion",
    "disc-replacement-artificial-disc": "cervical-disc",
    "csf-management": "csf-shunt",
    "laminoplasty": "laminoplasty",
    "neurovascular-devices": "neurovascular",
}


def save_nspr_listing(category_slug: str, products: list[dict]) -> str:
    """Save product listing data from a category page.

    Args:
        category_slug: NSPR URL slug (e.g., 'screws', 'intervertebral-cages')
        products: List of dicts with keys: name, company, tags, description, slug, href

    Returns:
        Path to saved file.
    """
    cat_dir = OUTPUT_DIR / category_slug
    cat_dir.mkdir(parents=True, exist_ok=True)

    catalog_category = NSPR_CATEGORIES.get(category_slug, "unknown")

    out = {
        "source": "nspr",
        "nspr_category": category_slug,
        "catalog_category": catalog_category,
        "source_url": f"https://neurospineproductreview.com/browse-products/{category_slug}",
        "products": products,
    }

    path = cat_dir / "_listing.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def save_nspr_detail(product_slug: str, data: dict) -> str:
    """Save product detail page data.

    Args:
        product_slug: NSPR URL slug for the product
        data: Dict with keys: name, company, specs (dict), description,
              features (list), pdfs (list of URLs), mfr_link, nspr_url

    Returns:
        Path to saved file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = slugify(product_slug, separator="-") + ".json"

    out = {
        "source": "nspr",
        "nspr_url": data.get("nspr_url", f"https://neurospineproductreview.com/{product_slug}"),
        "device_name": data.get("name", ""),
        "manufacturer": data.get("company", ""),
        "specs": data.get("specs", {}),
        "description": data.get("description", ""),
        "features": data.get("features", []),
        "pdfs": data.get("pdfs", []),
        "mfr_link": data.get("mfr_link", ""),
    }

    path = OUTPUT_DIR / fname
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also index PDFs for batch download
    if out["pdfs"]:
        _append_pdf_index(out["device_name"], out["manufacturer"], out["pdfs"])

    return str(path)


def _append_pdf_index(device_name: str, manufacturer: str, pdf_urls: list[str]) -> None:
    """Append to the master PDF index for batch downloading."""
    index_path = OUTPUT_DIR / "pdfs_index.json"
    index = []
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    existing_urls = {e["url"] for e in index}
    for url in pdf_urls:
        if url not in existing_urls:
            index.append({
                "device_name": device_name,
                "manufacturer": manufacturer,
                "url": url,
                "filename": url.split("/")[-1],
                "downloaded": False,
            })

    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def download_nspr_pdfs() -> int:
    """Download all PDFs from the NSPR index that haven't been downloaded yet.

    Returns number of PDFs downloaded.
    """
    import time
    import httpx

    index_path = OUTPUT_DIR / "pdfs_index.json"
    if not index_path.exists():
        logger.warning("No NSPR PDF index found")
        return 0

    index = json.loads(index_path.read_text(encoding="utf-8"))
    pdf_dir = OUTPUT_DIR / "pdfs"
    pdf_dir.mkdir(exist_ok=True)

    downloaded = 0
    for entry in index:
        if entry.get("downloaded"):
            continue

        fname = entry["filename"]
        dest = pdf_dir / fname
        if dest.exists():
            entry["downloaded"] = True
            continue

        logger.info("  Downloading: %s", fname)
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(entry["url"])
            if resp.status_code == 200 and len(resp.content) > 1024:
                dest.write_bytes(resp.content)
                entry["downloaded"] = True
                downloaded += 1
            else:
                logger.warning("  Failed (%d, %d bytes): %s", resp.status_code, len(resp.content), fname)
        except httpx.HTTPError as exc:
            logger.warning("  Error: %s", exc)

        time.sleep(1)

    # Update index
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("NSPR PDFs: %d downloaded", downloaded)
    return downloaded


def load_nspr_products() -> list[dict]:
    """Load all scraped NSPR product details."""
    products = []
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        if f.name.startswith("_") or f.name == "pdfs_index.json":
            continue
        products.append(json.loads(f.read_text(encoding="utf-8")))
    return products


def print_nspr_status() -> None:
    """Print NSPR scraping progress."""
    if not OUTPUT_DIR.exists():
        print("No NSPR data yet")
        return

    # Count listings
    listings = list(OUTPUT_DIR.glob("*/_listing.json"))
    print(f"Category listings: {len(listings)}")
    for l in listings:
        data = json.loads(l.read_text(encoding="utf-8"))
        print(f"  {l.parent.name}: {len(data.get('products', []))} products")

    # Count details
    details = [f for f in OUTPUT_DIR.glob("*.json") if not f.name.startswith("_") and f.name != "pdfs_index.json"]
    print(f"Product details: {len(details)}")

    # PDF index
    idx_path = OUTPUT_DIR / "pdfs_index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        dl = sum(1 for e in idx if e.get("downloaded"))
        print(f"PDFs indexed: {len(idx)} ({dl} downloaded)")
```

- [ ] **Step 2: Verify module imports**

```bash
PYTHONUTF8=1 python -c "from pipeline.extraction.nspr_scraper import print_nspr_status; print_nspr_status()"
```

Expected: "No NSPR data yet"

- [ ] **Step 3: Commit**

```bash
git add pipeline/extraction/nspr_scraper.py
git commit -m "feat: add NSPR Chrome-assisted scraper with PDF index and download"
```

---

### Task 4: NSPR Chrome DevTools Harvest Session

This is a Chrome DevTools session, not a Python script. The agent uses the authenticated browser to scrape NSPR category listings and product details, calling `save_nspr_listing()` and `save_nspr_detail()` via Bash.

**Files:**
- No new files. Interactive Chrome DevTools session using helpers from Task 3.

**Strategy:** For each NSPR category, scrape the listing page (all pages), then visit each product detail page to extract specs, description, features, and PDF URLs. Use JavaScript extraction in the browser, then save via Python helpers.

- [ ] **Step 1: Scrape listing pages for all key categories**

For each category (screws, intervertebral-cages, plates, corpectomy-cage, si-joint, csf-management), use Chrome DevTools to:
1. Navigate to `neurospineproductreview.com/browse-products/{category}`
2. Extract product cards via JavaScript (name, company, tags, description, slug)
3. Paginate through all pages (click next page, re-extract)
4. Save via `save_nspr_listing(category, products)`

JavaScript extraction template for listing pages:
```javascript
var learnLinks = Array.from(document.querySelectorAll('a')).filter(a => a.textContent.includes('Learn About'));
learnLinks.map(a => {
  var card = a.closest('[class*="col"]') || a.parentElement.parentElement;
  var text = card ? card.innerText : '';
  var lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  var company = '', tags = '', desc = '';
  lines.forEach(l => {
    if (l.startsWith('COMPANY:')) company = l.replace('COMPANY:', '').trim();
    if (l.startsWith('TAGS:')) tags = l.replace('TAGS:', '').trim();
    if (l.startsWith('DESCRIPTION:')) desc = l.replace('DESCRIPTION:', '').trim();
  });
  return {name: lines[0] || '', company, tags, desc, slug: a.href.split('.com/')[1], href: a.href};
});
```

- [ ] **Step 2: Scrape detail pages for priority products**

For products that match devices in our catalog (by name/manufacturer fuzzy match), visit the detail page and extract:
```javascript
var specs = {};
document.body.innerText.split('\n').filter(l => /^[A-Z][A-Z\s()\/,]+:/.test(l.trim()) && l.length < 300)
  .forEach(l => { var [k, ...v] = l.split(':'); specs[k.trim()] = v.join(':').trim(); });
var pdfs = Array.from(document.querySelectorAll('a[href*=".pdf"]')).map(a => a.href);
var desc = Array.from(document.querySelectorAll('p')).map(p => p.textContent.trim()).filter(p => p.length > 50).sort((a,b) => b.length - a.length)[0] || '';
var features = Array.from(document.querySelectorAll('li')).map(li => li.textContent.trim()).filter(l => l.length > 10 && l.length < 300).slice(0, 15);
```

Save via `save_nspr_detail(slug, {name, company, specs, description, features, pdfs})`.

- [ ] **Step 3: Download NSPR-hosted PDFs**

```bash
PYTHONUTF8=1 python -c "from pipeline.extraction.nspr_scraper import download_nspr_pdfs; download_nspr_pdfs()"
```

- [ ] **Step 4: Check harvest status**

```bash
PYTHONUTF8=1 python -c "from pipeline.extraction.nspr_scraper import print_nspr_status; print_nspr_status()"
```

- [ ] **Step 5: Commit harvested data**

```bash
git add pipeline/data/extracted/nspr/
git commit -m "data: NSPR harvest - structured specs and PDF index for spine/cranial devices"
```

---

### Task 5: FDA Structured Data APIs

**Files:**
- Create: `pipeline/extraction/fda_structured.py`

- [ ] **Step 1: Create fda_structured.py**

```python
"""FDA UDI, MAUDE, and Recall API queries.

Uses the same openFDA REST API pattern as the existing FDAClient.
Synchronous (no async needed -- these are supplementary queries, not bulk discovery).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import httpx

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/device"
REQUEST_DELAY = 0.3
TIMEOUT = 30
MAX_RETRIES = 3

UDI_OUTPUT_DIR = EXTRACTED_DIR / "fda_structured"
SAFETY_OUTPUT_DIR = EXTRACTED_DIR / "fda_safety"


def _get(endpoint: str, params: dict) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(REQUEST_DELAY)
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.get(url, params=params)
            if resp.status_code == 404:
                return {"results": []}
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError:
            time.sleep(2 ** attempt)
    return {"results": []}


def query_udi(brand_name: str, company_name: str) -> dict | None:
    search = f'brand_name:"{brand_name}" AND company_name:"{company_name}"'
    data = _get("udi.json", {"search": search, "limit": 5})
    results = data.get("results", [])
    if not results:
        data = _get("udi.json", {"search": f'brand_name:"{brand_name}"', "limit": 5})
        results = data.get("results", [])
    if not results:
        return None

    rec = results[0]
    fields = {}

    desc = rec.get("device_description")
    if desc:
        fields["what_it_is"] = desc

    parts = []
    if rec.get("catalog_number"):
        parts.append(f"Catalog: {rec['catalog_number']}")
    if rec.get("version_or_model_number"):
        parts.append(f"Model: {rec['version_or_model_number']}")
    if parts:
        fields["sizing_specs"] = "; ".join(parts)

    notes = []
    mri = rec.get("mri_safety")
    if mri:
        notes.append(f"MRI: {mri}")
    sterilization = rec.get("sterilization", {})
    if sterilization.get("is_sterile"):
        method = sterilization.get("sterilization_methods", "")
        notes.append(f"Sterilized: {method}" if method else "Pre-sterilized")
    if rec.get("is_single_use"):
        notes.append("Single-use")
    if notes:
        fields["use_notes"] = ". ".join(notes)

    aliases = []
    if rec.get("brand_name"):
        aliases.append(rec["brand_name"])
    for term in rec.get("gmdn_terms", []):
        if term.get("name"):
            aliases.append(term["name"])
    if aliases:
        fields["also_known_as"] = aliases

    if not fields:
        return None

    return {
        "source": "fda_udi",
        "brand_name": brand_name,
        "extraction_method": "fda_udi_api",
        "fields": fields,
        "confidence": {k: 0.85 for k in fields},
    }


def query_maude(product_code: str, brand_name: str | None = None) -> dict | None:
    search = f'product_code:"{product_code}"'
    if brand_name:
        search += f' AND brand_name:"{brand_name}"'
    data = _get("event.json", {"search": search, "count": "event_type.exact"})
    counts = {r["term"]: r["count"] for r in data.get("results", [])}
    if not counts:
        return None
    return {
        "source": "fda_maude",
        "product_code": product_code,
        "event_counts": counts,
        "total_events": sum(counts.values()),
    }


def query_recalls(product_code: str, firm_name: str | None = None) -> list[dict]:
    search = f'product_code:"{product_code}"'
    if firm_name:
        search += f' AND recalling_firm:"{firm_name}"'
    data = _get("recall.json", {"search": search, "limit": 20})
    return [
        {
            "reason": r.get("reason_for_recall", ""),
            "status": r.get("status", ""),
            "date": r.get("event_date_initiated", ""),
            "product_description": r.get("product_description", ""),
        }
        for r in data.get("results", [])
    ]


def extract_all_structured(devices: list[dict]) -> tuple[list, list, list]:
    """Run UDI, MAUDE, and Recall queries for a list of devices."""
    UDI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAFETY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    udi_results, maude_results, recall_results = [], [], []

    for device in devices:
        name = device.get("device_name", "")
        mfr = device.get("manufacturer", "")
        code = device.get("product_code", "")
        stem = device.get("filename_stem", name)

        logger.info("  FDA APIs: %s", name)

        udi = query_udi(name, mfr)
        if udi:
            (UDI_OUTPUT_DIR / f"{stem}.json").write_text(
                json.dumps(udi, indent=2, ensure_ascii=False), encoding="utf-8")
            udi_results.append(udi)

        if code:
            maude = query_maude(code, name)
            if maude:
                (SAFETY_OUTPUT_DIR / f"{stem}-maude.json").write_text(
                    json.dumps(maude, indent=2, ensure_ascii=False), encoding="utf-8")
                maude_results.append(maude)

            recalls = query_recalls(code, mfr)
            if recalls:
                (SAFETY_OUTPUT_DIR / f"{stem}-recalls.json").write_text(
                    json.dumps(recalls, indent=2, ensure_ascii=False), encoding="utf-8")
                recall_results.append({"stem": stem, "recalls": recalls})

    logger.info("FDA: %d UDI, %d MAUDE, %d recall", len(udi_results), len(maude_results), len(recall_results))
    return udi_results, maude_results, recall_results
```

- [ ] **Step 2: Test UDI query**

```bash
PYTHONUTF8=1 python -c "
from pipeline.extraction.fda_structured import query_udi
result = query_udi('Pipeline Flex', 'Medtronic')
if result:
    print('Fields:', list(result['fields'].keys()))
    for k, v in result['fields'].items():
        print(f'  {k}: {str(v)[:100]}')
else:
    print('No UDI results')
"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/extraction/fda_structured.py
git commit -m "feat: add FDA UDI/MAUDE/Recall structured data queries"
```

---

### Task 6: DeepSeek API Client

**Files:**
- Create: `pipeline/extraction/deepseek.py`

- [ ] **Step 1: Create deepseek.py**

```python
"""DeepSeek API client for structured extraction and enrichment."""

from __future__ import annotations

import json
import logging
import time

import httpx

from ..config import DEEPSEEK_API_KEY

logger = logging.getLogger(__name__)

BASE_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"
MAX_RETRIES = 3
TIMEOUT = 60


def deepseek_extract(prompt: str, max_tokens: int = 4096) -> dict | None:
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set")
        return None

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                resp = client.post(BASE_URL, json=payload, headers=headers)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_json(content)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("DeepSeek error: %s, retry %d", exc, attempt + 1)
            time.sleep(2 ** attempt)

    logger.error("DeepSeek failed after %d retries", MAX_RETRIES)
    return None


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON: %s", text[:200])
        return None
```

- [ ] **Step 2: Verify**

```bash
PYTHONUTF8=1 python -c "
from pipeline.extraction.deepseek import deepseek_extract
result = deepseek_extract('Return JSON: {\"status\": \"ok\"}')
print(result)
"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/extraction/deepseek.py
git commit -m "feat: add DeepSeek API client"
```

---

### Task 7: PDF Utilities and FDA Summary Parser

**Files:**
- Create: `pipeline/extraction/pdf_utils.py`
- Create: `pipeline/extraction/fda_parser.py`

- [ ] **Step 1: Create pdf_utils.py**

```python
"""Shared PDF utilities: Marker converter init, PDF validation."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_converter = None
_converter_llm = None


def validate_pdf(path: Path) -> str | None:
    if not path.exists():
        return f"Not found: {path}"
    if path.stat().st_size < 1024:
        return f"Too small: {path}"
    with open(path, "rb") as f:
        header = f.read(8)
    if header[:5] != b"%PDF-":
        if header[:5] in (b"<html", b"<!DOC"):
            return f"HTML disguised as PDF: {path}"
        return f"Invalid header: {path}"
    return None


def pdf_to_markdown(path: Path, use_llm: bool = False) -> str | None:
    error = validate_pdf(path)
    if error:
        logger.warning(error)
        return None
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
    except ImportError:
        logger.error("marker-pdf not installed")
        return None
    try:
        converter = _get_converter(use_llm)
        rendered = converter(str(path))
        text, _, _ = text_from_rendered(rendered)
        if len(text.strip()) < 50:
            return None
        return text
    except Exception as exc:
        logger.error("Marker failed on %s: %s", path, exc)
        return None


def _get_converter(use_llm: bool):
    global _converter, _converter_llm
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from ..config import DEEPSEEK_API_KEY

    if use_llm:
        if _converter_llm is None:
            _converter_llm = PdfConverter(
                artifact_dict=create_model_dict(),
                config={
                    "output_format": "markdown", "use_llm": True,
                    "llm_service": "marker.services.openai.OpenAIService",
                    "openai_api_key": DEEPSEEK_API_KEY or "",
                    "openai_base_url": "https://api.deepseek.com/v1",
                    "openai_model": "deepseek-chat",
                },
            )
        return _converter_llm
    if _converter is None:
        _converter = PdfConverter(
            artifact_dict=create_model_dict(),
            config={"output_format": "markdown", "use_llm": False},
        )
    return _converter
```

- [ ] **Step 2: Create fda_parser.py**

```python
"""Tier 1A: Deterministic extraction from FDA 510(k) summary PDFs."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import DATA_DIR, EXTRACTED_DIR
from .pdf_utils import pdf_to_markdown, validate_pdf

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "fda_summaries"

SECTION_PATTERNS = {
    "Device Description": re.compile(r"^#{0,3}\s*(?:device\s+description|description\s+of\s+(?:the\s+)?device)", re.I | re.M),
    "Indications for Use": re.compile(r"^#{0,3}\s*indications?\s+(?:for\s+)?use", re.I | re.M),
    "Contraindications": re.compile(r"^#{0,3}\s*contraindications?", re.I | re.M),
    "Substantial Equivalence": re.compile(r"^#{0,3}\s*(?:substantial\s+equivalence|predicate\s+device|comparison\s+with\s+predicate)", re.I | re.M),
}

K_NUMBER_PATTERN = re.compile(r"\b(K\d{6})\b")


def extract_fda_summary(pdf_path: Path) -> dict | None:
    error = validate_pdf(pdf_path)
    if error:
        return None
    markdown = pdf_to_markdown(pdf_path, use_llm=False)
    if not markdown:
        return None

    sections = _find_sections(markdown)
    fields = _map_sections(sections)
    confidence = {}
    if "Indications for Use" in sections:
        confidence["indications"] = 0.95
    if "Device Description" in sections:
        confidence["what_it_is"] = 0.9
    if "Contraindications" in sections:
        confidence["contraindications"] = 0.9

    return {
        "source_pdf": pdf_path.name,
        "clearance_number": pdf_path.stem.upper(),
        "extraction_method": "marker_deterministic",
        "fields": fields,
        "confidence": confidence,
        "raw_sections": sections,
    }


def extract_all_fda_summaries() -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdfs_dir = DATA_DIR / "pdfs"
    results, skipped = [], []

    seen = set()
    pdf_files = []
    for p in sorted(pdfs_dir.rglob("*.pdf")):
        if p.name not in seen:
            seen.add(p.name)
            pdf_files.append(p)

    logger.info("Processing %d FDA PDFs", len(pdf_files))
    for pdf_path in pdf_files:
        result = extract_fda_summary(pdf_path)
        if result is None:
            skipped.append({"file": pdf_path.name, "reason": "extraction_failed"})
            continue
        (OUTPUT_DIR / f"{pdf_path.stem}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(result)

    # Log skipped
    skip_path = EXTRACTED_DIR / "skipped.json"
    existing = json.loads(skip_path.read_text(encoding="utf-8")) if skip_path.exists() else []
    existing.extend(skipped)
    skip_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("FDA: %d extracted, %d skipped", len(results), len(skipped))
    return results


def _find_sections(md: str) -> dict[str, str]:
    matches = [(p.search(md).start(), name) for name, p in SECTION_PATTERNS.items() if p.search(md)]
    matches.sort()
    sections = {}
    for i, (start, name) in enumerate(matches):
        line_end = md.index("\n", start) if "\n" in md[start:] else len(md)
        end = matches[i + 1][0] if i + 1 < len(matches) else len(md)
        text = md[line_end + 1:end].strip()
        if text:
            sections[name] = text
    return sections


def _map_sections(sections: dict[str, str]) -> dict:
    fields = {"what_it_is": None, "indications": None, "contraindications": None, "sizing_specs": None, "also_known_as": None}
    if "Device Description" in sections:
        fields["what_it_is"] = sections["Device Description"]
        if re.search(r"\d+\s*(?:mm|cm|fr|french|inch)", sections["Device Description"], re.I):
            fields["sizing_specs"] = sections["Device Description"]
    if "Indications for Use" in sections:
        fields["indications"] = sections["Indications for Use"]
    if "Contraindications" in sections:
        fields["contraindications"] = sections["Contraindications"]
    if "Substantial Equivalence" in sections:
        preds = [m.group(1) for m in K_NUMBER_PATTERN.finditer(sections["Substantial Equivalence"])]
        if preds:
            fields["also_known_as"] = preds
    return fields
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/extraction/pdf_utils.py pipeline/extraction/fda_parser.py
git commit -m "feat: add PDF utils (Marker) and FDA 510(k) summary parser"
```

---

### Task 8: Document Extractor (Marker + DeepSeek)

**Files:**
- Create: `pipeline/extraction/doc_extractor.py`

- [ ] **Step 1: Create doc_extractor.py**

```python
"""Tier 2: Extract structured fields from brochures/technique guides via Marker + DeepSeek."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..config import CATALOG_ROOT, DATA_DIR, EXTRACTED_DIR
from .deepseek import deepseek_extract
from .pdf_utils import pdf_to_markdown

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "documents"

PROMPT = """You are extracting structured medical device data from a manufacturer document converted to markdown.

Extract ONLY what is explicitly stated. Return null for missing fields.
Preserve markdown tables in sizing_specs.

Fields:
- what_it_is: Device description, mechanism, materials
- sizing_specs: Dimensions, sizes, configurations, materials table
- indications: Approved/intended clinical uses
- contraindications: Conditions where device should not be used
- compatible_with: Compatible devices, instruments, accessories
- use_notes: Clinical or procedural details
- also_known_as: Alternate names, abbreviations

Document type: {doc_type}
Device: {device_name} by {manufacturer}

Content:
{content}

Respond in JSON."""


def extract_document(pdf_path: Path, device_name: str, manufacturer: str, doc_type: str = "brochure") -> dict | None:
    markdown = pdf_to_markdown(pdf_path, use_llm=True)
    if not markdown:
        return None
    if len(markdown) > 60000:
        markdown = markdown[:60000]

    fields = deepseek_extract(PROMPT.format(
        doc_type=doc_type, device_name=device_name, manufacturer=manufacturer, content=markdown))
    if not fields:
        return None

    return {
        "source_pdf": pdf_path.name,
        "device_name": device_name,
        "manufacturer": manufacturer,
        "extraction_method": "marker_deepseek",
        "fields": fields,
        "confidence": {k: 0.7 for k, v in fields.items() if v is not None},
    }


def extract_all_documents() -> list[dict]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    # Catalog root PDFs
    for pdf in sorted(CATALOG_ROOT.glob("*--*.pdf")):
        parts = pdf.stem.split("--")
        if len(parts) < 3:
            continue
        out_file = OUTPUT_DIR / f"{pdf.stem}.json"
        if out_file.exists():
            continue
        logger.info("  Extracting: %s", pdf.name)
        result = extract_document(pdf, parts[2], parts[1], parts[3] if len(parts) > 3 else "unknown")
        if result:
            out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            results.append(result)
        time.sleep(1)

    # NSPR-downloaded PDFs
    nspr_pdfs = EXTRACTED_DIR / "nspr" / "pdfs"
    if nspr_pdfs.exists():
        for pdf in sorted(nspr_pdfs.glob("*.pdf")):
            out_file = OUTPUT_DIR / f"nspr--{pdf.stem}.json"
            if out_file.exists():
                continue
            logger.info("  Extracting NSPR: %s", pdf.name)
            result = extract_document(pdf, pdf.stem, "nspr")
            if result:
                out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                results.append(result)
            time.sleep(1)

    logger.info("Documents: %d extracted", len(results))
    return results
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/extraction/doc_extractor.py
git commit -m "feat: add Tier 2 document extractor (Marker + DeepSeek)"
```

---

### Task 9: Enrichment Synthesis

**Files:**
- Create: `pipeline/extraction/enricher.py`

- [ ] **Step 1: Create enricher.py**

```python
"""Tier 3: Multi-source enrichment. Merge all sources per device, fill gaps via DeepSeek."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import CATALOG_ROOT, DATA_DIR, EXTRACTED_DIR, ENRICHED_DIR
from .deepseek import deepseek_extract

logger = logging.getLogger(__name__)

CONTENT_FIELDS = ["what_it_is", "sizing_specs", "indications", "contraindications",
                  "compatible_with", "use_notes", "also_known_as"]


def enrich_all() -> list[dict]:
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    merged_dir = DATA_DIR / "merged"
    if not merged_dir.exists():
        logger.error("No merged directory. Run --merge-only first.")
        return []

    results = []
    for f in sorted(merged_dir.glob("*.json")):
        merged = json.loads(f.read_text(encoding="utf-8"))
        stem = f.stem
        if (CATALOG_ROOT / f"{stem}--knowledge.md").exists():
            continue
        enriched = _enrich_device(stem, merged)
        (ENRICHED_DIR / f"{stem}.json").write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False), encoding="utf-8")
        results.append(enriched)

    logger.info("Enriched: %d devices", len(results))
    return results


def _enrich_device(stem: str, merged: dict) -> dict:
    sources = _gather_sources(stem, merged)
    log = {}

    for field in CONTENT_FIELDS:
        val, src, conf = _resolve_field(field, sources)
        if val is not None:
            merged[field] = val
            log[field] = {"source": src, "confidence": conf}
        else:
            log[field] = {"source": "none", "confidence": 0}

    # Safety annotations
    safety = sources.get("safety")
    if safety:
        _annotate_safety(merged, safety)

    merged["_enrichment"] = log
    return merged


def _gather_sources(stem: str, merged: dict) -> dict:
    sources = {"merged": merged}

    # FDA summary
    k = merged.get("clearance_number", "")
    p = EXTRACTED_DIR / "fda_summaries" / f"{k}.json"
    if p.exists():
        sources["fda_summary"] = json.loads(p.read_text(encoding="utf-8"))

    # UDI
    p = EXTRACTED_DIR / "fda_structured" / f"{stem}.json"
    if p.exists():
        sources["udi"] = json.loads(p.read_text(encoding="utf-8"))

    # Safety
    safety = {}
    for suffix in ("maude", "recalls"):
        p = EXTRACTED_DIR / "fda_safety" / f"{stem}-{suffix}.json"
        if p.exists():
            safety[suffix] = json.loads(p.read_text(encoding="utf-8"))
    if safety:
        sources["safety"] = safety

    # EVToday
    evt = _find_evtoday_match(stem, merged)
    if evt:
        sources["evtoday"] = evt

    # NSPR
    nspr = _find_nspr_match(stem, merged)
    if nspr:
        sources["nspr"] = nspr

    # Document extraction
    for doc in (EXTRACTED_DIR / "documents").glob(f"*{stem}*"):
        sources["document"] = json.loads(doc.read_text(encoding="utf-8"))
        break

    return sources


def _resolve_field(field: str, sources: dict):
    # Priority chain
    for src_key, conf_threshold in [
        ("fda_summary", 0.9), ("udi", 0.85), ("nspr", 0.8),
        ("evtoday", 0.8), ("document", 0.6)
    ]:
        src = sources.get(src_key, {})
        fields = src.get("fields", src.get("specs", {}))
        conf_map = src.get("confidence", {})
        val = fields.get(field)
        if val:
            conf = conf_map.get(field, 0.7)
            if conf >= conf_threshold or conf_threshold <= 0.6:
                return val, src_key, conf

    # Existing merged/scraper data
    val = sources.get("merged", {}).get(field)
    if val:
        return val, "scraper", 0.5

    return None, "none", 0


def _find_evtoday_match(stem: str, merged: dict) -> dict | None:
    evtoday_dir = EXTRACTED_DIR / "evtoday"
    if not evtoday_dir.exists():
        return None
    device_name = (merged.get("device_name") or "").lower()
    manufacturer = (merged.get("manufacturer") or "").lower()

    for f in evtoday_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        for entry in data.get("devices", []):
            entry_name = (entry.get("Product Name") or "").lower()
            entry_co = (entry.get("Company Name") or "").lower()
            name_words = set(device_name.split())
            entry_words = set(entry_name.split())
            if len(name_words & entry_words) >= 2 or (len(name_words & entry_words) >= 1 and manufacturer in entry_co):
                return {"fields": _map_evtoday(entry), "confidence": {"indications": 0.85, "sizing_specs": 0.8}}
    return None


def _find_nspr_match(stem: str, merged: dict) -> dict | None:
    nspr_dir = EXTRACTED_DIR / "nspr"
    if not nspr_dir.exists():
        return None
    device_name = (merged.get("device_name") or "").lower()

    for f in nspr_dir.glob("*.json"):
        if f.name.startswith("_") or f.name == "pdfs_index.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        nspr_name = (data.get("device_name") or "").lower()
        name_words = set(device_name.split())
        nspr_words = set(nspr_name.split())
        if len(name_words & nspr_words) >= 2:
            return {"fields": _map_nspr(data), "confidence": {"what_it_is": 0.8, "sizing_specs": 0.8}}
    return None


def _map_evtoday(entry: dict) -> dict:
    fields = {}
    if entry.get("US FDA Indicated Use"):
        fields["indications"] = entry["US FDA Indicated Use"]
    sizing_parts = []
    for k in ["Stent Diameters (mm)", "Stent Lengths (mm)", "Size (F)", "Length (cm)",
              "Balloon Diameters (mm)", "Maximum Tip Diameter (mm)", "Working Length (cm)",
              "Proximal Size (F)", "Distal Size (F)", "Device Diameter (mm)"]:
        if entry.get(k):
            sizing_parts.append(f"{k}: {entry[k]}")
    if entry.get("Materials Used"):
        sizing_parts.append(f"Materials: {entry['Materials Used']}")
    if sizing_parts:
        fields["sizing_specs"] = "\n".join(sizing_parts)
    if entry.get("Comments"):
        fields["what_it_is"] = entry["Comments"]
    notes = []
    for k in ["Mode of Operation", "Method of Detachment", "Coil Type", "Type"]:
        if entry.get(k):
            notes.append(f"{k}: {entry[k]}")
    if notes:
        fields["use_notes"] = "\n".join(notes)
    return fields


def _map_nspr(data: dict) -> dict:
    fields = {}
    if data.get("description"):
        fields["what_it_is"] = data["description"]
    specs = data.get("specs", {})
    sizing_parts = []
    if specs.get("BY MATERIAL"):
        sizing_parts.append(f"Material: {specs['BY MATERIAL']}")
    if specs.get("FEATURES"):
        sizing_parts.append(f"Features: {specs['FEATURES']}")
    if sizing_parts:
        fields["sizing_specs"] = "\n".join(sizing_parts)
    if specs.get("BY PROCEDURE TYPE"):
        fields["use_notes"] = f"Procedures: {specs['BY PROCEDURE TYPE']}"
    if data.get("features"):
        existing = fields.get("what_it_is", "")
        fields["what_it_is"] = existing + "\n\nFeatures:\n" + "\n".join(f"- {f}" for f in data["features"])
    return fields


def _annotate_safety(merged: dict, safety: dict) -> None:
    notes = merged.get("use_notes") or ""
    maude = safety.get("maude")
    if maude and maude.get("total_events", 0) > 0:
        counts = maude["event_counts"]
        summary = ", ".join(f"{k}: {v}" for k, v in counts.items())
        notes += f"\n\n[FDA MAUDE] {maude['total_events']} reports ({summary})."
    recalls = safety.get("recalls")
    if recalls:
        active = [r for r in recalls if r.get("status") != "Terminated"]
        if active:
            notes += f"\n\n[FDA RECALL] {len(active)} active recall(s)."
            for r in active[:2]:
                notes += f"\n  - {r.get('reason', '')[:200]}"
    if notes != (merged.get("use_notes") or ""):
        merged["use_notes"] = notes.strip()
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/extraction/enricher.py
git commit -m "feat: add Tier 3 enrichment with NSPR + EVToday + FDA source priority"
```

---

### Task 10: CLI Entry Points and Pipeline Integration

**Files:**
- Create: `pipeline/run_extract.py`
- Create: `pipeline/run_enrich.py`
- Modify: `pipeline/run_pipeline.py`
- Modify: `pipeline/processing/template.py`

- [ ] **Step 1: Create run_extract.py**

```python
"""CLI for extraction Tiers 1-2.

Usage:
    python -m pipeline.run_extract --evtoday           # Tier 1C
    python -m pipeline.run_extract --nspr-download     # Tier 1D: download NSPR PDFs
    python -m pipeline.run_extract --fda-summaries     # Tier 1A
    python -m pipeline.run_extract --fda-structured    # Tier 1B
    python -m pipeline.run_extract --documents         # Tier 2
    python -m pipeline.run_extract --all               # Everything
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from rich.console import Console

from .config import DATA_DIR

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def cli():
    parser = argparse.ArgumentParser(description="Run extraction pipeline")
    parser.add_argument("--evtoday", action="store_true", help="Tier 1C: EVToday device guide")
    parser.add_argument("--nspr-download", action="store_true", help="Tier 1D: download NSPR PDFs")
    parser.add_argument("--fda-summaries", action="store_true", help="Tier 1A: parse 510(k) PDFs")
    parser.add_argument("--fda-structured", action="store_true", help="Tier 1B: UDI/MAUDE/Recalls")
    parser.add_argument("--documents", action="store_true", help="Tier 2: extract brochures/guides")
    parser.add_argument("--all", action="store_true", help="Run all tiers")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        return

    if args.evtoday or args.all:
        console.rule("[bold]Tier 1C: EVToday Device Guide")
        from .extraction.evtoday_scraper import scrape_all_categories
        counts = scrape_all_categories()
        console.print(f"  [green]{sum(counts.values())}[/green] devices")

    if args.nspr_download or args.all:
        console.rule("[bold]Tier 1D: NSPR PDF Download")
        from .extraction.nspr_scraper import download_nspr_pdfs, print_nspr_status
        print_nspr_status()
        n = download_nspr_pdfs()
        console.print(f"  [green]{n}[/green] PDFs downloaded")

    if args.fda_summaries or args.all:
        console.rule("[bold]Tier 1A: FDA 510(k) Summary Extraction")
        from .extraction.fda_parser import extract_all_fda_summaries
        results = extract_all_fda_summaries()
        console.print(f"  [green]{len(results)}[/green] PDFs extracted")

    if args.fda_structured or args.all:
        console.rule("[bold]Tier 1B: FDA Structured Data")
        from .extraction.fda_structured import extract_all_structured
        devices = _load_device_list()
        udi, maude, recalls = extract_all_structured(devices)
        console.print(f"  [green]{len(udi)}[/green] UDI, [green]{len(maude)}[/green] MAUDE, [green]{len(recalls)}[/green] recalls")

    if args.documents or args.all:
        console.rule("[bold]Tier 2: Document Extraction")
        from .extraction.doc_extractor import extract_all_documents
        results = extract_all_documents()
        console.print(f"  [green]{len(results)}[/green] documents")


def _load_device_list() -> list[dict]:
    merged_dir = DATA_DIR / "merged"
    devices = []
    if merged_dir.exists():
        for f in merged_dir.glob("*.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            devices.append({
                "device_name": data.get("device_name", ""),
                "manufacturer": data.get("manufacturer", ""),
                "product_code": data.get("product_code", ""),
                "filename_stem": f.stem,
            })
    return devices


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Create run_enrich.py**

```python
"""CLI for enrichment Tier 3."""

from __future__ import annotations

import logging

from rich.console import Console

console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def cli():
    console.rule("[bold]Tier 3: Enrichment Synthesis")
    from .extraction.enricher import enrich_all
    results = enrich_all()
    console.print(f"  [green]{len(results)}[/green] devices enriched")

    source_counts: dict[str, int] = {}
    for r in results:
        for field, meta in r.get("_enrichment", {}).items():
            if field.startswith("_"):
                continue
            source_counts[meta.get("source", "none")] = source_counts.get(meta.get("source", "none"), 0) + 1
    if source_counts:
        console.print("\n  [bold]Sources:[/bold]")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            console.print(f"    {src}: {count}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 3: Add flags to run_pipeline.py**

Add to argparse in `pipeline/run_pipeline.py`:
```python
    parser.add_argument("--extract", action="store_true", help="Run extraction (Tiers 1-2)")
    parser.add_argument("--enrich", action="store_true", help="Run enrichment (Tier 3)")
```

Add to `main()` before merge phase:
```python
    if args.extract:
        from .run_extract import cli as extract_cli
        import sys
        sys.argv = ["run_extract", "--all"]
        extract_cli()

    if args.enrich:
        from .run_enrich import cli as enrich_cli
        enrich_cli()
```

- [ ] **Step 4: Modify template.py to prefer enriched records**

Add at top of `generate_drafts()`:
```python
    enriched_dir = DATA_DIR / "enriched"
    enriched_map = {}
    if enriched_dir.exists():
        for f in enriched_dir.glob("*.json"):
            enriched_map[f.stem] = json.loads(f.read_text(encoding="utf-8"))
```

Inside the loop, before rendering:
```python
        if record.filename_stem in enriched_map:
            enriched = enriched_map[record.filename_stem]
            for field in ["what_it_is", "sizing_specs", "indications", "contraindications",
                          "compatible_with", "use_notes", "also_known_as"]:
                val = enriched.get(field)
                if val:
                    record = record._replace(**{field: val})
```

- [ ] **Step 5: Verify CLI**

```bash
PYTHONUTF8=1 python -m pipeline.run_extract --help
PYTHONUTF8=1 python -m pipeline.run_enrich --help
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/run_extract.py pipeline/run_enrich.py pipeline/run_pipeline.py pipeline/processing/template.py
git commit -m "feat: add CLI entry points and pipeline integration for extraction/enrichment"
```

---

### Task 11: Smoke Test

- [ ] **Step 1: Run EVToday (already have data, verify module)**

```bash
PYTHONUTF8=1 python -m pipeline.run_extract --evtoday
```

- [ ] **Step 2: Run NSPR PDF download (after Chrome DevTools harvest)**

```bash
PYTHONUTF8=1 python -m pipeline.run_extract --nspr-download
```

- [ ] **Step 3: Run FDA structured queries**

```bash
PYTHONUTF8=1 python -m pipeline.run_extract --fda-structured
```

- [ ] **Step 4: Run enrichment**

```bash
PYTHONUTF8=1 python -m pipeline.run_enrich
```

- [ ] **Step 5: Regenerate drafts**

```bash
PYTHONUTF8=1 python -m pipeline.run_pipeline --merge-only
```

- [ ] **Step 6: Spot-check a few drafts for enriched content**

Check that previously-empty fields now have data from NSPR/EVToday/FDA sources.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "fix: smoke test fixes for extraction pipeline"
```
