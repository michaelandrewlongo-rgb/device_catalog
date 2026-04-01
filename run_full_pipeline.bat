@echo off
REM Full extraction + post-processing pipeline
REM Run this in a terminal: run_full_pipeline.bat
REM Takes 3-7 hours for 84 NSPR PDFs

set PYTHONUTF8=1

echo === Step 1: Tier 2 Document Extraction (catalog + NSPR PDFs) ===
echo Started: %date% %time%
python -m pipeline.run_extract --documents
echo Finished extraction: %date% %time%

echo === Step 2: Post-Extraction Pipeline ===
python -m pipeline.run_post_extract
echo Finished post-extract: %date% %time%

echo === DONE ===
echo %date% %time%
pause
