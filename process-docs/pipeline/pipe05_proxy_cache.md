# Pipe Section: Proxy Cache-Control

## State as of this section's audit

### Proxy Modification Pipeline

`proxy_addon.py` intercepts all API requests via mitmproxy and modifies the payload before sending:

1. `apply_modification_rules()` — content modifications:
   - **SR strip via template catalog (commit e1a3b9a, 2026-04-21):** `strip_sr.py` matches 11 distinct SR templates via an exact startswith identifier instead of a greedy regex. Templates: `task-tools-nag`, `pyright-diagnostics`, `deferred-tools`, `user-interrupt`, `system-notification`, `file-modified`, `claudemd-contents`, `date-changed`, `skills-available`, `agent-types`, `plan-mode`. Operates on all 4 content shapes: top-level string, `text` blocks in a list, `tool_result.content` (string), `tool_result.content` (list of text sub-blocks). The predecessor version (greedy regex `<sr>.*?</sr>`) had a false-positive bug — it matched across code literals like `if "<system-reminder>" in text:` and removed real Python code from payloads. Replay over 22 historical JSONLs (~37k strips): 0 false positives with the new template-based code (previously ~970 FPs).
   - **Env-context SR strip (commit a26f83a, 2026-05-30):** `strip_sr.py::_apply_sr_strip._replace` checks, before the `_PRESERVE_PREAMBLE` guard, via `_ENV_CONTEXT_RE.fullmatch(inner)` whether the SR block matches the CC-injected userEmail/currentDate block. On a match → full strip (`return ''`). The pre-guard position is mandatory: the env-context block has exactly the same preamble as CLAUDE.md context blocks (`"As you answer the user's questions, you can use the following context:"`), so the `_PRESERVE_PREAMBLE` guard would fire first otherwise. Regex: email literal, date `\d{4}-\d{2}-\d{2}`, whitespace before IMPORTANT via `\s+` (tolerates CC indentation changes), the rest of the text literal. `re.fullmatch` ensures only the exact block (not CLAUDE.md context with the same preamble) matches. The strip flows into the existing `_apply_final_sr_pass` (`stripped_all_sr`/`stripped_all_sr_msg0` mod). strip_vocab.py rule `'ENV'` added: marker `"As you answer the user's questions, you can use the following context:\n# userEmail"` — enables fn-materialization via `attribute_chunk` for dual-log attribution.
   - **6 strip_vocab.RULES additions (2026-06-04):** attribution-coverage analysis (dev/proxy_dual_log/attribution_coverage.py) identified 6 categories that showed up in strip logs but had no RULES marker → a residual gap. Now fixed: `ENV` (new rule, `_apply_final_sr_pass`), `HP` (new rule, `stripped_hook_error_prefix`, `_apply_hook_prefix_strip`), `SN` (new rule, `_apply_final_sr_pass`), `FM` (new rule, marker ` was modified`, `_apply_final_sr_pass`), `UI` rule: secondary marker `IMPORTANT: After completing your current task` added (UI_PARTIAL strips), `CMD` rule: marker `The date has changed.` added (DATE_SR strips). All now addressable in `attribute_chunk`.
   - `removed_plan_mode_sr`: still handled separately (text-block drop on "Plan mode is active")
   - `trimmed_task_notification` (completed) / `replaced_task_notification` (failed): **identical output logic** — both replace the entire `<task-notification>` block with a **single** wake-up block: `_WAKEUP_TEXT` + an optional `Output: <path>` line when the TN contains an `<output-file>` tag. `<summary>` text and the `<status>` line are discarded (not forwarded). Implementation: `_replace_task_notification_tags(old_content, injected_text)` replaces the TN block inline within the existing text block; `_extract_task_notification_output_file(old_content)` extracts the path. Detection via `_top_level_content_contains` (payload_helpers.py) — checks ONLY top-level str/text blocks, does NOT descend into `tool_result` content. The mod-name difference is purely for logging/attribution: `trimmed_task_notification` = completed status, `replaced_task_notification` = failed status.
   - `replaced_bg_completed_text` (`strip_bg_completed.py`): replaces the first CC-native BG-exit notification (plain-text kill-signal format) with `_WAKEUP_TEXT`. Further BG notifications are stripped. Detection guard in `_apply_bg_exit_strip` (rules.py) also via `_top_level_content_contains` — does not descend into `tool_result`. `_strip_bg_exit_notifications` now only traverses top-level `text` blocks, no `tool_result` descent (defense in depth). Prevents a false positive when `Background command "` occurs as DATA in a tool_result.
   - **Wake-up dedup (commit `fcfe6c1`, 2026-05-22):** `_dedup_wakeup_blocks(messages)` runs as the final pass in `apply_modification_rules` after all other modifications. When `replaced_task_notification` AND `replaced_bg_completed_text` (or `trimmed_task_notification` AND `replaced_bg_completed_text`) both fired on the same user message, both independently appended a `_WAKEUP_TEXT` block (TN path in `rules.py::_apply_first_pass`, BGK path in `strip_bg_completed.py`). Dedup collapses to a maximum of 1 wake-up block per message (an `rstrip('\n')` comparison treats both variants — the TN path with `\n`, the BGK path without — as the same signal). Does not touch `stripped_msg_removed` (display invariant — wake-up is not shown as stripped).
   - **BD noise strip (commit 384ced3, 2026-05-30):** `strip_bd_noise.py` removes all informational bd auto-import/export lines from `tool_result` content: `auto-importing N bytes … into empty database`, `auto-imported N issues [and N memories] from …/.beads/issues.jsonl`, `auto-imported N issues into empty database`, `Exported N issues [and N memories] to …/.beads/issues.jsonl`, `auto-export: wrote … to …`, `auto-export: no changes since last export`, `auto-export: throttled (…)`, `auto-export: skipping[…]`, upgrade-recovery variants. `Warning:`/`warning:`-prefixed error messages (auto-export failed/skipped, auto-import: failed to parse) are NOT stripped. Handles the `- ` prefix of the import variants via `^(?:- )?`. Fast-path `_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')` — three markers needed because `auto-imported N issues into empty database` contains neither of the first two. Pass in `rules.py` after `_apply_git_lock_strip`, mod-name `stripped_bd_noise`. strip_vocab.py rule `'BD'` with markers `['issues.jsonl', 'auto-export: no changes', 'auto-export: throttled', 'auto-export: skipping']`.
   - **Git index.lock advice strip (commit a26f83a, 2026-05-30):** `strip_git_lock.py` removes the constant 5-line git advice block (`"Another git process seems to be running in this repository…remove the file manually to continue."`) from `tool_result` content. The block is hardcoded in git's `lockfile.c` — constant across all repos/versions. Preserves the variable line above it (`Warning: auto-export: git add failed: … index.lock … File exists.`). Wired as the `_apply_git_lock_strip` pass in `rules.py` after `_apply_hook_prefix_strip`, mod-name `stripped_git_lock_advice`. Guard via `_content_contains` (descends into tool_result). strip_vocab.py rule `'GL'` with marker `'Another git process seems to be running'`.
   - `stripped_rejection_message`: strips rejection markers from tool_result.content (one of the few legitimate tool_result strip operations)
   - **CC 2.1.176 strips (2026-06):**
     - `stripped_role_system_msg` (`_apply_role_system_strip`, pass 1 / first in `_passes`): replaces the content of every `role=='system'` message with `"."`. CC 2.1.176 delivers the deferred-tools list, agent-types list, and skills list as a standalone `role='system'` message (~9,559 chars, no `<system-reminder>` wrapper) instead of as a `text` block in a `role='user'` message. Idempotency guard: skips empty and already-`"."` messages. Attribution is role-based (not content-marker-based): `_process_messages_section` in `strip_inject_delta.py` assigns `code='RS'` when `om_norm.role=='system'`. strip_vocab.py rule `'RS'` with an empty marker array.
     - `stripped_agent_types_sr` (`_apply_cumulative_sr_strips`, pass 2): strips the `<system-reminder>` block of the agent-types list from `role=='user'` messages on Sonnet workers. Sonnet workers still get agent-types as a standalone user SR (~2,353 chars) instead of in the role=system message. Template `'agent-types'` with identifier `'Available agent types for the Agent tool'` in `strip_sr.py`. strip_vocab.py rule `'AT'`.
     - `stripped_bg_launch_ack` (`_apply_bg_launch_ack_strip` via `strip_bg_launch_ack.py`): replaces the content of a block with the instruction text `'Command is running in the background. Do NOT check, poll, or read its output — just wait until it finishes (you will get a completion notice).'` only when its text (after `lstrip()`) **starts with** the ack prefix `'Command running in background with ID:'` — anchored `startswith` via `_is_bg_launch_ack`, NOT substring-anywhere. A real CC launch-ack always starts with this prefix; a large tool_result or a typed/pasted user message that only contains the phrase as data mid-content is preserved (the FP-nuke fix). The fast-path marker `'running in background with ID'` (`_BG_LAUNCH_ACK_MARKER`) only serves the gate in the caller (`message_passes.py`); the strip decision lives in the anchored prefix. Covers all 4 content shapes (str message, text block, tool_result-str, tool_result-list). strip_vocab.py rule `'BL'`. Pass after `_apply_bg_exit_strip` in `_passes`.
   - **`"Workflow"` in `TOOL_BLOCKLIST` (CC 2.1.176):** CC 2.1.176 brings a new built-in tool `Workflow` with a ~18.5k-char description. Added to `TOOL_BLOCKLIST` in `constants.py` — `_strip_unused_tools` removes it entirely from the payload.
   - `replaced_system_prompt` (`rules.py:103`): replaces the text content of system[2] with the loaded `system_rules` text (global + model + project, via `_load_system2_rules`); `"."` only as a fallback when there are no rules. No `>5000 chars` threshold.

