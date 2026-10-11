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

## Run record (2026-10-10, 18:00-21:45 CEST, M4 Pro 48 GB, other sessions active, 18-27 GB available at start)

Scripts in `dev/pdf_conversion_qa/`: `01` sample, `02` reference (pdftotext per page, eligibility, 5 sampled pages per whole document), `03_run_candidate.py` driven by `run_stage.sh <stage>` (`cheap`, `calibration`, `c1`, `c1panel`, `c2`, `c3`, `whole`), `04` metrics (csv), `05` report (`md/05_report.md`), `06` whole documents, `07` per-character diagnosis (`md/07_char_diagnosis.md`). Tests: `tests/test_metrics.py`. Results: `json/03_run_candidate.jsonl` (window rows), `json/06_run_whole_docs.jsonl`, `csv/04_metrics*.csv`.

### Environment fault and how it was handled

- MinerU 2.7.6 calls `huggingface_hub.snapshot_download` -> `model_info` against huggingface.co at the start of every conversion (`models_download_utils.auto_download_and_get_model_root_path`), although the model sits in `~/.cache/huggingface`. A conversion therefore needs the network, or it dies with `httpx.ProxyError`/connection errors and exit code 0 and no md. Observed: the first C1 sample run (online, through the session proxy `localhost:8083`) converted 9 windows, then the proxy answered 502 and the remaining 25 windows failed in 2.7 s each with `httpx.ProxyError: 502 Bad Gateway` (see `json/03_run_candidate_online_hf.jsonl`, 42 rows: the 8 valid online windows, 25 proxy failures, 9 calibration rows).
- Consequence: all valid MinerU rows were produced with `HF_HUB_OFFLINE=1` added to the MinerU env (`config.MINERU_ENV`, row field `hf_offline`). This is the only deviation from the `workflow.py` env. The rerun of C1 from scratch replaced the invalid online rows; these 25 windows were never converted, so rerunning them is not an added repetition. The 8 windows that had converted online also ran offline again and are the only paired online/offline observations (not analysed).
- Whether production on the user's terminal depends on the same network check was not tested (hypothesis: yes, offline machine means failure).

### Other harness defects found while running

- `os.killpg` raised `PermissionError` (EPERM) once, on an already exited group (C1 calibration rep 2). Now tolerated in `kill_group`; the row was rerun.
- `run_mineru` now clears the run's `out/` and `trace.jsonl` before starting so a stale md cannot count as a success.
- One surviving `mineru.cli.fast_api` after the C1 run on the first window (BasnerMcGuire); `teardown_fast_api` killed it. 0 survivors in all other MinerU runs.

### Measurement facts (rep 1 unless stated)

