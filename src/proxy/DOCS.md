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

### addon.py (349 LOC)

**Purpose:** Core mitmproxy addon class — receives HTTP flows, orchestrates the full modification pipeline, writes dual-log entries, appends 4xx errors to `api_errors.jsonl`. count_tokens requests (`/v1/messages/count_tokens`) pass through unmodified — `_is_messages_request()` matches only `/v1/messages` + optional query string.
**Reads:** mitmproxy `http.HTTPFlow`; env vars `MONITOR_CC_ROOT`, `PROXY_LOG_ID`, `PROXY_PROJECT_PATH` for log path resolution and session/worker context.
**Writes:** Modifies `flow.request.content` in place; appends one JSONL line to `src/logs/api_errors.jsonl` on 4xx. Writes six dual-log files via `_resolve_dual_log_file(suffix)` into `src/logs/dual_log/`: `_original` (raw CC payload before `apply_modification_rules`); `_forwarded` (delta entry via `_build_forwarded_delta` — REQ#1 full, subsequent only changed elements per hash diff; always carries `max_tokens` + `output_config` scalars + `anthropic_beta` list of CC beta-feature flags from the HTTP request header); `_stripped` and `_injected` (delta entries via `_build_stripped_injected_deltas` — written in `response()` hook via metadata bridge); `_errors` (`is_error=True` tool_result blocks from original payload, dedup by `tool_use_id` per model_family, written in `request()` hook); `_response` (Anthropic response HTTP headers filtered via `_filter_response_headers` — rate-limit family + `request-id` + `retry-after` — written in `responseheaders()` hook for ALL status codes). Each write in its own `try/except`; failures never affect forwarding.
**State:** `prev_messages_by_model` (dict, keyed by model_family) — message summaries from previous request; used by `_set_cache_breakpoints` for BP3 unchanged-prefix detection. `prev_delta_hashes_by_model` — per-element hash lists for `_forwarded` delta chain. `prev_stripped_hashes_by_model` / `prev_injected_hashes_by_model` — flat `loc_key → MD5[:10]` dicts for `_stripped`/`_injected` delta chains. `prev_error_ids_by_model` — set of `tool_use_id` strings already written to `_errors`; dedup guard. `_session_id` (computed once via `_derive_session_id`) — `md5(PROXY_PROJECT_PATH)[:8]`. `_worker_context` (computed once via `_derive_worker_context`) — `"main"` or `"worker:<name>"`. Metadata bridge: `mc_original_payload`, `mc_modified_payload`, `mc_model_family`, `mc_all_ops`, `mc_request_id` — stored on `flow.metadata` in `request()`, read in `response()`. (`mc_stripped_msg_removed` / `mc_injected_msg_added` still stashed in `request()` but no longer consumed in `response()` — dead stashes.)
**Called by:** mitmproxy (via `addons = [ProxyAddon()]` at module level). Hooks: `request`, `responseheaders`, `response`.
**Calls out:** `mitmproxy`
**Key functions (FUNCTIONS section):** `_filter_response_headers(headers) → dict` — filters Anthropic response headers by exact name (`request-id`, `retry-after`, `anthropic-organization-id`) or prefix (`anthropic-ratelimit-*`, `anthropic-priority-*`, `anthropic-fast-*`); normalizes keys to lowercase. Constants: `_RESPONSE_HEADER_EXACT` (frozenset), `_RESPONSE_HEADER_PREFIXES` (tuple).

---

### rules_config.py (82 LOC)

**Purpose:** Load and cache proxy rule files — reads `proxy_rules.json`, caches rule file content by mtime, assembles system2 rule text for a given model family and project path.
**Reads:** `~/.claude/shared-rules/proxy_rules.json` and rule files (mtime-cached).
**Writes:** Nothing — returns config dict or assembled rule text.
**Called by:** `rules.py`, `inject_helpers.py`
**Calls out:** stdlib only (`json`, `pathlib`).

---

### rules.py (628 LOC)

**Purpose:** Apply proxy modification rules — strip or replace system-reminders, task-notification tags, plan-mode blocks, rejection messages; inject system2 rules into `system[2]`; normalize worktree paths in `system[3]`. Single exported orchestrator `apply_modification_rules` delegates to private helpers: `_apply_first_pass`, `_apply_cumulative_sr_strips`, `_apply_final_sr_pass`, `_apply_po_preview_strip` (message passes), `_apply_bg_exit_strip` (BGK plain-text path), `_apply_hook_prefix_strip` (hook-error-prefix strip), `_apply_git_lock_strip` (git index.lock advice strip), `_apply_bd_noise_strip` (bd informational import/export lines), `_dedup_wakeup_blocks` (final pass), `_apply_system_passes` (system-block pass). All eight private pass helpers return a 5-tuple `(new_messages, pass_mods, pass_removed_by_idx, changed_indices, pass_injected_by_idx)`; the orchestrator accumulates `injected_msg_added: dict[int, list[str]]` (parallel to `stripped_msg_removed`) via `injected_msg_added.setdefault(idx, []).extend(pass_injected.get(idx, []))` after each pass. Three inject points recorded: (1) TN branch → `[_WAKEUP_TEXT]`; (2) plan-mode FULL-strip branch (stripped is None, content becomes `"(plan-mode reminder stripped by proxy)"`) → `["(plan-mode reminder stripped by proxy)"]`; (3) `_apply_bg_exit_strip` when `bg_removed` non-empty → `[_WAKEUP_TEXT]`. `_apply_first_pass` ALWAYS appends `_WAKEUP_TEXT` via `_append_wakeup_text_to_content` to ANY `<task-notification>` block — detection via `_top_level_content_contains` (top-level str/text only, does NOT descend into tool_result; prevents false-positive when the tag appears as DATA in tool_result content). mod-name still differentiates `replaced_task_notification` for failed vs `trimmed_task_notification` for non-failed. `_apply_bg_exit_strip` replaces first BGK plain-text notification with `_WAKEUP_TEXT` (mod: `replaced_bg_completed_text`) — guard likewise uses `_top_level_content_contains`. `_apply_hook_prefix_strip` strips `PreToolUse:<Tool> hook error: [python3 <path>]:` prefix from tool_result content before the payload reaches Anthropic (mod: `stripped_hook_error_prefix`). `_apply_git_lock_strip` strips the constant 5-line git index.lock advice block from tool_result content (mod: `stripped_git_lock_advice`); guard via `_content_contains` (descends into tool_result). `_apply_bd_noise_strip` strips all bd informational auto-import/export lines from tool_result content (mod: `stripped_bd_noise`); guard via `any(_content_contains(..., m) for m in _BD_NOISE_MARKERS)` — three markers needed because the `into empty database` variant has neither `issues.jsonl` nor `auto-export:`. `_dedup_wakeup_blocks` runs as the final message-side pass: collapses multiple consecutive `_WAKEUP_TEXT` blocks within a single user-message to one (TN path and BGK path firing on the same message both inject independently → dedup ensures max 1 wake-up block per message). Comparison via `rstrip('\n')` handles both TN-path (`_WAKEUP_TEXT` with `\n`) and BGK-path (inline form, `\n`-stripped). Dedup touches only `msg["content"]`, NEVER `stripped_msg_removed` — display invariant: wake-up text is INJECTED into outgoing payload, not stripped from it. `_apply_cumulative_sr_strips` uses diff-based SR extraction: `[sr for sr in _find_all_system_reminder_blocks(original_before_pass) if sr not in _find_all_system_reminder_blocks(content)]` — captures ENV-context SRs stripped via `_ENV_CONTEXT_RE` (previously excluded by marker-by-marker approach).
**Reads:** Raw payload dict; rule text via `rules_config._load_system2_rules`.
**Writes:** Nothing — returns `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, _all_ops)` 8-tuple. `_all_ops` is `{msg_idx: {blk_idx: [(offset, removed, injected)]}}` — position-anchored ops from all 8 passes accumulated via `_merge_ops`.
**Called by:** `src/proxy/addon.py`
**Calls out:** `rules_config`, `content_strip`, `payload_helpers`, `strip_sr`, `strip_po`, `strip_bg_completed`, `strip_hook_prefix`, `strip_git_lock`, `strip_bd_noise`.

---

### cache.py (135 LOC)

**Purpose:** Strip all existing cache_control markers from a payload and place new breakpoints (Tools Anchor, Tools End, BP3 last-unchanged-msg, BP4 last-msg).
**Reads:** Payload dicts; previous request's message summaries (for BP3 unchanged-prefix detection); previous tools count (for anchor-on-growth logic).
**Writes:** Nothing — returns modified payload dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_sr.py (194 LOC)

**Purpose:** Strip `<system-reminder>` tag blocks from API message content via template-based exact-match. Maintains a catalog of 10 known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed, skills-available, plan-mode); each template has one or more identifier strings. `claudemd-contents` uses a list of identifiers (`"As you answer the user's questions"` for CC's preamble form, `"Contents of "` for the bare form) — `_match_template` iterates the list with OR semantics. Strip uses `startswith` against extracted SR-block inner text — no greedy regex across code literals. `<task-notification>` blocks do NOT go through this module — they are handled separately by `_apply_first_pass` in `rules.py`. The injected `_WAKEUP_TEXT` is plain text — no `<system-reminder>` tags, SR-strip passes uninvolved. `_apply_sr_strip._replace` has a pre-guard `_ENV_CONTEXT_RE.fullmatch(inner)` check that fires BEFORE the `_PRESERVE_PREAMBLE` guard, stripping CC's injected userEmail/currentDate SR block; the full-block match (email literal + date regex + IMPORTANT footer literal) ensures CLAUDE.md-context blocks with the same preamble are never false-positively stripped. **Partial-strip trailing-`\n`:** `_apply_sr_strip._replace` partial path preserves the original trailing-`\n` state: `trailing_nl = '\n' if full.endswith('\n') else ''` — the `\n` is appended only when the matched original had one. When the original SR had no trailing newline, `_STANDALONE_SR_RE` (ends with `\n?`) consumed none, so appending unconditionally would introduce a net-new `\n` into the forwarded payload; with the fix the output is byte-identical to the input w.r.t. the trailing character.
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

### strip_bg_completed.py (71 LOC)

**Purpose:** Replace the first background-Bash kill notification in user-turn content with a generic plain-text wake-up hint; strip any further ones. CC injects `Background command “…” failed/completed (exit code 143/137)` when a background Bash process is terminated via SIGTERM (143) or SIGKILL (137). Instead of silently removing this, the proxy repurposes it: the first match is replaced with `_WAKEUP_TEXT` (generic wake-up hint), subsequent duplicates in the same traversal are stripped. Traverses top-level string and top-level `text` blocks only — does NOT descend into `tool_result` (defense in depth: guard in `rules.py` already uses `_top_level_content_contains`; not traversing tool_result here closes the gap structurally). Does NOT match exit code 0 — that is the legitimate timer-done polling signal. Returns `(new_content, removed_chunks)` for `replaced_bg_completed_text` mod attribution.

**Wake-up architecture:** CC natively injects bg-task-completion signals when a background bash timer ends or is killed. Rather than discarding them (leaving Opus with an empty wake-up turn and no context), the proxy replaces the first signal with a plain-text hint. Covers both worker-idle wake-ups and any other backgrounded task completion (rag-cli, build, etc.). Plain text avoids `<system-reminder>` wrapping and the associated SR-strip-pass concerns.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py`
**Calls out:** stdlib only (`re`).
---

### strip_hook_prefix.py (68 LOC)

**Purpose:** Strip CC's hook-error wrapper prefix (`PreToolUse:<Tool> hook error: [python3 <path>]:`) from user-turn `tool_result` content before forwarding to Anthropic. CC wraps every hook stderr in this prefix; the actual user-visible error message follows it. Stripping at proxy level means Anthropic receives the clean message, and `_build_entry` logs the stripped version — downstream display (warnings pane) reads clean `full_text` with no further transformation needed. Returns `(new_content, removed_chunks)` for `stripped_hook_error_prefix` mod attribution. Fast-path guard `_HOOK_PREFIX_MARKER = 'PreToolUse:'` skips non-matching messages cheaply. Traverses all 4 content shapes mirroring `strip_po.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py` (`_apply_hook_prefix_strip` pass).
**Calls out:** stdlib only (`re`).

---

### strip_git_lock.py (71 LOC)

**Purpose:** Strip the constant 5-line git index.lock advice block from user-turn `tool_result` content before forwarding to Anthropic. CC appends this block (hardcoded in git's `lockfile.c`) to bash tool output when the beads auto-export hook calls `git add` while another git process holds `index.lock`. The variable warning line above it (`Warning: auto-export: git add failed: … File exists.`) is preserved — it contains the actionable repo path. Exact literal match via `str.replace` (no regex needed — block is constant across all repos/versions). Fast-path guard `_GIT_LOCK_MARKER = 'Another git process seems to be running'` skips non-matching messages cheaply. Returns `(new_content, removed_chunks)` for `stripped_git_lock_advice` mod attribution. Traverses all 4 content shapes mirroring `strip_hook_prefix.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py` (`_apply_git_lock_strip` pass).
**Calls out:** stdlib only.

---

### strip_bd_noise.py (91 LOC)

**Purpose:** Strip all bd informational auto-import/export lines from user-turn `tool_result` content before forwarding to Anthropic. bd (beads) emits these on every git commit via its auto-export hook: import-start (`auto-importing N bytes … into empty database`), import-done (`auto-imported N issues [and N memories] from …` / `auto-imported N issues into empty database`), export-done (`Exported N issues … to …` / `auto-export: wrote …`), and no-op status lines (`auto-export: no changes since last export` / `auto-export: throttled …` / `auto-export: skipping …`). Also covers upgrade-recovery variants (`auto-import: N issues from …`). All variants stripped with and without the `- ` bullet prefix present in hook-captured output. `Warning:` / `warning:` prefixed error lines (`auto-export failed:`, `auto-export skipped:`, `auto-import: failed to parse …`) are NOT matched — regex starts at `auto-import`/`auto-export`/`Exported`, never `Warning:`. Fast-path markers: `_BD_NOISE_MARKERS = ('issues.jsonl', 'auto-export:', 'into empty database')` — three needed because `auto-imported N issues into empty database` contains neither of the first two. Returns `(new_content, removed_chunks)` for `stripped_bd_noise` mod attribution. Traverses all 4 content shapes mirroring `strip_git_lock.py`.
**Reads:** Message content (string or list of blocks).
**Writes:** Nothing — returns `(modified_content, list[str])`.
**Called by:** `src/proxy/rules.py` (`_apply_bd_noise_strip` pass).
**Calls out:** stdlib only (`re`).

---

### content_strip.py (167 LOC)

**Purpose:** Strip or extract non-SR content from API message payloads — rejection tool_result blocks, SessionStart SR extraction, session-guidance section removal, gitStatus stripping from sys[3], full sys[3] text replacement with `"."`, `tools[*].description` stripping, and `tools[*].input_schema.properties[*].description` (per-parameter) stripping. Both `_strip_sys3` and `_strip_tool_descriptions` capture pre-strip originals and return them as a third tuple element for log entry storage.
**Reads:** Message content (string or list of blocks); full payload dict for tool and system strip functions.
**Writes:** Nothing — returns modified content, extracted text, or modified payload.
**Called by:** `src/proxy/rules.py`; `src/proxy/addon.py` (directly calls `_strip_tool_descriptions` and `_strip_sys3` after tool injection)
**Calls out:** —

---

### diff_engine.py (281 LOC)

**Purpose:** Align and classify spans from an Original↔Forwarded payload diff. Produces strip/inject/equal spans for system blocks (by index), tools (by name), messages (by index + inner block), and top-level scalar fields. Also provides the GT (ground-truth) span builder that replaces blind word-diff for message blocks when strip chunks are recorded. Single source of truth used by `logging.py` (runtime strip/inject delta writes) and `dev/proxy_dual_log/` (offline verification scripts).
**Reads:** Nothing — pure functions operating on payload dicts/lists passed as arguments.
**Writes:** Nothing — returns diff result lists/dicts.
**Called by:** `src/proxy/logging.py` (imports `_diff_system`, `_diff_tools`, `_diff_messages`, `_diff_top_level_fields`, `_get_inner_text`, `compose_block`); `dev/proxy_dual_log/verify_strip_inject.py` and `dev/proxy_dual_log/diff_strip_inject.py` (via `sys.path.insert` + `from src.proxy.diff_engine import ...`).
**Calls out:** stdlib only (`json`, `difflib.SequenceMatcher`).

**Key functions:** `_diff_text(orig, fwd) -> list[tuple]` — word-level diff when `SequenceMatcher.ratio() >= RATIO_THRESHOLD (0.1)`, whole-block 2-span replacement otherwise. Called only by `_diff_system` and `_diff_tools` — NOT for messages (message spans use `compose_block` exclusively since Stage 4). `_diff_system`, `_diff_tools` — collection-level alignment with `_diff_text`. `_diff_messages(orig_msgs, fwd_msgs) -> list` — produces block structure only (each block_diffs entry: `{bidx, o_text, f_text}`, no `spans` field since Stage 4); spans for messages computed in `logging.py` via `compose_block`. `_diff_top_level_fields(orig_payload, fwd_payload) -> list` — iterates all keys in orig ∪ fwd, skips `_COLLECTION_KEYS = {"system","tools","messages"}`, classifies each non-collection key as stripped/injected/replaced; captures model override (`claude-opus-4-7` → `claude-opus-4-8`) as a `replaced` field entry. `_get_inner_text(block) -> str` — inner content extractor: returns `block["text"]` for text blocks, `block["content"]` (or `\n`-joined inner text for list content) for tool_result blocks, `json.dumps(block)` for other dicts. `apply_edit_to_spans(spans, offset, removed, injected) -> list` — applies one `(offset_in_Ck, removed, injected)` op to a span list; Ck = equal+injected cursor; equal bytes in removal range → stripped; injected bytes in removal range → disappear; new injected span inserted at splice point. Both invariants maintained: `equal+stripped==C0`, `equal+injected==Ck`. `compose_block(c0_text, block_ops) -> list` — composes all ops `[(offset, removed, injected)]` for one block into a span list over C0; initialises `[("equal", c0_text)]`, applies `apply_edit_to_spans` for each op in order. Proven byte-exact (9509/9509 blocks, money-shot TN+BG = 1 injected wakeup). Sole span-building path for messages since Stage 4; replaces the former `build_message_spans` / `_diff_text` fallback path.

---

### logging.py (468 LOC) ⚠️ refactor candidate (>400 LOC hard ceiling)

**Purpose:** Build structured JSONL entries for the dual-log files; compute message diffs vs previous request; build `forwarded_delta` / `stripped_delta` / `injected_delta` / `tool_error` entries.
**Reads:** Raw payload dicts, message lists, previous message summaries, previous delta hash state.
**Writes:** Nothing — returns structured entry dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** `src/proxy/diff_engine` (`_diff_system`, `_diff_tools`, `_diff_messages`, `_diff_top_level_fields`, `_get_inner_text`, `compose_block`); `src/proxy/strip_vocab` (`attribute_chunk` — for fn attribution in fn_map)

**Log record types:** `_build_forwarded_delta(payload, request_id, prev_hashes) -> (entry, curr_hashes)` → `{type: "forwarded_delta", is_first, counts, system_delta, tools_delta, messages_delta, model, max_tokens, output_config, context_management, diagnostics}`; REQ#1 full, subsequent only changed elements; `max_tokens` and `output_config` always-include per entry (like `model`) so read-side gets fresh values without a separate scalar accumulator. `_build_stripped_injected_deltas(orig_payload, fwd_payload, request_id, prev_stripped, prev_injected, model, all_ops=None) -> (stripped_entry, injected_entry, new_s_hashes, new_i_hashes)` — complete-payload diff (system + tools + messages + top-level fields via `_diff_top_level_fields`); both payloads pre-normalized at call site via `_strip_cache_control`; messages additionally normalized via `_normalize_msg_shape_for_hash` before diff. **Message span path (compose_block, Stage 4 — no fallback):** `all_ops` (`{msg_idx: {blk_idx: [(offset, removed, injected)]}}`) bridged via `flow.metadata["mc_all_ops"]`. Per block: `block_ops = msg_ops.get(bidx_int, [])` (empty default); `c0_text = _get_inner_text(orig_block)` always extracted; `spans = compose_block(c0_text, block_ops)`. Op-less (unmodified) blocks: `block_ops=[]` → `[("equal", c0_text)]` → `s_texts=[]`/`has_i=False` → nothing logged. `_diff_text` not called for messages; `_diff_messages` produces block structure only (no `bd["spans"]`). Guard: `dev/proxy_dual_log/test_composition_invariant.py` CI test — exit 1 on invariant violation, no runtime fallback. Double-inject fixed: TN+BG chain → 3 ops → 1 injected span; inj-badge surfaces via `has_i` from composed spans. **_stripped format:** `system_delta[idx]`/`messages_delta[midx][bidx]`/`tools_delta[name]["desc"]` = flat stripped text lists; hash via `_hash_spans` (MD5[:10] of pipe-joined texts). **_injected format (Stage 1):** same locations store ordered `[(tag, text), ...]` span lists with tags `"equal"` / `"injected"`; only written when block has ≥1 injected span; hash via `_hash_span_sequence` (MD5[:10] of `tag:text|...`). **fn_map (new):** top-level `fn_map: {loc_key → fn_name}` attached to both `_stripped` and `_injected` entries at write time. `loc_key` matches the hash-tracking keys (`sys.N`, `tool_w.name`, `tool_d.name`, `msg.M.B`, `field.key`). Attribution: sys by index (`_SYS_FN`), tools by shape (`_strip_unused_tools`/`inject_mcp_tools`/`_strip_tool_descriptions`), messages via `attribute_chunk` → `_MSG_CODE_TO_FN`. **Exclusions (write-side):** field overrides (`field.*` loc_keys — model, max_tokens, thinking, output_config, context_management) are NOT written to `fn_map`; they appear only in `fields_delta` (the drill-down); the proxy overrides these fields on every request so attributing them would badge every REQ. Message blocks whose only injected text is `"."` (the empty-block placeholder from `strip_sr.py`, used to satisfy the Anthropic API's non-empty-content constraint) are NOT written to `fn_map` — the "." is a structural necessity, not a real injection. Old entries without `fn_map` are read-side safe (field simply absent). Hashing helpers: `_strip_cache_control(obj)`, `_normalize_msg_shape_for_hash(msg)`, `_delta_hash(element)`, `_hash_spans(texts)`, `_hash_span_sequence(spans)` — latter two differ by namespace to prevent hash collisions across formats. `_build_errors_entries(payload, request_id, timestamp, seen_ids, worker_context, session_id, proxy_file) -> list` → scans `payload.messages` for `is_error=True` tool_result blocks not in `seen_ids`; builds `tu_name_map` from all `tool_use` blocks (id→name) to resolve `tool_name`; returns list of `{type: "tool_error", request_id, timestamp, ts, session_id, worker, tool_name, tool_use_id, error_full, proxy_file}` records (format field-matched to `tool_errors.jsonl`). `_extract_tool_result_text(content) -> str` — handles both tool_result content shapes: plain string returned as-is; list-of-blocks joins all `text` block values with `\n`.

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

### strip_vocab.py (258 LOC)

**Purpose:** Shared vocabulary + semantics for proxy strip classification. Single source of truth used by `dev/tool_use_analysis/strip_audit.py` and `src/proxy_display/` (monitor). MUST be updated in lockstep when `rules.py` adds/renames rules or changes markers. Exports:
- Constants: `BUCKETS` (EFF/INERT/IDX/LEAK/SUS), `RULES` (CMD/SK/DEF/NAG/TN/PYR/UI/PM/REJ/ALL/SC/IR/PP/BGK/GL/BD/ENV/HP/SN/FM with markers), `TAG_LITERALS` (PO/SR/TN/ND), `STRIP_RULE_CODES`, `_SR_STRIP_RULES` (SR-class strip rule full names, used for LEAK:<SR> detection; excludes TN, SC, IR, PP).
- `attribute_chunk(chunk) -> code | None` — marker-substring attribution (starts-with special-case for TN).
- `code_for_rule(full_name) -> code | None` — reverse lookup from `modifications[]` entry to rule code.
- `classify_tags(entry) -> (leak_signals, sus_signals)` — **delta-scoped**: scans `entry.messages[prev_message_count:][].blocks[].full_text` + content_preview/tail for the 4 tag literals. `prev_message_count = message_count - messages_added` (from `diff_from_prev`). Missing `diff_from_prev` → start=0 (first REQ, full scan). `first_diff_index < 0` (byte-identical re-fire sentinel) returns empty. Does NOT use `first_diff_index` as delta bound — `first_diff_index` can regress into old messages on 1-char re-serialization drift (TN strip appends `\n`) causing double-fire. Pairs each found tag with the relevant rule in `modifications[]` to decide LEAK vs SUS.
- `classify_req(entry, prev_entry) -> dict` — per-REQ 5-bucket classification. EFFECTIVE via chunk-tuple-diff against `prev.stripped_msg_removed` (skips chunks unchanged since prev). INERT via counter-delta on `modifications[]` filtered by "no chunks attributable". IDX from `smi` diff with empty `stripped_msg_removed[idx]`. LEAK/SUS delegate to `classify_tags` (inherits delta scope automatically — no separate first_diff_index handling needed).
- `legend_markdown() -> str` — Markdown legend block (3 tables: Buckets, Rules, Tag Literals) emitted at the top of audit reports.
**Reads:** Nothing at module level.
**Writes:** Nothing — pure data + helpers.
**Called by:** `dev/tool_use_analysis/strip_audit.py` (via sys.path insertion) for full legend + classify_req delegation; `src/proxy_display/render_messages.py` for attribute_chunk, classify_tags, code_for_rule, classify_req (monitor `_aggregate_req_buckets` is a thin delegate); `src/proxy/logging.py` (imports `attribute_chunk as _attribute_chunk` for fn_map attribution in `_build_stripped_injected_deltas`).
**Calls out:** `collections.Counter` (counter-delta inside classify_req).

---

### payload_helpers.py (202 LOC)

**Purpose:** Low-level payload content inspection and manipulation used by `rules.py` — find/strip system-reminder blocks, strip blocklisted tool_reference blocks, strip task-notification XML tags. Exports two content-search helpers with distinct scopes: `_content_contains` (descends into tool_result — used by SR-strip guards which legitimately match tool_result content); `_top_level_content_contains` (top-level str/text only, never tool_result — used by wakeup-injection guards to prevent false-positive injection from marker strings in tool_result data). `_find_system_reminder_blocks` and `_find_all_system_reminder_blocks` patterns include `\n?` after `</system-reminder>` (with `re.DOTALL`) — recorded chunk includes the trailing newline that `_STANDALONE_SR_RE` strips, closing the precision gap in GT span building.
**Reads:** Message content (string or list), payload dicts.
**Writes:** Nothing — returns modified content or filtered dicts.
**Called by:** `src/proxy/rules.py`
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

**Strip-tracking is guarded per-rule.** In `rules.py` second-pass, each rule (skills / claudemd / pyright) appends to `pass_mods` only if its strip function actually changed the content (`new_content != content`). Without this guard, `_content_contains` could match a marker that `_strip_system_reminder` then fails to strip (e.g. template identifier mismatch) — and `pass_mods` would incorrectly mark the rule as fired, polluting `modifications` and causing `stripped_msg_removed` to capture chunks that still survive in `raw_payload`. Root case: claudemd `"Contents of "` identifier vs CC's preamble form `"As you answer the user's questions"` — two distinct SR variants for the same template that previously went unmatched.

**Pyright-strip lives in the second pass, not the first-pass elif-chain.** `rules.py` has two passes: a first `elif`-chain (exclusive per message — a message that hits one elif cannot trigger another), and a cumulative second pass. Pyright diagnostics SRs can co-occur in the same message with Skills or claudeMd SRs; if pyright lived in the elif-chain it would be silently skipped for those messages. Any new rule that can co-occur with an existing first-pass rule MUST go to the second pass. The structural separation between `_apply_first_pass` and `_apply_cumulative_sr_strips` in `rules.py` enforces this invariant.


**`_PRESERVE_PREAMBLE` guard in strip_sr.py.** `strip_sr.py` has a hard-coded guard that prevents stripping claudeMd-context SR blocks: an SR whose inner text starts with `"As you answer the user's questions, you can use the following context:"` is always preserved verbatim, regardless of template matching. This allows the CLAUDE.md project-context block (injected by CC as a claudeMd SR with preamble) to survive the claudemd-strip rule. Adding new "preserve entire block" logic: mirror this pattern — `startswith` check in the extractor before template dispatch. **Exception: any new strip rule whose target block shares the same preamble (e.g. env-context SR) MUST insert its check BEFORE the `_PRESERVE_PREAMBLE` guard** — otherwise the guard fires first and the strip never runs. See `_ENV_CONTEXT_RE.fullmatch(inner)` check in `_apply_sr_strip._replace` for the pattern.
