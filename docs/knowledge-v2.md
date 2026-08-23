# Device Knowledge v2

`device_catalog` owns device source artifacts and claim review. `agent-textbooks` receives only the sanitized JSONL exchange under `exports/agent-textbooks/`.

## Trust model

- Existing `*-knowledge.md` prose is `legacy_derived_summary`: useful for discovery, but draft and unsupported until migrated claim by claim.
- Document status is independent of claim review: `current`, `historical`, `superseded`, `quarantined`, or `unavailable`.
- Claim support is `direct`, `adjacent`, `conflicting`, or `unsupported`.
- Review is `draft`, `source_checked`, `clinician_reviewed`, or `stale`.
- Compatibility is separately labeled as manufacturer-labeled, required, recommended, dimensional-only, reported off-label, or unknown.

The downstream export admits only direct, located, source-checked or clinician-reviewed claims tied to a current source whose full text was checked. Everything else fails closed.

## Workflow

```bash
python3 -m pipeline.run_knowledge_v2 official-scan
python3 -m pipeline.run_knowledge_v2 audit
python3 -m pipeline.run_knowledge_v2 export
```

The official scan is limited to configured FDA and manufacturer domains. It reports page availability, identity matches, hashes, and detected document identifiers. The audit reconciles the latest report: identity or pinned-hash mismatch quarantines a source, and a blocked/unavailable current source becomes unavailable until revalidated. A successful scan refreshes `checked_at` only when the official content matches the retained artifact. It never promotes a new source or claim automatically. Review `reviews/knowledge_v2/`, reopen the exact source, add only locatable claims to `pipeline/knowledge_v2/data/reviewed_claims.v2.jsonl`, then export again.

Both the historical flat layout and the relocated `pipeline/data/data_by_device/` layout are scanned. Divergent duplicate artifacts are quarantined rather than selected silently.

The initial neurovascular audit intentionally quarantines the misfiled ENTERPRISE document labeled as Onyx HD-500 and the plain Pipeline Flex document labeled as Pipeline Shield. Historical and superseded documents remain visible for version comparison.

## Pilot

Neuroform Atlas Rev AB is the first migrated pilot. The official one-page US indications and safety document is retained with its SHA-256 hash. Claims are limited to the page's explicit indication, contraindication, sizing, foreshortening, adjunctive-device, and MR statements; it is not misrepresented as the complete package insert.
