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
    assert parse_filename("flow-diverter--medtronic--knowledge.md") is None


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
    (tmp_path / "flow-diverter--medtronic--surpass-evolve--knowledge.md").write_text(
        "## What It Is\n\nNo H1 here.",
        encoding="utf-8",
    )
    devices = load_devices(tmp_path)
    assert devices[0]["name"] == "Surpass Evolve"


def test_parse_aliases_grouped_bold_headers():
    """Grouped AKA sections with bold headers should not produce markdown as aliases."""
    text = "**SL-10:**\n- Excelsior SL-10\n- SL-10\n\n**1018:**\n- Excelsior 1018"
    from pipeline.build_site import _parse_aliases
    aliases = _parse_aliases(text)
    # Should not contain raw markdown like "**SL-10:**"
    for a in aliases:
        assert not a.startswith("*"), f"Raw markdown in alias: {a!r}"
    # Should have extracted the actual device name aliases
    assert "Excelsior SL-10" in aliases or "SL-10" in aliases


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
    assert "Pipeline Flex" in content
    assert "Headway Duo" in content
    assert "__CATALOG_DATA__" not in content
    assert "neurovascular" in content


def test_build_site_device_count():
    """Site should reference at least 200 devices."""
    output = (CATALOG_ROOT / "site" / "index.html").read_text(encoding="utf-8")
    import re
    match = re.search(r'const CATALOG = (\[.*?\]);\s*\n', output, re.DOTALL)
    assert match, "Could not find CATALOG array in output"
    import json as _json
    catalog = _json.loads(match.group(1))
    assert len(catalog) >= 200, f"Expected >= 200 devices, got {len(catalog)}"
