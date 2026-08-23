from pathlib import Path

from pipeline.evidence.claims import extract_claims_from_markdown
from pipeline.evidence.models import SourceType


def test_extract_claims_tags_curated_human_notes():
    claims = extract_claims_from_markdown(
        Path("flow-diverter--medtronic--pipeline-flex--knowledge.md"),
        "# Pipeline Flex\n\n"
        "## What It Is\n\n"
        "A flow-diverter claim.\n"
        "- A bullet claim.\n\n"
        "## Sizing\n\n"
        "| Diameter | Length |\n"
        "|---|---|\n"
        "| 3 mm | 10 mm |\n",
    )

    assert [claim.claim_text for claim in claims] == [
        "A flow-diverter claim.",
        "A bullet claim.",
        "| Diameter | Length |",
        "| 3 mm | 10 mm |",
    ]
    assert {claim.source_type for claim in claims} == {SourceType.CURATED_HUMAN_NOTES}
    assert {claim.device_id for claim in claims} == {"flow-diverter--medtronic--pipeline-flex"}
    assert claims[0].section == "What It Is"
    assert claims[-1].section == "Sizing"
