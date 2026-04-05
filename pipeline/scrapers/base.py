"""Abstract base class for manufacturer website scrapers."""

import asyncio
import io
import json
import re
import time
import warnings
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from html import unescape
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse

from pydantic import BaseModel, Field
from rich.console import Console

from ..config import DATA_DIR

console = Console()


async def fetch_sync_in_thread(fetcher_cls, url: str, **kwargs):
    """Run a synchronous Scrapling fetcher inside an asyncio event loop.

    Scrapling's StealthyFetcher/DynamicFetcher use Playwright's sync API,
    which cannot be called directly from async code. This wraps the call
    in a thread via asyncio.to_thread() so the event loop isn't blocked.
    """
    return await asyncio.to_thread(fetcher_cls.fetch, url, **kwargs)


class ScrapedProduct(BaseModel):
    """Data extracted from a manufacturer product page."""
    device_name: str
    manufacturer: str                          # Canonical slug
    category_hint: str = ""                    # Best-guess catalog category
    what_it_is: str | None = None
    sizing_specs: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    compatible_with: str | None = None
    use_notes: str | None = None
    deployment_steps: str | None = None
    also_known_as: list[str] = Field(default_factory=list)
    source_url: str = ""
    ifu_pdf_url: str | None = None             # Direct link to IFU PDF
    other_pdf_urls: dict[str, str] = Field(default_factory=dict)  # doc_type -> url
    clearance_numbers: list[str] = Field(default_factory=list)     # K-numbers or PMA refs found on page
    raw_html: str = ""


