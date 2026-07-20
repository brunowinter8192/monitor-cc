# File-Open Routing — CotEditor for .md/.txt (2026-05-27)

## Scope

The `show <file>` tool (a wrapper script under `~/.local/bin/show`, source: `Meta/blank/bin/show`) is the central path for opening files for the user — from the menubar, from workers, from Opus. At the time it blindly delegated to macOS `open`, which picks the default handler by file type (Preview for PDF/PNG, TextEdit for txt, Xcode for py, etc.).

The user wants file-type routing: `.md` and `.txt` ALWAYS in **CotEditor**, other types unchanged at the default.

## State (before this change)

`~/.local/bin/show` (symlink → `/Users/brunowinter2000/Documents/ai/Meta/blank/bin/show`):

```bash
for f in "$@"; do
  f="${f/#\~/$HOME}"
  [[ "$f" != /* ]] && f="$(pwd)/$f"
  [ ! -e "$f" ] && { echo "show: not found: $f" >&2; exit 1; }
  open "$f"
  echo "opened: $f"
done
```

No file-type routing. No desktop awareness.

## Implementation (2026-05-27, Meta/blank/ commit cfd0d14)

**Extension routing in `Meta/blank/bin/show`:**
- `.md` / `.markdown` / `.txt` → `open -a "CotEditor" "$f"` (case-insensitive extension check via `tr '[:upper:]' '[:lower:]'`)
- Everything else → the existing `open "$f"` (macOS default handler)

**Desktop awareness implemented alongside** (no longer deferred to a later stage):
- After `open`, the script calls `python3 desktop_targeting.py wait-and-move "$PPID" "<app_name>" 4` in the background
- The helper finds the caller's main session via a parent-PID walk to the nearest `claude` ancestor → its cwd via lsof → lookup in Monitor_CC's `ghostty_cwd_uuid.json` → AppleScript window name → CGWindowList match → space ID via `CGSCopySpacesForWindows`
- Snapshots the target app's existing windows + polls 4s for a new window → `CGSMoveWindowsToManagedSpace` to the caller's space ID
- Best-effort: failure is silent (the file still opens, it just lands on the active desktop instead of the target)
- For unknown app handlers (everything except .md/.txt), show passes `app_name=""` → the helper polls cross-app (excluding system apps Dock/WindowServer/etc.)

**Helper module:** `Meta/blank/src/desktop/desktop_targeting.py` (CGS bridging extracted from Monitor_CC's `dev/desktop_detection/01_probe.py`, plus `CGSMoveWindowsToManagedSpace` for the move action).

**Verified installed:**
- `/Applications/CotEditor.app`
- `/opt/homebrew/bin/cot` (CLI shim)

## Pending (at the time)

- A live test once `plugin-publish` had run (commit `cfd0d14` was local, the plugin cache still had the old version)
- Cross-app polling risk: if an unrelated app window (e.g. a notification) appears during the 4s polling window, it gets incorrectly moved along. Low probability, accepted for the time being

## Sources

- `/Users/brunowinter2000/.local/bin/show` (symlink)
- `/Users/brunowinter2000/Documents/ai/Meta/blank/bin/show` (source)
- `/Applications/CotEditor.app` (editor)
- `/opt/homebrew/bin/cot` (CLI shim, in case it's preferable to `open -a`)
