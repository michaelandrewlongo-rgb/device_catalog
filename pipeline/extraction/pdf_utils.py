"""Shared PDF utilities: text extraction and validation.

Uses pdfplumber for text-based PDFs (fast, no model download).
Marker available as optional upgrade for scanned/complex PDFs.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_pdf(path: Path) -> str | None:
    """Return None if valid PDF, or an error reason string."""
    if not path.exists():
        return f"Not found: {path}"
    if path.stat().st_size < 1024:
        return f"Too small ({path.stat().st_size} bytes): {path}"
    if path.stat().st_size > 100 * 1024 * 1024:
        return f"Too large ({path.stat().st_size} bytes): {path}"
    with open(path, "rb") as f:
        header = f.read(8)
    if header[:5] != b"%PDF-":
        if header[:5] in (b"<html", b"<!DOC", b"<HTML"):
            return f"HTML disguised as PDF: {path}"
        return f"Invalid header: {path}"
    return None


def pdf_to_text(path: Path) -> str | None:
    """Extract text from PDF using pdfplumber. Returns None on failure."""
    error = validate_pdf(path)
    if error:
        logger.warning(error)
        return None

    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed. Run: pip install pdfplumber")
        return None

    try:
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

                # Also extract tables as markdown
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        md_table = _table_to_markdown(table)
                        if md_table:
                            text_parts.append(md_table)

        text = "\n\n".join(text_parts)
        if len(text.strip()) < 50:
            logger.warning("Near-empty extraction (%d chars): %s", len(text), path)
            return None
        return text
    except Exception as exc:
        logger.error("pdfplumber failed on %s: %s", path, exc)
        return None


def pdf_to_markdown(path: Path, use_llm: bool = False) -> str | None:
    """Convert PDF to markdown. Uses Marker if available, falls back to pdfplumber.

    Args:
        path: Path to PDF file.
        use_llm: If True and Marker is available, use LLM backend for complex tables.
    """
    error = validate_pdf(path)
    if error:
        logger.warning(error)
        return None

    # Try Marker first (better table handling, OCR support)
    try:
        return _marker_convert(path, use_llm)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Marker failed on %s: %s, falling back to pdfplumber", path, exc)

    # Fallback to pdfplumber
    return pdf_to_text(path)


def _marker_convert(path: Path, use_llm: bool) -> str | None:
    """Convert PDF via Marker. Raises ImportError if not installed."""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    converter = _get_marker_converter(use_llm)
    rendered = converter(str(path))
    result = text_from_rendered(rendered)

    # Handle different return types (string or tuple)
    if isinstance(result, str):
        text = result
    elif isinstance(result, tuple):
        text = result[0] if result else ""
    elif hasattr(result, "text"):
        text = result.text
    elif hasattr(result, "markdown"):
        text = result.markdown
    else:
        text = str(result)

    if len(text.strip()) < 50:
        return None
    return text


# Lazy-loaded Marker converters
_converter_cache: dict[bool, object] = {}


def _get_marker_converter(use_llm: bool):
    """Get or create a cached Marker PdfConverter."""
    if use_llm not in _converter_cache:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict

        config: dict = {"output_format": "markdown", "use_llm": use_llm}

        if use_llm:
            from ..config import DEEPSEEK_API_KEY
            config["openai_api_key"] = DEEPSEEK_API_KEY or ""
            config["openai_base_url"] = "https://api.deepseek.com/v1"
            config["openai_model"] = "deepseek-chat"

        artifact_dict = create_model_dict()

        kwargs: dict = {"artifact_dict": artifact_dict, "config": config}
        if use_llm:
            kwargs["llm_service"] = "marker.services.openai.OpenAIService"

        _converter_cache[use_llm] = PdfConverter(**kwargs)

    return _converter_cache[use_llm]


def _table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table to markdown format."""
    if not table or not table[0]:
        return ""

    # Clean cells
    clean = []
    for row in table:
        clean.append([str(cell).strip() if cell else "" for cell in row])

    if len(clean) < 2:
        return ""

    # Header row
    header = "| " + " | ".join(clean[0]) + " |"
    separator = "| " + " | ".join("---" for _ in clean[0]) + " |"
    rows = [header, separator]
    for row in clean[1:]:
        # Pad row to match header length
        padded = row + [""] * (len(clean[0]) - len(row))
        rows.append("| " + " | ".join(padded[:len(clean[0])]) + " |")

    return "\n".join(rows)
