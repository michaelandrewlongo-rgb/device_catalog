"""Scraper for Medtronic neurovascular product pages.

Uses DynamicFetcher because Medtronic's site is React/JS-heavy.
"""

from __future__ import annotations

try:
    from scrapling.fetchers import DynamicFetcher
except Exception:  # pragma: no cover
    DynamicFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class MedtronicScraper(ManufacturerScraper):
    manufacturer = "medtronic"
    base_url = "https://www.medtronic.com"
    products_url = "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular.html"
    request_delay = 4.0  # Medtronic site can be slow
    timeout = 30

    non_product_slugs = {
        "neurological",
        "neurological.html",
        "overview",
        "products",
        "product",
        "resources",
        "support",
        "contact",
        "about",
        "careers",
    }

    category_patterns: list[tuple[str, list[str]]] = [
        ("thrombectomy", [r"\bsolitaire\b", r"\brevascularization\b", r"\bthrombectomy\b"]),
        ("flow-diverter", [r"\bpipeline\b", r"\bflow divert"]),
        ("liquid-embolic", [r"\bonyx\b", r"\bliquid embolic\b"]),
        ("aspiration", [r"\breact\b", r"\baspiration\b", r"\briptide\b"]),
        ("microcatheter", [r"\bechelon\b", r"\bphenom\b", r"\bmarksman\b", r"\bmicrocatheter\b"]),
        ("csf-shunt", [r"\bstrata\b", r"\bshunt\b", r"\bvalve\b"]),
        ("navigation", [r"\bstealth\b", r"\bnavigation\b"]),
    ]

    fallback_products = [
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/stent-retrievers/solitaire-x-revascularization-device.html", "name": "Solitaire X"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/aneurysm-flow-diverters/pipeline-flex-with-shield-technology.html", "name": "Pipeline Flex"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/liquid-embolics/onyx-liquid-embolic-system.html", "name": "Onyx LES"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/catheters/micro-catheters/echelon-micro-catheter.html", "name": "Echelon"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/catheters/micro-catheters/phenom-catheter.html", "name": "Phenom"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/catheters/micro-catheters/marksman-micro-catheter.html", "name": "Marksman"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/catheters/aspiration-neurovascular-catheters/react-catheter.html", "name": "React"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/aspiration/riptide-aspiration-system.html", "name": "Riptide"},
        {"url": "https://www.medtronic.com/en-us/healthcare-professionals/products/neurological/neurovascular/aspiration/apro-70-aspiration-catheter.html", "name": "APRO"},
    ]

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs from Medtronic's neurovascular pages."""
        found: dict[str, dict[str, str]] = {}

        html = await self._fetch_listing_html()
        if html:
            for href, text in self.extract_links_from_html(html, self.products_url):
                if self._looks_like_product_link(href, text):
                    found[href] = {"url": href, "name": text or self._slug_to_name(href)}

        if not found:
            for href in await self.discover_from_sitemap():
                if self._looks_like_product_link(href, ""):
                    found[href] = {"url": href, "name": self._slug_to_name(href)}

        if not found:
            console.print("[yellow]Using known product URLs[/]")
            for row in self.fallback_products:
                found[row["url"]] = row

        urls = sorted(found.values(), key=lambda item: item["url"])
        console.print(f"[cyan]Discovered {len(urls)} Medtronic product URLs[/]")
        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Medtronic product page with PDF enrichment."""
        html = await self._fetch_detail_html(url)
        if not html:
            return None

        title = self.extract_title_from_html(html, fallback=name)
        if not title:
            return None

        page_text = self.extract_page_text_from_html(html)
        subtitle = self.extract_subtitle_from_html(html)
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

        description = self.extract_section_from_html(html, ["overview", "description", "about", "what is"]) or subtitle
        specs = self.extract_section_from_html(html, ["specification", "sizing", "features", "dimensions"])
        if not specs:
            specs = self.extract_sizing_from_text(page_text) or self.extract_sizing_from_text(pdf_text)

        indications = self.extract_section_from_html(html, ["indication", "intended use", "indications for use"])
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
            raw_html=raw_html,
        )

    async def _fetch_listing_html(self) -> str | None:
        if DynamicFetcher is None:
            return await self.fetch_html_via_requests(self.products_url)
        return await self.fetch_html(
            DynamicFetcher,
            self.products_url,
            headless=True,
            network_idle=True,
        )

    async def _fetch_detail_html(self, url: str) -> str | None:
        if DynamicFetcher is None:
            return await self.fetch_html_via_requests(url)
        return await self.fetch_html(
            DynamicFetcher,
            url,
            headless=True,
            network_idle=True,
        )

    def _looks_like_product_link(self, href: str, text: str) -> bool:
        normalized = self.normalize_url(href, page_url=self.products_url)
        if not normalized:
            return False
        path = normalized.lower()
        if "/healthcare-professionals/products/neurological" not in path:
            return False

        slug = path.rstrip("/").split("/")[-1]
        if not slug or slug in self.non_product_slugs:
            return False

        link_text = self.clean_text(text).lower()
        if link_text in {"overview", "learn more", "read more", "products", "view all"}:
            return False
        return True

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return self.clean_text(slug.replace("-", " ").replace("_", " ")).title()
