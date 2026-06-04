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

### pane.py (327 LOC)

**Purpose:** Event loop, keyboard + mouse handling, three-block render (GPU Servers + RAG Collections + Errors), idle-countdown computation, context-dependent button rendering. `COLLECTIONS_POLL_INTERVAL = 30.0` s controls the slower collection-count cadence; `last_collections_refresh` tracks last fetch. Digit-key handler accepts `'1'`-`'9'` capped to `len(PRESET_NAMES)`. Preset row format width 16 (fits longest variant name e.g. `embedding-0.6b`). Footer hint dynamic `[1-N] toggle presets`.
**Reads:** `all_statuses()`, `get_anomalies()`, `errors_today()`, `errors_today_by_server()` on each 2s tick; `_fetch_collections()` on each 30s tick (+ force-refresh); `RAG_SERVER_IDLE_TIMEOUT` env (default 3600); `PRESET_NAMES` from `status` module (set at import).
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `click_handler` (keyboard via `read_keypress`, mouse via `enable_mouse`/`disable_mouse`/`read_mouse_event`), `status`, `errors`, `subprocess.Popen` (rag-cli toggle).

---

### status.py (220 LOC)

**Purpose:** State-file registry reader + collection fetcher. Globs `~/.rag-locks/server-port-*.json`; builds preset + arbitrary status lists; detects six anomaly classes; logs to `src/gpu_pane/logs/gpu_pane.log` via `TimedRotatingFileHandler(when='d', backupCount=7)` — rotates daily, 7-day retention. `PRESET_NAMES` list discovered at module-import-time via `subprocess.run(['rag-cli', 'server', 'presets', '--json'])` with 3s timeout; falls back to legacy `['embedding', 'reranker', 'splade']`. `_fetch_collections()` calls `rag-cli list_collections --json` (5s timeout); returns `[{collection, chunks}]`; returns `[]` on any failure (rag-cli absent, Postgres down, JSON error).
**Reads:** `~/.rag-locks/server-port-*.json` JSON (content + mtime); `http://localhost:<port>/health`; `ps -o rss=`; `rag-cli server presets --json` (once per process at import); `rag-cli list_collections --json` (called by pane.py every 30s).
**Writes:** nothing (read-only); anomalies appended to module-level `_last_anomalies`; logging to `gpu_pane.log`.
**Called by:** `pane.py`.
**Calls out:** `urllib.request` (health), `subprocess` (ps + rag-cli preset discovery + rag-cli list_collections).

---

### errors.py (56 LOC)

**Purpose:** Read RAG's `errors.jsonl`, filter to (a) anomaly codes in `ERROR_CODES` (single_instance_alive_replaced / busy / watchdog_unlinked_dead / watchdog_killed_orphan) AND (b) >= local midnight. Lifecycle events (start_*/stop_*/state_unlinked) are excluded — the file mixes both and only the anomalies are surfaced to the GPU pane. `ERROR_CODES` mirrors src/rag/error_log.py (RAG) ERROR_CODES — keep in sync on writer-side additions.
**Reads:** `/Users/brunowinter2000/.../RAG/src/rag/logs/errors.jsonl` (hard-coded path).
**Writes:** nothing.
**Called by:** `pane.py`.
**Calls out:** nothing beyond stdlib.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_toggle_state: dict[str → ('starting'\|'stopping', float ts)]` | `_status_text`, `_expire_toggle_states`, key guard in digit+click handlers | `_toggle_server`, `_fire_button` |
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target_str)]` | mouse-click handler in `run_gpu_loop` | `_render_pane` (cleared and rebuilt per tick) |
| `pane.py` | `collections: list[dict]` (local in `run_gpu_loop`) | `_render_pane` (passed as arg) | `_fetch_collections()` every 30s + on force-refresh |
| `pane.py` | `last_collections_refresh: float` (local in `run_gpu_loop`) | 30s cadence check | updated after each `_fetch_collections()` call |
| `status.py` | `_last_anomalies: list[dict]` | `get_anomalies()` called by pane.py | `_warn()`, `_check_legacy_files()`, `_status_for_state()` (reset each tick by `all_statuses()`) |
| `status.py` | `_legacy_warned: bool` | `_check_legacy_files()` | `_check_legacy_files()` (set on first legacy-file detection) |
| `status.py` | `PRESET_NAMES: list[str]` | `pane.py` (digit-key handler, `_toggle_server`); `all_statuses` (preset row order) | `_discover_preset_names()` at module import — frozen for process lifetime |

**`_toggle_state` key convention:** preset name (e.g. `'embedding'`) for presets; `'port-{N}'` (e.g. `'port-8090'`) for arbitrary servers.

**`_button_regions` value convention:** `(action, name)` for preset rows; `('stop', 'port-{N}')` for arbitrary rows.

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
- **rag-cli not in PATH at gpu_pane import time → silent fallback to legacy 3-name list.** No anomaly logged for this case (intentional — keeps pane usable on machines without RAG installed). If user expects multi-model variants and only sees `embedding`/`reranker`/`splade`: check `which rag-cli` from the gpu_pane process's environment.
- **Collections block shows `(none indexed)` on any `_fetch_collections()` failure** — Postgres down, rag-cli absent, timeout. Silent degradation; no anomaly logged. Collections start as `[]` at pane launch and populate after the first 30s tick (or on 'r').
- **`list_collections` is lock-exempt in rag-cli** — pure Postgres aggregate read (`count(*) group by collection`), safe concurrent with indexing writes (Postgres MVCC). Does not require the advisory flock. `_fetch_collections()` will succeed even while `rag-cli index` or `rag-cli update_docs` holds the lock.
