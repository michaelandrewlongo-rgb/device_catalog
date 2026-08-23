# Device Knowledge v2

This package creates a fail-closed interface between `device_catalog` and clinical decision-support consumers such as `agent-textbooks`.

`*-knowledge.md` files are treated as legacy model-derived summaries until individual claims are source-checked. They remain useful for discovery, but they are not exported as authoritative facts.

Run:

```bash
python -m pipeline.run_knowledge_v2 audit
python -m pipeline.run_knowledge_v2 export
```

The audit hashes registered source PDFs, verifies document identity when PDF text extraction is available, inventories high-risk neurovascular summaries, and emits review artifacts under `reviews/knowledge_v2/`. The export admits only directly supported, source-checked claims whose sources are current and available as verified full text. Historical, superseded, quarantined, metadata-only, adjacent, unsupported, draft, and stale evidence is rejected.

Add reviewed claims to `data/reviewed_claims.v2.jsonl` only after reopening the exact source and recording a page, table, section, or paragraph locator. `clinician_reviewed` is distinct from `source_checked`; neither status should be inferred from the age or polish of existing prose.
