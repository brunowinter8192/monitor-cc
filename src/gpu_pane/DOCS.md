# src/gpu_pane/

## Role

Standalone tmux Window 4 pane that monitors the three RAG GPU servers (embedding, reranker, splade) cross-project. Reads `~/.rag-locks/rag-server-<name>.port` files, `errors.jsonl` from RAG, and per-server `~/.rag-locks/rag-server-<name>-last-used` timestamp files for the idle-countdown display. Digit keys `1`/`2`/`3` toggle each server. Mouse clicks on `[stop]`/`[start]`/`[restart]` buttons in each server row fire context-dependent actions (state-aware: stop running+healthy, restart running+unhealthy, start stopped). No dependency on `core/monitor.py` or `active_project_filter`.

## Public Interface

`from src.gpu_pane.pane import run_gpu_loop` — entry point called by `workflow.py --mode gpu`.

## Flow

1. `run_gpu_loop()` → `setup_keyboard_input()` + `enable_mouse()` → 2s tick loop.
2. Each tick: `all_statuses()` (port file + httpx /health + ps RSS) + `errors_today()` → `_render_pane()` → write to stdout if changed.
3. Per running server in render: `_format_countdown(name, status)` reads `~/.rag-locks/rag-server-<name>-last-used`, computes `IDLE_TIMEOUT - elapsed`, renders `stops in MM:SS` / `H:MM:SS` / `stopping…`. Hidden when stopped or timestamp missing.
4. `_render_pane` rebuilds `_button_regions: dict[(start_col, end_col, phys_row) → (action, server_name)]` per render — maps button-label cells to click actions.
5. Digit key → `_toggle_server()` → `subprocess.Popen(["rag-cli", "server", "start|stop", name])` fire-and-forget.
6. Mouse click (button=0) → row+col matched against `_button_regions` → `_fire_button(action, server)` → `subprocess.Popen(["rag-cli", "server", action, server])`. In-flight guard via `_toggle_state` prevents double-fire.
7. `_toggle_state` dict shows `[starting…]`/`[stopping…]` until next status change or 120s timeout.

## Modules

### pane.py (254 LOC)

**Purpose:** Event loop, keyboard + mouse handling, idle-countdown computation, context-dependent click-button rendering, render orchestration.
**Reads:** `all_statuses()`, `errors_today()`, `errors_today_by_server()` on each tick; `~/.rag-locks/rag-server-<name>-last-used` per running server for countdown; `RAG_SERVER_IDLE_TIMEOUT` env (default 3600).
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `click_handler` (keyboard via `read_keypress`, mouse via `enable_mouse`/`disable_mouse`/`read_mouse_event`), `status`, `errors`, `subprocess.Popen` (rag-cli toggle).

---

### status.py (67 LOC)

**Purpose:** Per-server state: port file → PID liveness → httpx health → ps RSS.
**Reads:** `~/.rag-locks/rag-server-<name>.port` JSON; `http://localhost:<port>/health`; `ps -o rss=`.
**Writes:** nothing (read-only; stale port files deleted on dead-PID detection).
**Called by:** `pane.py`.
**Calls out:** `httpx`, `subprocess` (ps).

---

### errors.py (43 LOC)

**Purpose:** Read and filter today's errors from RAG's `errors.jsonl`.
**Reads:** `/Users/brunowinter2000/.../RAG/src/rag/logs/errors.jsonl` (hard-coded path).
**Writes:** nothing.
**Called by:** `pane.py`.
**Calls out:** nothing beyond stdlib.

---

## State

| Owner | State | Reads | Writes |
|---|---|---|---|
| `pane.py` | `_toggle_state: dict[name → ('starting'|'stopping', float ts)]` | `_status_text`, `_expire_toggle_states`, mouse-click handler | `_toggle_server`, `_fire_button` |
| `pane.py` | `_button_regions: dict[(start_col, end_col, phys_row) → (action, server_name)]` | mouse-click handler in `run_gpu_loop` | `_render_pane` (cleared and rebuilt per tick) |

## Gotchas

- `RAG_LOG_DIR` in `errors.py` is hard-coded absolute path (user-specific). Must match actual RAG project location.
- Stopped servers skip httpx health check entirely — no ConnectionRefused errors on every tick.
- `rag-cli server start` takes 30-90s for embedding model load; badge flips naturally when `/health` returns 200.
- Countdown depends on `~/.rag-locks/rag-server-<name>-last-used` being written by RAG's `touch_timestamp()`. If RAG runs older code with `TIMESTAMP_DIR = Path("/tmp")`, the file appears at the wrong location and the countdown stays empty.
- `enable_mouse()` captures all mouse events (including wheel) — tmux native scrollback (`Ctrl+B [`) does NOT work while pane is active.
- `disable_mouse()` is called in the `finally` block before `restore_terminal()` to avoid leaving SGR mouse mode active in the parent shell after pane exit.
- `_render_pane` clears `_button_regions` at the top — anyone reading the regions outside the same render-tick sees stale data.
- Mouse click → action mapping is context-dependent: `running+healthy → stop`, `running+unhealthy → restart`, `stopped → start`. Single-button-per-row (not [stop]+[start] both visible).
- **KNOWN BUG (Bead Monitor_CC-fg9d):** click triggers `_fire_button` which sets `_toggle_state` to `starting`/`stopping` but the actual rag-cli execution may not complete cleanly — label gets stuck until `TOGGLE_TIMEOUT=120s` natural expiry. Investigation pending.
