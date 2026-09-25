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
