# attach_worker_stats real-file cost measurement

Run: 2026-09-15T21:30:48.154591

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

**`attach_worker_stats` over these 5 workers, one call: 70.3 ms**

## Extrapolation to the real call pattern

- `POLL_INTERVAL` = 0.5s -> 2 refresh ticks/second/pane
- one pane's own `attach_worker_stats` cost per second: 140.5 ms/s (14.1% of one CPU core, blocking, single-threaded)
- BOTH panes (worker-tokens + worker-proxy) doing this independently: 281.1 ms/s total (28.1% of one core)
- reads per second across both panes: 40 full-file reads/s (2 reads x 5 workers x 2 panes x 2 ticks/s)

## Worst-case single file (largest real worker-worktree JSONL found)

`b98344ea-da3b-4054-b01f-44b85e572e40.jsonl` -- 196.07 MB
**`attach_worker_stats` over this one file alone: 623.6 ms**

**This single worker alone costs MORE than one POLL_INTERVAL tick (0.5s) to refresh its own header stats.**
