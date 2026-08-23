# Device Catalog Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static HTML prototype that compiles 213 curated knowledge files into a searchable, browsable web app with split-panel layout and in-panel device comparison.

**Architecture:** A Python build script (`pipeline/build_site.py`) reads all `*--knowledge.md` files from the catalog root, parses them into structured device records, and writes a single self-contained `site/index.html` with the catalog data inlined as JSON. The frontend is plain HTML/CSS/JS using Fuse.js for fuzzy search and marked.js for markdown rendering — no server, no build toolchain.

**Tech Stack:** Python 3.10+ (build script), Fuse.js v7 (CDN), marked.js v12 (CDN), plain HTML/CSS/JS

---

## File Structure

| Path | Purpose |
|------|---------|
| `pipeline/build_site.py` | Build script: parse files → generate `site/index.html` |
| `pipeline/site_template.html` | Full HTML/CSS/JS app template (data injected at build time) |
| `tests/test_build_site.py` | Unit + integration tests for the build script |
| `site/index.html` | Generated output — open in any browser |

**Note:** `site/` should be added to `.gitignore` or committed as a build artifact — your choice.

**Deviation from spec:** `catalog.json` is inlined into `index.html` rather than served as a separate file. This is required for the app to work when opened via `file://` URL without a local server. The data is still valid JSON, just embedded in a `<script>` tag.

---

## Task 1: `parse_filename`

**Files:**
- Create: `pipeline/build_site.py`
- Create: `tests/test_build_site.py`

- [ ] **Step 1: Create `tests/test_build_site.py` with failing tests**

```python
# tests/test_build_site.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.build_site import parse_filename


def test_parse_filename_standard():
    result = parse_filename("flow-diverter--medtronic--pipeline-flex-shield--knowledge.md")
    assert result == {
        "id": "flow-diverter--medtronic--pipeline-flex-shield",
        "category": "flow-diverter",
        "manufacturer": "medtronic",
        "slug": "pipeline-flex-shield",
    }


def test_parse_filename_manufacturer_with_hyphens():
    result = parse_filename("aspiration--imperative-care-inc--zoom-71--knowledge.md")
    assert result is not None
    assert result["manufacturer"] == "imperative-care-inc"
    assert result["slug"] == "zoom-71"


def test_parse_filename_multi_word_slug():
    result = parse_filename("embolic-coil--stryker--target-detachable-coil--knowledge.md")
    assert result is not None
    assert result["category"] == "embolic-coil"
    assert result["manufacturer"] == "stryker"
    assert result["slug"] == "target-detachable-coil"


def test_parse_filename_not_knowledge_file():
    assert parse_filename("flow-diverter--medtronic--pipeline.pdf") is None


def test_parse_filename_wrong_suffix():
    assert parse_filename("flow-diverter--medtronic--pipeline--brochure.pdf") is None


def test_parse_filename_too_few_parts():
    # Only two segments before --knowledge.md — no slug
    assert parse_filename("flow-diverter--medtronic--knowledge.md") is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/Michael/documents/device_catalog
python -m pytest tests/test_build_site.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'pipeline.build_site'`

- [ ] **Step 3: Create `pipeline/build_site.py` with `parse_filename`**

```python
# pipeline/build_site.py
from pathlib import Path
import json
import re


def parse_filename(filename: str) -> dict | None:
    """Parse device metadata from a knowledge filename.

    Input:  "flow-diverter--medtronic--pipeline-flex-shield--knowledge.md"
    Output: {"id": "flow-diverter--medtronic--pipeline-flex-shield",
             "category": "flow-diverter", "manufacturer": "medtronic",
             "slug": "pipeline-flex-shield"}
    Returns None if the filename is not a knowledge file or has too few parts.
    """
    if not filename.endswith("--knowledge.md"):
        return None
    stem = filename[: -len("--knowledge.md")]
    parts = stem.split("--")
    if len(parts) < 3:
        return None
    category = parts[0]
    manufacturer = parts[1]
    slug = "--".join(parts[2:])
    return {
        "id": stem,
        "category": category,
        "manufacturer": manufacturer,
        "slug": slug,
    }
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_build_site.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_site.py tests/test_build_site.py
git commit -m "feat(prototype): add parse_filename for knowledge file metadata"
```

---

## Task 2: `parse_markdown` + `_parse_aliases`

**Files:**
- Modify: `pipeline/build_site.py` (add two functions)
- Modify: `tests/test_build_site.py` (add tests)

- [ ] **Step 1: Add failing tests to `tests/test_build_site.py`**

Append to the existing test file:

