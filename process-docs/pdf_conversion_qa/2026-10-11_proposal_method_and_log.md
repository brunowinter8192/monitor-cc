# 2026-10-11 — Proposal: conversion method and conversion log

Orchestrator proposal at the end of cycle "PDF conversion QA". Evidence: the gap analysis and the M1 measurement record in this area, report `dev/pdf_conversion_qa/md/05_report.md`. Nothing is rebuilt yet; the rebuild is the next cycle.

## Measured basis (M1, 2026-10-10/11, MacBook Pro M4 Pro 48 GB, 17–22 GB available during runs)

34 windows (235 pages) from all 21 wise2627 PDFs plus formula-dense trading papers; 504 window runs, 84 whole-document runs (21 PDFs, 5 130 pages, cheap candidates only). No candidate failed anywhere; the memory guard never fired.

| Candidate | s/page (windows) | Peak memory | Text recall vs pdftotext | Whole 21 PDFs |
|---|---|---|---|---|
| MinerU vlm-auto-engine (today) | 13.05 | 5.6 GB | 0.924 | not run (≈ 20 h estimated) |
| MinerU pipeline `-f false` | 3.21 | 18.0 GB on 8–10 scanned pages | 0.924 | not run |
| pymupdf4llm legacy | 0.235 | 0.44 GB | 0.879, near-empty output on OCR-layer PDFs | 1 719 s |
| pymupdf4llm layout + OCR | 0.392 | 0.69 GB | 0.942 | 833 s |
| liteparse, no OCR | 0.014 | 0.01 GB (1.19 GB whole docs) | 0.971 | 36 s |
| liteparse + Tesseract | 0.112 | 0.91 GB | 0.972 | 367 s |

Observed weaknesses that shape the proposal:
- liteparse writes straight quotes and drops the en dash (special-character recall 0.10); umlauts 0.985. Cosmetic for RAG. No LaTeX: formulas arrive as plain text (formula-window recall 0.97 as characters).
- pymupdf4llm returns status ok with near-empty md on PDFs that carry an OCR text layer (Boatright, Efron, Grundei; recall 0.02–0.11). Exit status and file existence are therefore not proof of success for any converter.
- MinerU contacts huggingface.co at every start although the model is cached; a proxy 502 made 25 windows fail in 2.7 s each with exit 0 and no md. MinerU 2.7.6 exits 0 on every failure.
- The 2026-10-10 detokenizer crash on Ewert did not reproduce on windows; it needs the full document. The one-line patch is proven (unpatched raises, patched decodes with U+FFFD, outputs bit-identical where no crash).

## Proposal 1 — method

**Default for every PDF: liteparse without OCR, Markdown output.** Reason: fastest by two orders of magnitude (144 pages/s on whole documents, all 21 wise2627 PDFs in 36 s), best text recall (0.971), memory at most 1.2 GB, Apache-2.0, and a worker-pool mode with hard per-parse timeouts. A crash risk of the kind seen with MinerU (model memory, detokenizer) does not exist in this path because no model runs.

**Content check after every conversion (tripwire):** characters per page of the output against the `pdftotext` layer of the same PDF. Below a threshold the run is a failure, logged as such, never a silent "ok". Threshold to be set from the M1 data during the rebuild.

**No OCR path and no MinerU fallback now.** No PDF without a text layer was observed in the sample (Grundei has an OCR layer and converts with liteparse). A PDF that fails the content check stops with an error and lands in the log; the cause is investigated then. This follows the fallback rule: a second path only for an observed condition.

**MinerU stays installed but leaves the default path.** If formula-exact LaTeX is ever needed for a specific paper, MinerU can be called explicitly. Not part of the rebuild.

**Cleanup:** stays with a Claude agent via the `websearch-pdf` skill. The skill's classes were written for MinerU output; liteparse output mainly needs class H (240 bare-fence/separator lines per 235 pages) and long-line handling J. The skill needs an update for liteparse output; skills are user-owned, so that is a proposal (patch) during the rebuild.

## Proposal 2 — conversion log

Pattern: websearch `scrape_log.jsonl` (one record per call, config fingerprint, sidecar). One append-only file `logs/conversions.jsonl` in the converter repo, never pruned by the janitor.

Two records per PDF attempt, linked by `run_id`:
- **start** (written before converting): `run_id`, `ts_start`, `pdf` path, `pdf_sha256`, `pages`, `converter`, `converter_version`, `config_hash`, `config`, `attempt` (count of earlier attempts on the same sha256).
- **end** (written after): `run_id`, `ts_end`, `outcome` (`ok` / `failed` / `content_check_failed`), `failure_class`, `wall_s`, `s_per_page`, `peak_mem_gb`, `min_available_gb`, `chars_out`, `chars_ref`, `char_ratio`, `md` path, `stderr_path` (sidecar with the tail of stderr on failure).

A start without an end means the process died (crash, kill, reboot) and is counted as such. Rows are written per PDF immediately, so a batch interrupted after 6 of 11 PDFs keeps 6 complete pairs.

A `stats` subcommand answers the user's questions from this file only: conversions all time or since a date, per `config_hash` (current production config = latest hash), failures by `failure_class`, unfinished starts, mean pages and mean duration.

The old `logs/jobs.jsonl` stays as it is; it has no config field and loses failed time, so it is not merged into the new statistics.

## Next cycle (setup)

Rebuild the converter repo (`~/Documents/ai/Mineru`) around liteparse plus the content check plus the new log, write the output `.md` per PDF immediately, then run the skills `iterative-dev-refactor` and `iterative-dev-doccheck` on that repo, then convert and index the wise2627 PDFs.
