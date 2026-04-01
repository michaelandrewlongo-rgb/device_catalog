"""Tier 2: Extract structured fields from brochures/technique guides.

Uses pdf_utils (pdfplumber or Marker) for PDF-to-text, then DeepSeek
for structured field extraction.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from ..config import CATALOG_ROOT, EXTRACTED_DIR
from .deepseek import deepseek_extract
from .pdf_utils import pdf_to_markdown, pdf_to_text

logger = logging.getLogger(__name__)

OUTPUT_DIR = EXTRACTED_DIR / "documents"

EXTRACTION_PROMPT = """You are extracting structured medical device data from a manufacturer document.

Extract ONLY what is explicitly stated. Do not infer or add information.
Return null for any field not found in the document.
For sizing_specs, preserve any tables as markdown.

Fields:
- what_it_is: Device description, mechanism, materials
- sizing_specs: Dimensions, sizes, configurations, materials table
- indications: Approved/intended clinical uses
- contraindications: Conditions where device should not be used
- compatible_with: Compatible devices, instruments, accessories
- use_notes: Clinical or procedural details, deployment steps
- also_known_as: Alternate names, abbreviations

Document type: {doc_type}
Device: {device_name} by {manufacturer}

Content:
{content}

Respond in JSON matching the field names above."""

MAX_CONTENT_CHARS = 60000  # ~15K tokens

# NSPR detail-page index for device name / manufacturer lookup
_nspr_index: dict[str, dict] | None = None


def _load_nspr_index() -> dict[str, dict]:
    """Load NSPR detail-page JSONs keyed by PDF filename stem."""
    global _nspr_index
    if _nspr_index is not None:
        return _nspr_index

    _nspr_index = {}
    nspr_dir = EXTRACTED_DIR / "nspr"
    pdfs_index_path = nspr_dir / "pdfs_index.json"

    # Try the pdfs_index.json first (maps slug -> pdf filenames)
    if pdfs_index_path.exists():
        try:
            index = json.loads(pdfs_index_path.read_text(encoding="utf-8"))
            # index maps slug -> list of pdf URLs; we need reverse: pdf stem -> slug
            for slug, pdf_urls in index.items():
                for url in (pdf_urls if isinstance(pdf_urls, list) else [pdf_urls]):
                    pdf_stem = Path(url.split("/")[-1]).stem if "/" in str(url) else str(url)
                    _nspr_index[pdf_stem] = {"slug": slug}
        except Exception:
            pass

    # Enrich with detail-page data (device_name, manufacturer)
    for jf in nspr_dir.glob("*.json"):
        if jf.name.startswith("_") or jf.name == "pdfs_index.json":
            continue
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            slug = jf.stem
            # Match PDFs to this slug via the index
            for stem, info in _nspr_index.items():
                if info.get("slug") == slug:
                    info["device_name"] = data.get("device_name", "")
                    info["manufacturer"] = data.get("manufacturer", "")
        except Exception:
            pass

    return _nspr_index


def extract_nspr_document(pdf_path: Path) -> dict | None:
    """Extract structured fields from an NSPR technique guide PDF.

    Uses pdfplumber (not Marker LLM) to avoid double DeepSeek calls,
    then sends to DeepSeek for structured field extraction.
    """
    # Look up device name / manufacturer from NSPR detail pages
    index = _load_nspr_index()
    stem = pdf_path.stem
    meta = index.get(stem, {})
    device_name = meta.get("device_name", stem.replace("-", " ").title())
    manufacturer = meta.get("manufacturer", "unknown")

    # Use pdfplumber directly -- reliable for text-based technique guides
    # and avoids Marker LLM timeout issues on large PDFs
    text = pdf_to_text(pdf_path)
    if not text or len(text.strip()) < 100:
        # Fall back to Marker without LLM for scanned pages
        text = pdf_to_markdown(pdf_path, use_llm=False)
    if not text:
        logger.warning("  No text extracted from NSPR PDF: %s", pdf_path.name)
        return None

    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS]

    prompt = EXTRACTION_PROMPT.format(
        doc_type="technique_guide",
        device_name=device_name,
        manufacturer=manufacturer,
        content=text,
    )

    fields = deepseek_extract(prompt)
    if not fields:
        return None

    return {
        "source_pdf": pdf_path.name,
        "source_path": str(pdf_path),
        "device_name": device_name,
        "manufacturer": manufacturer,
        "doc_type": "technique_guide",
        "extraction_method": "pdfplumber_deepseek",
        "extraction_source": "nspr_pdf",
        "fields": fields,
        "confidence": {k: 0.7 for k, v in fields.items() if v is not None},
    }


def extract_document(
    pdf_path: Path,
    device_name: str,
    manufacturer: str,
    doc_type: str = "brochure",
) -> dict | None:
    """Extract structured fields from a single manufacturer PDF."""
    # Use pdfplumber first (fast, reliable for text-based PDFs).
    # Marker LLM mode is disabled -- it calls DeepSeek internally with no
    # timeout, causing hangs on large technique guides. DeepSeek extraction
    # happens in the separate deepseek_extract() call below.
    text = pdf_to_text(pdf_path)
    if not text:
        text = pdf_to_markdown(pdf_path, use_llm=False)
    if not text:
        return None

    # Truncate to token budget
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS]

    prompt = EXTRACTION_PROMPT.format(
        doc_type=doc_type,
        device_name=device_name,
        manufacturer=manufacturer,
        content=text,
    )

    fields = deepseek_extract(prompt)
    if not fields:
        return None

    return {
        "source_pdf": pdf_path.name,
        "device_name": device_name,
        "manufacturer": manufacturer,
        "doc_type": doc_type,
        "extraction_method": "pdf_deepseek",
        "fields": fields,
        "confidence": {k: 0.7 for k, v in fields.items() if v is not None},
    }


def extract_all_documents() -> list[dict]:
    """Extract from catalog-root PDFs and NSPR-downloaded PDFs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    # Source 1: Catalog root PDFs (paired with knowledge files)
    for pdf in sorted(CATALOG_ROOT.glob("*--*.pdf")):
        parts = pdf.stem.split("--")
        if len(parts) < 3:
            continue

        out_file = OUTPUT_DIR / f"{pdf.stem}.json"
        if out_file.exists():
            logger.info("  Skip (exists): %s", pdf.name)
            continue

        manufacturer = parts[1]
        product = parts[2]
        doc_type = parts[3] if len(parts) > 3 else "unknown"

        logger.info("  Extracting: %s", pdf.name)
        try:
            result = extract_document(pdf, product, manufacturer, doc_type)
        except Exception as exc:
            logger.error("  Extraction crashed on %s: %s", pdf.name, exc)
            result = None
        if result:
            out_file.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            results.append(result)
        time.sleep(1)  # Rate limit for DeepSeek

    # Source 2: NSPR-downloaded PDFs
    nspr_pdfs = EXTRACTED_DIR / "nspr" / "pdfs"
    if nspr_pdfs.exists():
        nspr_list = sorted(nspr_pdfs.glob("*.pdf"))
        nspr_total = len(nspr_list)
        for idx, pdf in enumerate(nspr_list, 1):
            out_file = OUTPUT_DIR / f"nspr--{pdf.stem}.json"
            if out_file.exists():
                continue

            logger.info("  [%d/%d] Extracting NSPR: %s", idx, nspr_total, pdf.name)
            try:
                result = extract_nspr_document(pdf)
            except Exception as exc:
                logger.error("  NSPR extraction crashed on %s: %s", pdf.name, exc)
                result = None
            if result:
                out_file.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                results.append(result)
            time.sleep(1)

    logger.info("Document extraction: %d documents processed", len(results))
    return results


