from pathlib import Path

from pipeline.evidence.registry import identity_from_knowledge, match_device_by_term, parse_knowledge_filename


def test_parse_knowledge_filename():
    parsed = parse_knowledge_filename(Path("flow-diverter--medtronic--pipeline-flex--knowledge.md"))
    assert parsed == ("flow-diverter", "medtronic", "pipeline-flex")


def test_identity_from_knowledge_extracts_h1_and_aliases():
    identity = identity_from_knowledge(
        "flow-diverter",
        "medtronic",
        "pipeline-flex",
        "# Pipeline Flex Embolization Device\n\n"
        "## Also Known As\n\n"
        "Pipeline, PED\n"
        "- Pipeline Flex with Shield\n",
    )

    assert identity.display_name == "Pipeline Flex Embolization Device"
    assert identity.search_terms() == [
        "Pipeline Flex Embolization Device",
        "Pipeline",
        "PED",
        "Pipeline Flex with Shield",
    ]


def test_match_device_by_term_uses_aliases():
    registry = [
        identity_from_knowledge(
            "flow-diverter",
            "medtronic",
            "pipeline-flex",
            "# Pipeline Flex\n\n## Also Known As\n\nPED",
        )
    ]

    match = match_device_by_term("PED", registry)

    assert match is not None
    assert match.canonical_id == "flow-diverter--medtronic--pipeline-flex"
