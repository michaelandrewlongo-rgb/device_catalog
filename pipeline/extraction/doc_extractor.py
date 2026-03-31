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


def extract_document(
    pdf_path: Path,
    device_name: str,
    manufacturer: str,
    doc_type: str = "brochure",
) -> dict | None:
    """Extract structured fields from a single manufacturer PDF."""
    # Try Marker first (better tables), fall back to pdfplumber
    text = pdf_to_markdown(pdf_path, use_llm=(doc_type in ("ifu", "technique")))
    if not text:
        text = pdf_to_text(pdf_path)
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
        result = extract_document(pdf, product, manufacturer, doc_type)
        if result:
            out_file.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            results.append(result)
        time.sleep(1)  # Rate limit for DeepSeek

    # Source 2: NSPR-downloaded PDFs
    nspr_pdfs = EXTRACTED_DIR / "nspr" / "pdfs"
    if nspr_pdfs.exists():
        for pdf in sorted(nspr_pdfs.glob("*.pdf")):
            out_file = OUTPUT_DIR / f"nspr--{pdf.stem}.json"
            if out_file.exists():
                continue

            logger.info("  Extracting NSPR: %s", pdf.name)
            result = extract_document(pdf, pdf.stem, "nspr")
            if result:
                out_file.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                results.append(result)
            time.sleep(1)

    logger.info("Document extraction: %d documents processed", len(results))
    return results
