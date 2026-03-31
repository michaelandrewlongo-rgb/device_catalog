# Chrome-Assisted Scraping Design

## Problem

The existing Python scrapers (Scrapling + requests) fail to extract product data from several manufacturer sites due to bot detection, JS-rendered content behind tabs/accordions, and HCP-gated PDFs. Medtronic, Cerenovus, and Stryker have the worst yield -- all three fall back to hardcoded URL lists because dynamic discovery fails. Tabbed spec panels on Terumo Neuro and Stryker are never clicked, so sizing/indications fields end up as `[NEEDS CONTENT]` placeholders.

## Solution

Use Chrome DevTools MCP (`claude-in-chrome`) to run Claude-driven scraping sessions in a real Chrome browser. Claude navigates manufacturer sites, expands collapsed content, intercepts network requests to find product APIs, and writes `ScrapedProduct` JSON files that the existing pipeline (merger, template generator) consumes unchanged.

## Architecture

### What changes

Two new files:

1. **`pipeline/scrapers/chrome_assisted.py`** -- Python helper providing `save_chrome_product()`, `load_existing_stems()`, and `ChromeScrapedProduct` model. Not a scraper class; just I/O utilities Claude calls via the Bash tool during a session.
2. **`pipeline/scrapers/chrome_workflow.md`** -- Per-manufacturer navigation guide. Claude reads this at session start and follows it to scrape each manufacturer.

### What does not change

- `pipeline/processing/merger.py` -- reads all JSON files in `scraper_raw/{manufacturer}/`; agnostic to source
- `pipeline/processing/template.py` -- renders `MergedDeviceRecord` to markdown scaffold
- `pipeline/processing/naming.py` -- unchanged
- All existing scrapers -- remain the automated first pass

### Data flow

```
Chrome MCP session (Claude-driven)
  |
  v
pipeline/data/scraper_raw/{manufacturer}/*.json   <-- same directory as Python scrapers
  |
  v
merger.py  -->  MergedDeviceRecord  -->  template.py  -->  pipeline/data/drafts/*.md
```

### Workflow per manufacturer

1. Claude reads `chrome_workflow.md` for the target manufacturer
2. `navigate` to product listing page
3. Read DOM to discover product links (or intercept network requests to find a product catalog API)
4. For each product page:
   a. `navigate` to the URL
   b. `javascript_tool` to expand all tabs/accordions/collapsed panels
   c. `read_network_requests` to capture XHR/fetch calls with product JSON
   d. `get_page_text` for clean rendered text
   e. `read_page` for full DOM (link extraction, PDF discovery)
   f. Extract `ScrapedProduct` fields from content
   g. Call `save_chrome_product()` via Bash to write JSON
5. Log any discovered API endpoints for future automation

## Chrome MCP Tool Mapping

