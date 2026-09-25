# api_errors.jsonl ts format and janitor pruning

2026-09-25

## Observed defect

`src/proxy/addon_dual_log.py:_log_4xx_error` wrote `"ts": datetime.now(timezone.utc).isoformat() + "Z"`, e.g. `2026-09-25T01:37:02.682416+00:00Z`. `src/panes/log_janitor.py:_line_state` did `fromisoformat(ts.replace('Z', '+00:00'))`, giving `+00:00+00:00`, ValueError, so every line counted as unparsable and was kept forever. The main checkout's `src/logs/api_errors.jsonl` had 308 lines (195 MB) all with this suffix.

## Change

- Writer: `_log_4xx_error` ts is now plain `isoformat()` (ends `+00:00`), parsed by `fromisoformat` directly.
- Janitor: `_normalize_ts` maps the legacy `+00:00Z` suffix to `+00:00` before parsing (a plain trailing `Z` still maps to `+00:00`). `cleanup_old_jsonl` emits `log_pane_note('log_janitor', '<file>: handled N lines with legacy ts suffix +00:00Z')` next to the existing unparsable note, so the second path is visible at runtime.
- Decision tolerant reader vs one-time rewrite: tolerant reader. The proxy appends to the 195 MB file while running, a separate rewrite script would race with the appends; the janitor already rewrites atomically every 24 h; legacy lines age out after 7 days so the branch becomes inert without cleanup. The 195 MB file shrinks through normal age pruning; no separate action.
- Observed check: all 308 real lines parse under `_line_state` (Counter: 308 x expired with legacy=True at a far-future cutoff, 0 unparsable).

## Existing test adjusted

`dev/panes/test_display_tripwires.py` case `janitor_partition_and_atomic_write` used a `+00:00Z` ts as its "unparsable" fixture; that value is now legacy-handled. Fixture changed to `not-a-date`; expectations unchanged.

## Tests

`dev/proxy/test_api_errors_ts.py` (temp MONITOR_CC_ROOT, fake flow): writer ts parses with UTC offset; 5 real legacy lines from the main log are parsed and prunable by age with 0 unparsable; a mixed file (legacy old/fresh, new old/fresh, garbage) keeps exactly legacy_fresh, new_fresh, garbage and emits both notes. `dev/hook_smoke/test_log_janitor.py` and `dev/panes/test_display_tripwires.py` pass. The real proxy was not started.

## Other `isoformat() + "Z"` writers (left untouched, out of scope)

All produce `...+00:00Z`.

- `src/proxy/addon.py:233` field `timestamp` (dual-log forwarded/original entries). Readers: `src/dual_log_cli/*` (discovery, timeline_boundaries, numbering, render_reqs, usage `_epoch_from_iso`), `src/proxy_display/format.py`, `pane.py`, `frozen_turns.py`, `forwarded_parser.py` (mostly lexical string comparison), `src/core/monitor.py:55-57` and `src/utils.py:25` (`replace('Z','+00:00')` then `fromisoformat`, ValueError on this format for the dual-log path), many `dev/` scripts (`dev/proxy_analysis/01_session_summary.py`, `dev/proxy_forensics/strip_tracking_audit.py`, `dev/tool_use_analysis/*` ...).
- `src/proxy/addon_dual_log.py:36` field `timestamp` (`_log_original_request`): same readers as above.
- `src/proxy/bg_escape.py:82` field `ts` (bg_escape event log): only reader found is `dev/bg_wakeup_id_line/p2_bg_escape_probe.py`. No src reader found.

Changing the `timestamp` writers would mix two formats inside existing dual-log files that are compared lexically; that needs its own decision.

Related but different: `src/hooks/block_rag_cli_document_repeat.py:139` reads a hook `ts` with `replace('Z','+00:00')`; not one of the proxy writers.

## Review follow-up: frozen fixture

`dev/proxy/test_api_errors_ts.py` first read the live main-checkout `src/logs/api_errors.jsonl`; those lines age out 7 days after the fix is live, which would make the test non-reproducible. The first 5 real lines (ts 2026-05-30, all `+00:00Z`) are frozen in `dev/proxy/fixtures/api_errors_legacy_ts.jsonl` with `request_payload` set to null (the 5 lines were 3.3 MB, the janitor only reads `ts`); all other fields are verbatim. The test reads only that fixture and no longer touches live paths.

## Follow-up: log_janitor section order

Four-eyes review found `_LOG_REGISTRY` (a module-level assignment) after the `# FUNCTIONS` marker in `src/panes/log_janitor.py`. The `LogSpec` dataclass and `_LOG_REGISTRY` moved into INFRASTRUCTURE, below `_RETENTION` and `_LEGACY_TS_SUFFIX`; nothing else changed (file stays 202 LOC). Equality check: all 11 `LogSpec` entries of the pre-move version (imported from `git show HEAD:`) equal the moved ones. `cleanup_old_jsonl` still mixes orchestration and logic; the module has no separate ORCHESTRATOR function (not addressed, outside this task).

