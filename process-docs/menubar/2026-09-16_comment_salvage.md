# 2026-09-16 — Comment/docstring salvage for dev/menubar/ standards conformance

## Context for whoever picks this up

Milestone: bring `dev/menubar/` (3 `.py` files, 590 LOC) into conformance with the project's
three-marker comment standard. Every comment and docstring below was relocated here verbatim
before deletion from the code. Zero `__doc__`/`argparse` hits, so all 3 module docstrings found
here were deleted outright — none were load-bearing.

**Menubar-safety note for whoever re-verifies this directory later:** all 3 scripts here construct
real AppKit objects (`NSPanel`, `NSGridView`, subviews) but NEVER call anything that shows a window
or touches the real running menubar app process. I grepped `src/menubar/model_controller.py`,
`src/menubar/model_panel_ui.py`, and `src/menubar/panel_manager.py` (the modules these two AppKit
harnesses exercise) for `orderFront`, `orderFrontRegardless`, `makeKeyAndOrderFront`, and
`setIsVisible_` — zero hits in any of the three. The only `orderFrontRegardless()` calls in all of
`src/menubar/` live in `panel_lifecycle.py`, which none of these three files (nor
`model_controller.py`/`panel_manager.py` themselves) import. Confirmed safe to run in this
worktree: all three ran to completion with real (non-SKIPPED) hashes, no headless-AppKit fallback
needed in this environment. `panel_manager_byte_identity.py`'s hash
(`0efc9d390506a6e17c5b33958074e44d6ae5831ddd898ae82c9bd8b008876d42`) matched the baseline hash its
own (now-salvaged) docstring records from the original milestone B split — confirms this
environment's headless AppKit behavior is consistent with whatever environment recorded that
baseline.

---

## Salvage from dev/menubar/discover_byte_identity.py

Module docstring (was lines 1-26):
```
Byte-identity harness for src/menubar/discover.py:_process_project_dir (menubar milestone C:
86-LOC function extraction into _worker_session_info/_main_session_info/_hook_freshness).

Monkeypatches every I/O boundary the function touches (_newest_jsonl, _has_active_bg,
_read_hook_state, _cwd_from_jsonl, _worker_tmux_session, _tmux_session_exists,
_tmux_window_activity, _proc_cwd_for_encoded_dir, _proxy_log_newest_mtime) with deterministic
fakes, drives 4 scenarios through the real, unmocked _process_project_dir/_classify_encoded_dir/
_decode_dir_name logic, and hashes the resulting SessionInfo tuples:

1. worker_fresh_working_stale_activity: worker in a worktree, hook fresh + 'working', tmux window
   activity stale (> WORKING_THRESHOLD_SECS) -> crash-safety demote to 'idle'.
2. worker_no_worktree_old_mtime: worker branch, cwd unresolvable, JSONL older than
   ALIVE_WINDOW_SECS -> alive guard fails, returns None.
3. main_fresh_hook: main session, hook fresh + 'working' -> status taken directly from hook.
4. main_idle_proxy_override: main session, no hook, JSONL says idle, but a newer proxy-log mtime
   within THINKING_OVERRIDE_MAX_SECS overrides status to 'working'.

Usage (from project root):
    ./venv/bin/python dev/menubar/discover_byte_identity.py

Prints one HASH line. Run before and after a change to _process_project_dir; both must match.
No harness needed for detect_main_desktop_numbers / _refresh_ghostty_tty_to_id (Ghostty/
CoreGraphics/tty I/O, no clean seam) — see this milestone's recap for the import-smoke +
caller-check rationale instead.
```

Was lines 51-53 (above `_import_discover`):
```
# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src); discover.py's package-relative imports only resolve when
# loaded as part of the src.menubar package anyway.
```

Was line 83, trailing on a statement (inside `_scenario_worker_fresh_working_stale_activity`):
```
        tmux_window_activity=_NOW - 999,   # stale: now - wa = 999 > WORKING_THRESHOLD_SECS
```
(the comment token itself is `# stale: now - wa = 999 > WORKING_THRESHOLD_SECS`)

