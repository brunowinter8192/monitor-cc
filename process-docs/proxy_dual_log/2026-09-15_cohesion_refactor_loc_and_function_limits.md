# 2026-09-15 — Cohesion refactor of `dev/proxy_dual_log/` for the 400-LOC / 50-line limits

## Trigger

11 of the 15 `.py` files in `dev/proxy_dual_log/` violated the project's 400-LOC file limit
and/or had functions at or above 50 lines. Mandate: split by CONCERN (not cosmetic shrinking),
zero behaviour change (byte-identical reports/stdout/exit codes), no CLI/path/rename changes,
scope confined to this one directory.

## Investigation

Read every `.py` file in the directory in full (all 15 scripts, including the 4 not on the
hit-list, since those might import the ones being split) plus this directory's own DOCS.md and
`dev/DOCS.md`. Two facts drove every split decision:

1. **`test_composition_invariant.py` does `import composition_probe as _probe`** and reads
   `_probe._strip_cache_control`, `_probe.run_passes_and_collect_ops`, `_probe._block_text`,
   `_probe.compose_block`, `_probe.check_invariants` as module attributes. Any split of
   `composition_probe.py` had to keep re-importing these 5 names at the top of the (now-thin)
   `composition_probe.py` so the attribute lookup keeps working — moving the *definitions* out
   is fine, dropping the *re-import* is not.
2. **`block_dev_imports_src` (`src/hooks/block_dev_imports_src.py`) only blocks `from src.`/
   `import src.` at column 0** (`re.compile(r'^(?:from\s+src\.|import\s+src\.)', re.MULTILINE)`).
   Every script in this directory already exploits that: `sys.path.insert(0, ".")` at module
   scope, then an *indented* `from src.proxy.rules import apply_modification_rules` inside a
   function body. Every new split module that needs a `src.` import keeps this exact pattern
   (indented, inside a function) — a top-level `from src.` line in a new file would get blocked
   by the hook the moment a real Write/Edit tool call (not a Bash heredoc) touched it.

## Decisions

**No cross-script deduplication**, even though `_strip_cache_control`, `_infer_family`, and the
forwarded-delta-chain-reconstruction loop are copy-pasted near-identically across
`diff_strip_inject.py`, `span_inline_probe.py`, `composition_probe.py`,
`groundtruth_message_spans_probe.py`, `main_log_elimination_probe.py`, and `verify_delta.py`.
This is the pre-existing convention in the directory (every probe is self-contained) and
deduplicating it is a real behaviour-preserving improvement but is explicitly out of scope for a
"split for LOC/length" mandate — flagging it here rather than doing it silently.

**Files under 400 LOC with only a long function got in-place extraction, no new file.**
`verify_delta.py`, `diff_strip_inject.py`, `tt_delta_skip_replay.py` all kept their single file;
the over-50-line function was broken into 2-4 private helpers in the same file. Do this before
reaching for a new module — a new sibling file is only warranted once the *file* also crosses
400 LOC.

**Split boundary per file — one module per concern, always self-contained (own
`INFRASTRUCTURE`+`FUNCTIONS`, no `ORCHESTRATOR`) per the Utility-module exception, since none of
these siblings has its own CLI workflow:**
- `A_render_refactor_proof.py` → harness (kept) + `_fixtures.py` (3 builder fns) +
  `_cases.py` (14 case fns).
- `proxy_176_bg_launch_ack_tests.py` → runner (kept, now just imports+sequences) +
  `_fixtures.py` (constants only) + `_report.py` (`check`/`_PASS`/`_FAIL`) + `_cases.py` +
  `_cases_w3.py`. The case functions alone were 428 LOC as ONE file (still over 400 after
  pulling out fixtures/report) — split again at the file's own internal section boundary
  (the "LAUNCH-ACK WORDING 3" `# ──` comment divider already marked where wording-1/2 tests end
  and wording-3 + later-appended tests begin), giving 256 + 193 LOC.
- `attribution_coverage.py` → orchestrator (kept) + `_classify.py` (span-format detection +
  message classification + the two field-attribution maps + `_coverage`) +
  `_analyse.py` (pair discovery, JSONL load, one `_analyse_<section>_delta` fn per
  sys/tools/messages/fields) + `_report.py` (one `_report_<section>()` fn per report section,
  `_false_positive_section` itself split again into header/tail once it hit 57 lines with the
  25-line evidence-table loop counted in).
