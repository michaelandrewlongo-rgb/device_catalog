"""Run Tier 2 extraction: NSPR PDFs first, then remaining catalog PDFs.

Usage: PYTHONUTF8=1 python run_nspr_extract.py
"""
import logging
import sys
import time
from pathlib import Path

# Set up logging before imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("nspr_extract.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from pipeline.extraction.doc_extractor import extract_all_documents

if __name__ == "__main__":
    logger.info("Starting Tier 2 extraction (NSPR + catalog PDFs)")
    start = time.time()
    results = extract_all_documents()
    elapsed = time.time() - start
    logger.info("Done: %d documents extracted in %.0f minutes", len(results), elapsed / 60)
