from pipeline.evidence.models import SourceRecord, SourceType
from pipeline.evidence.review import build_category_review, render_review_markdown


def test_review_keeps_source_ids_and_pubmed_abstract():
    record = SourceRecord(
        source_id="pubmed:12345",
        source_type=SourceType.PUBMED,
        title="Device paper",
        retrieved_at="2026-04-15T00:00:00+00:00",
        device_family="flow-diverter--medtronic--pipeline-flex",
        query_used='"Pipeline Flex"',
        raw={"abstract": "This is the abstract, not extracted evidence."},
    )

    review = build_category_review("flow-diverter", [record])
    markdown = render_review_markdown(review)

    assert review["status"] == "draft"
    assert review["source_ids"] == ["pubmed:12345"]
    assert "Source ID: `pubmed:12345`" in markdown
    assert "This is the abstract, not extracted evidence." in markdown
