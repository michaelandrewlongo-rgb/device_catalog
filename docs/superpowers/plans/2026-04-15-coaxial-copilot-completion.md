# Thrombectomy Coaxial Copilot Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill all dimensional data gaps in the thrombectomy coaxial compatibility tool so that `--gaps` returns zero missing devices, add a validation test suite, and add a `--case` query mode for clinical scenario lookup.

**Architecture:** Three phases: (1) Chrome MCP data acquisition for the 8 highest-priority missing devices, updating `thrombectomy_stack.json` directly, (2) a pytest validation suite that catches data integrity problems (missing fields, impossible dimensions, duplicate names), and (3) a new `--case` CLI mode that answers "I'm doing an M1 thrombectomy with a Solitaire X, what do I need?" by walking the stack backwards from device to sheath.

**Tech Stack:** Python 3, pytest, Chrome MCP (for scraping), JSON data file.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `pipeline/data/compatibility/thrombectomy_stack.json` | Modify | Fill gaps, add missing devices |
| `pipeline/compat_query.py` | Modify | Add `--case` mode, fuzzy name matching |
| `tests/test_compat.py` | Create | Data integrity and query logic tests |

---

## Task 1: Fill Critical Dimensional Gaps via Chrome MCP (Tier 1 — 8 devices)

**Purpose:** The 8 most clinically important devices with missing data. These block the most common stack queries. Each device requires navigating to the manufacturer product page via Chrome MCP, extracting ID/OD/length, and updating the JSON entry.

**Files:**
- Modify: `pipeline/data/compatibility/thrombectomy_stack.json`

**Devices to scrape (in priority order):**

| Device | Manufacturer | URL | Missing |
|---|---|---|---|
| AXS Catalyst 6 | Stryker | stryker.com/us/en/neurovascular/products/axs-catalyst.html | ID, OD, length |
| CereGlide 71 | Cerenovus | cerenovus.com or jnjmedtech.com neuro products | ID, OD |
| React 68 | Medtronic | medtronic.com neurovascular products | ID, OD, length |
| React 71 | Medtronic | (same page as React 68, different model) | ID, OD, length |
| Walrus BGC | Q'Apel Medical | qapelmedical.com | ID, OD, length |
| AXS Infinity LS | Stryker | stryker.com neurovascular products | ID, OD, length |
| Zoom 7X | Imperative Care | imperativecare.com/zoom | OD, length |
| RED 68 | Penumbra | penumbrainc.com reperfusion catheters | OD |

- [ ] **Step 1: Open Chrome and navigate to AXS Catalyst product page**

Use Chrome MCP `tabs_context_mcp` to get a tab, then `navigate` to Stryker's AXS Catalyst page. Use `get_page_text` or `read_page` to extract the spec table. Look for: inner diameter, outer diameter (distal and proximal), working length, sheath compatibility.

- [ ] **Step 2: Update the AXS Catalyst 6 entry in thrombectomy_stack.json**

Find the entry with `"name": "AXS Catalyst 6"` and replace the null values with scraped data. Set `"source": "chrome-mcp"` and add `"source_url"`.

- [ ] **Step 3: Repeat for CereGlide 71**

Navigate to Cerenovus/JNJ MedTech neurovascular product page. Extract CereGlide 71 ID, OD. Update the JSON entry.

- [ ] **Step 4: Repeat for React 68 and React 71**

Navigate to Medtronic neurovascular aspiration products. The React 68 and React 71 are likely on the same page. Extract ID, OD, length for both models. Update both JSON entries.

- [ ] **Step 5: Repeat for Walrus BGC**

Navigate to Q'Apel Medical product page. Extract ID, OD, length, sheath compatibility. Update JSON entry.

- [ ] **Step 6: Repeat for AXS Infinity LS**

Navigate to Stryker neurovascular long sheath product page. Extract ID, OD, length. Update JSON entry.

- [ ] **Step 7: Repeat for Zoom 7X**

Navigate to Imperative Care Zoom product page. Extract OD, length. Update JSON entry.

- [ ] **Step 8: Repeat for RED 68**

Navigate to Penumbra reperfusion catheter product page. Extract OD. Update JSON entry.

- [ ] **Step 9: Verify gap count reduced**

Run:
```bash
python -m pipeline.compat_query --gaps
```

