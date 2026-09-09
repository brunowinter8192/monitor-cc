# src/gpu_pane/

## Role

Standalone tmux Window 4 pane that monitors RAG GPU servers and indexed collections cross-project. Reads `~/.rag-locks/server-port-{N}.json` state files written by the box architecture (Phase 1 RAG); renders three blocks: (1) GPU Servers — dynamic preset block (count = `len(PRESET_NAMES)`, discovered from `rag-cli server presets --json` at module import) + arbitrary block; (2) RAG Collections — polled every 30 s via `rag-cli list_collections --json`; (3) Errors today. Idle countdown derives from state file mtime (`log_path` from state file). Digit keys `1`-`9` (capped to actual preset count) toggle preset servers; mouse clicks on `[stop]`/`[start]`/`[restart]` buttons fire context-dependent actions for presets, or `[stop]` for arbitrary servers. No dependency on `core/monitor.py` or `active_project_filter`.

## Public Interface

`from src.gpu_pane.pane import run_gpu_loop` — entry point called by `workflow.py --mode gpu`.

## Flow

1. `run_gpu_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop.
2. Each 2s tick: `all_statuses()` globs `~/.rag-locks/server-port-*.json`, reads pid+port+log_path+model_name per file; anomalies collected in module-level `_last_anomalies`; `get_anomalies()` returns list for pane footer.
3. Each 30s tick (also on force-refresh): `_fetch_collections()` calls `rag-cli list_collections --json` (lock-exempt subprocess); returns `[{collection, chunks}]`.
4. `_render_pane()` renders three blocks: (a) GPU Servers — preset rows (`[i+1]` prefix) then optional arbitrary rows (`    ` indent, `[stop]` only); (b) RAG Collections — one row per collection `<name padded 32> N chunks`, `(none indexed)` when empty; (c) Errors today (last 10).
5. Per running server: `_format_countdown(s)` reads `s['idle_seconds']` (seconds since state-file mtime) and `s['idle_state_missing']`; renders `stops in MM:SS` / `H:MM:SS` / `stopping…` / `?` (state file missing) / `""` (stopped).
6. `_render_pane` rebuilds `_button_regions: dict[(start_col, end_col, phys_row) → (action, target_str)]` per render.
7. Digit key 1-9 (capped to `len(PRESET_NAMES)`) → `_toggle_server(idx, presets)` → `rag-cli server start|stop|restart <name>` fire-and-forget (preset only, guarded by `_toggle_state`).
8. Mouse click (button=0) → row+col matched against `_button_regions` → `_fire_button(action, target)`.
9. `_toggle_state` shows `[starting…]`/`[stopping…]` until next status change or 120s timeout.
10. Anomaly footer rendered when `len(anomalies) > 0`: `⚠ N anomaly/anomalies (see logs/gpu_pane.log)`.

## Modules

### pane.py (233 LOC)

**Purpose:** Event loop, keyboard + mouse dispatch, search wrappers. `COLLECTIONS_POLL_INTERVAL = 30.0` s controls the slower collection-count cadence; `GPU_POLL_INTERVAL = 2.0` s the status cadence. Digit-key handler accepts `'1'`-`'9'` capped to `len(PRESET_NAMES)`. **(2026-07-31) The `while True:` body is wrapped in its own `try/except Exception:`** — an uncaught exception (this pane previously had none, and could die silently) is caught, logged via `pane_error_log.log_pane_error('gpu')`, and the loop continues after `wait_for_input(INPUT_POLL_INTERVAL)`; `KeyboardInterrupt`/`SystemExit` still propagate, `finally: disable_mouse(); restore_terminal()` still runs. **(2026-07-30) Digit keys need no new button:** the per-preset row's ALREADY-registered `_button_regions` entry (`action` = `('stop' if healthy else 'restart') if running else 'start'`, `target` = preset name) computes the IDENTICAL action and fires the IDENTICAL `rag-cli server <action> <name>` subprocess call as `_toggle_server(idx, presets)` (what the digit key calls) — `presets = [_status_for_preset(n, ...) for n in PRESET_NAMES]` guarantees `presets[idx]['name'] == PRESET_NAMES[idx]` always, so digit `i+1`'s target and the `i`-th preset row's button target are always the same server. No gap, no new button; verified in `dev/click_ui/p4_gpu_news_button_probe.py`.
**(2026-08-18, rollout sub-milestone 7) Permanent row-1 search bar -- HIGHLIGHT-ONLY, per the approved decision: this pane has NO scroll/viewport infra at all** (`pane_height` is accepted by `_render_pane` but never read -- confirmed by grep before implementing), so there is no jump-to-match. `_gpu_search: search_bar.SearchState`; full drag-select/editor-style-deletion mechanics reused via `search_bar.py`'s generic functions. `n`/`N` (`_jump_gpu_search_match`) cycles `current_idx` ONLY (which on-screen match gets `SEARCH_CURRENT_BG` vs `SEARCH_MATCH_BG`, and the N/M counter) -- ZERO scroll call, since there's nothing to scroll to. `_gpu_search_on_commit` (the Enter callback) calls `_render_pane` ONCE without search kwargs (plain baseline, `pane_height=0` since it's never read) to get exactly what the real render would show, splits on `\n`, ANSI-strips each line, and collects 0-based indices containing the query -- no separate matcher function needed (no collapse/expand state to force-open, everything is always fully shown).

**(2026-09, gpu-pane-split milestone) `pane.py` (was 459 LOC, over the 400 ceiling) split into 3 modules by concern — `gpu_actions.py` (server control: `TOGGLE_TIMEOUT`, `_toggle_state`, `_expire_toggle_states`, `_fire_button`) and `gpu_render.py` (rendering: `_button_regions`, `_render_pane` and every helper it calls) moved out; `pane.py` itself kept the event loop, the inline-dispatch-turned-`_handle_gpu_mouse`, and the search wrappers.** `run_gpu_loop` (was 136 LOC, HARD) and `_render_pane` (was 110 LOC, HARD) both needed real multi-step extraction, not one cut, to get under 50 — see those two modules' own entries. **`_toggle_server` is the ONE function in the "server control" concern that stayed in `pane.py` rather than moving to `gpu_actions.py`:** it reads the module-level `PRESET_NAMES` bare-name (imported from `status.py`), and `dev/click_ui/p4_gpu_news_button_probe.py` monkeypatches `mod_gpu.PRESET_NAMES` directly before calling `_toggle_server(idx, presets)` (unchanged 2-arg signature) — a copy of `PRESET_NAMES` imported separately into `gpu_actions.py` would never see that monkeypatch, so the function had to stay where the patchable name lives. `run_gpu_loop`'s inline mouse-dispatch (the `if button == 0: ...` block, real-button-event case only — release/cancel handling stays inline in the poll loop, mirroring `token_pane._poll_tokens_input`'s own precedent) became `_handle_gpu_mouse(button, col, row) -> (input_changed, force_refresh_hit)`, `run_gpu_loop`'s own drain loop became `_poll_gpu_input(...)` (stays local — monkeypatch constraint, see Reads/Writes), the status+collections refresh became `_refresh_gpu_data(...)` (single combined helper, mirrors `token_pane._refresh_tokens_data`/`warnings_pane._refresh_warnings_data`'s pattern — each section only overwrites its own outputs when its own interval fires, unfired sections pass their current values straight through untouched), and the render+shift+diff+print tail became `_build_gpu_output(...)`.
**Reads:** `all_statuses()`, `get_anomalies()`, `errors_today()`, `errors_today_by_server()` on each 2s tick; `_fetch_collections()` on each 30s tick (+ force-refresh); `PRESET_NAMES` from `status` module (set at import).
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `_gpu_search` (query/focused/matches/match_set/current_idx/drag-select fields); mutates `_toggle_state`/`_button_regions` (imported, same objects — see `gpu_actions.py`/`gpu_render.py` entries).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `click_handler` (keyboard via `read_keypress`, mouse via `enable_mouse`/`disable_mouse`/`read_mouse_event`, `copy_to_clipboard`), `status`, `errors`, `gpu_actions` (`_toggle_state`, `_expire_toggle_states`, `_fire_button`), `gpu_render` (`_button_regions`, `_render_pane`, `_strip_ansi`), `pane_error_log` (`log_pane_error`), `search_bar` (shared search-bar mechanics), `subprocess.Popen` (rag-cli toggle, in `_toggle_server`).

---

### gpu_actions.py (44 LOC, new 2026-09, gpu-pane-split milestone)

**Purpose:** Server control actions, moved out of `pane.py`. `TOGGLE_TIMEOUT = 120` s — how long a `[starting…]`/`[stopping…]` label persists before natural expiry. `_toggle_state: dict[str → ('starting'|'stopping', float ts)]` — module-level, mutated (never rebound) by `_expire_toggle_states`, `_fire_button`, and `pane.py`'s own `_toggle_server` (imported back into `pane.py`, same dict object). `_expire_toggle_states(presets, arbitrary)` removes entries once the underlying server's real status confirms the transition finished, or after `TOGGLE_TIMEOUT`. `_fire_button(action, target)` fires the `rag-cli server <action> [--port <port>] <name>` subprocess (fire-and-forget) and stamps `_toggle_state[target]`. Leaf module — no dependency on `pane.py` or `gpu_render.py`, avoiding any import cycle.
**Reads:** `presets`/`arbitrary` lists passed as arguments (no module state read beyond its own `_toggle_state`).
**Writes:** `_toggle_state` (add/remove entries); one `subprocess.Popen` per `_fire_button` call.
**Called by:** `pane.py` (`_refresh_gpu_data` calls `_expire_toggle_states`; `_handle_gpu_mouse` calls `_fire_button`; `_toggle_server`, `_status_text` (`gpu_render.py`) both read `_toggle_state`).
**Calls out:** `subprocess` (rag-cli).

---

### gpu_render.py (178 LOC, new 2026-09, gpu-pane-split milestone)

**Purpose:** Pure(ish) rendering — three-block render (GPU Servers + RAG Collections + Errors), idle-countdown computation, context-dependent button rendering, moved out of `pane.py`. `IDLE_TIMEOUT` (env `RAG_SERVER_IDLE_TIMEOUT`, default 3600) — used only by `_format_countdown`. Preset row format width 16 (fits longest variant name e.g. `embedding-0.6b`), arbitrary row width 12. **(2026-07-30) New `[refresh]` header button:** appended to the `GPU Servers` title line (row 1, disjoint from every preset/arbitrary button which start at row >= 2), registered in `_button_regions` under a distinguishing `('refresh', 'refresh')` action/target pair — `pane.py`'s `_handle_gpu_mouse` special-cases `action == 'refresh'` (returns `force_refresh_hit=True`) BEFORE the pre-existing `target not in _toggle_state: _fire_button(...)` branch, so it never reaches `_fire_button` (which has no refresh verb). Width-guarded with a REAL gate (no button text and no region when it doesn't fit) — unlike the pre-existing per-server buttons, which use `pad = max(1, ...)` and always register regardless of fit (a pre-existing gap, left untouched, out of scope). **(2026-07-30 review fix) Decoration yields to the button, not the reverse:** `utils.compute_header_rule_len('  GPU Servers', '[refresh]', 64, pane_width)` shrinks the rule first (down to a 4-char minimum) to make room for the button; the button is only omitted when even the shrunk-to-minimum rule plus the button can't fit alongside the title. Crossover: button visible from pane_width >= 27; title text always renders regardless of width (this pane never calls `truncate_visible` on its lines). Verified with a width sweep in `dev/click_ui/p4_gpu_news_button_probe.py`. **No sentinel needed for search highlighting** — this pane has no per-row background/zebra/hover loop at all (lines are plain ANSI-colored text, always the terminal's own default background), so `utils.highlight_query_in_line`'s default `restore_bg='\\033[49m'` is directly correct, same simple case as `core/monitor_display.py`'s main pane. `_render_pane`'s OWN `_button_regions` row numbering stays UNSHIFTED, relative to its own top (row 1 = its own first line) -- `pane.py`'s `_build_gpu_output` shifts every region by `+_GPU_SEARCH_BAR_LINES` EXTERNALLY, after `_render_pane` returns (mirrors `worker_proxy_pane.py`'s identical rebuild-then-shift precedent) -- keeps `_render_pane` a reusable, standalone, directly-testable unit; `dev/click_ui/p4_gpu_news_button_probe.py` (which calls `_render_pane` directly) needed ZERO changes.
**(2026-09, gpu-pane-split milestone) `_render_pane` (was 110 LOC, HARD) split into one helper per section, itself now a thin orchestrator (15 LOC):** `_build_status_row(s, prefix, name_width, btn, action, target, error_counts, pane_width, phys_row)` — the shared row-builder, parameterized by prefix/name_width/button/action/target, used by both `_render_preset_rows` (`prefix='[i+1] '`, `name_width=16`, context-dependent button via `_button_label`) and `_render_arbitrary_rows` (`prefix='    '`, `name_width=12`, always `'[stop]'`/`'stop'`) — these two were near-duplicate row-builders before the split, differing only in those 5 values; `_render_gpu_header` (title + optional `[refresh]`); `_render_collections_block`; `_render_errors_block`; `_render_anomalies_line`; `_apply_gpu_search_highlight` (list-mutation in place, the single post-loop highlight pass). `_render_pane` itself now just calls each in sequence and joins.
**Reads:** `_toggle_state` (imported from `gpu_actions`, for `_status_text`); all other state passed as function arguments.
**Writes:** `_button_regions` (cleared and rebuilt every `_render_pane` call) — returns rendered string; no other mutation.
**Called by:** `pane.py` (`_render_pane` directly; `_gpu_search_on_commit`'s own baseline render); `dev/click_ui/p4_gpu_news_button_probe.py` (`_render_pane` directly, standalone).
**Calls out:** `gpu_actions` (`_toggle_state`), `utils` (`format_timestamp`, `compute_header_rule_len`, `highlight_query_in_line`), `colors` (2026-09 constants-split milestone — re-pointed from `constants`, all 8 imported names are colors).

---

### status.py (202 LOC)

**Purpose:** State-file registry reader + collection fetcher. Globs `~/.rag-locks/server-port-*.json`; builds preset + arbitrary status lists; detects six anomaly classes; logs to `src/gpu_pane/logs/gpu_pane.log` via `TimedRotatingFileHandler(when='d', backupCount=7)` — rotates daily, 7-day retention. `PRESET_NAMES` list discovered at module-import-time via `subprocess.run(['rag-cli', 'server', 'presets', '--json'])` with 3s timeout; returns `[]` on any failure (no fabricated names). `_fetch_collections()` calls `rag-cli list_collections --json` (5s timeout); returns `[{collection, chunks}]`; returns `[]` on any failure (rag-cli absent, Postgres down, JSON error).
**Reads:** `~/.rag-locks/server-port-*.json` JSON (content + mtime); `http://localhost:<port>/health`; `ps -o rss=`; `rag-cli server presets --json` (once per process at import); `rag-cli list_collections --json` (called by pane.py every 30s).
**Writes:** nothing (read-only); anomalies appended to module-level `_last_anomalies`; logging to `gpu_pane.log`.
**Called by:** `pane.py`.
**Calls out:** `urllib.request` (health), `subprocess` (ps + rag-cli preset discovery + rag-cli list_collections).

