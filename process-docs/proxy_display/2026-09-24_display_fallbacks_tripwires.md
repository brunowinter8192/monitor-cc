# Display-side fallbacks and tripwires (worker mcfix-display, 2026-09-24)

Scope: `src/proxy_display`, `src/panes`, `src/workers`, `src/jsonl`, `src/format`, `src/utils.py`, `src/core`, plus the reader call sites in `src/gpu_pane/errors.py` and `src/dual_log_cli/reader.py`. Rule applied: an unobserved second path is removed (the condition aborts and reaches the pane-loop log), an observed one stays and gets a trace, a swallowed error goes into the pane log channel (`/tmp/monitor_cc_error.log` via `log_pane_error` / `log_pane_note`). Six commits on branch `mcfix-display`, one per finding group.

## PD10, the live defect (166 TypeErrors from `worker_proxy` on 2026-09-24)

Root cause chain, reproduced on an extracted copy of the older tree: `_extract_forwarded_fields` wrote `entry['messages'] = None` for every entry outside the keep-last window. An expanded `('req', i)` state on such an entry rendered through `strip_vocab.classify_tags`, `entry.get('messages', [])[start:]` returned `None` (key present) and raised `TypeError: 'NoneType' object is not subscriptable`. The pane loop retried every 50 ms, so the error repeated per frame. Two ways to reach it: the lazy loader returned `False` and its callers ignored the result, and the hourly reparse cleared `entries` but not the expand states, so an old expanded index pointed at an entry without messages.

Fix (all in `src/proxy_display`):
- "Messages not loaded" is an absent key, never `None`. Readers use `'messages' not in entry`. `.get('messages', [])` is then safe everywhere, including `src/proxy/strip_vocab.py`.
- `_lazy_load_messages_forwarded` returns nothing on success and raises `LookupError` for a missing flow id, a missing file or an unmatched flow. `OSError` is no longer swallowed there.
- `_toggle_expand_and_lazy_load` loads first and sets the expand state afterwards, so a failed load leaves the state unchanged.
- Both hourly reparse resets clear the expand states (the main proxy pane also clears its undo stack).

Proof: `dev/proxy_display/test_pd10_lazy_messages.py`. On the older tree run with `MCFIX_TREE=/tmp/<extracted tree>` it fails with the exact `TypeError: 'NoneType' object is not subscriptable`; on the fixed tree all four strands pass.

## Shared JSONL reader (CL-PARTIAL)

`src/jsonl/jsonl_reader.py`: `JsonlReader(path, start_pos)` streams a file in binary mode, stops before an unterminated last line, exposes `.position` (byte offset after the last complete line), raises `JsonlCorruptError` for an unparseable terminated line. `read_json_records(path, pos)` returns `(list, new_pos)`. Streaming matters: `_original.jsonl` files reach 464 MB and `accumulate_original_tools` keeps only the tools.

Replaced: the readline loops in `forwarded_parser` (parse and lazy load), `dual_log_accumulator` (two), `side_logs` (two), `warnings_pane._read_errors_log`, `panes/cache_turns.build_cache_turns`, `workers/worker_format` (two), `core/monitor._get_session_start_ts`, `gpu_pane/errors._read_all`, `dual_log_cli/reader.iter_jsonl`. `read_new_lines`, `parse_jsonl_lines`, `get_current_position` had no caller left and were deleted.

Corpus measured before the change: 750k terminated lines (dual_log, `src/logs`, 457 transcripts) contained zero unparseable lines, and no file at rest ended in an unterminated line. So "raise on interior corruption" fires on an unobserved condition only. Consequence to know: one corrupt interior line makes a pane raise on every tick (the pane loop logs and retries), the same flood pattern PD10 showed.

Proof: a harness ran old tree and new tree over a frozen copy of three dual-log quartets (one with a 49 MB `_original`), three transcripts and the errors files, hashing 49 outputs (parsed entries, accumulators, positions, incremental two-step parse, turns, worker stats, `iter_jsonl`). All 49 identical after normalizing `messages: None` versus absent (the intended PD10 change) and with `PYTHONHASHSEED=0` (set reprs otherwise differ per process). `dev/jsonl/test_jsonl_reader.py` covers the partial tail and the corruption raise.

## Session marker and worker scope (PD02, PD07, P14, PA06, PA07)

- `get_proxy_session_start_ts` returns `None` when the marker does not exist (was `time.time()`).
- `core.monitor._get_session_start_ts` returning `None` stays a state. The main proxy pane no longer substitutes `utcnow`; it re-asks each refresh while `None`, parses nothing (so no file position advances) and renders "Session start unknown ...". The re-ask matters: a fresh transcript can start with records that carry no timestamp, so `None` is recoverable.
- Warnings pane: `_monitor_start_ts` is Optional. Without a project filter or without a marker there is no worker-errors scan, and the header states which one (`worker errors: no project` / `no proxy session marker`). `scan_worker_errors_logs` requires the project session id and `min_mtime`; the widening glob over every project is gone.
- `_monitor_start_ts` is recomputed when the errors path changes, and the errors path changes when the marker appears, so a marker created after pane start is picked up.

## Tripwires and traces

