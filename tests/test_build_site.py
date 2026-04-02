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