2. `_strip_all_cache_control()` — removes ALL cache_control markers set by Claude Code:
   - system blocks, tools, messages (top-level + content blocks)
   - Then calls `_normalize_user_content_shape()`: user messages whose content, after the strip, is `[{"type":"text","text":"X"}]` (a single text block, exactly `{type,text}` keys) are collapsed to a plain string `"X"`. Background: CC sends user messages natively as a string when no BP sits on them, as a list-with-block when a BP sits on them. Without normalization this produces a byte diff between requests when BP4 moves off a message. See the cache-rebuild-cases process history, case 1 (2026-04-12, commit 0f847b0).

3. `_set_cache_breakpoints()` — sets its own breakpoints (max 4) on the modified payload. **BP layout v3 (2026-04-16, commit dcb6aea + merge):**
   - **BP1 — system[2] (new):** `cache_control` directly on the `system[2]` text block. Prefix ends at sys[2] → sys[3] (CC-injected env: cwd, gitStatus, recent commits) is NOT in the prefix → a cross-session hit survives sys[3] drift (commits, main↔worker cwd difference). Verified: fresh-session REQ#1 CR=61,231 / CC=0 with byte-identical sys[3] between sessions (2026-04-16).
   - **BP2 — Tools End:** the last tool WITHOUT `defer_loading` (defer_loading + cache_control = API error). Caches the whole tools block.
   - **BP3 — Messages last_unchanged:** the last message that did NOT change relative to the previous request (`first_diff_index - 1` on modified content).
   - **BP4 — Messages last:** the last message, last content block — for the next request.
   - **Removed (BP layout v2 → v3):** the tools-anchor for tool growth. Tools in practice do not change within a session, the anchor was rarely active. Slot freed for the sys[2] marker. The `prev_tools_count_by_model` state in `addon.py` removed entirely.

