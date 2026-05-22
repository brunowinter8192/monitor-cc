# src/proxy/

## Role

mitmproxy addon package. Loaded at proxy startup via `src/proxy_addon.py` (thin `-s` entry point).
Intercepts every POST `/v1/messages` request from Claude Code, applies a deterministic modification
pipeline (rule injection, content stripping, MCP tool injection, fixation, cache marker placement),
logs the result, and forwards the modified payload to Anthropic. Touch this package when changing
what gets injected, stripped, or cached. Do NOT edit files here during a live proxy session —
the running proxy uses a frozen copy in `src/logs/.proxy_live_<id>/proxy/`. See Gotchas.

## Public Interface

`__init__.py` is a package marker only — no exports. External callers use `src/proxy_addon.py`
which mitmproxy loads via `-s` flag.

## Flow

mitmproxy `http.HTTPFlow` (POST /v1/messages) → `addon.ProxyAddon.request()`
→ `schema_check` (drift detection) → `rules` (system2 + project rule injection, content strip)
→ `fixation` (freeze sys[2] + msg[0] after first request) → `tools` (blocklist strip)
→ `tool_injection` (MCP schema append) → `inject_helpers` (model override, context management)
→ log entry written → `cache` (strip all markers, set BP3/BP4/anchor) → `hash_meta` (sent_meta log)
→ modified payload forwarded to Anthropic

## Modules

### addon.py (378 LOC)

**Purpose:** Core mitmproxy addon class — receives HTTP flows, orchestrates the full modification pipeline, writes JSONL log entries, saves error payloads on 4xx responses, writes `latency_update` records on successful responses.
**Reads:** mitmproxy `http.HTTPFlow`; env vars `MONITOR_CC_ROOT`, `PROXY_LOG_ID` for log path resolution.
**Writes:** Modifies `flow.request.content` in place; appends to `src/logs/api_requests_*.jsonl` (main entry on request, `latency_update` record on response); writes `src/logs/api_error_payload_*.json` on 4xx. Entry fields stamped post-modification include `stripped_unused_tools_names` (from `_strip_unused_tools` 3-tuple) and `deferred_tools_names` (from `_extract_deferred_tool_names` on the ORIGINAL pre-strip payload). Both default-omitted when empty.
**Called by:** mitmproxy (via `addons = [ProxyAddon()]` at module level). Hooks: `request`, `responseheaders`, `response`.
**Calls out:** `mitmproxy`

**Latency hooks:** `responseheaders(flow)` stores `flow.metadata["mc_responseheaders_at"]`. For 2xx responses it also sets `flow.response.stream = stream_chunks` (a closure that records per-chunk relative timestamps into `flow.metadata["mc_chunk_timestamps_ms"]` and buffers body in `flow.metadata["mc_body_parts"]` — because streaming mode empties `flow.response.content`). `response(flow)` success-path reads `mc_request_at` + `mc_responseheaders_at`, computes `ttfb_ms` / `stream_duration_ms` / `output_tokens_per_sec`, calls `_compute_stall_stats(chunk_timestamps_ms)` to derive `n_stalls` / `max_stall_ms` / `total_stall_ms`, writes a `latency_update` record with all 8 fields. Parser merges these fields into the main entry by matching `request_id`.

---

### rules_config.py (82 LOC)

**Purpose:** Load and cache proxy rule files — reads `proxy_rules.json`, caches rule file content by mtime, assembles system2 rule text for a given model family and project path.
**Reads:** `~/.claude/shared-rules/proxy_rules.json` and rule files (mtime-cached).
**Writes:** Nothing — returns config dict or assembled rule text.
**Called by:** `rules.py`, `inject_helpers.py`
**Calls out:** stdlib only (`json`, `pathlib`).

---

### rules.py (466 LOC)

