# Dev Scripts

Development and testing scripts for Monitor_CC pipeline components.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

```bash
cd Monitor_CC/
```

## Documentation Tree

- [display/DOCS.md](display/DOCS.md) — Display layer tests + format_cache_tracker differential proof
- [jsonl/DOCS.md](jsonl/DOCS.md) — extract_cache_turns differential proof harness
- `hook_firing/reports/` — Historical hook block-event analysis snapshots (read-only archive; `analyze.py` and `DOCS.md` deleted 2026-05-24 — replaced by `src/logs/hook_firing.jsonl` persistent log)
- [pipeline/DOCS.md](pipeline/DOCS.md) — Pipeline evaluation suite (memory, I/O, parsing, format stability)
- [session_analysis/DOCS.md](session_analysis/DOCS.md) — Forensic session JSONL + proxy log analysis (cache behavior, rebuild detection, token attribution)
- [tool_injection/DOCS.md](tool_injection/DOCS.md) — MCP tool schema extraction for proxy-side tool injection
- [tool_use_analysis/DOCS.md](tool_use_analysis/DOCS.md) — Tool-use input size extraction (Proxy JSONL) + zero-result detection (Session JSONL)
- [tool_use_errors/DOCS.md](tool_use_errors/DOCS.md) — Empirical audit of `src/logs/tool_errors.jsonl` — cluster analysis + strip_hook_prefix.py cross-check (2026-05-30)
- [cursor_edges/DOCS.md](cursor_edges/DOCS.md) — NSPanel cursor-rect investigation probe — edge hover ↔/↕ blockers (NonactivatingPanel, subview coverage, mask conflicts)
- [menubar_nspanel/DOCS.md](menubar_nspanel/DOCS.md) — NSPanel sticky-toggle probe suite — persistent menubar panel replacing NSMenu auto-dismiss behavior
- [cc_source_research/DOCS.md](cc_source_research/DOCS.md) — CC binary + source research artifacts — env-var inventory from npm binaries, cross-referenced against community decompiles
- [ram_audit/DOCS.md](ram_audit/DOCS.md) — Pane RAM snapshot investigation — SIGUSR1 dump handler + `dump_all.sh` for live RSS/allocator capture across all panes
- [sleep_pattern_analysis/DOCS.md](sleep_pattern_analysis/DOCS.md) — Empirical audit of `block_chained_sleep` firing events; classifies cmd_before tokens as trivial-sync / load-bearing / mixed to inform `rewrite_chained_sleep.py` design
- [hook_smoke/DOCS.md](hook_smoke/DOCS.md) — Hook blocking/rewrite smoke tests — one test script per hook (block_dangerous_kill, block_read_worktree, rewrite_chained_sleep; block_chained_sleep preserved for reference; test_fire_log added 2026-05-24)
- `bead_tracker_chain/` — `smoke.py`: end-to-end smoke for `bead_tracker_hook` per-subcommand processing (4 cases: single, chained `;`, cross-project skip, pipe non-split); creates/deletes real test beads; no own DOCS.md

## session_analysis/

See [session_analysis/DOCS.md](session_analysis/DOCS.md).

6 standalone analysis scripts (01–06) + `04_reports/` for `05_req_breakdown.py` output. No pipeline mapping.
