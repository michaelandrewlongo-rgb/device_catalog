"""Generate scaffold knowledge.md files from merged device records."""

import json
from pathlib import Path
from jinja2 import Environment

from .merger import MergedDeviceRecord
from .naming import make_knowledge_filename, deduplicate_stem
from ..config import DATA_DIR, ENRICHED_DIR

DRAFTS_DIR = DATA_DIR / "drafts"

# Jinja2 template matching the existing knowledge file format.
# Sections with data are populated; missing sections get [NEEDS CONTENT] markers.

KNOWLEDGE_TEMPLATE = """\
# {{ device_name }}

**Manufacturer:** {{ manufacturer_display }}
**Category:** {{ category_display }}
{%- if clearance_info %}
{{ clearance_info }}
{%- endif %}

## What It Is

{{ what_it_is }}

## Sizing/Specs

{{ sizing_specs }}

## Indications

{{ indications }}
{% if contraindications %}

## Contraindications

{{ contraindications }}
{% endif %}
{% if compatible_with %}

## Compatible With

{{ compatible_with }}
{% endif %}
{% if use_notes %}

## Use Notes

{{ use_notes }}
{% endif %}
{% if deployment_steps %}

## Deployment Step-by-Step

{{ deployment_steps }}
{% endif %}

## Key Differences vs Competitors

{{ key_differences }}

## Also Known As

{{ also_known_as }}
"""

# Display-friendly manufacturer names
MANUFACTURER_DISPLAY: dict[str, str] = {
    "medtronic": "Medtronic",
    "stryker": "Stryker",
    "microvention": "MicroVention (Terumo)",
    "penumbra": "Penumbra",
    "cerenovus": "Cerenovus (J&J)",
    "balt": "Balt",
    "phenox": "Phenox",
    "integra": "Integra LifeSciences",
    "depuy": "DePuy Synthes",
    "globus": "Globus Medical",
    "miethke": "Miethke (B. Braun)",
    "cordis": "Cordis",
    "neo-medical": "Neo Medical",
    "choicespine": "ChoiceSpine",
    "rapid-medical": "Rapid Medical",
    "boston-scientific": "Boston Scientific",
    "neuropace": "NeuroPace",
}

# Display-friendly category names
CATEGORY_DISPLAY: dict[str, str] = {
    "thrombectomy": "Thrombectomy device",
    "aspiration": "Aspiration catheter",
    "embolic-coil": "Embolic coil",
    "microcatheter": "Microcatheter",
    "distal-access": "Distal access catheter",
    "flow-diverter": "Flow diverter",
    "intrasaccular": "Intrasaccular device",
    "intracranial-stent": "Intracranial stent",
    "balloon-catheter": "Balloon catheter",
    "liquid-embolic": "Liquid embolic",
    "csf-shunt": "CSF shunt valve",
    "dural-sealant": "Dural sealant",
    "dural-substitute": "Dural substitute",
    "guidewire": "Guidewire",
    "pedicle-screw": "Pedicle screw system",
    "cervical-cage": "Cervical cage",
    "cervical-plate": "Cervical plate",
    "interbody-cage": "Interbody cage",
    "corpectomy": "Corpectomy mesh",
    "navigation": "Navigation system",
}

PLACEHOLDER = "[NEEDS CONTENT - {hint}]"


def _placeholder(hint: str) -> str:
    return f"[NEEDS CONTENT - {hint}]"


def render_knowledge_md(record: MergedDeviceRecord) -> str:
    """Render a knowledge.md file from a merged device record."""
    env = Environment(autoescape=False, keep_trailing_newline=True)
    template = env.from_string(KNOWLEDGE_TEMPLATE)

    # Build clearance info line
    clearance_info = ""
    if record.clearance_number:
        ctype = "510(k)" if record.clearance_type == "510k" else "PMA"
        clearance_info = (
            f"{ctype} {record.clearance_number} | "
            f"Class {record.device_class} | "
            f"{record.clearance_date[:10] if record.clearance_date else 'date unknown'}"
        )

    # Also known as
    aka = ", ".join(record.also_known_as) if record.also_known_as else _placeholder(
        "alternate names, abbreviations, legacy product names"
    )

    rendered = template.render(
        device_name=record.device_name,
        manufacturer_display=MANUFACTURER_DISPLAY.get(
            record.manufacturer, record.manufacturer.title()
        ),
        category_display=CATEGORY_DISPLAY.get(
            record.catalog_category, record.catalog_category.replace("-", " ").title()
        ),
        clearance_info=clearance_info,
        what_it_is=record.what_it_is or _placeholder(
            "describe device mechanism, materials, key design features"
        ),
        sizing_specs=record.sizing_specs or _placeholder(
            "dimensions, available sizes/configurations, materials table"
        ),
        indications=record.indications or _placeholder(
            "FDA-approved clinical uses, patient population criteria"
        ),
        contraindications=record.contraindications,
        compatible_with=record.compatible_with,
        use_notes=record.use_notes,
        deployment_steps=record.deployment_steps,
        key_differences=_placeholder(
            "head-to-head comparison with competing devices in same category"
        ),
        also_known_as=aka,
    )

    # Clean up excessive blank lines
    while "\n\n\n" in rendered:
        rendered = rendered.replace("\n\n\n", "\n\n")

    return rendered.strip() + "\n"


def generate_drafts(
    records: list[MergedDeviceRecord],
    skip_fda_only: bool = True,
) -> list[tuple[str, Path]]:
    """Generate scaffold knowledge.md files in the drafts directory.

    Returns:
        List of (filename_stem, file_path) tuples for generated files.
    """
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    current_run_stems: set[str] = set()
    generated: list[tuple[str, Path]] = []

    # Load enriched records if available (Tier 3 output)
    enriched_map: dict[str, dict] = {}
    if ENRICHED_DIR.exists():
        for f in ENRICHED_DIR.glob("*.json"):
            try:
                enriched_map[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

    for record in records:
        if not record.catalog_category or record.catalog_category == "unknown":
            continue

        if skip_fda_only and record.data_sources == ["fda"]:
            continue

        stem = deduplicate_stem(record.filename_stem, current_run_stems)
        current_run_stems.add(stem)

        # Overlay enriched data if available
        if stem in enriched_map:
            enriched = enriched_map[stem]
            overlay_fields = [
                "what_it_is", "sizing_specs", "indications",
                "contraindications", "compatible_with", "use_notes",
            ]
            replacements = {}
            for field in overlay_fields:
                val = enriched.get(field)
                if val and not getattr(record, field, None):
                    replacements[field] = val
            # Also handle also_known_as (list field)
            aka = enriched.get("also_known_as")
            if aka and not record.also_known_as:
                replacements["also_known_as"] = aka if isinstance(aka, list) else [aka]
            for field, val in replacements.items():
                setattr(record, field, val)

        filename = make_knowledge_filename(stem)
        content = render_knowledge_md(record)

        filepath = DRAFTS_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        generated.append((stem, filepath))

    return generated
