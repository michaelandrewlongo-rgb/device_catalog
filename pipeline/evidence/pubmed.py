"""PubMed E-utilities client.

V1 intentionally stores bibliographic records only: title, abstract, and basic
publication metadata. Classification and evidence extraction are out of scope.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import httpx

from .models import PubMedArticle, SourceHealth, utc_now_iso

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedClient:
    def __init__(self, email: str | None = None, api_key: str | None = None, timeout: float = 30.0):
        self.email = email
        self.api_key = api_key
        self.timeout = timeout

    def search(
        self,
        query: str,
        limit: int = 20,
        device_family: str = "",
        health_log: list[SourceHealth] | None = None,
    ) -> list[PubMedArticle]:
        checked_at = utc_now_iso()
        try:
            ids = self.search_pmids(query, limit=limit)
            articles = self.fetch_articles(ids, query_used=query, matched_device_family=device_family) if ids else []
        except httpx.RequestError as exc:
            _log(health_log, "pubmed", device_family, query, checked_at,
                 "connection_error", 0, None, str(exc))
            return []
        except httpx.HTTPStatusError as exc:
            _log(health_log, "pubmed", device_family, query, checked_at,
                 "http_error", 0, exc.response.status_code, str(exc))
            return []
        status = "ok" if articles else "empty"
        _log(health_log, "pubmed", device_family, query, checked_at, status, len(articles))
        return articles

    def search_pmids(self, query: str, limit: int = 20) -> list[str]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": limit,
            "sort": "relevance",
        }
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{EUTILS_BASE}/esearch.fcgi", params=params)
            response.raise_for_status()
            payload = response.json()
        return payload.get("esearchresult", {}).get("idlist", [])

    def fetch_articles(
        self,
        pmids: list[str],
        query_used: str = "",
        matched_device_family: str = "",
    ) -> list[PubMedArticle]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{EUTILS_BASE}/efetch.fcgi", params=params)
            response.raise_for_status()
        return parse_pubmed_xml(
            response.text,
            query_used=query_used,
            matched_device_family=matched_device_family,
        )


def _log(
    health_log: list[SourceHealth] | None,
    source_type: str,
    device_family: str,
    query_used: str,
    checked_at: str,
    status: str,
    record_count: int,
    http_status: int | None = None,
    error_detail: str = "",
) -> None:
    if health_log is None:
        return
    health_log.append(
        SourceHealth(
            source_type=source_type,
            device_family=device_family,
            query_used=query_used,
            checked_at=checked_at,
            status=status,
            record_count=record_count,
            http_status=http_status,
            error_detail=error_detail,
        )
    )


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _publication_date(article: ET.Element) -> str:
    pub_date = article.find(".//Journal/JournalIssue/PubDate")
    if pub_date is None:
        return ""
    year = _text(pub_date.find("Year"))
    month = _text(pub_date.find("Month"))
    day = _text(pub_date.find("Day"))
    return "-".join(part for part in [year, month, day] if part)


def _doi(article: ET.Element) -> str:
    for article_id in article.findall(".//ArticleId"):
        if article_id.attrib.get("IdType") == "doi":
            return _text(article_id)
    return ""


def parse_pubmed_xml(
    xml_text: str,
    query_used: str = "",
    matched_device_family: str = "",
) -> list[PubMedArticle]:
    root = ET.fromstring(xml_text)
    retrieved_at = utc_now_iso()
    articles: list[PubMedArticle] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//PMID"))
        if not pmid:
            continue
        abstract_parts = [_text(node) for node in article.findall(".//Abstract/AbstractText")]
        articles.append(
            PubMedArticle(
                pmid=pmid,
                title=_text(article.find(".//ArticleTitle")),
                abstract="\n".join(part for part in abstract_parts if part),
                journal=_text(article.find(".//Journal/Title")),
                publication_date=_publication_date(article),
                doi=_doi(article),
                query_used=query_used,
                matched_device_family=matched_device_family,
                source_retrieved_at=retrieved_at,
            )
        )
    return articles