### Context Editing (from 2026-04-17)

`_inject_context_management(payload)` in `src/proxy/inject_helpers.py` injects a `context_management` block into the API payload, when set under `context_management.enabled: true` in `~/.claude/shared-rules/proxy_rules.json`.

Injected block:
```json
{
  "context_management": {
    "edits": [
      {
        "type": "clear_tool_uses_20250919",
        "trigger": {"type": "input_tokens", "value": 100000},
        "keep":    {"type": "tool_uses",    "value": 5},
        "clear_at_least": {"type": "input_tokens", "value": 10000}
      },
      {
        "type": "clear_thinking_20251015",
        "keep": {"type": "thinking_turns", "value": 2}
      }
    ]
  }
}
```

**Strategy `clear_tool_uses_20250919`:** deletes old tool-result content server-side once > 100k input tokens have accumulated. Keeps the last 5 tool uses. Minimum-clear amount of 10k tokens per clearing event (ensures the cache-invalidation overhead pays off).

**Strategy `clear_thinking_20251015`:** deletes old thinking blocks, keeps only the last 2 thinking turns.

**Beta header:** no manipulation. CC's `anthropic-beta` header passes through the proxy unchanged. The earlier logic (strip `interleaved-thinking-2025-05-14`, add `context-management-2025-06-27`) was removed — the rationale, a full flag analysis (14 flags), and the verdict are recorded in the proxy-header-mods process history (research result resolved).

**Logging:** `entry["context_management_injected"]: bool` in every proxy-log entry. `"injected_context_management"` in the `modifications` list when applied.

**Cache interaction:** per the API docs, tool-result clearing invalidates the cached-prompt prefix as soon as content is deleted. `clear_at_least: 10000` ensures at least 10k tokens are deleted per event — makes the invalidation overhead amortizable. The 100k-input-token trigger is conservative: short sessions (<100k) are entirely unaffected.

**Configuration:**
```json
// ~/.claude/shared-rules/proxy_rules.json
{
  "context_management": {
    "enabled": true,
    "clear_tool_uses": {"enabled": true, "trigger_input_tokens": 100000, "keep_tool_uses": 5, "clear_at_least_tokens": 10000},
    "clear_thinking": {"enabled": true, "keep_thinking_turns": 2}
  }
}
```

### Project Rules in sys[2] (from the proj-rules-to-sys2 refactor, 2026-04-16)

`_load_system2_rules(model_family, project_path)` has loaded three layers since this refactor:

1. **global** — `system2_rules.global.files` (always, except exclude_projects)
2. **model** — `system2_rules.opus.files` or `system2_rules.worker.files`
3. **project** — `system2_rules.projects.<name>.files` when `path_contains in project_path`

Concatenation: `"\n\n".join(parts)` — deterministic order global → model → project. The result lands in `system[2]`, which is cached by BP1.

After this refactor, `msg[0]` contains **only user input**: as the final pass in `apply_modification_rules`, `_strip_all_system_reminders()` removes all remaining `<system-reminder>…</system-reminder>` blocks from `messages[0]` (provided `role == "user"`). Modifier: `"stripped_all_sr_msg0"`.

**Expected cross-session cache effect:** a 2nd fresh session within the TTL (55min): CR ≥ 55k / CC ≤ 3k (vs. pre-refactor CR=41k / CC=20k). Reason: project rules now sit in the sys[2] prefix of the BP1 cache region and are cached cross-session, instead of drifting session-specific into msg[0].

### State Tracking

`self.prev_messages_by_model` stores message summaries of the **modified** payload (not the original). Separated by model_family ("opus" / "haiku"). The BP3 computation compares the current modified messages with the previous modified messages via `_compute_diff()`.

### Worker Isolation

Every worker in a worktree gets its own mitmproxy process on its own port with its own log file. Implemented in `tmux_spawn.sh` (iterative-dev plugin):
- The worker discovers the proxy via `/tmp/.monitor_cc_proxy_<session_hash>`
- Hash based on the project path (the worktree suffix is stripped → same hash as the main)
- Its own port (next free one from main-port + 1)
- Its own log file: `api_requests_<worker_session_id>.jsonl`
- Cross-project workers (a different project than the main) get no proxy — the marker only exists for the main project

### Marker Lifecycle

Per-project marker files let the monitor (and workers in worktrees) discover the active proxy's
port and log_id without polling:

| File | Lines | Written by |
|---|---|---|
| `src/logs/.proxy_session_<sid>` | 1=port / 2=log_id / 3=owner_pid | `claude_proxy_start.sh` at session start |
| `/tmp/.monitor_cc_proxy_<sid>` | 1=port / 2=log_id / 3=root / 4=owner_pid | same |

`sid` = first 8 chars of MD5(`project_path`) — matches `_proxy_session_id_for_project()` in
`forwarded_parser.py`.

**Write guard** — `_proxy_pid_is_live()` (defined in `claude_proxy_start.sh`) is the primary
staleness check: `kill -0 <pid>` (process exists?) AND `ps -p <pid> -o args=` contains
`claude_proxy_start.sh` (identity check prevents PID-reuse false-positives — same bug class as the
retired port-listening guard). Belt-and-suspenders: alive PID must also have log mtime < 60s.
Old markers without PID line: fall back to mtime-only (safe rollout). New session claims the marker
only if the previous owner's PID is dead or identity-mismatched.

