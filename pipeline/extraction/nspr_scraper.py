"""NSPR (NeuroSpine Product Review) scraper.

Chrome MCP-assisted scraper for neurospineproductreview.com.
Requires authenticated browser session. Provides helpers that Claude
calls during Chrome MCP sessions to save extracted data.

Data saved to extracted/nspr/{category}/ and extracted/nspr/pdfs_index.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from slugify import slugify

from ..config import EXTRACTED_DIR

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "nspr"

NSPR_CATEGORIES = {
    "screws": "pedicle-screw",
    "intervertebral-cages": "interbody-cage",
    "plates": "cervical-plate",
    "corpectomy-cage": "corpectomy",
    "si-joint": "sacroiliac-fusion",
    "disc-replacement-artificial-disc": "cervical-disc",
    "csf-management": "csf-shunt",
    "laminoplasty": "laminoplasty",
    "neurovascular-devices": "neurovascular",
}


def save_nspr_listing(category_slug: str, products: list[dict]) -> str:
    """Save product listing data from a category page.

    Args:
        category_slug: NSPR URL slug (e.g., 'screws')
        products: List of dicts with keys: name, company, tags, description, slug, href

    Returns:
        Path to saved file.
    """
    cat_dir = OUTPUT_DIR / category_slug
    cat_dir.mkdir(parents=True, exist_ok=True)

    catalog_category = NSPR_CATEGORIES.get(category_slug, "unknown")

    out = {
        "source": "nspr",
        "nspr_category": category_slug,
        "catalog_category": catalog_category,
        "source_url": f"https://neurospineproductreview.com/browse-products/{category_slug}",
        "products": products,
    }

    path = cat_dir / "_listing.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def save_nspr_detail(product_slug: str, data: dict) -> str:
    """Save product detail page data.

    Args:
        product_slug: NSPR URL slug for the product
        data: Dict with keys: name, company, specs (dict), description,
              features (list), pdfs (list of URLs), mfr_link, nspr_url

    Returns:
        Path to saved file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = slugify(product_slug, separator="-") + ".json"

    out = {
        "source": "nspr",
        "nspr_url": data.get("nspr_url", f"https://neurospineproductreview.com/{product_slug}"),
        "device_name": data.get("name", ""),
        "manufacturer": data.get("company", ""),
        "specs": data.get("specs", {}),
        "description": data.get("description", ""),
        "features": data.get("features", []),
        "pdfs": data.get("pdfs", []),
        "mfr_link": data.get("mfr_link", ""),
    }

    path = OUTPUT_DIR / fname
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    if out["pdfs"]:
        _append_pdf_index(out["device_name"], out["manufacturer"], out["pdfs"])

    return str(path)


def _append_pdf_index(
    device_name: str, manufacturer: str, pdf_urls: list[str]
) -> None:
    """Append to the master PDF index for batch downloading."""
    index_path = OUTPUT_DIR / "pdfs_index.json"
    index: list[dict] = []
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    existing_urls = {e["url"] for e in index}
    for url in pdf_urls:
        if url not in existing_urls:
            index.append({
                "device_name": device_name,
                "manufacturer": manufacturer,
                "url": url,
                "filename": url.split("/")[-1],
                "downloaded": False,
            })

    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def download_nspr_pdfs() -> int:
    """Download all PDFs from the NSPR index that haven't been downloaded yet."""
    import time

    import httpx

    index_path = OUTPUT_DIR / "pdfs_index.json"
    if not index_path.exists():
        logger.warning("No NSPR PDF index found")
        return 0

    index = json.loads(index_path.read_text(encoding="utf-8"))
    pdf_dir = OUTPUT_DIR / "pdfs"
    pdf_dir.mkdir(exist_ok=True)

    downloaded = 0
    for entry in index:
        if entry.get("downloaded"):
            continue

        fname = entry["filename"]
        dest = pdf_dir / fname
        if dest.exists():
            entry["downloaded"] = True
            continue

        logger.info("  Downloading: %s", fname)
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(entry["url"])
            if resp.status_code == 200 and len(resp.content) > 1024:
                dest.write_bytes(resp.content)
                entry["downloaded"] = True
                downloaded += 1
            else:
                logger.warning(
                    "  Failed (%d, %d bytes): %s",
                    resp.status_code, len(resp.content), fname,
                )
        except httpx.HTTPError as exc:
            logger.warning("  Error: %s", exc)

        time.sleep(1)

    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("NSPR PDFs: %d downloaded", downloaded)
    return downloaded


def load_nspr_products() -> list[dict]:
    """Load all scraped NSPR product details."""
    products = []
    for f in sorted(OUTPUT_DIR.glob("*.json")):
        if f.name.startswith("_") or f.name == "pdfs_index.json":
            continue
        products.append(json.loads(f.read_text(encoding="utf-8")))
    return products


def print_nspr_status() -> None:
    """Print NSPR scraping progress."""
    if not OUTPUT_DIR.exists():
        print("No NSPR data yet")
        return

    listings = list(OUTPUT_DIR.glob("*/_listing.json"))
    print(f"Category listings: {len(listings)}")
    for listing in listings:
        data = json.loads(listing.read_text(encoding="utf-8"))
        print(f"  {listing.parent.name}: {len(data.get('products', []))} products")

    details = [
        f for f in OUTPUT_DIR.glob("*.json")
        if not f.name.startswith("_") and f.name != "pdfs_index.json"
    ]
    print(f"Product details: {len(details)}")

    idx_path = OUTPUT_DIR / "pdfs_index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        dl = sum(1 for e in idx if e.get("downloaded"))
        print(f"PDFs indexed: {len(idx)} ({dl} downloaded)")
