"""Scraper for MicroVention / Terumo Neuro product pages."""

from __future__ import annotations

try:
    from scrapling.fetchers import StealthyFetcher
except Exception:  # pragma: no cover
    StealthyFetcher = None

from .base import ManufacturerScraper, ScrapedProduct, console


class MicroVentionScraper(ManufacturerScraper):
    manufacturer = "microvention"
    base_url = "https://www.terumoneuro.com"
    products_url = "https://www.terumoneuro.com/products"
    request_delay = 2.0
    timeout = 25
    max_pdfs = 3

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        return ("terumoneuro.com", "www.terumoneuro.com")

    non_product_slugs = {
        "products",
        "product-use-and-safety",
        "company-overview",
        "history-milestones",
        "leadership-team",
        "life-at-terumo-neuro",
        "job-openings",
        "in-the-news",
        "press-releases",
        "upcoming-events",
        "glossary",
        "legal-compliance",
        "order-tracking",
        "press-resources",
        "contact-us",
        "search",
    }

    section_aliases = {
        "description": ["overview", "description", "about", "product overview", "device description"],
        "indications": ["indications", "indications for use", "intended use", "intended purpose"],
        "specifications": [
            "specifications",
            "technical specifications",
            "technical data",
            "sizes",
            "size",
            "dimensions",
            "ordering information",
            "product codes",
            "models",
            "available sizes",
        ],
    }

    category_patterns: list[tuple[str, list[str]]] = [
        ("flow-diverter", [r"\bfred\b", r"\bflow diverter\b", r"\bflow diversion\b"]),
        ("intracranial-stent", [r"\blvis\b", r"\bcoil assist stent\b", r"\bstent\b"]),
        ("intrasaccular", [r"\bweb\b", r"\bintrasaccular\b", r"woven endobridge"]),
        ("embolic-coil", [r"\bhydrocoil\b", r"\bcosmos\b", r"\bhydrofill\b", r"\bhydroframe\b", r"\bhydrosoft\b", r"\bhypersoft\b", r"\bvfc\b", r"\bcoil\b"]),
        ("microcatheter", [r"\bheadway\b", r"\bvia\b", r"\bmicrocatheter\b"]),
        ("delivery-catheter", [r"\bwedge\b", r"\bdelivery catheter\b"]),
        ("distal-access", [r"\bsofia\b", r"\bintermediate catheter\b", r"\bdistal access\b", r"\bsupport catheter\b"]),
        ("aspiration-catheter", [r"\baspiration catheter\b", r"\bflow plus\b"]),
        ("balloon-catheter", [r"\bscepter\b", r"\bballoon catheter\b", r"\bocclusion balloon\b"]),
        ("balloon-guide-catheter", [r"\bbobby\b", r"\bballoon guide catheter\b"]),
        ("guiding-catheter", [r"\bchaperon\b", r"\bguiding catheter\b", r"\bguide catheter\b"]),
        ("guidewire", [r"\bheadliner\b", r"\btraxcess\b", r"\bguidewire\b", r"\bmicrowire\b"]),
        ("stent-retriever", [r"\beric\b", r"\bretrieval device\b", r"\bstent retriever\b"]),
        ("accessory", [r"\bsyringe kit\b", r"\btubing kit\b", r"\baccessories\b"]),
    ]

    fallback_products = [
        {"url": "https://www.terumoneuro.com/products/bobby-balloon-guide-catheters", "name": "BOBBY Balloon Guide Catheters"},
        {"url": "https://www.terumoneuro.com/products/chaperon-guiding-catheters", "name": "Chaperon Guiding Catheters"},
        {"url": "https://www.terumoneuro.com/products/cosmos-platinum-coils", "name": "Cosmos Platinum Coils"},
        {"url": "https://www.terumoneuro.com/products/eric-retrieval-device", "name": "ERIC Retrieval Device"},
        {"url": "https://www.terumoneuro.com/products/fred-family", "name": "FRED"},
        {"url": "https://www.terumoneuro.com/products/headliner-guidewires", "name": "Headliner Guidewires"},
        {"url": "https://www.terumoneuro.com/products/headway-microcatheters", "name": "Headway Microcatheters"},
        {"url": "https://www.terumoneuro.com/products/hydrofill-specialty-filling-coils", "name": "HydroFill Specialty Filling Coils"},
        {"url": "https://www.terumoneuro.com/products/hydroframe-hydrosoft-hypersoft-coils", "name": "HydroFrame HydroSoft HyperSoft Coils"},
        {"url": "https://www.terumoneuro.com/products/lvis-family", "name": "LVIS & LVIS Jr"},
        {"url": "https://www.terumoneuro.com/products/lvis-evo", "name": "LVIS EVO"},
        {"url": "https://www.terumoneuro.com/products/scepter-family", "name": "Scepter C and XC"},
        {"url": "https://www.terumoneuro.com/products/scepter-mini", "name": "Scepter Mini"},
        {"url": "https://www.terumoneuro.com/products/sofia-family", "name": "SOFIA Family"},
        {"url": "https://www.terumoneuro.com/products/sofia-88", "name": "SOFIA 88"},
        {"url": "https://www.terumoneuro.com/products/sofia-ex", "name": "SOFIA EX"},
        {"url": "https://www.terumoneuro.com/products/sofia-flow-plus", "name": "SOFIA Flow Plus"},
        {"url": "https://www.terumoneuro.com/products/sofia-plus", "name": "SOFIA Plus"},
        {"url": "https://www.terumoneuro.com/products/traxcess-guidewires", "name": "Traxcess Guidewires"},
        {"url": "https://www.terumoneuro.com/products/traxcess-mini", "name": "Traxcess Mini Guidewires"},
        {"url": "https://www.terumoneuro.com/products/via-microcatheters", "name": "VIA Microcatheters"},
        {"url": "https://www.terumoneuro.com/products/web-family", "name": "WEB Embolization System"},
        {"url": "https://www.terumoneuro.com/products/wedge-delivery-catheter", "name": "WEDGE Delivery Catheter"},
    ]

    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product URLs with requests/sitemap fallback."""
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
            console.print("[yellow]Using fallback Terumo Neuro product list[/]")
            for row in self.fallback_products:
                found[row["url"]] = row

        urls = sorted(found.values(), key=lambda item: item["url"])
        console.print(f"[cyan]Discovered {len(urls)} Terumo Neuro product URLs[/]")
        return urls

    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a Terumo Neuro / MicroVention product page with PDF enrichment."""
        html = await self._fetch_detail_html(url)
        if not html:
            console.print("    [red]Fetch failed[/]")
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
        for pdf_url in self.prioritize_pdf_urls(pdf_urls, max_pdfs=self.max_pdfs):
            parsed = await self.parse_pdf_text(pdf_url)
            if parsed:
                pdf_texts.append(parsed)
        pdf_text = "\n\n".join(pdf_texts)

        description = self.extract_section_from_html(html, self.section_aliases["description"]) or subtitle
        sizing_specs = self.extract_section_from_html(html, self.section_aliases["specifications"])
        if not sizing_specs:
            sizing_specs = self.extract_sizing_from_text(page_text) or self.extract_sizing_from_text(pdf_text)

        indications = self.extract_section_from_html(html, self.section_aliases["indications"])
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
            sizing_specs=sizing_specs,
            indications=indications,
            source_url=url,
            ifu_pdf_url=ifu_url,
            other_pdf_urls=other_pdfs,
            raw_html=raw_html,
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

    def _looks_like_product_link(self, href: str, text: str) -> bool:
        path = self.normalize_url(href, page_url=self.products_url)
        if not path:
            return False
        path = path.lower()
        parsed = path.rstrip("/")
        if "/products/" not in parsed or parsed.endswith("/products"):
            return False
        slug = parsed.split("/")[-1]
        if not slug or slug in self.non_product_slugs:
            return False
        link_text = self.clean_text(text).lower()
        if link_text in {"products", "find a product", "learn more", "overview", "read more", "click here"}:
            return False
        return True

    def _slug_to_name(self, url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return self.clean_text(slug.replace("-", " ").replace("_", " ")).title()
