# Chrome-Assisted Scraping Workflow

Guide for Claude Code sessions using Chrome DevTools MCP to scrape manufacturer sites.

## Before Starting

1. Check existing progress:
```bash
python -c "from pipeline.scrapers.chrome_assisted import print_session_status; print_session_status('MANUFACTURER')"
```

2. Load Chrome MCP tools:
```
ToolSearch: select:mcp__claude-in-chrome__tabs_context_mcp
ToolSearch: select:mcp__claude-in-chrome__navigate
ToolSearch: select:mcp__claude-in-chrome__get_page_text
ToolSearch: select:mcp__claude-in-chrome__read_page
ToolSearch: select:mcp__claude-in-chrome__javascript_tool
ToolSearch: select:mcp__claude-in-chrome__read_network_requests
ToolSearch: select:mcp__claude-in-chrome__find
ToolSearch: select:mcp__claude-in-chrome__tabs_create_mcp
```

3. Get tab context and create a fresh tab:
```
mcp__claude-in-chrome__tabs_context_mcp(createIfEmpty=true)
mcp__claude-in-chrome__tabs_create_mcp(url="about:blank")
```

## Per-Product Extraction Protocol

For every product page, follow these steps in order:

### Step 1: Navigate
```
navigate(tabId, url)
```
Wait for page to load.

### Step 2: Expand all collapsed content
```javascript
// Run via javascript_tool
(function() {
  // Click all tabs, accordions, expandable elements
  document.querySelectorAll(
    '[role="tab"], .accordion-button, [data-toggle="collapse"], ' +
    '[data-bs-toggle="collapse"], [aria-expanded="false"], ' +
    '.tab-link, .expandable, details summary, ' +
    '.product-tab, .spec-tab, [data-tab]'
  ).forEach(function(el) { try { el.click(); } catch(e) {} });

  // Open all <details> elements
  document.querySelectorAll('details:not([open])').forEach(function(d) { d.open = true; });

  // Return count of elements clicked
  return document.querySelectorAll('[aria-expanded="true"]').length;
})();
```
Wait ~1 second, then run again to catch nested collapses.

### Step 3: Intercept network requests
```
read_network_requests(tabId, pattern="json")
```
Look for XHR/fetch calls returning JSON with product data. Record any promising endpoints.

### Step 4: Read page content
```
get_page_text(tabId)   -- clean text for field extraction
read_page(tabId)       -- full DOM for PDF link discovery
```

### Step 5: Extract fields

From the page text, extract these `ScrapedProduct` fields:
- `device_name`: H1 title or product name
- `what_it_is`: Overview/description section
- `sizing_specs`: Specifications/dimensions/sizing table content
- `indications`: Indications for use / intended use section
- `contraindications`: If present
- `compatible_with`: Compatible devices/instruments
- `use_notes`: Procedural or clinical details
- `also_known_as`: Alternate names, abbreviations
- `category_hint`: Use the category patterns from the manufacturer section below

From the DOM, extract:
- `source_url`: The current page URL
- `ifu_pdf_url`: First PDF link containing "ifu", "instructions", or "directions"
- `other_pdf_urls`: Other PDF links, keyed by type (brochure, technique, etc.)

### Step 6: Save product
```bash
python -c "
import json
from pipeline.scrapers.chrome_assisted import save_chrome_product
data = json.loads('''
{JSON_DATA_HERE}
''')
print(save_chrome_product(data))
"
```

### Step 7: Rate limiting
Wait 3-4 seconds before navigating to the next product page.

---

## Manufacturer: Medtronic

**Priority**: Highest (current yield: 3 hardcoded fallback URLs)

**Listing URL**: `https://www.medtronic.com/us-en/healthcare-professionals/products/neurological.html`

**Strategy**: Network interception first. The React SPA loads product data from an internal API. Check `read_network_requests` after the listing page loads. Look for JSON responses containing arrays of product objects.

