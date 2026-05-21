# dev/hook_firing/

## Role

Offline analysis suite for CC hook-block events. Reads `~/.claude/projects/*/*.jsonl` session logs, extracts `PreToolUse hook error: BLOCKED` events, classifies each block as TP/FP/uncertain using per-hook heuristics, and writes an MD report. Read-only — no hook code changes.

FP classification focus: `block_chained_sleep` settling-time FPs (sleep N ≤ 5 after side-effect), heredoc-in-$() scanner gap (confirmed FP class), and known-legitimate patterns that the current hooks over-block. Classification feeds the rule-refinement decision, not a bug report.

## Modules

### analyze.py (398 LOC)

**Purpose:** Walk all CC session JSONL files, extract hook-block events in a date window, classify each block FP/TP/uncertain via per-hook heuristics, write structured MD report. Trigger lookup uses `tool_use_id` for exact match (not "first tool_use in parent"), full command stored without truncation. Sections: summary-by-hook (with FP/TP/uncertain counts + FP rate), friction candidates, top trigger patterns (with FP/TP counts), events table (with FP verdict + heuristic column).
**Reads:** `~/.claude/projects/*/*.jsonl` (CC session logs).
**Writes:** `dev/hook_firing/reports/<timestamp>.md` (or `--output` path).
**Called by:** user (CLI). Never imported.
**Calls out:** stdlib only (`argparse`, `json`, `re`, `collections`, `datetime`, `pathlib`).

**Performance note:** mtime pre-filter skips JSONL files whose modification time predates the `--since` window (1h buffer). Fast-path `"BLOCKED" not in line` skips parsing of non-block lines.

**FP heuristics (per hook):**

| Hook | FP class | TP class | Uncertain |
|---|---|---|---|
| `block_chained_sleep` | heredoc-in-$() gap; sleep N ≤ 5 after side-effect (settling) | sleep in loop; N > 10; run_in_background | N ≤ 10 no context; trigger truncated |
| `block_dangerous_kill` | heredoc-in-$() gap | pkill -f in active command | pattern not in visible trigger |
| `block_cd_drift` | — | cd into worktree without cd-back | worktree path not in trigger |
| `block_read_worktree` | — | main-session read of foreign worktree | worker session (own vs cross unclear) |
| `block_broad_grep` | git grep; --include= present | grep -r without --include= | — |
| `block_unauthorized_background` | fast-returning cmd (worker-cli send, echo) | non-canonical + bg=true | — |
| `block_venv_no_redirect` | redirect/tee present | venv script without redirect | venv not visible in trigger |
| all others | — | — | no heuristic (uncertain) |

## Usage

```bash
# default: last 7 days, all projects, all hooks
./venv/bin/python dev/hook_firing/analyze.py > /tmp/hook_firing.md 2>&1; tail -5 /tmp/hook_firing.md

# filter to a project and date range
./venv/bin/python dev/hook_firing/analyze.py --since 2026-05-01 --project Monitor_CC > /tmp/hf.md 2>&1

# filter to a specific hook
./venv/bin/python dev/hook_firing/analyze.py --hook block_chained_sleep > /tmp/hf.md 2>&1

# explicit output path
./venv/bin/python dev/hook_firing/analyze.py --output /tmp/blocks.md > /tmp/hf.md 2>&1
```

## CLI Flags

| Flag | Default | Description |
|---|---|---|
| `--since YYYY-MM-DD` | 7 days ago | Start of date window |
| `--project NAME` | (all) | Case-insensitive substring match on project name |
| `--hook NAME` | (all) | Case-insensitive substring match on hook script name |
| `--output PATH` | `dev/hook_firing/reports/<ts>.md` | Report output path |

## Report Sections

1. **Summary by Hook** — total / main / worker / TP / FP / uncertain / FP-rate per hook
2. **Friction Candidates** — (hook, branch, project) groups with ≥3 blocks in 30 min; signals stuck workers
3. **Top Trigger Patterns by Hook** — top-5 trigger commands per hook with FP/TP counts per pattern
4. **Events (newest first, max 40)** — raw event table with timestamp, hook, project, type, branch, trigger, FP verdict, heuristic note
