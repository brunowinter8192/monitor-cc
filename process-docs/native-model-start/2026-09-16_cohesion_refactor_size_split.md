# 2026-09-16 — cohesion refactor: split every file/function over threshold in dev/native-model-start/

## Task

Four files violated the size thresholds: `p2_model_params_probe.py` (549 LOC, over the 400-LOC
file threshold; `test_clear_thinking_edit_stripped_when_thinking_disabled` at 78 lines, over the
50-line function threshold), `p3_cache_breakpoints_probe.py` (`main` 79 lines), `p4_dual_log_
integrity_probe.py` (`main` 98 lines), `p5_strip_wordings_probe.py` (`main` 100 lines). Bring every
file and function under threshold with zero behaviour change, entry-script filenames unchanged.

## Module split — only p2 needed a file split (the only file over 400 LOC)

`p2_model_params_probe.py` (549 -> 135 LOC) is a single 15-test-group probe with one clear seam:
the docstring itself already narrates two unrelated concerns ("Covers: legacy-config-only ..." /
fixation mechanics = Tests 1-12, vs. "2026-09 thinking/context_management self-consistency
coverage" = Tests 13-15). Split into three new sibling modules (no number prefix):
- `model_params_test_infra.py` (27 LOC) — the shared `check()`/`_RESULTS` assertion-recording pair
  and `_with_config`. `_RESULTS` is a plain module-level list; every sibling module that imports it
  binds to the SAME list object, so `check()`'s in-place `.append()` calls stay visible to the
  entry script's `_write_report` without any extra wiring — confirmed this holds by running the
  whole thing end-to-end (see Verification below), not just by reasoning about it.
- `model_override_injection_tests.py` (259 LOC) — Tests 1-12 (`test_legacy_only_unchanged` through
  `test_fixation_load_failure_does_not_pin`), plus `_base_payload`/`_LEGACY_CONFIG`/
  `_MODEL_PARAMS_CONFIG`, which only these 12 tests use.
- `thinking_context_management_tests.py` (187 LOC) — Tests 13-15 plus
  `_load_attribution_coverage_module`. Test 13 (`test_clear_thinking_edit_stripped_when_thinking_
  disabled`, 78 lines) needed a SECOND split on top of the file split: it has 6 lettered cases
  (a)-(f) with a natural 2+3+1 grouping (removal cases / no-op cases / end-to-end), which became
  `_test_clear_thinking_removal_cases`, `_test_clear_thinking_noop_cases`,
  `_test_clear_thinking_end_to_end`, called in sequence by the still-named test function.
- Entry script (`p2_model_params_probe.py`) kept `run_probe_workflow`/`_write_report` verbatim,
  now importing `_RESULTS` and all 15 test functions from the three siblings.

`p3`/`p4`/`p5` (`main` 79/98/100 lines) stayed single-file — none was anywhere near 400 LOC, so
this was pure function extraction. Pattern used in all three: separate PURE COMPUTATION (the
per-request/per-session accumulation loop) from MARKDOWN-LINES BUILDING (each report section as
its own `_*_lines(...)` function), then have `main()` just call collect -> section-builders ->
write, mirroring the exact split pattern used in the immediately-prior `dev/proxy_instrumentation/`
and `dev/display/` cohesion-refactor milestones (see those areas' process-docs).

## Gotcha — a cosmetic list-literal condensation triggers the same comment-multiset false positive twice, learn to recognize it immediately

While extracting `p3`'s and `p4`'s report-line builders, I mechanically condensed adjacent
`lines.append('## Verdict')` / `lines.append('')` pairs into a single `lines = ['## Verdict', '',
...]` list literal — harmless to the OUTPUT (same strings end up in the same order), but it makes
the `diff <(grep -oE '#.*' old|sort) <(grep -oE '#.*' new|sort)` comment-parity check (the exact
technique that caught a real comment-loss bug in the immediately-prior `dev/display/` milestone)
report a spurious difference, because the substring `## Verdict')` no longer appears verbatim on
its own line — it's now embedded inside a longer literal. This happened twice (p3, then p4) before
I stopped doing the condensation. **Recognize this pattern fast: if the diff shows an "old" line
disappearing and no NEW line appearing in its place — nothing added, nothing structurally
missing — the likely cause is a multi-statement literal merge, not a dropped comment.** Fix is to
just not do the merge: keep each `lines.append(...)` on its own line, exactly as the original had
it, purely mechanical relocation with zero re-expression. Re-ran the exact same diff check after
un-merging both instances; came back clean (identical multiset) in both files.

## Verification method and results

All 4 `.py` files in this directory are read-only: `p2` never touches real data (mocked config,
synthetic payloads); `p3` replays recorded payloads through a real `ProxyAddon()` but via a FAKE
`_FakeFlow`/`_FakeRequest` (no live mitmproxy connection); `p4`/`p5` only read dual-log JSONL and
call pure functions. None touch tmux/desktop/the live monitor. Confirmed by reading before
touching anything.

- **`p2_model_params_probe.py`**: this one has NO real-corpus dependency at all (everything is a
  synthetic in-process fixture), so it got a full real end-to-end run: pre-split backup (placed
  back into the real `dev/native-model-start/` directory under a throwaway filename — copying to
  `/tmp/` breaks its `WORKTREE_ROOT = Path(__file__).resolve().parents[2]` computation, the same
  trap documented in the `dev/display/` milestone's process-docs) vs. the post-split file, diffed
  stdout. Both runs hit the IDENTICAL pre-existing failure at Test 15 —
  `ModuleNotFoundError: No module named 'attribution_coverage_analyse'` when
  `_load_attribution_coverage_module` executes `dev/proxy_dual_log/attribution_coverage.py` (that
  file does a flat sibling import that only resolves when `dev/proxy_dual_log/` itself is
  `sys.path[0]`, which it never is when the driving script lives in a different directory) — this
  is a pre-existing environmental gap unrelated to this refactor, same class of issue as the
  corpus-rotation gaps found in every prior milestone in this series. All 105 PASS lines preceding
  that failure point are byte-identical between old and new; the traceback differs only in
  filename/line-number references (expected, since the two copies live at different paths).
- **`p3_cache_breakpoints_probe.py`, `p4_dual_log_integrity_probe.py`,
  `p5_strip_wordings_probe.py`**: their hardcoded corpus stems (`api_requests_opus_posts_
  1786051932`, `api_requests_opus_websearch_1786052022`) have rotated out of `src/logs/dual_log/`
  (confirmed missing before touching anything — same rotation problem this area's own DOCS.md
  Gotchas section already documents). Used the task's synthetic-input fallback for all three:
  built small hand-made records/payloads shaped exactly like what `_replay_session`/
  `_check_composition`/`_check_markers_stripped` actually produce, fed them into BOTH the
  extracted helper functions AND a manually-reconstructed copy of the original inline `main()`
  logic (since there's no unsplit function left to call directly for comparison — the split IS
  the change), asserted equal intermediate values (`_analyze`/`_classify_busts` return values,
  accumulated `keys_seen`/`sys_shapes_seen`/`block_types_seen`/`sample_payload_by_key`, `verdict`
  strings) and equal generated report-line lists at every stage. All three came back identical.
- All 7 `.py` files pass `python -m py_compile`; an AST sweep for `FunctionDef` nodes with
  `end_lineno - lineno + 1 >= 50` returns empty across the whole directory; `wc -l` on every file
  is under 400 (largest is `p3_cache_breakpoints_probe.py` at 331).
- No verification artifacts were left behind: `p2`'s crash happens before `_write_report` runs (in
  both old and new), so no new timestamped report landed in `md/`; `p3`/`p4`/`p5` were never run
  via their real `main()` (only their extracted helper functions were called directly with
  synthetic data), so their fixed-name `md/*_report.md` files were never touched either —
  confirmed via `git status --short` showing zero changes under `md/`.

## Cross-reference

See `process-docs/proxy_instrumentation/` and `process-docs/display/` for the two immediately-prior
cohesion-refactor milestones this one's split pattern and verification method are modeled on,
including the `__file__`-depth trap for backup copies and the comment-multiset verification
technique (and its one recurring false-positive mode, documented above for the first time).
