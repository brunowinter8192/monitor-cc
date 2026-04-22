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

### addon.py (249 LOC)

**Purpose:** Core mitmproxy addon class — receives HTTP flows, orchestrates the full modification pipeline, writes JSONL log entries, saves error payloads on 4xx responses.
**Reads:** mitmproxy `http.HTTPFlow`; env vars `MONITOR_CC_ROOT`, `PROXY_LOG_ID` for log path resolution.
**Writes:** Modifies `flow.request.content` in place; appends to `src/logs/api_requests_*.jsonl`; writes `src/logs/api_error_payload_*.json` on 4xx.
**Called by:** mitmproxy (via `addons = [ProxyAddon()]` at module level)
**Calls out:** `mitmproxy`

---

### rules_config.py (82 LOC)

**Purpose:** Load and cache proxy rule files — reads `proxy_rules.json`, caches rule file content by mtime, assembles system2 rule text for a given model family and project path.
**Reads:** `~/.claude/shared-rules/proxy_rules.json` and rule files (mtime-cached).
**Writes:** Nothing — returns config dict or assembled rule text.
**Called by:** `rules.py`, `inject_helpers.py`
**Calls out:** stdlib only (`json`, `pathlib`).

---

### rules.py (243 LOC)

**Purpose:** Apply proxy modification rules — strip system-reminders, task-notification tags, plan-mode blocks, rejection messages; inject system2 rules into `system[2]`; normalize worktree paths in `system[3]`. Single exported function `apply_modification_rules`. Remainder 243 LOC is a single monolithic function body — further split requires refactoring.
**Reads:** Raw payload dict; rule text via `rules_config._load_system2_rules`.
**Writes:** Nothing — returns `(modified_payload, modifications, original_system2_text, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed)` 6-tuple.
**Called by:** `src/proxy/addon.py`
**Calls out:** `rules_config`, `content_strip`, `payload_helpers`.

---

### cache.py (135 LOC)

**Purpose:** Strip all existing cache_control markers from a payload and place new breakpoints (Tools Anchor, Tools End, BP3 last-unchanged-msg, BP4 last-msg).
**Reads:** Payload dicts; previous request's message summaries (for BP3 unchanged-prefix detection); previous tools count (for anchor-on-growth logic).
**Writes:** Nothing — returns modified payload dicts.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_sr.py (161 LOC)

**Purpose:** Strip `<system-reminder>` tag blocks from API message content via template-based exact-match. Maintains a catalog of 8 known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed); each has a unique identifier-string. Strip uses `startswith` against extracted SR-block text — no greedy regex across code literals.
**Reads:** Message content (string or list of blocks); template catalog (module-local).
**Writes:** Nothing — returns modified content.
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

### logging.py (136 LOC)

**Purpose:** Build structured JSONL log entries from flow + payload data; compute message diffs vs previous request.
**Reads:** Raw payload dicts, message lists, previous message summaries.
**Writes:** Nothing — returns structured entry dict.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

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

### tools.py (23 LOC)

**Purpose:** Strip blocklisted tools from `payload["tools"]` using `TOOL_BLOCKLIST`.
**Reads:** Payload dict with tools list.
**Writes:** Nothing — returns `(modified_payload, count_removed)`.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

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

### inject_helpers.py (80 LOC)

**Purpose:** Inject model override (model/thinking/effort/max_tokens) and `context_management` payload block from `proxy_rules.json` config.
**Reads:** Payload dict, model_family string; `proxy_rules.json` via `rules_config._load_config()`.
**Writes:** Nothing — returns `(modified_payload, injected_bool)`.
**Called by:** `src/proxy/addon.py`
**Calls out:** —

---

### strip_vocab.py (229 LOC)

**Purpose:** Shared vocabulary + semantics for proxy strip classification. Single source of truth used by `dev/tool_use_analysis/strip_audit.py` and `src/proxy_display/` (monitor). MUST be updated in lockstep when `rules.py` adds/renames rules or changes markers. Exports:
- Constants: `BUCKETS` (EFF/INERT/IDX/LEAK/SUS), `RULES` (CMD/SK/DEF/NAG/TN/PYR/UI/PM/REJ/ALL with markers), `TAG_LITERALS` (PO/SR/TN/ND), `STRIP_RULE_CODES`.
- `attribute_chunk(chunk) -> code | None` — marker-substring attribution (starts-with special-case for TN).
- `code_for_rule(full_name) -> code | None` — reverse lookup from `modifications[]` entry to rule code.
- `classify_tags(entry) -> (leak_signals, sus_signals)` — scans `messages[].blocks[].full_text` for the 4 tag literals, pairs each with the relevant rule in `modifications[]` to decide LEAK vs SUS.
- `classify_req(entry, prev_entry) -> dict` — per-REQ 5-bucket classification. EFFECTIVE via chunk-tuple-diff against `prev.stripped_msg_removed` (skips chunks unchanged since prev). INERT via counter-delta on `modifications[]` filtered by "no chunks attributable". IDX from `smi` diff with empty `stripped_msg_removed[idx]`. LEAK/SUS delegate to `classify_tags`.
- `legend_markdown() -> str` — Markdown legend block (3 tables: Buckets, Rules, Tag Literals) emitted at the top of audit reports.
**Reads:** Nothing at module level.
**Writes:** Nothing — pure data + helpers.
**Called by:** `dev/tool_use_analysis/strip_audit.py` (via sys.path insertion) for full legend + classify_req delegation; `src/proxy_display/render_messages.py` for attribute_chunk, classify_tags, code_for_rule, classify_req (monitor `_aggregate_req_buckets` is a thin delegate).
**Calls out:** `collections.Counter` (counter-delta inside classify_req).

---

### payload_helpers.py (140 LOC)

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

**SR stripping is template-based, not regex-greedy.** `strip_sr.py` maintains a catalog of known SR templates (task-tools-nag, pyright-new-diagnostics, deferred-tools, user-interrupt, system-notification, file-modified, claudemd-contents, date-changed). Each template has a unique identifier-string; matching uses `startswith` against the extracted SR-block text, not a greedy regex. This is the fix for the historical false-positive bug where `<system-reminder>.*?</system-reminder>` matched across code literals (e.g. `if "<system-reminder>" in text:` in a tool_result) and stripped real user code. Adding a new strip rule = add a new template entry with its identifier-string. Tool_result.content IS strippable — CC does inject SRs there (task-tools-nag appended to tool-outputs), and the template-based matcher correctly distinguishes real SRs from code literals.
