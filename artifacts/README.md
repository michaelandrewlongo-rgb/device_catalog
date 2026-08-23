# Device Artifacts

Generated at: 2026-04-20T00:07:52.893Z

This folder reorganizes source data from `pipeline/data` into device artifact folders, now grouped by seed registry when the device cleanly fits one of the requested registries.

Seed registry folders are grouped under:

- `neurointerventional/`
- `spine/`
- `cranial_neurosurgery/`

Devices that do not cleanly fit a seed registry are kept under `_outside_seed_registries/` by source category. Catalog-wide or unmapped files remain in `_catalog_metadata/` and `_unassigned/`.

Each device folder contains source-named subdirectories when data exists:

- `510k/`
- `data_by_device/`
- `enriched/`
- `extracted/`
- `fda_raw/`
- `merged/`
- `scraper_raw/`

Each device folder also has a `manifest.json` listing the source files copied into that artifact and the registry mapping. Very long device slugs may use shortened folder names; the full slug remains in `manifest.json` and `ARTIFACT_INDEX.json`.

Mapping indexes:

- `SEED_REGISTRY_INDEX.md`
- `SEED_REGISTRY_MAP.json`
- `ARTIFACT_INDEX.json`
