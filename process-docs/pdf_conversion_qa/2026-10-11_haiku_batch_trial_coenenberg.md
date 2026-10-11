# 2026-10-11 — Trial: liteparse anchor + Haiku workers per 20-page batch on Coenenberg

Follows the proposal of the same day in this area. The user replaced "script marks pages that need repair, a strong model repairs them" with: split the PDF into 20-page batches and let cheap Haiku workers transcribe every batch, normal workers stay Sonnet, Haiku also with 1M context. Cleanup stays with Claude (the user's option 1), now done by Haiku per batch.

## Setup that made Haiku workers possible without touching the global config

- `worker-cli spawn` reads the worker model from `~/.claude/shared-rules/model_selection.json`, but `src/spawn/spawn.py` (iterative-dev) honours the env var `MODEL_SELECTION_FILE`. A per-flow file `/tmp/coka/pdf_models.json` with `{"worker": "claude-haiku-5-5[1m]"}` plus `MODEL_SELECTION_FILE=<that file> worker-cli spawn ...` spawned Haiku workers; tmux showed `WORKER_MODEL=claude-haiku-5-5[1m]`; all 50 transcripts record model `claude-haiku-5-5`.
- `proxy_rules.json` got a `claude-haiku-5-5` model_params entry (effort medium, 64000 max tokens, adaptive thinking).
- `worker-cli spawn --no-worktree` is blocked by a hook; every Haiku worker got a monitor-cc worktree (seconds each).
- `WORKER_NO_VIEWER=1` suppresses the Ghostty viewer window; used after the user was disrupted by windows popping to the front (see "Viewer windows" below).
- The proxy already drops all shared rules for model family `haiku` (`src/proxy/rules_config.py`, `_load_system2_rules`). Measured first-request context of every Haiku worker: about 1 745 tokens. An earlier orchestrator estimate of "25 000 tokens of rules" was wrong.

## Per-batch flow used

1. `lit parse <pdf> --format markdown --no-ocr --target-pages "a-b" -o anchor_a-b.md` (liteparse 1.x from the M1 dev venv). Pages separated by `---`. Gotcha: `lit parse` has `--max-pages` default 1000; longer books need it raised.
2. One Haiku worker per batch with a prompt: read the anchor completely, read PDF pages a-b with the Read tool (images), write `batch_a-b.md`; anchor = source of truth for characters, images = structure; `<!-- page N -->` marker per page; headings, pipe tables, LaTeX formulas, typographic characters; drop running headers/footers/page numbers/TOC leaders/image placeholders, keep captions.
3. A bash driver in `/tmp/coka` spawned up to N workers, polled `worker-cli status`, killed a worker once idle with its file present, started the next. N was 6, then 20 after the user asked for more parallelism.
4. Assembly in page order and a per-batch content check: alphanumeric multiset recall of the batch output against `pdftotext -f a -l b`.

## Results (Coenenberg Kostenrechnung/Kostenanalyse 2016, 993 pages, 50 batches)

- Smoke batch 101–120: about 4 min, recall 0.99, length ratio 0.993; clean headings, nested lists, bold.
- Full run: 50/50 batches, no failure, about 37 min wall with 6 and later 20 parallel workers. Output `/tmp/coka/CoenenbergKostenrechnungKostenanalyse_2016.md`, 2.19 MB, 992 page markers (batch 661–680 has 19). Not copied to a collection, not indexed.
- Per-batch recall: median 0.979, minimum 0.885 (841–860). Part of the gap is intended (headers, page numbers removed). The 841–860 gap is diagrams with labelled boxes (e.g. Abb. 19-10 ZVEI-Kennzahlensystem): the prompt said "drop image placeholders", so box labels were dropped. Fix for the next version: the prompt asks for a text description of every figure (what is shown, labels, relations, numbers) — a gain over MinerU, which only emits image placeholders.
- Context per Haiku worker (from Claude Code transcripts under `~/.claude/projects/*worktrees-coka-*`): peak median 104 142, min 83 154, max 181 439 tokens; roughly 5 000 tokens per page (anchor text + page image). All stayed below 200k, so this run does not show whether `[1m]` takes effect for Haiku.
- Memory: 6 Haiku workers ≈ 3.5 GB for the worker processes plus their per-worker proxies; about 0.8 GB per worker. With ~21 GB available, 20 parallel was the chosen ceiling; all 50 at once (~40 GB) would exceed RAM.

## Viewer windows (worker spawn)

`open_tmux_viewer` (`iterative-dev/src/spawn/worker_io.sh`) opened each viewer with AppleScript `activate` + `new window`; Ghostty came to the front for every spawned worker. Worker `viewerbg` measured (run 1 of 3) that removing `activate` is not enough: `new window` alone activates Ghostty within ~200 ms and gives the new window focus. The user rejected "restore focus afterwards"; websearch already launches headed browsers without focus theft (`open -g -n -a <.app>`; Camoufox via `LSUIElement=true`). Worker's next plan, under measurement at the time of writing: `open -g -b com.mitchellh.ghostty <self-deleting .command>` (Ghostty declares `.command` as a document type; same process, so the menubar still finds the window).

## Skill proposal

The new `websearch-pdf` flow is stored as a patch: `dev/pdf_conversion_qa/patch/websearch-pdf-SKILL.md.patch` (view with `patchview`). It references `workflow.py extract/assemble/stats`, which do not exist yet (rebuild cycle). Open points for the next version: figure descriptions in the worker prompt, the parallel ceiling computed from available RAM instead of a fixed number, batch size (40 pages ≈ 200k tokens would also test `[1m]`).

## State at session end (2026-10-11)

- `CoenenbergKostenrechnungKostenanalyse_2016.md` copied to `rag-cli/data/documents/wise2627-reference/`, not indexed. No figure descriptions (first prompt version). 206 lines over 1 000 characters (longest 2 589), all long paragraphs, no tables, no repeated-character runs; check before indexing.
- The skill patch `dev/pdf_conversion_qa/patch/websearch-pdf-SKILL.md.patch` now carries the second draft: figure descriptions in the worker prompt, parallel ceiling computed from free RAM by `extract`, all batches spawned at once up to that ceiling, books over 1 000 pages covered. The user saw the full draft and closed the session before deciding on it.
- The Menubar shows `claude-sonnet-5-5[1m]` correctly in the Models tab; Apply writes the loaded value back unchanged. Only clicking the model name cycles through the fixed list without `[1m]`. (An earlier orchestrator statement that Apply would overwrite it was wrong.)
- Whether `[1m]` takes effect for Haiku is visible in a worker's tmux pane status line, not by a larger test batch (user correction).
- Rebuild tracked in issue "Konvertierung" (#147, monitor-cc).
