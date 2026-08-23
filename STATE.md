# STATE.md

I was trying to:
Serve every high-quality source layer as primary, actionable evidence (per the 2026-08-23 decision: official labeling, official specification, manufacturer catalog, and trade-journal device guide are all primary candidates at equal rank), sync the branch with origin, and keep documentation current.

The last thing I saw (updated 2026-08-23, fourth pass):
```
audit  -> 642 registered sources, quarantined=2 (the known misfiled ENTERPRISE/Onyx HD-500 and Pipeline Flex/Shield docs), schema_failures=0
export -> 642 sources, 880 actionable claims, 0 secondary candidates, rejected=0 (schema 2.1.0)
pytest tests/ -> 134 passed
```
Registry composition (565 devices with actionable claims):
- 483 EVT guide rows (2026-08 US + European exports, every row independently audited) promoted to `device_specifications` claims at `trade_journal_device_guide`; French->inch conversions folded in as `derived_calculation` entries; prose cells served as printed text, never parsed numbers.
- 4 manufacturer catalogs (Medtronic 2019, Stryker 2024, MicroVention 2019 intl, Balt 2020 intl) + Penumbra 2025 spec page: 1,859 SKUs / 181 families at `manufacturer_catalog`.
- 14 devices with current-IFU `official_labeling` claims (11 supplied IFUs + River HDE H230002, Zilver IFU0043-10, Neuroform Atlas Rev AB); ~184 claims drafted by agents and validated by `import_claim_drafts` (indications, contraindications, sizing, compatibility, deployment, preparation - MRI/storage out of scope by decision).
- 25 `official_specification` claims (510(k) tables, Q'Apel Walrus/Armadillo/Zebra and Wedge 21 product pages).

Branch state: work lives on `jnis-catheter-focus`. On 2026-08-23 the previously uncommitted artifact reorganization (root `*--knowledge.md` files moved under `artifacts/<domain>/<category>/<device>/data_by_device/`, plus pipeline/data evidence trees) was preserved as commit `2348c203`, then origin's two divergent commits (FDA catheter backfill) were merged; export-file conflicts resolved by regenerating from the masters. `pipeline/build_site.py` now reads knowledge files from the artifacts layout. `core.longpaths` enabled for this repo. Note: CATALOG_INDEX.md and PRODUCT_GOAL.md were deleted by the reorg.

Flat exports (regenerate after any registry change):
```
python -m pipeline.run_knowledge_v2 audit && python -m pipeline.run_knowledge_v2 export
python -m pipeline.export_consolidated_csv        # exports/consolidated/... (482 rows)
python -m pipeline.export_flat_dimensions         # ~/Downloads/device_dimensions_flat.csv (2,558 rows, all layers)
```
Then run `refresh_device_knowledge.ps1` (or copy `exports/agent-textbooks/` into both skill registries) to sync the DSS.

I think the problem is:
- Onyx LES IFU on file is the 10/13 revision; Medtronic's page cites newer CDOC numbers.
- Zebra guide page only carried codes/lengths (no ID/OD); Onyx in-service pptx not ingested.
- 413 priority-2 wishlist devices (see ~/Downloads/ifu_wishlist.csv) still have no IFU; their specs come from catalogs/guides only.
- The two blocked official pages are still Medtronic.

What I want next:
Collect priority-2 IFUs as they surface and run them through the agent-draft -> `import_claim_drafts` lane; re-run `official-scan` periodically so `checked_at` stays within the DSS 30-day freshness gate.
