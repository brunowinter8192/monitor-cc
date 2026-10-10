# 2026-10-10 — PDF conversion QA: gap analysis for a converter choice and a conversion log

## Cycle goal (set by the user)

Deliver a justified proposal, nothing rebuilt yet:
1. How conversion runs are logged, so that "how many conversions ran (all time / last months / in the current production config), how many failed and why, pages and duration on average" is answered with numbers straight from the log.
2. Which conversion method is used in future, and why.

User priorities: a crash is unacceptable ("ein Absturz ist schon armageddon"); reliability and speed first; lower initial conversion quality is acceptable. Cleanup stays with a Claude agent as in the `websearch-pdf` skill today (user chose option 1 over a local LLM cleanup on 2026-10-10). Experiments on the PDFs in `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf/wise2627/`. The Mineru repo is not rebuilt in this cycle; the skills `iterative-dev-refactor` and `iterative-dev-doccheck` run on the Mineru repo only after a later rebuild.

Builds on area pdf_conversion (wise2627 run of 2026-10-10) in this project and on areas pdf_pipeline (cleanup classes) and logging in the websearch project.

## Gap process

The orchestrator named six gaps, checked them against RAG, then a fresh worker (`pdfgaps`) got the full state and named its own gaps first (28, without seeing the orchestrator's), then judged the orchestrator's six. Merged result: 16 gaps. The worker contributed two points the orchestrator lacked: for born-digital PDFs the text layer is a quasi ground truth for character content, and the sample must include formula-dense English trading papers, because the June memory failures came from those and not from German business texts.

## Facts found by the gaps worker (local, read-only)

- `~/Documents/ai/Mineru/logs/jobs.jsonl`, 1027 lines, five mixed schemas, no backend/version/config field. Since the hard-wiring of `vlm-auto-engine` (commit `e04eca9`, 2026-06-24): 156 per-PDF rows, 119 with an md, 7 295 pages in successful rows.
- When `_run_mineru` raises, `total_wall_s += ...` never runs: 13 job summaries show `total_wall_s` 0.0; the 1 h 51 min spent on Ewert on 2026-10-10 is invisible. The 2026-10-10 run has no row at all (rows are written at job end only).
- Deitel (887 pages) failed 6 times, mempressure peaks 18–22 GB, reason not logged. Shefrin (520 pages) failed 5 times, then succeeded on 2026-10-04 with the same code: success depends on machine state. The 2026-10-04 run touched 4.94 GB available, right at the 5 GB floor.
- wise2627 holds 21 PDFs. All have a text layer except possibly the two 1–2 page Telekom PDFs. Grundei is 449 MB for 433 pages, producer "Acrobat 9.44 Paper Capture" (an OCR layer). WHO Night Noise is RC4-encrypted (pypdf counts pages fine).

## Gaps closed by external sources (2026-10-10)

| Gap | Result | Source |
|---|---|---|
| C4 mlx_vlm detokenizer crash | Fixed upstream in mlx-vlm commit `3cf2e75` "fix bpe detokenizer utf8 flush", 2026-07-24, first tag v0.6.9: one line, `decode("utf-8")` → `decode("utf-8", errors="replace")` in `BPEStreamingDetokenizer.add_token`. Installed: mlx-vlm 0.3.12. mineru 2.7.6 and mineru_vl_utils 0.2.8 both require `mlx-vlm<0.4`, so the upgrade is blocked by the pin; the one-line change could be applied locally. MinerU issue #3985 (same traceback, mlx engine) was closed without a fix ("unable to reproduce"). | GitHub source and git history of Blaizzy/mlx-vlm; installed METADATA |
| C5 MinerU pipeline without formula model | The installed 2.7.6 CLI has `-f/--formula BOOLEAN` and `-s/--start`, `-e/--end` (page range, 0-based); env `MINERU_FORMULA_ENABLE`. Whether `pipeline` loads in the mlx venv with `-f false` (the transformers conflict came from the formula model) is untested. | `mineru --help` in the venv; mineru-reference collection |
| C1 converter landscape 2026 | Active repos (push within days): docling, marker, pymupdf4llm, MinerU, xberg (formerly kreuzberg). Stale since March 2026: olmocr, dots.ocr. New since June: run-llama/liteparse (12.8k stars, Apache-2.0, PDFium, ~2–5 ms/page, worker pool with hard per-parse timeouts, Tesseract OCR). | gh-cli search_repos, repo_freshness, README |
| C6 quality comparison without own ground truth | ParseBench (run-llama, arXiv 2604.08538, ~2 000 human-verified enterprise pages). Leaderboard rows relevant here, Content Faithfulness / Overall: PyMuPDF4LLM local 79.34 / 53.49; MinerU2.5-2509-1.2B (our current model) 80.8 / 45.9; MinerU2.5-Pro-2605-1.2B 87.88 / 72.78; PaddleOCR-VL-1.6 82.71 / 67.43; Docling-models 66.93 / 50.65; LiteParse no OCR 70.0 / 36.9; PyMuPDF plain text 68.28 / 16.02; MarkItDown 64.54 / 18.63. Marker is only listed as the Datalab API. Caveat: English enterprise documents, not German textbooks. | ParseBench README, leaderboard.csv, docs/pipelines.md |
| C3 text layer vs OCR per page | pymupdf4llm decides per page: OCR only for pages without text, with too many illegible characters (U+FFFD), with vector graphics that imitate text, or with images containing text; an existing OCR layer can be accepted instead of re-OCRed; `pages=` processes a subset; Tesseract or rapidocr. License AGPL. | pymupdf4llm README |
| L1 MinerU exit code | `mineru/cli/client.py` 2.7.6 wraps `do_parse` in `except Exception as e: logger.exception(e)` and returns normally: a failed conversion exits 0. Failure is only visible as a missing md plus the traceback on stderr. | installed source |
| C10 cloud option | Mistral OCR 4: $4 per 1 000 pages, $2 with batch API; max upload 512 MB; uploaded files retained 30 days. | docs.mistral.ai, mistral.ai/news/ocr-4 (via websearch) |
| C8 macOS memory kill | No fixed GB threshold: XNU compresses, then swaps, then jetsam kills lowest-priority processes when free memory falls below a band threshold. Whether the 5 GB floor is safe can only be measured; the question disappears for a converter with a small memory footprint. | macinternals.app "memory pressure on macOS" |
| L6 logging convention | websearch `scrape_log.jsonl`: one JSONL record per call with `ts`, `timings_ms`, error fields, `config_hash` plus full `config`, and `content_path` to a sidecar file with the returned content. | local websearch logs |

## Gaps that remain for experiments (Phase 2)

- C2 how each candidate fails on this Mac and whether it runs per page range with resume.
- C7 speed per candidate on the same machine state.
- C9 sample includes formula-dense English trading papers next to wise2627.
- C5 whether MinerU `pipeline -f false` loads and stays in bounded memory.
- L2–L5 log design questions (config fingerprint, start/end record per PDF, machine-state fields, attempts vs PDFs) are settled in the logging proposal itself.

No literature gap: OmniDocBench and ParseBench publish their metric code on GitHub.
