# STATE.md

I was trying to:
Implement the thrombectomy coaxial copilot plan in a conservative, verified-only way.

The last thing I saw:
The compatibility CLI now supports fuzzy device lookup, source/confidence labels, a `--case` workflow, and grouped gap triage. The source acquisition pass now fills React 68, React 71, and Penumbra RED 68 from manufacturer-backed evidence.

## What was done this session

- Added `tests/test_compat.py` for catalog integrity and compatibility logic.
- Rebuilt `pipeline/compat_query.py` around reusable helpers:
  - `find_device()` for exact, normalized, substring, and fuzzy matching.
  - `fit_details()` for explainable fit status and clearance.
  - `verification_status()` and `source_label()` for conservative confidence labels.
  - `missing_fields()` and `gap_kind()` for critical/context gap grouping.
- Added `python -m pipeline.compat_query --case DEVICE` for a case-oriented summary:
  - selected device dimensions and source status
  - accepting outer devices
  - inner devices that fit through the selected device
  - unknown counts where missing dimensions block a determination
- Updated `--fits-through`, `--accepts`, `--stack`, `--gaps`, and default listing to show source/confidence labels.
- Updated `pipeline/data/compatibility/thrombectomy_stack.json` metadata:
  - version `0.3.0-experimental`
  - explicit verified/partial/inferred/needs-source policy
  - Stryker manufacturer source URLs for unresolved AXS Infinity LS, FlowGate2, and AXS Catalyst 6 rows
- Added `pipeline/coaxial_acquisition.py`:
  - pulls/parses manufacturer pages for source-backed dimensions
  - writes `pipeline/data/evidence/coaxial/coaxial_unresolved_review.json`
  - auto-applies only accepted manufacturer-tier records
  - keeps seller/distributor-style sources as candidates unless corroborated
- Filled manufacturer-backed dimensions:
  - React 68: ID 0.068", OD 0.083", length 132 cm
  - React 71: ID 0.071", OD 0.0855", length 132 cm
  - Penumbra RED 68: ID 0.068", OD 0.084", length 132 cm

## Verification

```
python -m pytest -q tests/test_coaxial_acquisition.py tests/test_compat.py -p no:cacheprovider
```

Result: 20 passed.

## Known issues

- Numeric fields are still filled only from official/manufacturer/FDA-style sources. Distributor or seller pages should remain review candidates unless corroborated.
- Highest-impact unresolved rows:
  - AXS Catalyst 6
  - AXS Infinity LS
  - Walrus BGC
  - CereGlide 71
  - Zoom 7X
- `ROADMAP.md` had pre-existing modifications before this session; avoid staging it blindly with future commits.

## What I want next

1. Add AccessGUDID/distributor candidate discovery for Walrus BGC, Zoom 7X, AXS Catalyst 6, AXS Infinity LS, and CereGlide 71.
2. Keep distributor values out of `thrombectomy_stack.json` until matched to manufacturer/FDA evidence.
3. Add source URLs beside every newly filled field or row.
4. Broaden CLI tests around ambiguous fuzzy matches and command-line invocation.

## Additional Focus

- `my_endo_catheters` review artifacts were created for catheter and catheter-system mentions across `study_new_129.csv` and `study_blinded_88.csv`.
- Focus outputs live under `reviews/jnis_study/`:
  - `catheter_system_focus_report.md`
  - `catheter_system_focus_summary.csv`
  - `catheter_system_case_mentions.csv`
- Current priority order for `my_endo_catheters` is centered on catheter platforms and workflow systems such as Zoom, Benchmark/BMX, Phenom, Echelon 10, RIST, Walrus, Simmons, Glide, Vertebral/VERT, and Cerebase DA.
