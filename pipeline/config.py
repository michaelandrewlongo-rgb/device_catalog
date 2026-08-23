"""Central configuration for the device catalog pipeline.

Maps FDA product codes to catalog categories, normalizes manufacturer names,
and tracks which devices already exist in the catalog.
"""

import os
from pathlib import Path
import re

# Root of the device catalog (parent of pipeline/)
CATALOG_ROOT = Path(__file__).resolve().parent.parent

# Where intermediate data lives
DATA_DIR = Path(__file__).resolve().parent / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
ENRICHED_DIR = DATA_DIR / "enriched"
FDA_510K_DIR = DATA_DIR / "510k"

def _load_env_key(filename: str, key: str) -> str | None:
    """Load a key from a simple KEY=VALUE env file."""
    if os.environ.get(key):
        return os.environ[key].strip()
    path = Path.home() / "Desktop" / filename
    if not path.exists():
        return None
    value = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip()
    return value

DEEPSEEK_API_KEY: str | None = _load_env_key("master_env.txt", "DEEPSEEK_API_KEY")
OPENROUTER_API_KEY: str | None = _load_env_key("master_env.txt", "OPENROUTER_API_KEY")

# --------------------------------------------------------------------------
# FDA product code -> catalog category
# --------------------------------------------------------------------------
# Some codes are shared across subcategories and require disambiguation
# by inspecting the device_name field. See DISAMBIGUATION_RULES below.

PRODUCT_CODE_MAP: dict[str, str] = {
    # Neurovascular (priority)
    "POL": "thrombectomy",          # Stent retrievers
    "NRY": "aspiration",            # Aspiration thrombectomy catheters
    "HCG": "embolic-coil",          # Neurovascular embolization (coils + liquid; disambiguate)
    "QJP": "microcatheter",         # Neurovascular catheters (micro + distal access; disambiguate)
    "OUT": "flow-diverter",         # Class III, PMA
    "OPR": "intrasaccular",         # Class III, PMA
    "QCA": "intracranial-stent",    # Class III, PMA
    "MZQ": "balloon-catheter",      # Neurovascular balloon catheters
    # CSF / Neuro general
    "JXG": "csf-shunt",            # Hydrocephalus shunt valves
    # Dural
    "GXQ": "dural-substitute",     # Dural substitute/graft materials
    # Guidewires
    "MOF": "guidewire",            # Neurovascular guidewires (filter by neuro applicants)
    # Spine
    "MAX": "pedicle-screw",        # Pedicle screw spinal systems
    "NKB": "interbody-cage",       # Intervertebral body fusion devices
    "MQP": "cervical-plate",       # Anterior cervical plates
    "KWP": "corpectomy",           # Vertebral body replacement devices
    "OUR": "sacroiliac-fusion",    # Sacroiliac joint fusion devices
}

# Product codes that require PMA lookup instead of 510(k)
PMA_PRODUCT_CODES = {"OUT", "OPR", "QCA"}

# --------------------------------------------------------------------------
# Disambiguation rules for shared product codes
# --------------------------------------------------------------------------
# Each rule is: (product_code, keyword_patterns, override_category)
# First match wins. If no rule matches, the default from PRODUCT_CODE_MAP is used.

DISAMBIGUATION_RULES: list[tuple[str, list[str], str]] = [
    # NRY: stent retrievers filed under aspiration code -> thrombectomy
    ("NRY", ["solitaire", "embotrap", "trevo", "preset", "eric retrieval",
             "tigertriever", "revascularization", "retriever", "stent retriever",
             "mechanical thrombectomy", "mindframe capture"],
     "thrombectomy"),
    # NRY: devices that are truly distal access / intermediate catheters
    ("NRY", ["sofia", "intermediate catheter", "cereglide"],
     "distal-access"),
    # HCG: liquid embolics vs coils
    ("HCG", ["onyx", "liquid embolic", "phil", "squid", "nbca", "trufill", "n-bca",
             "embolic agent", "embolic system liquid"], "liquid-embolic"),
    # QJP: distal access catheters vs microcatheters
    ("QJP", ["sofia", "ace ", "ace6", "jet ", "jet7", "catalyst", "react",
             "aspiration", "distal access", "intermediate", "reperfusion"],
     "distal-access"),
    ("QJP", ["balloon", "scepter", "hyperglide", "hyperform", "transform",
             "ascent", "eclipse"], "balloon-catheter"),
]


