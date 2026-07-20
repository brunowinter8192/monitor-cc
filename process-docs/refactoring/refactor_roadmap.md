# Refactor Roadmap — Sequencing (2026-05-28)

> HISTORICAL — a point-in-time sequencing decision from 2026-05-28, not a living status board.
> Active cross-session tracking runs through GitHub Issues (bd/dolt beads retired).
> Stage status here is only updated where subsequently factually corrected (Stage 1).

## Decision

Four refactor/fix topics run SEQUENTIALLY, not in parallel. Order:

1. **Menubar** — controller-composition refactor — COMPLETED (2026-06, B1-B5, all 6 controllers)
2. **blank** — desktop-targeting sidecar consolidation (Path 2)
3. **Logging + Proxy** — unified janitor + the logging current-state doc + count_tokens fix + orphan cleanup
4. **Dolt** — bd↔dolt lifecycle hook fix

## Why Sequential, Not Parallel

- **Hard dependency Menubar → blank:** blank's Path 2 (documented in the desktop_allocation area's sidecar-consolidation entry) needs the menubar to publish a `cwd → space_id` sidecar (a Monitor_CC source change). Cleanest to hook this in *after* the controller refactor, into the then-clear structure. blank cannot finish before the sidecar exists.
- **Review load:** two parallel refactor streams both merging to `dev` = doubled Opus cross-model review + tangled merge topology + higher regression risk. Sequential keeps each refactor verifiable on a clean dev state before the next starts.
- **Menubar already in flight** (steps 1-2 merged, 3 running, 4-6 pending) — finish it first for a clean baseline.

## Stages

### 1. Menubar — Controller-Composition Refactor — COMPLETED
- Process history: the menubar_refactor_v1 area
- Status: all 6 steps merged (B1 Sessions, B2 Bead, B3 Queue, B4 PanelManager, B4b Focus, B5 Hotkey — see the B5 migration log in that area). The LOC-ceiling violations deferred there (app.py, queue_controller.py) were resolved 2026-06-10 in the LOC-refactor campaign via a standalone split (documented in this area's LOC-refactor-campaign entry).

### 2. blank — Desktop-Targeting Sidecar Consolidation
- Process history: the desktop_allocation area's sidecar-consolidation entry
- Depends on: Stage 1 (menubar publishes the cwd→space_id sidecar).
- Scope: menubar publishes the verified detection result as a sidecar; blank's `desktop_targeting.py` consumes it (the fragile name-match chain goes away); blank-side logging for worker-spawn + file-open; detect-before-disturb reorder.

### 3. Logging + Proxy — Unified Janitor + count_tokens Fix
- Process history: the logging area's log-janitor entry, the audit_logging area's architecture entry; the proxy-cache pipeline current-state doc (count-30 + log naming)
- Current-state doc (planned, new at the time): the logging area's authoritative log inventory (writer/reader/purpose/format/retention/janitor), RAG-indexed as the single source.
- Scope:
  - **Unified janitor:** consolidate scattered logic (`claude_proxy_start.sh` count-30, `log_janitor.py` 7-day records, `gpu_pane/status.py` TimedRotating, `ccwrap/ansi_log.py` keep-count) in `src/log_janitor.py` as a declarative LogSpec registry. Two triggers remain sensible (proxy-start for api_requests, monitor-24h tick for the rest).
  - **count_tokens proxy fix:** `_is_messages_request` (`src/proxy/addon.py:341-343`) matches `/v1/messages/count_tokens` too via `path.startswith("/v1/messages")`. Consequence: `_inject_model_override` (`src/proxy/inject_helpers.py:27-28`) injects `max_tokens` + `output_config.effort` from `proxy_rules.json` into count_tokens pre-checks too → 400 `max_tokens: Extra inputs are not permitted` (99 of 102 error payloads). Real `/v1/messages` generation requests are unaffected (max_tokens is legal there, 200). **Fix (simplified):** exclude count_tokens from the pipeline entirely (`_is_messages_request` matches the messages endpoint exactly, not by prefix) → CC's count_tokens passes through unmodified, no injection, no 400, no file flood. No field stripping needed because we never consume the count_tokens count anywhere (see below).
  - **Token-counting audit (finding 2026-05-28):** production `src/` has NO `tiktoken`, NO count_tokens response consumption. Authoritative CC/CR numbers come from session-JSONL `usage` (`jsonl/jsonl_extractors.py` → `token_pane`/`proxy_display`/`worker_pane`). The only own estimate: `_chars_to_tokens` (chars/3.5) in `proxy_display` for "~Ntok" display labels — char-based, model-independent, no accounting. Open: whether this display heuristic stays or goes. The count_tokens pre-flight is CC's own call, not consumed by us → can pass through untouched.
  - **api_error_payload:** switch the proxy writer (`src/proxy/addon.py:235`) from one file per error to a rolling `api_errors.jsonl` → eliminates the file flood by design + gets covered by the existing 7-day-record janitor.
  - **Orphan cleanup:** `tool_use_errors.jsonl` (legacy, no writer anymore) + orphaned `.proxy_live_*` directories of dead sessions.
- count-30 retention for api_requests: deliberately NO size limit — accepted (user decision 2026-05-28), 16GB is not a problem.

### 4. Dolt — bd↔dolt Lifecycle — RESOLVED (2026-05-30) — bd v0.60.0 → v1.0.4 Upgrade
- Process history: the dolt area's server-lifecycle entry (RESOLVED block at the top of the file).
- Two discarded theories: (1) TIME_WAIT buildup on a fixed port (2026-05-28); (2) the Homebrew-dolt two-server war (2026-05-29 — a red herring, the loop came back without Homebrew).
- Real root: an internal bd per-command server-lifecycle instability, driven by continuous menubar bd polling (the #2655 class upstream). v1.0.4 keeps the auto-started server alive → no more churn.
- Fix: bd pinned as a controlled single version at `~/.local/bin/bd` (v1.0.4, checksum-verified), `brew uninstall bd` + `brew pin dolt`, no auto-update. 7 project DBs migrated in-place (schema 0.60.0→1.0.4, zero data loss, sandbox-tested). Loop verified dead (port+PID stable, 0 breakers). Details in the RESOLVED block of that entry.

## Follow-Up (After Dolt)

- **Opus worker-rules cleanup:** remove the `<20%`-context kill threshold in `~/.claude/shared-rules/opus`. Sole policy: use workers until they die, then successor handoff (recap-after-stage secures a clean committed state). No preemptive kill on low context — the last few percent often go further than expected. Opus edits the rule files directly; cross-project, no project tracking task.
