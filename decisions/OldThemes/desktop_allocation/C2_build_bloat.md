# C2 — Build Bloat: 15 GB Bundle from Main Repo

## Root Cause

`./venv/bin/python setup_py2app.py py2app` produces a 15 GB bundle when built from the main
repo (vs 39 MB from a fresh worktree with no runtime data).

**Mechanism:** `src/__init__.py` exists → py2app's modulegraph registers `src` as a `Package`
node → `build_app.py:copy_package_data(src)` iterates `listdir(src/)`. For each entry that is
NOT a Python package (no `__init__.py`), it calls `copy_tree(entry, dest)` wholesale.

`src/logs/` is a runtime log directory (gitignored, no `__init__.py`). In the main repo it
accumulates proxy API request logs and menubar logs reaching ≥15 GB. `copy_package_data` has no
awareness of this and copies all of it into the bundle.

Verified in `venv/lib/python3.14/site-packages/py2app/build_app.py:copy_package_data()` (~lines
1763–1830): gate is `for p in listdir(pth): if p.startswith("__init__.") ... break / else:
copy_tree(...)`.

## Why `packages`/`includes` Rewriting Doesn't Fix It

Changing `packages=['src.menubar']` vs `includes=['src.menubar']` does not help. `src` remains
a registered `Package` node regardless of how `src.menubar` is declared — py2app's module graph
traces the package hierarchy, not just the explicitly listed subpackages. Once `src` is a
`Package`, `copy_package_data(src)` sweeps all its non-package subdirs. No config-level option
suppresses `copy_package_data` for a parent package.

## The Fix: Whitelist Post-Build Prune

After `setup()` returns, `_prune_bundle_bloat()` iterates the bundle's `src/` copy and removes
everything not in `_BUNDLE_SRC_KEEP`. Whitelist (NOT blacklist — robust against future data dirs
being added to `src/`):

```python
_BUNDLE_SRC_KEEP = {'menubar', 'session_finder.py', 'constants.py', '__init__.py', '__pycache__'}
```

Whitelist derivation:
- `menubar/` — the app package
- `session_finder.py` — `discover.py:from ..session_finder import ...`
- `constants.py` — `session_finder.py:from .constants import ...` (transitive)
- `__init__.py` / `__pycache__` — package infrastructure

Grep confirmed no other cross-package `src.X` imports from `src/menubar/`.

## Sentinel Verification (2026-05-28, worktree `bloat-fix`)

```
mkdir -p src/logs && dd if=/dev/zero of=src/logs/SENTINEL_BIG.jsonl bs=1m count=50
./venv/bin/python setup_py2app.py py2app
```

Build output (last lines):
```
Done!
  pruned from bundle src/: DOCS.md, ccwrap, claude_proxy_start.sh, core, format, gpu_pane,
  hooks, input, jsonl, logs, metadata, panes, proxy, proxy_addon.py, proxy_display, ram_audit,
  startup.py, tmux_launcher.py, utils.py, workers
```

Verification:
```
ls .../src/logs/   → No such file or directory    ✅ sentinel pruned
ls .../src/        → __init__.py constants.py menubar session_finder.py   ✅ survivors correct
du -sh dist/...    → 38M   ✅ lean (was 15 GB+ from main repo)
file .../MacOS/... → Mach-O 64-bit executable arm64   ✅ binary intact
```

Build-from-main-repo is now safe.
