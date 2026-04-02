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
