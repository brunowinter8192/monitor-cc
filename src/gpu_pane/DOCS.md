# src/gpu_pane/

## Role

Standalone tmux Window 4 pane that monitors the three RAG GPU servers (embedding, reranker, splade) cross-project. Reads `~/.rag-locks/rag-server-<name>.port` files and `errors.jsonl` from the RAG project — no dependency on `core/monitor.py` or `active_project_filter`. Digit keys 1/2/3 fire-and-forget toggle (start/stop) via `rag-cli`.

## Public Interface

`from src.gpu_pane.pane import run_gpu_loop` — entry point called by `workflow.py --mode gpu`.

## Flow

1. `run_gpu_loop()` → `setup_keyboard_input()` → 2s tick loop.
2. Each tick: `all_statuses()` (port file + httpx /health + ps RSS) + `errors_today()` → `_render_pane()` → write to stdout if changed.
3. Digit key → `_toggle_server()` → `subprocess.Popen(["rag-cli", "server", "start|stop", name])` fire-and-forget. `_toggle_state` dict shows `[starting…]`/`[stopping…]` until next status change or 120s timeout.

## Modules

### pane.py (111 LOC)

**Purpose:** Event loop, keyboard handling, render orchestration.
**Reads:** `all_statuses()`, `errors_today()`, `errors_today_by_server()` on each tick.
**Writes:** stdout (full-screen ANSI via `\033[2J\033[3J\033[H`).
**Called by:** `workflow.py` (`--mode gpu` route).
**Calls out:** `click_handler` (keyboard), `status`, `errors`, `subprocess.Popen` (rag-cli toggle).

---

### status.py (53 LOC)

**Purpose:** Per-server state: port file → PID liveness → httpx health → ps RSS.
**Reads:** `~/.rag-locks/rag-server-<name>.port` JSON; `http://localhost:<port>/health`; `ps -o rss=`.
**Writes:** nothing (read-only; stale port files deleted on dead-PID detection).
**Called by:** `pane.py`.
**Calls out:** `httpx`, `subprocess` (ps).

---

### errors.py (38 LOC)

**Purpose:** Read and filter today's errors from RAG's `errors.jsonl`.
**Reads:** `/Users/brunowinter2000/.../RAG/src/rag/logs/errors.jsonl` (hard-coded path).
**Writes:** nothing.
**Called by:** `pane.py`.
**Calls out:** nothing beyond stdlib.

---

## State

`_toggle_state` in `pane.py` — module-level dict, owned and mutated only by `pane.py`. Maps `name → ('starting'|'stopping', timestamp)`. Cleared on confirmed state change or 120s timeout.

## Gotchas

- `RAG_LOG_DIR` in `errors.py` is hard-coded absolute path (user-specific). Must match actual RAG project location.
- Stopped servers skip httpx health check entirely — no ConnectionRefused errors on every tick.
- `rag-cli server start` takes 30-90s for embedding model load; badge flips naturally when `/health` returns 200.
- `_render_pane` is side-effect-free — safe to call with synthetic data for testing.
