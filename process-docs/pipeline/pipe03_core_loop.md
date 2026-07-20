# Pipe Section: Core Loop

## State as of this section's audit

- `monitor.py`: `run_main_loop()` calls `load_historical_main()` (sets the newest main session to position 0), tracks `current_main_session` via `_get_newest_main_session()`. Detects a session change each poll cycle → clears the screen + resets position. Polls every 0.5s via `monitor_sessions()` + `_refresh_strip_cache()` + `render_main_buffer()`
- `src/panes/token_pane.py`: `run_tokens_loop()` polls every 0.5s, `build_cache_turns()` reads the newest main session from position 0 and renders the cache tracker. Supports mouse events (expand/collapse, hover).
- `src/panes/warnings_pane.py`: `run_warnings_loop()` calls `load_historical_warnings()` (sets the newest main session to position 0), then polls every 0.5s via `monitor_sessions()` and renders `_format_warnings_pane()` (in `src/panes/warnings_render.py`) on change
- `src/workers/worker_pane.py`: `run_workers_loop()` polls every 0.5s, calls `list_workers()` and renders `format_workers_block()` on change. Expanded workers show the cache-tracker token view (CR/CC/D per API call) via `extract_cache_turns()` + `format_cache_tracker()`. No more subagent rendering (separate pane).
- `system_messages` is returned as the 9th (last) return value of `parse_new_tool_calls()`; `process_session_file()` unpacks and renders it via `display_system_message()` / `format_system_message()`
- Agent tracking: `agent_to_task`, `agent_to_type` maps, `buffered_subagent_calls` for orphans (calls with no known agent)
- Session browser: `token_cumulative_n: Optional[int]` (monitor.py:48) controls the mode. Keyboard input in `run_tokens_loop()`: digits → buffer, Enter → set/clear n, 'q' → clear. `compute_cumulative_tokens(n)` reads the last N main sessions from position 0.

`run_workers_loop()` sequence:
1. `list_workers(active_project_filter)` → reads tmux sessions with the `worker-{project}-` prefix
2. Per worker: `detect_worker_status()` via `#{pane_dead}` + pane-content analysis, `get_tmux_env()` for WORKER_SPAWNED + WORKER_PURPOSE
3. Per expanded worker: `find_worker_jsonl()` → `extract_cache_turns()` → `worker_turns[name]`
4. `format_workers_block(workers, expand_states, worker_turns, ...)` → renders the worker list with the cache tracker on expand
5. On change: screen-clear + print
6. `time.sleep(POLL_INTERVAL)`

### Global Mutable State — All Variables (category: architecture / coupling)

All module-level variables in `src/core/monitor.py` with an access mapping (state after session 3):

| Variable | Type | Defined | Read | Written | Description |
|----------|-----|-----------|---------|-------------|--------------|
| `file_positions` | `Dict[Path, int]` | monitor.py:28 | monitor.py | monitor.py | Byte offsets per JSONL file |
| `tool_use_caches` | `Dict[Path, dict]` | monitor.py:29 | monitor.py | monitor.py | tool_use_cache per session file |
| `call_counter` | `int` | monitor.py:30 | monitor.py | monitor.py | Global call counter for display |
| `agent_to_task` | `Dict[str, str]` | monitor.py:31 | monitor.py | monitor.py | agent_id → task tool_use_id |
| `agent_to_type` | `Dict[str, str]` | monitor.py:32 | monitor.py | monitor.py | agent_id → subagent_type |
| `buffered_subagent_calls` | `Dict[str, List[dict]]` | monitor.py:33 | monitor.py | monitor.py | Calls with no known agent, no TTL |
| `task_requests_seen` | `Set[str]` | monitor.py:34 | monitor.py | monitor.py | Seen task-request IDs |
| `active_project_filter` | `Optional[str]` | monitor.py:35 | monitor.py | monitor.py | Active project filter |
| `active_mode` | `str` | monitor.py | monitor.py | monitor.py | Current mode (all/main/rules/workers/proxy/...) |
| `_last_monitored_count` | `Optional[int]` | monitor.py | monitor.py | monitor.py | Logging guard: session count |
| `token_profile` | `Dict[str, int]` | monitor.py:45 | monitor.py | monitor.py | Cumulative output tokens by block type |
| `token_profile_tools` | `Dict[str, int]` | monitor.py:46 | monitor.py | monitor.py | Output tokens by tool name |
| `token_profile_request_ids` | `Set[str]` | monitor.py:47 | monitor.py | monitor.py | Seen requestIds (turn dedup) |
| `token_cumulative_n` | `Optional[int]` | monitor.py:48 | monitor.py | monitor.py | Session browser: last N sessions (None = current session) |
| `token_input_buffer` | `str` | monitor.py:49 | monitor.py | monitor.py | Keyboard input buffer for the session browser |

