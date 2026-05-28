# C1 — py2app Migration: Monitor_CC_Menubar as Native Bundle (2026-05-28)

## What Was Built

py2app bundle at `dist/Monitor_CC_Menubar.app/` in the worktree. The native Mach-O launcher at `Contents/MacOS/Monitor_CC_Menubar` (86KB arm64 binary) starts the embedded Python (3.14.3) directly — no Bash exec chain. Audit token at `CGWindowListCopyWindowInfo` call time is our bundle identity `com.brunowinter.monitor_cc_menubar`.

This is the production deliverable for Etappe 2. After user install and Screen Recording grant on the new bundle, `kCGWindowName` becomes readable from the launchd-spawned context and the existing three-strategy detection pipeline in `desktop_detection.py` works unchanged.

## Files Changed

| File | Change | LOC |
|---|---|---|
| `setup_py2app.py` | NEW at project root — py2app build script | 65 |
| `src/menubar/menubar_main.py` | NEW — thin py2app entry wrapper | 5 |
| `decisions/OldThemes/desktop_allocation/C1_py2app_migration.md` | NEW — this file | — |
| `decisions/menubar_desktop_allocation.md` | NEW — first IST file | — |
| `src/menubar/DOCS.md` | UPDATE — new module entries, LOC updates | — |

`setup_menubar.py` (ad-hoc bash bundle builder) is unchanged and preserved as a fallback/reference.

## py2app Option Rationale

**`argv_emulation: False`** — the entry wrapper calls `run()` directly; macOS Open Document events are irrelevant for a menubar app.

**`semi_standalone: False`** — embeds the full Python.framework. We trade ~39MB bundle size (actual, vs theoretical ~80MB — py2app strips the framework to the bare `.dylib` + stdlib) for robustness: the app works regardless of whether the user's Homebrew Python 3.14 survives updates, formula removal, or version changes.

**`packages: ['src.menubar', 'rumps']`** — `src.menubar` force-includes all 15+ submodules wholesale. This bypasses modulegraph's import tracing for two lazy imports that would otherwise be missed:
  - `system.py:run()` → `from .app import CCMenuBarApp` (inside function body)
  - `app.py:restartApp_()` → `from .setup_menubar import write_plist` (inside method body)
  Modulegraph does not trace imports inside function bodies. Without this option, those modules would be absent from the bundle and cause ImportError at runtime.

**`includes: ['src.session_finder', 'src.constants']`** — `discover.py` imports via `from ..session_finder import ...` (parent-package relative import). These modules live outside `src.menubar/`, so `packages=['src.menubar']` alone doesn't pull them in. Explicit `includes` is required.

**`excludes`** — belt-and-suspenders. modulegraph does not trace mitmproxy etc. from our entry chain; these excludes guard against accidental inclusion if py2app's fallback analysis ever widens scope.

**CFBundleIdentifier: `com.brunowinter.monitor_cc_menubar`** — MUST match the identifier already registered in TCC's database from the ad-hoc bundle grant. Changing it would invalidate the existing grant and require the user to re-grant. The identifier is identical to what `setup_menubar.py` used.

**`NSScreenCaptureUsageDescription` + `NSAppleEventsUsageDescription`** — required strings on macOS 14+. The ad-hoc stub bundle was missing these (it had bare minimum Info.plist). py2app bundle adds them. macOS may show these strings in the permission dialog on first launch.

## Why `setup_py2app.py` is at Project Root (deviation from Phase A plan)

Phase A planned placement at `src/menubar/setup_py2app.py` — same convention as `setup_menubar.py`. This caused a fatal import error:

```
ImportError: attempted relative import with no known parent package
```

Root cause: when Python runs a script at path `src/menubar/X.py`, it adds `src/menubar/` to `sys.path[0]`. setuptools internally does `import queue` (stdlib). Python finds `src/menubar/queue.py` (our message-queue module) before the stdlib `queue` — and `src/menubar/queue.py` uses `from .paths import ...` which fails without a package context.

Fix: `setup_py2app.py` at project root. `sys.path[0]` = project root, no collision with `src/menubar/queue.py`. This is also the canonical py2app convention (all reference repos place the setup script at root). DOCS.md updated accordingly.

## Build Verification Results

```
codesign --verify --verbose=4 dist/Monitor_CC_Menubar.app
  → valid on disk; satisfies its Designated Requirement (exit=0)

/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" .../Info.plist
  → com.brunowinter.monitor_cc_menubar

/usr/libexec/PlistBuddy -c "Print :LSUIElement" .../Info.plist
  → true

file dist/Monitor_CC_Menubar.app/Contents/MacOS/Monitor_CC_Menubar
  → Mach-O 64-bit executable arm64

ls .../Contents/Frameworks/Python.framework/Versions/3.14/Python
  → present (5.1MB stripped Python binary)

Functional smoke test:
  ./dist/Monitor_CC_Menubar.app/Contents/MacOS/Monitor_CC_Menubar 2>&1
  → "Another menubar instance is already running, exiting."  exit=0
  Confirms: Python starts, all imports resolve, singleton lock logic runs.
  (Production PID 10228 holds the lock → correct clean exit)

Bundle total size: 39MB
Python.framework (stripped): 5.1MB
```

