# Evidence Pipeline Notes

Date: 2026-04-15

## Summary

Implemented a conservative V1 evidence layer for grounded device reviews. The design keeps direct source records separate from any LLM-derived interpretation, and PubMed ingestion is intentionally limited to bibliographic metadata plus title and abstract.

## Implemented

- Added `pipeline/evidence/` for evidence models, source clients, storage helpers, provenance backfill, synonym registry, OpenRouter helper client, and review rendering.
- Added `pipeline/run_evidence.py` CLI with:
  - `build-registry`
  - `build-provenance`
  - `pubmed`
  - `trials`
  - `fda-safety`
  - `gudid`
  - `review`
  - `all-pilot`
- Added `OPENROUTER_API_KEY` loading in `pipeline/config.py`.
- Environment variables now take precedence over `~/Desktop/master_env.txt`.
- If a key appears multiple times in `master_env.txt`, the last matching value is used. Secrets are not logged.
- Added tests for curated claim provenance, registry parsing/matching, PubMed XML parsing, review rendering, and OpenRouter cache behavior.

## Pilot Run

Pilot category: `flow-diverter`

Commands run:

```powershell
python -m pipeline.run_evidence build-registry --category flow-diverter
python -m pipeline.run_evidence build-provenance --category flow-diverter
python -m pipeline.run_evidence pubmed --category flow-diverter --limit 1
python -m pipeline.run_evidence trials --category flow-diverter --limit 1
python -m pipeline.run_evidence fda-safety --category flow-diverter --limit 1
python -m pipeline.run_evidence gudid --category flow-diverter --limit 1
python -m pipeline.run_evidence review --category flow-diverter
python -m pipeline.run_evidence all-pilot --category flow-diverter --limit 1
```

Final artifact counts:

```text
registry: 1 file, 5 records
claims: 1 file, 290 records
pubmed: 5 files, 5 records
trials: 5 files, 0 records
fda_maude: 5 files, 0 records
fda_recalls: 5 files, 0 records
fda_raw / UDI: 5 files, 3 records
accessgudid: 5 files, 0 records
review: 5 devices, 8 source records, draft status
mock_in_review: false
```

Generated review artifacts:

- `reviews/flow-diverter/flow-diverter-review.json`
- `reviews/flow-diverter/flow-diverter-review.md`

## Source Behavior Observed

- PubMed worked and returned one title/abstract record per flow-diverter identity with `--limit 1`.
- FDA UDI returned records for `PIPELINE`, `Fred`, and `Surpass Streamline`.
- FDA MAUDE and recalls returned no records for the current precise flow-diverter queries.
- ClinicalTrials.gov exited cleanly but returned no stored records in this environment.
- AccessGUDID exited cleanly but returned no stored records from the current endpoint/query shape.
- Short acronym-only aliases such as `PED` are filtered out of direct-source API queries to avoid false positives, because V1 does not classify matches.

## Tests

Targeted evidence tests passed:

```powershell
python -m pytest -q tests/test_evidence_claims.py tests/test_evidence_registry.py tests/test_evidence_pubmed.py tests/test_evidence_review.py tests/test_evidence_openrouter.py -p no:cacheprovider
```

Result:

```text
8 passed
```

## Session 2 (2026-04-15) — Hardening

### Completed

- Fixed AccessGUDID: `size` → `pageSize` (API v2 param). Added unexpected-response guard when
  `gudid.device` is present but not a list. Added connection error + http_error handling.
- Hardened ClinicalTrials.gov: now queries `query.intr` (intervention field) first, falls back to
  `query.term` if empty. Terms are quoted for phrase matching via `build_trials_query()`.
- Added `SourceHealth` dataclass to `models.py`. All four source clients (`pubmed`, `clinicaltrials`,
  `accessgudid`, `fda_*`) now accept an optional `health_log: list[SourceHealth]` parameter.
  Health logs are written to `pipeline/data/evidence/health/{category}-{command}-health.json`.
  `fallback_used` flag in ClinicalTrials health records surfaces when `query.term` fallback fires.
  `http_status: int | None` — None means no HTTP response received (connection error).
- Added `detect_potential_duplicates()` to `registry.py`: flags same-category/manufacturer pairs
  where product slugs are prefix-related (min 2 segments in shorter slug) or display names share
  ≥3 non-stopword words. `build-registry` CLI prints warnings.
- 24 evidence tests passing (8 original + 16 new in `tests/test_evidence_health.py`).

### Session 3 (2026-04-15) — Live verification + endpoint fix

Both endpoints verified against live APIs:

**ClinicalTrials.gov:**
- Query format confirmed correct via ClinicalTrials MCP tool: `"Pipeline Flex" OR "Pipeline
  Embolization Device"` → 12 results. Quoted phrase syntax + `query.intr` field are valid.
- Direct Python requests from this IP are rate-limited (403). The `_fetch` method now returns
  the HTTP status code (not just `[]`) so health log shows `http_error:403` rather than `empty`.
  This is a network-level block, not a query format bug.

**AccessGUDID:**
- Endpoint was wrong: `/api/v2/devices/search.json` → 404. Correct: `/devices/search.json`.
- Response shape was wrong: `gudid.device` → `search_results.result`.
- ID field was wrong: `identifiers.identifier[0].deviceId` → `ID[0].deviceId` (type=Primary).
- Source URL now points to device UUID: `https://accessgudid.nlm.nih.gov/devices/{uuid}`.
- After fix: 5/5 flow-diverter devices return results (10 records each with `--limit 2`).

**Live pilot results (flow-diverter, --limit 2):**
- pubmed: ok x5
- clinicaltrials: http_error x5 (403, IP rate-limit — not a code bug)
- fda_maude: empty x5
- fda_recalls: empty x5
- fda_udi: ok x3, empty x2
- accessgudid: ok x5

**Tests:** 25 evidence tests passing.

### Remaining

- ClinicalTrials.gov is rate-limiting direct Python requests. Options: use a VPN/proxy, add
  retry with backoff, or accept that ClinicalTrials data will be collected via MCP manually.
- Consider later LLM pass for synonym expansion and name normalization only.

## my_endo_catheters Inventory

We also created a focused device inventory from `my_endo_catheters` in `.research/jnis_study/`.
That pass tracks catheter and catheter-system mentions separately from wires, coils, stents, liquid embolics, closure devices, and generic access supplies.

Generated artifacts:

- `reviews/jnis_study/device_inventory_report.md`
- `reviews/jnis_study/device_inventory_summary.csv`
- `reviews/jnis_study/device_case_mentions.csv`
- `reviews/jnis_study/catheter_system_focus_report.md`
- `reviews/jnis_study/catheter_system_focus_summary.csv`
- `reviews/jnis_study/catheter_system_case_mentions.csv`

The working focus list emphasizes catheter platforms and systems such as Zoom, Benchmark/BMX, Phenom, Echelon 10, RIST, Walrus, Simmons, Glide, Vertebral/VERT, and Cerebase DA.
