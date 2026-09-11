# src/gpu_pane/

## Role

Standalone tmux window 4 pane that monitors RAG GPU servers and indexed collections
cross-project. Reads `~/.rag-locks/server-port-{N}.json` state files written by the RAG project's
box architecture; renders GPU Servers (preset + arbitrary), RAG Collections, and Errors-today
blocks. Digit keys `1`-`9` and button clicks toggle preset/arbitrary servers via `rag-cli`. No
dependency on `core/monitor.py` or `active_project_filter`. Touch this package to change the
GPU-monitoring UI or anomaly detection. Do NOT touch it to change RAG's own server lifecycle —
that lives in the RAG project.

## Public Interface

`from src.gpu_pane.pane import run_gpu_loop` — entry point called by `workflow.py --mode gpu`.

## Flow

1. `run_gpu_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop; each tick calls `all_statuses()` (glob `~/.rag-locks/server-port-*.json`) and `get_anomalies()`/`errors_today()`.
2. Every 30s (or on force-refresh): `_fetch_collections()` calls `rag-cli list_collections --json`.
3. `gpu_render._render_pane()` renders three blocks (GPU Servers, RAG Collections, Errors today) and rebuilds `_button_regions`.
4. Digit key `1`-`9` or a button click → `gpu_actions._fire_button` / `pane._toggle_server` → `rag-cli server start|stop|restart <name>` fire-and-forget, tracked in `_toggle_state` until the real status confirms the transition or `TOGGLE_TIMEOUT` (120s) expires.

## Modules

### pane.py (233 LOC)

**Purpose:** Event loop — keyboard/mouse dispatch, row-1 search bar (highlight-only, no scroll infra since this pane has none), digit-key preset toggle. `GPU_POLL_INTERVAL = 2.0` s; `COLLECTIONS_POLL_INTERVAL = 30.0` s. `_toggle_server` stays in this module (not `gpu_actions.py`) because it reads the module-level `PRESET_NAMES` bare name that `dev/click_ui/p4_gpu_news_button_probe.py` monkeypatches directly.
**Reads:** `all_statuses()`, `get_anomalies()`, `errors_today()`, `errors_today_by_server()` every 2s tick; `_fetch_collections()` every 30s tick (+ force-refresh); `PRESET_NAMES` from `status` (set at import).
**Writes:** stdout (full-screen ANSI); `/tmp/monitor_cc_error.log` on caught exception (via `pane_error_log`); mutates `_gpu_search` (search state); mutates `gpu_actions._toggle_state` and `gpu_render._button_regions` (imported, same objects).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `rag-cli` (subprocess CLI, `_toggle_server`).

---

### gpu_actions.py (44 LOC)

**Purpose:** Server control actions. `TOGGLE_TIMEOUT = 120` s — how long a `[starting…]`/`[stopping…]` label persists before natural expiry. `_toggle_state: dict[str → ('starting'|'stopping', float ts)]` is module-level, mutated by `_expire_toggle_states`, `_fire_button`, and `pane.py`'s own `_toggle_server` (imported back into `pane.py`, same dict object). `_expire_toggle_states` removes entries once the server's real status confirms the transition, or after `TOGGLE_TIMEOUT`. `_fire_button` fires the `rag-cli server <action> [--port <port>] <name>` subprocess and stamps `_toggle_state`.
**Reads:** `presets`/`arbitrary` lists passed as arguments.
**Writes:** `_toggle_state` (add/remove entries); one `subprocess.Popen` per `_fire_button` call.
**Called by:** `pane.py` (`_expire_toggle_states`, `_fire_button`, `_toggle_server`'s reads), `gpu_render.py` (`_status_text` reads `_toggle_state`).
**Calls out:** `rag-cli` (subprocess CLI).

---

### gpu_render.py (178 LOC)

**Purpose:** Rendering — three-block render (GPU Servers + RAG Collections + Errors), idle-countdown computation, context-dependent button labels/regions. `IDLE_TIMEOUT` (env `RAG_SERVER_IDLE_TIMEOUT`, default 3600) is used only by `_format_countdown`. `_render_pane` is a thin orchestrator over `_render_gpu_header`, `_render_preset_rows`, `_render_arbitrary_rows`, `_render_collections_block`, `_render_errors_block`, `_render_anomalies_line`, `_apply_gpu_search_highlight`.
**Reads:** `gpu_actions._toggle_state` (for `_status_text`); all other state passed as function arguments.
**Writes:** `_button_regions` (cleared and rebuilt every `_render_pane` call); returns the rendered string.
**Called by:** `pane.py` (`_render_pane` directly; the search-commit baseline render); `dev/click_ui/p4_gpu_news_button_probe.py` (`_render_pane` directly, standalone).
**Calls out:** none.

---

### status.py (201 LOC)

**Purpose:** State-file registry reader + collection fetcher. Globs `~/.rag-locks/server-port-*.json`, builds preset + arbitrary status lists, detects six anomaly classes, logs to `src/gpu_pane/logs/gpu_pane.log` via `TimedRotatingFileHandler` (daily, 7-day retention). `PRESET_NAMES` is discovered once at module-import time via `rag-cli server presets --json` (3s timeout; `[]` on any failure). `_fetch_collections()` calls `rag-cli list_collections --json` (5s timeout; `[]` on any failure).
**Reads:** `~/.rag-locks/server-port-*.json` (content + mtime); `http://localhost:<port>/health`; `ps -o rss=`; `rag-cli server presets --json` (once, at import); `rag-cli list_collections --json` (every 30s).
**Writes:** nothing (read-only); anomalies appended to module-level `_last_anomalies`; logs to `gpu_pane.log`.
**Called by:** `pane.py`.
**Calls out:** `rag-cli` (subprocess CLI); `ps` (subprocess CLI).

