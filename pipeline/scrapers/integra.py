"""Scraper for Integra LifeSciences neurosurgical product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover
    StealthyFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class IntegraScraper(ManufacturerScraper):
    manufacturer = "integra"
    base_url = "https://products.integralife.com"
    request_delay = 2.0
    products_url = "https://products.integralife.com/neuro/category/for-the-neurosurgeon"
    timeout = 20

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return ("products.integralife.com", "integralife.com")

    category_patterns: list[tuple[str, list[str]]] = [
        ("dural-sealant", [r"\bduraseal\b", r"\bdural sealant\b"]),
        ("dural-substitute", [r"\bduragen\b", r"\bdural substitute\b", r"\bdural graft\b", r"\bdurasorb\b"]),
        ("csf-shunt", [r"\bcertas\b", r"\bshunt\b", r"\bvalve\b", r"\bsiphonguard\b", r"\bbactiseal\b"]),
        ("navigation", [r"\bcusa\b", r"\bultrasonic\b", r"\blicox\b", r"\bmonitoring\b"]),
    ]
    neurointerventional_terms = (
        "aneurysm",
        "embol",
        "endovascular",
        "intervention",
        "interventional",
        "intracranial",
        "microcatheter",
        "neurovascular",
        "stroke",
        "thromb",
    )

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from Integra's neurosurgery catalog."""
        urls: list[dict[str, str]] = []
        seen: set[str] = set()

        html = await self._fetch_listing_html()
        if html:
            for href, text in self.extract_links_from_html(html, self.products_url):
                if self._looks_like_neurointerventional_link(href, text):
                    self.add_discovered_url(
                        urls,
                        seen,
                        href,
                        text,
                        page_url=self.products_url,
                        require_segments=("/product/",),
                    )

        if not urls:
            console.print("[yellow]No Integra neurointerventional product URLs discovered; skipping Integra rather than scraping the full site catalog[/]")
            return []

        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape an Integra product page."""
        html = await self._fetch_detail_html(url)
        if not html:
            return None

        title = self.extract_title_from_html(html, fallback=name)
        if not title:
            return None

        page_text = self.extract_page_text_from_html(html)
        raw_html = html[:50000]
        if self.is_probably_blocked_page(page_text, title=title, html=html):
            console.print("    [yellow]Rejected blocked or error page[/]")
            return None
        pdf_urls = self.extract_pdf_candidates_from_html(html, url)
        pdf_texts: list[str] = []
        for pdf_url in self.prioritize_pdf_urls(pdf_urls, max_pdfs=3):
            parsed = await self.parse_pdf_text(pdf_url)
            if parsed:
                pdf_texts.append(parsed)
        pdf_text = "\n\n".join(pdf_texts)

        ifu_url, other_pdfs = self.classify_pdf_urls(pdf_urls)
        description = self.extract_section_from_html(html, ["overview", "description", "about", "product description"])
        if not description:
            description = self.extract_section_text(page_text, ["overview", "description", "about", "product description"])
        sizing_specs = self.extract_section_from_html(html, ["specification", "sizing", "features", "dimensions"])
        if not sizing_specs:
            sizing_specs = self.extract_section_text(page_text, ["specification", "sizing", "features", "dimensions"])
        if not sizing_specs:
            sizing_specs = self.extract_sizing_from_text(pdf_text)
        indications = self.extract_section_from_html(html, ["indication", "intended", "indications for use", "intended use"])
        if not indications:
            indications = self.extract_section_text(page_text, ["indication", "intended", "indications for use", "intended use"])
        if not indications:
            indications = self.extract_indications_from_text(pdf_text)

        category_hint = self.score_category_patterns(
            "\n".join([title, page_text[:2000], pdf_text[:2000]]),
            self.category_patterns,
        )

        return ScrapedProduct(
            device_name=title.strip(),
            manufacturer=self.manufacturer,
            category_hint=category_hint,
            what_it_is=description,
            sizing_specs=sizing_specs,
            indications=indications,
            source_url=url,
            ifu_pdf_url=ifu_url,
            other_pdf_urls=other_pdfs,
            raw_html=raw_html,
        )

    @staticmethod
    def _guess_category(title: str, text: str) -> str:
        combined = (title + " " + text[:500]).lower()
        if any(kw in combined for kw in ["licox", "monitoring"]):
            return "navigation"
        return "unknown"

    async def _fetch_listing_html(self) -> str | None:
        if StealthyFetcher is None:
            return await self.fetch_html_via_requests(self.products_url)
        return await self.fetch_html(
            StealthyFetcher,
            self.products_url,
            headless=True,
            network_idle=True,
        )

    async def _fetch_detail_html(self, url: str) -> str | None:
        if StealthyFetcher is None:
            return await self.fetch_html_via_requests(url)
        return await self.fetch_html(
            StealthyFetcher,
            url,
            headless=True,
            network_idle=True,
        )

    def _looks_like_neurointerventional_link(self, href: str, text: str) -> bool:
        normalized = self.normalize_url(href, page_url=self.products_url, allowed_domains=self.allowed_domains)
        if not normalized or "/product/" not in normalized.lower():
            return False
        combined = f"{normalized.lower()} {self.clean_text(text).lower()}"
        return any(term in combined for term in self.neurointerventional_terms)
