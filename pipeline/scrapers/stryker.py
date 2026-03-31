"""Scraper for Stryker neurovascular/neurosurgical product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover
    StealthyFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class StrykerScraper(ManufacturerScraper):
    manufacturer = "stryker"
    base_url = "https://www.stryker.com"
    request_delay = 3.0

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return ("www.stryker.com", "stryker.com")

    neuro_keywords = (
        "/neurovascular/products/",
        "/nse/products/",
    )

    category_patterns: list[tuple[str, list[str]]] = [
        ("thrombectomy", [r"\btrevo\b", r"\bthrombectomy\b", r"\brevascularization\b", r"\bstroke retriev"]),
        ("flow-diverter", [r"\bsurpass\b", r"\bflow divert"]),
        ("intracranial-stent", [r"\bneuroform\b", r"\batlas stent\b", r"\bstent\b"]),
        ("embolic-coil", [r"\btarget\b", r"\bcoil\b", r"\bdetachable coil\b"]),
        ("microcatheter", [r"\bexcelsior\b", r"\bsl-10\b", r"\bmicrocatheter\b"]),
        ("distal-access", [r"\baxs\b", r"\bcatalyst\b", r"\bdistal access\b"]),
        ("guidewire", [r"\bsynchro\b", r"\bguidewire\b"]),
        ("pedicle-screw", [r"\bxia\b", r"\bpedicle\b", r"\bspinal\b"]),
        ("navigation", [r"\bspinemap\b", r"\bnavigation\b"]),
    ]

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from Stryker's neurovascular portfolio pages."""
        found: dict[str, dict[str, str]] = {}

        # Stryker's product links are on the AIS and hemorrhagic portfolio pages
        for listing_url in (
            "https://www.stryker.com/us/en/portfolios/neurotechnology-spine/neurovascular/acute-ischemic-stroke.html",
            "https://www.stryker.com/us/en/portfolios/neurotechnology-spine/neurovascular/hemorrhagic-stroke.html",
            "https://www.stryker.com/us/en/nse.html",
        ):
            html = await self._fetch_html_content(listing_url)
            if not html:
                continue
            for href, text in self.extract_links_from_html(html, listing_url):
                if self._looks_like_product_link(href):
                    found[href] = {"url": href, "name": text or self._slug_to_name(href)}

        if not found:
            for href in await self.discover_from_sitemap():
                if self._looks_like_product_link(href):
                    found[href] = {"url": href, "name": self._slug_to_name(href)}

        urls = sorted(found.values(), key=lambda item: item["url"])
        console.print(f"[cyan]Discovered {len(urls)} Stryker URLs[/]")
        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Stryker product page."""
        html = await self._fetch_html_content(url)
        if not html:
            return None

        title = self.extract_title_from_html(html, fallback=name)
        if not title:
            return None

        subtitle = self.extract_subtitle_from_html(html)
        page_text = self.extract_page_text_from_html(html)
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

        category_hint = self.score_category_patterns(
            "\n".join([title, subtitle or "", page_text[:2500], pdf_text[:2500]]),
            self.category_patterns,
        )

        description = self.extract_section_from_html(
            html,
            ["overview", "description", "about", "product overview"],
        ) or subtitle
        specs = self.extract_section_from_html(
            html,
            ["specification", "sizing", "dimensions", "features", "technical specifications"],
        )
        if not specs:
            specs = self.extract_sizing_from_text(page_text) or self.extract_sizing_from_text(pdf_text)
        indications = self.extract_section_from_html(
            html,
            ["indication", "intended use", "clinical", "indications for use"],
        )
        if not indications:
            indications = self.extract_indications_from_text(pdf_text) or self.extract_indications_from_text(page_text)

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

    async def _fetch_html_content(self, url: str) -> str | None:
        if StealthyFetcher is None:
            return await self.fetch_html_via_requests(url)
        return await super().fetch_html(
            StealthyFetcher,
            url,
            headless=True,
            network_idle=True,
        )

    def _looks_like_product_link(self, href: str) -> bool:
        normalized = self.normalize_url(href, page_url=self.base_url, allowed_domains=self.allowed_domains)
        if not normalized:
            return False
        path = normalized.lower().rstrip("/")
        if any(segment in path for segment in ("/privacy", "/contact", "/news", "/careers", "/about", "/investor")):
            return False
        if not any(keyword in path for keyword in self.neuro_keywords):
            return False
        # Must end with a specific product slug, not just a listing page
        slug = path.split("/")[-1]
        if slug in {"products", "neurovascular", "nse", "acute-ischemic-stroke", "hemorrhagic-stroke"}:
            return False
        return True

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return self.clean_text(slug.replace("-", " ").replace("_", " ")).title()
