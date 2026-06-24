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
→ `rules` (system2 + project rule injection, content strip)
→ `fixation` (freeze sys[2] + msg[0] after first request) → `tools` (blocklist strip)
→ `tool_injection` (MCP schema append) → `inject_helpers` (model override, context management)
→ dual-log writes (original + forwarded + errors) → `cache` (strip all markers, set BP3/BP4/anchor)
→ modified payload forwarded to Anthropic; `response()` hook writes stripped/injected dual-logs via metadata bridge

## Modules

### addon.py (377 LOC)

**Purpose:** Core mitmproxy addon class — receives HTTP flows, orchestrates the full modification pipeline, writes dual-log entries, appends 4xx errors to `api_errors.jsonl`. count_tokens requests (`/v1/messages/count_tokens`) pass through unmodified — `_is_messages_request()` matches only `/v1/messages` + optional query string.
**Reads:** mitmproxy `http.HTTPFlow`; env vars `MONITOR_CC_ROOT`, `PROXY_LOG_ID`, `PROXY_PROJECT_PATH` for log path resolution and session/worker context.
**Writes:** Modifies `flow.request.content` in place; appends one JSONL line to `src/logs/api_errors.jsonl` on 4xx. Writes six dual-log files via `_resolve_dual_log_file(suffix)` into `src/logs/dual_log/`: `_original` (raw CC payload before `apply_modification_rules`); `_forwarded` (delta entry via `_build_forwarded_delta` — REQ#1 full, subsequent only changed elements per hash diff; always carries `max_tokens` + `output_config` scalars + `anthropic_beta` list of CC beta-feature flags from the HTTP request header); `_stripped` and `_injected` (delta entries via `_build_stripped_injected_deltas` — written in `response()` hook via metadata bridge); `_errors` (`is_error=True` tool_result blocks from original payload, dedup by `tool_use_id` per model_family, written in `request()` hook); `_response` (Anthropic response HTTP headers filtered via `_filter_response_headers` — rate-limit family + `request-id` + `retry-after` — written in `responseheaders()` hook for ALL status codes). Each write in its own `try/except`; failures never affect forwarding.
**State:** `prev_messages_by_model` (dict, keyed by model_family) — message summaries from previous request; used by `_set_cache_breakpoints` for BP3 unchanged-prefix detection. `prev_delta_hashes_by_model` — per-element hash lists for `_forwarded` delta chain. `prev_stripped_hashes_by_model` / `prev_injected_hashes_by_model` — flat `loc_key → MD5[:10]` dicts for `_stripped`/`_injected` delta chains. `prev_error_ids_by_model` — set of `tool_use_id` strings already written to `_errors`; dedup guard. `_session_id` (computed once via `_derive_session_id`) — `md5(PROXY_PROJECT_PATH)[:8]`. `_worker_context` (computed once via `_derive_worker_context`) — `"main"` or `"worker:<name>"`. Metadata bridge: `mc_original_payload`, `mc_modified_payload`, `mc_model_family`, `mc_all_ops`, `mc_request_id` — stored on `flow.metadata` in `request()`, read in `response()`. (`mc_stripped_msg_removed` / `mc_injected_msg_added` still stashed in `request()` but no longer consumed in `response()` — dead stashes.)
**Called by:** mitmproxy (via `addons = [ProxyAddon()]` at module level). Hooks: `request`, `responseheaders`, `response`.
**Calls out:** `mitmproxy`
**Key functions (FUNCTIONS section):** `_filter_response_headers(headers) → dict` — filters Anthropic response headers by exact name (`request-id`, `retry-after`, `anthropic-organization-id`) or prefix (`anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`); normalizes keys to lowercase. Constants: `_RESPONSE_HEADER_EXACT` (frozenset), `_RESPONSE_HEADER_PREFIXES` (tuple). `request()` decomposed (C2): 5 private helpers `_log_errors_entries`, `_log_forwarded_delta`, `_run_post_fixation_pipeline`, `_log_original_request`, `_infer_model_family`.

---

### rules_config.py (82 LOC)

**Purpose:** Load and cache proxy rule files — reads `proxy_rules.json`, caches rule file content by mtime, assembles system2 rule text for a given model family and project path.
**Reads:** `~/.claude/shared-rules/proxy_rules.json` and rule files (mtime-cached).
**Writes:** Nothing — returns config dict or assembled rule text.
**Called by:** `rules.py`, `message_passes.py`, `inject_helpers.py`
**Calls out:** stdlib only (`json`, `pathlib`).

---

### rules.py (123 LOC)

**Purpose:** Orchestrates the proxy modification pipeline. Exports `apply_modification_rules` — loads system2 rules, runs 11 message passes from `message_passes` via a `_passes` loop (each pass updates `new_messages` in sequence, accumulates `modifications`/`stripped_msg_indices`/`stripped_msg_removed`/`injected_msg_added`/`_all_ops`), then calls `_dedup_wakeup_blocks` and `_apply_system_passes`. Re-exports `_strip_blocked_tool_references` (imported from `payload_helpers`) for `addon.py`. Contains `_apply_system_passes`: injects system2 rules into `system[2]`, strips session-guidance and gitStatus from `system[3]`, normalizes worktree paths in `system[3]`.
**Reads:** Raw payload dict; rule text via `rules_config._load_system2_rules`.
**Writes:** Nothing — returns `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, _all_ops)` 8-tuple. `_all_ops` is `{msg_idx: {blk_idx: [(offset, removed, injected)]}}` — position-anchored ops from all passes accumulated via `_merge_ops`.
**Called by:** `src/proxy/addon.py` (imports `apply_modification_rules`, `_strip_blocked_tool_references`)
**Calls out:** `rules_config`, `message_passes`, `rule_ops` (`_merge_ops`), `content_strip` (`_strip_session_guidance`, `_strip_git_status`), `payload_helpers` (`_strip_blocked_tool_references` re-export).

---

### rule_ops.py (70 LOC)

**Purpose:** Op-recording primitives shared by all message passes. `_extract_block_op(before, after)` — minimal `(offset, removed, injected)` triple via common-prefix/suffix scan. `_block_inner_text(block)` — extracts plain text from any content block shape (str, text-dict, tool_result, fallback json.dumps). `_ops_from_content_change(old, new)` — per-block ops dict `{blk_idx: [(offset, removed, injected)]}` dispatching over list vs str content shapes. `_merge_ops(dst, src)` — accumulates per-pass ops into `_all_ops` in the orchestrator. `_append_wakeup_text_to_content(content)` — appends `_WAKEUP_TEXT` to str (with separator) or list (appending text block) content values.
**Reads:** Nothing — operates on content values passed as arguments.
**Writes:** Nothing — returns new dicts/lists/tuples; no mutation of arguments.
**Called by:** `src/proxy/message_passes.py` (imports `_ops_from_content_change`, `_append_wakeup_text_to_content`); `src/proxy/rules.py` (imports `_merge_ops`)
**Calls out:** `strip_bg_completed` (`_WAKEUP_TEXT`).

---

### message_passes.py (441 LOC)

**Purpose:** All twelve message-level passes delegated by `apply_modification_rules`. Each of the 11 main passes receives `messages: list` and returns a 6-tuple `(new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx, pass_ops_by_msg_blk)`. Pass sequence (call order in `rules._passes` loop): `_apply_role_system_strip` (replaces entire content of every `role='system'` message with `"."`, mod: `stripped_role_system_msg` — CC 2.1.176 delivers deferred-tools / agent-types / skills as a role=system plain-string message on Opus; idempotency guard skips empty + already-`"."` content); `_apply_first_pass` (elif-chain: plan-mode SR, task-notification tags + wakeup injection, task-tools-nag SR, deferred-tools SR, user-interrupt SR, rejection message — TN branch forks by `is_failed_bg`: completed path calls `_replace_task_notification_tags` inline + skips `_append_wakeup_text_to_content`; failed path keeps legacy summary-extract + append); `_apply_cumulative_sr_strips` (skills-SR, agent-types-SR, claudeMd-SR, pyright-diagnostics — cumulative: applied to every user msg including those already touched by pass 1, diff-based SR extraction; `stripped_agent_types_sr` added for Sonnet-worker standalone agent-types SR ~2,353 chars); `_apply_final_sr_pass` (strips all remaining `<system-reminder>` blocks); `_apply_po_preview_strip` (strips `Preview (first NKB):` section from `<persisted-output>` blocks); `_apply_bg_exit_strip` (replaces first BGK kill notification with `_WAKEUP_TEXT`, mod: `replaced_bg_completed_text`); `_apply_bg_launch_ack_strip` (replaces block content with `"."` only for blocks whose text `lstrip().startswith('Command running in background with ID:')` — anchored prefix, NOT substring-anywhere; blocks merely containing the phrase mid-content are preserved (FP-nuke fix); all 4 content shapes, mod: `stripped_bg_launch_ack`); `_apply_hook_prefix_strip` (strips `PreToolUse:<Tool> hook error: [python3 <path>]:` prefix from tool_result content, mod: `stripped_hook_error_prefix`); `_apply_git_lock_strip` (strips constant 5-line git index.lock advice from tool_result content, mod: `stripped_git_lock_advice`); `_apply_bd_noise_strip` (strips bd informational auto-import/export lines from tool_result content, mod: `stripped_bd_noise`). `_dedup_wakeup_blocks` returns a 2-tuple `(new_messages, ops_by_msg_blk)` — deduplicates multiple `_WAKEUP_TEXT` injections within the same user message to one; called after the 11-pass loop by `rules.apply_modification_rules`. Three inject points across passes: (1) TN branch completed path → `[_WAKEUP_TEXT]` or `[_WAKEUP_TEXT + "\\nOutput: <path>\\n"]`; (2) plan-mode FULL-strip branch → `["(plan-mode reminder stripped by proxy)"]`; (3) `_apply_bg_exit_strip` when `bg_removed` non-empty → `[_WAKEUP_TEXT]`. All passes call `_ops_from_content_change` from `rule_ops`; `_append_wakeup_text_to_content` used only by the failed-TN path and plan-mode path.
**Reads:** Message list; `rules_config._load_config()` (pyright-strip flag in `_apply_cumulative_sr_strips`).
**Writes:** Nothing — returns new lists/dicts; no mutation of input messages.
**Called by:** `src/proxy/rules.py` (all 12 functions imported; 11 via `_passes` loop + `_dedup_wakeup_blocks` after)
**Calls out:** `strip_sr`, `content_strip` (`_message_has_rejection`, `_strip_rejection_message`), `payload_helpers`, `rules_config`, `strip_po`, `strip_bg_completed`, `strip_bg_launch_ack`, `strip_hook_prefix`, `strip_git_lock`, `strip_bd_noise`, `rule_ops`.

---

### cache.py (135 LOC)

**Purpose:** Strip all existing cache_control markers from a payload and place new breakpoints (Tools Anchor, Tools End, BP3 last-unchanged-msg, BP4 last-msg).
**Reads:** Payload dicts; previous request's message summaries (for BP3 unchanged-prefix detection); previous tools count (for anchor-on-growth logic).
**Writes:** Nothing — returns modified payload dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_sr.py (196 LOC)

**Purpose:** Strip `<system-reminder>` tag blocks from API message content via template-based exact-match. Maintains a catalog of 11 known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed, skills-available, agent-types, plan-mode); each template has one or more identifier strings. `claudemd-contents` uses a list of identifiers (`"As you answer the user's questions"` for CC's preamble form, `"Contents of "` for the bare form) — `_match_template` iterates the list with OR semantics. Strip uses `startswith` against extracted SR-block inner text — no greedy regex across code literals. `<task-notification>` blocks do NOT go through this module — they are handled separately by `_apply_first_pass` in `message_passes.py`. The injected `_WAKEUP_TEXT` is plain text — no `<system-reminder>` tags, SR-strip passes uninvolved. `_apply_sr_strip._replace` has a pre-guard `_ENV_CONTEXT_RE.fullmatch(inner)` check that fires BEFORE the `_PRESERVE_PREAMBLE` guard, stripping CC's injected userEmail/currentDate SR block; the full-block match (email literal + date regex + IMPORTANT footer literal) ensures CLAUDE.md-context blocks with the same preamble are never false-positively stripped. **Partial-strip trailing-`\n`:** `_apply_sr_strip._replace` partial path preserves the original trailing-`\n` state: `trailing_nl = '\n' if full.endswith('\n') else ''` — the `\n` is appended only when the matched original had one. When the original SR had no trailing newline, `_STANDALONE_SR_RE` (ends with `\n?`) consumed none, so appending unconditionally would introduce a net-new `\n` into the forwarded payload; with the fix the output is byte-identical to the input w.r.t. the trailing character.
**Reads:** Message content (string or list of blocks); template catalog (module-local).
**Writes:** Nothing — returns modified content.
**Called by:** `src/proxy/message_passes.py`
**Calls out:** stdlib only (`re`).
---

### strip_po.py (72 LOC)

**Purpose:** Strip the `Preview (first NKB):` section from `<persisted-output>` blocks injected by CC when Bash output exceeds its inline limit. Preserves the `<persisted-output>` wrapper and the `Output too large ... Full output saved to:` header line; removes only the Preview section (which biases readers toward 2KB snippets rather than the persisted file). Traverses all 4 content shapes (top-level string, list→text, list→tool_result/string, list→tool_result/list-of-text) mirroring `strip_sr.py`. Malformed PO blocks (missing `Output too large` or `Preview (first` header) are left untouched. Returns `(new_content, removed_chunks)` — caller (`rules.py` PO-Preview pass) appends chunks to `stripped_msg_removed` for `attribute_chunk` PP-rule attribution.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py`
**Calls out:** stdlib only (`re`).

---

### strip_bg_launch_ack.py (71 LOC)

**Purpose:** Replace entire block content with an instructive hold message for genuine background-command launch-ack blocks. CC emits `"Command running in background with ID: <id>. Output is being written to: <path>. You will be notified when it completes. To check interim output, use Read on that file path."` as tool_result content or text block. **Anchored decision** — `_is_bg_launch_ack(text)` returns True only when `text.lstrip().startswith(_BG_LAUNCH_ACK_PREFIX)`, where `_BG_LAUNCH_ACK_PREFIX = 'Command running in background with ID:'`. A genuine ack ALWAYS starts with this prefix; a large tool_result or a user-typed/pasted message that merely CONTAINS the phrase as data mid-content is preserved (this `startswith` anchor replaced the old substring-anywhere match that nuked legitimate blocks — the FP-nuke bug). `_BG_LAUNCH_ACK_MARKER = 'running in background with ID'` is retained only as the cheap fast-path gate imported by `message_passes.py` (it GATES whether the strip is invoked; the actual decision lives in the anchored prefix). Replacement text: `"Command is running in the background. Do NOT check, poll, or read its output — just wait until it finishes (you will get a completion notice)."` — replaces the raw ack with a direct hold instruction so the model neither polls nor reads before the completion notice arrives. Covers all 4 content shapes (str, list/text, list/tool_result-str, list/tool_result-list). Does NOT match BGK completion notification (`"Background command … failed/completed"`). Returns `(new_content, removed_chunks)` for `stripped_bg_launch_ack` mod attribution via BL rule.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py` (`_apply_bg_launch_ack_strip`)
**Calls out:** stdlib only.

---

### strip_bg_completed.py (71 LOC)

**Purpose:** Replace the first background-Bash kill notification in user-turn content with a generic plain-text wake-up hint; strip any further ones. CC injects `Background command “…” failed/completed (exit code 143/137)` when a background Bash process is terminated via SIGTERM (143) or SIGKILL (137). Instead of silently removing this, the proxy repurposes it: the first match is replaced with `_WAKEUP_TEXT` (generic wake-up hint), subsequent duplicates in the same traversal are stripped. Traverses top-level string and top-level `text` blocks only — does NOT descend into `tool_result` (defense in depth: guard in `rules.py` already uses `_top_level_content_contains`; not traversing tool_result here closes the gap structurally). Does NOT match exit code 0 — that is the legitimate timer-done polling signal. Returns `(new_content, removed_chunks)` for `replaced_bg_completed_text` mod attribution.

**Wake-up architecture:** CC natively injects bg-task-completion signals when a background bash timer ends or is killed. Rather than discarding them (leaving Opus with an empty wake-up turn and no context), the proxy replaces the first signal with a plain-text hint. Covers both worker-idle wake-ups and any other backgrounded task completion (rag-cli, build, etc.). Plain text avoids `<system-reminder>` wrapping and the associated SR-strip-pass concerns.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py`, `src/proxy/rule_ops.py` (`_WAKEUP_TEXT`)
**Calls out:** stdlib only (`re`).
---

### strip_hook_prefix.py (68 LOC)

**Purpose:** Strip CC's hook-error wrapper prefix (`PreToolUse:<Tool> hook error: [python3 <path>]:`) from user-turn `tool_result` content before forwarding to Anthropic. CC wraps every hook stderr in this prefix; the actual user-visible error message follows it. Stripping at proxy level means Anthropic receives the clean message, and `_build_entry` logs the stripped version — downstream display (warnings pane) reads clean `full_text` with no further transformation needed. Returns `(new_content, removed_chunks)` for `stripped_hook_error_prefix` mod attribution. Fast-path guard `_HOOK_PREFIX_MARKER = 'PreToolUse:'` skips non-matching messages cheaply. Traverses all 4 content shapes mirroring `strip_po.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py` (`_apply_hook_prefix_strip`).
**Calls out:** stdlib only (`re`).

---

### strip_git_lock.py (71 LOC)

**Purpose:** Strip the constant 5-line git index.lock advice block from user-turn `tool_result` content before forwarding to Anthropic. CC appends this block (hardcoded in git's `lockfile.c`) to bash tool output when the beads auto-export hook calls `git add` while another git process holds `index.lock`. The variable warning line above it (`Warning: auto-export: git add failed: … File exists.`) is preserved — it contains the actionable repo path. Exact literal match via `str.replace` (no regex needed — block is constant across all repos/versions). Fast-path guard `_GIT_LOCK_MARKER = 'Another git process seems to be running'` skips non-matching messages cheaply. Returns `(new_content, removed_chunks)` for `stripped_git_lock_advice` mod attribution. Traverses all 4 content shapes mirroring `strip_hook_prefix.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py` (`_apply_git_lock_strip`).
**Calls out:** stdlib only.

---

### strip_bd_noise.py (91 LOC)

**Purpose:** Strip all bd informational auto-import/export lines from user-turn `tool_result` content before forwarding to Anthropic. bd (beads) emits these on every git commit via its auto-export hook: import-start (`auto-importing N bytes … into empty database`), import-done (`auto-imported N issues [and N memories] from …` / `auto-imported N issues into empty database`), export-done (`Exported N issues … to …` / `auto-export: wrote …`), and no-op status lines (`auto-export: no changes since last export` / `auto-export: throttled …` / `auto-export: skipping …`). Also covers upgrade-recovery variants (`auto-import: N issues from …`). All variants stripped with and without the `- ` bullet prefix present in hook-captured output. `Warning:` / `warning:` prefixed error lines (`auto-export failed:`, `auto-export skipped:`, `auto-import: failed to parse …`) are NOT matched — regex starts at `auto-import`/`auto-export`/`Exported`, never `Warning:`. Fast-path markers: `_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')` — three needed because `auto-imported N issues into empty database` contains neither of the first two. Returns `(new_content, removed_chunks)` for `stripped_bd_noise` mod attribution. Traverses all 4 content shapes mirroring `strip_git_lock.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/message_passes.py` (`_apply_bd_noise_strip`).
**Calls out:** stdlib only (`re`).

---

### content_strip.py (167 LOC)

**Purpose:** Strip or extract non-SR content from API message payloads — rejection tool_result blocks, SessionStart SR extraction, session-guidance section removal, gitStatus stripping from sys[3], full sys[3] text replacement with `"."`, `tools[*].description` stripping, and `tools[*].input_schema.properties[*].description` (per-parameter) stripping. Both `_strip_sys3` and `_strip_tool_descriptions` capture pre-strip originals and return them as a third tuple element for log entry storage.
**Reads:** Message content (string or list of blocks); full payload dict for tool and system strip functions.
**Writes:** Nothing — returns modified content, extracted text, or modified payload.
**Called by:** `src/proxy/rules.py` (`_strip_session_guidance`, `_strip_git_status`); `src/proxy/message_passes.py` (`_message_has_rejection`, `_strip_rejection_message`); `src/proxy/addon.py` (`_strip_tool_descriptions`, `_strip_sys3`)
**Calls out:** —

---

### diff_engine.py (281 LOC)

**Purpose:** Align and classify spans from an Original↔Forwarded payload diff. Produces strip/inject/equal spans for system blocks (by index), tools (by name), messages (by index + inner block), and top-level scalar fields. Also provides the GT (ground-truth) span builder that replaces blind word-diff for message blocks when strip chunks are recorded. Single source of truth used by `logging.py` (runtime strip/inject delta writes) and `dev/proxy_dual_log/` (offline verification scripts).
**Reads:** Nothing — pure functions operating on payload dicts/lists passed as arguments.
**Writes:** Nothing — returns diff result lists/dicts.
**Called by:** `src/proxy/strip_inject_delta.py` (imports `_diff_system`, `_diff_tools`, `_diff_messages`, `_diff_top_level_fields`, `_get_inner_text`, `compose_block`); `dev/proxy_dual_log/verify_strip_inject.py` and `dev/proxy_dual_log/diff_strip_inject.py` (via `sys.path.insert` + `from src.proxy.diff_engine import ...`).
**Calls out:** stdlib only (`json`, `difflib.SequenceMatcher`).

**Key functions:** `_diff_text(orig, fwd) -> list[tuple]` — word-level diff when `SequenceMatcher.ratio() >= RATIO_THRESHOLD (0.1)`, whole-block 2-span replacement otherwise. Called only by `_diff_system` and `_diff_tools` — NOT for messages (message spans use `compose_block` exclusively since Stage 4). `_diff_system`, `_diff_tools` — collection-level alignment with `_diff_text`. `_diff_messages(orig_msgs, fwd_msgs) -> list` — produces block structure only (each block_diffs entry: `{bidx, o_text, f_text}`, no `spans` field since Stage 4); spans for messages computed in `logging.py` via `compose_block`. `_diff_top_level_fields(orig_payload, fwd_payload) -> list` — iterates all keys in orig ∪ fwd, skips `_COLLECTION_KEYS = {"system","tools","messages"}`, classifies each non-collection key as stripped/injected/replaced; captures model override (`claude-opus-4-7` → `claude-opus-4-8`) as a `replaced` field entry. `_get_inner_text(block) -> str` — inner content extractor: returns `block["text"]` for text blocks, `block["content"]` (or `\n`-joined inner text for list content) for tool_result blocks, `json.dumps(block)` for other dicts. `apply_edit_to_spans(spans, offset, removed, injected) -> list` — applies one `(offset_in_Ck, removed, injected)` op to a span list; Ck = equal+injected cursor; equal bytes in removal range → stripped; injected bytes in removal range → disappear; new injected span inserted at splice point. Both invariants maintained: `equal+stripped==C0`, `equal+injected==Ck`. `compose_block(c0_text, block_ops) -> list` — composes all ops `[(offset, removed, injected)]` for one block into a span list over C0; initialises `[("equal", c0_text)]`, applies `apply_edit_to_spans` for each op in order. Proven byte-exact (9509/9509 blocks, money-shot TN+BG = 1 injected wakeup). Sole span-building path for messages since Stage 4; replaces the former `build_message_spans` / `_diff_text` fallback path.

---

### logging.py (235 LOC)

**Purpose:** Build structured JSONL entries for `forwarded_delta` and `tool_error` dual-log records; compute message diffs vs previous request. Shared normalization helpers (`_strip_cache_control`, `_normalize_msg_shape_for_hash`, `_delta_hash`) are imported by `strip_inject_delta.py` for the stripped/injected pipeline.
**Reads:** Raw payload dicts, message lists, previous message summaries, previous delta hash state.
**Writes:** Nothing — returns structured entry dicts.
**Called by:** `src/proxy/addon.py` (imports `_build_forwarded_delta`, `_build_errors_entries`); `src/proxy/cache.py` (imports `_summarize_message`, `_compute_diff`); `src/proxy/strip_inject_delta.py` (imports `_strip_cache_control`, `_normalize_msg_shape_for_hash`, `_delta_hash`)
**Calls out:** `src/proxy/message_summary.py` (`_summarize_message`)

**Log record types:** `_build_forwarded_delta(payload, request_id, prev_hashes) -> (entry, curr_hashes)` → `{type: "forwarded_delta", is_first, counts, system_delta, tools_delta, messages_delta, model, max_tokens, output_config, context_management, diagnostics}`; REQ#1 full, subsequent only changed elements; `max_tokens` and `output_config` always-include per entry (like `model`) so read-side gets fresh values without a separate scalar accumulator. **Shared hashing helpers** (imported by `strip_inject_delta.py`): `_strip_cache_control(obj)` — recursively removes `cache_control` keys for stable comparison; `_normalize_msg_shape_for_hash(msg)` — collapses single-text-block user-message list to plain string (mirrors `cache._normalize_user_content_shape`, cannot import from there due to circular dep); `_delta_hash(element)` — MD5[:10] of element after both normalizations, used for forwarded-delta hash chains and field-level hashes in the stripped/injected chain. `_build_errors_entries(payload, request_id, timestamp, seen_ids, worker_context, session_id, proxy_file) -> list` → scans `payload.messages` for `is_error=True` tool_result blocks not in `seen_ids`; builds `tu_name_map` from all `tool_use` blocks (id→name) to resolve `tool_name`; returns list of `{type: "tool_error", request_id, timestamp, ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file}` records. `_extract_tool_result_text(content) -> str` — handles both tool_result content shapes: plain string returned as-is; list-of-blocks joins all `text` block values with `\n`.

---

### strip_inject_delta.py (290 LOC)

**Purpose:** Build `stripped_delta` and `injected_delta` JSONL entries from an original↔forwarded payload pair. Computes per-section diffs via four pure-return helpers (`_process_system_section`, `_process_tools_section`, `_process_messages_section`, `_process_fields_section`), builds flat `loc_key → MD5[:10]` hash chains for delta suppression, and attributes each change to the responsible strip/inject function via `fn_map`. Fn-attribution constants (`_SYS_FN`, `_FIELD_STRIP_FN`, `_FIELD_INJECT_FN`, `_MSG_CODE_TO_FN`) and span-hash helpers (`_hash_spans`, `_hash_span_sequence`) live here. `_process_messages_section` uses role-based attribution for `role='system'` message strips: if `om_norm.get("role") == "system"` → `code = 'RS'` directly (bypasses `_attribute_chunk`), ensuring correct attribution regardless of content.
**Reads:** Original and forwarded payload dicts (cache_control stripped at call site); previous hash state dicts (`loc_key → MD5[:10]`) from prior request; `all_ops` (`{msg_idx: {blk_idx: [(offset, removed, injected)]}}`) bridged from `flow.metadata`.
**Writes:** Nothing — returns `(stripped_entry, injected_entry, new_stripped_hashes, new_injected_hashes)` 4-tuple.
**Called by:** `src/proxy/addon.py` (imports `_build_stripped_injected_deltas`, called in `response()` hook via metadata bridge)
**Calls out:** `src/proxy/diff_engine.py` (`_diff_system`, `_diff_tools`, `_diff_messages`, `_diff_top_level_fields`, `_get_inner_text`, `compose_block`); `src/proxy/strip_vocab.py` (`attribute_chunk` — fn_map attribution via `_MSG_CODE_TO_FN`); `src/proxy/logging.py` (`_strip_cache_control`, `_normalize_msg_shape_for_hash`, `_delta_hash`)

**`_build_stripped_injected_deltas(orig_payload, fwd_payload, request_id, prev_stripped, prev_injected, model, all_ops=None) -> (stripped_entry, injected_entry, new_s_hashes, new_i_hashes)`** — complete-payload diff; both payloads pre-normalized at call site; messages additionally normalized via `_normalize_msg_shape_for_hash` before diff. **Message span path (compose_block):** per block: `block_ops = msg_ops.get(bidx_int, [])` (empty default); `c0_text = _get_inner_text(orig_block)` always extracted; `spans = compose_block(c0_text, block_ops)`. Op-less (unmodified) blocks produce `[("equal", c0_text)]` → nothing logged. **_stripped format:** `system_delta[idx]`/`messages_delta[midx][bidx]`/`tools_delta[name]["desc"]` = flat stripped text lists; hash via `_hash_spans` (MD5[:10] of pipe-joined texts). **_injected format:** same locations store ordered `[(tag, text), ...]` span lists with tags `"equal"` / `"injected"`; written only when block has ≥1 injected span; hash via `_hash_span_sequence` (MD5[:10] of `tag:text|...`). **fn_map:** top-level `fn_map: {loc_key → fn_name}` in both entries; attribution: sys by index (`_SYS_FN`), tools by shape, messages via `attribute_chunk → _MSG_CODE_TO_FN`. **Exclusions:** `field.*` loc_keys not written to `fn_map` (overridden every request); message, system, and tools-desc blocks whose only injected text is `"."` are skipped (`"."` is the API-required empty-block placeholder from `_strip_sys3` / `_apply_system_passes` / `strip_sr.py`, not a real inject). The overlay dicts (`i_sys`, `i_tools`, `i_blks`) are always written when `has_i` — only fn attribution is suppressed. Old entries without `fn_map` are read-side safe.

---

### message_summary.py (168 LOC)

**Purpose:** Summarize and classify message content for log entries — produces compact dicts with role, type, chars, preview, block counts, and cache_control presence.
**Reads:** Raw message dicts from API payload.
**Writes:** Nothing — returns summary dicts.
**Called by:** `src/proxy/addon.py`, `src/proxy/logging.py`, `src/proxy/cache.py`
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

### inject_helpers.py (81 LOC)

**Purpose:** Three post-rules payload injections: model override (model/thinking/effort/max_tokens from `proxy_rules.json`), `context_management` block, and post-sleep cap. `_apply_post_sleep_cap` MUST be called after `_inject_model_override` — it re-applies effort=low/max_tokens=2000 for `capped_post_sleep` turns, overriding whatever model_override set.
**Reads:** Payload dict, model_family string, modifications list; `proxy_rules.json` via `rules_config._load_config()`.
**Writes:** Nothing — returns modified payload or `(modified_payload, injected_bool)`.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_vocab.py (262 LOC)

**Purpose:** Shared vocabulary + semantics for proxy strip classification. Single source of truth used by `dev/tool_use_analysis/strip_audit.py` and `src/proxy_display/` (monitor). MUST be updated in lockstep when `rules.py` adds/renames rules or changes markers. Exports:
- Constants: `BUCKETS` (EFF/INERT/IDX/LEAK/SUS), `RULES` (CMD/SK/AT/DEF/NAG/TN/PYR/UI/PM/REJ/ALL/SC/IR/PP/BGK/BL/GL/BD/ENV/HP/SN/FM/RS with markers), `TAG_LITERALS` (PO/SR/TN/ND), `STRIP_RULE_CODES`, `_SR_STRIP_RULES` (SR-class strip rule full names, used for LEAK:<SR> detection; excludes TN, SC, IR, PP).
- `attribute_chunk(chunk) -> code | None` — marker-substring attribution (starts-with special-case for TN).
- `code_for_rule(full_name) -> code | None` — reverse lookup from `modifications[]` entry to rule code.
- `classify_tags(entry) -> (leak_signals, sus_signals)` — **delta-scoped**: scans `entry.messages[prev_message_count:][].blocks[].full_text` + content_preview/tail for the 4 tag literals. `prev_message_count = message_count - messages_added` (from `diff_from_prev`). Missing `diff_from_prev` → start=0 (first REQ, full scan). `first_diff_index < 0` (byte-identical re-fire sentinel) returns empty. Does NOT use `first_diff_index` as delta bound — `first_diff_index` can regress into old messages on 1-char re-serialization drift (TN strip appends `\n`) causing double-fire. Pairs each found tag with the relevant rule in `modifications[]` to decide LEAK vs SUS.
- `classify_req(entry, prev_entry) -> dict` — per-REQ 5-bucket classification. EFFECTIVE via chunk-tuple-diff against `prev.stripped_msg_removed` (skips chunks unchanged since prev). INERT via counter-delta on `modifications[]` filtered by "no chunks attributable". IDX from `smi` diff with empty `stripped_msg_removed[idx]`. LEAK/SUS delegate to `classify_tags` (inherits delta scope automatically — no separate first_diff_index handling needed).
- `legend_markdown() -> str` — Markdown legend block (3 tables: Buckets, Rules, Tag Literals) emitted at the top of audit reports.
**Reads:** Nothing at module level.
**Writes:** Nothing — pure data + helpers.
**Called by:** `dev/tool_use_analysis/strip_audit.py` (via sys.path insertion) for full legend + classify_req delegation; `src/proxy_display/render_messages.py` for attribute_chunk, classify_tags, code_for_rule, classify_req (monitor `_aggregate_req_buckets` is a thin delegate); `src/proxy/strip_inject_delta.py` (imports `attribute_chunk as _attribute_chunk` for fn_map attribution in `_build_stripped_injected_deltas`).
**Calls out:** `collections.Counter` (counter-delta inside classify_req).

---

### payload_helpers.py (235 LOC)

**Purpose:** Low-level payload content inspection and manipulation used by `rules.py` — find/strip system-reminder blocks, strip blocklisted tool_reference blocks, strip/replace task-notification XML tags. Exports two content-search helpers with distinct scopes: `_content_contains` (descends into tool_result — used by SR-strip guards which legitimately match tool_result content); `_top_level_content_contains` (top-level str/text only, never tool_result — used by wakeup-injection guards to prevent false-positive injection from marker strings in tool_result data). `_find_system_reminder_blocks` and `_find_all_system_reminder_blocks` patterns include `\n?` after `</system-reminder>` (with `re.DOTALL`) — recorded chunk includes the trailing newline that `_STANDALONE_SR_RE` strips, closing the precision gap in GT span building. Task-notification helpers: `_strip_task_notification_tags` — extracts `<summary>` text, replaces TN block with it (used by the failed-TN path); `_extract_task_notification_output_file` — extracts the `<output-file>` path from the first TN block in content, returns `''` if absent; `_replace_task_notification_tags(content, replacement_text)` — replaces TN blocks inline with `replacement_text` using lambda re.sub (no backslash-sequence interpretation), no separate append (used by the completed-TN path to produce a single block).
**Reads:** Message content (string or list), payload dicts.
**Writes:** Nothing — returns modified content or filtered dicts.
**Called by:** `src/proxy/rules.py` (`_strip_blocked_tool_references` re-export); `src/proxy/message_passes.py` (all other helpers)
**Calls out:** —

---

## State

`tool_injection.py` holds four module-level caches (set once per mitmproxy process):
- `_SCHEMA_STORE_CACHE` — all plugin schemas loaded from `src/proxy/schemas/`
- `_ACTIVE_PLUGINS_CACHE`, `_ACTIVE_PLUGINS_MTIME`, `_ACTIVE_PLUGINS_PATH` — active plugin list with mtime-based reload

`addon.py` owns `ProxyAddon` instance state: `prev_messages_by_model` for BP3 unchanged-prefix detection; `prev_delta_hashes_by_model` for `_forwarded` delta chain; `prev_stripped_hashes_by_model` / `prev_injected_hashes_by_model` (flat `loc_key → MD5[:10]` dicts) for `_stripped`/`_injected` delta chains; `prev_error_ids_by_model` (sets of `tool_use_id` strings) for `_errors` dedup chain. All state resets on mitmproxy hot-reload. `_session_id` and `_worker_context` are computed once at `__init__` and are immutable for the proxy's lifetime.

## Gotchas

**Hot-reload causes cache rebuilds.** mitmproxy hot-reloads addon scripts on any file change on disk, resetting `ProxyAddon.prev_messages_by_model` → BP3 can no longer find the unchanged prefix → full cache rebuild. `claude_proxy_start.sh` works around this by copying both `proxy_addon.py` AND the entire `src/proxy/` package to `src/logs/.proxy_live_<id>/proxy/` at startup. Never edit files in `src/proxy/` during a live session expecting the running proxy to stay isolated — only git merges are blocked by the freeze; direct edits to the live copy affect it immediately.

**Post-merge load test is mandatory.** After ANY merge touching `src/proxy/` or `src/proxy_addon.py`, run:
```bash
cd src/logs && mitmdump -s ../.proxy_addon_live_*.py --set flow_detail=0 -q -p 0 2>&1 &
PID=$!; sleep 3; kill $PID 2>/dev/null; wait $PID 2>/dev/null
```
mitmproxy import errors are silent — the proxy crashes on startup and workers get ECONNREFUSED.

**Worker proxies are frozen at spawn time.** Each worker's proxy package snapshot in `src/logs/.proxy_live_worker_<name>/` never updates. A worker spawned before a proxy-touching merge cannot reach new behavior or new imports. Before `worker_send` for a proxy task: check spawn time, run `git log --since='<spawn-time>' -- src/proxy/`, and kill+respawn if any merges are found.

**SR stripping is template-based, not regex-greedy.** `strip_sr.py` maintains a catalog of known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed, skills-available, plan-mode). Each template has one or more identifier-strings; matching uses `startswith` against the extracted SR-block inner text, not a greedy regex. This is the fix for the historical false-positive bug where `<system-reminder>.*?</system-reminder>` matched across code literals (e.g. `if "<system-reminder>" in text:` in a tool_result) and stripped real user code. Adding a new strip rule = add a new template entry with its identifier-string (or list of identifiers for OR semantics). Tool_result.content IS strippable — CC does inject SRs there (task-tools-nag appended to tool-outputs), and the template-based matcher correctly distinguishes real SRs from code literals.

