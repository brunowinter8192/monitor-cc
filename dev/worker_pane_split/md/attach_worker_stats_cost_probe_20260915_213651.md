# attach_worker_stats real-file cost measurement

Run: 2026-09-15T21:36:51.174416

Found 211 real worker-worktree JSONL files under `~/.claude/projects/*--claude-worktrees-*/`.

## Typical set (5 workers, median-sized real files)

| File | Size (MB) |
|---|---|
| `f10af877-da60-43ec-9efe-22059da2a9c7.jsonl` | 1.60 |
| `85349ba7-2103-4224-867a-3e82d280def9.jsonl` | 1.60 |
| `bd6a41e4-c018-4ce5-a560-bc0439df4acc.jsonl` | 1.60 |
| `e00f5b12-1ed4-465b-8b04-926e652551da.jsonl` | 1.61 |
| `cd5d37d3-a544-4a14-afb3-9970fcafb9e7.jsonl` | 1.62 |

Total bytes across the 5 files: 8.02 MB

**COLD (fresh cache, full read -- what every tick cost BEFORE the incremental fix): 31.1 ms**
**WARM (cached, no new bytes -- what every tick AFTER the first costs with the fix): 0.14 ms**
speedup (COLD / WARM): 220x

## Extrapolation to the real call pattern (per-tick cost x ticks/s x 2 panes)

`POLL_INTERVAL` = 0.5s -> 2 refresh ticks/second/pane

| | one pane, ms/s | both panes, ms/s | both panes, % of one core |
|---|---|---|---|
| BEFORE the fix (every tick pays COLD) | 62.1 | 124.2 | 12.42% |
| AFTER the fix (every tick pays WARM) | 0.3 | 0.6 | 0.06% |

## Worst-case single file (largest real worker-worktree JSONL found)

`b98344ea-da3b-4054-b01f-44b85e572e40.jsonl` -- 196.07 MB
**COLD: 320.5 ms** -- **WARM: 0.08 ms**
