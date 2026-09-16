# dev/worker_pane_split/

## Role
Cost measurement for the worker-panes' header-liveness read path (`src/workers/worker_tmux.py`'s `attach_worker_stats`). Settles whether the panesplit milestone's per-worker stat computation was a measurable regression, and proves the incremental-delta fix. Touch when changing `attach_worker_stats`/`parse_worker_stats_delta`.

## Public Interface
No `__init__.py` in this directory. Entry point is direct invocation: `./venv/bin/python dev/worker_pane_split/attach_worker_stats_cost_probe.py`.

## Flow
Picks real worker-worktree JSONL files under `~/.claude/projects/*--claude-worktrees-*/`, times `attach_worker_stats` against a realistic 5-worker set and the single largest real file found, and writes a timestamped report to `md/`. Rerunnable — every run measures the current code.

## Modules

### attach_worker_stats_cost_probe.py (212 LOC)

**Purpose:** Measures `attach_worker_stats` COLD (fresh cache, full read) and WARM (cached, no new bytes) cost over real worker JSONL files, then extrapolates to the real call pattern.
**Reads:** real worker JSONL files under `~/.claude/projects/*--claude-worktrees-*/`.
**Writes:** `md/attach_worker_stats_cost_probe_<timestamp>.md`; stdout summary.
**Called by:** none — manual measurement, run before and after a change to `attach_worker_stats`/`parse_worker_stats_delta`.
**Calls out:** `src.workers.worker_tmux` (`attach_worker_stats`, `find_worker_jsonl` monkeypatched to resolve to the real files under measurement) — loaded via `importlib.import_module`.

---

## State
No persistent state owned by this directory. The script's only mutation is a temporary monkeypatch of `mod_worker_tmux.find_worker_jsonl`, restored in a `finally` block before the function returns.
