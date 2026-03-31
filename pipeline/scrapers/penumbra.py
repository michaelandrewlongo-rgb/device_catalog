"""Scraper for Penumbra neurovascular product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover
    StealthyFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class PenumbraScraper(ManufacturerScraper):
    manufacturer = "penumbra"
    base_url = "https://www.penumbrainc.com"
    products_url = "https://www.penumbrainc.com/neuro/"
    request_delay = 3.0
    max_pdfs = 4

    # Known product page paths (fallback if discovery fails)
    KNOWN_PRODUCTS = [
        {
            "url": "https://www.penumbrainc.com/neuro/",
            "name": "Penumbra Neuro Product Listing",
            "is_listing": True,
        },
    ]

    category_patterns: list[tuple[str, list[str]]] = [
        ("aspiration", [r"\baspiration\b", r"\bjet 7\b", r"\brace 6\b", r"\brace6\b"]),
        ("embolic-coil", [r"\bcoil\b", r"\bruby\b", r"\bsmart coil\b", r"\bembolization coil\b"]),
        ("distal-access", [r"\baccess catheter\b", r"\bneuron\b", r"\bbenchmark\b", r"\bdistal access\b"]),
        ("thrombectomy", [r"\bthrombectomy\b", r"\brevascularization\b", r"\bstent retriever\b"]),
        ("flow-diverter", [r"\bflow divert", r"\bsilk\b"]),
        ("microcatheter", [r"\bmicrocatheter\b", r"\bmicrovention\b"]),
    ]

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from Penumbra's neuro product pages."""
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
            for row in self.KNOWN_PRODUCTS:
                found[row["url"]] = row
            for path in ("/products/neuro-access-catheters/", "/products/neuro-embolization/"):
                full_url = self.base_url + path
                found.setdefault(full_url, {"url": full_url, "name": path.split("/")[-2]})

        urls = sorted(found.values(), key=lambda item: item["url"])
        console.print(f"[cyan]Discovered {len(urls)} Penumbra product URLs[/]")
        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Penumbra product page."""
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

        description = (
            self.extract_section_from_html(html, ["description", "overview", "about", "product overview"])
            or subtitle
        )
        indications = (
            self.extract_section_from_html(html, ["indication", "intended use", "cleared for", "indications for use"])
            or self.extract_indications_from_text(pdf_text)
            or self.extract_indications_from_text(page_text)
        )
        specs = (
            self.extract_section_from_html(html, ["specification", "dimensions", "sizing", "compatibility", "features"])
            or self.extract_sizing_from_text(page_text)
            or self.extract_sizing_from_text(pdf_text)
        )

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
        normalized = self.normalize_url(href, page_url=self.products_url, allowed_domains=("penumbrainc.com",))
        if not normalized:
            return False
        path = normalized.lower().rstrip("/")
        if "/products/" not in path or path.endswith("/products"):
            return False
        slug = path.split("/")[-1]
        if slug in {"neuro", "products"}:
            return False
        return True

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        slug = slug.replace("-", " ").replace("_", " ")
        return self.clean_text(slug).title()
