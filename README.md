# Monitor_CC - Claude Code CLI Monitor

Live monitoring tool for Claude Code CLI conversations - captures all tool calls with full input/output.

**Remote:** https://github.com/brunowinter8192/ClaudeCode-Monitor

## Directory Structure

```
Monitor_CC/
    workflow.py
    README.md
    CLAUDE.md
    LOGS_MAP.md
    src/                                 [See DOCS.md](src/DOCS.md)
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
# Monitor ALL active Claude Code sessions (tmux split-screen)
python3 workflow.py

# Monitor specific project only
python3 workflow.py --project /path/to/your/project

# Single mode (no tmux)
python3 workflow.py --mode main
python3 workflow.py --mode subagent
```