- `green_overlay_probe.py` → orchestrator (kept, one `_emit_<section>` per report section,
  `_emit_primary_bug_case` split again into `_emit_bug_case_variants` once loop+3-variant body
  hit 52 lines) + `_diff.py` (the 3 diff-variant functions + attribution + fidelity + format
  helpers) + `_cases.py` (bug case + regression cases + live gating-soundness scan).
- `composition_probe.py` → orchestrator (kept, re-exports the 5 names
  `test_composition_invariant.py` needs, one `_emit_<section>` per report section) +
  `_ops.py` (pure span algebra: strip/get-inner-text/block-text/extract-ops/apply-edit/
  compose/check-invariants) + `_passes.py` (`run_passes_and_collect_ops`, split into
  `_collect_real_ops`/`_collect_standin_ops`/`_record_ops`) + `_corpus.py` (`run_corpus` split
  into `_scan_entry`/`_check_block`, plus `get_money_shot_case`, plus `LOG_STEMS`/`LOG_DIR`).
- `main_log_elimination_probe.py` → orchestrator (kept, now 77 LOC) + `_io.py` (path
  resolution + JSONL loaders) + `_reconstruct.py` (delta-chain reconstruction + the 3 field
  classification maps/tables) + `_questions.py` (`_run_question_a` split via a new
  `_compare_request(idx, main_e, fwd_r)` helper that replaced 3 write-only accumulator
  variables — see "Incidental cleanup" below; `_run_question_b` split via
  `_extract_tool_errors`) + `_report.py` (one `_report_<section>` fn per report section,
  threading `all_content_lossless`/`must_add`/`meta_only` through as explicit return values
  instead of shared closure locals).
- `span_inline_probe.py` → orchestrator (kept, 68 LOC) + `_reconstruct.py` (JSONL load +
  chain reconstruction + request matching) + `_blocks.py` (the 3 `_find_*_block` finders —
  each now takes the diff function as a parameter instead of relying on the module-level
  `_diff_text` the original file loaded via `importlib`, so the finder module has zero
  `importlib`/`sys.path` machinery of its own) + `_report.py` (Form A/B analysis + one
  `_report_<section>` fn per report section; two of those — `_report_form_a`/`_report_form_b`
  — were still exactly 51 lines after the first pass, fixed by extracting
  `_report_form_a_row(r)` and `_report_storage_cost(...)`).
- `groundtruth_message_spans_probe.py` → orchestrator (kept, 115 LOC) + `_algorithm.py`
  (the mirrored src/ helpers, `diff_text_word`, `build_message_spans` split into
  `_split_stripped_chunks`/`_walk_forward_spans`, both fidelity checks) + `_cases.py`
  (`load_entry_by_flow_id`/`run_rules` + the 4 `get_*_case` builders) + `_report.py`
  (`fmt_spans`/`phantom_green_check`/`run_case` + one `_emit_case_*`/`emit_*_summary` fn per
  report section; `run_case` itself landed at exactly 50 lines, fixed by extracting
  `_derive_diff_spans(case, o_text, f_text)`).

**Incidental cleanup, not a feature:** `main_log_elimination_probe.py`'s original
`_run_question_a` computed `total_sys`/`total_tools`/`total_msgs` (all three always equal to `n`,
incremented once per loop iteration) but never read them anywhere — not returned, not printed.
Extracting `_compare_request` per-request made carrying these three write-only locals forward
awkward, and since nothing downstream ever consumed them, they were dropped. Confirmed
behaviour-neutral by a synthetic-fixture diff against the original monolithic function (see
Verification) — the returned dict and the rendered report are identical either way.

## Verification

Ran every touched script BEFORE editing and saved stdout + any generated report under
`/tmp/pre_refactor_snapshot/` (worktree-local, never staged), then re-ran after each file's split
and diffed. Three categories of expected, accepted diff:
- **Traceback line/file numbers** — several scripts crash with a pre-existing, unrelated error
  against current data (`diff_strip_inject.py`/`main_log_elimination_probe.py`/
  `span_inline_probe.py`/`green_overlay_probe.py`/`composition_probe.py`'s money-shot section all
  hit `FileNotFoundError` or `KeyError: 'spans'` against hardcoded session stems that no longer
  exist on disk, or against a `_diff_messages` shape drift already called out in this directory's
  DOCS.md). Confirmed the exception type, message, and logical call site are unchanged; only the
  file path (now the new sibling module) and line number differ.
