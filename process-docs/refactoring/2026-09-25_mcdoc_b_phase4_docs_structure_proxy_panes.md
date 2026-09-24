# Phase 4 DOCS.md restructure: proxy, proxy_display, dual_log_cli, panes, gpu_pane, news_pane (2026-09-25)

## Why this file exists

The DOCS.md files of six src/ directories were rewritten to module level only (no function, method, class or constant names, no thresholds, no gotcha lists). Everything that a successor needs and that is not recoverable from reading the code was moved here verbatim from the previous DOCS.md revisions. Function and constant names are kept intentionally in this file. Line references like `Gotchas` inside the quoted text point to the section quoted here, not to a DOCS.md section.

Format decisions for the rewritten files:
- Role <= 50 words, Public Interface, Flow (3-5 lines), Modules (Purpose <= 25 words), State (owner/mutator/reader in one short paragraph).
- Called by for modules whose only callers are dev/ tests keeps the dev path; a module with no caller would be marked DEAD CODE (none found in these six directories).
- LOC headings equal wc -l at rewrite time.
- Stale path fixed: the proxy DOCS.md pointed to a poread CLI path under src/ that no longer exists in this repo (the CLI lives in the iterative-dev plugin).

Pointers from the old DOCS.md to other process-docs areas that remain valid: abort_cascade, message_strip_fp_nuke, proxy_tool_stripping, proxy_instrumentation, dual_log_cli, proxy_display, pane_flicker.

## proxy: module details (old addon.py and inject_poread.py entries)

```
### addon.py (331 LOC)

**Purpose:** mitmproxy addon hook class (`ProxyAddon`) that receives HTTP flows and orchestrates the full request-modification and dual-log pipeline; `count_tokens` requests pass through unmodified.
**Reads:** mitmproxy `http.HTTPFlow`; env vars `PROXY_PROJECT_PATH`, `PROXY_LOG_ID` (required; a missing one raises at import, a `worker_` id that does not parse raises).
**Writes:** `flow.request.content` (modified payload, in place); `flow.request.headers` (`content-encoding` popped, `accept-encoding: identity` forced via `_request_identity_encoding`); `flow.metadata` (`mc_original_payload`, `mc_modified_payload`, `mc_model_family`, `mc_all_ops`, `mc_request_id`, `mc_answering_model_state`, `mc_response_entry_written`, `mc_model_mismatch_logged` — stashed in `request()`/`responseheaders()`, read/set in `response()`/`error()`). `_response` dual-log entry carries three distinctly-named model fields side by side — `cc_requested_model` (from `mc_original_payload`, what Claude Code asked for), `proxy_forwarded_model` (from `mc_modified_payload`, what the proxy actually sent — equal to the model Claude Code requested, since the proxy no longer rewrites the model id), `answering_model` (from the streamed probe state, what the API answered with) — written by `_write_response_entry`, called (via `_write_response_and_mismatch`) from both `response()` and `error()` (mitmproxy fires exactly one of the two per flow, never both) so a client-side mid-stream abort still produces an entry; `mc_response_entry_written` guards against a double write if that invariant is ever violated. When `proxy_forwarded_model` and a non-empty `answering_model` differ, `_write_model_mismatch_entry` additionally writes one `type: model_mismatch` record straight to the session `_errors` dual-log (`paths.errors`, the same file `addon_dual_log._log_errors_entries` writes tool_error records to) in the exact shape `warnings_pane._errors_record_to_display` expects (`tool_name`/`error_full`/`ts`/`worker`/`tool_use_id: ""`) — written independently of that function's `tool_use_id` dedup set, so it can never interact with it; `mc_model_mismatch_logged` guards its own double write. Actual dual-log file writes are delegated to `addon_dual_log.py`.
**Called by:** `src/proxy_addon.py` (imports `ProxyAddon`, `addons`); mitmproxy itself via `addons = [ProxyAddon()]` at module level (hooks: `request`, `responseheaders`, `response`, `error`).
**Calls out:** `mitmproxy`
### inject_poread.py (81 LOC)

**Purpose:** Recognizes a `<poread-export ...>` marker plus its fixed notice sentence as one whole `tool_result` block, replaces it with the file's full content.
**Reads:** Message content (string or list of blocks); the named file's bytes from disk, up to its own `POREAD_MAX_BYTES`.
**Writes:** — (returns `(modified_content, list[str])`); `src/logs/proxy_error.log` diagnostic (source `inject_poread <path>`, logged once per changed reason) when a structurally-valid marker fails validation (source changed, vanished, declares a size over the ceiling, or the block is not EXACTLY the marker followed by `POREAD_NOTICE` — a marker with no notice under it, different trailing text, or anything chained after it in one Bash call, leaves the whole block untouched rather than being silently dropped) — never partially expanded, and never cached across requests: size + truncated sha256 are both recomputed from disk on every call. This gives the notice sentence a property for free: when expansion succeeds it disappears along with the marker (both were part of the one matched-and-replaced block); when it doesn't, the notice stays in the agent's own context, which is exactly the case where it needs the explanation. Within one call, the file is opened exactly once — `_inject_poread_content` hands the predicate's own validated bytes to the replacement via a closure-scoped cache keyed by the exact marker text, so there is no second read and no window in which the source could change between validation and use (a benign race there would previously raise inside `_build_poread_replacement` and, uncaught, cause `ProxyAddon.request()`'s outer handler to skip ALL modifications for that request, not just this one marker).
**Called by:** `src/proxy/message_passes_simple.py` (`_apply_poread_expand_strip`).
**Calls out:** none — `POREAD_MAX_BYTES`/`POREAD_HASH_LEN`/`POREAD_MARKER_PREFIX`/`POREAD_NOTICE` are this module's own constants now (see Gotchas), no more `constants`-module `sys.path` bootstrap.
```

## proxy: State and Gotchas (old sections, verbatim)

## State

`tool_injection.py` holds four module-level caches (set once per mitmproxy process): `_SCHEMA_STORE_CACHE` (all plugin schemas from the gitignored schemas directory under `src/proxy/`, populated by `dev/tool_injection/01_extract_schemas.py`); `_ACTIVE_PLUGINS_CACHE`/`_ACTIVE_PLUGINS_MTIME`/`_ACTIVE_PLUGINS_PATH` (active-plugin list, mtime-reloaded).

`addon.py` owns `ProxyAddon` instance state via 4 collaborator objects from `addon_state.py`: `self.delta` (per-model-family delta-chain dicts for BP3 unchanged-prefix detection and the forwarded/stripped/injected/errors dedup chains), `self.fixation` (`fixated` — sys2/msg0 snapshot per model_family; `model_params_fixated` — resolved model-params snapshot per exact model id, owned by `inject_helpers._inject_model_override`), `self.identity` (`session_id`, `worker_context` — computed once at `__init__`, immutable for the process lifetime in production; a few `dev/` probes overwrite `worker_context` directly after construction). All of this state resets on mitmproxy hot-reload.

`bg_escape.py` owns `_escaped_task_ids` — a module-global (not per-`ProxyAddon`-instance) in-memory set of background-task ids that have already fired an Escape, for this proxy process's lifetime. Resets on hot-reload or a full process restart. `bg_escape_events.jsonl` is append-only across restarts even though `_escaped_task_ids` is memory-only, so a restart-caused extra fire is still visible in the log.

## Gotchas