**Heartbeat** — `_marker_heartbeat` runs in background every 10s after proxy starts. If the
marker is missing or its stored PID is dead/unrelated, the secondary session reclaims it. Max
blindness window after primary exits without cleanup: ~10s. `$$` in the heartbeat subshell = parent
shell PID (bash spec).

**Cleanup guard** — `cleanup()` removes markers only if `marker_pid (line 3/4) == $$`. A parallel
session that reclaimed the marker via heartbeat has its own PID on those lines — the exiting
session skips the rm and leaves the reclaimer's marker intact.

**Read side** — `parse_proxy_log_forwarded()` reads `lines[1]` (log_id) — unchanged by the
3-line/4-line format extension. No changes to the Python read path.

### count_tokens Passthrough

`_is_messages_request()` in `src/proxy/addon.py` matched, as of 2026-05-29, exactly on `/v1/messages` + an optional query string:
```python
path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?")
```
Before: `path.startswith(MESSAGES_PATH)` — also matched `/v1/messages/count_tokens?beta=true` → `_inject_model_override` injected `max_tokens` → API 400. Now: count_tokens requests run COMPLETELY unmodified through. No stripping, no inject, no log entry in `api_requests_*.jsonl`.

### Model Override

`_inject_model_override(payload, model_family)` in `src/proxy/inject_helpers.py` injects `model`, `effort`, `max_tokens`, and `thinking` from `~/.claude/shared-rules/proxy_rules.json` blocks `model_override` (main/opus) and `model_override_worker` (sonnet).

| Param | Opus (`model_override`) | Worker (`model_override_worker`) |
|---|---|---|
| `model` | `claude-opus-4-8` | `claude-sonnet-4-6` |
| `effort` | `xhigh` | `high` |
| `max_tokens` | `128000` | `64000` |
| `thinking` | adaptive + omitted | adaptive + omitted |

Guard: `_is_messages_request()` in `addon.py` restricts injection to the exact `/v1/messages` path (+ optional query string) — count_tokens requests pass through unmodified (see "count_tokens Passthrough" above). The `64000` value reflects `proxy_rules.json` as of this audit, after a correction from 128000 (the Sonnet 4.6 ceiling; see the model-override-limits process history).

### 4xx Error Logging

`ProxyAddon.response()` writes 4xx errors as a single JSONL line into `src/logs/api_errors.jsonl` (rolling, 7-day retention via `cleanup_old_jsonl`). Fields: `ts`, `status_code`, `error_response`, `request_url`, `request_payload`. Before: a separate file `api_error_payload_<ts>.json` per error.

### Log Pipeline

```
Main Session → mitmdump :8084 → proxy_addon.py → api_requests_opus_<project>_<timestamp>.jsonl
Worker (Worktree) → mitmdump :8085 → proxy_addon.py → api_requests_worker_<name>_<timestamp>.jsonl
4xx Errors (both) → api_errors.jsonl (rolling, 7d retention)
```

All write to `$MONITOR_CC_ROOT/src/logs/`. The monitor reads the right log per `session_id`.

Additionally, `addon.py` writes six additive logs to `src/logs/dual_log/` (subfolder, auto-created):
- `api_requests_<log_id>_original.jsonl` — the raw CC payload BEFORE any modification (`payload` before `apply_modification_rules`). Fully cumulative, each request complete. `model` = the CC-requested model before override.
- `api_requests_<log_id>_forwarded.jsonl` — **delta log** (`type: forwarded_delta`). REQ#1 is full (`is_first: true`), from REQ#2 on only changed/new elements via a per-element content-hash diff (system/tools/messages separately). Hash comparison normalized in two stages: (1) `cache_control` stripped recursively (`_strip_cache_control`) → BP3/BP4 movement produces no spurious delta; (2) message shape normalized (`_normalize_msg_shape_for_hash`) — single-text-block list `[{type,text}]` → plain string, mirrors `cache._normalize_user_content_shape` exactly → a BP-induced shape flip produces no spurious delta. The written content retains markers and the real shape. Self-healing hash chain: `prev_delta_hashes_by_model` is only updated after a successful write. Entry fields: `type`, `request_id`, `timestamp`, `model` (post-override), `is_first`, `counts` (total system/tools/messages), `system_delta`/`tools_delta`/`messages_delta` (only changed/new indices as a dict), `anthropic_beta` (the full list of CC beta-feature flags from the HTTP request header `anthropic-beta`, empty if the header is absent), `context_management` (body-field passthrough, None if absent), `diagnostics` (body-field passthrough, None if absent). `model` = the possibly-overridden value after `_inject_model_override`.
- `api_requests_<log_id>_stripped.jsonl` — **delta log** (`type: stripped_delta`). What the proxy REMOVED from the original payload (present in original, not in forwarded). Written in the `response()` hook after the upstream send (zero forwarding latency). Diff via `_build_stripped_injected_deltas` (in `logging.py`) + the `diff_engine.py` engine; both payloads are normalized before the diff via `_strip_cache_control` → BP repositioning produces no spurious strip; user messages additionally normalized via `_normalize_msg_shape_for_hash` → json-reserialization false positives (string vs. block-list from `_set_cache_breakpoints`) eliminated. Full payload diff: covers system/tools/messages AND all top-level fields (`_diff_top_level_fields`) — the model override correctly shows up as `fields_delta["model"]`. Delta encoding: a per-location hash chain (`loc_key → MD5[:10]` of the span texts via `_hash_spans`), state in `prev_stripped_hashes_by_model` (keyed by model_family). Stable strips (identical sys[2] rules) appear only in the first request. **fn_map (new):** a top-level dict `{loc_key → fn_name}` — the responsible function per strip entry, AT WRITE TIME via `_attribute_chunk` (messages), `_SYS_FN`/`_FIELD_STRIP_FN`/tool-shape (other sections). Old entries without fn_map are read-side-safe (the field is simply absent).
- `api_requests_<log_id>_injected.jsonl` — **delta log** (`type: injected_delta`). What the proxy ADDED to the forwarded payload (present in forwarded, not in original). State in `prev_injected_hashes_by_model`. `fields_delta["model"]` contains the override target model. Logically non-redundant with original/forwarded: the classification "this was injected" is not persisted anywhere else. **Span format (Stage 1):** `system_delta[idx]`, `messages_delta[midx][bidx]`, `tools_delta[name]["desc"]` store ordered span lists `[[tag, text], ...]` with tags `"equal"` / `"injected"` (instead of flat text lists). Only blocks with ≥1 `injected` span are written. Equal spans = context anchors (inline render: equal=DIM, injected=DIM_GREEN_BG). Hash via `_hash_span_sequence()` (namespace key `tag:text|...`). `fields_delta` and `tools_delta[name]["whole"]` unchanged. Backward compat: old-format entries (item[0] = str) vs new format (item[0] = list) via `isinstance(val[0], (list, tuple))`. **fn_map (new):** like stripped; inject-side messages via the `"background done"` check (→ `_apply_bg_exit_strip`) or the `_attribute_chunk` fallback; fields via `_FIELD_INJECT_FN` (incl. `context_management → _inject_context_management`).
- `api_requests_<log_id>_errors.jsonl` — derived tool-error log. `is_error=True` tool_result blocks from the original payload, deduped by `tool_use_id` per model_family, written in the `request()` hook. Format: `{ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file, request_id}`.
- `api_requests_<log_id>_response.jsonl` — response HTTP-header log. Written in the `responseheaders()` hook for ALL status codes (no 2xx gate — 429 `retry-after` must be captured). Filtered via `_filter_response_headers` (exact: `request-id`, `retry-after`, `anthropic-organization-id`; prefix-match: `anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`; keys normalized to lowercase). Entry fields: `flow_id`, `timestamp`, `request_id` (from the response header `request-id`), `status_code`, `headers` (filtered dict). Correlated to all other logs via `flow_id`. Writer handle: `self.response_log_file = _resolve_dual_log_file("response")`.