```python
from pipeline.build_site import parse_markdown


def test_parse_markdown_extracts_name():
    content = "# Pipeline Flex Embolization Device\n\n**Manufacturer:** Medtronic\n"
    name, sections, aliases = parse_markdown(content)
    assert name == "Pipeline Flex Embolization Device"


def test_parse_markdown_extracts_sections():
    content = (
        "# Device\n\n"
        "## What It Is\n\nFlow diverter text.\n\n"
        "## Sizing\n\n| Diameter | Length |\n|---|---|\n| 3mm | 20mm |"
    )
    name, sections, aliases = parse_markdown(content)
    assert sections["What It Is"] == "Flow diverter text."
    assert "3mm" in sections["Sizing"]


def test_parse_markdown_aliases_comma_separated():
    content = "# Device\n\n## Also Known As\n\nPipeline, PED, Pipeline Flex"
    _, _, aliases = parse_markdown(content)
    assert aliases == ["Pipeline", "PED", "Pipeline Flex"]


def test_parse_markdown_aliases_list_format():
    content = "# Device\n\n## Also Known As\n\n- Pipeline\n- PED\n- Pipeline Shield"
    _, _, aliases = parse_markdown(content)
    assert aliases == ["Pipeline", "PED", "Pipeline Shield"]


def test_parse_markdown_no_aliases():
    content = "# Device\n\n## What It Is\n\nSome text."
    _, _, aliases = parse_markdown(content)
    assert aliases == []


def test_parse_markdown_no_h1():
    content = "## What It Is\n\nText here."
    name, sections, _ = parse_markdown(content)
    assert name == ""
    assert sections["What It Is"] == "Text here."


def test_parse_markdown_section_content_stripped():
    content = "# D\n\n## What It Is\n\n\nText with leading blank.\n\n"
    _, sections, _ = parse_markdown(content)
    assert sections["What It Is"] == "Text with leading blank."
```

- [ ] **Step 2: Run to confirm failures**

```bash
python -m pytest tests/test_build_site.py -v -k "markdown or aliases"
```

Expected: `ImportError` (function not yet defined)

- [ ] **Step 3: Add `parse_markdown` and `_parse_aliases` to `pipeline/build_site.py`**

Append after `parse_filename`:

```python
def parse_markdown(content: str) -> tuple[str, dict, list[str]]:
    """Parse a knowledge markdown file into (name, sections, aliases).

    name     -- text of the H1 heading (empty string if absent)
    sections -- dict of H2 heading text -> section body (raw markdown, stripped)
    aliases  -- list extracted from the "Also Known As" section
    """
    lines = content.split("\n")
    name: str = ""
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            name = line[2:].strip()
        elif line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    aliases = _parse_aliases(sections.get("Also Known As", ""))
    return name, sections, aliases


def _parse_aliases(text: str) -> list[str]:
    """Extract alias strings from an Also Known As section body."""
    stripped = text.strip()
    if not stripped:
        return []
    # List format: lines starting with "- "
    if stripped.startswith("-"):
        return [
            line.lstrip("-").strip()
            for line in stripped.split("\n")
            if line.strip().startswith("-")
        ]
    # Comma-separated (possibly multi-line)
    flat = stripped.replace("\n", ", ")
    return [a.strip() for a in flat.split(",") if a.strip()]
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_build_site.py -v
```

Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_site.py tests/test_build_site.py
git commit -m "feat(prototype): add parse_markdown and alias extractor"
```

---

## Task 3: `slug_to_title`, `DOMAIN_MAP`, `map_domain`

**Files:**
- Modify: `pipeline/build_site.py`
- Modify: `tests/test_build_site.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_build_site.py`:

```python
from pipeline.build_site import slug_to_title, map_domain


def test_slug_to_title_simple():
    assert slug_to_title("flow-diverter") == "Flow Diverter"


def test_slug_to_title_special_abbreviations():
    assert slug_to_title("csf-shunt") == "CSF Shunt"
    assert slug_to_title("sacroiliac-fusion") == "Sacroiliac Fusion"


def test_slug_to_title_manufacturer_with_inc():
    assert slug_to_title("imperative-care-inc") == "Imperative Care Inc"


def test_slug_to_title_single_word():
    assert slug_to_title("medtronic") == "Medtronic"


def test_map_domain_neurovascular():
    for cat in ["flow-diverter", "microcatheter", "aspiration", "distal-access",
                "embolic-coil", "intracranial-stent", "stent-retriever",
                "thrombectomy", "intrasaccular", "liquid-embolic",
                "balloon-catheter", "balloon-guide-catheter",
                "guidewire", "guiding-catheter", "delivery-catheter",
                "aspiration-catheter"]:
        assert map_domain(cat) == "neurovascular", f"Expected neurovascular for {cat}"


def test_map_domain_spine():
    for cat in ["pedicle-screw", "interbody-cage", "cervical-cage",
                "cervical-plate", "corpectomy", "sacroiliac-fusion", "cervical-disc"]:
        assert map_domain(cat) == "spine", f"Expected spine for {cat}"


def test_map_domain_cranial():
    for cat in ["csf-shunt", "dural-sealant", "dural-substitute", "navigation"]:
        assert map_domain(cat) == "cranial", f"Expected cranial for {cat}"


def test_map_domain_other_for_unknown():
    assert map_domain("unknown") == "other"
    assert map_domain("accessory") == "other"
    assert map_domain("not-a-real-category") == "other"
```

- [ ] **Step 2: Run to confirm failures**

```bash
python -m pytest tests/test_build_site.py -v -k "slug or domain"
```

Expected: `ImportError`

- [ ] **Step 3: Add to `pipeline/build_site.py`**

Append after `_parse_aliases`:

```python
_SPECIAL_WORDS: dict[str, str] = {
    "csf": "CSF",
    "si":  "SI",
    "vrd": "VRD",
    "tlif": "TLIF",
    "llif": "LLIF",
    "alif": "ALIF",
    "acdf": "ACDF",
    "nbca": "NBCA",
    "llc":  "LLC",
    "inc":  "Inc",
    "ltd":  "Ltd",
    "co":   "Co",
}


