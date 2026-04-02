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


def parse_markdown(content: str) -> tuple[str, dict, list[str]]:
    """Parse a knowledge markdown file into (name, sections, aliases).

    name     -- text of the H1 heading (empty string if absent)
    sections -- dict of H2 heading text -> section body (raw markdown, stripped)
    aliases  -- list extracted from the "Also Known As" section
    """
    lines = content.split("\n")
    name: str = ""
    sections: dict[str, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            name = line[2:].strip()
        elif line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    aliases = _parse_aliases(sections.get("Also Known As", ""))
    return name, sections, aliases


def _parse_aliases(text: str) -> list[str]:
    """Extract alias strings from an Also Known As section body."""
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("-"):
        return [
            line.lstrip("-").strip()
            for line in stripped.split("\n")
            if line.strip().startswith("-")
        ]
    flat = stripped.replace("\n", ", ")
    return [a.strip() for a in flat.split(",") if a.strip()]
