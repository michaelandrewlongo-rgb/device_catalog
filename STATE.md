# STATE.md

I was trying to:
Land the knowledge v2.1 lane in git and feed it the 15 Endovascular Today device-guide PDFs (2026-08 exports) as discovery-only secondary candidates, so `agent-textbooks` can see EVT sizing rows without ever treating them as labeling.

The last thing I saw (updated 2026-08-23, third pass):
```
export -> 639 sources, 873 actionable claims, 269 secondary candidates, rejected=0
- 483 EVT guide rows (every row independently audited) at trade_journal_device_guide
- 4 manufacturer catalogs (Medtronic 2019, Stryker 2024, MicroVention 2019 intl, Balt 2020 intl) + Penumbra 2025 spec page: 1,859 SKUs in 181 families at manufacturer_catalog
- 11 current IFUs registered and identity-checked; 163 official_labeling claims drafted by agents, validated by import_claim_drafts (1 draft rejected on page check)
All priority-1 wishlist IFUs are now on file (Onyx LES is the 10/13 revision as served; product page cites newer CDOC numbers).
```
Earlier (second pass):
```
Spot audit of 20 EVT candidates (5 independent auditors): rows 20/20, fields 121/127; all 6 partials were numbers parsed out of prose cells.
Fix: classify_cell()/cell_unit() in secondary_candidates.py - numbers only from pure number cells, ranges kept as ranges, in-cell units override headers (73 prose, 10 range cells corpus-wide).
Added manufacturer IFUs: River Stent System (HDE H230002, 1115-001 Rev A, 9 claims) and Zilver Vascular Stent (IFU0043-10, 6 claims; iliac labeling only - venous-sinus use is off-label and is NOT a claim).
export -> 43 sources, 46 actionable claims, 247 secondary candidates; rejected=0
```
Earlier:
```
python -m pipeline.run_knowledge_v2 official-scan   -> {'reviewable': 28, 'blocked': 2}
python -m pipeline.run_knowledge_v2 audit           -> 41 sources, quarantined=2, schema_failures=0
python -m pipeline.run_knowledge_v2 build-candidates-> 311 guide rows from 15 PDFs; 247 candidates (94 joined to existing records, 63 peripheral rows dropped)
python -m pipeline.run_knowledge_v2 export          -> 41 sources, 31 actionable claims, 247 secondary candidates; rejected=0 (schema 2.1.0)
python -m pipeline.export_consolidated_csv          -> 482 rows -> exports/consolidated/device_catalog_neurointerventional_consolidated.csv
pytest tests/test_knowledge_v2.py                   -> 23 passed
```
The 21 `fda_510k_summary` sources and 25 `official_specification` claims that previously existed only in the untracked `~/.codex` skill copy are now in `source_registry.json` / `reviewed_claims.v2.jsonl` and on the official watchlist (the scan now text-extracts PDF bodies for identity checks).

I think the problem is:
- EVT rows are joined to enriched records by normalized product name + manufacturer; 153 of 247 candidates have `device_entry: none`. That is by design (no skeleton devices), but it means alias/clearance metadata is thin for them.
- `pipeline/data/extracted/evt_guides/` is regenerable and should be gitignored; `.gitignore` carries unrelated uncommitted edits so it was left alone.
- The two blocked official pages are still Medtronic.
- The hand-made CSV in Downloads is superseded by the generator output.

What I want next:
Spot-audit ~20 candidates against the retained PDFs (`sources/trade_journal/endovascular-today/2026-08/`), then run `refresh_device_knowledge.ps1` after each guide refresh. Promote a dimension to actionable only via a reviewed claim against an IFU, labeling, or 510(k) table - never from a candidate.
