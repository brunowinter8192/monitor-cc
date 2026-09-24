# src/proxy/

## Role

mitmproxy addon package that intercepts every Messages request from Claude Code, applies a deterministic modification pipeline (rule injection, content stripping, tool injection, fixation, cache breakpoints), logs the exchange and forwards the result. Touch it to change what gets injected, stripped, cached or logged. Do not edit during a live proxy session; the running proxy uses a frozen copy.

## Public Interface

`__init__.py` is empty. The entry path is `src/proxy_addon.py`, which mitmproxy loads via `-s` (see `src/claude_proxy_start.sh`).

## Flow

Request hook in `addon.py` → `rules.py` and the strip modules → `fixation.py`, `tools.py`, `tool_injection.py`, `inject_helpers.py`.
→ `addon_dual_log.py` writes the dual-log streams → `cache.py` places breakpoints → payload forwarded to Anthropic.
Response side: `response_model_probe.py` inspects the stream; the response and model-mismatch records are written from the response or error hook.

## Modules

### addon.py (331 LOC)

**Purpose:** mitmproxy hook class that orchestrates the request-modification and dual-log pipeline and writes the response record.
**Reads:** mitmproxy flows; process environment for project and log id.
**Writes:** the modified request payload and headers in place; flow metadata handed from request to response hooks.
**Called by:** `src/proxy_addon.py`; mitmproxy.
**Calls out:** `mitmproxy`

---

### response_model_probe.py (28 LOC)

**Purpose:** Builds a per-flow stream callable that reads the answering model from streamed SSE bytes without buffering the body.
**Reads:** raw response chunks passed by mitmproxy.
**Writes:** a state dict the addon stores in flow metadata.
**Called by:** `addon.py`; `dev/proxy_instrumentation/p8_answering_model_probe_test.py`.
**Calls out:** none

---

### addon_dual_log.py (148 LOC)

**Purpose:** Builds and writes the dual-log JSONL entries and the flat API error log for one request/response cycle.
**Reads:** flows and payload dicts from the addon; process environment; repo root via `proxy_error_log.py`.
**Writes:** the runtime dual-log streams and the flat API error log (both gitignored under the runtime log directory).
**Called by:** `addon.py`.
**Calls out:** none

---

### addon_state.py (35 LOC)

**Purpose:** Plain state holder classes for the addon's per-concern instance state.
**Reads:** none.
**Writes:** none (instances are mutated by the addon).
**Called by:** `addon.py`.
**Calls out:** none

---

### proxy_error_log.py (72 LOC)

**Purpose:** The proxy's error channel: size-capped timestamped log with tracebacks; also provides the repo root to sibling modules.
**Reads:** repo root via `monitor_root`.
**Writes:** the proxy error log in the runtime log directory.
**Called by:** `addon.py`, `addon_dual_log.py`, `bg_escape.py`, `inject_helpers.py`, `inject_poread.py`, `rules_config.py`, `tool_injection.py`; `dev/proxy/test_proxy_error_log.py`.
**Calls out:** none

---

### bg_escape.py (102 LOC)

**Purpose:** Sends a tmux Escape into a worker pane the first time a background-launch acknowledgement is detected.
**Reads:** stripped-content data and worker context from the addon.
**Writes:** an event log in the runtime log directory; tmux keystrokes; in-memory set of handled task ids.
**Called by:** `addon.py`.
**Calls out:** none

---

### rules_config.py (89 LOC)

**Purpose:** Loads and mtime-caches the proxy rules file and system2 rule texts; owns the shared main-session predicate.
**Reads:** the proxy rules JSON and rule files in the shared-rules directory of the home folder.
**Writes:** none.
**Called by:** `rules.py`, `message_passes.py`, `inject_helpers.py`, `bg_escape.py`.
**Calls out:** none

---

### rules.py (142 LOC)

**Purpose:** Runs the message-pass pipeline and the system-block replacement pass, returning the modified payload and its op records.
**Reads:** raw payload; system2 rule text via `rules_config.py`.
**Writes:** none (returns the modified payload and modification records).
**Called by:** `src/proxy_addon.py`, `addon.py`.
**Calls out:** none

