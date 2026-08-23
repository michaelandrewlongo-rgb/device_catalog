"""Device synonym registry built from curated knowledge files."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import CATALOG_ROOT
from .models import DeviceIdentity
from .storage import REGISTRY_DIR, write_json


def _title_from_slug(slug: str) -> str:
    return " ".join(part.upper() if part in {"csf", "mri"} else part.capitalize() for part in slug.split("-"))


def parse_knowledge_filename(path: Path) -> tuple[str, str, str] | None:
    if not path.name.endswith("--knowledge.md"):
        return None
    stem = path.name.removesuffix("--knowledge.md")
    parts = stem.split("--")
    if len(parts) < 3:
        return None
    return parts[0], parts[1], "--".join(parts[2:])


def _extract_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _extract_aliases(text: str) -> list[str]:
    match = re.search(
        r"^##\s+Also Known As\s*$([\s\S]*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        return []
    block = match.group(1).strip()
    aliases: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip().removeprefix("-").strip()
        if not line or line.startswith("**"):
            continue
        aliases.extend(part.strip() for part in line.split(",") if part.strip())
    return aliases


def identity_from_knowledge(
    category: str,
    manufacturer: str,
    product_slug: str,
    text: str,
) -> DeviceIdentity:
    display_name = _extract_h1(text) or _title_from_slug(product_slug)
    aliases = _extract_aliases(text)
    return DeviceIdentity(
        canonical_id=f"{category}--{manufacturer}--{product_slug}",
        category=category,
        manufacturer=manufacturer,
        display_name=display_name,
        synonyms=aliases,
    )


def build_registry(catalog_root: Path = CATALOG_ROOT, category: str | None = None) -> list[DeviceIdentity]:
    identities: list[DeviceIdentity] = []
    for path in sorted(catalog_root.glob("*--knowledge.md")):
        parsed = parse_knowledge_filename(path)
        if not parsed:
            continue
        device_category, manufacturer, product_slug = parsed
        if category and device_category != category:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        identities.append(identity_from_knowledge(device_category, manufacturer, product_slug, text))
    return identities


def write_registry(category: str | None = None, catalog_root: Path = CATALOG_ROOT) -> Path:
    identities = build_registry(catalog_root=catalog_root, category=category)
    suffix = category or "all"
    return write_json(REGISTRY_DIR / f"{suffix}.json", identities)


def detect_potential_duplicates(identities: list[DeviceIdentity]) -> list[dict]:
    """Flag pairs that may represent the same device family or product line.

    Two identities are flagged if one canonical_id is a prefix of the other
    (same category + manufacturer, product slug overlaps), or if they share a
    display name word overlap above a threshold. Returned list is advisory only.
    """
    flagged: list[dict] = []
    for i, a in enumerate(identities):
        for b in identities[i + 1 :]:
            if a.category != b.category or a.manufacturer != b.manufacturer:
                continue
            # Slug prefix overlap: one product slug starts with the other.
            # Require at least 2 dash-separated segments (≥1 dash) in the shorter slug
            # to avoid spurious matches from single-word stubs.
            a_slug = a.canonical_id.split("--", 2)[-1]
            b_slug = b.canonical_id.split("--", 2)[-1]
            shorter = a_slug if len(a_slug) <= len(b_slug) else b_slug
            if (
                a_slug and b_slug
                and "-" in shorter  # at least two slug segments
                and (a_slug.startswith(b_slug) or b_slug.startswith(a_slug))
            ):
                flagged.append({"a": a.canonical_id, "b": b.canonical_id, "reason": "slug_prefix"})
                continue
            # Display name word overlap: ≥3 words in common
            a_words = set(a.display_name.lower().split())
            b_words = set(b.display_name.lower().split())
            shared = a_words & b_words - {"the", "a", "an", "and", "or", "of", "for"}
            if len(shared) >= 3:
                flagged.append({
                    "a": a.canonical_id,
                    "b": b.canonical_id,
                    "reason": "name_overlap",
                    "shared_words": sorted(shared),
                })
    return flagged


def match_device_by_term(term: str, identities: list[DeviceIdentity]) -> DeviceIdentity | None:
    needle = term.lower()
    for identity in identities:
        for candidate in identity.search_terms():
            if candidate.lower() == needle:
                return identity
    for identity in identities:
        for candidate in identity.search_terms():
            lowered = candidate.lower()
            if lowered and (lowered in needle or needle in lowered):
                return identity
    return None