**The proxy runs with `mitmdump -q 2>/dev/null`, so nothing printed to stderr survives.** Every swallowed exception and refusal in this package goes through `proxy_error_log.log_proxy_error` into `src/logs/proxy_error.log`; the fail-open behaviour of the handlers is unchanged.

**The live copy resolves code outside `proxy/` from the repo checkout.** `src/proxy_addon.py` puts the repo root on `sys.path` next to the live `proxy/` directory, so `from src.constants import ...` and `from src.monitor_root import ...` load the checkout's files, not copies.

**`_TrailerCrashFilter` drops one specific mitmproxy crash record, not crash logging in general.** It filters the `NotImplementedError: HTTP trailers are not implemented yet` `LogRecord` mitmproxy 12.x raises from `proxy/layers/http/_http1.py`; every other `mitmproxy has crashed!` record still reaches stderr.

**`_process_fields_section` never contributes to `fn_map` — only the `sys`/`tools`/`messages` sections do.** Every top-level field (`model`/`max_tokens`/`thinking`/`output_config`/`context_management`) that shows up in a `stripped_delta`/`injected_delta` entry's `fields_delta` carries NO function attribution in the real written JSONL `fn_map`. `strip_inject_delta.py` used to hold its own unread `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` maps for this — removed as dead code, since nothing consumed them and they had already drifted from the live copy (missing the `context_management` strip-side entry). The only attribution for `fields_delta` entries now lives in `dev/proxy_dual_log/attribution_coverage/attribution_coverage.py`'s own local `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` maps — update those directly if a field's owning function ever changes.

**An op-less strip still rewrites the payload — it only loses its dual-log entry, silently.** `message_passes` sets new content directly; the op is recorded separately via `_ops_from_content_change`. If a pass changes content shape (e.g. list→str) in a way the op-builder doesn't handle, the op comes back empty, `strip_inject_delta._process_messages_section` skips the message (`if s_texts:`), and nothing marks the strip anywhere visible — the forwarded payload is still correct, but no pane or CLI can show it happened. When adding a pass that changes content shape, verify the message index appears in `all_ops`, not just that the payload is right.

**`bg_escape.py`'s per-task-id dedup (`_escaped_task_ids`) is load-bearing, not an optimization.** A second `tmux send-keys ... Escape` into an already-idle or menu-open CC TUI opens the quit menu. The raw launch-ack text stays in the worker's own conversation history and is resent on nearly every subsequent request, so relaxing the dedup (e.g. to "per request" or "per tick") would re-fire the Escape on almost every request.

**Hot-reload resets all `ProxyAddon` state.** mitmproxy hot-reloads addon scripts on any file change under `src/proxy/`, so BP3 loses its unchanged-prefix reference and forces a full cache rebuild. `claude_proxy_start.sh` works around this by copying `proxy_addon.py` and the entire `src/proxy/` package to `src/logs/.proxy_live_<id>/proxy/` at startup — that live copy is what actually runs; a direct edit to the live copy affects the running proxy immediately, but an edit to the repo copy does not until the next start.

**Worker proxies are frozen at spawn time.** Each worker's `src/logs/.proxy_live_worker_<name>/` snapshot never updates. A worker spawned before a proxy-touching merge cannot reach the new code until it is killed and respawned.

**SR stripping matches via `startswith` against extracted inner text, never a greedy regex across the whole message.** A greedy `<system-reminder>.*?</system-reminder>` would match across code literals inside `tool_result` and strip real user code — this is why `strip_sr.py` uses a template catalog instead.

**The SR family never descends into `tool_result` content.** `strip_sr.py`, `_apply_first_pass`'s SR branches, `_apply_cumulative_sr_strips`, and `_find_system_reminder_blocks`/`_find_all_system_reminder_blocks` (`payload_helpers.py`) only scan top-level `str`/`text` blocks. Adding `tool_result` descent to any SR-family strip reintroduces false-positive stripping of quoted SR examples inside tool output. The non-SR passes (git-lock, hook-prefix, bd-noise, po-preview, bg-launch-ack) intentionally do descend into `tool_result` and are unaffected by this constraint.

**In `_apply_cumulative_sr_strips`, a rule only counts as fired if its strip function actually changed the content.** A marker-guard match with no matching strip (template-identifier mismatch) must not append to `pass_mods`, or `modifications`/`stripped_msg_removed` desyncs from what the forwarded payload actually contains.

**Pyright-diagnostics stripping lives in `_apply_cumulative_sr_strips`, never in `_apply_first_pass`'s elif-chain.** The elif-chain is exclusive per message (one branch wins); pyright SRs can co-occur in the same message as Skills/agent-types/claudeMd SRs. Any new rule that can co-occur with an existing first-pass rule must go in the cumulative pass, not the elif-chain.

**`_PRESERVE_PREAMBLE` in `strip_sr.py` unconditionally preserves any SR whose inner text starts with the CLAUDE.md-context preamble.** A new strip rule targeting a block that shares this preamble (e.g. the env-context SR) must insert its own check BEFORE this guard, or the guard wins and the new strip never fires — see `_ENV_CONTEXT_RE.fullmatch(inner)` in `_apply_sr_strip._replace` for the pattern.

**`_apply_role_system_strip`'s blanket `role='system'` → `"."` nuke has two content-anchored carve-outs checked before the nuke** (truncation-notice prefix, top-level `<task-notification>` presence). A new carve-out must follow the same anchored-check shape and add a matching exception to `strip_inject_delta.py`'s `role=='system' → 'RS'` attribution shortcut, or `fn_map` mislabels the change as the blanket nuke.

**The session `_errors` dual-log carries two record shapes now, and `warnings_pane._errors_record_to_display` discriminates neither.** Real `tool_error` records (`addon_dual_log._log_errors_entries` → `logging._build_errors_entries`, request-side, deduped by `tool_use_id`) and `model_mismatch` records (`addon._write_model_mismatch_entry`, response-side, one-shot per flow) are structurally unrelated writers into the same file — the pane just renders whatever dict shows up as long as it carries `tool_name`/`error_full` (everything else defaults via `.get(..., '')`). A third record type added later must follow the same two-field minimum or it renders as a blank/garbled row with no error and no warning that something is missing.

**A client-side mid-stream abort is the common case, not the exception, in this project — see `process-docs/abort_cascade/`.** Claude Code cancels the SSE connection and refires on any incoming event while a stream is open (user keystroke, background-task completion, subagent task-notification); depth-3+ cascades are routine. mitmproxy fires exactly one of `response`/`error` per flow, never both (`HttpErrorHook`'s own docstring: "Every flow will receive either an error or an response event, but not both."). Any per-request write that must survive an abort — the `_response` dual-log write is the current example — has to be called from both `response()` and `error()`, not just `response()`; a write that only lives in `response()` silently disappears for every aborted REQ, which given the cascade frequency here means most REQs, not a rare edge case.

**`response_model_probe.py` needs uncompressed bytes to ever match — `_request_identity_encoding` is what makes that true in real traffic, not a body-decompression path.** The probe regexes raw wire bytes; a `gzip`/`br`-compressed SSE body never contains the literal `"message_start"` text, so `answering_model` stayed empty on every real (non-test) request until `ProxyAddon.request()` started forcing `accept-encoding: identity` on the outbound Messages request. This is a request-side fix, not a response-side decompression path — deliberately, per this project's stance against building/maintaining a decompression layer. Applies uniformly to every Messages request regardless of whether the response turns out to stream or not (not knowable at request time), including the non-streaming JSON side calls (`claude-haiku-4-5`, `content-type: application/json`) — harmless there since their body never contains `message_start` either way, compressed or not.

**`strip_pasted_content.py` only ever touches top-level `text` blocks on `role='user'` messages, by design, not a placeholder.** CC's bracketed-paste wrapper is CC's own formatting of the user's own message text, so it structurally cannot appear inside a `tool_result` (a tool's return value) or on a non-`user` role — and real corpus confirms this both ways: a well-formed, matching-id `<pasted_content id="...">...</pasted_content id="...">` pair shows up quoted verbatim inside a `role='assistant'` text block in a real session (only the role gate saves it), and inside `tool_result` blocks from `Read`/`Bash` tool output quoting this same feature's own task/process docs (only the no-`tool_result`-descent saves those). Same precedent as the SR-family `tool_result`-descent removal (`process-docs/message_strip_fp_nuke/2026-07-28_tool_result_sr_fix.md`) — do not widen either gate without fresh corpus evidence.