def slug_to_title(slug: str) -> str:
    """Convert 'flow-diverter' → 'Flow Diverter', 'csf-shunt' → 'CSF Shunt'."""
    return " ".join(
        _SPECIAL_WORDS.get(w, w.title()) for w in slug.split("-")
    )


DOMAIN_MAP: dict[str, str] = {
    "flow-diverter":        "neurovascular",
    "microcatheter":        "neurovascular",
    "aspiration":           "neurovascular",
    "aspiration-catheter":  "neurovascular",
    "distal-access":        "neurovascular",
    "embolic-coil":         "neurovascular",
    "intracranial-stent":   "neurovascular",
    "stent-retriever":      "neurovascular",
    "thrombectomy":         "neurovascular",
    "intrasaccular":        "neurovascular",
    "liquid-embolic":       "neurovascular",
    "balloon-catheter":     "neurovascular",
    "balloon-guide-catheter": "neurovascular",
    "guidewire":            "neurovascular",
    "guiding-catheter":     "neurovascular",
    "delivery-catheter":    "neurovascular",
    "pedicle-screw":        "spine",
    "interbody-cage":       "spine",
    "cervical-cage":        "spine",
    "cervical-plate":       "spine",
    "corpectomy":           "spine",
    "sacroiliac-fusion":    "spine",
    "cervical-disc":        "spine",
    "csf-shunt":            "cranial",
    "dural-sealant":        "cranial",
    "dural-substitute":     "cranial",
    "navigation":           "cranial",
}


def map_domain(category: str) -> str:
    """Return the top-level clinical domain for a device category slug."""
    return DOMAIN_MAP.get(category, "other")
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python -m pytest tests/test_build_site.py -v
```

Expected: `24 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_site.py tests/test_build_site.py
git commit -m "feat(prototype): add slug_to_title, DOMAIN_MAP, map_domain"
```

---

## Task 4: `load_devices`

**Files:**
- Modify: `pipeline/build_site.py`
- Modify: `tests/test_build_site.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_build_site.py`:

```python
import tempfile
from pipeline.build_site import load_devices


def test_load_devices_basic(tmp_path):
    (tmp_path / "flow-diverter--medtronic--pipeline-flex--knowledge.md").write_text(
        "# Pipeline Flex\n\n## What It Is\n\nFlow diverter.\n\n## Also Known As\n\nPipeline, PED",
        encoding="utf-8",
    )
    (tmp_path / "microcatheter--microvention--headway-duo--knowledge.md").write_text(
        "# Headway Duo\n\n## What It Is\n\nMicrocatheter.",
        encoding="utf-8",
    )
    devices = load_devices(tmp_path)
    assert len(devices) == 2
    names = {d["name"] for d in devices}
    assert "Pipeline Flex" in names
    assert "Headway Duo" in names


def test_load_devices_fields(tmp_path):
    (tmp_path / "flow-diverter--medtronic--pipeline-flex--knowledge.md").write_text(
        "# Pipeline Flex\n\n## What It Is\n\nFlow diverter.\n\n## Also Known As\n\nPipeline, PED",
        encoding="utf-8",
    )
    devices = load_devices(tmp_path)
    d = devices[0]
    assert d["domain"] == "neurovascular"
    assert d["manufacturer_display"] == "Medtronic"
    assert d["category_display"] == "Flow Diverter"
    assert d["aliases"] == ["Pipeline", "PED"]
    assert "What It Is" in d["sections"]


def test_load_devices_skips_non_knowledge_files(tmp_path):
    (tmp_path / "flow-diverter--medtronic--pipeline.pdf").write_bytes(b"")
    (tmp_path / "README.md").write_text("hello")
    (tmp_path / "flow-diverter--medtronic--knowledge.md").write_text("too few parts")
    devices = load_devices(tmp_path)
    assert len(devices) == 0


def test_load_devices_fallback_name_from_slug(tmp_path):
    # File has no H1 heading — name should fall back to slug_to_title(slug)
    (tmp_path / "flow-diverter--medtronic--surpass-evolve--knowledge.md").write_text(
        "## What It Is\n\nNo H1 here.",
        encoding="utf-8",
    )
    devices = load_devices(tmp_path)
    assert devices[0]["name"] == "Surpass Evolve"
