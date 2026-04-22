# Dev Scripts

Development and testing scripts for Monitor_CC pipeline components.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

```bash
cd Monitor_CC/
```

## Documentation Tree

- [display/DOCS.md](display/DOCS.md) — Display layer tests (tmux layout, rules rendering)
- [pipeline/DOCS.md](pipeline/DOCS.md) — Pipeline evaluation suite (memory, I/O, parsing, format stability)
- [tool_injection/DOCS.md](tool_injection/DOCS.md) — MCP tool schema extraction for proxy-side tool injection
- [session_analysis/DOCS.md](session_analysis/DOCS.md) — Forensic session JSONL + proxy log analysis (cache behavior, rebuild detection, token attribution)
- [tool_use_analysis/DOCS.md](tool_use_analysis/DOCS.md) — Tool-use input size extraction (Proxy JSONL) + zero-result detection (Session JSONL)

## session_analysis/

See [session_analysis/DOCS.md](session_analysis/DOCS.md).

5 standalone analysis scripts (01–05) + `04_reports/` for `05_req_breakdown.py` output. No pipeline mapping.