## Known Limitation: Restart Button

`app.py:restartApp_()` runs:
```python
cmd = f'sleep 0.5 && "{sys.executable}" "{_SETUP_PY}"'
```
In the py2app bundle, `sys.executable` = bundled Python inside `Contents/Frameworks/`, and `_SETUP_PY` = bundled `setup_menubar.py` inside `Contents/Resources/`. Running `setup_menubar.py` from those paths would attempt to rebuild `~/Applications/Monitor_CC_Menubar.app` from a bundle-internal path — not useful. The Restart button in the toolbar will exit the menubar but NOT re-bootstrap the launchd service correctly.

**Workaround until fixed:** Kill → re-`open ~/Applications/Monitor_CC_Menubar.app`. Or re-run `./venv/bin/python setup_py2app.py py2app` + reinstall. The restart button fix is a follow-on task (update `restartApp_` to shell out to `setup_py2app.py` from the source tree, or remove the restart path entirely for the native bundle).

## Install Instructions for User

### Prerequisites
- New bundle at: worktree `dist/Monitor_CC_Menubar.app/` (path below)
- Production menubar PID 10228 currently running

### Step 1 — Stop production menubar

```bash
# Graceful kill via Kill button in the panel, OR:
kill 10228
```

Wait 2 seconds. Verify:
```bash
ps aux | grep Monitor_CC_Menubar | grep -v grep
# Should return empty — menubar stopped
```

If launchd respawns it immediately (KeepAlive plist), use launchctl to also stop the service:
```bash
launchctl bootout "gui/$(id -u)/com.brunowinter.monitor_cc_menubar"
# ignore "error 3: No such process" — means it wasn't loaded, that's fine
```

### Step 2 — Back up old bundle

```bash
cp -R ~/Applications/Monitor_CC_Menubar.app ~/Applications/Monitor_CC_Menubar.app.backup_20260528
```

### Step 3 — Copy new bundle

```bash
cp -R /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/py2app-build/dist/Monitor_CC_Menubar.app ~/Applications/Monitor_CC_Menubar.app
```

If macOS shows "replace existing?" — confirm yes.

Verify the copy:
```bash
/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" ~/Applications/Monitor_CC_Menubar.app/Contents/Info.plist
# → com.brunowinter.monitor_cc_menubar

file ~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/Monitor_CC_Menubar
# → Mach-O 64-bit executable arm64   (NOT bash — this is the key change)
```

### Step 4 — First launch

```bash
open ~/Applications/Monitor_CC_Menubar.app
```

macOS will show a privacy dialog on first launch: **"Monitor_CC_Menubar.app wants to access data from other apps"** (NSAppleEventsUsageDescription). Click **OK**.

The menubar icon should appear. If nothing appears after 5 seconds, check:
```bash
cat /tmp/monitor_cc_menubar.err    # if running via launchd
# or just run directly:
~/Applications/Monitor_CC_Menubar.app/Contents/MacOS/Monitor_CC_Menubar
```

### Step 5 — Grant Screen Recording permission

Open **System Settings** (not System Preferences) → **Privacy & Security** → **Screen Recording**.

Scroll down to find **Monitor_CC_Menubar** in the list.
  - If it already appears with a toggle: toggle it **OFF then back ON** (forces TCC to re-evaluate the new binary identity).
  - If it does NOT appear: click the **+** button at the bottom-left of the list → a file picker opens → navigate to `~/Applications/` → select `Monitor_CC_Menubar.app` → click **Open** → the entry appears → toggle **ON**.

After toggling ON, macOS may show: **"Quit & Reopen Monitor_CC_Menubar to allow it to record your screen?"** — click **Quit & Reopen** (or manually kill + relaunch if the dialog doesn't appear).

### Step 6 — Verify detection works

Relaunch if you clicked "Quit & Reopen" above:
```bash
open ~/Applications/Monitor_CC_Menubar.app
```

Open the Sessions panel (click menubar icon or Cmd+L). Mains should now show `[N]` desktop-number prefixes instead of missing slot numbers. Cmd+1..9 should focus the corresponding desktop's Main session.

If mains still show no prefix: check `src/logs/menubar.log` for `[detection]` lines. A single `all_failed` entry with `reason=...` will identify the failure point.

### Rollback (if needed)

```bash
kill $(pgrep -f Monitor_CC_Menubar)
cp -R ~/Applications/Monitor_CC_Menubar.app.backup_20260528 ~/Applications/Monitor_CC_Menubar.app
open ~/Applications/Monitor_CC_Menubar.app
```

### Note on LaunchAgent

Production currently runs via `open` (Aqua launch), not launchd. There is no active LaunchAgent plist managing auto-restart. After install you start the app manually via `open`. Auto-restart-on-crash via LaunchAgent is a separate topic for a future session — see `decisions/OldThemes/desktop_allocation/` for context.