**Coupling analysis:** token-profiling state (`token_profile` etc.) lives in `panes/token_pane.py`.

### buffered_subagent_calls — No TTL (category: memory)

`buffered_subagent_calls: Dict[str, List[dict]]` (monitor.py:65):
- An entry is added when a subagent call arrives but `agent_id` is not yet in `agent_to_task` (`handle_subagent_call()`, monitor.py:410-414)
- An entry is cleared when a task response with `spawned_agent_id` arrives (`handle_task_response()`, monitor.py:374-379)
- No TTL: if no task response arrives (e.g. Claude Code crashed, session ends), entries grow unbounded
- No cleanup on session removal (unlike `tool_use_caches`, which get cleaned up via `update_session_tracking()`)

### filter_sessions_by_mode — Session Count in the Header (session 4, category: correctness)

`run_monitor()` (monitor.py:52-79) now calls `filter_sessions_by_mode(sessions, mode)` BEFORE calling `print_session_status(session_count, ...)` (monitor.py:72-73 and 77-78).

Before: `session_count = len(sessions)` — counted all sessions (main + subagent) regardless of mode
Now: `session_count = len(filter_sessions_by_mode(sessions, mode))` — counts only the sessions actually relevant to that mode

Affects modes: `MODE_MAIN` (non-agent files only), `MODE_ALL` (all).

## Evidence

The `dev/pipeline/` suites were primarily set up for pipe02 decisions; their measurement results back several pipe03 claims:

### Poll Overhead per 0.5s Cycle (context for finding 1)

`dev/pipeline/io_profile/01_reports/poll_cycle_20260322_152817.md` (script: `dev/pipeline/io_profile/01_poll_cycle_cost.py`, dataset: 70 projects, 1479 files, 2026-03-22): discovery overhead 9.58ms per cycle (without filter) vs. 0.25ms (with project filter). Confirms that POLL_INTERVAL=0.5s with a project filter remains the dominant wait time (discovery 0.25ms << 500ms sleep).

### tool_use_cache Orphan Behavior (structural evidence for finding 4)

`dev/pipeline/memory_profile/01_reports/cache_growth_20260322_152818.md` (script: `dev/pipeline/memory_profile/01_cache_growth.py`, dataset: session `35ca8892`, 357 messages): 1 orphaned entry after 357 messages (a Bash call without a tool_result). The `buffered_subagent_calls` section is not in the report — the test session contained no subagents. Structurally analogous behavior to `tool_use_caches`.

### Unknown Types / Warnings Coverage (RETIRED — finding 5)

`dev/pipeline/format_stability/01_reports/unknown_types_20260322_152802.md` (script: `dev/pipeline/format_stability/01_unknown_types.py`, dataset: 1479 files, 222,636 lines, 2026-03-22): 5 real-world unknown top-level types found (8.1% unknown without a filter). Evidence that the warnings loop detected real cases — historically correct, the feature has since been removed. The dev script remains. Format inspection now happens via the proxy pane (full forwarded payload visible).

Findings 2 (workers-loop 6-step), 3 (state table), 6 (`filter_sessions_by_mode`), 7 (token-profiling globals), 8 (logging 0) are code-read-derived — no dev/ benchmark backing.

## Recommendation (target state)

Pending — needs evaluation.

## Open Questions

- `buffered_subagent_calls` still has no TTL cleanup (remains open)

## Sources

- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: token counts ~2x too low in JSONL (affects `turn_usage_accumulator`)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (no official monitoring API)
