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
- session_analysis/ — Session JSONL analysis scripts (cache behavior, rebuild detection)

## session_analysis/

Analysis scripts for Claude Code session JSONL data. No pipeline mapping — standalone analysis tools.

**Scripts:**

| Script | Description |
|--------|-------------|
| `01_extract.py` | Extract and analyze Claude Code session JSONL files |
| `02_cache_timeline.py` | Analyze cache/token behavior over time in Claude Code sessions |
| `03_cache_rebuild_context.py` | Detect cache rebuilds and display surrounding message context; `--session <path>` or `--all`; `--context N` (default 5), `--summary-only` |
| `04_cache_validation.py` | Validate proxy cache breakpoint placement and stability; `<proxy_log.jsonl>` `--limit N` `--rebuilds-only` |

**Usage:**

```bash
./venv/bin/python dev/session_analysis/03_cache_rebuild_context.py --session ~/.claude/projects/<encoded>/session.jsonl
./venv/bin/python dev/session_analysis/03_cache_rebuild_context.py --all
./venv/bin/python dev/session_analysis/03_cache_rebuild_context.py --session <path> --context 10 --summary-only
```