def disambiguate_category(product_code: str, device_name: str) -> str:
    """Resolve the catalog category for a device, applying disambiguation rules."""
    name_lower = device_name.lower()
    for code, keywords, override_cat in DISAMBIGUATION_RULES:
        if code == product_code:
            if any(kw in name_lower for kw in keywords):
                return override_cat
    return PRODUCT_CODE_MAP.get(product_code, "unknown")


# --------------------------------------------------------------------------
# Manufacturer name normalization
# --------------------------------------------------------------------------
# FDA applicant strings are inconsistent. This maps known variants to the
# canonical lowercase slug used in catalog filenames.

MANUFACTURER_ALIASES: dict[str, str] = {
    # Medtronic / ev3 family
    "medtronic": "medtronic",
    "medtronic, inc.": "medtronic",
    "medtronic neurovascular": "medtronic",
    "medtronic sofamor danek usa, inc.": "medtronic",
    "medtronic sofamor danek, inc.": "medtronic",
    "sofamor danek usa, inc.": "medtronic",
    "medtronic spine llc": "medtronic",
    "micro therapeutics inc. d/b/a ev3 neurovascular": "medtronic",
    "micro therapeutics, inc.": "medtronic",
    "ev3 neurovascular": "medtronic",
    "ev3 inc.": "medtronic",
    "ev3, inc.": "medtronic",
    "covidien lp": "medtronic",
    # Stryker
    "stryker neurovascular": "stryker",
    "stryker neurovscular": "stryker",  # Known FDA typo
    "stryker corporation": "stryker",
    "stryker spine": "stryker",
    "stryker spine, inc.": "stryker",
    "k2m, inc.": "stryker",
    "k2m": "stryker",
    "concentric medical, inc.": "stryker",
    "target therapeutics": "stryker",
    "boston scientific neurovascular": "stryker",  # Acquired by Stryker
    # MicroVention / Terumo
    "microvention, inc.": "microvention",
    "microvention": "microvention",
    "terumo neuro": "microvention",
    "terumo medical corporation": "microvention",
    # Penumbra
    "penumbra, inc.": "penumbra",
    "penumbra": "penumbra",
    # Cerenovus / J&J / Codman
    "cerenovus, inc.": "cerenovus",
    "cerenovus": "cerenovus",
    "codman & shurtleff, inc.": "cerenovus",
    "codman neuro": "cerenovus",
    "neuravi limited": "cerenovus",
    "neuravi ltd.": "cerenovus",
    "neuravi, ltd.": "cerenovus",
    "depuy synthes products, inc.": "depuy",
    "depuy synthes products, llc": "depuy",
    "depuy synthes spine, inc.": "depuy",
    "depuy spine, inc.": "depuy",
    "depuy spine": "depuy",
    "synthes usa, llc": "depuy",
    "synthes usa products, llc": "depuy",
    "synthes (usa)": "depuy",
    # Balt
    "balt usa, llc": "balt",
    "balt extrusion": "balt",
    "balt": "balt",
    # Phenox
    "phenox gmbh": "phenox",
    "phenox limited": "phenox",
    "phenox": "phenox",
    # Rapid Medical
    "rapid medical, ltd.": "rapid-medical",
    "rapid medical , ltd.": "rapid-medical",
    # Integra / Codman (non-neuro)
    "integra lifesciences": "integra",
    "integra lifesciences corporation": "integra",
    "integra": "integra",
    # Miethke / B. Braun
    "christoph miethke gmbh & co. kg": "miethke",
    "miethke": "miethke",
    # Globus Medical
    "globus medical, inc.": "globus",
    "globus medical": "globus",
    # NuVasive (merged with Globus Medical 2023)
    "nuvasive, inc.": "nuvasive",
    "nuvasive": "nuvasive",
    "nuvasive specialized orthopedics, inc.": "nuvasive",
    # Zimmer Biomet spine
    "zimmer biomet spine, inc.": "zimmer-biomet",
    "zimmer spine, inc.": "zimmer-biomet",
    "ldr spine usa, inc.": "zimmer-biomet",
    # Cordis
    "cordis neurovascular, inc.": "cordis",
    "cordis corporation": "cordis",
    "cordis": "cordis",
    # SI-BONE
    "si-bone, inc.": "si-bone",
    "si-bone inc.": "si-bone",
    # Orthofix / Musculoskeletal
    "orthofix, inc.": "orthofix",
    "orthofix medical, inc.": "orthofix",
    # Others
    "neo medical inc.": "neo-medical",
    "choicespine, lp": "choicespine",
    "neuropace, inc.": "neuropace",
    "boston scientific corporation": "boston-scientific",
    "boston scientific neuromodulation corp.": "boston-scientific",
}