**`strip_bg_launch_ack.py`'s three wordings deliberately do NOT share one detection predicate.** `_is_bg_launch_ack` (the two deliberate/manual-launch wordings) stays untouched and is still what `bg_escape.py` imports to decide whether to fire a real tmux `Escape` keystroke into a worker's pane; the third wording (auto-backgrounded on timeout) is detected by a separate `_is_bg_auto_timeout_ack`, combined only inside `_strip_bg_launch_ack`'s own predicate via `_is_bg_launch_ack_any`. Widening `_is_bg_launch_ack` itself instead would have made `bg_escape.py` also fire on timeout auto-backgrounding — a real production side effect (see the `bg_escape.py`'s per-task-id dedup Gotcha above) this project never asked for. A future fourth wording should follow the same pattern: extend the strip's own combined predicate, never `_is_bg_launch_ack` directly, unless `bg_escape.py` is meant to fire for it too.

**`strip_vocab.py`'s `RULES['BL']` marker list must carry a literal for every wording `strip_bg_launch_ack.py` recognizes, by hand.** `attribute_chunk` matches by plain substring against the ORIGINAL removed ack text (not the code), and this file has zero imports from `strip_bg_launch_ack.py` by design (same separately-maintained-copy pattern as the `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` Gotcha above) — a new wording added to the strip without a matching literal here silently returns `None` from `attribute_chunk`, losing `fn_map` attribution for `stripped_delta`/`injected_delta` entries for that wording specifically, with no error anywhere.