| Scraping task | Chrome MCP tool | Replaces |
|---|---|---|
| Go to page | `navigate` | `StealthyFetcher.fetch()` / `DynamicFetcher.fetch()` |
| Get clean text | `get_page_text` | `extract_page_text_from_html()` |
| Get full DOM | `read_page` | `fetch_html()` return value |
| Expand collapsed content | `javascript_tool` | Nothing (not possible with headless Playwright) |
| Find API calls | `read_network_requests` | Nothing (new capability) |
| Find elements | `find` | BeautifulSoup `select()` |
| Click elements | `javascript_tool` / `computer` | Nothing (headless doesn't interact) |

### Tab/accordion expansion JS

Run on every product page before text extraction:

```javascript
// Expand all collapsed content
document.querySelectorAll(
  '[role="tab"], .accordion-button, [data-toggle="collapse"], ' +
  '[aria-expanded="false"], .tab-link, .expandable, details summary'
).forEach(el => { try { el.click(); } catch(e) {} });

// Wait for animations
await new Promise(r => setTimeout(r, 800));

// Also expand any <details> elements
document.querySelectorAll('details:not([open])').forEach(d => d.open = true);
```

## Per-Manufacturer Strategy

### Medtronic (priority: highest)

- **Current yield**: 3 hardcoded fallback URLs. DynamicFetcher blocked by Cloudflare.
- **Listing URL**: `medtronic.com/us-en/healthcare-professionals/products/neurological.html`
- **Strategy**: Intercept network requests on the listing page. Medtronic's React SPA calls an internal product API on load. If found, that single endpoint returns the full product tree -- skip page-by-page navigation.
- **Product link pattern**: `/healthcare-professionals/products/neurological/` path prefix
- **Known product families**: Pipeline Flex (flow diverter), Solitaire X (thrombectomy), Onyx (liquid embolic), Echelon/Phenom/Marksman (microcatheters), Strata (CSF shunt)
- **Tab patterns**: Product pages use tabbed panels for Overview / Specifications / Resources
- **HCP content**: Some IFU PDFs gated behind HCP login. If user is logged in, Chrome session can access them.

### Cerenovus / J&J MedTech (priority: high)

- **Current yield**: Falls back to 3 seed landing pages only. No individual product pages scraped.
- **Listing URL**: `jnjmedtech.com/en-US/companies/cerenovus` and `/specialties/neurointerventional/`
- **Strategy**: Network interception on landing pages. J&J sites typically call internal catalog APIs.
- **Product link pattern**: URLs containing `cerenovus`, `embotrap`, `galaxy`, `cereglide`, `trufill`, `bravo`, `emboguard`
- **Known product families**: EmboTrap III (thrombectomy), Galaxy G3 (coils), CereGlide (distal access), Trufill (liquid embolic), Bravo (flow diverter)

### Stryker (priority: high)

- **Current yield**: Discovery mostly fails; falls back to 2 URLs.
- **Listing URLs**: `neurosurgical.stryker.com/products/` and `stryker.com/.../neurovascular.html`
- **Strategy**: `neurosurgical.stryker.com` is less JS-heavy; Chrome reliably gets product links. `stryker.com/neurotechnology` portfolio page has tiles that need JS click to expand.
- **Product link pattern**: paths containing `/neurovascular`, `/trevo`, `/surpass`, `/target`, `/excelsior`, `/synchro`, `/axs`
- **Tab patterns**: Spec panels on product pages (click "Specifications" tab before reading)
- **Known product families**: Surpass Evolve (flow diverter), Trevo (thrombectomy), Neuroform Atlas (stent), Target (coils), Excelsior (microcatheters), AXS (distal access)

### Terumo Neuro / MicroVention (priority: medium)

- **Current yield**: Fallback list has 22 products; yields reasonable data. Tabs hide specs.
- **Strategy**: Navigate the real product listing to find any new products since the fallback list was last updated. Main win: click spec/ordering tabs on each product page to get sizing tables.
- **Tab patterns**: Product pages have "Product Codes" / "Specifications" / "Ordering Information" tabs

### Balt (priority: medium)

- **Current yield**: Blocked intermittently (see `balt_failures_v5.json`, `balt_failures_v6.json`)
- **Strategy**: Chrome with real fingerprint resolves the blocking. Full extraction of SILK, OPTIMA, LEO, RAPTOR product families.
- **Product link pattern**: `/products/` path prefix on `baltgroup.com`

### Penumbra / Integra (priority: lower)

- **Current yield**: Reasonable. Chrome sessions useful for filling specific gaps, not full re-scrape.

## Output Format

Same JSON schema as `ScrapedProduct.model_dump()`, plus one extra field:

```json
{
  "device_name": "Pipeline Flex Embolization Device",
  "manufacturer": "medtronic",
  "category_hint": "flow-diverter",
  "what_it_is": "Flow diverter for endovascular treatment of...",
  "sizing_specs": "Available in diameters 2.5-5.0mm, lengths 10-35mm...",
  "indications": "Indicated for the endovascular treatment of adults...",
  "contraindications": null,
  "compatible_with": null,
  "use_notes": null,
  "deployment_steps": null,
  "also_known_as": ["Pipeline", "PED"],
  "source_url": "https://www.medtronic.com/...",
  "ifu_pdf_url": "https://www.medtronic.com/.../pipeline-flex-ifu.pdf",
  "other_pdf_urls": {},
  "clearance_numbers": [],
  "chrome_api_endpoint": "https://api.medtronic.com/products/v2/neurological"
}
```

The merger ignores unknown fields, so `chrome_api_endpoint` passes through harmlessly and is available in `merged/` output for future use.

## API Endpoint Capture

During Chrome sessions, any JSON API endpoint discovered via `read_network_requests` is:
1. Recorded in the product JSON as `chrome_api_endpoint`
2. Logged to `pipeline/data/scraper_raw/{manufacturer}/discovered_apis.json`
3. Manually reviewed after the session

Stable endpoints can later be added to `config.py` as `API_ENDPOINTS` and consumed by a lightweight `api_client.py` scraper for future automated runs.

## Session Workflow (what Claude does)

```
1. Read chrome_workflow.md for target manufacturer
2. load_existing_stems(manufacturer) -- skip already-scraped products
3. navigate to listing page
4. [If SPA] read_network_requests -- look for product catalog API
5. Extract product URLs from DOM or API response
6. For each product URL:
   a. navigate to URL
   b. javascript_tool -- expand tabs/accordions
   c. read_network_requests -- capture any product-specific API calls
   d. get_page_text -- clean rendered text
   e. read_page -- full DOM for links/PDFs
   f. Extract fields into ScrapedProduct dict
   g. save_chrome_product(data, manufacturer) via Bash
   h. Log progress
7. Write discovered_apis.json
8. Report: N products scraped, M API endpoints found, K PDFs discovered
```

## Checkpointing

`load_existing_stems(manufacturer)` returns slugified device names already present in `scraper_raw/{manufacturer}/`. Claude checks this before scraping each product and skips duplicates. This allows:
- Resuming a session mid-manufacturer after a disconnection
- Running multiple sessions without duplication
- Overlapping with Python scraper output (same directory, same filenames)

## Limitations and trade-offs

- **Not automated**: requires Claude Code + Chrome running. Use for the 3-5 hardest manufacturers, not all 7.
- **Session-dependent**: HCP-gated content only accessible if user is logged in. Discovered API endpoints may require authentication tokens that expire.
- **Rate limiting**: Claude respects the same `request_delay` as the Python scrapers. The workflow doc specifies this per manufacturer.
- **Token cost**: a full manufacturer session (20-50 products) may use significant context. The workflow is designed to be incremental -- process one product at a time, write JSON immediately, so progress is never lost.