All six writes each in their own `try/except` — errors never affect forwarding or the main log. `_stripped`/`_injected` are written by the `response()` hook (metadata bridge: `mc_original_payload`, `mc_modified_payload`, `mc_model_family` on `flow.metadata`). Janitor rotation: all `dual_log/` files of one log_id rotate together, suffix-aligned — after the main-log rotation (count-30 opus/worker), all `dual_log/api_requests_*.jsonl` without a matching `log_id` are deleted. Implemented in `_janitor_cleanup_jsonl_logs()` (`claude_proxy_start.sh`); all six suffixes in `_LOG_REGISTRY` (`log_janitor.py`) with `retention="count-30"`, `janitor_trigger="proxy-start-bash"`.

**Correlation key:** all six dual-log entries carry `"flow_id": flow.id` — mitmproxy's stable per-flow UUID, identical across all hooks. `request_id` in `_response` comes from the Anthropic response header `request-id` (directly available in `responseheaders()`). `flow_id` is the read-side join key for all six logs.

### Tool Stripping (TOOL_BLOCKLIST)

`TOOL_BLOCKLIST` (frozenset) in `constants.py:124-146` removes 27 unused tools from the `tools` array before the API send. ~25k fewer chars per request (incl. ~18.5k Workflow description as of CC 2.1.176). `Agent` has been in `TOOL_BLOCKLIST` since the refactor (`constants.py:137`) → fully stripped; the earlier git-committer-only description trimming no longer exists.

### Live-Copy Isolation

`claude_proxy_start.sh` copies `proxy_addon.py` to `$LOG_DIR/.proxy_addon_live.py` at start. mitmproxy loads the copy. Git merges to the original trigger no hot reload. Cleanup on proxy stop.

### Log Naming & Rotation

Log files: `api_requests_{project_name}_{timestamp}.jsonl` instead of cryptic MD5 hashes. Max 30 files, oldest deleted at proxy start.

### Session-State Fixation (from commit feat/prefix-hash-instrumentation)

`ProxyAddon` holds a `self.fixated: dict` (keyed by model_family). Purpose: the sys[2] and msg[0] project-rules block are frozen after the **first request** of a proxy session. All subsequent requests get byte-identical bytes for these fields — regardless of whether the underlying rule files change on disk.

**Why only model_family as the key:** the proxy process lives for one session. Model family is the only split factor (opus vs. sonnet vs. haiku loads different rules). On a proxy restart, `self.fixated` resets — the first request loads fresh.

**What gets fixated:**
- `sys2_text` — the text content of `system[2]` after `apply_modification_rules()`. That is the content `_load_system2_rules()` produces (global + model-specific rule files).

**What does NOT get fixated:**
- sys[0], sys[1], sys[3] — controlled by Claude Code, untouched
- messages[1..N-1] — session-volatile by design
- tools[] — append-only, untouched

**Implementation:** orchestration in `addon.py`, helpers `_capture_fixation` / `_apply_fixation` live in `src/proxy/fixation.py` since the 2026-04-19 refactor. No change to `rules.py`. After `apply_modification_rules()`, either a capture happens (first request) or `_apply_fixation()` overwrites the bytes (subsequent requests). `apply_modification_rules()` always runs fully (no short-circuit) — the overhead is minimal (mtime-based file caching in `_read_rule_file()`), the bytes are overwritten afterward.

**Edge cases:**
- Content `"."` (messages emptied after stripping) — no `</system-reminder>` marker, `_capture_fixation` stores nothing, `_apply_fixation` changes nothing, no crash.
- Haiku (model_family="haiku") — `_load_system2_rules` returns `""` → sys[2] becomes `"."`. Fixation is stored for Haiku too (with `"."`) so the second request doesn't diverge due to file-mtime changes.

