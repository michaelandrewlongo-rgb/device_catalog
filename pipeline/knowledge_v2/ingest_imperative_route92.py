"""Register the 2026-08 Imperative Care and Route 92 retrievals; extract Zoom claims.

One-time, verification-gated ingestion of the documents staged per
``sources/official/incoming/RETRIEVAL-MANIFEST.json`` (PDFs now in
``sources/official/current/``):

- registers every document as a source (per device, sha256-pinned, with its
  retrieval URL), and
- builds ``official_labeling`` claims from the Zoom System eIFU (LBL002069-02.D)
  Table 1 dimensions, Table 2 vessel sizing, and Table 3 compatibility.

Every claim value below was transcribed from the eIFU and is re-verified
against the text of its cited PDF page before anything is written; a single
missing quote aborts the whole run. Idempotent: existing source_ids/claim_ids
are left untouched.

Route 92 documents are registered as reopenable sources only; their claims
follow after the same page-level review.

    python -m pipeline.knowledge_v2.ingest_imperative_route92
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import CATALOG_ROOT
from .io import read_json, read_jsonl, write_json

DATA = Path(__file__).resolve().parent / "data"
REGISTRY = DATA / "source_registry.json"
CLAIMS = DATA / "reviewed_claims.v2.jsonl"
CURRENT = "sources/official/current"
CHECKED_AT = "2026-08-24"

ZOOM_IFU = f"{CURRENT}/aspiration--imperative-care--zoom-system--ifu.pdf"

REVIEW_NOTE = ("Transcribed from the retained Zoom System eIFU (LBL002069-02.D) and "
               "re-verified against the cited PDF page text at ingest time; the ingest "
               "aborts if any quoted value is absent from the page.")

# ---------------------------------------------------------------------------
# Sources: (source_id, device_id, title, source_type, jurisdiction, revision,
#           file (repo-relative), official_url, notes, identity_any)
# ---------------------------------------------------------------------------
SOURCES = [
    ("ifu:imperative-care:zoom-system:lbl002069-02d",
     "aspiration--imperative-care--zoom-aspiration-catheters",
     "Imperative Care Zoom System eIFU, LBL002069-02.D",
     "manufacturer_ifu", "US", "LBL002069-02.D (retrieved 2026-08-24)",
     ZOOM_IFU,
     "https://imperativecare.com/wp-content/uploads/2026/02/LBL002069-02.D-Zoom-System-eIFU.pdf",
     "System eIFU covering the Zoom (7X, 71, 55, 45, 4S, 35) aspiration catheters; "
     "the same document also covers the LDP catheters (separate source records per device).",
     ["Zoom System", "Zoom 71", "Zoom 55"]),
    ("ifu:imperative-care:zoom-system:lbl002069-02d:zoom-88-ldp",
     "distal-access--imperative-care--zoom-88-ldp",
     "Imperative Care Zoom System eIFU, LBL002069-02.D (Zoom 88 LDP tables)",
     "manufacturer_ifu", "US", "LBL002069-02.D (retrieved 2026-08-24)",
     ZOOM_IFU,
     "https://imperativecare.com/wp-content/uploads/2026/02/LBL002069-02.D-Zoom-System-eIFU.pdf",
     "Same retained eIFU PDF as the aspiration-catheter source; registered per device "
     "so claims join on device_id.",
     ["Zoom 88", "Large Distal Platform"]),
    ("ifu:imperative-care:zoom-system:lbl002069-02d:tracstar-ldp",
     "guide-catheter--imperative-care--tracstar-ldp",
     "Imperative Care Zoom System eIFU, LBL002069-02.D (TracStar LDP tables)",
     "manufacturer_ifu", "US", "LBL002069-02.D (retrieved 2026-08-24)",
     ZOOM_IFU,
     "https://imperativecare.com/wp-content/uploads/2026/02/LBL002069-02.D-Zoom-System-eIFU.pdf",
     "Same retained eIFU PDF as the aspiration-catheter source; registered per device.",
     ["TracStar"]),
    ("ifu:imperative-care:zoom-88:lbl002052-02d",
     "distal-access--imperative-care--zoom-88-ldp",
     "Zoom 88 and Zoom 88 Support Large Distal Platform IFU, LBL002052-02.D",
     "manufacturer_ifu", "US", "LBL002052-02.D (retrieved 2026-08-24)",
     f"{CURRENT}/distal-access--imperative-care--zoom-88--ifu.pdf",
     "https://imperativecare.com/wp-content/uploads/2025/08/LBL002052-02.D_Zoom-88-IFU_DIGITAL_v2.pdf",
     "Device-specific IFU; the Zoom System eIFU is the newer combined labeling.",
     ["Zoom 88"]),
    ("ifu:imperative-care:tracstar-ldp:lbl002056-02c",
     "guide-catheter--imperative-care--tracstar-ldp",
     "TracStar LDP Large Distal Platform (Gen 2) IFU, LBL002056-02.C",
     "manufacturer_ifu", "US", "LBL002056-02.C (retrieved 2026-08-24)",
     f"{CURRENT}/guide-catheter--imperative-care--tracstar-ldp--ifu.pdf",
     "https://imperativecare.com/wp-content/uploads/2025/08/LBL002056-02.C_TracStar-LDP-Gen-2-IFU_DIGITAL_v2-1.pdf",
     "Device-specific IFU; the Zoom System eIFU is the newer combined labeling.",
     ["TracStar"]),
    ("ifu:imperative-care:zoom-rdl:lbl002007-02h",
     "access-devices--imperative-care--zoom-rdl",
     "Zoom RDL Radial Access System IFU, LBL002007-02.H",
     "manufacturer_ifu", "US", "LBL002007-02.H (retrieved 2026-08-24)",
     f"{CURRENT}/access-devices--imperative-care--zoom-rdl--ifu.pdf",
     "https://imperativecare.com/wp-content/uploads/2025/08/LBL002007-02.H-Imperative-Care-Zoom-RDL-Radial-Access-System-IFU_DIGITAL_v3.pdf",
     "Radial access platform IFU.",
     ["Zoom RDL", "Radial Access"]),
    ("fda510k:K242672",
     "distal-access--imperative-care--zoom-88-ldp",
     "K242672 510(k) Summary - Imperative Care Zoom System (.088 aspiration, decided 2025-01-14)",
     "fda_510k_summary", "US", "K242672 (decided 2025-01-14)",
     f"{CURRENT}/aspiration--imperative-care--zoom-system--510k-K242672.pdf",
     "https://www.accessdata.fda.gov/cdrh_docs/pdf24/K242672.pdf",
     "Official clearance document; not manufacturer IFU/current labeling and cannot override either.",
     ["K242672"]),
    ("ifu:route-92-medical:hipoint-reperfusion-system:ifu-2418e",
     "aspiration--route-92-medical--hipoint-reperfusion-system",
     "HiPoint Reperfusion System IFU (HiPoint 70 and 88; includes Tenzing 8), IFU-2418 rev E",
     "manufacturer_ifu", "US", "IFU-2418 rev E (retrieved 2026-08-24)",
     f"{CURRENT}/aspiration--route-92-medical--hipoint-reperfusion-system--ifu.pdf",
     "https://www.route92medical.com/wp-content/uploads/2024/12/IFU-2418.E-IFU-HiPoint-Reperfusion-System.pdf",
     "Registered as a reopenable source; claims to follow page-level review.",
     ["HiPoint"]),
    ("ifu:route-92-medical:tenzing-7:ifu-0466p",
     "delivery-catheter--route-92-medical--tenzing-7",
     "Tenzing 7 Delivery Catheter IFU, IFU-0466 rev P",
     "manufacturer_ifu", "US", "IFU-0466 rev P (retrieved 2026-08-24)",
     f"{CURRENT}/delivery-catheter--route-92-medical--tenzing-7--ifu.pdf",
     "https://www.route92medical.com/wp-content/uploads/2024/12/IFU-0466.P-IFU-Tenzing-7-Delivery-Catheter.pdf",
     "Registered as a reopenable source; claims to follow page-level review.",
     ["Tenzing"]),
    ("ifu:route-92-medical:base-camp-sheath:ifu-0663j",
     "access-devices--route-92-medical--base-camp-sheath",
     "Base Camp Sheath System IFU (CE), IFU-0663 rev J",
     "manufacturer_ifu", "EU", "IFU-0663 rev J (retrieved 2026-08-24)",
     f"{CURRENT}/access-devices--route-92-medical--base-camp-sheath--ifu.pdf",
     "https://www.route92medical.com/wp-content/uploads/2025/08/IFU-0663.J-IFU-Base-Camp-Sheath-System-CE.pdf",
     "CE labeling; confirm US labeling before any US-availability claim.",
     ["Base Camp"]),
    ("ifu:route-92-medical:base-camp-sheath-2-0:ifu-3798b",
     "access-devices--route-92-medical--base-camp-sheath-2-0",
     "Base Camp Sheath System 2.0 IFU (EU), IFU-3798 rev B",
     "manufacturer_ifu", "EU", "IFU-3798 rev B (retrieved 2026-08-24)",
     f"{CURRENT}/access-devices--route-92-medical--base-camp-sheath-2-0--ifu.pdf",
     "https://www.route92medical.com/wp-content/uploads/2025/08/IFU-3798.B-Instructions-for-Use-Base-Camp-Sheath-System-2.0-EU.pdf",
     "EU labeling; confirm US labeling before any US-availability claim.",
     ["Base Camp"]),
    ("ifu:route-92-medical:freeclimb-reperfusion-system:ifu-2556e",
     "aspiration--route-92-medical--freeclimb-reperfusion-system",
     "FreeClimb Reperfusion System IFU (70 and 88 sizes, CE), IFU-2556 rev E",
     "manufacturer_ifu", "EU", "IFU-2556 rev E (retrieved 2026-08-24)",
     f"{CURRENT}/aspiration--route-92-medical--freeclimb-reperfusion-system--ifu.pdf",
     "https://www.route92medical.com/wp-content/uploads/2026/07/Instructions-for-Use-FreeClimb-Reperfusion-System-CE-IFU-2556.pdf",
     "CE labeling; confirm US labeling before any US-availability claim.",
     ["FreeClimb"]),
    ("fda510k:K243601",
     "aspiration--route-92-medical--hipoint-reperfusion-system",
     "K243601 510(k) Summary - Route 92 HiPoint Reperfusion System (direct .088 aspiration, decided 2025-05-19)",
     "fda_510k_summary", "US", "K243601 (decided 2025-05-19)",
     f"{CURRENT}/aspiration--route-92-medical--hipoint-reperfusion-system--510k-K243601.pdf",
     "https://www.accessdata.fda.gov/cdrh_docs/pdf24/K243601.pdf",
     "Official clearance document; not manufacturer IFU/current labeling and cannot override either.",
     ["K243601"]),
    ("fda510k:K233329",
     "aspiration--route-92-medical--freeclimb-54-reperfusion-system",
     "K233329 510(k) Summary - Route 92 Full Length 054 Reperfusion System (FreeClimb 54, decided 2024-04-23)",
     "fda_510k_summary", "US", "K233329 (decided 2024-04-23)",
     f"{CURRENT}/aspiration--route-92-medical--freeclimb-54-reperfusion-system--510k-K233329.pdf",
     "https://www.accessdata.fda.gov/cdrh_docs/pdf23/K233329.pdf",
     "Official clearance document; not manufacturer IFU/current labeling and cannot override either.",
     ["K233329"]),
]

# ---------------------------------------------------------------------------
# Zoom System eIFU Table 1 rows, as printed (pages 1-2)
# fields: catalog_number, product_name, distal ID, distal OD, prox ID, prox OD,
#         max OD, working length, coating length, pdf_page
# ---------------------------------------------------------------------------
TABLE1 = [
    ("ICTC088110", "Zoom 88 LDP, 110 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "110 cm", "18 cm", 1),
    ("ICTC088100S", "Zoom 88 LDP Support, 100 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "100 cm", "14 cm", 1),
    ("ICAC088105", "TracStar LDP, 105 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "105 cm", "14 cm", 1),
    ("ICAC088095", "TracStar LDP, 95 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "95 cm", "14 cm", 1),
    ("ICAC088090", "TracStar LDP, 90 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "90 cm", "14 cm", 1),
    ("ICAC088080", "TracStar LDP, 80 cm", "0.088", "0.107", "0.088", "0.110", "0.110", "80 cm", "14 cm", 1),
    ("ICRC07X137", "Zoom 7X, 137cm", "0.071", "0.083", "0.071", "0.083", "0.086", "137 cm", "35 cm", 1),
    ("ICRC071137", "Zoom 71, 137 cm", "0.071", "0.083", "0.071", "0.083", "0.086", "137 cm", "35 cm", 1),
    ("ICRC055137", "Zoom 55, 137 cm", "0.055", "0.069", "0.067", "0.080", "0.083", "137 cm", "35 cm", 2),
    ("ICRC045144", "Zoom 45, 144 cm", "0.045", "0.060", "0.064", "0.080", "0.083", "144 cm", "65 cm", 2),
    ("ICRC04S125", "Zoom 4S, 125 cm", "0.045", "0.056", "0.045", "0.060", "0.062", "125 cm", "65 cm", 2),
    ("ICRC04S144", "Zoom 4S, 144 cm", "0.045", "0.056", "0.045", "0.060", "0.062", "144 cm", "65 cm", 2),
    ("ICRC04S160", "Zoom 4S, 160 cm", "0.045", "0.056", "0.045", "0.060", "0.062", "160 cm", "65 cm", 2),
    ("ICRC035158", "Zoom 35, 160 cm", "0.035", "0.051", "0.047", "0.061", "0.063", "160 cm", "90 cm", 2),
]

FAMILY_OF = {
    "ICTC": ("distal-access--imperative-care--zoom-88-ldp", "Zoom 88 Large Distal Platform",
             "ifu:imperative-care:zoom-system:lbl002069-02d:zoom-88-ldp"),
    "ICAC": ("guide-catheter--imperative-care--tracstar-ldp", "TracStar LDP Large Distal Platform",
             "ifu:imperative-care:zoom-system:lbl002069-02d:tracstar-ldp"),
    "ICRC": ("aspiration--imperative-care--zoom-aspiration-catheters",
             "Zoom Aspiration Catheters (7X, 71, 55, 45, 4S, 35)",
             "ifu:imperative-care:zoom-system:lbl002069-02d"),
}

COMPAT_CLAIMS = [
    ("aspiration--imperative-care--zoom-aspiration-catheters",
     "ifu:imperative-care:zoom-system:lbl002069-02d",
     "guidewire-compatibility",
     ["PDF page 1, DEVICE DESCRIPTION", "PDF page 2, TABLE 3 - CATHETER COMPATIBILITY"],
     ["compatible with 0.014", "0.035", "0.024"],
     "Per the Zoom System eIFU, the Zoom (7X, 71, 55, 45, 4S) Catheters are compatible with "
     "0.014\" - 0.035\" guidewires and the Zoom 35 Catheter with 0.014\" - 0.024\" guidewires. "
     "Table 3 minimum guide/introducer sheath ID: Zoom 7X, 71, 55 and 45 require 6F / 0.088\"; "
     "Zoom 4S requires 5F / 0.071\"; Zoom 35 requires 5F / 0.068\"."),
    ("aspiration--imperative-care--zoom-aspiration-catheters",
     "ifu:imperative-care:zoom-system:lbl002069-02d",
     "vessel-sizing",
     ["PDF page 2, TABLE 2 - CATHETER VESSEL SIZING GUIDELINES"],
     ["0.071", "3.0 – 3.5", "2.5 – 3.0", "2.0 – 2.5"],
     "Zoom System eIFU vessel sizing guidelines (distal ID -> distal OD mm -> recommended "
     "vessel diameter): 0.071\" -> 2.1 mm -> > 3.5 mm; 0.055\" -> 1.8 mm -> 3.0 - 3.5 mm; "
     "0.045\" -> 1.5 mm -> 2.5 - 3.0 mm; 0.035\" -> 1.3 mm -> 2.0 - 2.5 mm. Select by Table 1 "
     "sizing and the smallest vessel diameter at the thrombus site."),
    ("distal-access--imperative-care--zoom-88-ldp",
     "ifu:imperative-care:zoom-system:lbl002069-02d:zoom-88-ldp",
     "compatibility",
     ["PDF page 1, DEVICE DESCRIPTION", "PDF page 2, TABLE 3 - CATHETER COMPATIBILITY",
      "PDF page 2, TABLE 2 - CATHETER VESSEL SIZING GUIDELINES"],
     ["0.038", "0.115", "0.086"],
     "Per the Zoom System eIFU, the LDP Catheters (Zoom 88 LDP, Zoom 88 LDP Support, TracStar "
     "LDP) are compatible with 0.038\" or smaller guidewires; Table 3 requires an 8F / 0.115\" "
     "minimum-ID guide or introducer sheath and limits coaxial microcatheters/intermediate "
     "catheters to 6F / 0.086\" maximum OD. Table 2: 0.088\" distal ID -> 2.7 mm distal OD -> "
     "recommended vessel diameter > 3.5 mm."),
    ("guide-catheter--imperative-care--tracstar-ldp",
     "ifu:imperative-care:zoom-system:lbl002069-02d:tracstar-ldp",
     "compatibility",
     ["PDF page 1, DEVICE DESCRIPTION", "PDF page 2, TABLE 3 - CATHETER COMPATIBILITY"],
     ["0.038", "0.115", "0.086"],
     "Per the Zoom System eIFU, the TracStar LDP (an LDP Catheter) is compatible with 0.038\" "
     "or smaller guidewires; Table 3 requires an 8F / 0.115\" minimum-ID guide or introducer "
     "sheath and limits coaxial microcatheters/intermediate catheters to 6F / 0.086\" maximum OD."),
]


# ---------------------------------------------------------------------------
# Route 92 claims. Each entry: (claim dict, verification: {file: {page: [needles]}})
# Dimensions come from the FDA 510(k) technological-characteristics tables
# (official_specification); compatibility and labeled dimensions from the IFUs
# (official_labeling). EU/CE labeling is marked and must not ground a
# US-availability answer.
# ---------------------------------------------------------------------------
R92_REVIEW_NOTE = ("Transcribed from the retained document and re-verified against the cited "
                   "PDF page text at ingest time; the ingest aborts if any quoted value is "
                   "absent from the page.")


def _r92_claim(claim_id, device_id, source_id, layer, evidence_class, claim_type,
               locators, text, jurisdiction="US", skus=None, source_quote=None,
               notes=None, source_year="2024"):
    claim = {
        "claim_id": claim_id,
        "device_id": device_id,
        "claim_type": claim_type,
        "evidence_layer": layer,
        "evidence_class": evidence_class,
        "support": "direct",
        "review_status": "source_checked",
        "review_note": R92_REVIEW_NOTE,
        "source_ids": [source_id],
        "locators": locators,
        "checked_at": CHECKED_AT,
        "manufacturer": "route-92-medical",
        "catalog_category": device_id.split("--")[0],
        "jurisdiction": jurisdiction,
        "source_year": source_year,
        "text": text,
    }
    if skus:
        claim["skus"] = skus
        claim["device_name"] = skus[0]["product_name"].rsplit(",", 1)[0]
    if source_quote:
        claim["source_quote"] = source_quote
    if notes:
        claim["notes"] = notes
    return claim


def _sku(product_name, fields, page):
    return {"catalog_number": "", "product_name": product_name, "pdf_page": page,
            "fields": fields, "units": {}, "headers": {}}


ROUTE92_CLAIMS = [
    (_r92_claim(
        "claim:fda510k:K243601:hipoint-reperfusion-system:dimensions",
        "aspiration--route-92-medical--hipoint-reperfusion-system",
        "fda510k:K243601", "official_specification", "fda_510k_or_pma",
        "device_specifications",
        ["PDF pages 7-8 (510(k) Summary pages 3-4), predicate comparison table, subject device column"],
        "Route 92 Medical HiPoint Reperfusion System per the K243601 510(k) summary: "
        "88 Aspiration Catheter nominal ID 0.088\", OD 0.101\" distal / 0.105\" proximal, length 143 cm; "
        "70 Aspiration Catheter nominal ID 0.070\", OD 0.082\" distal / 0.087\" proximal, length 142 cm; "
        "Delivery Catheter ID 0.019\", OD 0.080\" distal / 0.062\" proximal (88) or 0.062\" (70), length 151 cm. "
        "Aspiration uses a hospital vacuum pump at a constant -25 inHg to -27.5 inHg with the Route 92 "
        "Aspiration Tubing Set (K223530). 510(k) technological-characteristics evidence; the IFU is "
        "current labeling and outranks on conflict.",
        skus=[
            _sku("HiPoint 88 Aspiration Catheter",
                 {"id": '0.088"', "distal_od": '0.101"', "proximal_od": '0.105"',
                  "working_length": "143 cm"}, 7),
            _sku("HiPoint 70 Aspiration Catheter",
                 {"id": '0.070"', "distal_od": '0.082"', "proximal_od": '0.087"',
                  "working_length": "142 cm"}, 7),
            _sku("HiPoint 88 Delivery Catheter (Tenzing 8)",
                 {"id": '0.019"', "distal_od": '0.080"', "proximal_od": '0.062"',
                  "working_length": "151 cm"}, 7),
            _sku("HiPoint 70 Delivery Catheter",
                 {"id": '0.019"', "od": '0.062"', "working_length": "151 cm"}, 7),
        ],
        source_year="2025"),
     {"aspiration--route-92-medical--hipoint-reperfusion-system--510k-K243601.pdf": {
         7: ["0.088", "0.070", "0.101", "0.105", "0.082", "0.087", "143 cm", "142 cm",
             "0.019", "0.080", "0.062"],
         8: ["151 cm", "-25 inHg to -27.5 inHg", "K223530"]}}),

    (_r92_claim(
        "claim:ifu:route-92-medical:hipoint-reperfusion-system:ifu-2418e:compatibility",
        "aspiration--route-92-medical--hipoint-reperfusion-system",
        "ifu:route-92-medical:hipoint-reperfusion-system:ifu-2418e",
        "official_labeling", "manufacturer_ifu", "compatibility",
        ["PDF page 1, COMPATIBILITY"],
        "Per IFU-2418.E, the HiPoint 70 Reperfusion System is compatible with catheters or sheaths "
        "with an inner diameter of 0.088\" (2.24 mm); the HiPoint 88 Reperfusion System with sheaths "
        "with an inner diameter of 0.106\" (2.69 mm). Only guidewires may be introduced through the "
        "Delivery Catheters (compatible with guidewires 0.016\" or less); the Delivery Catheters are "
        "not compatible with embolic coils, stent retrievers or other interventional devices.",
        source_quote="HiPoint 70 ... inner diameter of 0.088” (2.24 mm); HiPoint 88 ... inner "
                     "diameter of 0.106” (2.69 mm); guidewires 0.016” or less"),
     {"aspiration--route-92-medical--hipoint-reperfusion-system--ifu.pdf": {
         1: ["2.24 mm", "2.69 mm", "0.016", "not compatible with embolic coils"]}}),

    (_r92_claim(
        "claim:fda510k:K233329:freeclimb-54-reperfusion-system:dimensions",
        "aspiration--route-92-medical--freeclimb-54-reperfusion-system",
        "fda510k:K233329", "official_specification", "fda_510k_or_pma",
        "device_specifications",
        ["PDF page 6 (510(k) Summary page 3), predicate comparison table, subject device column"],
        "Route 92 Medical Full Length 054 Reperfusion System (FreeClimb 54) per the K233329 510(k) "
        "summary: Aspiration Catheter nominal ID 0.054\", nominal OD 0.066\", lengths 125 cm and "
        "148 cm; Delivery Catheter ID 0.019\" proximal / 0.015\" distal, OD 0.048\", length 167 cm; "
        "Aspiration Tubing ID 0.110\", OD 0.188\", length 112\". Vacuum -25 inHg to -27.5 inHg. "
        "510(k) technological-characteristics evidence; the IFU is current labeling and outranks "
        "on conflict.",
        skus=[
            _sku("FreeClimb 54 Aspiration Catheter",
                 {"id": '0.054"', "od": '0.066"', "working_length": "125 cm; 148 cm"}, 6),
            _sku("FreeClimb 54 Delivery Catheter",
                 {"id": '0.019" proximal / 0.015" distal', "od": '0.048"',
                  "working_length": "167 cm"}, 6),
        ],
        source_year="2024"),
     {"aspiration--route-92-medical--freeclimb-54-reperfusion-system--510k-K233329.pdf": {
         6: ["0.054", "0.066", "125 cm and 148 cm", "0.019", "0.015", "0.048", "167 cm",
             "0.110", "0.188"]}}),

    (_r92_claim(
        "claim:ifu:route-92-medical:freeclimb-reperfusion-system:ifu-2556e:compatibility",
        "aspiration--route-92-medical--freeclimb-reperfusion-system",
        "ifu:route-92-medical:freeclimb-reperfusion-system:ifu-2556e",
        "official_labeling", "manufacturer_ifu", "compatibility",
        ["PDF page 1, Compatibility"],
        "Per the CE IFU-2556.E, the FreeClimb 88 Reperfusion System is compatible with catheters or "
        "sheaths with a minimum inner diameter of 0.106\" (2.69 mm); FreeClimb 70 requires 0.088\" "
        "(2.24 mm); FreeClimb 54 requires 0.070\" (1.8 mm). Only guidewires (0.016\" or less) may be "
        "introduced through the Delivery Catheter; it is not compatible with embolic coils, stent "
        "retrievers or other interventional devices. EU/CE labeling - confirm US labeling before "
        "assuming US availability.",
        jurisdiction="EU",
        source_quote="minimum inner diameter of 0.106” (2.69 mm) ... 0.088” (2.24 mm) ... "
                     "0.070” (1.8 mm) ... guidewires 0.016” or less",
        source_year="2026"),
     {"aspiration--route-92-medical--freeclimb-reperfusion-system--ifu.pdf": {
         1: ["2.69 mm", "2.24 mm", "1.8 mm", "0.016"]}}),

    (_r92_claim(
        "claim:ifu:route-92-medical:base-camp-sheath-2-0:ifu-3798b:dimensions",
        "access-devices--route-92-medical--base-camp-sheath-2-0",
        "ifu:route-92-medical:base-camp-sheath-2-0:ifu-3798b",
        "official_labeling", "manufacturer_ifu", "device_specifications",
        ["PDF page 1, Dimensional Specifications", "PDF page 1, Compatibility",
         "PDF page 1, Hydrophilic Coating Length"],
        "Base Camp Sheath System 2.0 per the EU IFU-3798.B dimensional specifications: Sheath "
        "working length 90 cm or 80 cm, ID 2.7 mm (0.106\"), OD 3.1 mm (0.122\"); Dilator working "
        "length 103 cm, ID 1.0 mm (0.040\"), OD 2.6 mm (0.102\"); Navigating Catheter working length "
        "113 cm, ID 1.0 mm (0.040\"), OD 2.7 mm (0.104\"). The Sheath accepts 8F or smaller "
        "catheters; a 0.035\" guidewire may be used through the Dilator and Navigating Catheter. "
        "Hydrophilic coating: Sheath 8 cm, Dilator 15 cm, Navigating Catheter 40 cm from the distal "
        "end. EU/CE labeling - confirm US labeling before assuming US availability.",
        jurisdiction="EU",
        skus=[
            _sku("Base Camp 2.0 Sheath",
                 {"id": '2.7 mm (0.106")', "od": '3.1 mm (0.122")',
                  "working_length": "90 cm; 80 cm"}, 1),
            _sku("Base Camp 2.0 Dilator",
                 {"id": '1.0 mm (0.040")', "od": '2.6 mm (0.102")',
                  "working_length": "103 cm"}, 1),
            _sku("Base Camp 2.0 Navigating Catheter",
                 {"id": '1.0 mm (0.040")', "od": '2.7 mm (0.104")',
                  "working_length": "113 cm"}, 1),
        ],
        source_year="2025"),
     {"access-devices--route-92-medical--base-camp-sheath-2-0--ifu.pdf": {
         1: ["0.106", "0.122", "103 cm", "0.040", "0.102", "113 cm", "0.104",
             "8 cm", "15 cm", "40 cm", "0.035"]}}),

    (_r92_claim(
        "claim:ifu:route-92-medical:base-camp-sheath:ifu-0663j:compatibility",
        "access-devices--route-92-medical--base-camp-sheath",
        "ifu:route-92-medical:base-camp-sheath:ifu-0663j",
        "official_labeling", "manufacturer_ifu", "compatibility",
        ["PDF page 1, Device Description"],
        "Per the CE IFU-0663.J, the Base Camp Sheath System comprises a Sheath, Dilator, Navigating "
        "Catheter and RHV; the Sheath's inner lumen is compatible with 8F or smaller catheters. "
        "EU/CE labeling - confirm US labeling before assuming US availability.",
        jurisdiction="EU",
        source_quote="The inner lumen of the catheter is compatible with 8F or smaller catheters",
        source_year="2024"),
     {"access-devices--route-92-medical--base-camp-sheath--ifu.pdf": {
         1: ["8F or smaller catheters"]}}),

    (_r92_claim(
        "claim:ifu:route-92-medical:tenzing-7:ifu-0466p:labeled-use",
        "delivery-catheter--route-92-medical--tenzing-7",
        "ifu:route-92-medical:tenzing-7:ifu-0466p",
        "official_labeling", "manufacturer_ifu", "compatibility",
        ["PDF page 1, Indications for Use (United States FDA)", "PDF page 1, Intended Purpose"],
        "Per IFU-0466.P, the Tenzing 7 Delivery Catheter is indicated (US FDA) for use with "
        "compatible catheters to facilitate insertion and guidance of catheters into the "
        "neurovasculature; it is intended to deliver large-bore catheters with an inner diameter of "
        "0.068\" or greater, and a standard 0.014\" or 0.016\" neurovascular guidewire may be "
        "inserted through it.",
        source_quote="deliver large-bore catheters with an inner diameter of 0.068” or greater "
                     "... standard 0.014” or 0.016” neurovascular guidewire",
        source_year="2024"),
     {"delivery-catheter--route-92-medical--tenzing-7--ifu.pdf": {
         1: ["0.068", "0.014", "0.016"]}}),
]


def verify_route92() -> None:
    import fitz

    problems = []
    for claim, verification in ROUTE92_CLAIMS:
        for filename, pages in verification.items():
            with fitz.open(CATALOG_ROOT / CURRENT / filename) as doc:
                for page, needles in pages.items():
                    text = doc[page - 1].get_text("text")
                    for needle in needles:
                        if needle not in text:
                            problems.append(f"{claim['claim_id']}: {needle!r} not on "
                                            f"{filename} page {page}")
    if problems:
        raise SystemExit("Route 92 verification failed; nothing written:\n" + "\n".join(problems))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def page_texts(pdf_path: Path, pages: int = 2) -> list[str]:
    import fitz

    with fitz.open(pdf_path) as doc:
        return [doc[i].get_text("text") for i in range(min(pages, doc.page_count))]


def verify_zoom_table(pdf_path: Path) -> None:
    texts = page_texts(pdf_path, 2)
    problems = []
    for row in TABLE1:
        number, _, *values, page = row
        text = texts[page - 1]
        if number not in text:
            problems.append(f"{number}: model number not on page {page}")
            continue
        for value in values:
            token = value.split(" ")[0]
            if token not in text:
                problems.append(f"{number}: value {value!r} not on page {page}")
    for _, _, kind, _, needles, _ in COMPAT_CLAIMS:
        joined = "\n".join(texts)
        for needle in needles:
            if needle not in joined:
                problems.append(f"{kind}: quote {needle!r} not on pages 1-2")
    if problems:
        raise SystemExit("verification failed; nothing written:\n" + "\n".join(problems))


def build_dimension_claims() -> list[dict]:
    families: dict[str, list] = {}
    for row in TABLE1:
        families.setdefault(row[0][:4], []).append(row)
    claims = []
    for prefix, rows in families.items():
        device_id, device_name, source_id = FAMILY_OF[prefix]
        skus = []
        for (number, name, d_id, d_od, p_id, p_od, max_od, length, coating, page) in rows:
            skus.append({
                "catalog_number": number,
                "product_name": name,
                "pdf_page": page,
                "fields": {
                    "id": f'{d_id}"',
                    "distal_od": f'{d_od}"',
                    "proximal_od": f'{p_od}"',
                    "od": f'{max_od}"',
                    "working_length": length,
                    "proximal_inner_diameter": f'{p_id}"',
                    "hydrophilic_coating_length": coating,
                },
                "units": {},
                "headers": {"id": "Distal Inner Diameter", "distal_od": "Distal Outer Diameter",
                            "proximal_inner_diameter": "Proximal Inner Diameter",
                            "proximal_od": "Proximal Outer Diameter",
                            "od": "Maximum Outer Diameter",
                            "working_length": "Nominal Working Length",
                            "hydrophilic_coating_length": "Hydrophilic Coating Length"},
            })
        pages = sorted({s["pdf_page"] for s in skus})
        printed = "; ".join(
            f"{s['catalog_number']} ({s['product_name']}): distal ID {s['fields']['id']}, distal OD "
            f"{s['fields']['distal_od']}, proximal ID {s['fields']['proximal_inner_diameter']}, proximal OD "
            f"{s['fields']['proximal_od']}, max OD {s['fields']['od']}, working length {s['fields']['working_length']}"
            for s in skus)
        claims.append({
            "claim_id": f"claim:ifu:imperative-care:zoom-system:lbl002069-02d:{device_id.split('--')[-1]}:dimensions",
            "device_id": device_id,
            "device_name": device_name,
            "manufacturer": "imperative-care",
            "catalog_category": device_id.split("--")[0],
            "claim_type": "device_specifications",
            "evidence_layer": "official_labeling",
            "evidence_class": "manufacturer_ifu",
            "support": "direct",
            "review_status": "source_checked",
            "review_note": REVIEW_NOTE,
            "source_ids": [source_id],
            "locators": [f"PDF page {p}, TABLE 1 - CATHETER SIZES" for p in pages],
            "checked_at": CHECKED_AT,
            "source_year": "2026",
            "jurisdiction": "US",
            "skus": skus,
            "notes": "IFU is current labeling and outranks catalog/510(k) values on conflict "
                     "(e.g. the K243047-derived Zoom 7X distal OD 0.085\" is superseded by the "
                     "eIFU's printed distal OD 0.083\" / maximum OD 0.086\").",
            "text": f"{device_name} per the Imperative Care Zoom System eIFU (LBL002069-02.D): {printed}. "
                    "Current labeling; dimensions also appear on each device label.",
        })
    return claims


def build_compat_claims() -> list[dict]:
    claims = []
    for device_id, source_id, kind, locators, needles, text in COMPAT_CLAIMS:
        claims.append({
            "claim_id": f"claim:ifu:imperative-care:zoom-system:lbl002069-02d:{device_id.split('--')[-1]}:{kind}",
            "device_id": device_id,
            "claim_type": "compatibility" if "compat" in kind else "sizing",
            "compatibility_status": "manufacturer_labeled",
            "evidence_layer": "official_labeling",
            "evidence_class": "manufacturer_ifu",
            "support": "direct",
            "review_status": "source_checked",
            "review_note": REVIEW_NOTE,
            "source_ids": [source_id],
            "locators": locators,
            "checked_at": CHECKED_AT,
            "source_year": "2026",
            "jurisdiction": "US",
            "source_quote": "; ".join(needles),
            "text": text,
        })
    return claims


def main() -> int:
    zoom_pdf = CATALOG_ROOT / ZOOM_IFU
    verify_zoom_table(zoom_pdf)
    verify_route92()

    registry = read_json(REGISTRY)
    have_sources = {s["source_id"] for s in registry["sources"]}
    new_sources = 0
    for (source_id, device_id, title, source_type, jurisdiction, revision,
         filename, url, notes, identity_any) in SOURCES:
        if source_id in have_sources:
            continue
        path = CATALOG_ROOT / filename
        if not path.is_file():
            raise SystemExit(f"missing file for {source_id}: {filename}")
        registry["sources"].append({
            "source_id": source_id,
            "device_id": device_id,
            "title": title,
            "source_type": source_type,
            "status": "current",
            "evidence_depth": "local_full_text",
            "jurisdiction": jurisdiction,
            "revision": revision,
            "local_filename": filename,
            "official_url": url,
            "sha256": sha256_of(path),
            "checked_at": CHECKED_AT,
            "identity": {"required_any": identity_any},
            "notes": notes,
        })
        have_sources.add(source_id)
        new_sources += 1

    existing = read_jsonl(CLAIMS)
    have_claims = {c["claim_id"] for c in existing}
    new_claims = [c for c in (build_dimension_claims() + build_compat_claims()
                              + [claim for claim, _ in ROUTE92_CLAIMS])
                  if c["claim_id"] not in have_claims]

    write_json(REGISTRY, registry)
    with CLAIMS.open("a", encoding="utf-8", newline="\n") as handle:
        for claim in new_claims:
            handle.write(json.dumps(claim, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"new_sources": new_sources, "new_claims": len(new_claims)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
