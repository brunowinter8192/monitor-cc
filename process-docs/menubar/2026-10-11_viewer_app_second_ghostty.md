# Menubar lookup of a second Ghostty process: the worker viewer app (2026-10-11)

## Why the menubar changed

iterative-dev now opens each worker's viewer window in a separate Ghostty process (a patched copy of `Ghostty.app`, bundle id `com.brunowinter.ghostty-viewer`, installed at `~/Library/Application Support/iterative-dev/GhosttyViewer.app`). The reason is outside this repo: every window the main Ghostty creates calls `NSApp.activate(ignoringOtherApps: true)`, so a viewer window in the main process always steals focus. The copy swallows those calls with an injected shim. Details and measurements live in the iterative-dev process-docs, area `worker_spawn`.

For the menubar this means a worker's `tmux attach` client tty is a child of the viewer process, not of the main Ghostty. Before the change `_ghostty_pid` only knew the main process, so the tty stayed unmapped and a worker row click logged `NO-OP reason=tty_unmapped`.

## What changed

- `ghostty.py` holds a `GhosttyApp` tuple per known app (`GHOSTTY_MAIN`, `GHOSTTY_VIEWER`): process-command marker, AppleScript target, bundle id, and whether the app must be activated from outside. `_refresh_ghostty_tty_to_id` runs the OSC2 marker probe once per running app, with the AppleScript target of that app, and records which app owns each tty (`_ghostty_tty_to_app`, next to `_ghostty_tty_to_id`).
- The marker for the main process is `Ghostty.app/Contents/MacOS`. The viewer's path contains `GhosttyViewer.app/Contents/MacOS`, which does not contain that string, so the two never collide (pinned by `dev/menubar/test_ghostty_viewer_app.py`).
- `system.py` `_focus_terminal_by_id(term_id, app)` sends `focus terminal id` to the owning app. For the viewer app it then runs `open -b com.brunowinter.ghostty-viewer`. Reason: the shim also swallows AppleScript's `activate` (it arrives as `activateIgnoringOtherApps:`), so activation has to come from LaunchServices outside the process. A row click is a user action, so activation is intended there.
- Session rows (main windows by cwd) are untouched.

## Coupling to remember

The bundle id string `com.brunowinter.ghostty-viewer` exists in two repos: `GHOSTTY_VIEWER` here and `_VIEWER_APP_ID` in iterative-dev `src/spawn/viewer_app.sh`. There is no shared module across the repos.

## Removing it once upstream stops activating on AppleScript `new window`

1. Delete the `GHOSTTY_VIEWER` tuple and its entry in `_GHOSTTY_APPS`.
2. Remove the `activate_from_outside` field and `_activate_bundle_from_outside` in `system.py`; `_focus_terminal_by_id` goes back to taking only the terminal id (the `tell` target becomes `application "Ghostty"` again).
3. Delete `dev/menubar/test_ghostty_viewer_app.py`; revert the `_app_pid(app)` signature changes in `dev/menubar/p5_g6_caches.py`.
The multi-app loop in `_refresh_ghostty_tty_to_id` can stay; with one entry in `_GHOSTTY_APPS` it behaves like the old single-app flow.

## Verification

Hermetic: `dev/menubar/test_ghostty_viewer_app.py` (13 checks) and `dev/menubar/p5_run_all.py` (all groups exit 0) on 2026-10-11. The live row-click check (viewer window comes to the front, terminal focused) is a separate live run recorded in the iterative-dev process-docs.
