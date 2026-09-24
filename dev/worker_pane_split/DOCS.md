# dev/worker_pane_split/

## Role
Cost measurement for the worker panes' header-liveness read path in `src/workers/worker_tmux.py`. Settled whether the pane-split milestone's per-worker stat computation was a measurable regression and proves the incremental-delta fix. Touch when changing that stat path.

## Public Interface
No `__init__.py`. Entry point: `./venv/bin/python dev/worker_pane_split/attach_worker_stats_cost_probe.py`.

## Flow
Picks real worker-worktree JSONL files, times the stat attachment against a realistic five-worker set and the single largest file, and writes a timestamped report to `md/`. Rerunnable; every run measures the current code.

## Modules

### attach_worker_stats_cost_probe.py (212 LOC)

**Purpose:** Measures cold (full read) and warm (cached) cost of the worker stat attachment over real worker JSONLs and extrapolates to the real call pattern.
**Reads:** real worker JSONL files under the user's Claude projects worktree directories.
**Writes:** `md/attach_worker_stats_cost_probe_<timestamp>.md`; stdout summary.
**Called by:** none; manual measurement before and after a change.
**Calls out:** `src.workers.worker_tmux` via `importlib`, with worker-file lookup patched to the real files.

---

## State
No persistent state. The only mutation is a temporary patch of the worker-file lookup, restored before the run returns.