def normalize_manufacturer(applicant: str) -> str:
    """Resolve an FDA applicant string to the canonical manufacturer slug."""
    key = applicant.strip().lower()
    if key in MANUFACTURER_ALIASES:
        return MANUFACTURER_ALIASES[key]
    # Fallback: try partial matching
    for alias, canonical in MANUFACTURER_ALIASES.items():
        if alias in key or key in alias:
            return canonical
    # Last resort: slugify the raw applicant name
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-")


# --------------------------------------------------------------------------
# Known PMA numbers for Class III neurovascular devices
# --------------------------------------------------------------------------
# (pma_number, category, manufacturer_canonical, device_family_name)

PMA_NUMBERS: list[tuple[str, str, str, str]] = [
    ("P100018", "flow-diverter", "medtronic", "Pipeline"),
    ("P170024", "flow-diverter", "stryker", "Surpass Streamline"),
    ("P180027", "flow-diverter", "microvention", "FRED"),
    ("P170013", "intracranial-stent", "microvention", "LVIS"),
    ("P170032", "intrasaccular", "microvention", "WEB"),
    ("P040034", "dural-sealant", "integra", "DuraSeal"),
]

# --------------------------------------------------------------------------
# Known neuro applicants (for filtering guidewires from cardio-panel records)
# --------------------------------------------------------------------------

NEURO_APPLICANTS: set[str] = {
    "stryker neurovascular",
    "stryker neurovscular",
    "microvention, inc.",
    "penumbra, inc.",
    "medtronic",
    "ev3 neurovascular",
    "micro therapeutics inc. d/b/a ev3 neurovascular",
    "cerenovus, inc.",
    "codman & shurtleff, inc.",
    "balt usa, llc",
    "boston scientific neurovascular",
    "target therapeutics",
    "concentric medical, inc.",
    "rapid medical, ltd.",
    "rapid medical , ltd.",
    "phenox gmbh",
    "phenox limited",
    "terumo medical corporation",
    "asahi intecc co., ltd.",
}


def is_neuro_applicant(applicant: str) -> bool:
    """Check if an FDA applicant is a known neurovascular manufacturer."""
    return applicant.strip().lower() in NEURO_APPLICANTS


# --------------------------------------------------------------------------
# Existing catalog inventory (auto-populated)
# --------------------------------------------------------------------------

def scan_existing_devices() -> set[str]:
    """Scan catalog root for existing knowledge.md files, return filename stems.

    Returns stems like 'thrombectomy--stryker--trevo-nxt'.
    """
    stems = set()
    for f in CATALOG_ROOT.glob("*--knowledge.md"):
        stem = f.name.replace("--knowledge.md", "")
        stems.add(stem)
    return stems


EXISTING_DEVICES: set[str] = scan_existing_devices()
