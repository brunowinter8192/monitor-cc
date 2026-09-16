# 2026-09-16 — Comment/docstring salvage for dev/hotkey_latency/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/hotkey_latency/` (2 `.py` files, 299 LOC) into conformance with the
project's three-marker comment standard. Every comment and both docstrings below were relocated
here verbatim before deletion from the code. Zero `__doc__`/`argparse` hits, so neither docstring
was load-bearing and both deleted outright.

**`probe_get_event_time.py` is a real desktop-driving GUI script — NEVER run or imported for this
milestone.** Its `main()` (properly guarded behind `if __name__ == '__main__':`, unlike
`dev/grid_probe/probe.py`) registers Cmd+Shift+9 as a **live, system-wide Carbon global hotkey**
via `RegisterEventHotKey`, then builds a real `rumps.App` and calls `app.run()`, blocking in an
AppKit-backed event loop until Ctrl+C. Behavior-unchanged proof used a **token-skeleton diff**
instead of execution (same method used for `dev/grid_probe/probe.py` last cycle): tokenized the
file before and after editing, dropped every `COMMENT` token and the module docstring's `STRING`
token (AST-identified) plus whitespace-structural tokens, and diffed the remaining token stream —
732 tokens before, byte-identical after (see the completion checklist in the task response for the
exact result). This proves zero code tokens were added, removed, or reordered.

**`analyze_latency.py` has a genuine, pre-existing crash unrelated to this milestone — found
while trying to run it for verification, NOT fixed here (out of scope; comments/docstrings only).**
It does `sys.path.insert(0, str(WORKTREE_ROOT / 'src'))` then `from menubar.menubar_log import
MENUBAR_LOG`, which imports `menubar` as a **top-level** package. But `menubar/__init__.py` does
`from .system import run`, and `src/menubar/system.py` itself does `from ../tmux_launcher import
...` — a double-dot relative import that needs `menubar` to be loaded as a proper subpackage
(`src.menubar`), not a top-level `menubar`. This raises `ImportError: attempted relative import
beyond top-level package` immediately on import, before `main()` ever runs, regardless of
arguments or cwd — confirmed reproducible both from the directory itself and from the project
root. This is the same class of dead-end already documented for
`dev/timer-loop/p3_project_scope_incident_probe.py` two cycles ago. Verification here used the
same normalized-traceback method Main approved for that file: stripped line numbers (comment
deletion shifts every line below it) and compared exception type + message + frame file/function
sequence before vs. after — identical both times.

---

## Salvage from dev/hotkey_latency/probe_get_event_time.py

Module docstring (was lines 1-16):
```
Verifies Carbon's GetEventTime(event)/GetCurrentEventTime() symbols resolve and produce a
plausible main-thread-stall delta — the technique used by src/menubar/hotkey_controller.py's
per-press queue_delay_ms instrumentation (see process-docs/hotkey_latency/).

Two checks:
  1. Symbol-resolution + monotonicity — non-interactive, runs standalone (no GUI focus needed).
  2. Live delta on a real key press — registers throwaway global hotkey Cmd+Shift+9 (unused
     elsewhere in this codebase) and prints queue_delay_ms on each press.

Usage (from project root):
    ./venv/bin/python3 dev/hotkey_latency/probe_get_event_time.py

Then press Cmd+Shift+9 anywhere (global hotkey, no focus required) — a line prints per press.
Ctrl+C to exit. No menu bar icon is shown (LSUIElement, no status item).
```

Was line 25, trailing on the `_CMD_SHIFT_9_KEYCODE` assignment:
```
_CMD_SHIFT_9_KEYCODE = 0x19            # kVK_ANSI_9
```
(the comment token itself is `# kVK_ANSI_9`)

Was line 26, trailing on the `_CMD_SHIFT_MODIFIERS` assignment:
```
_CMD_SHIFT_MODIFIERS = 0x0100 | 0x0200  # cmdKey | shiftKey
```
(the comment token itself is `# cmdKey | shiftKey`)

Was line 27, trailing on the `_MBAR_SIG` assignment:
```
_MBAR_SIG            = 0x4D424152      # OSType 'MBAR' — matches hotkey_controller.py convention
```
(the comment token itself is `# OSType 'MBAR' — matches hotkey_controller.py convention`)

Was line 28, trailing on the `_PROBE_ID` assignment:
```
_PROBE_ID            = 999             # EventHotKeyID.id, collision-free with production IDs (1, 2..10, 20, 21, 30)
```
(the comment token itself is `# EventHotKeyID.id, collision-free with production IDs (1, 2..10, 20, 21, 30)`)

