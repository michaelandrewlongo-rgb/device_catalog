# Skill Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the `pdf`, `read-file`, and `read-memories` skills into documented, repeatable workflows that make each skill useful on-demand during real catalog work.

**Architecture:** This plan produces three artifacts: (1) a DuckDB query library for auditing `pipeline/data/` JSON files via `read-file`, (2) a PDF extraction decision guide for choosing between `pdf` skill / pdfplumber / Marker+DeepSeek, and (3) CLAUDE.md updates that wire all three skills into the session start and gap-fill workflows. No new Python code. No new pipeline stages. These are documentation and convention changes only.

**Tech Stack:** DuckDB (via `read-file` skill), pypdf/pdfplumber (via `pdf` skill), Claude Code session logs (via `read-memories` skill), Markdown docs.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `docs/queries/pipeline-duckdb-queries.md` | Create | Library of DuckDB SQL queries for auditing pipeline JSON data |
| `docs/pdf-extraction-guide.md` | Create | Decision tree: when to use pdf skill vs. pdfplumber vs. Marker+DeepSeek |
| `CLAUDE.md` | Modify | Wire all three skills into session-start and gap-fill workflows |

---

## Task 1: DuckDB Query Library for Pipeline Data Auditing

**Purpose:** The `read-file` skill runs DuckDB SQL over local JSON files. The bottleneck is knowing *which queries to run*. This task creates a saved query library covering the five most common pipeline audit needs.

**Files:**
- Create: `docs/queries/pipeline-duckdb-queries.md`

- [ ] **Step 1: Create the docs/queries directory**

```bash
mkdir -p docs/queries
```

- [ ] **Step 2: Create the query library file**

Create `docs/queries/pipeline-duckdb-queries.md` with the following content:

````markdown
# Pipeline DuckDB Query Library

Use these queries with the `read-file` skill or directly via `duckdb :memory: -c "..."`.

All queries assume the working directory is the repo root.
Adjust glob paths if running from elsewhere.

---

## 1. Find all enriched devices missing a specific field

Finds enriched JSON records where `device_description` is null or empty.
Replace `device_description` with any top-level field name.

```sql
SELECT
  regexp_extract(filename, '[^/\\\\]+\.json$', 0) AS file,
  json_extract_string(content, '$.device_name') AS device_name,
  json_extract_string(content, '$.manufacturer') AS manufacturer
FROM (
  SELECT filename, content::VARCHAR AS content
  FROM read_ndjson_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
  UNION ALL
  SELECT filename, content::VARCHAR AS content
  FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
)
WHERE json_extract_string(content, '$.device_description') IS NULL
   OR length(json_extract_string(content, '$.device_description')) < 20
ORDER BY manufacturer, device_name;
```

---

## 2. Count [NEEDS CONTENT] gaps across all enriched records

Returns a count of enriched files that still contain placeholder text,
useful for tracking gap-fill progress.

```sql
SELECT
  count(*) AS files_with_gaps,
  count(*) FILTER (WHERE content ILIKE '%[NEEDS CONTENT%') AS gap_count
FROM read_json('pipeline/data/enriched/*.json', format='auto', ignore_errors=true);
```

---

## 3. Cross-device contamination audit

Detects enriched records where the `device_name` field does not share
any meaningful token with the filename stem (the contamination pattern
fixed in ac309a3 for gap_filler; the underlying merger.py issue remains).

```sql
WITH records AS (
  SELECT
    regexp_extract(filename, '[^/\\\\]+(?=\.json)', 0) AS stem,
    json_extract_string(content::VARCHAR, '$.device_name') AS device_name,
    json_extract_string(content::VARCHAR, '$.manufacturer') AS manufacturer
  FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
)
SELECT stem, device_name, manufacturer
FROM records
WHERE device_name IS NOT NULL
  AND NOT (
    lower(stem) ILIKE '%' || lower(split_part(device_name, ' ', 1)) || '%'
    OR lower(device_name) ILIKE '%' || split_part(lower(stem), '--', 3) || '%'
  )
ORDER BY stem;
```

---

## 4. Category coverage summary

Counts enriched records per category. Useful for spotting thin categories
before deciding what to scrape next.

```sql
SELECT
  regexp_extract(filename, '^([^-]+(?:-[^-]+)*?)--', 1) AS category,
  count(*) AS device_count
FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
GROUP BY category
ORDER BY device_count DESC;
```

> Note: The regex extracts the first `--`-delimited segment as the category.
> This matches the file naming convention `{category}--{manufacturer}--{product}--...`

---

## 5. Merged vs. enriched delta

Finds devices that have a merged record but no corresponding enriched record.
These are candidates for running `python -m pipeline.run_enrich`.

```sql
WITH merged AS (
  SELECT regexp_extract(filename, '[^/\\\\]+(?=\.json)', 0) AS stem
  FROM read_json_auto('pipeline/data/merged/*.json', filename=true, ignore_errors=true)
),
enriched AS (
  SELECT regexp_extract(filename, '[^/\\\\]+(?=\.json)', 0) AS stem
  FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
)
SELECT m.stem
FROM merged m
LEFT JOIN enriched e ON m.stem = e.stem
WHERE e.stem IS NULL
ORDER BY m.stem;
```