### API Constraints (Reference)

- Max 4 breakpoints per request
- `defer_loading=true` and `cache_control` on the same tool = API error
- Min cacheable prefix: 2048 tokens (Opus) / 1024 (Haiku)
- A cache write costs 125% of the tokens — wrong placement can be more expensive than no caching
- `cache_control` marker: `{"type": "ephemeral"}` (no TTL needed, the API decides)
- `scope: "global"` — content-based cache across sessions/API keys. Same content = cache hit, different content = separate entries. No cross-contamination between Opus and worker.

### Tool Injection

Before this change: `tools[]` fully controlled by Claude Code. MCP schemas loaded lazily via ToolSearch (alphabetical insert into the middle of the tools array). Deferred built-ins (CronList, ListMcpResourcesTool etc.) appear mid-session via CC's deferred-tool lifecycle. Both mechanisms cause mid-session `tools[]` mutations that break the byte prefix before BP2 → cache rebuilds (see the cache-rebuild-cases process history, case 4, Tool INSERT subsection).

Current implementation: the proxy takes full deterministic control of `tools[]`:
- `ToolSearch`, `ScheduleWakeup`, `Monitor` added to `TOOL_BLOCKLIST` → stripped from every request
- CC deferred built-ins already in the blocklist (TaskCreate, CronCreate, AskUserQuestion etc.)
- `src/proxy/tool_injection.py` injects MCP schemas: iterative-dev always from REQ#1, other plugins appended when activated via the `activate_plugin` MCP tool (iterative-dev/blank server.py)
- Schema store at `src/proxy/schemas/<plugin>/<tool>.json` populated by `dev/tool_injection/01_extract_schemas.py` — a one-time extraction via FastMCP introspection per plugin
- Append-only injection logic: iterative-dev first, active plugins in activation order, stable alphabetical within each plugin block
- `active_plugins` tracked in `ProxyAddon.fixated` for session-stable behavior; explicit `activate_plugin` calls emit an `"active_plugins_changed"` modifier (a one-time controlled rebuild by design)

**Update 2026-04-14 (evening) — Research Plugins Converted to Skill+CLI:**

The scope of tool injection **narrowed**: on 2026-04-14 the 4 research plugins `github-research`, `reddit`, `arxiv`, `rag` were converted from MCP servers to pure Skill+CLI plugins (43 tool schemas removed from the API prefix). Each got a `cli.py` entry point; `server.py` + `mcp-start.sh` deleted; the `plugin.json` `mcpServers` block removed.

Consequences for tool injection:
- `tool_injection.py` now only handles `iterative-dev` (4 tools) — the only remaining MCP plugin
- `active_plugins.json` effectively stable at `{"plugins":["iterative-dev"]}` — no activation flow for research plugins because they have no MCP tools to inject
- The dynamic `activate_plugin` MCP tool becomes an edge case (still exists for theoretical future MCP plugins)
- First Opus REQ tools count: 7 built-ins + 4 iterative-dev = **11** (previously 31+ with research plugins injected)
- Schema bytes per request: ~2k (previously ~13k)
- Research plugin tools are now invoked via `Bash(<plugin>/.venv/bin/python <plugin>/cli.py <cmd> ...)` — zero prefix cost, documented in each plugin's SKILL.md

Affected commits (per repo):
- `github-research` v1.1.0 — commit `37807a3`
- `reddit` v1.1.0 — commit `381f97e`
- `arxiv` v1.1.0 — commit `8b89e08`
- `rag` v1.1.0 — commit `909375d`

### Pane RAM (Phase 2a concluded 2026-04-29)

Four levers implemented + merged to dev:

**(1) Lazy-msg-strip + lazy-reload (commit cf8037c, 2026-04-29).** `src/proxy_display/parser.py` stamps `entry['_byte_offset']` per line during parsing. `_lazy_load_messages(entry, log_path)` re-populates `entry['messages']` on demand via `seek(offset) + readline()`. Pane modules (proxy, worker_proxy) drop, after every `extend()`, the `messages` list from entries that are NEITHER in the last 10 NOR actively expanded — `_strip_inactive_messages()` checks three expand-key forms (`entry_idx`, `('req', N)`, `(N, 'neg_delta')`). The click handler triggers `_lazy_load_messages` for the entry + prev_same on expand. This solves the O(N²) growth caused by cumulative Anthropic wire-format messages. Constant: `PROXY_MESSAGES_KEEP_LAST = 10` in `src/constants.py`.

**(2) tracemalloc env-var gate (commit 10f110a, 2026-04-29).** `src/ram_audit/instrument.py` activates `tracemalloc.start(25)` only when `MONITOR_CC_RAM_AUDIT=1` is set. Default off → no 2-5x CPU overhead per Python allocation in the proxy-pane render loop. Lag/flicker in the proxy pane was primarily caused by this.

**(3) Warnings tail-bytes (commits 2ffe9b9 + 166b18b + 47a4415, 2026-04-29).** `src/panes/warnings_pane.py` sets, in the site-A reset block, `_proxy_log_position = max(0, fsize - WARNINGS_INITIAL_TAIL_BYTES)` instead of 0. `WARNINGS_INITIAL_TAIL_BYTES = 50_000_000` in constants.py. `scan_worker_logs` in parser.py accepts two params: `tail_bytes` (for first-time-seen worker logs) and `min_mtime` (skip worker logs with mtime < `_monitor_start_ts`). With this, warnings only parses the last 50 MB of the main proxy log + fresh worker logs from the running session — old worker logs from earlier sessions are skipped entirely.