If an API is found, extract all product URLs from it rather than crawling the DOM.

**Product link pattern**: Path contains `/healthcare-professionals/products/neurological/`

**Category patterns**:
| Pattern | Category |
|---------|----------|
| solitaire, thrombectomy, revascularization | thrombectomy |
| pipeline, flow divert | flow-diverter |
| onyx, liquid embolic | liquid-embolic |
| react, aspiration, riptide | aspiration |
| echelon, phenom, marksman, microcatheter | microcatheter |
| strata, shunt, valve | csf-shunt |
| stealth, navigation | navigation |

**Tab expansion**: Product pages use tabbed panels: "Overview", "Specifications", "Resources", "Ordering Information". Click all tabs before reading.

**HCP gate**: Some IFU PDFs require HCP login. If user is authenticated in Chrome, these are accessible. If not, log `ifu_pdf_url` as null and note the gated URL in `use_notes`.

**Known products to look for**:
- Pipeline Flex Embolization Device (flow-diverter)
- Pipeline Vantage (flow-diverter)
- Solitaire X Revascularization Device (thrombectomy)
- Onyx Liquid Embolic System (liquid-embolic)
- Echelon / Phenom microcatheters (microcatheter)
- Marksman Microcatheter (microcatheter)
- React aspiration catheter (aspiration)
- Riptide aspiration system (aspiration)
- Strata family valves (csf-shunt)

---

## Manufacturer: Cerenovus (J&J MedTech)

**Priority**: High (current yield: 3 seed landing pages, no product detail pages scraped)

**Listing URLs**:
- `https://www.jnjmedtech.com/en-US/companies/cerenovus`
- `https://www.jnjmedtech.com/en-US/specialties/neurointerventional/`
- `https://www.jnjmedtech.com/en-US/cerenovus-stroke-solutions`

**Strategy**: Network interception on landing pages. J&J sites typically call internal catalog APIs. Also follow DOM links containing product segment keywords.

**Product link segments**: `cerenovus`, `embotrap`, `galaxy`, `cereglide`, `trufill`, `bravo`, `emboguard`

**Category patterns**:
| Pattern | Category |
|---------|----------|
| embotrap, thrombectomy, revascularization | thrombectomy |
| galaxy, coil, emboliz | embolic-coil |
| cereglide, aspiration, intermediate | distal-access |
| trufill, nbca, liquid | liquid-embolic |
| bravo, flow divert | flow-diverter |
| emboguard, balloon | balloon-catheter |

**Known products to look for**:
- EmboTrap III Revascularization Device (thrombectomy)
- Galaxy G3 Mini Coil System (embolic-coil)
- CereGlide Aspiration Catheter (distal-access)
- Trufill n-BCA Liquid Embolic (liquid-embolic)
- Bravo Flow Diverter (flow-diverter)
- EmboGuard Balloon (balloon-catheter)

---

## Manufacturer: Stryker

**Priority**: High (current yield: discovery mostly fails, 2 fallback URLs)

**Listing URLs**:
- `https://neurosurgical.stryker.com/products/`
- `https://www.stryker.com/us/en/portfolios/neurotechnology-and-spine/neurovascular.html`

**Strategy**: `neurosurgical.stryker.com` is less JS-heavy; Chrome reliably gets links. `stryker.com/neurotechnology` has portfolio tiles requiring JS click. Navigate both.

**Product link keywords**: `/neurovascular`, `/trevo`, `/surpass`, `/target`, `/excelsior`, `/synchro`, `/axs`, `/neuroform`

**Exclude**: `/privacy`, `/contact`, `/news`, `/careers`, `/about`, `/investor`

**Category patterns**:
| Pattern | Category |
|---------|----------|
| trevo, thrombectomy, revascularization, stroke retriev | thrombectomy |
| surpass, flow divert | flow-diverter |
| neuroform, atlas stent, stent | intracranial-stent |
| target, coil, detachable coil | embolic-coil |
| excelsior, sl-10, microcatheter | microcatheter |
| axs, catalyst, distal access | distal-access |
| synchro, guidewire | guidewire |