## Test-run gotchas for a successor

- The venv is at `/Users/brunowinter2000/Documents/ai/monitor-cc/venv/bin/python` (main checkout), not inside the worktree. Only the AppKit test needs it; the proxy/janitor tests run with system `python3`.
- Running `dev/model_selector/verify_four_tab_ring.py` rewrites its report `md/verify_four_tab_ring.md` (one-line diff noise); revert it before committing.
- macOS `sed -i` needs `-i ''`; a failed sed silently left a weak assertion once.

## 2026-09-25 (second task): the other three writers and bg_escape pruning

### Correction of the earlier reader claim

The earlier list named `src/core/monitor.py:55-57` and `src/utils.py:25` as readers of the `+00:00Z` fields. Wrong: `monitor._get_session_start_ts` reads the Claude Code session transcript (`...123Z`), `utils.format_timestamp` is fed by CC call timestamps, `tool_errors.jsonl` ts and gpu error ts. Nothing in `src/` parses the `timestamp` of `*_original.jsonl`, the `timestamp` of `*_response.jsonl` or the `ts` of `bg_escape_events.jsonl`. `format_timestamp('2026-09-25T01:37:02.682416+00:00Z')` does raise `ValueError` (`...+00:00+00:00`), reproduced, but no data path delivers that value to it.

### Format census on disk (2026-09-25, regex over the first 400 chars of each line)

- `*_original.jsonl` 1785 lines and `*_response.jsonl` 1781 lines (19 files each): all `+00:00Z`.
- `bg_escape_events.jsonl` 315970 lines: all `+00:00Z`.
- `*_forwarded`, `*_stripped`, `*_injected`, `*_errors` (1785, 1749, 1749, 103 lines) and `tool_errors.jsonl` (274): all `.mmmZ` (written by `_forwarded_timestamp` / `strip_inject_delta`, valid for every reader).
- The lexical-comparison readers (`proxy_display/format.py`, `pane.py:264`, `frozen_turns.py`, `dual_log_cli/numbering.py`) only see the `.mmmZ` streams and CC transcript timestamps. Mixed legacy/new values would differ only for identical instants to the microsecond (legacy sorts later); no reader reads those files lexically.
- `dual_log_cli/reader.py:local_datetime` (`rstrip("Z")` then `fromisoformat`) parses both formats; `dev/dual_log_cli/tests/test_sidecar_exclusion.py` even uses `+00:00Z` as a fixture.

### Change

- Writers `addon.py` (`_write_response_entry` "timestamp"), `addon_dual_log.py` (`_log_original_request` "timestamp"), `bg_escape.py` (`_log_bg_escape_event` "ts") now write plain `isoformat()` (ends `+00:00`). No reader changed. Legacy lines stay on disk untouched.
- `_LOG_REGISTRY` gained `bg_escape_events` (`sweep_eligible=True`, 7 d ts records), so the token pane's 24 h sweep prunes it like `api_errors.jsonl`. Legacy `+00:00Z` lines are handled by the existing `_normalize_ts` with the traceable note.
- One-shot proof on a temp copy of the real file (50.6 MB, 316065 lines at copy time): janitor pass took 0.4 s, left 47333 lines / 7.6 MB, oldest kept ts `2026-09-18T16:27:53+00:00Z` (7 days before the run), 0 unparsable, note `handled 316065 lines with legacy ts suffix +00:00Z`. Nothing on live paths was touched.

### Tests

- `dev/proxy/test_writer_timestamps.py` (venv python, mitmproxy import): each writer's value parses via `fromisoformat` with UTC offset and no `Z`; `local_datetime` gives the same instant for legacy and new; mixed legacy/new sequence stays lexically chronological for distinct instants; janitor on a temp file of 6 real legacy lines (frozen in `dev/proxy/fixtures/bg_escape_events_legacy_ts.jsonl`) plus fresh legacy and fresh new lines prunes the old ones and keeps both fresh ones; sweep-eligible registry is exactly hook_firing, api_errors, bg_escape_events.
- Byte identity: `dev/proxy/addon_hook_byte_identity.py` and `pipeline_byte_identity.py` (venv python) give identical hashes with and without the change (they normalise `timestamp`/`ts` keys).
- `test_api_errors_ts.py`, `dev/hook_smoke/test_log_janitor.py`, `dev/panes/test_display_tripwires.py` still pass.
- Gotcha: `addon_hook_byte_identity.py` fails under system python3 (no mitmproxy); use `/Users/brunowinter2000/Documents/ai/monitor-cc/venv/bin/python`.

### Not done

- `utils.format_timestamp` and `_get_session_start_ts` were left as they are (no data path feeds them the legacy value).
- The proxy running from its `.proxy_live_*` copy keeps writing the old format until it is restarted; that is expected and covered by the legacy handling.
