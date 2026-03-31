"""Scraper for Cerenovus (J&J MedTech) neurovascular product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import DynamicFetcher
except Exception:  # pragma: no cover
    DynamicFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class CerenovusScraper(ManufacturerScraper):
    manufacturer = "cerenovus"
    base_url = "https://www.jnjmedtech.com"
    request_delay = 4.0
    timeout = 25

    product_segments = (
        "cerenovus",
        "embotrap",
        "galaxy",
        "cereglide",
        "trufill",
        "bravo",
        "emboguard",
    )

    category_patterns: list[tuple[str, list[str]]] = [
        ("thrombectomy", [r"\bembotrap\b", r"\bthrombectomy\b", r"\brevascularization\b"]),
        ("embolic-coil", [r"\bgalaxy\b", r"\bcoil\b", r"\bemboliz"]),
        ("distal-access", [r"\bcereglide\b", r"\baspiration\b", r"\bintermediate\b"]),
        ("liquid-embolic", [r"\btrufill\b", r"\bnbca\b", r"\bliquid\b"]),
        ("flow-diverter", [r"\bbravo\b", r"\bflow divert"]),
        ("balloon-catheter", [r"\bemboguard\b", r"\bballoon\b"]),
    ]

    seed_urls = (
        "https://www.jnjmedtech.com/en-US/companies/cerenovus",
        "https://www.jnjmedtech.com/en-US/specialties/neurointerventional/",
        "https://www.jnjmedtech.com/en-US/cerenovus-stroke-solutions",
    )

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from J&J MedTech and fall back cleanly."""
        urls: list[dict[str, str]] = []
        seen: set[str] = set()

        for seed_url in self.seed_urls:
            listing_html = await self._fetch_html_content(seed_url)
            if not listing_html:
                continue
            for href, text in self.extract_links_from_html(listing_html, seed_url):
                self.add_discovered_url(
                    urls,
                    seen,
                    href,
                    text,
                    page_url=seed_url,
                    require_segments=self.product_segments,
                )

        if not urls:
            for href in await self.discover_from_sitemap():
                self.add_discovered_url(
                    urls,
                    seen,
                    href,
                    "",
                    page_url=self.base_url,
                    require_segments=self.product_segments,
                )

        if not urls:
            console.print("[yellow]Using high-level Cerenovus landing pages only; verified product detail URLs were not discovered[/]")
            urls = [{"url": url, "name": url.rsplit("/", 2)[-2].replace("-", " ").title()} for url in self.seed_urls]

        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Cerenovus/J&J product page with HTML and PDF enrichment."""
        html = await self._fetch_html_content(url)
        if not html:
            return None

        title = self.extract_title_from_html(html, fallback=name)
        if not title:
            return None

        subtitle = self.extract_subtitle_from_html(html)
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

        description = self.extract_section_from_html(html, ["overview", "description", "about", "product overview"]) or subtitle
        indications = self.extract_section_from_html(html, ["indications", "indications for use", "intended use", "intended purpose"])
        if not indications:
            indications = self.extract_indications_from_text(pdf_text) or self.extract_indications_from_text(page_text)

        category_hint = self.score_category_patterns(
            "\n".join([title, subtitle or "", page_text[:2500], pdf_text[:2500]]),
            self.category_patterns,
        )

        ifu_url, other_pdfs = self.classify_pdf_urls(pdf_urls)

        return ScrapedProduct(
            device_name=title,
            manufacturer=self.manufacturer,
            category_hint=category_hint,
            what_it_is=description,
            indications=indications,
            source_url=url,
            ifu_pdf_url=ifu_url,
            other_pdf_urls=other_pdfs,
            raw_html=raw_html,
        )

    async def _fetch_html_content(self, url: str) -> str | None:
        if DynamicFetcher is None:
            return await self.fetch_html_via_requests(url)
        return await super().fetch_html(
            DynamicFetcher,
            url,
            headless=True,
            network_idle=True,
        )