---

### rule_ops.py (62 LOC)

**Purpose:** Op-recording primitives that every message pass uses to record strip/inject positions for later log reconstruction.
**Reads:** none.
**Writes:** none.
**Called by:** `message_passes.py`, `message_passes_simple.py`, `message_passes_wakeup.py`, `rules.py`.
**Calls out:** none

---

### message_passes.py (252 LOC)

**Purpose:** The structural message-level passes that do not fit the generic spec runner.
**Reads:** message list; the rules config.
**Writes:** none (returns new structures).
**Called by:** `rules.py`.
**Calls out:** none

---

### message_passes_simple.py (184 LOC)

**Purpose:** Spec-driven pass runner plus the declarative specs for the simple per-block strip rules.
**Reads:** message list.
**Writes:** none (returns new structures).
**Called by:** `rules.py`.
**Calls out:** `constants` (via `inject_poread.py`)

---

### message_passes_wakeup.py (68 LOC)

**Purpose:** Deduplicates repeated wake-up texts within a message and unwraps a system-reminder wrapper around a task notification.
**Reads:** message content passed as arguments.
**Writes:** none.
**Called by:** `rules.py`, `message_passes.py`.
**Calls out:** none

---

### cache.py (140 LOC)

**Purpose:** Strips all existing cache markers from a payload and places the new breakpoints.
**Reads:** payload; previous request's message summaries.
**Writes:** none (returns the modified payload).
**Called by:** `addon.py`.
**Calls out:** none

---

### strip_sr.py (162 LOC)

**Purpose:** Strips system-reminder blocks from message content through a catalog of exact-match templates.
**Reads:** message content; module-local template catalog.
**Writes:** none (returns modified content).
**Called by:** `message_passes.py`.
**Calls out:** none

---

### strip_po.py (63 LOC)

**Purpose:** Strips the preview section from persisted-output blocks while keeping the wrapper and header line.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_bg_launch_ack.py (79 LOC)

**Purpose:** Replaces the background-launch acknowledgement wordings with a short hold instruction.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`, `bg_escape.py`.
**Calls out:** none

---

### inject_poread.py (81 LOC)

**Purpose:** Recognizes a poread export marker with its notice sentence and replaces the whole block with the file's content.
**Reads:** message content; the named file from disk.
**Writes:** proxy error log on a failed validation; returns content and removed texts.
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_bg_completed.py (55 LOC)

**Purpose:** Replaces the first background-Bash kill notification in a message with a wake-up hint and strips later duplicates.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`, `message_passes.py`, `message_passes_wakeup.py`.
**Calls out:** none

---

### strip_hook_prefix.py (61 LOC)

**Purpose:** Strips the hook-error wrapper prefix from tool results.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_git_lock.py (63 LOC)

**Purpose:** Strips the constant git index-lock advice block from tool results, keeping the variable warning line.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_bd_noise.py (71 LOC)

**Purpose:** Strips bd auto-import/export status lines from tool results.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_interrupt_marker.py (19 LOC)

**Purpose:** Replaces the interrupt-marker wordings that result from the tmux Escape of `bg_escape.py` with a placeholder.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_pasted_content.py (47 LOC)

