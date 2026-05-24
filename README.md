# Monitor_CC

Real-time TUI dashboard for Claude Code CLI sessions. See every tool call, token breakdown, hook injection, and worker status as it happens.

## Features

- Live tool call monitoring with full input/output (main agent + subagents)
- 4-window tmux layout: Main + Tokens | Rules + Hooks | Workers | Warnings + Subagents
- Token profiling per session with input cache breakdown and output by block type
- Hook injection tracking with color-coded audience (Opus-only / Worker-only / Shared)
- Worker monitoring with real-time status, output tokens, and per-turn breakdown
- Keyboard + mouse interaction: expand/collapse, scroll, hover highlight
- Auto-discovery of active sessions with live session switching
- Cumulative session browser across multiple sessions

## Quick Start

```bash
git clone https://github.com/your-username/Monitor_CC.git
cd Monitor_CC
python3 workflow.py --project /path/to/your/project
```

This opens a tmux session with 4 windows and 7 panes. Switch windows with `Ctrl-b 0/1/2/3`.

## Prerequisites

- Python 3.10+
- tmux
- macOS or Linux (uses termios for raw terminal input)
- Optional: Pillow (for `dev/display/screenshot_panes.py` screenshot tool)

## Setup

No external dependencies required for the core monitor — stdlib only. Just clone and run.

**Per-clone (one-time):** activate the auto-deploy git hooks that keep `~/.claude/settings.json` in sync when `src/hooks/` changes:
```bash
git config core.hooksPath .githooks
```
See `src/hooks/DOCS.md` § Gotchas for details (worktree guard behavior, verification).

For the screenshot dev tool:
```bash
python3 -m venv venv
source venv/bin/activate
pip install Pillow
```

## Usage

### CLI

```bash
# Full dashboard (4-window tmux layout)
python3 workflow.py --project /path/to/project

# Single pane modes (no tmux)
python3 workflow.py --mode main --project /path/to/project
python3 workflow.py --mode tokens --project /path/to/project
python3 workflow.py --mode hooks --project /path/to/project
python3 workflow.py --mode workers --project /path/to/project
```

| Flag | Description |
|------|-------------|
| `--project PATH` | Filter sessions by project path |
| `--mode MODE` | `all` (default), `main`, `subagent`, `rules`, `warnings`, `hooks`, `tokens`, `workers`, `subagents` |
| `--ui` | Enable collapsible subagent UI |

### Window Layout

| Window | Panes | Content |
|--------|-------|---------|
| 0 main | 2 | Main monitoring output + Token profiling |
| 1 rules | 2 | Active rules display + Hook injections |
| 2 workers | 1 | Worker status and token breakdown |
| 3 debug | 2 | Warnings + Subagent list |

### Keyboard & Mouse

| Input | Action |
|-------|--------|
| `1-9` | Toggle expand/collapse for items |
| `a` | Expand all items |
| `A` | Collapse all items |
| Mouse click | Toggle expand/collapse |
| Mouse scroll | Scroll through items |
| Mouse hover | Highlight row |

## How It Works

Monitor_CC discovers active Claude Code sessions by scanning `~/.claude/projects/` for JSONL files. It polls these files for new tool calls, parses them, and renders a formatted live dashboard. Hook injections are tracked via a separate log file written by Claude Code's hook system.

## Troubleshooting

<details>
<summary>"Error: Already inside tmux session"</summary>

You're running inside an existing tmux session. Use a specific mode instead:
```bash
python3 workflow.py --mode main --project /path/to/project
```
</details>

<details>
<summary>No sessions appearing</summary>

- Check that Claude Code is running with an active session
- Verify the `--project` path matches your project directory
- Sessions are discovered in `~/.claude/projects/` — ensure this directory exists
</details>

<details>
<summary>Panes not updating</summary>

The monitor polls every 0.5 seconds. If a pane is empty, the session may not have produced tool calls yet. Check that the correct project filter is set.
</details>

## License

MIT