**Purpose:** Apply proxy modification rules — detect and strip sidecar requests (single-message plain-string payload); strip system-reminders, task-notification tags, plan-mode blocks, rejection messages; inject system2 rules into `system[2]`; normalize worktree paths in `system[3]`; inject worker-idle wakeup SR for opus. Single exported orchestrator `apply_modification_rules` delegates to 8 private helpers: `_check_idle_recap`, `_check_sidecar` (short-circuits), `_inject_worker_wakeup` (opus-only pre-pass), `_apply_first_pass`, `_apply_cumulative_sr_strips`, `_apply_final_sr_pass`, `_apply_po_preview_strip` (message passes), `_apply_system_passes` (system-block pass).
**Reads:** Raw payload dict; rule text via `rules_config._load_system2_rules`; `/tmp/worker-idle-*.signal` files (consumed on read).
**Writes:** Deletes consumed `/tmp/worker-idle-*.signal` files via `os.unlink` — returns `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)` 6-tuple.
**Called by:** `src/proxy/addon.py`
**Calls out:** `rules_config`, `content_strip`, `payload_helpers`, `strip_sr`, `strip_po`, `strip_bg_completed`.

**`_inject_worker_wakeup(payload, model_family)`:** Runs after `_check_sidecar` short-circuit, before all message passes. Opus only: globs `/tmp/worker-idle-*.signal`, reads each JSON (`{worker_name, timestamp}`), builds a `<system-reminder>[WORKER-IDLE EVENT]…</system-reminder>` block listing idle worker names, appends it to the last user message (string → `\n\n` + block; list → new `{type:text}` entry), unlinks consumed signal files, returns `(modified_payload, worker_names)`. Survives `_apply_final_sr_pass` — `[WORKER-IDLE EVENT]` does not match any known strip template, so `_apply_sr_strip` preserves it as-is.

---

### cache.py (135 LOC)

**Purpose:** Strip all existing cache_control markers from a payload and place new breakpoints (Tools Anchor, Tools End, BP3 last-unchanged-msg, BP4 last-msg).
**Reads:** Payload dicts; previous request's message summaries (for BP3 unchanged-prefix detection); previous tools count (for anchor-on-growth logic).
**Writes:** Nothing — returns modified payload dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_sr.py (173 LOC)

