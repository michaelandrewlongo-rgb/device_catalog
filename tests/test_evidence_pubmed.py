from pipeline.evidence.models import SourceType
from pipeline.evidence.pubmed import parse_pubmed_xml


PUBMED_XML = """\
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal>
          <Title>Journal of Devices</Title>
          <JournalIssue>
            <PubDate><Year>2024</Year><Month>Jan</Month><Day>02</Day></PubDate>
          </JournalIssue>
        </Journal>
        <ArticleTitle>Pipeline Flex abstract-only record</ArticleTitle>
        <Abstract>
          <AbstractText>First abstract sentence.</AbstractText>
          <AbstractText>Second abstract sentence.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1000/device</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parse_pubmed_xml_bibliographic_only():
    articles = parse_pubmed_xml(
        PUBMED_XML,
        query_used='"Pipeline Flex"',
        matched_device_family="flow-diverter--medtronic--pipeline-flex",
    )

    assert len(articles) == 1
    article = articles[0]
    assert article.pmid == "12345"
    assert article.title == "Pipeline Flex abstract-only record"
    assert article.abstract == "First abstract sentence.\nSecond abstract sentence."
    assert article.publication_date == "2024-Jan-02"
    assert article.doi == "10.1000/device"

    source = article.to_source_record()
    assert source.source_type == SourceType.PUBMED
    assert source.raw["abstract"] == article.abstract
    assert "study_type" not in source.raw
    assert "classification" not in source.raw
