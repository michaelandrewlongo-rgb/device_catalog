# pipeline/build_site.py
from pathlib import Path
import json
import sys


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
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
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
            if line.strip().startswith("-") and line.lstrip("-").strip()
        ]
    # Comma-separated or grouped format -- strip markdown and group headers
    flat = stripped.replace("\r\n", "\n").replace("\n", ", ")
    raw_items = [a.strip() for a in flat.split(",")]
    items = []
    for item in raw_items:
        # Strip bold markers
        clean = item.strip("*").strip()
        # Skip empty items, group headers (end with ":"), and residual markdown
        if not clean or clean.endswith(":") or clean.startswith("*") or clean.startswith("#"):
            continue
        # Dash-prefixed entries are real aliases (from sub-lists in grouped format)
        if clean.startswith("-"):
            clean = clean.lstrip("-").strip()
        if clean:
            items.append(clean)
    return items


_SPECIAL_WORDS: dict[str, str] = {
    "csf": "CSF",
    "si":  "SI",
    "vrd": "VRD",
    "tlif": "TLIF",
    "llif": "LLIF",
    "alif": "ALIF",
    "acdf": "ACDF",
    "nbca": "NBCA",
    "llc":  "LLC",
    "inc":  "Inc",
    "ltd":  "Ltd",
    "co":   "Co",
}


def slug_to_title(slug: str) -> str:
    """Convert 'flow-diverter' -> 'Flow Diverter', 'csf-shunt' -> 'CSF Shunt'."""
    return " ".join(
        _SPECIAL_WORDS.get(w, w.title()) for w in slug.split("-")
    )


DOMAIN_MAP: dict[str, str] = {
    "flow-diverter":          "neurovascular",
    "microcatheter":          "neurovascular",
    "aspiration":             "neurovascular",
    "aspiration-catheter":    "neurovascular",
    "distal-access":          "neurovascular",
    "embolic-coil":           "neurovascular",
    "intracranial-stent":     "neurovascular",
    "stent-retriever":        "neurovascular",
    "thrombectomy":           "neurovascular",
    "intrasaccular":          "neurovascular",
    "liquid-embolic":         "neurovascular",
    "balloon-catheter":       "neurovascular",
    "balloon-guide-catheter": "neurovascular",
    "guidewire":              "neurovascular",
    "guiding-catheter":       "neurovascular",
    "delivery-catheter":      "neurovascular",
    "pedicle-screw":          "spine",
    "interbody-cage":         "spine",
    "cervical-cage":          "spine",
    "cervical-plate":         "spine",
    "corpectomy":             "spine",
    "sacroiliac-fusion":      "spine",
    "cervical-disc":          "spine",
    "csf-shunt":              "cranial",
    "dural-sealant":          "cranial",
    "dural-substitute":       "cranial",
    "navigation":             "cranial",
}


def map_domain(category: str) -> str:
    """Return the top-level clinical domain for a device category slug."""
    return DOMAIN_MAP.get(category, "other")


def load_devices(catalog_root: Path) -> list[dict]:
    """Load all curated knowledge files from catalog_root.

    Reads every file matching *--knowledge.md directly in catalog_root
    (non-recursive -- drafts in subdirectories are excluded).
    Returns a list of device dicts ready for JSON serialization.
    """
    devices: list[dict] = []
    for path in sorted(catalog_root.glob("*--knowledge.md")):
        meta = parse_filename(path.name)
        if not meta:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"WARNING: skipped {path.name}: {e}", file=sys.stderr)
            continue
        name, sections, aliases = parse_markdown(content)
        if not name:
            name = slug_to_title(meta["slug"])
        devices.append({
            **meta,
            "name": name,
            "domain": map_domain(meta["category"]),
            "manufacturer_display": slug_to_title(meta["manufacturer"]),
            "category_display": slug_to_title(meta["category"]),
            "aliases": aliases,
            "sections": sections,
            "image": find_device_image(meta["id"], catalog_root),
        })
    return devices


def find_device_image(device_id: str, catalog_root: Path) -> "str | None":
    """Return 'images/{device_id}.{ext}' if image exists in site/images/, else None.

    The returned path is relative to the site/ directory, suitable for HTML src.
    """
    images_dir = catalog_root / "site" / "images"
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if (images_dir / f"{device_id}{ext}").exists():
            return f"images/{device_id}{ext}"
    return None


def main() -> None:
    catalog_root = Path(__file__).parent.parent
    template_path = Path(__file__).parent / "site_template.html"
    output_dir = catalog_root / "site"
    output_path = output_dir / "index.html"

    print(f"Loading devices from {catalog_root} ...")
    devices = load_devices(catalog_root)
    print(f"  {len(devices)} curated devices loaded")

    template = template_path.read_text(encoding="utf-8")
    catalog_json = json.dumps(devices, ensure_ascii=False)
    assert "__CATALOG_DATA__" not in catalog_json, \
        "A knowledge file contains the literal string '__CATALOG_DATA__' — rename it before building."
    html = template.replace("__CATALOG_DATA__", catalog_json)

    output_dir.mkdir(exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"  Written to {output_path}")
    print("Done. Open site/index.html in your browser.")


if __name__ == "__main__":
    main()