**(4) Subprocess parse for the initial parse (commit c3d69ed, 2026-04-29).** `_parse_log_file_isolated` and `parse_proxy_log_isolated` in `src/proxy_display/parser.py` spawn, for `last_position == 0`, a child process via `multiprocessing.get_context('spawn')`. `_subprocess_worker` parses in the child, drops messages pre-IPC, sends entries + new_position + pending_rids via a queue. The parent rebuilds pending_by_rid via an RID-set lookup (not via pickle copies). Child exit returns all pages to the OS → the ~3 GB initial-parse peak no longer sits in the parent process. Falls back to an in-parent parse on crash, timeout (default 60s, `SUBPROCESS_PARSE_TIMEOUT` env-overridden), or IPC-pickle failure. Active caller sites: `pane.py`, `worker_proxy_pane.py`.

## Evidence

### Cache-Rebuild Analysis (session a3b6577a)

Script: `dev/session_analysis/04_cache_validation.py` (stdout-only, no persistent report MD). Dataset: proxy log `src/logs/api_requests_f93afc17.jsonl` (825MB, 2026-04-08) + session JSONL `a3b6577a-8f2c-4cef-a594-15aa18c0f520.jsonl`. 148 requests with modifications:

- **98%** of requests had modifications BEFORE the breakpoint
- 4 cache rebuilds: REQ#0 36k CC (expected), REQ#1 27k CC (ToolSearch), REQ#70 93k CC / 9k CR (91% rebuild), REQ#133 162k CC / 9k CR (95% rebuild)
- 9,297 CR at REQ#70 + #133 = exactly the `system[2]` breakpoint — everything after it (tools + 100+ messages) rewritten
- Total cost: 319k tokens for rebuilds (2% of the total, 162k = ~6% of the session limit for one request)

**Critical:** proxy modifications change messages that sit BEFORE the cache_control breakpoint. The API sees modified content → prefix mismatch → cache invalidated.

### Fix Verification

Script: `dev/session_analysis/04_cache_validation.py` / `02_cache_timeline.py` (stdout-only, no persistent report MD). Dataset: a test-project session (14+ requests):

