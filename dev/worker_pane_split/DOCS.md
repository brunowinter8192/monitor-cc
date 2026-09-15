# dev/worker_pane_split/

## Role

Cost measurement for the worker-panes' header-liveness read path (`src/workers/worker_tmux.py`'s
`attach_worker_stats`). Created to settle whether the panesplit milestone's move of per-worker
token/context-% stat computation into both worker panes' own refresh ticks was a measurable
regression, and to prove the incremental-delta fix that followed it. Touch this area when
changing `attach_worker_stats`/`worker_format.parse_worker_stats_delta`, or when a future report
of worker-pane lag needs a same-machine before/after comparison.

## Flow

Picks real worker-worktree JSONL files under `~/.claude/projects/*--claude-worktrees-*/`, times
`attach_worker_stats` against a realistic 5-worker set and the single largest real file found,
and writes a timestamped report to `md/`. Rerunnable — every run measures the CURRENT code, so
running it before and after a change to the read path gives a same-machine comparison pair.

## Modules

### attach_worker_stats_cost_probe.py (206 LOC)

**Purpose:** Measures `attach_worker_stats` COLD (fresh cache, full read — what every tick cost
before the 2026-09 incremental fix, and what the first tick after a pane starts or a worker's
resolved JSONL path changes still costs) and WARM (same cache, no new bytes — what every
steady-state tick costs after the fix) over a real 5-worker set and the single largest real
worker JSONL found, then extrapolates both to the actual call pattern (both panes, `POLL_INTERVAL`
gate).
**Reads:** real worker JSONL files under `~/.claude/projects/*--claude-worktrees-*/`.
**Writes:** `md/attach_worker_stats_cost_probe_<timestamp>.md`; stdout summary.
**Called by:** none — manual measurement, run before and after a change to
`attach_worker_stats`/`parse_worker_stats_delta`.
**Calls out:** `src.workers.worker_tmux` (`attach_worker_stats`, `find_worker_jsonl` monkeypatched
to resolve to the real files under measurement) — loaded via `importlib.import_module`.

---

## Gotchas

- The COLD number measured against the post-fix code is NOT identical to the pre-fix code's own
  per-tick cost, even though both are "a full read from byte 0" — the pre-fix code called two
  separate extractors (`extract_worker_tokens` then `extract_worker_context_pct`), each doing its
  own full `read_new_lines`+`parse_jsonl_lines` pass; the post-fix COLD path does one merged pass.
  The actual pre-fix measurement (5 workers: 70.3ms, worst-case single file: 623.6ms) is preserved
  in `md/attach_worker_stats_cost_probe_20260915_213048.md` since the pre-fix code no longer
  exists to re-measure directly; the post-fix run
  (`md/attach_worker_stats_cost_probe_20260915_213651.md`) is the COLD-vs-WARM comparison.
- `_find_worktree_jsonls` filters on the path substring `--claude-worktrees-`, which is how
  worker-spawned sessions' project directories are named — a plain (non-worktree) session file
  never appears in the measured set, by design (workers only ever run in worktrees).