---

### errors.py (49 LOC)

**Purpose:** Reads RAG's `errors.jsonl`, filters to anomaly codes in `ERROR_CODES` (`single_instance_alive_replaced`/`busy`/`watchdog_unlinked_dead`/`watchdog_killed_orphan`) at or after local midnight. Lifecycle events (`start_*`/`stop_*`/`state_unlinked`) are excluded — the file mixes both, and only the anomalies surface to this pane.
**Reads:** RAG's `errors.jsonl` (hard-coded path).
**Writes:** nothing.
**Called by:** `pane.py`.
**Calls out:** none.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `gpu_actions.py` | `_toggle_state: dict[str → ('starting'\|'stopping', float ts)]` — imported back into `pane.py`/`gpu_render.py`, same dict object | `_status_text` (`gpu_render.py`), digit/click handlers (`pane.py`) | `_toggle_server` (`pane.py`), `_fire_button` (`gpu_actions.py`) |
| `gpu_render.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, target_str)]` — imported back into `pane.py`, same dict object | mouse-click handler in `pane.py` | `_render_pane` (cleared and rebuilt per tick) |
| `pane.py` | `_gpu_search: search_bar.SearchState` | `.matches` holds 0-based indices into `_render_pane`'s own lines list | mutated by `_poll_gpu_input`/`_handle_gpu_mouse` |
| `status.py` | `_last_anomalies: list[dict]` | `get_anomalies()` | reset each tick by `all_statuses()` |
| `status.py` | `PRESET_NAMES: list[str]` | `pane.py` (digit-key handler, `_toggle_server`); `all_statuses` (preset row order) | `_discover_preset_names()` at module import — frozen for the process lifetime |

**`_toggle_state` key convention:** preset name (e.g. `'embedding'`) for presets; `'port-{N}'` for arbitrary servers.

## Gotchas

- Stopped servers skip the httpx health check entirely — no connection-refused errors on every tick.
- `rag-cli server start` takes 30-90s for embedding model load; the badge flips naturally once `/health` returns 200.
- **Idle countdown requires `log_path` in the state file.** If a server was started outside the RAG box architecture (no state file), it never appears. If `log_path` points to a deleted file, the countdown shows `?` and an anomaly is logged.
- `enable_mouse()` captures all mouse events (including wheel) — tmux native scrollback (Ctrl+B `[`) does not work while the pane is active.
- `_render_pane` clears `_button_regions` at the top of every call — anyone reading the regions outside the same render tick sees stale data.
- **Hard cut:** this pane does not read legacy `~/.rag-locks/rag-server-{name}.port` files — they are detected and logged as anomalies (via glob) but their content is never read.
- **`PRESET_NAMES` is frozen per pane process.** Discovery runs once at `status.py` import. To pick up a RAG-side preset change, the pane must be respawned (Ctrl+R triggers a tmux `respawn-pane`, which re-imports the module).
- **`rag-cli` failure at import → empty preset block, no fabricated names.** `_discover_preset_names` returns `[]` on `FileNotFoundError`/`TimeoutExpired`/`JSONDecodeError`/`KeyError`; all running servers then land in the arbitrary block with no anomaly logged.
- **Collections block shows `(none indexed)` on any `_fetch_collections()` failure** (Postgres down, rag-cli absent, timeout) — silent degradation, no anomaly logged.
- **`list_collections` is lock-exempt in rag-cli** (pure Postgres aggregate read) — it succeeds even while `rag-cli index`/`update_docs` holds the advisory flock.
- `status.py`'s `except PermissionError: pass` (PID alive, different owner) must stay single-line — a two-line `except ...:\n    pass` with no comment is rejected by this codebase's write-time safety hook.
