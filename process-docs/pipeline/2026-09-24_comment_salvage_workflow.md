# Comment salvage for workflow.py — 2026-09-24

Root entry point that dispatches the CLI modes. Salvage per the rule that every comment is relocated verbatim before deletion; no triage.

Every comment removed from `workflow.py`, verbatim, grouped by consecutive comment block in source order. Line numbers refer to the file before removal. Each block names the code line that followed it. The three section markers stay in the file and are not listed. The file contains no docstring and nothing reads `__doc__`.

## Salvage from workflow.py

### Lines 4-4, followed by `from src.startup import parse_arguments, setup_signal_handlers, print_startup_message`

```
# From src/startup.py: CLI argument parsing, signal handlers, startup messages
```

### Lines 7-7, followed by `from src.tmux_launcher import launch_split_screen, restart_panes`

```
# From src/tmux_launcher.py: Launch tmux split-screen session; self-heal missing panes
```

### Lines 10-10, followed by `from src.core.monitor import run_monitor`

```
# From src/core/monitor.py: Run continuous monitoring loop
```

## Process notes

- Removed: 3 full-line comments. Kept: the `# INFRASTRUCTURE` and `# ORCHESTRATOR` markers. No docstring existed and a grep for `__doc__` returned nothing.
- Verification: token sequence compared before and after with comments and NL tokens dropped, 255 tokens on both sides, identical. `python workflow.py --help` was diffed as well; the only difference is the argparse usage-wrap indentation, which follows the program name (the old copy ran under a different file name).