- **Live-corpus timestamp/count drift** — `attribution_coverage.py`, `green_overlay_probe.py`
  (report has no live data — hardcoded session, unaffected), `composition_probe.py`'s money-shot
  section scan the actual `src/logs/dual_log/` corpus, which is growing *during this very
  session* (the worker's own tool calls go through the proxy and get logged). For
  `attribution_coverage.py` specifically, took a `cp -r` snapshot of `src/logs/dual_log/` to
  `/tmp/frozen_dual_log`, ran the pre-refactor script and the post-refactor script both pointed
  at that frozen snapshot (temporary one-line `sed` patch of `_dual_log_direct`, reverted
  immediately after), and diffed — byte-identical. `composition_probe.py`'s corpus run targets 5
  FIXED stems (not a glob), so it was naturally stable across the two runs without needing a
  snapshot.
- **Report timestamp header** — several reports self-stamp `datetime.now()` in the header line;
  diffed with that one line normalized out.

For `main_log_elimination_probe.py` and `span_inline_probe.py`, the only real session data that
would exercise the SUCCESS path (not the early FileNotFoundError) no longer exists on disk at
all (main proxy logs were superseded by the dual-log quartet before this session; the hardcoded
`span_inline_probe` session was rotated out). Built synthetic fixtures instead and asserted the
new split functions produce an IDENTICAL result dict / report text to the original monolithic
functions (loaded from the pre-edit snapshot via `importlib.util.spec_from_file_location`) — see
the synthetic-fixture blocks in this recap's shell history equivalent; not persisted as a dev/
script since it was a one-off cross-check, not a regression guard anyone will re-run (the real
regression guard for `main_log_elimination_probe.py`'s question logic would need real main-log
data that plain does not exist anymore — flagging this as a coverage gap rather than inventing a
fixture no one asked for).

Final state: `python3 -c ast.parse` on all 38 `.py` files in the directory (syntax check),
`wc -l` on all 38 (every file 384 LOC or under), and an AST walk for any `FunctionDef`/
`AsyncFunctionDef` at 50+ lines (none found) — see the WORKER's COMPLETION CHECKLIST for the
exact numbers.

## Gotchas for the next agent

- If you touch `composition_probe.py` again: do NOT remove the
  `from composition_probe_ops import _strip_cache_control, _block_text, compose_block,
  check_invariants` / `from composition_probe_passes import run_passes_and_collect_ops` imports
  at its top even if `composition_probe.py`'s own body stops calling them directly — they exist
  ONLY so `test_composition_invariant.py`'s `import composition_probe as _probe;
  _probe.run_passes_and_collect_ops(...)` keeps resolving. Grep
  `dev/proxy_dual_log/test_composition_invariant.py` before deleting any composition_probe
  import.
- The `_dual_log_direct`/`LOG_DIR` path-resolution blocks in every script are NOT
  interchangeable even though several look byte-identical — `span_inline_probe.py` uses
  `Path(__file__).parents[5]` (single path, worktree-only, no main-checkout fallback) while
  every other script in the directory uses the `_log_from_main`/`_log_from_wt` two-path
  fallback pattern. This was already inconsistent before this refactor; preserved as-is per
  negative scope (no CLI/path changes).
- `dev/proxy_dual_log/*_reports/` directories (attribution_coverage_reports/,
  green_overlay_probe_reports/, groundtruth_message_spans_probe_reports/, 01_reports/,
  main_log_elimination_probe_reports/) are NOT gitignored and NOT tracked either — only
  `A_render_refactor_proof_reports/baseline_*.json` is committed. Every verification run during
  this refactor regenerated one of these dirs; all were `rm -rf`'d before the final commit so
  `gcommit`'s auto-stage-untracked doesn't pick up one-off debug output. If a future run leaves
  one behind, check `git ls-files dev/proxy_dual_log/` for what's actually meant to be tracked
  before staging.