```

- [ ] **Step 2: Run to confirm failures**

```bash
python -m pytest tests/test_build_site.py -v -k "load_devices"
```

Expected: `ImportError`

- [ ] **Step 3: Add `load_devices` to `pipeline/build_site.py`**

Append after `map_domain`:

```python
def load_devices(catalog_root: Path) -> list[dict]:
    """Load all curated knowledge files from catalog_root.

    Reads every file matching *--knowledge.md directly in catalog_root
    (non-recursive — drafts in subdirectories are excluded).
    Returns a list of device dicts ready for JSON serialization.
    """
    devices: list[dict] = []
    for path in sorted(catalog_root.glob("*--knowledge.md")):
        meta = parse_filename(path.name)
        if not meta:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        name, sections, aliases = parse_markdown(content)
        if not name:
            name = slug_to_title(meta["slug"])
        devices.append({
            **meta,
            "name": name,
            "domain": map_domain(meta["category"]),
            "manufacturer_display": slug_to_title(meta["manufacturer"]),
            "category_display": slug_to_title(meta["category"]),
            "aliases": aliases,
            "sections": sections,
        })
    return devices
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python -m pytest tests/test_build_site.py -v
```

Expected: `32 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_site.py tests/test_build_site.py
git commit -m "feat(prototype): add load_devices"
```

---

## Task 5: HTML/CSS/JS application template

**Files:**
- Create: `pipeline/site_template.html`

This is the complete frontend. The placeholder `__CATALOG_DATA__` in the script tag will be replaced by the build script with the actual JSON array.

- [ ] **Step 1: Create `pipeline/site_template.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NeuroDevice Catalog</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f0f1a; color: #e0e0e0; display: flex; flex-direction: column; }

/* ── Top bar ── */
#top-bar { background: #1a1a2e; border-bottom: 1px solid #2a2a45;
           padding: 10px 16px; display: flex; align-items: center;
           gap: 12px; flex-shrink: 0; }
.logo { color: #4f8ef7; font-weight: 700; font-size: 15px; white-space: nowrap; }
.logo span { color: #666; font-weight: 400; }
#search-input { flex: 1; max-width: 440px; background: #0f3460;
                border: 1px solid #2a2a55; border-radius: 6px; color: #fff;
                padding: 7px 12px; font-size: 13px; outline: none; }
#search-input:focus { border-color: #4f8ef7; }
#search-input::placeholder { color: #444; }
#device-count { color: #444; font-size: 12px; white-space: nowrap; margin-left: auto; }

/* ── App body ── */
#app-body { display: flex; flex: 1; overflow: hidden; }

/* ── Left panel ── */
#left-panel { width: 300px; background: #13132a; border-right: 1px solid #2a2a45;
              display: flex; flex-direction: column; flex-shrink: 0; }