Expected: The 8 devices above should no longer appear in the gaps list. Remaining gaps should be OD-only for guide catheters (which is acceptable since guide catheter OD is rarely the limiting dimension clinically) and working lengths for some microcatheters.

- [ ] **Step 10: Commit**

```bash
git add -f pipeline/data/compatibility/thrombectomy_stack.json
git commit -m "data: fill 8 critical dimensional gaps via Chrome MCP scraping"
```

---

## Task 2: Fill Remaining Minor Gaps (Tier 2 — lengths and guide ODs)

**Purpose:** Fill the remaining non-critical gaps: working lengths for microcatheters, aspiration catheter lengths, and guide catheter ODs. These are less blocking than Tier 1 but needed for a complete dataset.

**Files:**
- Modify: `pipeline/data/compatibility/thrombectomy_stack.json`

**Devices to fill:**

| Device | Missing | Likely source |
|---|---|---|
| Excelsior SL-10 | length | Stryker product page or Excelsior family knowledge file (already has OD) |
| Excelsior XT-17 | length | Same source |
| Excelsior XT-27 | length | Same source |
| Solitaire X | length | Medtronic product page |
| Penumbra ACE 64 | length | Penumbra product page |
| Penumbra ACE 68 | length | Penumbra product page |
| Q'Apel 072 | length | Q'Apel product page or FDA 510(k) |
| Esperance pHLO | length | Phenox/Wallaby product page |
| Guide catheter ODs | OD for Benchmark 6F, BMX81, BMX96, CEREBASE DA, Neuron MAX, FlowGate2 | Manufacturer pages; lower priority since guide OD is needed for sheath compatibility, not for coaxial nesting |

- [ ] **Step 1: Scrape microcatheter lengths from Stryker Excelsior product pages**

Navigate to the Stryker Excelsior product page. Find working lengths for SL-10, XT-17, XT-27. Update all three JSON entries.

- [ ] **Step 2: Scrape aspiration catheter lengths from Penumbra, Q'Apel, Phenox**

Navigate to each manufacturer's product page. Find working lengths for ACE 64, ACE 68, Q'Apel 072, Esperance pHLO. Update JSON entries.

- [ ] **Step 3: Scrape Solitaire X length from Medtronic**

Navigate to Medtronic Solitaire product page. Find overall length. Update JSON entry.

- [ ] **Step 4: Scrape guide catheter ODs where available**