Was line 29, trailing on the `_kEventParamDirect` assignment:
```
_kEventParamDirect   = 0x2D2D2D2D      # kEventParamDirectObject ('----')
```
(the comment token itself is `# kEventParamDirectObject ('----')`)

Was line 30, trailing on the `_typeEventHotKeyID` assignment:
```
_typeEventHotKeyID   = 0x686B6964      # typeEventHotKeyID ('hkid')
```
(the comment token itself is `# typeEventHotKeyID ('hkid')`)

Was line 39, trailing on the `_HOTKEY_EVENT_SPEC` assignment:
```
_HOTKEY_EVENT_SPEC = _EventTypeSpec(0x6B657962, 6)   # kEventClassKeyboard, kEventHotKeyPressed
```
(the comment token itself is `# kEventClassKeyboard, kEventHotKeyPressed`)

Was line 44 (above `_load_carbon`):
```
# Load Carbon CDLL with argtypes for GetEventTime/GetCurrentEventTime + hotkey registration calls
```

Was line 70 (above `_check_symbols_resolve`):
```
# Check 1: symbols resolve + GetCurrentEventTime is a plausible, monotonically-increasing double
```

Was line 79 (above `_register_probe_hotkey`):
```
# Check 2: register throwaway global hotkey, print live queue_delay_ms per press
```

Was line 113, trailing on a return statement (inside `_register_probe_hotkey`):
```
    return cb, hk_ref   # caller must keep alive (GC anchor)
```
(the comment token itself is `# caller must keep alive (GC anchor)`)

Was line 127, trailing on a statement (inside `main`):
```
    app._probe_cb, app._probe_hk_ref = _cb, _hk_ref   # GC anchor
```
(the comment token itself is `# GC anchor`)

## Salvage from dev/hotkey_latency/analyze_latency.py

Module docstring (was lines 1-14):
```
Parses menubar.log [latency] lines — main-thread tick phase breakdowns (app.py), background
discovery-worker cycle breakdowns (discovery_worker.py, 2026-08 M3: list_alive_sessions +
_scan_bg_sleep_timers moved off the main thread), hotkey queue-delays (hotkey_controller.py),
focus-path splits (system.py); see process-docs/hotkey_latency/ — into a distribution report:
per-phase stats, slowest entries with full breakdown, hotkey queue-delay percentiles, focus
lookup-vs-osascript split.

Usage (from project root):
    ./venv/bin/python3 dev/hotkey_latency/analyze_latency.py [path/to/menubar.log]

Default log path: menubar.menubar_log.MENUBAR_LOG (live APP_SUPPORT location).
Report written to dev/hotkey_latency/md/latency_report_<UTC-timestamp>.md.
```

Was line 27 (above the `menubar_log` import):
```
# From menubar_log.py: default live log location
```

Was lines 53-56 (above `_parse_latency_lines`):
```
# Parse menubar.log for [latency] lines; returns (ticks, bg_refreshes, hotkeys, focuses)
# ticks/bg_refreshes: [{'ts': str, 'total_ms': int, 'phases': {name: ms}}]
# hotkeys:  [{'ts': str, 'name': str, 'delay_ms': float}]
# focuses:  [{'ts': str, 'lookup_ms': float, 'osascript_ms': float, 'label': str}]
```

Was line 84 (above `_pct`):
```
# Nearest-rank percentile over a non-empty list of numbers
```

Was line 90 (above `_dist_line`):
```
# Distribution line: n, mean, median, p90, p95, max
```

Was lines 98-99 (above `_tick_like_section`):
```
# Markdown section for one tick-like series (main-thread tick OR bg-thread bg_refresh):
# total-duration distribution + per-phase distribution + slowest N entries with full breakdown
```

Was line 123 (above `_hotkey_section`):
```
# Markdown section: hotkey queue-delay percentiles, overall + per hotkey name
```

Was line 138 (above `_focus_section`):
```
# Markdown section: focus-path lookup vs osascript split
```

Was line 150 (above `_build_report`):
```
# Assemble full markdown report
```

## Salvage from dev/hotkey_latency/DOCS.md

No section, subsection, or bullet in the pre-rewrite `DOCS.md` fell outside the mandated format —
it already carried only Role / Modules (5-field, some fields honestly minimal) with no extra
subsections and no trailing Gotchas-style section. Nothing to cut here; this heading exists for
completeness of the walk. The rewrite adds the two sections the pre-rewrite version lacked
(`## Public Interface`, `## Flow`, `## State`) without removing any existing content.