class ManufacturerScraper(ABC):
    """Base class for scraping a manufacturer's product catalog.

    Subclasses implement get_product_urls() to discover product pages and
    scrape_product() to extract structured data from each page.
    """

    manufacturer: str = ""     # Canonical slug (e.g., "penumbra")
    base_url: str = ""
    request_delay: float = 3.0  # Seconds between requests
    timeout: float = 25.0
    blocked_page_patterns: tuple[str, ...] = (
        "oops! it looks like there's an error",
        "please switch to a different browser",
        "access denied",
        "403 forbidden",
        "forbidden",
        "page not found",
        "404",
        "something went wrong",
        "an error occurred",
        "temporarily unavailable",
        "enable javascript",
        "enable cookies",
        "request unsuccessful",
    )

    def __init__(self):
        self.output_dir = DATA_DIR / "scraper_raw" / self.manufacturer
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._failed_urls: list[str] = []

    @property
    def allowed_domains(self) -> tuple[str, ...]:
        host = urlparse(self.base_url).netloc.lower()
        return (host,) if host else ()

    @abstractmethod
    async def get_product_urls(self) -> list[dict[str, str]]:
        """Discover product page URLs from the manufacturer's catalog.

        Returns:
            List of dicts with at least {"url": ..., "name": ...}
        """
        ...

    @abstractmethod
    async def scrape_product(self, url: str, name: str = "") -> ScrapedProduct | None:
        """Scrape a single product page.

        Args:
            url: Product page URL.
            name: Product name hint (from catalog listing).

        Returns:
            ScrapedProduct or None if scraping failed.
        """
        ...

    async def run(self, urls: list[dict[str, str]] | None = None) -> list[ScrapedProduct]:
        """Run the scraper: discover URLs, then scrape each product page.

        Args:
            urls: Optional pre-supplied URL list. If None, calls get_product_urls().

        Returns:
            List of successfully scraped products.
        """
        if urls is None:
            console.print(f"[bold blue]Discovering product pages for {self.manufacturer}...[/]")
            urls = await self.get_product_urls()
            console.print(f"  Found {len(urls)} product URLs")

        products: list[ScrapedProduct] = []

        for i, entry in enumerate(urls, 1):
            url = entry["url"]
            name = entry.get("name", "")
            console.print(f"  [{i}/{len(urls)}] Scraping: {name or url}")

            try:
                product = await self.scrape_product(url, name)
                if product:
                    self._save_product(product)
                    products.append(product)
                    console.print(f"    [green]OK[/] - {product.device_name}")
                else:
                    self._failed_urls.append(url)
                    console.print(f"    [yellow]No data extracted[/]")
            except Exception as e:
                self._failed_urls.append(url)
                console.print(f"    [red]Error: {e}[/]")

            await asyncio.sleep(self.request_delay)

        # Log failures
        if self._failed_urls:
            failures_path = self.output_dir / "failed_urls.txt"
            failures_path.write_text("\n".join(self._failed_urls), encoding="utf-8")
            console.print(f"  [yellow]{len(self._failed_urls)} failures logged to {failures_path}[/]")

        console.print(
            f"[bold green]{self.manufacturer}: scraped {len(products)}/{len(urls)} products[/]"
        )
        return products

    def _save_product(self, product: ScrapedProduct) -> None:
        """Save scraped product data as JSON (without raw_html for size)."""
        from slugify import slugify
        fname = slugify(product.device_name, separator="-") + ".json"
        data = product.model_dump(exclude={"raw_html"})
        (self.output_dir / fname).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load_checkpoint(self) -> list[str]:
        """Load previously scraped product filenames to skip re-scraping."""
        return [f.stem for f in self.output_dir.glob("*.json") if f.name != "failed_urls.txt"]

    async def fetch_page(self, fetcher_cls, url: str, retries: int = 2, **kwargs):
        """Fetch a page with light retry handling for flaky JS-heavy sites."""
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return await fetch_sync_in_thread(fetcher_cls, url, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    await asyncio.sleep(min(2 ** attempt, 4))
        console.print(f"    [red]Fetch failed: {last_exc}[/]")
        return None

    async def fetch_html(self, fetcher_cls, url: str, **kwargs) -> str | None:
        """Fetch HTML, falling back to requests when browser-based fetchers fail."""
        page = await self.fetch_page(fetcher_cls, url, **kwargs)
        if page is not None:
            html = getattr(page, "html", None)
            if html:
                browser_html = str(html)
                if not self.is_probably_blocked_page(
                    self.extract_page_text_from_html(browser_html),
                    title=self.extract_title_from_html(browser_html),
                    html=browser_html,
                ):
                    return browser_html
                console.print(f"[yellow]Browser fetch returned blocked/error content for {url}; trying requests fallback[/]")

        fallback_html = await self.fetch_html_via_requests(url)
        if fallback_html and not self.is_probably_blocked_page(
            self.extract_page_text_from_html(fallback_html),
            title=self.extract_title_from_html(fallback_html),
            html=fallback_html,
        ):
            return fallback_html
        return None

    async def fetch_html_via_requests(self, url: str, retries: int = 2) -> str | None:
        def _inner() -> str | None:
            try:
                import requests
            except Exception:
                return None

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
            last_exc: Exception | None = None
            with requests.Session() as session:
                session.headers.update(headers)
                for attempt in range(retries + 1):
                    try:
                        if attempt:
                            time.sleep(min(attempt, 3))
                        resp = session.get(url, timeout=self.timeout, allow_redirects=True)
                        resp.raise_for_status()
                        return resp.text
                    except Exception as exc:
                        last_exc = exc
            if last_exc:
                console.print(f"[yellow]Requests fetch failed for {url}: {last_exc}[/]")
            return None

        return await asyncio.to_thread(_inner)

    async def fetch_bytes_via_requests(self, url: str, retries: int = 2) -> bytes | None:
        def _inner() -> bytes | None:
            try:
                import requests
            except Exception:
                return None

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            }
            with requests.Session() as session:
                session.headers.update(headers)
                for attempt in range(retries + 1):
                    try:
                        if attempt:
                            time.sleep(min(attempt, 3))
                        resp = session.get(url, timeout=self.timeout, allow_redirects=True)
                        resp.raise_for_status()
                        return resp.content
                    except Exception:
                        continue
            return None

        return await asyncio.to_thread(_inner)

    @staticmethod
    def clean_text(text: str | None) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    @staticmethod
    def clean_multiline_text(text: str | None) -> str:
        if not text:
            return ""
        text = unescape(text)
        text = text.replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in str(text).splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def dedupe_preserve(items: Iterable[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            stripped = item.strip()
            key = stripped.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(stripped)
        return out

    def normalize_url(
        self,
        href: str,
        page_url: str | None = None,
        allowed_domains: tuple[str, ...] | None = None,
    ) -> str | None:
        if not href:
            return None
        href = href.strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            return None

        absolute = urljoin(page_url or self.base_url, href)
        absolute, _ = urldefrag(absolute)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            return None

        domains = allowed_domains or self.allowed_domains
        host = parsed.netloc.lower()
        if domains and not any(host == domain or host.endswith(f".{domain}") for domain in domains):
            return None
        return parsed.geturl().rstrip("/")

    def add_discovered_url(
        self,
        urls: list[dict[str, str]],
        seen: set[str],
        href: str,
        text: str,
        *,
        page_url: str | None = None,
        allowed_domains: tuple[str, ...] | None = None,
        require_segments: tuple[str, ...] = (),
        exclude_segments: tuple[str, ...] = (),
    ) -> None:
        normalized = self.normalize_url(href, page_url=page_url, allowed_domains=allowed_domains)
        if not normalized:
            return
        normalized_lower = normalized.lower()
        if require_segments and not any(segment in normalized_lower for segment in require_segments):
            return
        if exclude_segments and any(segment in normalized_lower for segment in exclude_segments):
            return
        if normalized in seen:
            return

        seen.add(normalized)
        urls.append({"url": normalized, "name": self.clean_text(text) or normalized.rsplit("/", 1)[-1]})

    def extract_page_text(self, page, selectors: tuple[str, ...] = ("main", "body")) -> str | None:
        for selector in selectors:
            nodes = page.css(selector)
            if not nodes:
                continue
            node = nodes[0] if isinstance(nodes, list) else nodes
            raw_text = getattr(node, "text", "") or ""
            text = "\n".join(
                cleaned for cleaned in (self.clean_text(line) for line in raw_text.splitlines()) if cleaned
            )
            if text:
                return text
        return None

    def extract_page_text_from_html(self, html: str) -> str:
        soup = self.get_soup_from_html(html)
        if soup is not None:
            for selector in ("script", "style", "noscript", "svg", "header", "footer"):
                for node in soup.select(selector):
                    node.decompose()
            main = soup.select_one("main") or soup.body or soup
            return self.clean_multiline_text(main.get_text("\n", strip=True))
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", "\n", text)
        return self.clean_multiline_text(text)

    def extract_title(self, page, fallback: str = "") -> str:
        for selector in ("h1", "[data-testid='page-title']"):
            nodes = page.css(selector)
            if not nodes:
                continue
            node = nodes[0] if isinstance(nodes, list) else nodes
            title = self.clean_text(getattr(node, "text", ""))
            if title:
                return title
        return self.clean_text(fallback)

    def extract_title_from_html(self, html: str, fallback: str = "") -> str:
        soup = self.get_soup_from_html(html)
        if soup is not None:
            node = soup.select_one("h1")
            if node:
                title = self.clean_text(node.get_text(" ", strip=True))
                if title:
                    return title
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
        if match:
            return self.clean_text(re.sub(r"<[^>]+>", " ", match.group(1)))
        return self.clean_text(fallback)

    def extract_subtitle_from_html(self, html: str) -> str | None:
        soup = self.get_soup_from_html(html)
        if soup is not None:
            h1 = soup.select_one("h1")
            if h1:
                for sib in h1.find_all_next(limit=6):
                    text = self.clean_text(sib.get_text(" ", strip=True))
                    if text and len(text) <= 100:
                        return text
        lines = [line for line in self.extract_page_text_from_html(html).splitlines() if line]
        for line in lines[1:8]:
            if len(line) <= 100:
                return line
        return None

    def get_soup_from_html(self, html: str):
        try:
            from bs4 import BeautifulSoup
        except Exception:
            return None
        return BeautifulSoup(html, "html.parser")

    def extract_links_from_html(self, html: str, base_url: str) -> list[tuple[str, str]]:
        soup = self.get_soup_from_html(html)
        out: list[tuple[str, str]] = []
        if soup is not None:
            for a in soup.select("a[href]"):
                href = self.normalize_url(a.get("href", ""), page_url=base_url)
                if href:
                    out.append((href, self.clean_text(a.get_text(" ", strip=True))))
            return out
        for href, text in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
            normalized = self.normalize_url(href, page_url=base_url)
            if normalized:
                out.append((normalized, self.clean_text(re.sub(r"<[^>]+>", " ", text))))
        return out

    def is_probably_blocked_page(self, text: str, title: str = "", html: str = "") -> bool:
        combined = "\n".join(part for part in (title, text, html[:4000]) if part).lower()
        if any(pattern in combined for pattern in self.blocked_page_patterns):
            return True

        alpha_count = sum(ch.isalpha() for ch in text)
        if alpha_count < 80:
            generic_titles = {
                "",
                "error",
                "oops!",
                "access denied",
                "page not found",
                "not found",
            }
            if self.clean_text(title).lower() in generic_titles:
                return True
        return False

    def extract_pdf_links(
        self,
        page,
        *,
        page_url: str,
        allowed_domains: tuple[str, ...] | None = None,
    ) -> tuple[str | None, dict[str, str]]:
        ifu_url: str | None = None
        other_pdfs: dict[str, str] = {}

        for link in page.css("a[href]"):
            href = self.normalize_url(
                link.attrib.get("href", ""),
                page_url=page_url,
                allowed_domains=allowed_domains,
            )
            if not href or ".pdf" not in href.lower():
                continue

            link_text = self.clean_text(getattr(link, "text", "")).lower()
            combined = f"{link_text} {href.lower()}"
            if any(keyword in combined for keyword in ("ifu", "instructions for use", "instructions", "directions for use", "directions")):
                ifu_url = ifu_url or href
            elif "technique" in combined:
                other_pdfs.setdefault("technique", href)
            elif any(keyword in combined for keyword in ("brochure", "catalog")):
                other_pdfs.setdefault("brochure", href)
            elif any(keyword in combined for keyword in ("mri", "mr conditional", "mr safety")):
                other_pdfs.setdefault("mri", href)
            elif any(keyword in combined for keyword in ("safety", "warning", "warnings")):
                other_pdfs.setdefault("safety", href)
            else:
                other_pdfs.setdefault("other", href)

        return ifu_url, other_pdfs

    def extract_pdf_candidates_from_html(self, html: str, page_url: str) -> list[str]:
        urls = [href for href, _ in self.extract_links_from_html(html, page_url) if ".pdf" in href.lower()]
        raw_matches = re.findall(r'https?://[^"\'\s>]+\.pdf(?:\?[^"\'\s>]*)?', html, flags=re.I)
        raw_matches += re.findall(r'/[^"\'\s>]+\.pdf(?:\?[^"\'\s>]*)?', html, flags=re.I)
        for match in raw_matches:
            normalized = self.normalize_url(match, page_url=page_url)
            if normalized:
                urls.append(normalized)
        return self.dedupe_preserve(urls)

    def classify_pdf_urls(self, pdf_urls: list[str]) -> tuple[str | None, dict[str, str]]:
        ifu_url: str | None = None
        other: dict[str, str] = {}
        counts: dict[str, int] = {}
        for url in pdf_urls:
            lower = url.lower()
            if any(token in lower for token in ("ifu", "instructions", "directions-for-use", "product-use", "safety")):
                if ifu_url is None:
                    ifu_url = url
                else:
                    key = self._next_label("ifu_alt", counts)
                    other[key] = url
            elif "brochure" in lower:
                other[self._next_label("brochure", counts)] = url
            elif "mri" in lower:
                other[self._next_label("mri", counts)] = url
            else:
                stem = lower.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "pdf"
                other[self._next_label(stem, counts)] = url
        return ifu_url, other

    def prioritize_pdf_urls(self, pdf_urls: list[str], max_pdfs: int = 3) -> list[str]:
        scored: list[tuple[int, str]] = []
        for url in pdf_urls:
            lower = url.lower()
            score = 0
            if any(token in lower for token in ("ifu", "instructions", "directions-for-use", "product-use", "safety")):
                score += 5
            if "brochure" in lower:
                score += 2
            if "mri" in lower:
                score += 1
            scored.append((score, url))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [url for _, url in scored[:max_pdfs]]

    def extract_section_text(self, text: str, keywords: list[str], max_lines: int = 20) -> str | None:
        """Extract text following a short heading-like line matching keywords."""
        lines = [line.strip() for line in text.splitlines()]
        for i, line in enumerate(lines):
            if not line:
                continue
            line_lower = line.lower()
            if not any(keyword in line_lower for keyword in keywords):
                continue
            if len(line) > 100:
                continue

            collected: list[str] = []
            for candidate in lines[i + 1 : i + 1 + max_lines]:
                if not candidate:
                    continue
                # Stop when we likely hit the next section header.
                if (
                    collected
                    and len(candidate) < 80
                    and candidate[0].isupper()
                    and candidate == self.clean_text(candidate)
                    and sum(ch.isalpha() for ch in candidate) > 3
                ):
                    break
                collected.append(candidate)

            if collected:
                return "\n".join(collected)
        return None

    def extract_section_from_html(self, html: str, aliases: list[str]) -> str | None:
        soup = self.get_soup_from_html(html)
        normalized_aliases = {alias.lower().strip() for alias in aliases}
        if soup is not None:
            for heading in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
                heading_text = self.clean_text(heading.get_text(" ", strip=True)).lower().rstrip(":")
                if heading_text not in normalized_aliases and not any(alias in heading_text for alias in normalized_aliases):
                    continue
                collected: list[str] = []
                for sib in heading.next_siblings:
                    name = getattr(sib, "name", None)
                    if name in {"h1", "h2", "h3", "h4"}:
                        break
                    text = self.clean_text(sib.get_text(" ", strip=True)) if hasattr(sib, "get_text") else self.clean_text(str(sib))
                    if text:
                        collected.append(text)
                    if len(" ".join(collected)) > 2000:
                        break
                if collected:
                    return self.clean_multiline_text("\n".join(self.dedupe_preserve(collected)))
        return self.extract_section_text(self.extract_page_text_from_html(html), aliases)

    async def discover_from_sitemap(self) -> list[str]:
        for sitemap_url in (f"{self.base_url}/robots.txt", f"{self.base_url}/sitemap.xml"):
            text = await self.fetch_html_via_requests(sitemap_url)
            if not text:
                continue
            if sitemap_url.endswith("robots.txt"):
                matches = [line.split(":", 1)[1].strip() for line in text.splitlines() if line.lower().startswith("sitemap:")]
                for nested in matches:
                    urls = await self.parse_sitemap(nested)
                    if urls:
                        return urls
            else:
                urls = await self.parse_sitemap(sitemap_url)
                if urls:
                    return urls
        return []

    async def parse_sitemap(self, sitemap_url: str) -> list[str]:
        xml_text = await self.fetch_html_via_requests(sitemap_url)
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        tag_name = root.tag.lower()
        if tag_name.endswith("sitemapindex"):
            out: list[str] = []
            for loc in root.findall(".//sm:sitemap/sm:loc", ns):
                if loc.text:
                    out.extend(await self.parse_sitemap(loc.text.strip()))
            return out
        if tag_name.endswith("urlset"):
            return [loc.text.strip() for loc in root.findall(".//sm:url/sm:loc", ns) if loc.text]
        return []

    async def parse_pdf_text(self, url: str) -> str | None:
        pdf_bytes = await self.fetch_bytes_via_requests(url)
        if not pdf_bytes:
            return None

        def _inner() -> str | None:
            try:
                from pypdf import PdfReader
            except Exception:
                return None
            warnings.filterwarnings("ignore", category=Warning)
            try:
                reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
                pages = []
                for page in reader.pages:
                    text = page.extract_text() or ""
                    if text:
                        pages.append(text)
                return self.clean_multiline_text("\n\n".join(pages)) or None
            except Exception:
                return None

        return await asyncio.to_thread(_inner)

    def extract_indications_from_text(self, text: str) -> str | None:
        if not text:
            return None
        pattern = re.compile(
            r"(?is)\b(?:indications? for use|indications?|intended use|intended purpose)\b[:\s]+(.{40,1800}?)"
            r"\b(?:contraindications?|warnings?|precautions?|adverse events|potential complications|how supplied|sterilization|storage)\b"
        )
        match = pattern.search(text)
        return self.clean_multiline_text(match.group(1)) if match else None

    def extract_sizing_from_text(self, text: str) -> str | None:
        if not text:
            return None
        working = self.clean_multiline_text(text)
        patterns = [
            r"\b\d+(?:\.\d+)?\s?mm\b",
            r"\b\d+(?:\.\d+)?\s?cm\b",
            r"\b\d+(?:\.\d+)?\s?(?:F|Fr|French)\b",
            r"\b(?:ID|OD)\s*(?:up to|of|:)??\s*\.?\d{2,3}\s*\"?\b",
            r"\b(?:0\.\d{3}|\.\d{3})\s*\"\b",
            r"\bvarious lengths\b",
        ]
        hits: list[str] = []
        for pattern in patterns:
            hits.extend(re.findall(pattern, working, flags=re.I))
        hits = self.dedupe_preserve([self.clean_text(x) for x in hits])
        return "; ".join(hits[:12]) if hits else None

    def score_category_patterns(self, text: str, category_patterns: list[tuple[str, list[str]]]) -> str:
        combined = text.lower()
        scores: dict[str, int] = {}
        for category, patterns in category_patterns:
            score = 0
            for pattern in patterns:
                if re.search(pattern, combined):
                    score += 1
            if score:
                scores[category] = score
        return max(scores.items(), key=lambda item: item[1])[0] if scores else "unknown"

    @staticmethod
    def _next_label(label: str, counts: dict[str, int]) -> str:
        counts[label] = counts.get(label, 0) + 1
        return label if counts[label] == 1 else f"{label}_{counts[label]}"

    @staticmethod
    def compact_raw_html(page, limit: int = 50000) -> str:
        html = getattr(page, "html", "")
        return str(html)[:limit] if html else ""
