# Monitor_CC - Claude Code CLI Monitor

Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output.

## Directory Structure

```
Monitor_CC/
├── workflow.py                     → Pipeline entry point
├── README.md
├── CLAUDE.md
├── LOGS_MAP.md
├── src/                            → [DOCS.md](src/DOCS.md)
├── decisions/                      → Pipeline decision records
├── sources/                        → External reference index
├── dev/                            → [DOCS.md](dev/DOCS.md)
├── not_working/                    → Failed approaches
└── repo/                           → tmux source code (external reference)
```

## Workflow

### Phase 1: Session Discovery

**Purpose:** Find active Claude Code sessions in ~/.claude/projects

**Input:** ~/.claude/projects directory, optional project path filter

**Output:** List of JSONL file paths sorted by modification time

**Details:** [src/DOCS.md](src/DOCS.md)

### Phase 2: Monitoring Loop

**Purpose:** Poll sessions, parse tool calls, display formatted output

**Input:** Session file paths, mode filter (main/subagent/all), UI mode flag

**Output:** Formatted console output with color-coded headers

**Details:** [src/DOCS.md](src/DOCS.md)

## Quick Start

```bash
cd /path/to/Monitor_CC

# Default: tmux split-screen (main + subagent panes)
python3 workflow.py

# Filter by project
python3 workflow.py --project /path/to/your/project

# Single mode (no tmux split)
python3 workflow.py --mode main
python3 workflow.py --mode subagent

# Collapsible UI for subagent monitoring
python3 workflow.py --project /path/to/project --ui
```

**Flags:**
- `--project PATH` - Filter sessions by project path
- `--mode {all,main,subagent,rules,warnings,hooks,tokens}` - Monitor mode (default: all = tmux 6-pane)
- `--ui` - Enable collapsible subagent UI (keyboard 1-9 to toggle)