**Purpose:** Removes the paste wrapper tag pair around bracketed-paste user messages, keeping the text byte-for-byte.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`.
**Calls out:** none

---

### strip_sn_notice.py (53 LOC)

**Purpose:** Strips the system-notification paragraph injected ahead of task-notification tags in wake-up messages.
**Reads:** message content.
**Writes:** none (returns content and removed texts).
**Called by:** `message_passes_simple.py`, `message_passes_wakeup.py`.
**Calls out:** none

---

### content_strip.py (156 LOC)

**Purpose:** Strips or extracts non-system-reminder content: rejection results, session-start extraction, system-block cleanup and tool description stripping.
**Reads:** message content; full payload for tool and system strips.
**Writes:** none (returns modified content or payload).
**Called by:** `rules.py`, `message_passes.py`, `addon.py`.
**Calls out:** none

---

### diff_engine.py (207 LOC)

**Purpose:** Aligns and classifies strip, inject and equal spans between the original and forwarded payloads.
**Reads:** payload dicts passed as arguments.
**Writes:** none (returns diff results).
**Called by:** `strip_inject_delta.py`.
**Calls out:** none

---

### logging.py (245 LOC)

**Purpose:** Builds forwarded-delta and tool-error log entries and owns the payload normalization and hashing shared with the stripped/injected pipeline.
**Reads:** payloads, message lists, previous summaries and hash state.
**Writes:** none (returns entry dicts).
**Called by:** `addon_dual_log.py`, `cache.py`, `strip_inject_delta.py`.
**Calls out:** none

---

### strip_inject_delta.py (287 LOC)

**Purpose:** Builds the stripped and injected delta entries from an original/forwarded payload pair with per-location hash chains and function attribution.
**Reads:** original and forwarded payloads; previous hash state; ops from flow metadata.
**Writes:** none (returns the two entries and new hash state).
**Called by:** `addon_dual_log.py`.
**Calls out:** none

---

### message_summary.py (183 LOC)

**Purpose:** Summarizes message content into compact log dicts and owns the single model-family classifier used across proxy and display code.
**Reads:** message dicts; model id strings.
**Writes:** none (returns summaries or a family string).
**Called by:** `addon.py`, `logging.py`, `cache.py`, `src/proxy_display/forwarded_parser.py`, `src/dual_log_cli/reader.py`.
**Calls out:** none

---

### tool_injection.py (179 LOC)

**Purpose:** Appends MCP tool schemas to the payload tool list in a stable order to avoid cache rebuilds.
**Reads:** the gitignored schema store inside this package; the project's active-plugins file; the rules file's exclude list.
**Writes:** none (returns the modified payload).
**Called by:** `addon.py`, `fixation.py`.
**Calls out:** none

---

### tools.py (45 LOC)

**Purpose:** Pipeline helpers that remove blocklisted tools and read the deferred-tool names before their reminder is stripped.
**Reads:** payload with tools and messages.
**Writes:** none (returns tuples or lists).
**Called by:** `addon.py`.
**Calls out:** none

---

### fixation.py (71 LOC)

**Purpose:** Captures and replays system2, the message-0 project-rules block and the active plugins after the first request per model family.
**Reads:** modified payload; fixated state.
**Writes:** none (returns updated state or payload).
**Called by:** `addon.py`.
**Calls out:** none

---

### inject_helpers.py (127 LOC)

**Purpose:** Injects model parameters and the context-management block into the payload and reconciles contradictory combinations.
**Reads:** payload; fixation state; the rules config on a cache miss.
**Writes:** the caller-owned fixated model override state; returns the modified payload.
**Called by:** `addon.py`.
**Calls out:** none

---

### strip_vocab.py (224 LOC)

**Purpose:** Shared vocabulary and classification for strip attribution and the per-request strip classifier used by audit tooling and the display.
**Reads:** none.
**Writes:** none (pure data and helpers).
**Called by:** `strip_inject_delta.py`, `src/proxy_display/render_messages.py`, `dev/tool_use_analysis/strip_audit.py`.
**Calls out:** none

---

### payload_helpers.py (220 LOC)

**Purpose:** Low-level payload inspection and manipulation: system-reminder block lookup, tool-reference stripping and the whole-text block walker.
**Reads:** message content; payload dicts.
**Writes:** none (returns modified content or dicts).
**Called by:** `rules.py`, `message_passes.py`, `message_passes_simple.py`, `strip_bg_launch_ack.py`, `strip_interrupt_marker.py`, `strip_inject_delta.py`.
**Calls out:** none

---

## State

`tool_injection.py` holds process-wide schema and active-plugin caches. `addon.py` owns the per-session addon state through the collaborators in `addon_state.py` and resets on hot-reload. `bg_escape.py` owns a process-wide set of handled task ids. Details and the full gotcha list are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file).
