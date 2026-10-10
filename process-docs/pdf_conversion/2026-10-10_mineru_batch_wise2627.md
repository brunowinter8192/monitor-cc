# 2026-10-10 — MinerU batch of 11 study PDFs: slow, one crash, nothing delivered yet

Observed run, written down for the session that fixes PDF conversion. Nothing was changed in the Mineru repo on this day. The user's verdict: "ultra lahm, null reliable, unfassbar schlecht".

## The run

- Repo: `~/Documents/ai/Mineru` (`workflow.py convert`), MinerU 2.7.6, mlx_vlm 0.3.12, backend `vlm-auto-engine` (mlx). Job slug `2026-10-10T13-05-07-88155100-00` (15:05 CEST).
- Input: 11 PDFs from `~/Documents/ai/Meta/ClaudeCode/cli/rag-cli/data/pdf/wise2627/`, output dir `…/rag-cli/data/documents/wise2627-reference/`. Order and size: six journal articles (10, 5, 8, 6, 28, 20 pages), then EwertWagenhoferRohlfingBastianInterneUnternehmensrechnung_2023 (734 pages), CoenenbergKostenrechnungKostenanalyse_2016 (993), KuepperControlling_2024 (658), WelgeEulerichCorporateGovernanceManagement_2021 (379), GrundeiZaumseilAufsichtsratCorporateGovernance_2012 (433, 454 MB).
- Console log: `/tmp/wise2627_mineru.log` (tee of the user's terminal).

## Timeline from the log

| Time (CEST) | Event |
|---|---|
| 15:05–15:20 | The six articles: each shows two `Predict` passes reaching 100 % (e.g. 10 pages in 00:41, then 114 items in 00:59). About 15 minutes for 77 pages. |
| 15:20 | Ewert starts. First pass `Predict 734/734` in 53:22, i.e. 4.36 s per page. |
| ~16:13–17:11 | Second pass of Ewert, 10 028 items, reached 6 249 (62 %) after 58:01, about 1.8 it/s. |
| 17:11:45 | Crash: `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x9d in position 4: invalid start byte` in `mlx_vlm/tokenizer_utils.py` line 232, `BPEStreamingDetokenizer.add_token`, called from `mlx_vlm/generate.py` `stream_generate`. |
| 17:11:49 | `[continue-on-failure]`: Coenenberg starts. The first 21 pages slow from 3.4 s to 8 s per page (estimate shown by tqdm rises from 55 min to 2 h 9 min). |

About 1 h 51 min of compute on Ewert produced nothing.

## Two separate problems

**1. Known crash class, deterministic.** The Mineru repo already documents this exact failure in `decisions/OldThemes/vlm_detokenizer_utf8_crash_2026-07-04.md`: mlx_vlm 0.3.12 decodes each token's bytes as UTF-8 immediately, so a multi-byte character split across BPE tokens raises on a continuation byte (there `0x83` on SPO_MScBWL_2024.pdf, here `0x9d` on Ewert). Greedy decoding makes it deterministic: re-running Ewert will crash at the same token. The note says mlx_vlm is pinned on purpose and that `vlm-auto-engine` is the only backend that loads in this venv. Its applied workaround for born-digital PDFs: skip MinerU, extract text with PyMuPDF.

**2. Results are only delivered at the very end of the batch.** `workflow.py` writes every PDF's output into one `/tmp/mineru_whole_*` directory and copies the `.md` files to the output dir only in `_collect_and_log()` after the last PDF; the `finally` block then deletes the temp directory. Consequence observed: at 17:14 the output dir still held only an old file from 04.10., although the six articles had finished before 15:20. If the run is interrupted before the end, every finished conversion is lost with it. (Whether the six article outputs still sit in the temp dir at that moment could not be checked from the agent shell; the glob on `/tmp/mineru_whole_*` returned nothing there. Hypothesis: sandbox visibility.)

## Facts that matter for the fix

- At least Bosch-Badia 2013, Friedman 1970, Coenenberg 9th ed., Küpper, Welge/Eulerich and Grundei/Zaumseil contain selectable text (pdftotext returned real text from their first pages on 10.10.2026). For these, the PyMuPDF route from the 07-04 note applies. Ewert was not checked.
- Throughput on this Mac (M4 Pro, 48 GB): roughly 4–8 s per page in the first pass alone, plus a second pass; a 700–1000 page textbook takes several hours.
- `PDF_RENDER_THREADS = 1` and the memory watchdog are earlier fixes in the same repo (see its DOCS.md); they were not involved here.

## Open (not handled in this session)

- Decide per PDF: PyMuPDF for born-digital, MinerU only where layout or scans need it.
- Copy each finished `.md` to the output dir right after its PDF, not at batch end.
- The UTF-8 detokenizer crash: either an mlx_vlm version that buffers incomplete UTF-8, or a guarded decode, or a different backend; the 07-04 note lists why each is blocked.
- The batch was still running on Coenenberg when this was written; its outcome is unknown.