- REQ#2: CR:0, CC:30.478 (first request, expected)
- REQ#3–#14: all CR >30k, CC only 150–1200 (new content)
- **Not a single rebuild** — not even for ToolSearch (REQ#8: CC:425)
- BP3 prevents cache invalidation: the modified content is deterministic → the prefix stays stable between requests

### Tool Injection Evidence

Script: `dev/session_analysis/04_cache_validation.py` (stdout-only). Dataset: `api_requests_opus_monitor_cc_1776099723.jsonl`: REQ#2 → REQ#3 rebuild as a result of a tool INSERT (ToolSearch load). Detailed in the cache-rebuild-cases process history, case 4 (Tool INSERT subsection).

Stage 3 live verification — was pending the next session at the time.

### Pane RAM KPIs (2026-04-29)

Script: `dev/ram_audit/dump_all.sh` (SIGUSR1 → per pane-PID file, format documented in `dev/ram_audit/DOCS.md`). Dataset: "final dump_all post-restart 2026-04-29". Dumps under `dev/ram_audit/dumps/` (gitignored):

| Pane | Baseline 04-28 | Final 04-29 | Reduction |
|---|---|---|---|
| proxy | 1,151 MB | 504 MB | -56% |
| worker_proxy | 385 MB | 170 MB | -56% |
| metadata | 1,304 MB | 465 MB | -64% |
| worker_metadata | 370 MB | 156 MB | -58% |
| main | 1,131 MB | 1,043 MB | -8% (out of scope) |
| warnings | 2,856 MB | 690 MB | -76% |
| **Total** | **7,497 MB** | **3,208 MB** | **-57%** |

Subjective: lag/flicker in the proxy pane fully gone (the source was tracemalloc overhead, not RAM). RSS warnings 2,856 → 506 MB (-82%) live-verified after lever 3.

### Tokenizer Approximation (chars/token)

`dev/session_analysis/04_reports/20260416_222700_token_ratios.md` (script: `dev/session_analysis/06_char_token_ratio.py`, proxy log: `api_requests_opus_monitor_cc_1776359177.jsonl`, session: `48273804-df12-42e1-bd5f-dd64fe734f48.jsonl`, 2026-04-16):

- Known prefix anchor: **154,550 chars → 41,975 tokens = 3.68 chars/token**
- Full-rebuild ratio (CR=0): 3.42 chars/token (N=0 in this session; N=3 across several historical sessions, stddev 0.11)
- 84 message-delta data points; median 0.53 chars/token (delta-only, not usable for prefix calculation)
- Stable ~3.4–3.7 across sessions without interleaved thinking

**tiktoken cl100k_base is unusable** — underestimates Claude's tokenization by 35–75% (varies with the thinking share). Don't use it for proxy decisions.

**Caveat:** per-segment ratios (sys vs tools vs messages separately) are NOT extractable with current data (sys/tools are constant per session = no variance for regression). The 3.68 value is prefix-dominated (sys+tools make up 95% of the payload) and counts as a "good enough" overall approximation.

Details + experiments + paths forward: the tokenizer-baseline process history (parked).

### Model Override Limits

Per-model max output (synchronous Messages API):

| Model | Max output |
|---|---|
| Opus 4.8 | 128,000 |
| Sonnet 4.6 | 64,000 |
| Haiku 4.5 | 64,000 |

Source: `monitor-cc-reference`: `about_claude_models_overview.md` (Max output row), `extended_thinking.md`. Note: 300k is Batches-API-only (`output-300k-2026-03-24`).

`max_tokens` schema (`monitor-cc-reference`: `api_messages_create.md`): `minimum: 0`, no max enforced; `stop_reason: "max_tokens"` = "exceeded requested `max_tokens` or the model's maximum" → the API clamps to the ceiling. Evidence: Sonnet workers ran `max_tokens=128000`, zero 400s; the schema enforces no upper bound. Caveat: "clamp" is inferred from the stop_reason wording + no-400; the docs contain no literal clamp statement.

Effort levels (`monitor-cc-reference`: `effort.md`): `low < medium < high < xhigh < max`. `high` = "exactly the same behavior as omitting the effort parameter". `xhigh` Opus 4.8 / 4.7 ONLY. Sonnet ceiling = `max`; Sonnet recommended default = `medium`. No beta header required for the effort param.

Full investigation trail: the model-override-limits process history.

## Recommendation (target state)

Keep (no change needed) — the proxy's own breakpoints are implemented and verified. TTL `1h` and `scope: "global"` correctly set on markers.

### Global Rules Caching

Change: hook-injected rules (78k chars, `SessionStart hook additional context:`) are extracted from MSG[0] and inserted as their own system block with `scope: "global"`. System-block position: after system[2] (stripped), before dynamic content (gitStatus). BP1 targets the rules block instead of the last system block.

Expected impact: ~25-30k tokens CR instead of CC from the 2nd request of every session onward. Cross-session cache hits on unchanged rules. Cross-model: Opus + worker with the same rules → cache hit.

### Rejection Message Stripping

Change: ESC-abort tool_result messages ("The user doesn't want to proceed with this tool use...") are shortened to `"."`. Marker: the `_REJECTION_MARKER` constant.

### Agent-Tool Trimming — SUPERSEDED

Superseded: the earlier description trimming (Agent stays in the tools array, ~10k → ~300 chars git-committer-only) was replaced by full blocklisting. `Agent` now sits in `TOOL_BLOCKLIST` (`constants.py:137`) → stripped entirely from the payload. No more trim code exists.

### Session-Guidance Stripping

Change: the `# Session-specific guidance` section removed from system[3→4]. `# Environment`, `# Language`, `gitStatus` are preserved.

### Worker Proxy Live-Copy

Change: worker proxies now also use a live copy (`.proxy_addon_worker_{name}.py`). Prevents a hot reload on git merges to proxy_addon.py. Fixed in the iterative-dev plugin's `tmux_spawn.sh`.

### Proxy Log Naming

Change: main logs are named `api_requests_opus_{project}_{timestamp}.jsonl`, worker logs `api_requests_worker_{name}_{timestamp}.jsonl`. Clear separation between Opus and worker proxy logs.

### Tool Injection (Deterministic Control)

Change: the proxy takes full deterministic control of `tools[]`:
- `ToolSearch`, `ScheduleWakeup`, `Monitor` added to `TOOL_BLOCKLIST` → stripped from every request
- CC deferred built-ins already in the blocklist (TaskCreate, CronCreate, AskUserQuestion etc.)
- `src/proxy/tool_injection.py` injects MCP schemas: iterative-dev always from REQ#1, other plugins appended when activated via the `activate_plugin` MCP tool
- Schema store at `src/proxy/schemas/<plugin>/<tool>.json` populated by `dev/tool_injection/01_extract_schemas.py` — a one-time extraction via FastMCP introspection per plugin
- Append-only injection logic: iterative-dev first, active plugins in activation order, stable alphabetical within each plugin block
- `active_plugins` tracked in `ProxyAddon.fixated` for session-stable behavior

### Model Override — max_tokens

Change applied: worker `max_tokens` 128000 → 64000 (Sonnet 4.6 ceiling). Opus 128000 kept (= Opus 4.8 ceiling, exact). Source: `monitor-cc-reference` `about_claude_models_overview.md`.

### Model Override — effort

Keep: worker `high`, opus `xhigh`. No change. `high` = default (deliberate); `xhigh` valid on Opus 4.8 only — must NOT be set on Sonnet.

### anthropic-beta Headers

Keep: ALL 14 flags pass through unmodified, no manipulation. Per-flag research resolved in the proxy-header-mods process history. Conclusion: no flag worth stripping — each is auth-critical, feature-active, cost-relevant, or correctness-sensitive.

## Open Questions

- Long-term stability: behavior on sessions >500 requests not yet observed
- Claude Code updates could change cache_control handling (e.g. more than 2 own breakpoints) — `_strip_all_cache_control` removes everything, so it is robust against changes
- Global rules caching: verify `scope: "global"` on the proxy's own system blocks — test the cross-session cache hit (same rules, new session → CR instead of CC?)
- Whether CC dispatches `tool_use` calls for proxy-injected MCP tools whose MCP client is still connected but which were never client-side loaded via ToolSearch. Stage 0 (hardcoded bead_list) already passed in a prior session; Stage 3 tests this for the full iterative-dev schema set and github-research via `activate_plugin`.
- `claude_proxy_start.sh` integration: at the time, the schema store was populated manually via `01_extract_schemas.py`. Next step is to run the extractor automatically in the proxy startup script.
- **The main pane at 1043 MB** — the largest remaining consumer. Not caused by the proxy_display path but by `core/monitor.py`, which parses session JSONLs from `~/.claude/projects/**/*.jsonl` (its own code path). Follow-up: a subprocess-parse pattern for session-JSONL parsing analogous to the proxy-pane solution.
- **Periodic pane respawn / pymalloc accumulation** — the subprocess-parse pattern only solves the initial peak in the parent. Ongoing incremental allocations accumulate pymalloc pages over hours. Observed: proxy 506 → 624 → 749 MB within hours. Follow-up: periodic pane self-respawn OR the subprocess pattern also for incremental parses.

## Sources

- Anthropic API docs: prompt caching (cache_control semantics, breakpoint limits)
- The cache-rebuild-cases process history, case 4 (Tool INSERT subsection)
