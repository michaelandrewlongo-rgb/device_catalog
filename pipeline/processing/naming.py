"""Filename convention enforcement for the device catalog."""

from slugify import slugify

from ..config import EXISTING_DEVICES


def make_filename_stem(category: str, manufacturer: str, product_name: str) -> str:
    """Generate a catalog filename stem following the naming convention.

    Pattern: {category}--{manufacturer}--{product-slug}

    Args:
        category: Device category (e.g., "thrombectomy").
        manufacturer: Canonical manufacturer slug (e.g., "penumbra").
        product_name: Human-readable product name (e.g., "JET 7 Xtra Flex").

    Returns:
        Filename stem like "thrombectomy--penumbra--jet-7-xtra-flex".
    """
    product_slug = slugify(product_name, separator="-", lowercase=True)

    # Trim overly long slugs
    parts = product_slug.split("-")
    if len(parts) > 6:
        product_slug = "-".join(parts[:6])

    return f"{category}--{manufacturer}--{product_slug}"


def make_knowledge_filename(stem: str) -> str:
    """Append the knowledge.md suffix to a filename stem."""
    return f"{stem}--knowledge.md"


def check_collision(stem: str, current_run_stems: set[str] | None = None) -> bool:
    """Check if a filename stem collides with existing catalog or current run.

    Returns True if there is a collision.
    """
    if stem in EXISTING_DEVICES:
        return True
    if current_run_stems and stem in current_run_stems:
        return True
    return False


def deduplicate_stem(stem: str, current_run_stems: set[str]) -> str:
    """Add a numeric suffix to avoid collisions.

    Returns the original stem if no collision, or stem-2, stem-3, etc.
    """
    if not check_collision(stem, current_run_stems):
        return stem

    parts = stem.rsplit("--", 1)
    if len(parts) < 2:
        return stem

    base = stem
    for i in range(2, 100):
        candidate = f"{base}-{i}"
        if not check_collision(candidate, current_run_stems):
            return candidate

    return stem  # Give up after 99 attempts