Check manufacturer spec sheets for Benchmark 6F, BMX81, BMX96, CEREBASE DA, Neuron MAX, FlowGate2. Many guide catheter ODs are published as French sizes (e.g., "6F OD" = ~0.079"). Update JSON entries. If a spec sheet is not publicly available, mark the source as `"NEEDS_IFU"` and move on.

- [ ] **Step 5: Verify gap count**

Run:
```bash
python -m pipeline.compat_query --gaps
```

Expected: Zero or near-zero gaps. Any remaining should only be devices where the manufacturer does not publish specs publicly.

- [ ] **Step 6: Commit**

```bash
git add -f pipeline/data/compatibility/thrombectomy_stack.json
git commit -m "data: fill remaining dimensional gaps (lengths, guide ODs)"
```

---

## Task 3: Data Integrity Test Suite

**Purpose:** Catch broken JSON, impossible dimensions (OD > ID, negative clearance), duplicate device names, and missing required fields. This prevents regressions when adding new devices.

**Files:**
- Create: `tests/test_compat.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_compat.py`:

```python
"""Tests for thrombectomy coaxial compatibility data and query logic."""
import json
import pytest
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "pipeline" / "data" / "compatibility" / "thrombectomy_stack.json"


@pytest.fixture
def devices():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return [d for d in data["devices"] if "_section" not in d]


def test_json_loads_without_error():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "devices" in data
    assert "_meta" in data


def test_no_duplicate_names(devices):
    names = [d["name"] for d in devices]
    dupes = [n for n in names if names.count(n) > 1]
    assert dupes == [], f"Duplicate device names: {set(dupes)}"


def test_required_fields_present(devices):
    required = ["name", "manufacturer", "category"]
    for d in devices:
        for field in required:
            assert field in d and d[field], f"{d.get('name', '?')} missing {field}"


def test_id_greater_than_od_where_both_present(devices):
    """A catheter's ID must be less than its OD -- if not, data is swapped."""
    for d in devices:
        id_val = d.get("id_inch")
        od_val = d.get("od_inch")
        if id_val is not None and od_val is not None:
            assert id_val < od_val, (
                f"{d['name']}: ID ({id_val}) >= OD ({od_val}) -- dimensions likely swapped"
            )


def test_od_prox_gte_od_distal_where_both_present(devices):
    """Proximal OD should be >= distal OD (catheters taper distally)."""
    for d in devices:
        od = d.get("od_inch")
        od_p = d.get("od_prox_inch")
        if od is not None and od_p is not None:
            assert od_p >= od, (
                f"{d['name']}: proximal OD ({od_p}) < distal OD ({od}) -- unexpected"
            )


def test_dimensions_in_reasonable_range(devices):
    """Catch obviously wrong values (e.g., someone enters mm instead of inches)."""
    for d in devices:
        for field in ["id_inch", "od_inch", "od_prox_inch"]:
            val = d.get(field)
            if val is not None:
                assert 0.010 < val < 0.200, (
                    f"{d['name']}.{field} = {val} -- outside 0.010-0.200\" range, likely wrong units"
                )


def test_lengths_are_positive(devices):
    for d in devices:
        lengths = d.get("length_cm")
        if lengths:
            for l in lengths:
                assert l > 0, f"{d['name']} has non-positive length: {l}"


def test_source_field_present(devices):
    for d in devices:
        assert "source" in d, f"{d['name']} missing source field"


def test_at_least_30_devices(devices):
    """Guard against accidental data loss."""
    assert len(devices) >= 30, f"Only {len(devices)} devices -- expected at least 30"


def test_all_categories_represented(devices):
    categories = {d["category"] for d in devices}
    expected = {"guide_catheter", "intermediate", "aspiration", "microcatheter", "stent_retriever"}
    assert expected.issubset(categories), f"Missing categories: {expected - categories}"
```

- [ ] **Step 2: Run the tests**

```bash
python -m pytest tests/test_compat.py -v
```

Expected: All tests pass. If `test_id_greater_than_od_where_both_present` fails, a device has swapped ID/OD -- fix the JSON data.

- [ ] **Step 3: Commit**

```bash
git add tests/test_compat.py
git commit -m "test: add data integrity tests for coaxial compatibility matrix"
```

---

## Task 4: Add `--case` Query Mode

**Purpose:** The current `--stack` query takes a single device and shows what fits. The `--case` mode takes a clinical scenario (thrombectomy device + approach) and walks the full stack backwards: device -> microcatheter -> intermediate -> guide -> sheath. This is the query a clinician actually asks at 2am.

**Files:**
- Modify: `pipeline/compat_query.py`

- [ ] **Step 1: Add the build_case function to compat_query.py**

Add this function after `build_stack`:

```python
def build_case(device_name, devices):
    """Build complete access stack backwards from a thrombectomy device or aspiration catheter."""
    target = next((d for d in devices if d["name"].lower() == device_name.lower()), None)
    if not target:
        print(f"Device not found: {device_name}")
        print(f"Available: {', '.join(d['name'] for d in devices)}")
        return

    print(f"\n  Full access stacks for: {target['name']} ({target['manufacturer']})")
    print(f"  {'='*70}")

    role = target.get("role", "")

    if role == "thrombectomy_device":
        # Stent retriever: find compatible microcatheters
        min_cath_id = target.get("min_catheter_id_inch")
        if not min_cath_id:
            print(f"  {target['name']}: minimum catheter ID unknown")
            return

        compatible_micros = []
        for d in devices:
            if d.get("role") != "delivery_microcatheter":
                continue
            d_id = d.get("id_inch")
            if d_id is not None and d_id >= min_cath_id:
                compatible_micros.append(d)

        if not compatible_micros:
            print("  No compatible delivery microcatheters found")
            return

        for mc in compatible_micros:
            mc_od = mc.get("od_prox_inch") or mc.get("od_inch")
            if mc_od is None:
                continue
            # Find intermediates/guides that accept this microcatheter
            accepting = []
            for d in devices:
                if d.get("role") in ("intermediate_catheter", "large_bore_intermediate",
                                     "guide_catheter", "balloon_guide_catheter"):
                    d_id = d.get("id_inch")
                    if d_id is not None and d_id > mc_od:
                        accepting.append(d)
            # Group by role
            intermediates = [d for d in accepting if "intermediate" in d.get("role", "")]
            guides = [d for d in accepting if "guide" in d.get("role", "")]

            print(f"\n  Via {mc['name']} (ID={mc['id_inch']}\", OD={mc_od}\"):")
            if intermediates:
                for inter in intermediates:
                    inter_od = inter.get("od_prox_inch") or inter.get("od_inch")
                    # Find guides that accept this intermediate
                    inter_guides = []
                    if inter_od:
                        for g in devices:
                            if "guide" in g.get("role", ""):
                                g_id = g.get("id_inch")
                                if g_id is not None and g_id > inter_od:
                                    inter_guides.append(g)
                    inter_id_str = f"ID={inter['id_inch']}\"" if inter.get("id_inch") else "ID=?"
                    inter_od_str = f"OD={inter_od}\"" if inter_od else "OD=?"
                    guide_names = ", ".join(g["name"] for g in inter_guides) if inter_guides else "guide TBD"
                    print(f"    [{guide_names}] -> {inter['name']} ({inter_id_str}) -> {mc['name']} -> {target['name']}")
            if guides:
                # Direct: guide -> microcatheter (no intermediate)
                for g in guides:
                    print(f"    [{g['name']}] -> {mc['name']} -> {target['name']}  (no intermediate)")

    elif role == "aspiration_catheter":
        # Aspiration catheter: find what it fits inside
        asp_od = target.get("od_prox_inch") or target.get("od_inch")
        if asp_od is None:
            print(f"  {target['name']}: OD unknown, cannot determine compatible guides/intermediates")
            return

        # Find intermediates and guides that accept this aspiration catheter
        intermediates = []
        guides = []
        for d in devices:
            d_id = d.get("id_inch")
            if d_id is None or d_id <= asp_od:
                continue
            if "intermediate" in d.get("role", ""):
                intermediates.append(d)
            elif "guide" in d.get("role", ""):
                guides.append(d)

        print(f"\n  ADAPT (direct aspiration) with {target['name']} (OD={asp_od}\"):")
        if intermediates:
            for inter in intermediates:
                inter_od = inter.get("od_prox_inch") or inter.get("od_inch")
                inter_guides = []
                if inter_od:
                    for g in devices:
                        if "guide" in g.get("role", ""):
                            g_id = g.get("id_inch")
                            if g_id is not None and g_id > inter_od:
                                inter_guides.append(g)
                guide_names = ", ".join(g["name"] for g in inter_guides) if inter_guides else "guide TBD"
                print(f"    [{guide_names}] -> {inter['name']} -> {target['name']}")
        if guides:
            for g in guides:
                print(f"    [{g['name']}] -> {target['name']}  (direct, no intermediate)")
    else:
        print(f"  {target['name']} is not a thrombectomy device or aspiration catheter.")
        print(f"  Use --stack for intermediate/guide queries, or --fits-through / --accepts.")
```

- [ ] **Step 2: Wire `--case` into the argument parser**

In the `main()` function, add the argument and dispatch:

```python
parser.add_argument("--case", metavar="DEVICE", help="Build full access stack backwards from a thrombectomy device or aspiration catheter")
```

And in the dispatch block, add before the final `else`:
```python
elif args.case:
    build_case(args.case, devices)
```

- [ ] **Step 3: Test the --case mode**

Run:
```bash
python -m pipeline.compat_query --case "Trevo NXT"
python -m pipeline.compat_query --case "Penumbra JET 7X"
```

Expected for Trevo NXT: Shows stacks like `[BMX96] -> CereGlide 92 -> Trevo Trak 21 -> Trevo NXT` and `[BMX81] -> SOFIA 6F -> Marksman -> Trevo NXT`.

Expected for JET 7X: Shows ADAPT stacks like `[BMX96] -> CereGlide 92 -> JET 7X` and `[BMX81] -> JET 7X (direct)`.

- [ ] **Step 4: Commit**

```bash
git add pipeline/compat_query.py
git commit -m "feat: add --case mode for full access stack lookup from device to sheath"
```

---

## Task 5: Add Fuzzy Name Matching

**Purpose:** Clinicians will type "catalyst 7" not "AXS Catalyst 7 (068)". Add case-insensitive substring matching so partial names work.

**Files:**
- Modify: `pipeline/compat_query.py`

- [ ] **Step 1: Add a fuzzy lookup helper**

Add this function near the top of the file, after `load_devices`:

```python
def find_device(name, devices):
    """Find a device by exact match, then case-insensitive, then substring."""
    # Exact match
    match = next((d for d in devices if d["name"] == name), None)
    if match:
        return match
    # Case-insensitive match
    match = next((d for d in devices if d["name"].lower() == name.lower()), None)
    if match:
        return match
    # Substring match
    candidates = [d for d in devices if name.lower() in d["name"].lower()]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        print(f"  Ambiguous name '{name}'. Did you mean:")
        for c in candidates:
            print(f"    - {c['name']}")
        return None
    print(f"  Device not found: {name}")
    print(f"  Available: {', '.join(d['name'] for d in devices)}")
    return None
```

- [ ] **Step 2: Replace all `next((d for d in devices if d["name"].lower() == ...` calls**

In `find_fits_through`, `find_accepts`, `build_stack`, and `build_case`, replace the inline device lookup with `find_device(target_name, devices)`. Each function currently has a pattern like:

```python
target = next((d for d in devices if d["name"].lower() == target_name.lower()), None)
if not target:
    print(f"Device not found: {target_name}")
    ...
    return
```

Replace with:

```python
target = find_device(target_name, devices)
if not target:
    return
```

- [ ] **Step 3: Test fuzzy matching**

Run:
```bash
python -m pipeline.compat_query --fits-through "catalyst 7"
python -m pipeline.compat_query --stack "sofia 6"
python -m pipeline.compat_query --case "solitaire"
python -m pipeline.compat_query --case "catalyst"
```

Expected: First three resolve to the correct device. Last one should print "Ambiguous name 'catalyst'. Did you mean: AXS Catalyst 6, AXS Catalyst 7 (068)".

- [ ] **Step 4: Commit**

```bash
git add pipeline/compat_query.py
git commit -m "feat: add fuzzy name matching for device lookups"
```

---

## Task 6: Update STATE.md and ROADMAP.md

**Purpose:** Record the coaxial copilot as a new catalog feature and update project state.

**Files:**
- Modify: `STATE.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Update STATE.md**

Add to the top of STATE.md:

```markdown
I was trying to:
Build the thrombectomy coaxial copilot -- a tool that answers "what fits through what" for neurointerventional device stacks.

The last thing I saw:
Copilot has 34+ devices across 5 categories. --case mode walks the full stack backwards from device to sheath. Fuzzy name matching works. Test suite passes.

What I want next:
1. Extend to flow diverter deployment stacks (reuse the same JSON schema and query tool)
2. Add SOFIA Plus, Headway 21/27 to compatibility data
3. Consider extracting ID/OD as structured fields in knowledge files for automatic sync
```

- [ ] **Step 2: Update ROADMAP.md**

Add a new section after the current highest priority:

```markdown
### 0.5. Coaxial Compatibility Copilot
Status: **Experimental — thrombectomy stack complete**

- `python -m pipeline.compat_query --case "Trevo NXT"` shows full access stacks
- 34 devices: 8 guide catheters, 6 intermediates, 12 aspiration, 5 microcatheters, 3 stent retrievers
- Data in `pipeline/data/compatibility/thrombectomy_stack.json`
- Tests in `tests/test_compat.py`
- Next: extend to flow diverter stacks, add remaining devices (SOFIA Plus, Headway family)
```

- [ ] **Step 3: Commit**

```bash
git add STATE.md ROADMAP.md
git commit -m "docs: update STATE.md and ROADMAP.md with coaxial copilot status"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| Fill all critical dimensional gaps | Task 1 (8 devices via Chrome MCP) |
| Fill remaining minor gaps | Task 2 (lengths, guide ODs) |
| Data integrity tests | Task 3 (pytest suite) |
| Clinical scenario query mode | Task 4 (`--case`) |
| Usability (partial names) | Task 5 (fuzzy matching) |
| Project state documentation | Task 6 (STATE.md, ROADMAP.md) |

**Placeholder scan:** No TBDs in code blocks. All code is complete. Chrome MCP steps are intentionally procedural (navigate, extract, update JSON) because the exact page structure varies by manufacturer.

**Type consistency:** `find_device` returns the same dict type as the inline `next()` calls it replaces. All functions already handle `None` returns.

**Scope note:** Tasks 1 and 2 are the most time-intensive (Chrome MCP scraping is serial and manufacturer-dependent). If a manufacturer page is bot-protected or doesn't publish specs, mark the device as `"source": "NEEDS_IFU"` and move on rather than blocking the commit.
