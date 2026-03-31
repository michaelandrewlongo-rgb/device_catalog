"""Scraper for Balt Group neurovascular product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover
    StealthyFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class BaltScraper(ManufacturerScraper):
    manufacturer = "balt"
    base_url = "https://baltgroup.com"
    products_url = "https://baltgroup.com/products/"
    request_delay = 3.0
    max_pdfs = 4

    category_patterns: list[tuple[str, list[str]]] = [
        ("flow-diverter", [r"\bsilk\b", r"\bflow divert"]),
        ("embolic-coil", [r"\boptima\b", r"\bcoil\b", r"\bembolization coil\b"]),
        ("aspiration", [r"\braptor\b", r"\baspiration\b"]),
        ("microcatheter", [r"\bcarrier\b", r"\bmicrocatheter\b"]),
        ("intracranial-stent", [r"\bleo\b", r"\bstent\b"]),
    ]

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from Balt's website."""
        found: dict[str, dict[str, str]] = {}

        html = await self._fetch_listing_html()
        if html:
            for href, text in self.extract_links_from_html(html, self.products_url):
                if self._looks_like_product_link(href):
                    found[href] = {"url": href, "name": text or self._slug_to_name(href)}

        if not found:
            for href in await self.discover_from_sitemap():
                if self._looks_like_product_link(href):
                    found[href] = {"url": href, "name": self._slug_to_name(href)}

        if not found:
            console.print("[yellow]Using Balt product listing as fallback[/]")
            found[self.products_url] = {"url": self.products_url, "name": "Products Overview"}

        urls = sorted(found.values(), key=lambda item: item["url"])
        console.print(f"[cyan]Discovered {len(urls)} Balt product URLs[/]")
        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Balt product page."""
        html = await self._fetch_detail_html(url)
        if not html:
            return None

        title = self.extract_title_from_html(html, fallback=name)
        if not title:
            return None

        page_text = self.extract_page_text_from_html(html)
        subtitle = self.extract_subtitle_from_html(html)
        if self.is_probably_blocked_page(page_text, title=title, html=html):
            console.print("    [yellow]Rejected blocked or error page[/]")
            return None

        pdf_urls = self.extract_pdf_candidates_from_html(html, url)
        pdf_texts: list[str] = []
        for pdf_url in self.prioritize_pdf_urls(pdf_urls, max_pdfs=self.max_pdfs):
            parsed = await self.parse_pdf_text(pdf_url)
            if parsed:
                pdf_texts.append(parsed)
        pdf_text = "\n\n".join(pdf_texts)

        description = self.extract_section_from_html(html, ["overview", "description", "about", "product overview"]) or subtitle
        specs = self.extract_section_from_html(html, ["specification", "sizing", "features", "dimensions"])
        if not specs:
            specs = self.extract_sizing_from_text(page_text) or self.extract_sizing_from_text(pdf_text)
        indications = self.extract_section_from_html(html, ["indication", "intended", "indications for use", "intended use"])
        if not indications:
            indications = self.extract_indications_from_text(pdf_text) or self.extract_indications_from_text(page_text)

        category_hint = self.score_category_patterns(
            "\n".join([title, subtitle or "", page_text[:2500], pdf_text[:2500]]),
            self.category_patterns,
        )

        ifu_url, other_pdfs = self.classify_pdf_urls(pdf_urls)

        return ScrapedProduct(
            device_name=title.strip(),
            manufacturer=self.manufacturer,
            category_hint=category_hint,
            what_it_is=description,
            sizing_specs=specs,
            indications=indications,
            source_url=url,
            ifu_pdf_url=ifu_url,
            other_pdf_urls=other_pdfs,
            raw_html=html[:50000],
        )

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

    def _looks_like_product_link(self, href: str) -> bool:
        normalized = self.normalize_url(href, page_url=self.products_url)
        if not normalized:
            return False
        path = normalized.lower().rstrip("/")
        return "/products/" in path and not path.endswith("/products")

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return self.clean_text(slug.replace("-", " ").replace("_", " ")).title()