---

## Usage with read-file skill

Invoke the skill with any query file or inline SQL:

```
/read-file pipeline/data/enriched/aspiration--penumbra--penumbra-ace.json
```

For cross-file queries, paste the SQL block above directly into a prompt like:
"Run this DuckDB query over pipeline/data/enriched/"
````

- [ ] **Step 3: Verify the query library file was written**

```bash
ls -la docs/queries/pipeline-duckdb-queries.md
```

Expected: file exists, non-zero size.

- [ ] **Step 4: Smoke-test query #4 (category coverage) manually**

Run this to confirm DuckDB can actually read the enriched JSON files:

```bash
duckdb :memory: -c "
SELECT
  split_part(regexp_extract(filename, '[^/\\]+(?=\.json)', 0), '--', 1) AS category,
  count(*) AS cnt
FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
GROUP BY category
ORDER BY cnt DESC
LIMIT 10;
"
```

Expected: table output showing category names (aspiration, thrombectomy, etc.) with counts.
If DuckDB is not installed: `pip install duckdb` or `winget install DuckDB.cli`.

- [ ] **Step 5: Commit**

```bash
git add docs/queries/pipeline-duckdb-queries.md
git commit -m "docs: add DuckDB query library for pipeline data auditing (read-file skill)"
```

---

## Task 2: PDF Extraction Decision Guide

**Purpose:** The `pdf` skill (pypdf/pdfplumber) is fast and works in-session but produces lower-quality output than Marker+DeepSeek for complex tables. Without a decision tree, the temptation is to always use one or the other. This task creates a guide that specifies exactly when to use which tool.

**Files:**
- Create: `docs/pdf-extraction-guide.md`

- [ ] **Step 1: Create the PDF extraction guide**

Create `docs/pdf-extraction-guide.md` with the following content:

````markdown
# PDF Extraction Guide

When you have a device PDF (IFU, 510(k) summary, brochure, NSPR technique guide),
use this guide to choose the right extraction tool.

---

## Decision Tree

```
Is the PDF a simple text-based 510(k) summary (no complex tables)?
├── YES → Use pdfplumber (Tier 1A pipeline) or pdf skill for ad-hoc
└── NO
    └── Does it contain sizing tables, compatibility matrices, or multi-column layouts?
        ├── YES → Use Marker + DeepSeek (Tier 2 pipeline: run_extract --documents)
        └── NO (scanned image PDF)
            └── Use pdf skill with OCR: tesseract fallback via pytesseract
```

---

## Tool Profiles

### 1. `pdf` skill (pypdf / pdfplumber) — in-session, ad-hoc

**When:** Quick extraction of a single PDF in the current session.
Manufacturer brochures, simple IFUs, anything where you need one or two fields fast.

**Invoke:** Type `/pdf` then give the path:
```
/pdf pipeline/data/pdfs/aspiration--penumbra--penumbra-ace.json
Extract: device description, sizing table, indicated vessel diameters
```

**Limitations:**
- Poor on complex multi-column layouts or scanned pages
- No structured JSON output — returns text you then parse manually
- Snyk flags this as High Risk due to PDF parsing deps; use only on trusted catalog PDFs

**Best for:**
- Checking if a 510(k) summary mentions a specific spec
- Extracting one paragraph of text from an IFU
- Confirming a device name or clearance number

---

### 2. pdfplumber (Tier 1A pipeline)

**When:** Batch extraction of 510(k) summary PDFs already in `pipeline/data/pdfs/`.

**Invoke:**
```bash
PYTHONUTF8=1 python -m pipeline.run_extract --fda-summaries
```

**Output:** `pipeline/data/extracted/fda_summaries/*.json`

**Best for:** FDA regulatory metadata. Not suited for complex IFU tables.

---

### 3. Marker + DeepSeek (Tier 2 pipeline)

**When:** Manufacturer brochures, IFUs, and NSPR technique PDFs with complex tables,
multi-column layouts, or rich formatting. This is the highest-fidelity option.

**Invoke:**
```bash
PYTHONUTF8=1 python -m pipeline.run_extract --documents
```

**Output:** `pipeline/data/extracted/documents/*.json`

**Cost:** DeepSeek API call per page. Check `~/Desktop/master_env.txt` for `DEEPSEEK_API_KEY`.

**Best for:** Sizing tables, compatibility matrices, deployment step sequences, and
any content that pdfplumber produces garbled output for.

---

## In-Session PDF Workflow (using `pdf` skill)

For a device with a `[NEEDS CONTENT]` gap and a known PDF in `pipeline/data/pdfs/`:

1. Identify the gap:
   ```
   grep -r "\[NEEDS CONTENT" {device-knowledge-file}.md
   ```

2. Find the matching PDF:
   ```
   ls pipeline/data/pdfs/{device-stem}*
   ```

