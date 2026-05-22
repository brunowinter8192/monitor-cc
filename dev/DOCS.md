# Dev Scripts

Development and testing scripts for Monitor_CC pipeline components.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

```bash
cd Monitor_CC/
```

## Documentation Tree

- [display/DOCS.md](display/DOCS.md) — Display layer tests (tmux layout, rules rendering)
- [hook_firing/DOCS.md](hook_firing/DOCS.md) — Hook block event analysis from CC session JSONLs, with FP/TP classification
- [pipeline/DOCS.md](pipeline/DOCS.md) — Pipeline evaluation suite (memory, I/O, parsing, format stability)
- [session_analysis/DOCS.md](session_analysis/DOCS.md) — Forensic session JSONL + proxy log analysis (cache behavior, rebuild detection, token attribution)
- [tool_injection/DOCS.md](tool_injection/DOCS.md) — MCP tool schema extraction for proxy-side tool injection
- [tool_use_analysis/DOCS.md](tool_use_analysis/DOCS.md) — Tool-use input size extraction (Proxy JSONL) + zero-result detection (Session JSONL)
- [tool_use_errors/DOCS.md](tool_use_errors/DOCS.md) — Tool-use error analysis from Proxy JSONLs, with hookability classification
- [cursor_edges/DOCS.md](cursor_edges/DOCS.md) — NSPanel cursor-rect investigation probe — edge hover ↔/↕ blockers (NonactivatingPanel, subview coverage, mask conflicts)
- [menubar_nspanel/DOCS.md](menubar_nspanel/DOCS.md) — NSPanel sticky-toggle probe suite — persistent menubar panel replacing NSMenu auto-dismiss behavior
- [cc_source_research/DOCS.md](cc_source_research/DOCS.md) — CC binary + source research artifacts — env-var inventory from npm binaries, cross-referenced against community decompiles
- [ram_audit/DOCS.md](ram_audit/DOCS.md) — Pane RAM snapshot investigation — SIGUSR1 dump handler + `dump_all.sh` for live RSS/allocator capture across all panes
- `hook_smoke/` — Hook blocking rule smoke tests (chained_sleep, dangerous_kill, read_worktree); no own DOCS.md

## session_analysis/

See [session_analysis/DOCS.md](session_analysis/DOCS.md).

6 standalone analysis scripts (01–06) + `04_reports/` for `05_req_breakdown.py` output. No pipeline mapping.