Was line 92, trailing on a statement (inside `_scenario_worker_no_worktree_old_mtime`):
```
        jsonl=_FakeJsonl('sess-w2', _NOW - 999999),   # far older than ALIVE_WINDOW_SECS
```
(the comment token itself is `# far older than ALIVE_WINDOW_SECS`)

Was line 115, trailing on a statement (inside `_scenario_main_idle_proxy_override`):
```
        jsonl=_FakeJsonl('sess-m2', _NOW - 999),   # older than WORKING_THRESHOLD_SECS -> JSONL idle
```
(the comment token itself is `# older than WORKING_THRESHOLD_SECS -> JSONL idle`)

Was line 119, trailing on a statement (same function):
```
        proxy_mtime=_NOW - 100,   # newer than mtime, within THINKING_OVERRIDE_MAX_SECS
```
(the comment token itself is `# newer than mtime, within THINKING_OVERRIDE_MAX_SECS`)

Was lines 130-132 (above `_install_fakes`):
```
# Replaces every I/O-boundary name on the live module object with a scenario-backed fake;
# returns the originals for restoration. discover.py's own functions resolve these names as
# module globals at call time, so reassigning the attribute redirects every internal caller.
```

## Salvage from dev/menubar/model_controller_byte_identity.py

Module docstring (was lines 1-24):
```
Byte-identity harness for src/menubar/model_controller.py (menubar milestone A: persistence +
NSPanel-construction concern split into sibling modules).

(1) Persistence: MODEL_SELECTION_FILE/PROXY_RULES_FILE redirected to temp copies (rules file
seeded from a copy of the real ~/.claude/shared-rules/proxy_rules.json if present, else a
synthetic minimal fixture) — load, cycle main/worker model/effort/max_tokens through a fixed
sequence, write; hashes both written files' raw bytes.
(2) UI: instantiates ModelController with a minimal fake app (settings = a SimpleNamespace with
panel_width/panel_min_height/auto_focus, per menubar milestone B's PanelSettings split;
_panel_controller = a plain NSObject subclass instance), calls open() then each
handle_cycle_* once, dumping every arranged subview's class/frame/title/attributedTitle/tag/action
after each step; hashes the dump. Does NOT call handle_apply — that writes the REAL shared-rules
files, and this harness must never touch them; open()/handle_cycle_* are read-only with respect to
the real files (a cycle click only re-reads model_params for the newly-selected model, nothing is
written until Apply).

Usage (from project root):
    ./venv/bin/python dev/menubar/model_controller_byte_identity.py

Prints two lines: PERSISTENCE_HASH and UI_HASH. Run before and after the split; both must match.
If AppKit refuses headless view creation, UI_HASH reports SKIPPED with the reason and an
import + open() smoke check runs instead.
```

Was lines 64-66 (above `_import_model_controller`):
```
# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src); model_controller.py's package-relative imports only resolve
# when loaded as part of the src.menubar package anyway.
```

Was lines 71-74 (above `_import_model_selection`):
```
# Loaded via importlib, same reason as _import_model_controller. (2026-09, menubar milestone A:
# every persistence function this harness drives — load/cycle/write — moved out of
# model_controller.py into this pure module; the harness's own import target was updated in the
# same commit as the split, exactly like every other symbol move this milestone.)
```

Was lines 79-81 (above `_hash_persistence`):
```
# Redirect MODEL_SELECTION_FILE/PROXY_RULES_FILE to temp copies via each function's own path=
# parameter (no monkeypatching needed); load -> fixed cycle sequence -> write; hash both written
# files' raw bytes.
```

Was line 124 (above `_safe_call`):
```
# Call obj.method_name() if the method exists; None if absent or if the call itself raises.
```

Was lines 134-135 (above `_dump_subviews`):
```
# Dump class/frame/title/attributedTitle/tag/action for every arranged subview, as a stable
# JSON-serialized bytes blob.
```

Was lines 183-184 (above `_smoke_import_and_open`):
```
# Fallback when headless AppKit view creation fails: import already succeeded (main() got this
# far), so just prove open() doesn't raise.
```

## Salvage from dev/menubar/panel_manager_byte_identity.py