**Tab expansion**: Product detail pages have "Specifications" tab. Click it before reading sizing data.

**Known products to look for**:
- Surpass Evolve Flow Diverter (flow-diverter)
- Surpass Streamline (flow-diverter)
- Trevo XP ProVue Retriever (thrombectomy)
- Neuroform Atlas Stent (intracranial-stent)
- Target XL / Nano / 360 / Helical coils (embolic-coil)
- Excelsior SL-10 / XT-17 / XT-27 (microcatheter)
- AXS Catalyst / Vecta (distal-access)
- Synchro guidewires (guidewire)

---

## Manufacturer: Terumo Neuro / MicroVention

**Priority**: Medium (fallback list has 22 products; tabs hide specs)

**Listing URL**: `https://www.terumoneuro.com/products`

**Strategy**: Navigate listing to find any products missing from the fallback list. Main win: click spec/ordering tabs on each product page to capture sizing tables that the Python scraper misses.

**Tab expansion**: Look for "Product Codes", "Specifications", "Ordering Information" tabs. These contain the sizing tables.

**Category patterns**:
| Pattern | Category |
|---------|----------|
| fred, flow diverter, flow diversion | flow-diverter |
| lvis, coil assist stent, stent | intracranial-stent |
| web, intrasaccular, woven endobridge | intrasaccular |
| hydrocoil, cosmos, hydroframe, hydrosoft, hypersoft, vfc, coil | embolic-coil |
| headway, via, microcatheter | microcatheter |
| sofia, intermediate catheter, distal access, support catheter | distal-access |
| scepter, balloon catheter, occlusion balloon | balloon-catheter |
| bobby, balloon guide catheter | balloon-guide-catheter |
| eric, retrieval device, stent retriever | stent-retriever |
| headliner, traxcess, guidewire, microwire | guidewire |

---

## Manufacturer: Balt

**Priority**: Medium (intermittent blocking; see balt_failures logs)

**Listing URL**: `https://baltgroup.com/products/`

**Strategy**: Chrome with real fingerprint resolves the bot blocking that causes intermittent failures with StealthyFetcher.

**Product link pattern**: `/products/` path prefix on `baltgroup.com`

**Category patterns**:
| Pattern | Category |
|---------|----------|
| silk, flow divert | flow-diverter |
| optima, coil, embolization coil | embolic-coil |
| raptor, aspiration | aspiration |
| carrier, microcatheter | microcatheter |
| leo, stent | intracranial-stent |

---

## Manufacturer: Penumbra

**Priority**: Lower (existing scraper yields reasonable data)

**Listing URL**: `https://www.penumbrainc.com/neuro/`

**Strategy**: Only use Chrome for specific products that failed in the automated run. Check `pipeline/data/scraper_raw/penumbra/failed_urls.txt` for URLs to retry.

---

## Manufacturer: Integra

**Priority**: Lower (existing scraper works for neurosurgical catalog)

**Listing URL**: `https://products.integralife.com/neuro/category/for-the-neurosurgeon`

**Strategy**: Only use Chrome for specific gaps. The Integra scraper filters by neurointerventional terms, so most neurosurgical products (dural substitutes, CSF shunts, monitoring) are already captured.

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

---

## After the Session

1. Review scraped products:
```bash
python -c "from pipeline.scrapers.chrome_assisted import print_session_status; print_session_status('MANUFACTURER')"
```

2. Review discovered APIs:
```bash
cat pipeline/data/scraper_raw/MANUFACTURER/discovered_apis.json
```

3. Run the merger to integrate new data:
```bash
python -m pipeline.run_pipeline --merge-only
```

4. Review drafts in `pipeline/data/drafts/` and move approved files to catalog root.