- Failures: none in 504 window rows (C1 42, C2 12, C3 42, C4/C5 102 each) and none in 84 whole-document runs. The two Ewert suspected crash windows (pages 441-448 and 367-374) converted fine with unpatched C1 (no UnicodeDecodeError in any log): the 2026-10-10 crash at item 6249 of 10 028 was not reproduced by windows, it needs the full document context. Therefore C2 was never needed as a rescue and ran only on the panel plus the calibration PDF; C1 and C2 md hashes are identical in all 12 compared runs (patch marker present in each C2 run).
- Stability panel (Coenenberg mid, Kelly 40-48, Welge early): 3 runs each for C1, C2, C3, one md hash per window and candidate. Speed instability: C2 Kelly rep 3 took 445.5 s against 157.2 s and 156.9 s for reps 1 and 2 with identical output (load 3.94, 23.6 GB available at start, min 18.7 GB): cause unexplained, no run added.
- Speed (pooled wall s/page, minus startup floor in brackets): C1 13.05 (10.96), C2 14.06 (11.48, 4 windows), C3 3.21 (1.42), C4a 0.235, C4b 0.392, C5a 0.014, C5b 0.112. Startup floors (median of 3 on 1 page): C1 14.5 s, C2 14.2 s, C3 12.4 s, C4a 0.40 s, C4b 0.45 s, C5a 0.08 s, C5b 0.69 s. Cheap candidates n=3 full passes differ by at most 8 % (C5b), 3-4 % for the others.
- C1 on formula windows: 20.5 s/page; Efron 10 pages took 313 s.
- Memory: C1 peak tree footprint 5.6 GB max, C2 5.5 GB, C3 median 4.2 GB but 18.0 GB (Efron, scanned JSTOR pages), 16.0 GB (Collins), 12.0 GB (Boatright) on 8-10 page scanned PDFs; C4/C5 under 1 GB on windows, under 1.9 GB on whole documents. Lowest system available RAM seen during MinerU runs: 10.2 GB (C2 panel rep 2, while the tree itself held 5.5 GB: other processes). The 30 GB / 5 GB guard never fired.
- Recall (character multiset against the pdftotext layer, eligible pages, text windows, pooled over 31 windows): C1 0.924, C3 0.924, C4a 0.879, C4b 0.942, C5a 0.971, C5b 0.972. Sample counts (reference): 941 special characters, 2 805 umlauts.
- Special characters: the low `recall special` of C1 (0.43) and C5 (0.10) is mainly typographic normalisation, not loss of text: both turn „ “ ” into ASCII `"` (checked on Pies et al.: `“ethical dilemma,”` becomes `"ethical dilemma,"`), and C5 also drops the en dash. Section sign and euro survive in C5 (85/85, 6/6), C1 keeps 77/85 §. C4a loses § (27/85) and about 10 % of umlauts because legacy mode emits U+FFFD (425 in 235 pages, 365 of them in the Kelly formula window). C4b keeps §, umlauts 99.9 %.
- Silent content loss with status ok (recall below 0.5): C4a on Boatright (0.11), Efron (0.08), both Grundei windows (0.02); C4b on Boatright (0.09) and Efron (0.06): pymupdf4llm ignores the OCR text layer of scanned JSTOR PDFs (md 3 058 characters where C5a returns 26 906) and legacy mode ignores the "Paper Capture" layer of Grundei; layout mode with OCR recovered Grundei (0.97-1.00) but not Boatright/Efron. C1 and C3 on Coenenberg mid (formula/table-heavy textbook pages): 0.45 / 0.46, identical md in three runs.
- Whole documents (21 PDFs, 5 130 pages, one run each): C4a 1 718.8 s (2.98 p/s; Grundei alone 1 295 s at 0.33 p/s), C4b 832.6 s (6.16 p/s), C5a 35.6 s (144 p/s), C5b 367.3 s (14 p/s). No failure, pages_out equal to the page count everywhere, peak footprint at most 1.9 GB. Sampled-page recall pooled: C4a 0.884, C4b 0.949, C5a 0.969, C5b 0.970. Weak documents: C4a Grundei 0.04, Boatright 0.17, Deitel 0.65; C5 Deitel 0.81 (code listings), Din5008 0.90, Kuepper 0.93.
- liteparse OCR (C5b) gave the same recall as C5a on every text-layer window and cost 8x the time (Coenenberg 125.7 s against 2.5 s). The sample contains no PDF without a text layer, so the only OCR check is the synthetic image-only page from the takeover (C4b 1 319 and C5b 1 440 of 1 568 characters).

### Caveats

- Recall is character-level against pdftotext: it cannot see reading order, table structure or headings, and it ignores added markup. MinerU writes formulas as LaTeX (formula windows out/ref length 1.35), so formula-window recall is indicative only.
- Whole-document recall uses only 5 evenly spaced eligible pages per PDF.
- The metrics, report and pytest runs overlapped the last three whole-document runs (WHO Night Noise C4b, C5a, C5b), a few seconds of single-core work.
- Cheap candidates read the PDFs in document order per PDF, so the first candidate (C4a) paid cold file cache on large files.
- `Tesseract` models: `deu` from tesseract-ocr/tessdata, `eng` from the system install.
