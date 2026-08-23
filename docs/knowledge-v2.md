# Device Knowledge v2

`device_catalog` owns device source artifacts and claim review. `agent-textbooks` receives only the sanitized JSONL exchange under `exports/agent-textbooks/` (schema 2.1.0: `device_sources.v2.jsonl`, `device_claims.v2.jsonl`, `manifest.json`).

## Trust model

- Existing `*-knowledge.md` prose is `legacy_derived_summary`: useful for discovery, but draft and unsupported until migrated claim by claim.
- Document status is independent of claim review: `current`, `historical`, `superseded`, `quarantined`, or `unavailable`.
- Claim support is `direct`, `adjacent`, `conflicting`, or `unsupported`.
- Review is `draft`, `source_checked`, `clinician_reviewed`, or `stale`.
- Compatibility is separately labeled as manufacturer-labeled, required, recommended, dimensional-only, reported off-label, or unknown.

The downstream export admits only direct, located, source-checked or clinician-reviewed claims tied to a current source whose full text was checked. Everything else fails closed.

## Evidence layers (all primary, equal rank)

Per the 2026-08-23 decision, every served layer is primary, actionable evidence; the DSS ranks them equally and interleaves results:

| Layer | Source type | How it enters |
|---|---|---|
| `official_labeling` | Current IFU / labeling summary / HDE | Retained PDF + agent-drafted claims via `import_claim_drafts` |
| `official_specification` | 510(k) summary tables, manufacturer product pages | Reviewed claims with verbatim locators |
| `manufacturer_catalog` | Manufacturer product catalogs (dated) | `ingest_manufacturer_catalog` from extracted rows |
| `trade_journal_device_guide` | Endovascular Today device guides | `promote_guide_rows` from independently audited rows |
| `clinical_context` | Peer-reviewed clinical statements | Manual review |

Layer conventions that keep the layers honest:
- Catalog and guide claims carry their publication year and a "confirm against current IFU" note; labeling wins on conflict as a matter of *content*, not rank.
- French->inch conversions inside guide claims are separate entries labeled `derived_calculation` (`inches = French / 76.2`), never blended into printed values.
- Guide cells that are prose, ranges, or unit-conflicting are stored as such (`parse: "prose"`, `range: [lo, hi]`, `unit_conflict` + `header_unit`); a number is only served when the printed cell is a pure number.
- Secondary candidates (`device_dimension_candidates.v2.jsonl`) are an empty legacy lane: every former candidate was audited and promoted; the exporter still validates the file when present.

## Claim scope

Drafted labeling claims cover indications, contraindications, sizing tables, compatibility / minimum-ID requirements, deployment rules, and preparation. MRI conditions and storage/handling are out of scope by decision (2026-08-23).

## Workflow

```bash
python -m pipeline.run_knowledge_v2 official-scan       # identity/hash check of official pages
python -m pipeline.run_knowledge_v2 audit               # quarantine mismatches; never auto-promotes
python -m pipeline.run_knowledge_v2 build-candidates    # EVT guides: extract + audit-join + promote
python -m pipeline.knowledge_v2.ingest_manufacturer_catalog <name> --manufacturer <mfr> --pdf <path>
python -m pipeline.knowledge_v2.import_claim_drafts <draft.json> ...   # agent-drafted IFU claims
python -m pipeline.run_knowledge_v2 export              # fail-closed export to exports/agent-textbooks/
python -m pipeline.export_consolidated_csv              # flat SKU CSV (exports/consolidated/)
python -m pipeline.export_flat_dimensions               # device x dimension CSV, all layers -> ~/Downloads
```

The official scan is limited to configured FDA and manufacturer domains. It reports page availability, identity matches, hashes, and detected document identifiers. The audit reconciles the latest report: identity or pinned-hash mismatch quarantines a source, and a blocked/unavailable current source becomes unavailable until revalidated. A successful scan refreshes `checked_at` only when the official content matches the retained artifact. It never promotes a new source or claim automatically. Review `reviews/knowledge_v2/`, reopen the exact source, add only locatable claims to `pipeline/knowledge_v2/data/reviewed_claims.v2.jsonl`, then export again.

After any export, sync `exports/agent-textbooks/` into the DSS registries (`refresh_device_knowledge.ps1`); the DSS re-verifies every gate on sync (`sync_device_knowledge.py` fails closed) and at query time enforces 30-day `checked_at` freshness.

Both the historical flat layout and the relocated `artifacts/**/data_by_device/` layout are scanned. Divergent duplicate artifacts are quarantined rather than selected silently.

The neurovascular audit intentionally quarantines the misfiled ENTERPRISE document labeled as Onyx HD-500 and the plain Pipeline Flex document labeled as Pipeline Shield. Historical and superseded documents remain visible for version comparison.

## Ingestion lanes in detail

**EVT device guides** (`pipeline/extraction/evt_guide_pdf.py` -> `secondary_candidates.py` -> `promote_guide_rows.py`): geometric row extraction (header cell x-bounds + shaded bands + gaps, page-wrap continuation merging), cell classification, then promotion of only rows present in `data/evt_guide_audit.jsonl` — the record of the 483/483-row independent audit. Retained PDFs live under `sources/trade_journal/endovascular-today/2026-08/`.

**Manufacturer catalogs** (`ingest_manufacturer_catalog.py`): one source + one `device_specifications` claim per product family, carrying every catalog number's printed fields with units and page locators. Jurisdiction-aware (international catalogs are flagged; US availability must be confirmed against labeling).

**IFUs** (`import_claim_drafts.py`): an independent agent reads the retained PDF and drafts claims with page locators and a verbatim anchor quote; the importer validates required fields, claim types, and a unique current IFU source per device, then appends at `official_labeling`/`source_checked`. Drafts that fail a page check are rejected, not fixed.

## Pilot

Neuroform Atlas Rev AB was the first migrated pilot. The official one-page US indications and safety document is retained with its SHA-256 hash. Claims are limited to the page's explicit indication, contraindication, sizing, foreshortening, adjunctive-device, and MR statements; it is not misrepresented as the complete package insert.
