# pipeline/build_site.py
from pathlib import Path
import json


def parse_filename(filename: str) -> dict | None:
    """Parse device metadata from a knowledge filename.

    Input:  "flow-diverter--medtronic--pipeline-flex-shield--knowledge.md"
    Output: {"id": "flow-diverter--medtronic--pipeline-flex-shield",
             "category": "flow-diverter", "manufacturer": "medtronic",
             "slug": "pipeline-flex-shield"}
    Returns None if the filename is not a knowledge file or has too few parts.
    """
    if not filename.endswith("--knowledge.md"):
        return None
    stem = filename[: -len("--knowledge.md")]
    parts = stem.split("--")
    if len(parts) < 3:
        return None
    category = parts[0]
    manufacturer = parts[1]
    slug = "--".join(parts[2:])
    return {
        "id": stem,
        "category": category,
        "manufacturer": manufacturer,
        "slug": slug,
    }
