# pipeline/fetch_images.py
"""Download product images for catalog devices.

For each device that has an enriched JSON with a source_url:
  1. Fetch the manufacturer page
  2. Extract og:image meta tag (primary)
  3. Fallback: first <img> in a product-image container, or first img with width > 200
  4. Download to site/images/{device_id}.{ext}
  5. Skip if image already exists (idempotent)

Usage:
    python -m pipeline.fetch_images           # all devices
    python -m pipeline.fetch_images --dry-run # report only, no downloads
    python -m pipeline.fetch_images --limit 10
    python -m pipeline.fetch_images --device aspiration--balt--ballast
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

_THIS_DIR = Path(__file__).resolve().parent
CATALOG_ROOT = _THIS_DIR.parent
ENRICHED_DIR = _THIS_DIR / "data" / "enriched"
IMAGES_DIR = CATALOG_ROOT / "site" / "images"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
REQUEST_TIMEOUT = 15
INTER_REQUEST_DELAY = 1.0  # seconds between fetches to same host


def find_enriched_json(device_id: str) -> Optional[Path]:
    p = ENRICHED_DIR / f"{device_id}.json"
    return p if p.exists() else None


def get_source_url(device_id: str) -> Optional[str]:
    """Return source_url from enriched JSON, or None."""
    p = find_enriched_json(device_id)
    if p is None:
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    url = data.get("source_url")
    return url if url and isinstance(url, str) and url.startswith("http") else None


def image_ext_from_url(url: str) -> Optional[str]:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in VALID_EXTENSIONS:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None


def image_ext_from_content_type(content_type: str) -> Optional[str]:
    ct = content_type.split(";")[0].strip().lower()
    if ct == "image/jpeg":
        return ".jpg"
    ext = mimetypes.guess_extension(ct)
    if ext in VALID_EXTENSIONS:
        return ".jpg" if ext == ".jpeg" else ext
    return None


def extract_og_image(soup: BeautifulSoup) -> Optional[str]:
    tag = soup.find("meta", property="og:image")
    if tag and tag.get("content"):
        return tag["content"].strip()
    tag = soup.find("meta", attrs={"name": "og:image"})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def extract_fallback_image(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Return first qualifying product image: product container > width > 200."""
    product_containers = soup.find_all(
        class_=lambda c: c and any(
            kw in c for kw in (
                "product-image", "product-photo", "hero-image",
                "product-img", "product__image", "product-media"
            )
        )
    )
    candidates: list[str] = []
    for container in product_containers:
        for img in container.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if src:
                candidates.append(src)

    if not candidates:
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue
            try:
                w = int(img.get("width", 0))
            except (ValueError, TypeError):
                w = 0
            if w > 200:
                candidates.append(src)

    for src in candidates:
        abs_url = urllib.parse.urljoin(base_url, src)
        parsed = urllib.parse.urlparse(abs_url)
        if parsed.scheme in ("http", "https"):
            return abs_url
    return None


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return None


def download_image(image_url: str, dest_path: Path) -> bool:
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
        return True
    except Exception:
        return False


def find_existing_image(device_id: str) -> Optional[Path]:
    for ext in VALID_EXTENSIONS:
        p = IMAGES_DIR / f"{device_id}{ext}"
        if p.exists():
            return p
    return None


def fetch_image_for_device(device_id: str, dry_run: bool = False) -> str:
    """Try to fetch and save an image for device_id.

    Returns: 'skipped' | 'fetched' | 'failed' | 'no_url' | 'no_enriched'
    """
    if find_existing_image(device_id):
        return "skipped"

    source_url = get_source_url(device_id)
    if source_url is None:
        return "no_enriched" if find_enriched_json(device_id) is None else "no_url"

    soup = fetch_page(source_url)
    if soup is None:
        return "failed"

    image_url = extract_og_image(soup)
    if image_url is None:
        image_url = extract_fallback_image(soup, source_url)
    if image_url is None:
        return "failed"

    image_url = urllib.parse.urljoin(source_url, image_url)

    ext = image_ext_from_url(image_url)
    if ext is None:
        try:
            head = requests.head(image_url, headers=HEADERS, timeout=10, allow_redirects=True)
            ext = image_ext_from_content_type(head.headers.get("content-type", ""))
        except Exception:
            pass
    if ext is None:
        ext = ".jpg"

    dest = IMAGES_DIR / f"{device_id}{ext}"

    if dry_run:
        print(f"  [DRY-RUN] would save: {dest.name}  from  {image_url}")
        return "fetched"

    return "fetched" if download_image(image_url, dest) else "failed"


def get_all_device_ids() -> list[str]:
    ids = []
    for f in CATALOG_ROOT.iterdir():
        if f.name.endswith("--knowledge.md"):
            stem = f.name[: -len("--knowledge.md")]
            if len(stem.split("--")) >= 3:
                ids.append(stem)
    return sorted(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch product images for catalog devices.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--device", type=str, default="")
    args = parser.parse_args()

    device_ids = [args.device] if args.device else get_all_device_ids()
    if args.limit > 0:
        device_ids = device_ids[: args.limit]

    counts: dict[str, int] = {k: 0 for k in ("fetched", "skipped", "failed", "no_url", "no_enriched")}
    last_host = ""

    for device_id in device_ids:
        # Only compute host / sleep when the image actually needs fetching
        if find_existing_image(device_id) is None:
            source_url = get_source_url(device_id)
            if source_url:
                host = urllib.parse.urlparse(source_url).netloc
                if host == last_host:
                    time.sleep(INTER_REQUEST_DELAY)
                last_host = host

        result = fetch_image_for_device(device_id, dry_run=args.dry_run)
        counts[result] = counts.get(result, 0) + 1
        if result not in ("no_url", "no_enriched"):
            symbol = {"fetched": "OK", "skipped": "--", "failed": "FAIL"}.get(result, "??")
            print(f"  [{symbol}] {device_id}")

    print(
        f"\nResults: {counts['fetched']} fetched, {counts['skipped']} skipped, "
        f"{counts['failed']} failed, "
        f"{counts['no_url']} no source_url, {counts['no_enriched']} no enriched JSON"
    )


if __name__ == "__main__":
    main()
