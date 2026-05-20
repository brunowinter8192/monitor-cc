# dev/hook_analysis/

## Role

Offline analysis suite for CC hook-block events. Reads `~/.claude/projects/*/*.jsonl` session logs, extracts `PreToolUse hook error: BLOCKED` events, aggregates by hook/project/session-type, and writes an MD report. Read-only — no hook code changes.

## Modules

### analyze_blocks.py (182 LOC)

**Purpose:** Walk all CC session JSONL files, extract hook-block events in a date window, write a structured MD report (summary-by-hook, by-project×hook, timeline, raw events).
**Reads:** `~/.claude/projects/*/*.jsonl` (CC session logs).
**Writes:** `dev/hook_analysis/reports/<timestamp>.md` (or `--output` path).
**Called by:** user (CLI). Never imported.
**Calls out:** stdlib only (`argparse`, `json`, `re`, `collections`, `datetime`, `pathlib`).

**Performance note:** mtime pre-filter skips JSONL files whose modification time predates the `--since` window (1h buffer). Fast-path `"BLOCKED" not in line` skips parsing of non-block lines.

## Usage

```bash
# default: last 7 days, all projects, all hooks
python3 dev/hook_analysis/analyze_blocks.py

# filter to a project and date range
python3 dev/hook_analysis/analyze_blocks.py --since 2026-05-01 --project Monitor_CC

# filter to a specific hook
python3 dev/hook_analysis/analyze_blocks.py --hook block_chained_sleep

# explicit output path
python3 dev/hook_analysis/analyze_blocks.py --output /tmp/blocks.md
```

## CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--since YYYY-MM-DD` | 7 days ago | Start of date window |
| `--project NAME` | (all) | Case-insensitive substring match on project name |
| `--hook NAME` | (all) | Case-insensitive substring match on hook script name |
| `--output PATH` | `dev/hook_analysis/reports/<ts>.md` | Report output path |

## Report Sections

1. **Summary by Hook** — total / main-session / worker-session counts per hook
2. **By Project × Hook** — cross-tabulation, sorted by total desc
3. **Timeline** — blocks per date per hook
4. **Events (newest first, max 50)** — raw event table with timestamp, hook, project, type, branch, message prefix
