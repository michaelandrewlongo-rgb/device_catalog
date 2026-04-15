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
/pdf pipeline/data/pdfs/aspiration--penumbra--penumbra-ace--510k.pdf
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
   grep -r "\[NEEDS CONTENT" <device-knowledge-file>.md
   ```

2. Find the matching PDF:
   ```
   ls pipeline/data/pdfs/<device-stem>*
   ```

3. Extract with pdf skill:
   ```
   /pdf pipeline/data/pdfs/<device-stem>--510k.pdf
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