---

### errors.py (49 LOC)

**Purpose:** Read RAG's `errors.jsonl`, filter to (a) anomaly codes in `ERROR_CODES` (single_instance_alive_replaced / busy / watchdog_unlinked_dead / watchdog_killed_orphan) AND (b) >= local midnight. Lifecycle events (start_*/stop_*/state_unlinked) are excluded — the file mixes both and only the anomalies are surfaced to the GPU pane. `ERROR_CODES` mirrors src/rag/error_log.py (RAG) ERROR_CODES — keep in sync on writer-side additions.
**Reads:** `/Users/brunowinter2000/.../RAG/src/rag/logs/errors.jsonl` (hard-coded path).
**Writes:** nothing.
**Called by:** `pane.py`.
**Calls out:** nothing beyond stdlib.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `gpu_actions.py` (2026-09, moved from `pane.py`) | `_toggle_state: dict[str → ('starting'\|'stopping', float ts)]` — imported back into `pane.py` and `gpu_render.py`, same dict object | `_status_text` (`gpu_render.py`), `_expire_toggle_states`, key guard in digit+click handlers (`pane.py`) | `_toggle_server` (`pane.py`), `_fire_button` (`gpu_actions.py`) |
| `gpu_render.py` (2026-09, moved from `pane.py`) | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target_str)]` — imported back into `pane.py`, same dict object | mouse-click handler in `pane.py`'s `_handle_gpu_mouse` | `_render_pane` (cleared and rebuilt per tick) |
| `pane.py` | `collections: list[dict]` (local in `run_gpu_loop`) | `_render_pane` (passed as arg) | `_fetch_collections()` every 30s + on force-refresh |
| `pane.py` | `last_collections_refresh: float` (local in `run_gpu_loop`) | 30s cadence check | updated after each `_fetch_collections()` call |
| `pane.py` | `_gpu_search: search_bar.SearchState` (2026-08-18) | `.matches` holds 0-based indices into `_render_pane`'s own lines list (no click-interactivity concept for matches -- only buttons are clickable, so no coupling to physical row numbers) | mutated by `_poll_gpu_input`/`_handle_gpu_mouse` (2026-09: extracted from `run_gpu_loop`'s own former inline dispatch) |
| `status.py` | `_last_anomalies: list[dict]` | `get_anomalies()` called by pane.py | `_warn()`, `_check_legacy_files()`, `_status_for_state()` (reset each tick by `all_statuses()`) |
| `status.py` | `_legacy_warned: bool` | `_check_legacy_files()` | `_check_legacy_files()` (set on first legacy-file detection) |
| `status.py` | `PRESET_NAMES: list[str]` | `pane.py` (digit-key handler, `_toggle_server`); `all_statuses` (preset row order) | `_discover_preset_names()` at module import — frozen for process lifetime; `[]` on rag-cli failure |

**`_toggle_state` key convention:** preset name (e.g. `'embedding'`) for presets; `'port-{N}'` (e.g. `'port-8090'`) for arbitrary servers.

**`_button_regions` value convention:** `(action, name)` for preset rows; `('stop', 'port-{N}')` for arbitrary rows; `('refresh', 'refresh')` for the header `[refresh]` button (2026-07-30) — the sentinel `action == 'refresh'` is checked FIRST in `pane.py`'s `_handle_gpu_mouse` so it never reaches `_fire_button`.

## Gotchas

- `RAG_LOG_DIR` in `errors.py` is hard-coded absolute path (user-specific). Must match actual RAG project location.
- Stopped servers skip httpx health check entirely — no ConnectionRefused errors on every tick.
- `rag-cli server start` takes 30-90s for embedding model load; badge flips naturally when `/health` returns 200.
- **Idle countdown requires `log_path` in the state file.** State files written by the box architecture always include `log_path`. If a server was started outside the box (no state file written), it does not appear at all. If `log_path` points to a file that no longer exists (deleted externally), the countdown shows `?` and an anomaly is logged.
- Arbitrary block only renders when `len(arbitrary) > 0`. If all box-managed servers are presets, the divider and arbitrary section are omitted entirely.
- `enable_mouse()` captures all mouse events (including wheel) — tmux native scrollback (`Ctrl+B [`) does NOT work while pane is active.
- `disable_mouse()` is called in the `finally` block before `restore_terminal()` to avoid leaving SGR mouse mode active in the parent shell after pane exit.
- `_render_pane` clears `_button_regions` at the top — anyone reading the regions outside the same render-tick sees stale data.
- click triggers `_fire_button` which sets `_toggle_state` to `starting`/`stopping` then runs `rag-cli` fire-and-forget; if the rag-cli execution stalls, label gets stuck until `TOGGLE_TIMEOUT=120s` natural expiry.
- **Hard cut:** pane does NOT read `~/.rag-locks/rag-server-{name}.port` or `rag-server-{name}-last-used` files. Those are obsolete. Legacy `.port` files are detected and logged as anomalies (via glob in `_check_legacy_files`) but their content is never read.
- **PRESET_NAMES is frozen per pane process.** Discovery runs once at `status.py` import via `rag-cli server presets --json`. To pick up RAG-side SERVERS changes, user must respawn the pane via Ctrl+R (tmux respawn-pane re-imports the module). Without respawn, new presets registered in RAG don't appear in the pane.
- **rag-cli failure at import → empty preset block, no fabricated names.** `_discover_preset_names` returns `[]` on FileNotFoundError / TimeoutExpired / JSONDecodeError / KeyError. The GPU Servers header renders with no preset rows; all running servers land in the arbitrary block. No anomaly logged (mirrors `_fetch_collections` behavior). Check `which rag-cli` from the gpu_pane process's environment if presets never appear.
- **Collections block shows `(none indexed)` on any `_fetch_collections()` failure** — Postgres down, rag-cli absent, timeout. Silent degradation; no anomaly logged. Collections start as `[]` at pane launch and populate after the first 30s tick (or on 'r').
- **`list_collections` is lock-exempt in rag-cli** — pure Postgres aggregate read (`count(*) group by collection`), safe concurrent with indexing writes (Postgres MVCC). Does not require the advisory flock. `_fetch_collections()` will succeed even while `rag-cli index` or `rag-cli update_docs` holds the lock.
- **`status.py`'s `except PermissionError: pass  # PID alive, different owner` keeps its inline comment** — the platform's write-time safety hook rejects any Edit/Write whose new content contains a bare `except ...: pass` with no comment, so the comment could not be removed without changing the `pass` into a different statement (out of scope for a comment-only pass). Every other comment in this package was deleted per the standard; this one line is the sole documented exception.