3. Extract with pdf skill:
   ```
   /pdf pipeline/data/pdfs/{device-stem}--510k.pdf
   Extract the following fields: device description, sizes available,
   indicated vessels, compatible guide catheter inner diameter
   ```

4. Copy relevant content into the knowledge file under the appropriate section.

5. Mark the gap resolved by replacing `[NEEDS CONTENT - ...]` with the extracted text.

---

## When NOT to use the pdf skill

- Do not use it for batch processing — use the pipeline (`run_extract`) instead
- Do not use it to replace Tier 2 extraction for complex IFUs — Marker quality is higher
- Do not use it on scanned PDFs without confirming OCR output is readable first
````

- [ ] **Step 2: Verify the file was written**

```bash
ls -la docs/pdf-extraction-guide.md
```

Expected: file exists, non-zero size.

- [ ] **Step 3: Commit**

```bash
git add docs/pdf-extraction-guide.md
git commit -m "docs: add PDF extraction decision guide (pdf skill integration)"
```

---

## Task 3: Wire All Three Skills into CLAUDE.md

**Purpose:** The skills are only useful if there's a documented convention for when to reach for them. This task adds two sections to CLAUDE.md: a session-start checklist that includes `read-memories`, and a gap-fill workflow section that references the `pdf` skill and DuckDB query library.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Read the current CLAUDE.md**

Read `CLAUDE.md` to confirm the exact text near the "Core Working Rule" and "Before Making Changes" sections, so the edits below can be applied precisely.

- [ ] **Step 2: Add the Skills section to CLAUDE.md**

Find the section that begins `## Core Working Rule` and insert the following block **after** the `## Required Session Files` section (after the `MEMORY.md` entry and before `## Repository Purpose and Non-Goals`):

```markdown
## Installed Skills

Three skills are active in this project. Use them instead of writing one-off scripts for these tasks:

### `pdf` skill — in-session PDF extraction
- Invoke: `/pdf <path-to-pdf>`
- Use for: extracting content from a single catalog PDF to fill a [NEEDS CONTENT] gap
- When to use Marker instead: complex sizing tables, multi-column IFU layouts
- Full decision tree: `docs/pdf-extraction-guide.md`

### `read-file` skill — SQL over pipeline JSON
- Invoke: `/read-file <path> [question]`
- Use for: auditing pipeline/data/ files — finding gaps, checking contamination, profiling coverage
- Pre-written queries: `docs/queries/pipeline-duckdb-queries.md`
- Example: "How many enriched files are missing device_description?" → run Query #1 from the library

### `read-memories` skill — session context recovery
- Invoke: `/read-memories <keyword>`
- Use for: recovering prior decisions about a device, pipeline stage, or known bug
- Run at session start when STATE.md is stale or ambiguous
- Example: `/read-memories merger contamination` → surfaces the ac309a3 fix discussion
- Scope to this project: `/read-memories <keyword> --here`
```

- [ ] **Step 3: Add skill invocation to the session-start checklist**

Find the `## Core Working Rule` section:

```markdown
## Core Working Rule

The repo must remain understandable after context loss.

That means:
1. Read `STATE.md` first at the start of every session.
```

Replace with:

```markdown
## Core Working Rule

The repo must remain understandable after context loss.

That means:
1. Read `STATE.md` first at the start of every session.
2. If `STATE.md` is missing or stale, run `/read-memories <last-topic> --here` to recover context from session logs before making changes.
3. Update `STATE.md` at the end of any meaningful work session.
4. Do not rely on chat history as the only source of project memory.
```

(This replaces the existing numbered list; the original items 2-4 become 3-4 with item 2 inserted.)

- [ ] **Step 4: Verify the CLAUDE.md edit looks correct**

Read the modified sections of CLAUDE.md and confirm:
- "Installed Skills" section appears between "Required Session Files" and "Repository Purpose and Non-Goals"
- Item 2 in the Core Working Rule checklist references `read-memories`
- No duplicate sections, no broken markdown

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: wire pdf, read-file, read-memories skills into CLAUDE.md session workflow"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task covering it |
|---|---|
| Integrate `pdf` skill | Task 2 (decision guide), Task 3 (CLAUDE.md wiring) |
| Integrate `read-file` skill | Task 1 (query library), Task 3 (CLAUDE.md wiring) |
| Integrate `read-memories` skill | Task 3 (CLAUDE.md wiring, session-start protocol) |
| Make skills discoverable in future sessions | Task 3 (CLAUDE.md) |
| Concrete usage patterns, not generic docs | Task 1 (5 real queries), Task 2 (step-by-step workflow) |

**Placeholder scan:** No TBDs, no "implement later", no "appropriate error handling". All code blocks contain real SQL or real CLI commands.

**Type consistency:** No shared types across tasks — each task is self-contained documentation.

**Known gaps addressed:**
- merger.py fuzzy matching root cause (threshold 0.4) is noted in Query #3 but not fixed here — fixing it is a separate Python task in the pipeline, not a skill integration task.
- Firecrawl API key requirement is moot — those skills were removed.