- PD08 `_resolve_log_id`: missing marker still falls back to the session id and now logs one note per session id per process. A marker with fewer than two lines raises `IndexError`, an empty line 2 raises `ValueError`.
- PD09 `_reconstruct_delta_request` raises `LookupError` when a non-first delta has no earlier state. Measured first: 2908 forwarded records in 39 files, zero deltas without an earlier `is_first` of the same family (continue entries excluded).
- PD06: both `OSError` skips in `scan_worker_errors_logs` call `log_pane_error('side_logs')`. Tested with a dangling symlink that matches the glob.

## Dead code removed (PD13, F03, P13)

- PD13: `_render_stripped_block`, `_render_prestripped_range`, all `use_dual` parameters and `is_stripped and not use_dual` branches, the old-strip branch of `_sys_block_spans` with its `mods` parameter, the `original_text` branch, the `system_prompt_chars` / `tools_chars` fallbacks. Kept on purpose: the else branch of `_render_span_content` (plain-string spans are live for dual entries) and the entry fields `modifications` / `stripped_msg_indices`, which `src/proxy/strip_vocab.py` still reads.
- Every entry must now carry `_stripped_spans` / `_injected_spans` (`_attach_overlay_references` does this in both panes). Dev fixtures that build entries by hand needed those keys and, for the main proxy pane, `_proxy_session_start_ts` set.
- F03: `expand_states` and keyword-only `turn_cache` are required in `format_proxy_block` and `format_cache_tracker`.
- P13: `file_positions` and its five helpers in `core/monitor.py` had no reader; the warnings pane called `monitor_sessions()` only for that side effect. Deleted with both calls.
- Proof: `dev/proxy_display/render_byte_identity.py` (old harness on the old tree, updated harness on the new tree) gives identical hashes on three frozen quartets with every discoverable key expanded (2425 keys on the largest); `dev/panes/render_byte_identity.py` identical.

## Smaller fixes

- P02: `NO_TIME_PLACEHOLDER = '--:--:--'` in `src/constants.py` is the single "no time" text (`format_timestamp`, warnings header, warnings rows; the third placeholder `??:??:??` is gone). A non-empty malformed timestamp raises `ValueError`. Checked first: 221k transcript `timestamp` fields all parse. Side effect outside the scope: `gpu_render` now shows `--:--:--` for an empty `ts` instead of `00:00:00`.
- F01: `_fmt_rl_reset_time` lets a malformed header raise. F02: absent unified-status header is "no line" (output identical to before).
- W01: selection write `OSError` logged. W03: both `_read_selected_worker_name` copies swallow only `FileNotFoundError`. W04: unused `model` field (and one tmux call per worker) deleted. W05: the `window_activity` probe returns `unknown` on non-zero return code or empty output (was `int("0")`, reported `idle`).
- PA08: the synthetic user message in `build_cache_turns` is an observed fallback (commit d0d9a562: a mid-turn batch without a user line) and stays; it now logs one `log_pane_note` per (file, last-turn timestamp) so it does not flood the capped log.
- PA01/PA02 (`cleanup_old_jsonl`): partition into kept / expired / unparsable, one note with the unparsable count per file per run, atomic write (tmp plus `os.replace`), failures to `log_pane_error`. Naive timestamps stay kept: `dev/hook_smoke/test_log_janitor.py` documents "naive ts no TZ -> kept (fail-safe)". My first version let that `TypeError` propagate and would have left the whole file uncleaned; the existing test caught it. Always grep `dev/` for a test of the module before narrowing an except.

## Observed case worth passing on

`src/logs/api_errors.jsonl` has 270 of 270 lines with `ts` like `2026-05-30T17:16:51.395711+00:00Z` (offset and `Z` together). `datetime.fromisoformat` rejects it, so the daily janitor keeps every line forever and now says so in the pane log. The writer is in `src/proxy` (owner: another worker); the fix belongs there, not in the janitor.

## Verification notes and hazards

- Method that held up: `git archive integration src` into a temp directory, run the same harness under both trees (cwd decides which `src` is imported), compare digests. Test files take `MCFIX_TREE` to select the tree. Old-tree failures of the new tests show they provoke the changed behaviour.
- `dev/pane_flicker/m1_frame_e2e_test.py` is timing dependent (private tmux socket, compares against commit 0ce370df). It scored 128/132 and 123/132 on integration and 98/132 and 82/132 on this branch under machine load, with the failing steps being cursor and boot-timing checks of the worker panes, while the main proxy pane had no FAIL. Not re-verified in a quiet moment.
- `dev/pane_search/p2..p8`, `dev/click_ui/p1..p3`: need a sized pty (`script -q /dev/null bash -c "stty cols 220 rows 50; python3 ..."`). Pass counts equal old versus new (p3 62, p5 77, p6 78, p7 83, p8 82, click_ui reports 22/21/75). These scripts write report files into their `md/` folders inside the tree they run in; remove new report files by explicit name afterwards.
- Not repaired, pre-existing or dead-path: `dev/display/test_strip_markers.py` (ImportError `get_stripped_data`, fails on the older tree too) and the `stripped_msg_indices` cases of `dev/proxy_dual_log/A_render_refactor_proof` (they exercise the removed non-dual paths, so a baseline compare would differ by design).
- Live check in process, without a window: refresh, build, expand-with-lazy-load of the proxy pane, warnings refresh and tokens refresh against the real logs of the monitor-cc project ran without exception (122 entries, 31 warnings, 21 turns).
- A pane started by the user was not exercised; the change takes effect on the next pane restart.
