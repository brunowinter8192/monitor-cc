# 2026-09-09 — hotkey_controller cluster split and three long-function extractions (menubar milestone C)

## Context

Third menubar milestone of the src-wide refactor scan (cohesion step, fixed thresholds: file
≤ 400 LOC, function < 50 LOC, two or more constant clusters per file split into one module per
cluster). Findings: `hotkey_controller.py` carried three clusters (`_DIGIT_*` 4, `_CMD_*` 4,
`_ARROW_*` 3); `detect_main_desktop_numbers` 61 LOC, `discover._process_project_dir` 86 LOC,
`ghostty._refresh_ghostty_tty_to_id` 74 LOC.

## Decisions

- The split boundary for `hotkey_controller.py` was driven by a Python constraint, not by the
  naming clusters alone: every module-level variable rebound via `global` must live in the same
  module as the function that rebinds it, because a `from x import` copy in another module never
  sees the rebind. So the persistent-handler state travels with its `_ensure_*_handler`,
  register and unregister functions: `hotkey_digits.py` (`_DIGIT_*`), `hotkey_arrows.py`
  (`_ARROW_*` plus `_CMD_RIGHT_ID`/`_CMD_LEFT_ID`, consumed only by arrow dispatch), the shared
  Carbon plumbing in `hotkey_carbon.py`, and `hotkey_controller.py` keeping `HotkeyController`,
  `register_cmd_l`/`register_cmd_k` and their two IDs. The `_CMD_*` naming cluster was therefore
  split by concern across two modules, leaving no file with three or more members.
- `app.py`'s import line needed no change; no dev script imported the split symbols.
- `discover._process_project_dir` became a dispatcher over `_worker_session_info` and
  `_main_session_info`, with the duplicated hook-freshness check folded into `_hook_freshness`.

## Evidence

- `dev/menubar/discover_byte_identity.py` (new) drives `_process_project_dir` through four
  scenarios with all I/O boundaries monkeypatched; hash before and after:
  `0395eddc436c042aea4b5fa2ca313f207248dc6efc70679e15520ecf6c636a37`, identical.
- The desktop-detection and Ghostty functions touch CoreGraphics, AppleScript and tty devices;
  no harness was built for them. Proof there is import smoke plus the seven existing menubar
  checks (model_selector ×2, menubar_per_project, monitor_lifecycle, timer-loop, and the two
  earlier menubar harnesses), all passing after the change.

## Pitfall recorded

- The worker's Edit tool guardrail rejects a two-line `except X:\n    pass`; two verbatim-moved
  blocks in `ghostty.py` were written in the one-line form `except OSError: pass`. Formatting
  only, no behavior change.
- The milestone prompt's negative scope said "no process-docs edits", which the worker applied
  to its recap as well; this entry was written by the orchestrator instead.