.panel-tabs { display: flex; border-bottom: 1px solid #2a2a45; flex-shrink: 0; }
.panel-tab { flex: 1; padding: 8px; background: none; border: none; color: #555;
             font-size: 12px; font-weight: 600; cursor: pointer; letter-spacing: 0.3px; }
.panel-tab.active { color: #4f8ef7; border-bottom: 2px solid #4f8ef7; }
.results-header { padding: 8px 14px 6px; color: #444; font-size: 11px;
                  letter-spacing: 0.4px; border-bottom: 1px solid #1e1e38; flex-shrink: 0; }
.results-list { flex: 1; overflow-y: auto; }

.result-item { padding: 9px 14px; border-bottom: 1px solid #1a1a30; cursor: pointer; }
.result-item:hover { background: #1a1a38; }
.result-item.active { background: #0f1e40; border-left: 2px solid #4f8ef7; padding-left: 12px; }
.result-name { font-size: 13px; color: #ddd; font-weight: 500; }
.result-meta { font-size: 11px; color: #555; margin-top: 2px; }
.cat-pill { display: inline-block; background: #1e1e38; border-radius: 3px;
            padding: 1px 5px; font-size: 10px; color: #777; }

/* ── Browse mode ── */
#browse-mode { display: none; flex-direction: column; flex: 1; overflow: hidden; }
#browse-tree { overflow-y: auto; border-bottom: 1px solid #2a2a45; flex-shrink: 0; max-height: 55%; }
#browse-results { display: flex; flex-direction: column; flex: 1; overflow: hidden; }
.domain-header { padding: 8px 14px; color: #888; font-size: 12px; font-weight: 600;
                 cursor: pointer; display: flex; justify-content: space-between; }
.domain-header:hover { background: #1a1a38; color: #bbb; }
.domain-header.expanded { color: #4f8ef7; }
.domain-cats { display: none; }
.domain-cats.open { display: block; }
.cat-row { padding: 6px 14px 6px 24px; font-size: 12px; color: #777;
           cursor: pointer; display: flex; justify-content: space-between; }
.cat-row:hover { background: #1a1a38; color: #ccc; }
.cat-row.active { color: #4f8ef7; background: #0f1e40; }
.cat-count { color: #444; }

/* ── Right panel ── */
#right-panel { flex: 1; display: flex; overflow: hidden; }
.detail-pane { flex: 1; overflow-y: auto; padding: 20px 24px; }
.detail-pane + .detail-pane { border-left: 2px solid #2a2a45; }

.empty-state { display: flex; align-items: center; justify-content: center;
               height: 80%; color: #2a2a45; font-size: 13px; }

/* ── Device header ── */
.device-header { margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #2a2a35; }
.device-category-label { font-size: 11px; color: #4f8ef7; font-weight: 600;
                          letter-spacing: 0.5px; margin-bottom: 4px; }
.device-name { font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 3px; }
.device-mfr { font-size: 13px; color: #666; margin-bottom: 10px; }
.compare-btn { background: #1e2d50; border: 1px solid #2a4070; border-radius: 5px;
               color: #4f8ef7; font-size: 12px; padding: 5px 12px; cursor: pointer; }
.compare-btn:hover { background: #253660; }
.exit-compare-btn { background: #2a1e1e; border: 1px solid #503030; border-radius: 5px;
                    color: #c06060; font-size: 12px; padding: 5px 12px; cursor: pointer; }

/* ── Compare search ── */
.compare-search-wrap { display: none; margin-top: 10px; position: relative; }
.compare-search-input { width: 100%; background: #0f3460; border: 1px solid #4f8ef7;
                        border-radius: 6px; color: #fff; padding: 7px 12px;
                        font-size: 13px; outline: none; }
.compare-dropdown { position: absolute; top: 100%; left: 0; right: 0;
                    background: #1a1a38; border: 1px solid #2a2a55;
                    border-top: none; border-radius: 0 0 6px 6px;
                    max-height: 200px; overflow-y: auto; z-index: 10; }
.compare-option { padding: 8px 12px; cursor: pointer; }
.compare-option:hover { background: #0f3460; }
.co-name { font-size: 12px; color: #ddd; }
.co-meta { font-size: 11px; color: #555; }

/* ── Sections ── */
.section-block { margin-bottom: 18px; }
.section-label { font-size: 10px; font-weight: 700; color: #444; letter-spacing: 0.8px;
                 text-transform: uppercase; margin-bottom: 6px; }
.section-content { font-size: 13px; color: #c0c0c0; line-height: 1.6; }
.section-content table { border-collapse: collapse; width: 100%; margin-top: 4px; font-size: 12px; }
.section-content td, .section-content th { border: 1px solid #2a2a45; padding: 5px 8px; }
.section-content th { background: #1a1a38; color: #777; }
.section-content td { color: #bbb; }
.section-content strong { color: #ddd; }
.section-content code { background: #1e1e38; padding: 1px 4px; border-radius: 3px; font-size: 11px; }
.section-content ul, .section-content ol { padding-left: 18px; }
.section-content li { margin-bottom: 3px; }
.aka-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.aka-tag { background: #1e1e38; border-radius: 3px; padding: 2px 7px;
           font-size: 11px; color: #777; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2a2a45; border-radius: 2px; }
</style>
</head>
<body>

<div id="top-bar">
  <div class="logo">NeuroDevice <span>Catalog</span></div>
  <input id="search-input" type="text"
         placeholder="Search devices by name, alias, or manufacturer...">
  <span id="device-count"></span>
</div>

<div id="app-body">

  <div id="left-panel">
    <div class="panel-tabs">
      <button class="panel-tab active" id="tab-search"
              onclick="setMode('search')">Search</button>
      <button class="panel-tab" id="tab-browse"
              onclick="setMode('browse')">Browse</button>
    </div>

    <div id="search-mode"
         style="display:flex;flex-direction:column;flex:1;overflow:hidden;">
      <div class="results-header" id="results-header">ALL DEVICES</div>
      <div class="results-list" id="results-list"></div>
    </div>

    <div id="browse-mode">
      <div id="browse-tree"></div>
      <div id="browse-results">
        <div class="results-header" id="results-header-browse"></div>
        <div class="results-list" id="results-list-browse"
             style="flex:1;overflow-y:auto;"></div>
      </div>
    </div>
  </div>

  <div id="right-panel">
    <div id="detail-panel-a" class="detail-pane">
      <div class="empty-state">Select a device to view details</div>
    </div>
    <div id="detail-panel-b" class="detail-pane" style="display:none;"></div>
  </div>

</div>

<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const CATALOG = __CATALOG_DATA__;

// ── State ──────────────────────────────────────────────────────────────────
let fuse;
let activeDeviceId  = null;
let compareDeviceId = null;
let mode            = 'search';
let activeDomain    = null;
let activeCategory  = null;
let currentResults  = [];
let searchTimer     = null;

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('device-count').textContent =
    CATALOG.length + ' curated devices';

  fuse = new Fuse(CATALOG, {
    keys: [
      { name: 'name',                 weight: 1.0 },
      { name: 'aliases',              weight: 0.9 },
      { name: 'manufacturer_display', weight: 0.6 },
      { name: 'category',             weight: 0.5 },
    ],
    threshold: 0.4,
    includeScore: true,
  });

  buildBrowseTree();
  showResults(CATALOG, 'search');

  document.getElementById('search-input')
    .addEventListener('input', onSearch);
});

// ── Mode ───────────────────────────────────────────────────────────────────
function setMode(m) {
  mode = m;
  document.getElementById('search-mode').style.display =
    m === 'search' ? 'flex' : 'none';
  document.getElementById('browse-mode').style.display  =
    m === 'browse' ? 'flex' : 'none';
  document.getElementById('tab-search')
    .classList.toggle('active', m === 'search');
  document.getElementById('tab-browse')
    .classList.toggle('active', m === 'browse');

  if (m === 'search') {
    document.getElementById('search-input').focus();
    const q = document.getElementById('search-input').value.trim();
    showResults(q ? fuse.search(q).map(r => r.item) : CATALOG, 'search');
  } else {
    const filtered = activeCategory
      ? CATALOG.filter(d => d.category === activeCategory)
      : activeDomain
        ? CATALOG.filter(d => d.domain === activeDomain)
        : CATALOG;
    showResults(filtered, 'browse');
  }
}

// ── Search ─────────────────────────────────────────────────────────────────
function onSearch(e) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(function() {
    const q = e.target.value.trim();
    showResults(q ? fuse.search(q).map(r => r.item) : CATALOG, 'search');
  }, 150);
}

// ── Results ────────────────────────────────────────────────────────────────
function showResults(devices, target) {
  currentResults = devices;
  const listId   = target === 'browse' ? 'results-list-browse'  : 'results-list';
  const headerId = target === 'browse' ? 'results-header-browse' : 'results-header';
  document.getElementById(headerId).textContent =
    devices.length + ' DEVICE' + (devices.length !== 1 ? 'S' : '');
  document.getElementById(listId).innerHTML = devices.map(function(d) {
    return '<div class="result-item' + (activeDeviceId === d.id ? ' active' : '') +
      '" onclick="selectDevice(\'' + d.id + '\')">' +
      '<div class="result-name">' + esc(d.name) + '</div>' +
      '<div class="result-meta">' + esc(d.manufacturer_display) +
      ' <span class="cat-pill">' + esc(d.category_display) + '</span></div>' +
      '</div>';
  }).join('');
}

function refreshList() {
  showResults(currentResults, mode === 'browse' ? 'browse' : 'search');
}

// ── Browse tree ────────────────────────────────────────────────────────────
var DOMAIN_ORDER  = ['neurovascular', 'spine', 'cranial', 'other'];
var DOMAIN_LABELS = {
  neurovascular: 'Neurovascular',
  spine: 'Spine',
  cranial: 'Cranial',
  other: 'Other'
};

function catDisplay(cat) {
  var SPECIAL = { csf:'CSF', si:'SI', vrd:'VRD', tlif:'TLIF',
                  llif:'LLIF', alif:'ALIF', acdf:'ACDF' };
  return cat.split('-').map(function(w) {
    return SPECIAL[w] || (w.charAt(0).toUpperCase() + w.slice(1));
  }).join(' ');
}

function buildBrowseTree() {
  var tree = document.getElementById('browse-tree');
  tree.innerHTML = DOMAIN_ORDER.map(function(domain) {
    var cats = [];
    CATALOG.forEach(function(d) {
      if (d.domain === domain && cats.indexOf(d.category) === -1)
        cats.push(d.category);
    });
    cats.sort();
    if (!cats.length) return '';
    var rows = cats.map(function(cat) {
      var count = CATALOG.filter(function(d) { return d.category === cat; }).length;
      return '<div class="cat-row' + (activeCategory === cat ? ' active' : '') +
        '" onclick="selectCategory(\'' + domain + '\',\'' + cat + '\')">' +
        '<span>' + catDisplay(cat) + '</span>' +
        '<span class="cat-count">' + count + '</span></div>';
    }).join('');
    var isExpanded = activeDomain === domain;
    return '<div>' +
      '<div class="domain-header' + (isExpanded ? ' expanded' : '') +
      '" id="dh-' + domain + '" onclick="toggleDomain(\'' + domain + '\')">' +
      '<span>' + DOMAIN_LABELS[domain] + '</span>' +
      '<span>' + (isExpanded ? '▾' : '▸') + '</span></div>' +
      '<div class="domain-cats' + (isExpanded ? ' open' : '') +
      '" id="dc-' + domain + '">' + rows + '</div></div>';
  }).join('');
}

function toggleDomain(domain) {
  var cats = document.getElementById('dc-' + domain);
  if (!cats) return;
  var opening = !cats.classList.contains('open');
  // Close all domains first
  DOMAIN_ORDER.forEach(function(d) {
    var c = document.getElementById('dc-' + d);
    var h = document.getElementById('dh-' + d);
    if (c) { c.classList.remove('open'); }
    if (h) {
      h.classList.remove('expanded');
      var arr = h.querySelector('span:last-child');
      if (arr) arr.textContent = '▸';
    }
  });
  if (opening) {
    cats.classList.add('open');
    var hdr = document.getElementById('dh-' + domain);
    hdr.classList.add('expanded');
    hdr.querySelector('span:last-child').textContent = '▾';
    activeDomain   = domain;
    activeCategory = null;
    buildBrowseTree();
    document.getElementById('dc-' + domain).classList.add('open');
    document.getElementById('dh-' + domain).classList.add('expanded');
    document.getElementById('dh-' + domain).querySelector('span:last-child').textContent = '▾';
    showResults(CATALOG.filter(function(d) { return d.domain === domain; }), 'browse');
  } else {
    activeDomain   = null;
    activeCategory = null;
    buildBrowseTree();
    showResults(CATALOG, 'browse');
  }
}

function selectCategory(domain, cat) {
  activeDomain   = domain;
  activeCategory = cat;
  buildBrowseTree();
  document.getElementById('dc-' + domain).classList.add('open');
  document.getElementById('dh-' + domain).classList.add('expanded');
  document.getElementById('dh-' + domain).querySelector('span:last-child').textContent = '▾';
  showResults(CATALOG.filter(function(d) { return d.category === cat; }), 'browse');
}

// ── Device detail ──────────────────────────────────────────────────────────
var SECTION_ORDER = [
  'What It Is','Sizing','Indications','Contraindications',
  'Compatible With','Use Notes','Key Differences vs Competitors','Also Known As'
];

function selectDevice(id) {
  activeDeviceId  = id;
  compareDeviceId = null;
  refreshList();
  document.getElementById('detail-panel-b').style.display = 'none';
  renderDetail(id, 'detail-panel-a', true);
}

function renderDetail(id, panelId, showCompareBtn) {
  var device = CATALOG.find(function(d) { return d.id === id; });
  var panel  = document.getElementById(panelId);
  if (!device) { panel.innerHTML = ''; return; }

  var ordered = SECTION_ORDER.filter(function(k) { return device.sections[k]; });
  var extras  = Object.keys(device.sections).filter(function(k) {
    return SECTION_ORDER.indexOf(k) === -1;
  });

  var sectionsHtml = ordered.concat(extras).map(function(label) {
    var content = device.sections[label];
    if (label === 'Also Known As') {
      var inner = device.aliases.length
        ? device.aliases.map(function(a) {
            return '<span class="aka-tag">' + esc(a) + '</span>';
          }).join('')
        : marked.parse(content);
      return '<div class="section-block">' +
        '<div class="section-label">' + esc(label) + '</div>' +
        '<div class="section-content"><div class="aka-tags">' + inner + '</div></div>' +
        '</div>';
    }
    return '<div class="section-block">' +
      '<div class="section-label">' + esc(label) + '</div>' +
      '<div class="section-content">' + marked.parse(content) + '</div>' +
      '</div>';
  }).join('');

  var actionHtml = showCompareBtn
    ? '<button class="compare-btn" onclick="openCompareSearch()">⟷ Compare with...</button>' +
      '<div class="compare-search-wrap" id="compare-search-wrap">' +
      '<input class="compare-search-input" id="compare-search-input"' +
      ' placeholder="Search for second device..." oninput="onCompareSearch(event)">' +
      '<div class="compare-dropdown" id="compare-dropdown"></div></div>'
    : '<button class="exit-compare-btn" onclick="exitComparison()">✕ Exit comparison</button>';

  panel.innerHTML =
    '<div class="device-header">' +
    '<div class="device-category-label">' +
    esc(catDisplay(device.category)) + ' · ' +
    esc(device.manufacturer_display.toUpperCase()) + '</div>' +
    '<div class="device-name">' + esc(device.name) + '</div>' +
    '<div class="device-mfr">' + esc(device.manufacturer_display) + '</div>' +
    '<div>' + actionHtml + '</div>' +
    '</div>' + sectionsHtml;
}

// ── Comparison ─────────────────────────────────────────────────────────────
function openCompareSearch() {
  var wrap = document.getElementById('compare-search-wrap');
  if (wrap) { wrap.style.display = 'block'; }
  var input = document.getElementById('compare-search-input');
  if (input) { input.focus(); }
}

function onCompareSearch(e) {
  var q = e.target.value.trim();
  var dropdown = document.getElementById('compare-dropdown');
  if (!dropdown) return;
  if (!q) { dropdown.innerHTML = ''; return; }
  var results = fuse.search(q).slice(0, 8)
    .map(function(r) { return r.item; })
    .filter(function(d) { return d.id !== activeDeviceId; });
  dropdown.innerHTML = results.map(function(d) {
    return '<div class="compare-option" onclick="selectCompareDevice(\'' + d.id + '\')">' +
      '<div class="co-name">' + esc(d.name) + '</div>' +
      '<div class="co-meta">' + esc(d.manufacturer_display) + ' · ' +
      esc(catDisplay(d.category)) + '</div></div>';
  }).join('');
}

function selectCompareDevice(id) {
  compareDeviceId = id;
  document.getElementById('detail-panel-b').style.display = 'block';
  renderDetail(activeDeviceId,  'detail-panel-a', false);
  renderDetail(compareDeviceId, 'detail-panel-b', false);
}

function exitComparison() {
  compareDeviceId = null;
  document.getElementById('detail-panel-b').style.display = 'none';
  renderDetail(activeDeviceId, 'detail-panel-a', true);
}

// ── Utils ──────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
</script>
</body>
</html>
```

- [ ] **Step 2: Verify the file was created and has the placeholder**

```bash
grep -c "__CATALOG_DATA__" pipeline/site_template.html
```

Expected output: `1`

- [ ] **Step 3: Commit**

```bash
git add pipeline/site_template.html
git commit -m "feat(prototype): add site_template.html - full split-panel app"
```

---

## Task 6: `main()` in build script + integration test

**Files:**
- Modify: `pipeline/build_site.py` (add `main`)
- Modify: `tests/test_build_site.py` (add integration test)

- [ ] **Step 1: Add integration test to `tests/test_build_site.py`**

Append:

```python
import subprocess

CATALOG_ROOT = Path(__file__).parent.parent


def test_build_site_integration():
    """Run the build script against the real catalog and check output."""
    result = subprocess.run(
        ["python", "pipeline/build_site.py"],
        cwd=str(CATALOG_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Build failed:\n{result.stderr}"

    output = CATALOG_ROOT / "site" / "index.html"
    assert output.exists(), "site/index.html not created"

    content = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Pipeline Flex" in content          # known device
    assert "Headway Duo" in content            # known device
    assert "__CATALOG_DATA__" not in content   # placeholder was replaced
    assert "neurovascular" in content          # domain data present


def test_build_site_device_count():
    """Site should reference at least 200 devices."""
    output = (CATALOG_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    import re
    # The JS sets: CATALOG.length + ' curated devices'
    # We check the JSON array has at least 200 objects
    match = re.search(r'const CATALOG = (\[.*?\]);', output, re.DOTALL)
    assert match, "Could not find CATALOG array in output"
    catalog = json.loads(match.group(1))
    assert len(catalog) >= 200, f"Expected >= 200 devices, got {len(catalog)}"
```

- [ ] **Step 2: Run integration test to confirm it fails**

```bash
python -m pytest tests/test_build_site.py::test_build_site_integration -v
```

Expected: `AssertionError: Build failed` or `FileNotFoundError` (main() not defined yet)

- [ ] **Step 3: Add `main()` to `pipeline/build_site.py`**

Append at the end of the file:

```python
def main() -> None:
    catalog_root = Path(__file__).parent.parent
    template_path = Path(__file__).parent / "site_template.html"
    output_dir = catalog_root / "site"
    output_path = output_dir / "index.html"

    print(f"Loading devices from {catalog_root} ...")
    devices = load_devices(catalog_root)
    print(f"  {len(devices)} curated devices loaded")

    template = template_path.read_text(encoding="utf-8")
    catalog_json = json.dumps(devices, ensure_ascii=False)
    html = template.replace("__CATALOG_DATA__", catalog_json)

    output_dir.mkdir(exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"  Written to {output_path}")
    print("Done. Open site/index.html in your browser.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests — expect pass**

```bash
python -m pytest tests/test_build_site.py -v
```

Expected: `34 passed` (all prior tests + 2 integration tests)

- [ ] **Step 5: Add `site/` to `.gitignore`**

```bash
echo "site/" >> .gitignore
```

- [ ] **Step 6: Commit**

```bash
git add pipeline/build_site.py tests/test_build_site.py .gitignore
git commit -m "feat(prototype): add main() build entry point and integration tests"
```

---

## Task 7: End-to-end verification

**Files:** none (manual verification)

- [ ] **Step 1: Run the build**

```bash
cd C:/Users/Michael/documents/device_catalog
python pipeline/build_site.py
```

Expected output:
```
Loading devices from C:\...\device_catalog ...
  213 curated devices loaded
  Written to C:\...\device_catalog\site\index.html
Done. Open site/index.html in your browser.
```

- [ ] **Step 2: Open in browser**

Open `site/index.html` directly in Chrome or Edge (double-click in Explorer, or drag to browser).

- [ ] **Step 3: Verify Search mode**

1. The top bar shows "213 curated devices"
2. The results list shows all devices
3. Type "pipeline" in the search box — results narrow to Pipeline Flex and related devices
4. Type "ace" — Penumbra ACE catheters appear
5. Type "trevo" — Trevo NXT, Trevo XP appear
6. Click a device — detail panel renders with formatted sections and sizing tables

- [ ] **Step 4: Verify Browse mode**

1. Click the "Browse" tab in the left panel
2. Click "Neurovascular" — expands showing subcategory rows with counts
3. Click "Microcatheter" — results list updates to microcatheters only
4. Click a different domain — previous domain collapses, new one opens
5. Click "Spine" → "Pedicle Screw" — spine devices shown

- [ ] **Step 5: Verify comparison**

1. Select a device (e.g., Pipeline Flex)
2. Click "Compare with..."
3. Type "fred" in the compare search
4. Select FRED X — right panel splits into two columns
5. Both devices show sections side by side
6. Click "Exit comparison" — returns to single-device view

- [ ] **Step 6: Final commit**

```bash
git add site/index.html  # or skip if site/ is gitignored
git commit -m "feat(prototype): working static HTML device catalog prototype"
```

---

## Self-Review Notes

**Spec coverage check:**
- Split-panel layout (B): Task 5 + 6 — covered
- Search with Fuse.js: Task 5 — covered
- Browse mode with domain tree: Task 5 — covered
- Device detail with markdown rendering: Task 5 — covered
- Compare with... button splitting panel: Task 5 — covered
- Build script `pipeline/build_site.py`: Task 1–4 + 6 — covered
- Output to `site/index.html`: Task 6 — covered
- Curated files only (not drafts): `load_devices` uses non-recursive `glob("*--knowledge.md")` — covered
- Domain mapping for all 22 categories: Task 3 — covered, tested exhaustively

**Type consistency:** `device.id` is used consistently as the lookup key in `selectDevice`, `renderDetail`, `selectCompareDevice`. `catDisplay` is defined in JS and used in both browse tree and detail header. No naming mismatches found.

**Placeholder scan:** No TBDs or TODOs in the plan. All code blocks are complete and runnable.
