# 2026-10-10 - PDF conversion QA, milestone M1 (measurements), takeover worker

Second worker of M1 (the first died of context exhaustion). Harness lives in `dev/pdf_conversion_qa/`.

## Takeover verification (2026-10-10)

- Gitignored folders `venv/ tessdata/ samples/ runs/ traces/` do not travel with the merge. Rebuild: `uv venv --python 3.12 venv`, `uv pip install --python venv/bin/python pymupdf4llm pymupdf-layout liteparse psutil pytest`, copy `eng`/`osd` traineddata from `/opt/homebrew/share/tessdata` plus `deu.traineddata` from github.com/tesseract-ocr/tessdata into `tessdata/`, then `PYTHONPATH=<worktree> venv/bin/python 01_build_sample.py` (4 s, 34 windows, 235 pages; manifest identical to the previous one except the absolute `slice_pdf` paths and two slice sizes differing by 2 bytes).
- Run all dev scripts with the dev venv python and `PYTHONPATH` set to the worktree root (imports are `dev.pdf_conversion_qa...`).
- Smoke on the 1-page window `TelekomPibMagentaZuhauseL_p0001-0001`: C1 14.8 s (peak 4.65 GB), C2 14.1 s (patch marker written by 1 pid), C3 29.3 s (peak 3.6 GB, pipeline with `-f false` loads and converts in the mlx venv), C4a 0.7 s, C4b 0.4 s, C5a 0.08 s, C5b 0.7 s. No surviving `mineru.cli.fast_api` after any MinerU run.
- OCR paths verified on an image-only rasterised German textbook page (Coenenberg, 200 dpi): C4b logs "Using Tesseract" and returns 1319 chars, C5b returns 1440 chars, reference text layer 1568 chars. Both pick up `TESSDATA_PREFIX`/`tessdata_path` with `deu`.
- C4b is layout mode because `pymupdf-layout` is installed (`pymupdf4llm` activates it on import); C4a calls `use_layout(False)`.

## Defect found and fixed in the harness

The memory probe slept one interval before its first sample, so any run shorter than one second reported peak 0 and no available-RAM minimum (all four cheap candidates on the 1-page window). The probe now samples first, then waits; cheap candidates sample every 0.2 s (MinerU stays at 1 s / footprint every 3 s as in `mem_watchdog.py`). The cheap worker additionally reports `ru_maxrss` of itself and of its children as a cross-check.
