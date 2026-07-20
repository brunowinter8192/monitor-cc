# menubar_bundle_rename — Naming Unification for menubar bundle/ID/runtime

## What was done

Two independent problems addressed together (they share the same root: the project rename `Monitor_CC` → `monitor-cc` was applied to paths and session_finder but not to the menubar bundle identifiers).

---

## Part 1 — discover.py Case-Sensitivity Bug ("No active sessions")

### Root Cause

`_proc_cwd_for_encoded_dir()` in `src/menubar/discover.py` compared encoded paths case-sensitively:

```python
if encode_project_path(proc_cwd) == encoded_dir:
```

After the project rename, the live CC process cwd is `/Users/.../monitor-cc` (lowercase). `encode_project_path` yields `-Users-...-monitor-cc`. But `~/.claude/projects/` contains the dir `-Users-...-Monitor-CC` (capital M and CC) — macOS case-insensitive FS never physically renamed the dir; the old case survived. The case-sensitive `==` never matched → every Main session `_proc_cwd_for_encoded_dir` returned `None` → menubar showed "No active sessions".

### Evidence

- `list_alive_sessions()` returned count 0 on a known-running session.
- Manual inspection: `encode_project_path(proc_cwd)` = `-Users-...-monitor-cc`; `~/.claude/projects/` dirname = `-Users-...-Monitor-CC`. Case mismatch confirmed. `.lower()` on both = identical strings.

### Fix

Applied `.lower()` on both sides in `_proc_cwd_for_encoded_dir`:

```python
if encode_project_path(proc_cwd).lower() == encoded_dir.lower():
```

Same pattern already used in `matches_project_filter()` (`src/session_finder.py`) — established convention for case-insensitive macOS FS path comparisons.

---

## Part 2 — Full Bundle/ID Naming Consistency Pass

### Why

After the project rename, the menubar bundle identifiers remained `monitor_cc_menubar` (underscores) while everything else moved to `monitor-cc` (hyphens). Inconsistency surface:
- Bundle ID / launchd label: `com.brunowinter.monitor_cc_menubar`
- App bundle: `Monitor_CC_Menubar.app`
- CFBundleName / py2app `name=`: `Monitor_CC_Menubar`
- APP_SUPPORT dir: `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/`
- Plist template filename: `com.brunowinter.monitor_cc_menubar.plist`

### Final naming strings

| Identifier | Old | New |
|---|---|---|
| Bundle ID / launchd label | `com.brunowinter.monitor_cc_menubar` | `com.brunowinter.monitor-cc-menubar` |
| App bundle | `Monitor_CC_Menubar.app` | `monitor-cc-menubar.app` |
| CFBundleName | `Monitor_CC_Menubar` | `monitor-cc-menubar` |
| py2app `name=` / CFBundleExecutable | `Monitor_CC_Menubar` | `monitor-cc-menubar` |
| APP_SUPPORT dir | `com.brunowinter.monitor_cc_menubar/` | `com.brunowinter.monitor-cc-menubar/` |
| Plist template | `com.brunowinter.monitor_cc_menubar.plist` | `com.brunowinter.monitor-cc-menubar.plist` |

### Touch points

| File | Change |
|---|---|
| `src/menubar/paths.py` | `_APP_SUPPORT` string; added `_migrate_from_old_bundle_id()` |
| `src/menubar/ghostty.py` | Removed inline `_APP_SUPPORT`; added `from .paths import _APP_SUPPORT` |
| `src/menubar/hook_writer.py` | Updated inline `_APP_SUPPORT` string (standalone script — can't use relative import) |
| `src/menubar/system.py` | `_LAUNCHD_LABEL`; `/tmp/monitor-cc-menubar_focus.log` |
| `src/menubar/app.py` | Two `label =` strings in `killApp_` / `restartApp_` |
| `src/menubar/setup_menubar.py` | `_LABEL`, `_BUNDLE`, `_BUNDLE_EXE`, CFBundleName in `_write_info_plist`, error msg |
| `src/menubar/com.brunowinter.monitor-cc-menubar.plist` | Renamed (git mv); Label, comment, stdio paths |
| `setup_py2app.py` | Plist data-file ref, `CFBundleIdentifier`, `CFBundleName`, `name=`, comments, `_prune_bundle_bloat` path |
| `src/menubar/menubar_log.py` | Comment only |

### APP_SUPPORT migration rationale

On first import after upgrade, `paths.py` runs `_migrate_from_old_bundle_id()`:
- Checks if `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/` exists
- For each known runtime file (settings.json, hooks.json, hooks.lock, msg_queue.json, queue.lock, ghostty_cwd_uuid.json, orchestrator_signals.json, menubar.pid, menubar.log, cwd_desktop.json): moves old → new if old exists AND new does not (no clobber)
- Idempotent: no-op if old dir absent or all files already migrated

### ghostty.py cycle claim (corrected)

The pre-existing comment in `ghostty.py` stated: "can't import paths.py — would create paths→proc_cache→ghostty→paths cycle." This is incorrect: `paths.py` imports only `pathlib`, so no menubar-package cycle exists. The inline `_APP_SUPPORT` was simply never updated to import from paths when the paths module was created. Fixed: removed inline definition + cycle comment; added `from .paths import _APP_SUPPORT`.

`hook_writer.py` genuinely cannot use a relative import — it is invoked standalone via `python3 /abs/path/hook_writer.py` by the CC hook system. Its `_APP_SUPPORT` stays inline and is kept in sync manually.