**Purpose:** Strip `<system-reminder>` tag blocks from API message content via template-based exact-match. Maintains a catalog of 10 known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed, skills-available, plan-mode); each template has one or more identifier strings. `claudemd-contents` uses a list of identifiers (`"As you answer the user's questions"` for CC's preamble form, `"Contents of "` for the bare form) — `_match_template` iterates the list with OR semantics. Strip uses `startswith` against extracted SR-block inner text — no greedy regex across code literals.
**Reads:** Message content (string or list of blocks); template catalog (module-local).
**Writes:** Nothing — returns modified content.
**Called by:** `src/proxy/rules.py`
**Calls out:** stdlib only (`re`).

---

### strip_po.py (72 LOC)

**Purpose:** Strip the `Preview (first NKB):` section from `<persisted-output>` blocks injected by CC when Bash output exceeds its inline limit. Preserves the `<persisted-output>` wrapper and the `Output too large ... Full output saved to:` header line; removes only the Preview section (which biases readers toward 2KB snippets rather than the persisted file). Traverses all 4 content shapes (top-level string, list→text, list→tool_result/string, list→tool_result/list-of-text) mirroring `strip_sr.py`. Malformed PO blocks (missing `Output too large` or `Preview (first` header) are left untouched. Returns `(new_content, removed_chunks)` — caller (`rules.py` PO-Preview pass) appends chunks to `stripped_msg_removed` for `attribute_chunk` PP-rule attribution.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py`
**Calls out:** stdlib only (`re`).

---

### strip_bg_completed.py (75 LOC)

**Purpose:** Strip `Background command "..." failed with exit code 143/137` kill notifications from user-turn content. CC injects these when it detects that a background Bash process was terminated via SIGTERM (143) or SIGKILL (137) — e.g. when the user aborts a sleep timer via the menubar. The failure wording is misleading (user intentionally killed the process) and is noise for Opus. Traverses all 4 content shapes mirroring `strip_po.py`. Regex also covers the `completed (exit code 143/137)` form defensively. Does NOT match exit code 0 (`completed (exit code 0)`) — that is the legitimate timer-done polling signal. Returns `(new_content, removed_chunks)` for BGK-rule attribution via `attribute_chunk`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py`
**Calls out:** stdlib only (`re`).

---

### content_strip.py (167 LOC)

**Purpose:** Strip or extract non-SR content from API message payloads — rejection tool_result blocks, SessionStart SR extraction, session-guidance section removal, gitStatus stripping from sys[3], full sys[3] text replacement with `"."`, `tools[*].description` stripping, and `tools[*].input_schema.properties[*].description` (per-parameter) stripping. Both `_strip_sys3` and `_strip_tool_descriptions` capture pre-strip originals and return them as a third tuple element for log entry storage.
**Reads:** Message content (string or list of blocks); full payload dict for tool and system strip functions.
**Writes:** Nothing — returns modified content, extracted text, or modified payload.
**Called by:** `src/proxy/rules.py`; `src/proxy/addon.py` (directly calls `_strip_tool_descriptions` and `_strip_sys3` after tool injection)
**Calls out:** —

---

### logging.py (158 LOC)

**Purpose:** Build structured JSONL log entries from flow + payload data; compute message diffs vs previous request; build `latency_update` records for response-side timing.
**Reads:** Raw payload dicts, message lists, previous message summaries.
**Writes:** Nothing — returns structured entry dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

**Log record types:** `_build_entry` → main request entry. `_build_latency_update(request_id, ttfb_ms, stream_duration_ms, output_tokens, output_tokens_per_sec, n_stalls=0, max_stall_ms=None, total_stall_ms=None)` → `{type: "latency_update", ...}` with 9 fields; written after successful response. Parser (proxy_display/parser.py) merges all latency fields into the main entry by matching `request_id`.

---

### message_summary.py (168 LOC)

**Purpose:** Summarize and classify message content for log entries — produces compact dicts with role, type, chars, preview, block counts, and cache_control presence.
**Reads:** Raw message dicts from API payload.
**Writes:** Nothing — returns summary dicts.
**Called by:** `src/proxy/addon.py`, `src/proxy/logging.py`, `src/proxy/cache.py`, `src/proxy/hash_meta.py`
**Calls out:** —

---

### tool_injection.py (167 LOC)

**Purpose:** Deterministically append MCP tool schemas to `payload["tools"]` in stable order (always-injected plugin slot first, then active plugins in activation order), preventing cache rebuilds from alphabetical INSERT behavior. iterative-dev schemas removed — `_ALWAYS_INJECTED_PLUGIN` constant is retained but is a no-op until new schemas are added.
**Reads:** Schema store at `src/proxy/schemas/<plugin>/*.json` (one-time load); `<project>/.claude/active_plugins.json` (mtime-reloaded); `proxy_rules.json` exclude list.
**Writes:** Nothing — returns modified payload.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### tools.py (52 LOC)

**Purpose:** Two helpers used during the modification pipeline.
- `_strip_unused_tools(payload)` removes blocklisted tools from `payload["tools"]` using `TOOL_BLOCKLIST`. Returns `(modified_payload, count_removed, removed_names)` — the 3rd element preserves the dropped tool names for downstream stamping on the log entry as `stripped_unused_tools_names`.
- `_extract_deferred_tool_names(payload)` scans user-message content of the ORIGINAL payload (pre-modification) for the `<system-reminder>` block matching the deferred-tools identifier, parses the listed tool names, and returns a deduplicated list. Mirror of the linestart-anchored regex used in `strip_sr.py`. Stamped on the entry as `deferred_tools_names`. Reads from the original payload (not the modified copy) so it captures the SR before `apply_modification_rules` strips it.
**Reads:** Payload dict with tools list and (for deferred-extraction) `messages`.
**Writes:** Nothing — returns tuples / list per function.
**Called by:** `src/proxy/addon.py`
**Calls out:** stdlib only (`re`).

---

### fixation.py (73 LOC)

**Purpose:** Freeze `sys[2]` content and `msg[0]` project-rules block after the first request per model family, preventing byte-drift from rule-file reloads mid-session.
**Reads:** Modified payload dict; fixated state dict.
**Writes:** Nothing — returns updated fixated dict (capture) or modified payload (apply).
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### hash_meta.py (185 LOC)

**Purpose:** Compute per-request MD5 hash snapshots of tools, system blocks, and messages for cache-stability forensics; produce drift report vs previous request.
**Reads:** Final modified payload (tools, system, messages lists).
**Writes:** Nothing — returns `sent_meta` JSONL entry dict.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### inject_helpers.py (81 LOC)

**Purpose:** Three post-rules payload injections: model override (model/thinking/effort/max_tokens from `proxy_rules.json`), `context_management` block, and post-sleep cap. `_apply_post_sleep_cap` MUST be called after `_inject_model_override` — it re-applies effort=low/max_tokens=2000 for `capped_post_sleep` turns, overriding whatever model_override set.
**Reads:** Payload dict, model_family string, modifications list; `proxy_rules.json` via `rules_config._load_config()`.
**Writes:** Nothing — returns modified payload or `(modified_payload, injected_bool)`.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_vocab.py (251 LOC)

**Purpose:** Shared vocabulary + semantics for proxy strip classification. Single source of truth used by `dev/tool_use_analysis/strip_audit.py` and `src/proxy_display/` (monitor). MUST be updated in lockstep when `rules.py` adds/renames rules or changes markers. Exports:
- Constants: `BUCKETS` (EFF/INERT/IDX/LEAK/SUS), `RULES` (CMD/SK/DEF/NAG/TN/PYR/UI/PM/REJ/ALL/SC/IR/PP with markers), `TAG_LITERALS` (PO/SR/TN/ND), `STRIP_RULE_CODES`, `_SR_STRIP_RULES` (SR-class strip rule full names, used for LEAK:<SR> detection; excludes TN, SC, IR, PP).
- `attribute_chunk(chunk) -> code | None` — marker-substring attribution (starts-with special-case for TN).
- `code_for_rule(full_name) -> code | None` — reverse lookup from `modifications[]` entry to rule code.
- `classify_tags(entry) -> (leak_signals, sus_signals)` — **delta-scoped**: reads `entry.diff_from_prev.first_diff_index` and scans `entry.messages[first_diff_index:][].blocks[].full_text` + content_preview/tail for the 4 tag literals. Missing `diff_from_prev` or `first_diff_index == 0` falls back to full-scan (correct for first REQ). `first_diff_index < 0` (no-change sentinel) returns empty. Pairs each found tag with the relevant rule in `modifications[]` to decide LEAK vs SUS.
- `classify_req(entry, prev_entry) -> dict` — per-REQ 5-bucket classification. EFFECTIVE via chunk-tuple-diff against `prev.stripped_msg_removed` (skips chunks unchanged since prev). INERT via counter-delta on `modifications[]` filtered by "no chunks attributable". IDX from `smi` diff with empty `stripped_msg_removed[idx]`. LEAK/SUS delegate to `classify_tags` (inherits delta scope automatically — no separate first_diff_index handling needed).
- `legend_markdown() -> str` — Markdown legend block (3 tables: Buckets, Rules, Tag Literals) emitted at the top of audit reports.
**Reads:** Nothing at module level.
**Writes:** Nothing — pure data + helpers.
**Called by:** `dev/tool_use_analysis/strip_audit.py` (via sys.path insertion) for full legend + classify_req delegation; `src/proxy_display/render_messages.py` for attribute_chunk, classify_tags, code_for_rule, classify_req (monitor `_aggregate_req_buckets` is a thin delegate).
**Calls out:** `collections.Counter` (counter-delta inside classify_req).

---

### payload_helpers.py (226 LOC)

**Purpose:** Low-level payload content inspection and manipulation used by `rules.py` — find/strip system-reminder blocks, strip blocklisted tool_reference blocks, strip task-notification XML tags.
**Reads:** Message content (string or list), payload dicts.
**Writes:** Nothing — returns modified content or filtered dicts.
**Called by:** `src/proxy/rules.py`
**Calls out:** —

---

### schema_check.py (57 LOC)

**Purpose:** Validate API payload structure against known-good invariants on first opus request per session; detect schema drift (unexpected top-level keys, system block count, messages[0] shape, tools shape).
**Reads:** Raw payload dict before any proxy modifications.
**Writes:** Nothing — returns list of warning strings (empty = no drift).
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

## State

`tool_injection.py` holds four module-level caches (set once per mitmproxy process):
- `_SCHEMA_STORE_CACHE` — all plugin schemas loaded from `src/proxy/schemas/`
- `_ACTIVE_PLUGINS_CACHE`, `_ACTIVE_PLUGINS_MTIME`, `_ACTIVE_PLUGINS_PATH` — active plugin list with mtime-based reload

`addon.py` owns `ProxyAddon` instance state (not module-level variables): `prev_messages_by_model` dict for BP3 unchanged-prefix detection. This state resets on mitmproxy hot-reload.

## Gotchas

**Hot-reload causes cache rebuilds.** mitmproxy hot-reloads addon scripts on any file change on disk, resetting `ProxyAddon.prev_messages_by_model` → BP3 can no longer find the unchanged prefix → full cache rebuild. `claude_proxy_start.sh` works around this by copying both `proxy_addon.py` AND the entire `src/proxy/` package to `src/logs/.proxy_live_<id>/proxy/` at startup. Never edit files in `src/proxy/` during a live session expecting the running proxy to stay isolated — only git merges are blocked by the freeze; direct edits to the live copy affect it immediately.

**Post-merge load test is mandatory.** After ANY merge touching `src/proxy/` or `src/proxy_addon.py`, run:
```bash
cd src/logs && mitmdump -s ../.proxy_addon_live_*.py --set flow_detail=0 -q -p 0 2>&1 &
PID=$!; sleep 3; kill $PID 2>/dev/null; wait $PID 2>/dev/null
```
mitmproxy import errors are silent — the proxy crashes on startup and workers get ECONNREFUSED.

**Pre/post-modification log fields are distinct.** `entry.tools` / `entry.tools_count` reflect what Claude Code sent (pre-modification). `sent_meta.sent_tools_count` / `sent_meta.sent_cache_breakpoints` reflect what actually went on the wire (post-injection, post-cache-marker). When investigating cache rebuilds, always read `sent_meta.*` first — `raw_payload.tools` will mislead you.

**Worker proxies are frozen at spawn time.** Each worker's proxy package snapshot in `src/logs/.proxy_live_worker_<name>/` never updates. A worker spawned before a proxy-touching merge cannot reach new behavior or new imports. Before `worker_send` for a proxy task: check spawn time, run `git log --since='<spawn-time>' -- src/proxy/`, and kill+respawn if any merges are found.

**SR stripping is template-based, not regex-greedy.** `strip_sr.py` maintains a catalog of known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed, skills-available, plan-mode). Each template has one or more identifier-strings; matching uses `startswith` against the extracted SR-block inner text, not a greedy regex. This is the fix for the historical false-positive bug where `<system-reminder>.*?</system-reminder>` matched across code literals (e.g. `if "<system-reminder>" in text:` in a tool_result) and stripped real user code. Adding a new strip rule = add a new template entry with its identifier-string (or list of identifiers for OR semantics). Tool_result.content IS strippable — CC does inject SRs there (task-tools-nag appended to tool-outputs), and the template-based matcher correctly distinguishes real SRs from code literals.