**`addon_dual_log._is_sidecar_payload` (`len(payload.get("tools") or []) == 0`) mirrors `dual_log_cli.timeline_boundaries._is_sidecar`'s `counts.tools == 0` criterion, applied to the payload directly since `addon_dual_log.py` has not built a `counts` dict yet at the point it needs the check.** No import between the two — same separately-maintained-copy pattern as the `strip_vocab.py`/`RULES['BL']` Gotcha above — keep them in sync if the shape of a sidecar (a CC-internal zero-tool call: session-titling, quota check, security-monitor) ever changes. The sidecar's own `forwarded_delta` line is still written (full evidence stays visible, per this project's `process-docs/proxy_tool_stripping/sidecar_idle_recap_removal.md` stance against write-side content suppression) — only `DeltaState.forwarded_hashes_by_model[family]` is left un-advanced by it, so the next REAL request in that family keeps diffing against the last REAL request. `src/proxy_display/format.py`'s `_is_standalone_entry` was deliberately NOT widened to the same `tools == 0` criterion — every sidecar observed on disk is haiku, and its existing haiku check already excludes all of them from REQ numbering; see `process-docs/proxy_instrumentation/` for the measurement behind that call.

**`inject_poread.py`'s four marker constants (`POREAD_MAX_BYTES`, `POREAD_HASH_LEN`, `POREAD_MARKER_PREFIX`, `POREAD_NOTICE`) are a hand-maintained copy of the poread CLI's own copy in the iterative-dev plugin (`src/poread_cli/__main__.py` there), not a shared import — the CLI half moved out of this repo entirely (it needed `worker-cli`'s sibling-CLI home, stdlib-only, no venv), so the single `src/constants.py` both sides used to import from no longer spans both halves. Same separately-maintained-copy pattern as the `strip_vocab.py`/`RULES['BL']` Gotcha above.** A change to the marker prefix, the ceiling, the hash length, or the exact notice sentence on one side without the matching edit on the other makes every future marker silently stop expanding — the agent sees only the tiny marker-plus-notice lines forever, no error anywhere, exactly the "drift nobody notices" failure mode this pattern always risks. `dev/proxy/poread_inject_tests.py` pins its own independent literal copy of the same four values (hardcoded in the test file, not imported from this module) specifically so a drift in THIS module's copy fails that test loudly instead of silently minting an unexpandable marker; the iterative-dev CLI's own test does the same for its side. Cross-repo drift itself is not machine-detectable — there is no shared CI between the two repos — change both together by hand.

## proxy_display: module details (old proxy_pane_shared, worker_proxy_pane, render_messages, dual_log_accumulator entries)

```
### worker_proxy_pane.py (351 LOC)

**Purpose:** Event loop for the worker-proxy pane — watches the active worker list, reads the selected worker's `_forwarded` dual-log, handles digit-key and header-click worker switching, mouse/keyboard input, renders with a 2-row header (search bar + worker-switcher). Force-reload-or-tick refresh gate. The worker-switcher header itself is built by the shared `workers.worker_switch_header.format_worker_switch_header` (imported under the alias `_format_worker_proxy_header`, its pre-move name) — `_worker_proxy_workers` is enriched with token/context-% liveness via `worker_tmux.attach_worker_stats(_worker_proxy_workers, _worker_proxy_stats_cache)` before that header renders (incremental, own cache — see `workers/DOCS.md`'s `attach_worker_stats` gotcha for why this must stay incremental).
**Reads:** Module-level state; live worker list from `workers.worker_tmux`; worker selection IPC file (`workers.worker_selection.get_selection_file_path`); stdin.
**Writes:** frames to stdout via `frame_writer.write_frame` (header is the first rows of the built output); clipboard via `copy_to_clipboard`; worker selection IPC file via `workers.write_selection`; `/tmp/monitor_cc_error.log` on caught exception; mutates its own module-level state (including `_worker_proxy_stats_cache`, the per-session incremental read state `attach_worker_stats` owns — never reset on worker switch, same as `worker_tokens_pane.py`'s own copy).
**Called by:** `src/proxy_display/__init__.py`, `src/core/monitor.py` (lazy import, mode dispatch)
**Calls out:** `input.click_handler`, `workers.worker_tmux` (`find_worker_jsonl`, `list_workers`, `attach_worker_stats`), `workers.worker_selection` (`get_selection_file_path`), `workers` (`write_selection`), `workers.worker_switch_header` (`format_worker_switch_header`), `panes.cache_turns` (`build_cache_turns`), `utils` (`visual_line_count`), `ram_audit` (`register_ram_dump`), `pane_error_log` (`log_pane_error`), `search_bar`

### proxy_pane_shared.py (271 LOC)

**Purpose:** Mechanics shared by both proxy panes (`pane.py`, `worker_proxy_pane.py`), each function parameterized by explicit arguments — never reads either pane's own module-level globals. Covers key/entry-idx resolution, copy-text serialization, the flow_id-to-request_id and flow_id-to-status accumulation from `_response` (`_accumulate_request_ids`, `_attach_http_status` writing `entry['http_status']`), expand+lazy-load toggling, dual-log accumulate-and-attach, search-on-commit, scroll/hover dispatch, and render+scroll+row-shift. (2026-09) The worker-switcher header builder moved to `workers.worker_switch_header` — that pane's own header is now shared with `workers/worker_tokens_pane.py` too, and `proxy_display` already depends on `workers` one-directionally for worker discovery/selection, so the header followed that same direction rather than `workers` depending back on `proxy_display`.
**Reads:** Parameters only.
**Writes:** Nothing — returns values; several functions mutate an argument in place (`entries`, `line_map`, `copy_rows`, accumulator dicts) as documented per function, never a name outside the parameter list. `_prepare_copy_text` dispatches on key shape — a `('think', entry_idx, msg_idx, bidx)` key OR a `('block', entry_idx, msg_idx, bidx)` key both route to the same `_serialize_proxy_block` (one block's own `full_text`, with `preview` fallback; for a thinking block this is never its signature — the signature is never stored anywhere in this data, only its char count — the two key shapes share one serializer because nothing in its body was ever thinking-specific, only the guard was), a `('msg', entry_idx, msg_idx)` key routes to `_serialize_proxy_message`, everything else to `_serialize_proxy_entry` (unchanged); `_copy_feedback_key` returns the same `key` for a msg, think, or block row (so its flash never leaks onto the REQ header or a sibling row) and `entry_idx` for everything else, unchanged.
**Called by:** `src/proxy_display/pane.py`, `src/proxy_display/worker_proxy_pane.py` exclusively
**Calls out:** `side_logs` (`read_response_log`), `search_bar` (`SearchState`, `handle_search_mouse_motion`)
### dual_log_accumulator.py (112 LOC)

**Purpose:** Dual-log overlay accumulation — tails `_stripped`/`_injected`/`_original` and builds the per-family accumulator state both panes' entries hold references into. `accumulate_original_tools` keeps a latest-snapshot `{tool_name -> tool_def}` map per family (the `_original` log is a full-snapshot log, not delta-encoded). `accumulate_dual_log` mutates its accumulator dict in place (`.clear()`+`.update()`, preserving Python references held by pane entries), maintaining per-flow lookup dicts (`_has_content_by_flow_id`, `_msg_idx_by_flow_id`, `_sys_idx_by_flow_id`, `_tool_name_by_flow_id`, `_lag_msg_idx_by_flow_id`) that back the REQ-header badge and the flow-scoped span lookup in `render_messages._lookup_spans`.
**Reads:** `_stripped`/`_injected`/`_original` dual-log JSONL files (incremental by byte position).
**Writes:** Nothing — returns the new file position; mutates the `acc_by_family` argument in place; `/tmp/monitor_cc_error.log` on a log-read `OSError` (via `pane_error_log`, retry-next-poll position unchanged).
**Called by:** `src/proxy_display/pane.py` (`accumulate_original_tools`), `src/proxy_display/proxy_pane_shared.py` (`accumulate_dual_log`), `src/proxy_display/frozen_turns.py` (`overlay_epoch`), `src/dual_log_cli/overlay.py` (`accumulate_dual_log`, its own independent accumulator per call — never shares state with the panes')
**Calls out:** `pane_error_log` (`log_pane_error`), `forwarded_parser` (`_monitor_root`)
### render_messages.py (230 LOC)

**Purpose:** Renders new/modified/removed messages for an expanded request entry. `render_messages()` dispatches to `_render_new_messages` (when the message count grew) or `_render_modified_messages` (retry/abort re-send) — the request's payload delta is the only source of rendered message content; every entry must carry the dual-log overlay references (`_stripped_spans`/`_injected_spans`), the pre-overlay render paths were removed. Span content rendering (inline new-format vs. legacy stacked) goes through the shared `_render_span_content`. `_lookup_spans` scopes the shared, cumulative `_stripped_spans`/`_injected_spans` accumulator dicts to the entry's own `flow_id` via the `_strip_msgs_lookup`/`_inject_msgs_lookup`/`_lag_msgs_lookup` reference sets, preventing a later request's overwrite of a message index from rendering under an earlier/neighbor request. Thinking blocks (`btype == 'thinking'`) get their own collapsed-by-default drill-down (`('think', entry_idx, msg_idx, bidx)` key) with word-wrapped content via `utils.wrap_visible`.
**Reads:** Entry dict, previous entry, all entries, expand states, pane width.
**Writes:** Nothing — returns `(lines, keys)` tuple; when `copy_feedback` is given, the two plain message-summary row sites (`_render_new_messages`/`_render_modified_messages`, not the `[STRIPPED]` variant) assign each row a `('msg', entry_idx, msg_idx)` key and append a `utils.append_copy_symbol` copy affordance — `None` when `copy_feedback` is omitted, unchanged. `_render_block_spans` does the same for a thinking block's own always-visible summary line (`('think', entry_idx, msg_idx, bidx)` key, not gated on that block's own expand/collapse state) and, identically, for every other block row reaching its non-thinking branch — text, tool_use, tool_result, anything else — via a `('block', entry_idx, msg_idx, bidx)` key (`_block_row_key`) — the same `_append_msg_copy_symbol` helper, reused rather than duplicated, across all three row kinds.
**Called by:** `src/proxy_display/render_turn.py`
**Calls out:** `proxy.strip_vocab` (`attribute_chunk`, `classify_tags`, `code_for_rule`, `classify_req`), `utils` (`wrap_visible`, `append_copy_symbol`)
```

## proxy_display: State and Gotchas (old sections, verbatim)

## State

`pane.py` and `worker_proxy_pane.py` each own independent module-level mutable state — entries
list, expand states dict, scroll offset, hover row, line map, turns list, current log path,
last-rendered pane width, copy-row set, copy-feedback timers, and an undo stack (`pane.py` only,
capped at 200).

**Search state** — each pane owns one `search_bar.SearchState` instance (`_proxy_search` /
`_worker_proxy_search`): query text, focus, ordered match list, match set, current-match index,
and drag-select fields. Rebuilt on every Enter via `proxy_pane_shared._run_pane_search` (never
gated on query-unchanged — the one-sweep reconstruction is cheap enough to always re-run).
Cleared via `search_bar.handle_search_cancel(state)` on session/worker change, NOT on the hourly
reparse (entry_idx-keyed expand/search state assumes stable re-indexing across a same-file
reparse). Drag-select and click-elsewhere clearing go through `search_bar.clear_selection(state)`,
called directly from each pane's own mouse handler.

**Dual-log accumulator** (both panes) — `_proxy_acc_stripped`/`_proxy_acc_injected` and their
worker-pane equivalents are `{family: {...}}` dicts mutated in place by
`dual_log_accumulator.accumulate_dual_log`; every parsed entry holds a REFERENCE (not a copy) to
its family's accumulator dict plus the per-flow lookup sub-dicts, so late-arriving delta updates
propagate to already-rendered entries automatically. Reset (`.clear()`, byte positions to 0) on
session/worker change and on the hourly reparse trigger.

**Whole-stripped tool original-def accumulator** (`pane.py` only) — `_proxy_acc_original`
(`{family -> {tool_name -> tool_def}}`), fed from the `_original` log via
`dual_log_accumulator.accumulate_original_tools`, latest-snapshot overwrite (not merge — tool
defs are stable within a session). `worker_proxy_pane.py` has no equivalent; a whole-stripped
tool row there always shows the `(original definition unavailable)` fallback.

**Frozen-turn cache** — each pane owns one `turn_cache.TurnCache` (`_proxy_turn_cache` / `_worker_proxy_turn_cache`), passed to `format_proxy_block`, cleared in the pane's `_reset_*positions`. Details in `process-docs/pane_flicker/`.

**Lazy-reload invariant:** an entry outside the `PROXY_MESSAGES_KEEP_LAST` tail window and not in
`expand_states` has `messages=None` (stripped by `_parse_forwarded_log`). On expand-click or
search-match, `_lazy_load_messages_forwarded`/`reconstruct_all_messages` replay the forwarded
stream from byte 0, matched by `flow_id`, to repopulate it.

## Gotchas

- `entry['http_status']` is set only once a `_response` line has been read (both panes, every poll): an int for a finished request, `None` for one still without a response line (`[pending]`). Without any response info the key is absent and no marker or status line appears.

- REQ numbers in the proxy panes are the token pane's numbers, joined per request: forwarded `flow_id` -> `_response` `request_id` -> transcript call (`token_format.request_numbers_by_id`). `forwarded.request_id` is empty in every entry, so the `_response` join is the only path. See `process-docs/proxy_display/`.
- A continue request (sonnet, `counts.tools == 0`, `diagnostics.previous_message_id` set) is flagged `is_continue`, never enters `acc_by_family`, carries only its own 1-2 msgs, is never standalone, and has no `prev_same` (nor is it anyone's). Folding it into the accumulator truncates the family list to 2 msgs and the next create raises `KeyError: 'role'` in `_compute_diff`.

- `PROXY_MESSAGES_KEEP_LAST = 10` — only the last N parsed entries retain `messages`; older
  entries are lazy-loaded on demand. `PROXY_REPARSE_INTERVAL_SECONDS = 3600` — hourly full
  reparse resets byte positions and accumulators but NOT expand/search state.
- `flow_id`, not `_fwd_req_idx`, is the stable cross-call correlation key. `_fwd_req_idx` resets
  to 0 on every `_parse_forwarded_log` call — it is unique only within one incremental batch, not
  across the polling session. Using it as a dict key across separate parse calls silently loads
  the wrong entry's content.
- `ZEBRA_BG_A = ''` is a valid "no override" background value, not "nothing". `resolve_bg_restore`
  must substitute an explicit `\033[49m` for it when closing a search-highlight span, or the
  highlight background floods the rest of the row to the trailing `\033[K`.
- `_BG_RESTORE_SENTINEL = '\033[999m'` (out-of-range but syntactically valid SGR code) stands in
  for "resume the row's real background" at embed time in `render_turn.py`, since that module
  doesn't know `chosen_bg` (zebra/hover/strip/collision) until `format._apply_row_backgrounds`
  computes it; `utils._ANSI_ESCAPE_RE` strips the sentinel as zero-width wherever visible-length
  math (padding, truncation) already runs.
- A trailing-message total_tokens strip is attributed one request LATE by the delta writer (CC
  hangs the cache-control breakpoint on the last message, so a fresh trailing system message
  arrives list-shaped and produces no diff op on the request that actually stripped it).
  `dual_log_accumulator._apply_lag_correction` re-attributes it to the correct flow via
  `_lag_msg_idx_by_flow_id`, guarded by `proxy_badge._is_total_tokens_nuke` matching the previous
  line's trailing index. This guard is load-bearing: without it, a mid-conversation nag/deferred
  nuke that lands on an index that was an earlier request's trailing message would bleed into the
  wrong request's rendered spans.
- A strip landing outside the request's own payload delta (task-tools nag, deferred-tools notice,
  date-changed) is INVISIBLE in the expanded body — only the REQ-header `strip`/`inject` badge
  words show it happened. The original text is only recoverable via the dual-log CLI
  (`duallog expand`), not in the pane. Do not "fix" this by loosening `_lookup_spans`' flow
  scoping — that reintroduces cross-request span bleed.
- `_is_total_tokens_nuke_text`'s catalogued-nudge-paragraph matching (`_TOTAL_TOKENS_NUDGE_PARAGRAPHS`)
  is deliberately NOT future-proof against a new, uncatalogued CC nudge sentence: an unrecognized
  sentence fails the test and the request stays badged (fails toward showing it) rather than being
  silently absorbed as quiet.
- `parser.get_proxy_session_start_ts` always returns an existing marker file's mtime, however old —
  a warnings-pane session-start filter keyed off this can reach back arbitrarily far if the marker
  itself is stale (no marker at all returns `None`; the warnings pane then shows a header notice and scans no worker errors).

## dual_log_cli: State and Gotchas (old sections, verbatim)

## State

No mutable state — every command is a single pass with no caches, no module-level state, and no
files written anywhere. Two external inputs decide the output: the dual_log directory's contents
and CC's own `~/.claude/projects/` transcript store (read by `project_map`/`usage` for project and
CR/CC resolution) — a run is reproducible only while both are unchanged, and the output tracks
whatever the proxy has appended to a live session by the time it runs.

## Gotchas

**A "sidecar" line is any non-haiku `_forwarded` entry with `counts.tools == 0`
(`timeline_boundaries._is_sidecar`).** `request_boundaries`, `discovery.build_session` and
`reader.load_last_request` each apply an equivalent exclusion independently rather than sharing one
predicate across all three — keep them in sync if the shape of a sidecar ever changes.

**`reader.load_last_request`'s haiku sniff is a cheap 512-byte window
(`_MODEL_SNIFF_BYTES`), but the zero-tool sidecar check needs the full parsed line** — `tools` can
sit arbitrarily far past that window behind a large system block, so there is no equivalently cheap
sniff for it.

**System index 0 (`_BILLING_HEADER_SYS_INDEX = 0`) is excluded unconditionally from the sys delta
comparison on every request but the first, and from the original-chars lookup on every request
including the first** — it is a hash plus the previous request id, so it differs by construction on
every single request and would otherwise swamp the real changed/new signal.

**Tool comparison in `timeline_boundaries._tool_lines` is NAME-based, not index-based** — removing
one tool renumbers every tool after it, which an index-based diff cannot distinguish from a real
edit. The name-based set-difference this uses has one blind spot: it cannot tell "tool X removed"
apart from "tool X removed AND a different, already-present-elsewhere tool added in the same
request" — both look like the same net membership change.

**`timeline_grouping._group_markers_by_turn` assigns a request to a turn via
`bisect_right(openers, marker["message_count"] - 1)`, never via the marker's own msg-index key
(`start_index`).** A request whose send bundles the previous turn's idle reply together with the
next turn's new prompt has a `start_index` that lands in the wrong turn if grouped by key instead
of by `message_count`.

**`render_reqs._rebuild_drop_qualifies`'s `--drop` boundary is strict (`<`), the opposite
convention from `--gap`'s inclusive (`>=`).** An exact `CR(n) == CR(n-1) + CC(n-1)` means the whole
prefix WAS read back, so it must NOT qualify for `--drop`.

**`--gap` only pairs consecutive REQs of the same `(stem, turn)`; a REQ with no turn never pairs.**
Chronological neighbors across turns or sessions are ignored, also under `--merged`.

**`--drop`'s "previous request" is always the same session's own previous REQ, even under
`--merged`.** `prev_usage` is precomputed per session (msg-index order in the create-only fallback,
chronological over creates and continues in the transcript path) before `_merged_entries`
ever flattens/sorts across sessions, so a cross-session chronological neighbor never substitutes
for it.

**`usage._candidate_dirs` appends `.claude/worktrees/<name>` to a worker's sid8-resolved project
cwd; `discovery.project_for_stem` returns that same cwd UNCHANGED.** The two need different paths
for different reasons — `usage.py` needs the worker's own worktree cwd to find its transcript,
`sessions`' PROJECT column needs the project itself, not the worktree. Conflating them breaks one
or the other silently.

**`discovery.resolve_dual_log_dir` reaches the main checkout from inside a worktree via a fixed
parent-count (`here.parents[5]`).** Moving this module to a different depth in the package tree
breaks that offset.

**`render_msgs`'s columns are fixed-width** — chars is 6 wide (`_MSG_CHARS_WIDTH`), `_BLOCK_INDENT`
is exactly 8 spaces so a block sub-line never matches `^\[` (the `grep '^\['`-selects-msg-lines
contract). An index of 1000+ or a 7-digit chars value pushes its own line one column wider;
right-alignment keeps it readable but not aligned to its neighbors.

**`search.find_matches` returns `[]` for an empty term rather than matching everything** — `str.count("")` counts positions, so a blank needle would otherwise report every block as a hit.

**`reader.local_datetime` returns `None` for an empty timestamp and raises `ValueError` for a non-empty unparseable one.**
Callers handle the empty case: `"?"` in a renderer, drop from an active date filter in
`discovery.filter_sessions`; a REQ marker without a timestamp raises in `render_reqs`.

**`__main__.py`'s `BrokenPipeError` guard has two parts, both required.** It flushes stdout inside
the `try`, and on failure `dup2`s stdout to `os.devnull` so the interpreter's own shutdown flush has
nothing left that can fail — dropping either half can resurface `BrokenPipeError` on stderr during
shutdown.

**`timeline_markers.request_msg_range` raises `AmbiguousRequestNumberError` when a REQ number maps
to more than one msg index, rather than guessing.** This can happen even without a restart: a
trailing re-fire that adds no msg can become the sole owner of its own group (a new `start_index`
nothing after it ever fills), but the running request-number counter never advanced for it, so it
inherits the same number as the group before it.

**`reqs`/`msgs` numbering has two paths, named on stderr each run.** With a resolvable transcript,
REQ numbers, turn numbers and times are the token pane's (`numbering.py`); without one, only create
requests are listed with duallog's own running numbers and send times, and continues have no turn.
See `process-docs/dual_log_cli/`.

**`timeline_markers.request_markers` picks the LAST MAPPED boundary of a refire group as owner** once
boundaries are annotated (a group whose last boundary is a 404 keeps the mapped one's number); an
all-unmapped group has number `None`, printed `REQ ?` and not addressable by `msgs --req`.

**In the transcript path every located request is its own msg group, and `msgs --req N` / `expand --req N`
read it that way.** A REQ owns the assistant reply it answers plus the msgs it sent; `msgs --req N` prints
N's group and the next request's group, `expand --req N` prints only the next request's group (N's reply
plus what came back). Msgs of unlocated requests sit under the preceding located REQ's group. See
`process-docs/dual_log_cli/`.

**`reqs` lists every create and continue as its own entry (no refire folding) and prints no header for a
session with no surviving REQ line;** when nothing prints at all, the single line `no REQs to show`.

**A REQ without a transcript match (`REQ ?`) sits in the turn its send time falls in and never forms a `--gap` pair.**
Its turn comes from the same rule as the proxy pane; a pair member must be a numbered REQ so the chain can
continue with `expand --req N`. See `process-docs/dual_log_cli/`.

**`numbering._annotate_status` reads `_response` with no fallback:** a broken `_response` log fails the command
loudly instead of printing rows without status.

## dual_log_cli: module details (old numbering, project_map, timeline_markers entries)

```
### project_map.py (70 LOC)

**Purpose:** Resolves the proxy's `md5(project_path)[:8]` session id — the only trace of a
worker's project in its stem — to that project's real cwd, by scanning CC's own transcript store.
`build_project_index` does that walk once and returns it in two shapes: `cwd_to_dir` (a main
stem's label match) and `sid_to_cwd` (a worker stem's sid8 lookup, keeping the real project path),
hashed via `src/proxy_display/forwarded_parser.py`'s `_proxy_session_id_for_project` — the single
source shared with `addon.py`'s own session-id derivation.
**Reads:** `~/.claude/projects/<encoded>/<uuid>.jsonl` (first ~40 lines of up to 3 newest transcripts per project dir).
**Writes:** Nothing — returns `{"cwd_to_dir": ..., "sid_to_cwd": ...}`; an unreadable directory or transcript (`OSError`/`ValueError`) is reported once on stderr and skipped.
**Called by:** `discovery.py`, `commands.py`, `usage.py`.
**Calls out:** —
### timeline_markers.py (136 LOC)

**Purpose:** Request markers and numbering. `request_markers` folds boundaries into
`{msg_index: {number, timestamp, clock_timestamp, pane_turn, http_status, refires, flow_id, sys_lines, tool_lines, message_count}}`, what
`msgs` draws its REQ separators from (grouped by `msg_start` once annotated, else `start_index`). `resolve_req_range_with_next` (`msgs --req`: the REQs' groups plus the next request's group) and `resolve_req_output_range` (`expand --req`: the next request's group, i.e. the reply plus the returned result). `request_numbers_by_flow` is what `overlay` uses to name the
request behind a strip. `resolve_req_range`/`request_msg_range` translate a REQ number range into
the equivalent msg-index range for `msgs --req`.
**Reads:** Boundary dicts (from `timeline_boundaries.request_boundaries`) — parameters only, no module state.
**Writes:** Nothing — returns dicts, lists, or a `(start, end)` tuple; raises on an ambiguous/unknown REQ number.
**Called by:** `timeline_grouping.py` (`request_markers`), `overlay.py` (`request_numbers_by_flow`), `render_msgs.py` (`request_markers`), `commands.py` (`resolve_req_range`, `resolve_req_range_with_next`, `resolve_req_output_range`, the two errors); `dev/dual_log_cli/tests/test_msgs_req_range.py`.
**Calls out:** —
### numbering.py (101 LOC)

**Purpose:** `build_session_numbering` resolves a session's transcript once and annotates every create and continue request with the token pane's own REQ number, turn and response-end time (`pane_number`/`pane_turn`/`pane_time`, `None` when unmapped); returns usage, the transcript turns and which path was used.
**Reads:** the payload messages passed in by `commands`, `src/panes/cache_turns.build_cache_turns` over the resolved transcript, `src/format/token_format.call_numbers`, `usage.resolve_transcript`/`usage_from_transcript`.
**Writes:** mutates the passed boundary/continue dicts in place (`pane_*`, `http_status` from the `_response` stream for every main-thread request in either path, plus `msg_start` for every located request); returns `{usage, pane_turns, path, requests}` (`path` is `transcript` or `boundaries`, `requests` the annotated creates plus continues; the `boundaries` path also carries `reason`, why the transcript did not resolve).
**Also:** `_locate_msgs` finds each request's msg group start in the last full payload — a create at the last assistant msg before its last sent msg, a continue at the last assistant msg before its tool_result (matched by `tool_use_id`); openers, unmapped and newer-than-payload continues stay unlocated.
**Called by:** `commands.py` (`_run_reqs`, `_numbered_view`); `dev/dual_log_cli/tests/test_reqs_pane_numbering.py`.
**Calls out:** `panes.cache_turns`, `format.token_format` (absolute imports).

---
```

## panes: State and Gotchas (old sections, verbatim)

## State

Each pane module owns its own module-level scroll/expand/hover state. State is NOT shared between
panes. All panes read `monitor.active_project_filter` via `from ..core import monitor as _monitor`.

| Module | Key state vars |
|---|---|
| `token_pane` | `cache_expand_states`, `cache_line_map`, `cache_scroll_offset`, `cache_copy_rows`, `_cache_copy_feedback_until`, `_cache_turns`, `_cache_jsonl_position`, `_response_log_pos`, `_response_rid_map`, `_tokens_search` (`search_bar.SearchState`), `_tokens_nav` (key → line-idx cache for jump-to-match, refreshed every render) |
| `warnings_pane` | `tool_errors`, `error_expand_states`, `error_line_map`, `error_hover_row`, `error_scroll_offset`, `error_copy_rows`, `_error_copy_feedback_until`, `_warnings_header_regions`, `_errors_log_pos`, `_errors_log_path`, `_worker_errors_positions`, `_last_project_filter`, `_monitor_start_ts`, `_warnings_search` (`search_bar.SearchState`) |
| `warnings_render` / `token_search` / `cache_turns` | none — stateless, receive state as arguments and return new values |

## Gotchas

- `from ..core import monitor as _monitor` is lazy, inside `_refresh_tokens_data`/`_refresh_warnings_data`, to avoid circular imports; `input.click_handler` imports stay module-level (no circular-import risk there).
- The zebra/hover/truncation render loop lives in `_render_tokens_rows()` (`token_pane.py`) / `_render_warnings_rows()` (`warnings_render.py`), not in `format/token_format.py` — `format_cache_tracker` only returns logical lines and a uniform 5-tuple.
- `token_pane._render_tokens_rows`, `warnings_render._render_warnings_rows`, and `workers/worker_render._render_workers_rows` are three separate, near-identical zebra/hover/copy-row render loops — not folded into one shared helper. They differ in the search-match-substring-bg constant checked (`LIGHT_RED_BG` in the first two, `DIM_YELLOW_BG` in warnings) and in key handling (tuple keys vs. bare int/str keys).
- `line_map` is built 1:1 in each render loop (one physical row per logical line) — long lines are truncated at render time, not wrapped.
- **Header + Body pane contract:** a pane that renders a fixed header above a scrolling body must overdraw the header after printing the body (`print(f"\033[H{header}\033[K", end='', flush=True)`), or long body lines that wrap visually push the header off the top. Applies to `warnings_pane`. Does NOT apply to `token_pane` — it truncates every line (`truncate_visible`) instead of wrapping, so the precondition never occurs.
- `token_pane.py`'s `_handle_tokens_mouse` checks `row == 1` (search bar) before the `cache_line_map` body lookup — no collision is possible since `cache_line_map` never gets a row-1 entry.
- Wheel direction is inverted between the two panes: `warnings_pane` renders top-to-bottom, so wheel-up (button 64) decreases `error_scroll_offset` and wheel-down (65) increases it; `token_pane` renders bottom-to-top and adds on wheel-up (64).
- `colors.ZEBRA_BG_A == ''` is the `chosen_bg` for every non-hovered, non-error row in both render loops — `search_bar.resolve_bg_restore(line, chosen_bg)` must run unconditionally there, or an embedded search-highlight sentinel leaks into the terminal.

## gpu_pane: module details, State and Gotchas (old, verbatim)

## Flow

1. `run_gpu_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop; each tick calls `all_statuses()` (glob `~/.rag-locks/server-port-*.json`) and `get_anomalies()`/`errors_today()`.
2. Every 30s (or on force-refresh): `_fetch_collections()` calls `rag-cli list_collections --json`.
3. `gpu_render._render_pane()` renders three blocks (GPU Servers, RAG Collections, Errors today) and rebuilds `_button_regions`.
4. Digit key `1`-`9` or a button click → `gpu_actions._fire_button` / `pane._toggle_server` → `rag-cli server start|stop|restart <name>` fire-and-forget, tracked in `_toggle_state` until the real status confirms the transition or `TOGGLE_TIMEOUT` (120s) expires.
### pane.py (226 LOC)

**Purpose:** Event loop — keyboard/mouse dispatch, row-1 search bar (highlight-only, no scroll infra since this pane has none), digit-key preset toggle. `GPU_POLL_INTERVAL = 2.0` s; `COLLECTIONS_POLL_INTERVAL = 30.0` s. `_toggle_server` stays in this module (not `gpu_actions.py`) because it reads the module-level `PRESET_NAMES` bare name that `dev/click_ui/p4_gpu_news_button_probe.py` monkeypatches directly.
**Reads:** `all_statuses()`, `get_anomalies()`, `errors_today()`, `errors_today_by_server()` every 2s tick; `_fetch_collections()` every 30s tick (+ force-refresh); `PRESET_NAMES` from `status` (filled in place by the first successful discovery).
**Writes:** stdout (full-screen ANSI); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `_gpu_search` (search state); mutates `gpu_actions._toggle_state` and `gpu_render._button_regions` (imported, same objects).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `rag-cli` (subprocess CLI, `_toggle_server`).

---

### gpu_actions.py (44 LOC)

**Purpose:** Server control actions. `TOGGLE_TIMEOUT = 120` s — how long a `[starting…]`/`[stopping…]` label persists before expiry; an expiry without the target state writes a `log_pane_note`. `_toggle_state: dict[str → ('starting'|'stopping', float ts)]` is module-level, mutated by `_expire_toggle_states`, `_fire_button`, and `pane.py`'s own `_toggle_server` (imported back into `pane.py`, same dict object). `_expire_toggle_states` removes entries once the server's real status confirms the transition, or after `TOGGLE_TIMEOUT`. `_fire_button` fires the `rag-cli server <action> [--port <port>] <name>` subprocess and stamps `_toggle_state`.
**Reads:** `presets`/`arbitrary` lists passed as arguments.
**Writes:** `_toggle_state` (add/remove entries); one `subprocess.Popen` per `_fire_button` call.
**Called by:** `pane.py` (`_expire_toggle_states`, `_fire_button`, `_toggle_server`'s reads), `gpu_render.py` (`_status_text` reads `_toggle_state`).
**Calls out:** `rag-cli` (subprocess CLI); `pane_error_log`.

---

### gpu_render.py (180 LOC)

**Purpose:** Rendering — three-block render (GPU Servers + RAG Collections + Errors), idle-countdown computation, context-dependent button labels/regions. `IDLE_TIMEOUT` (env `RAG_SERVER_IDLE_TIMEOUT`, default 3600) is used only by `_format_countdown`. `_render_pane` is a thin orchestrator over `_render_gpu_header`, `_render_preset_rows`, `_render_arbitrary_rows`, `_render_collections_block`, `_render_errors_block`, `_render_anomalies_line`, `_apply_gpu_search_highlight`.
**Reads:** `gpu_actions._toggle_state` (for `_status_text`); all other state passed as function arguments.
**Writes:** `_button_regions` (cleared and rebuilt every `_render_pane` call); returns the rendered string.
**Called by:** `pane.py` (`_render_pane` directly; the search-commit baseline render); `dev/click_ui/p4_gpu_news_button_probe.py` (`_render_pane` directly, standalone).
**Calls out:** none.

---

### status.py (228 LOC)

**Purpose:** State-file registry reader + collection fetcher. Globs `~/.rag-locks/server-port-*.json`, builds preset + arbitrary status lists, detects the anomaly classes, logs to `src/gpu_pane/logs/gpu_pane.log` via `TimedRotatingFileHandler` (daily, 7-day retention). `PRESET_NAMES` starts empty and is filled in place by `_ensure_preset_names` via `rag-cli server presets --json` (3s timeout) on every `all_statuses` tick until discovery succeeds; a failure shows as a `presets_unavailable` anomaly. `_fetch_collections()` calls `rag-cli list_collections --json` (5s timeout; `None` on any failure, noted once per state change).
**Reads:** `~/.rag-locks/server-port-*.json` (content + mtime); `http://localhost:<port>/health`; `ps -o rss=`; `rag-cli server presets --json` (until it succeeds); `rag-cli list_collections --json` (every 30s).
**Writes:** nothing (read-only); anomalies appended to module-level `_last_anomalies`; logs to `gpu_pane.log`.
**Called by:** `pane.py`.
**Calls out:** `rag-cli` (subprocess CLI); `ps` (subprocess CLI); `pane_error_log`.

---
## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `gpu_actions.py` | `_toggle_state: dict[str → ('starting'\|'stopping', float ts)]` — imported back into `pane.py`/`gpu_render.py`, same dict object | `_status_text` (`gpu_render.py`), digit/click handlers (`pane.py`) | `_toggle_server` (`pane.py`), `_fire_button` (`gpu_actions.py`) |
| `gpu_render.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target_str)]` — imported back into `pane.py`, same dict object | mouse-click handler in `pane.py` | `_render_pane` (cleared and rebuilt per tick) |
| `pane.py` | `_gpu_search: search_bar.SearchState` | `.matches` holds 0-based indices into `_render_pane`'s own lines list | mutated by `_poll_gpu_input`/`_handle_gpu_mouse` |
| `status.py` | `_last_anomalies: list[dict]` | `get_anomalies()` | reset each tick by `all_statuses()` |
| `status.py` | `PRESET_NAMES: list[str]` | `pane.py` (digit-key handler, `_toggle_server`); `all_statuses` (preset row order) | `_ensure_preset_names()` mutates it in place (same list object) while it is empty |

**`_toggle_state` key convention:** preset name (e.g. `'embedding'`) for presets; `'port-{N}'` for arbitrary servers.

## Gotchas

- Stopped servers skip the httpx health check entirely — no connection-refused errors on every tick.
- `rag-cli server start` takes 30-90s for embedding model load; the badge flips naturally once `/health` returns 200.
- **Idle countdown requires `log_path` in the state file.** If a server was started outside the RAG box architecture (no state file), it never appears. If `log_path` points to a deleted file, the countdown shows `?` and an anomaly is logged.
- `enable_mouse()` captures all mouse events (including wheel) — tmux native scrollback (Ctrl+B `[`) does not work while the pane is active.
- `_render_pane` clears `_button_regions` at the top of every call — anyone reading the regions outside the same render tick sees stale data.
- **Hard cut:** this pane does not read legacy `~/.rag-locks/rag-server-{name}.port` files — they are detected and logged as anomalies (via glob) but their content is never read.
- **`PRESET_NAMES` is filled once and then kept.** A successful discovery is never repeated; to pick up a RAG-side preset change the pane must be respawned (Ctrl+R triggers a tmux `respawn-pane`, which re-imports the module).
- **`rag-cli` failure → empty preset block plus a `presets_unavailable` anomaly, no fabricated names.** Discovery is retried on every 2s tick; the cause is logged to `gpu_pane.log` only when it changes.
- **Collections block shows `?` when `_fetch_collections()` fails** (Postgres down, rag-cli absent, timeout); `(none indexed)` means the fetch succeeded with an empty list.
- **A state file without an integer port is skipped with a `missing_port` anomaly.**
- **`IDLE_TIMEOUT` is coupled to the RAG server's own idle timeout** by the env var `RAG_SERVER_IDLE_TIMEOUT` (default 3600); the state files carry no idle-timeout value, so a differing server setting makes the countdown wrong without any sign.
- **`list_collections` is lock-exempt in rag-cli** (pure Postgres aggregate read) — it succeeds even while `rag-cli index`/`update_docs` holds the advisory flock.
- `status.py`'s `except PermissionError: pass` (PID alive, different owner) must stay single-line — a two-line `except ...:\n    pass` with no comment is rejected by this codebase's write-time safety hook.

## news_pane: State and Gotchas (old sections, verbatim)

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target)]` | mouse-click handler | `_render_pane` (cleared + rebuilt per tick) |
| `pane.py` | `_pipeline_proc: Popen \| None` | `_is_running()` | `_fire_pipeline()` |
| `pane.py` | `_news_search: search_bar.SearchState` | `.matches` holds 0-based indices into `_render_pane`'s own lines list | mutated by `_poll_news_input`/`_handle_news_mouse` |

## Gotchas

- `log_pane.py` has no search bar — the right log-tail pane's top-anchored, scroll-free rendering is explicitly out of scope for the search-bar rollout.
- `log_parser.py` is the constant anchor for the whole package (`WEBSEARCH_ROOT`, `LOG_DIR`, `LAST_RUN_FILE`, `TARGET_COLLECTION`) — none of these live in `src/constants.py`.
- `_LOG_LINE_RE`'s `\s+` group before `(.*)` consumes all leading whitespace from the message — whitelist patterns must not include leading spaces (e.g. `\[(OK|FAIL)\]`, not `  \[(OK|FAIL)\]`).
- `_button_regions` for `[run pipeline]` is only registered when `running=False`. While running, a click on that position hits no registered region and is silently ignored.
- Running state is the `_pipeline_proc` handle only. A pipeline started outside this pane (cron, CLI) does not disable the button; the log-based detection was removed because no observation of a lost handle was recorded.
- NEWS-LOG pane uses plain `time.sleep(0.5)` (no raw-stdin setup), so Ctrl+C delivers SIGINT cleanly to `startup.py`'s signal handler.
- `find_current_run_lines()` falls back to all lines when no start marker is found (empty collection / first-ever run).
- The pipeline `Popen` sends stdout+stderr to `DEVNULL` — the pipeline writes its own log file in `LOG_DIR` independently, which is the only channel this pane observes.

## Outcome (2026-09-25)

New DOCS.md line counts: proxy 371, proxy_display 195, dual_log_cli 251, panes 80, gpu_pane 71, news_pane 50 (none at or above 400). docs-drift-check run from the worktree root reports 0 findings for these six files.

Tool behavior noted: the checker flags backticked dotted module.attr forms and paths that do not exist in a fresh checkout (gitignored runtime log directory, gitignored schema store), so those are described in words. Use `dir/file.py` path form for cross-package module references instead of dotted form.
