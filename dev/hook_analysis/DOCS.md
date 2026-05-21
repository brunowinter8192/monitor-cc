# dev/hook_analysis/

## Role

Offline analysis suite for CC hook-block events. Reads `~/.claude/projects/*/*.jsonl` session logs, extracts `PreToolUse hook error: BLOCKED` events, aggregates by hook/project/session-type, and writes an MD report. Read-only — no hook code changes.

## Modules

### analyze_blocks.py (346 LOC)

**Purpose:** Walk all CC session JSONL files, extract hook-block events in a date window, write a structured MD report. Sections: summary-by-hook, friction candidates (same hook+branch with ≥3 blocks in 30 min — likely false-positive loop), top trigger patterns per hook (from parentUuid lookup of the preceding tool_use call), by-project×hook, timeline, raw events with trigger command.
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
2. **Friction Candidates** — (hook, branch, project) groups with ≥3 blocks in 30 min; signals stuck workers
3. **Top Trigger Patterns by Hook** — top-5 trigger commands per hook (from parentUuid lookup); reveals which commands repeatedly hit each hook
4. **By Project × Hook** — cross-tabulation, sorted by total desc
5. **Timeline** — blocks per date per hook
6. **Events (newest first, max 50)** — raw event table with timestamp, hook, project, type, branch, trigger pattern, message prefix