def extract_fda_documents(curated_only: bool = True) -> list[dict]:
    """Extract structured fields from FDA 510(k) PDFs via Marker + DeepSeek.

    Args:
        curated_only: If True, only process PDFs matching curated knowledge files.
    """
    from ..config import DATA_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_dir = DATA_DIR / "pdfs"
    if not pdf_dir.exists():
        logger.warning("No FDA PDF directory: %s", pdf_dir)
        return []

    # Build set of curated stems for filtering
    curated_stems: set[str] = set()
    if curated_only:
        for kf in CATALOG_ROOT.glob("*--knowledge.md"):
            curated_stems.add(kf.name.replace("--knowledge.md", ""))

    results = []
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        parts = pdf.stem.split("--")
        if len(parts) < 3:
            continue

        # Stem is everything before --510k (the doc_type suffix)
        stem = "--".join(parts[:-1]) if parts[-1] == "510k" else pdf.stem

        if curated_only and stem not in curated_stems:
            continue

        out_file = OUTPUT_DIR / f"{pdf.stem}.json"
        if out_file.exists():
            logger.info("  Skip (exists): %s", pdf.name)
            continue

        manufacturer = parts[1]
        product = parts[2] if len(parts) > 2 else ""

        logger.info("  Extracting FDA: %s", pdf.name)
        result = extract_document(pdf, product, manufacturer, "510k")
        if result:
            out_file.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            results.append(result)
        time.sleep(1)

    logger.info("FDA document extraction: %d documents processed", len(results))
    return results
