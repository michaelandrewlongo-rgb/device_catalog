# STATE.md

I was trying to:
Implement the thrombectomy coaxial copilot plan in a conservative, verified-only way.

The last thing I saw:
The compatibility CLI now supports fuzzy device lookup, source/confidence labels, a `--case` workflow, and grouped gap triage. The data file has been versioned to `0.3.0-experimental` with an explicit source policy.

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

## Verification

```
python -m pytest -q tests/test_compat.py
```

Result: 15 passed. Pytest emitted a cache warning because `.pytest_cache` already has a conflicting path, but tests passed.

## Known issues

- Numeric fields were not filled from non-official snippets. This is intentional: official source acquisition is still required before adding values for unresolved rows.
- Highest-impact unresolved rows:
  - AXS Catalyst 6
  - React 68 / React 71
  - AXS Infinity LS
  - Walrus BGC
  - CereGlide 71
  - Zoom 7X
  - Penumbra RED 68
- `ROADMAP.md` had pre-existing modifications before this session; avoid staging it blindly with future commits.

## What I want next

1. Acquire official manufacturer/FDA dimensions for the critical unresolved rows.
2. Fill only fields supported by official sources, leaving unsupported fields null.
3. Add source URLs beside every newly filled field or row.
4. Broaden CLI tests around ambiguous fuzzy matches and command-line invocation.