Module docstring (was lines 1-27):
```
Byte-identity harness for src/menubar/panel_manager.py (menubar milestone B: PanelManager
class-attribute split + _rebuild_inner helper extraction).

Constructs PanelManager with a minimal fake app (settings + a real NSObject _panel_controller),
calls rebuild(sessions, bg_by_project) with a synthetic 3-project session list (one project with
two mains sharing a desktop number -> conflict; one with a worker; one with a bg timer and a main
with desktop_no=None), dumps the full NSGridView contents (per cell: class, title string, tag,
action, color description, row height) plus every lookup map, hashes. Then calls update_inplace
with one session's status flipped and extends the hash. Run before and after a change; both
hashes must match.

Targets PanelManager's post-split attribute layout (menubar milestone B): `_widgets` (a
_PanelWidgets: panel/stack/quit_btn/toggle_btn/kill_btn) and `_lookups` (a _PanelLookups: the 6
per-rebuild maps) replace the 11 flat attrs the pre-split PanelManager carried; the fake app
exposes `.settings` (panel_width/panel_min_height/auto_focus) instead of the 3 flat attrs
PanelManager used to read directly off `app`. Baseline hash captured against the pre-split
layout was 0efc9d390506a6e17c5b33958074e44d6ae5831ddd898ae82c9bd8b008876d42 — this file's own
accessor code was updated in the same commit as the split, mirroring
dev/menubar/model_controller_byte_identity.py's import-target update pattern from milestone A.

Usage (from project root):
    ./venv/bin/python dev/menubar/panel_manager_byte_identity.py

Prints one HASH line. If AppKit refuses headless NSGridView introspection, reports SKIPPED with
the reason and falls back to an import + rebuild() smoke check.
```

Was lines 60-62 (above `_import_panel_manager`):
```
# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src); panel_manager.py's package-relative imports only resolve
# when loaded as part of the src.menubar package anyway.
```

Was lines 71-73 (above `_make_sessions`):
```
# 3 projects: alpha has two mains sharing desktop_no=2 (conflict -> "[!2]" red rendering); beta
# has one main + one worker (worker row, clickable); gamma has one main with desktop_no=None
# (no slot prefix) and carries the bg timer (badge + abort button on its separator row).
```

Was lines 98-99 (above `_FakeApp`):
```
# PanelManager reads app.settings.panel_width / .panel_min_height / .auto_focus and
# app._panel_controller (post-milestone-B layout).
```

Was lines 145-147 (above `_dump_stack`):
```
# Walks every arranged subview of the stack; for the one NSGridView among them, dumps every
# row/cell (class/title/tag/action/color/height); everything else (separator, header label) dumps
# by class name + frame only.
```

## Salvage from dev/menubar/DOCS.md

The pre-rewrite `DOCS.md` carried two extra sub-bullets under module entries that don't fit the
mandated 5-field-only per-module format (Purpose/Reads/Writes/Called by/Calls out), plus a
trailing `## Gotchas` section that has no place in the mandated top-level format (Role / Public
Interface / Flow / Modules / State only). All three cut verbatim:

Under `model_controller_byte_identity.py`:
```
**Determinism note:** the UI check's `open()` reads the REAL `MODEL_SELECTION_FILE`/
`PROXY_RULES_FILE` (no override seam for that code path in production) — the before/after
comparison only holds if those files don't change between the two runs (nobody clicks Apply on a
live menubar in between). The UI check itself never writes.
```

Under `panel_manager_byte_identity.py`:
```
**Gotcha:** this harness's accessor code targets `PanelManager`'s CURRENT internal attribute
layout (`_widgets`/`_lookups`) — a future attribute rename requires updating the accessor code
here first, or the hash comparison silently breaks instead of catching a real regression.
```

Trailing section:
```
## Gotchas

**`detect_main_desktop_numbers` (`desktop_detection.py`) and `_refresh_ghostty_tty_to_id`
(`ghostty.py`) have no byte-identity harness in this directory.** Both call CGS/AppleScript/tty
I/O with no clean monkeypatch seam comparable to `discover.py`'s plain-function boundaries (CGS is
`ctypes` CDLL calls, not overridable Python names) — only import-smoke coverage plus
`discover.py:list_alive_sessions`'s own caller check exist for these two functions.
```

This content is preserved here in full; it is not carried into the rewritten DOCS.md.
