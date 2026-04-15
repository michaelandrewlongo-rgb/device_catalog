# Pipeline DuckDB Query Library

Use these queries with the `read-file` skill or directly via `duckdb :memory: -c "..."`.

All queries assume the working directory is the repo root.
Adjust glob paths if running from elsewhere.

**Windows compatibility notes:**
- DuckDB's regex engine does not support lookahead (`(?=...)`). Queries below use `replace(..., '.json', '')` instead.
- On Windows, `filename` values use backslash separators. Queries below account for this with an extra `split_part(..., '\\', -1)` to isolate the bare filename before parsing.
- The `[^/\\]` character class in regex requires escaping only one backslash in SQL string literals; in Python `duckdb.sql()` use raw strings to avoid SyntaxWarning.
- JSON files on Windows have CRLF line endings. Use `decode(content)` (not `content::VARCHAR`) when calling `read_blob` -- `decode` handles the byte-to-text conversion correctly so DuckDB's JSON functions can parse the result.

---

## 1. Find all enriched devices missing a specific field

Finds enriched JSON records where `what_it_is` is null or empty.
Replace `what_it_is` with any top-level field name.

```sql
SELECT
  split_part(replace(regexp_extract(filename, '[^/]+\.json', 0), '.json', ''), '\', -1) AS file,
  json_extract_string(decode(content), '$.device_name') AS device_name,
  json_extract_string(decode(content), '$.manufacturer') AS manufacturer
FROM read_blob('pipeline/data/enriched/*.json')
WHERE json_extract_string(decode(content), '$.what_it_is') IS NULL
   OR length(json_extract_string(decode(content), '$.what_it_is')) < 20
ORDER BY manufacturer, device_name;
```

---

## 2. Count [NEEDS CONTENT] gaps across all enriched records

Returns a count of enriched files that still contain placeholder text,
useful for tracking gap-fill progress.

```sql
SELECT
  count(*) AS files_with_gaps,
  count(*) FILTER (WHERE decode(content) ILIKE '%[NEEDS CONTENT%') AS gap_count
FROM read_blob('pipeline/data/enriched/*.json');
```

---

## 3. Cross-device contamination audit

Detects enriched records where the `device_name` field does not share
any meaningful token with the filename stem (the contamination pattern
fixed in ac309a3 for gap_filler; the underlying merger.py issue remains).

```sql
WITH records AS (
  SELECT
    split_part(replace(regexp_extract(filename, '[^/]+\.json'), '.json', ''), '\', -1) AS stem,
    json_extract_string(decode(content), '$.device_name') AS device_name,
    json_extract_string(decode(content), '$.manufacturer') AS manufacturer
  FROM read_blob('pipeline/data/enriched/*.json')
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
  split_part(
    split_part(replace(regexp_extract(filename, '[^/]+\.json'), '.json', ''), '\', -1),
    '--', 1
  ) AS category,
  count(*) AS device_count
FROM read_json_auto('pipeline/data/enriched/*.json', filename=true, ignore_errors=true)
GROUP BY category
ORDER BY device_count DESC;
```

> Note: The inner split_part strips the Windows path prefix (backslash-separated).
> The outer split_part extracts the first `--`-delimited segment as the category.
> This matches the file naming convention `{category}--{manufacturer}--{product}--...`
> Smoke-tested 2026-04-15: returns correct category rows (pedicle-screw: 741, interbody-cage: 605, etc.).

---

## 5. Merged vs. enriched delta

Finds devices that have a merged record but no corresponding enriched record.
These are candidates for running `python -m pipeline.run_enrich`.

```sql
WITH merged AS (
  SELECT split_part(replace(regexp_extract(filename, '[^/]+\.json'), '.json', ''), '\', -1) AS stem
  FROM read_json_auto('pipeline/data/merged/*.json', filename=true, ignore_errors=true)
),
enriched AS (
  SELECT split_part(replace(regexp_extract(filename, '[^/]+\.json'), '.json', ''), '\', -1) AS stem
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
