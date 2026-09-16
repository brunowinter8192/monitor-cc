## Salvage from dev/worker_pane_split/attach_worker_stats_cost_probe.py

```
"""
attach_worker_stats_cost_probe.py -- Measures the real wall-time cost of
src.workers.worker_tmux.attach_worker_stats against real worker JSONL files on disk, and
extrapolates to the actual call pattern introduced by the panesplit milestone: BOTH
worker_tokens_pane.py and worker_proxy_pane.py call attach_worker_stats(workers, cache) once per
refresh tick, each tick gated by POLL_INTERVAL (0.5s), for as many workers as are alive.

Measures TWO costs per file set, since the fix (2026-09, this same milestone) changed
attach_worker_stats from an unconditional full reparse into an incremental delta scan keyed by a
per-pane cache dict:

  - COLD: attach_worker_stats called with a FRESH (empty) cache -- a full read from byte 0 for
    every worker. This is what the pre-fix code paid on EVERY tick, forever (it never cached a
    position). Post-fix, it is only what the FIRST tick after a pane starts (or after a worker's
    resolved JSONL path changes) pays.
  - WARM: attach_worker_stats called AGAIN immediately after, same cache, no bytes appended to
    any file in between -- what every steady-state tick costs post-fix. Pre-fix had no such state
    to warm; every tick WAS a cold call.

The COLD number is therefore directly comparable to "what every tick cost before the fix" and the
WARM number is "what every tick after the first costs now" -- rerun this script before and after
touching attach_worker_stats/parse_worker_stats_delta to get a same-machine before/after pair.

Picks real worker-worktree JSONL files under ~/.claude/projects/ (paths containing
'--claude-worktrees-'), reports their sizes, and times attach_worker_stats over a realistic
5-worker set (the 2026-09-02 lag observation's own worker count) plus a stress set using the
largest real file found, to bound both the typical and worst-case cost.

Run: ./venv/bin/python dev/worker_pane_split/attach_worker_stats_cost_probe.py
"""
```

```
N_WORKERS_TYPICAL = 5  # matches the 2026-09-02 lag observation's own worker count
```

```
POLL_INTERVAL = 0.5    # src/constants.py -- both panes' refresh gate
```

```
# Typical set: N_WORKERS_TYPICAL files at the MEDIAN size (not the largest -- the largest
# is a single outlier that would misrepresent a normal worker fleet).
```

```
    # attach_worker_stats resolves the JSONL via find_worker_jsonl(session) -- monkeypatched
    # below to hand back these exact paths, so the REAL parse_worker_stats_delta runs unmocked
    # against real file bytes.
```

```
# Extrapolate to the ACTUAL call pattern: both panes call this every POLL_INTERVAL tick.
```

```
# Stress set: the single largest real file found (worst case a worker's own session can be).
```

## Salvage from dev/worker_pane_split/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Flow`, and `## Modules` sections already fit the required format. The pre-existing `## Gotchas` section has no home in the new fixed format and moved here in full:

```
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
```

## Notes for successor

- 1 file, 9 comments + 1 docstring — matches the measured state exactly. Two are trailing inline comments (`N_WORKERS_TYPICAL = 5  # ...`, `POLL_INTERVAL = 0.5    # ...`); the rest are standalone blocks (two 1-line, one 2-line, one 3-line) each directly preceding a `def` or a statement.
- No load-bearing docstring: grepped `__doc__` — zero hits. Docstring deleted outright.
- **Run directly** (safe): this script only reads real worker JSONL files under `~/.claude/projects/` (never mutates them) and writes one new timestamped report into the tracked `dev/worker_pane_split/md/` directory — it never overwrites an existing report (filename includes a fresh timestamp each run), so no tracked artifact needed backing up. Confirmed via `ls dev/worker_pane_split/md/` before/after: only the one newly-created file appeared, the two pre-existing tracked reports (`..._20260915_213048.md`, `..._20260915_213651.md`) were untouched.
- Verification: ran before and after the comment/docstring strip, diffed stdout with the wall-clock timing numbers themselves necessarily varying run-to-run (this is a live performance probe against real, currently-mutating session files — COLD/WARM ms values are expected to differ slightly between any two runs regardless of code changes) — confirmed the report *structure* (headers, table shapes, line count, which real files got selected as the typical/stress set) is identical between runs, and the two newly-written report `.md` files were deleted by explicit filename afterward (never a wildcard) to leave the tracked `md/` directory exactly as found.
- Because this probe's numeric output is inherently non-deterministic (real wall-clock timing against real, live-growing session files), the useful proof here is structural/output-shape equivalence, not byte-identical output — this differs from every other byte-identity harness in this milestone's areas, which hash synthetic/mocked input and expect exact hash equality.