**Strip-tracking is guarded per-rule.** In `message_passes.py` `_apply_cumulative_sr_strips`, each rule (skills / claudemd / pyright) appends to `pass_mods` only if its strip function actually changed the content (`new_content != content`). Without this guard, `_content_contains` could match a marker that `_strip_system_reminder` then fails to strip (e.g. template identifier mismatch) — and `pass_mods` would incorrectly mark the rule as fired, polluting `modifications` and causing `stripped_msg_removed` to capture chunks that still survive in `raw_payload`. Root case: claudemd `"Contents of "` identifier vs CC's preamble form `"As you answer the user's questions"` — two distinct SR variants for the same template that previously went unmatched.

**Pyright-strip lives in the second pass, not the first-pass elif-chain.** `message_passes.py` has two passes: `_apply_first_pass` — an `elif`-chain (exclusive per message, a message that hits one branch cannot trigger another) — and `_apply_cumulative_sr_strips` — a cumulative pass applied to every user message. Pyright diagnostics SRs can co-occur in the same message with Skills or claudeMd SRs; if pyright lived in the elif-chain it would be silently skipped for those messages. Any new rule that can co-occur with an existing first-pass rule MUST go to the second pass. The structural separation between `_apply_first_pass` and `_apply_cumulative_sr_strips` in `message_passes.py` enforces this invariant.


**`_PRESERVE_PREAMBLE` guard in strip_sr.py.** `strip_sr.py` has a hard-coded guard that prevents stripping claudeMd-context SR blocks: an SR whose inner text starts with `"As you answer the user's questions, you can use the following context:"` is always preserved verbatim, regardless of template matching. This allows the CLAUDE.md project-context block (injected by CC as a claudeMd SR with preamble) to survive the claudemd-strip rule. Adding new "preserve entire block" logic: mirror this pattern — `startswith` check in the extractor before template dispatch. **Exception: any new strip rule whose target block shares the same preamble (e.g. env-context SR) MUST insert its check BEFORE the `_PRESERVE_PREAMBLE` guard** — otherwise the guard fires first and the strip never runs. See `_ENV_CONTEXT_RE.fullmatch(inner)` check in `_apply_sr_strip._replace` for the pattern.