**Strip-tracking is guarded per-rule.** In `rules.py` second-pass, each rule (skills / claudemd / pyright) appends to `pass_mods` only if its strip function actually changed the content (`new_content != content`). Without this guard, `_content_contains` could match a marker that `_strip_system_reminder` then fails to strip (e.g. template identifier mismatch) — and `pass_mods` would incorrectly mark the rule as fired, polluting `modifications` and causing `stripped_msg_removed` to capture chunks that still survive in `raw_payload`. See bead Monitor_CC-93l for the original failure case (claudemd `"Contents of "` identifier vs CC's preamble form).

**Pyright-strip lives in the second pass, not the first-pass elif-chain.** `rules.py` has two passes: a first `elif`-chain (exclusive per message — a message that hits one elif cannot trigger another), and a cumulative second pass. Pyright diagnostics SRs can co-occur in the same message with Skills or claudeMd SRs; if pyright lived in the elif-chain it would be silently skipped for those messages. Any new rule that can co-occur with an existing first-pass rule MUST go to the second pass. The structural separation between `_apply_first_pass` and `_apply_cumulative_sr_strips` in `rules.py` enforces this invariant.

**`_PRESERVE_PREAMBLE` guard in strip_sr.py.** `strip_sr.py` has a hard-coded guard that prevents stripping claudeMd-context SR blocks: an SR whose inner text starts with `"As you answer the user's questions, you can use the following context:"` is always preserved verbatim, regardless of template matching. This allows the CLAUDE.md project-context block (injected by CC as a claudeMd SR with preamble) to survive the claudemd-strip rule. Adding new "preserve entire block" logic: mirror this pattern — `startswith` check in the extractor before template dispatch.
