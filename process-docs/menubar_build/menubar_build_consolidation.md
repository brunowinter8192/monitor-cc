# Menubar Build Consolidated — One Canonical py2app Install (2026-06-12)

## Starting Confusion

There were TWO build paths for the menubar, which at deploy time led to a running
**python process** instead of a compiled binary:

- `setup_py2app.py` (project root) — a real py2app compile → native Mach-O, embedded Python.
  The CANONICAL path (DOCS: "replaces the Bash-exec chain").
- `src/menubar/setup_menubar.py` — LEGACY: a thin Bash launcher that starts `workflow.py` via
  python (`exec venv/python workflow.py --mode menubar`). DOCS: "superseded by setup_py2app.py".

At deploy time the legacy path was accidentally run → `.app` = Bash launcher → python process
(instead of a self-contained binary). That was the "confusion."

## Footgun (history in the menubar-restart-broken topic)

`app.py:restartApp_`'s dev branch called `python setup_menubar.py` → `setup_menubar_workflow()` →
`_build_app_bundle()` → overwrote the Info.plist of an installed py2app bundle → corruption.

## Install-Orchestration Gap (discovered during the refactor)

`setup_menubar_workflow()` did build + codesign + write_plist + bootout + bootstrap in ONE step.
Simply removing the legacy pipeline would have left the install orchestration (plist + bootstrap)
homeless — `setup_py2app.py` only built (`dist/`), it didn't install (DOCS: "user copies
manually"). This gap was closed in the refactor (see decision 3).

## Decision

1. **`setup_menubar.py` → a pure plist-helper module** (143 → 30 LOC): only the 8 constants +
   `write_plist()`/`write_plist_py2app()` (needed by `restartApp_`). The legacy build pipeline
   (`setup_menubar_workflow`, `_build_app_bundle`, `_write_launcher`, `_codesign_bundle`, `_bootout`,
   `_bootstrap`, the `__main__` guard) removed.
2. **Footgun defused**: the dev-restart branch in `restartApp_` now uses the same pure
   launchctl cycle as the py2app branch — no more bundle rebuild possible from `setup_menubar.py`.
3. **`setup_py2app.py` made into the ONE complete install**: after the build, `_install_bundle()`
   runs (a post-setup hook alongside `_prune_bundle_bloat`) → rmtree+copytree to `~/Applications`, ad-hoc
   codesign, inline plist (native binary), launchctl bootout+bootstrap **with retry** (the first
   bootstrap empirically fails with rc=5 I/O error, retry after 1s succeeds). plist logic inline instead of
   `import` (importing `src.menubar.setup_menubar` would load the AppKit-heavy menubar code in the
   build context).
4. **`dev/menubar_debug.py`** warning corrected to point at `./venv/bin/python setup_py2app.py py2app`.

## End State

One command `./venv/bin/python setup_py2app.py py2app` does **build + install + bootstrap**.
The menubar runs as a native Mach-O binary (51 MB, validly signed, `codesign --verify` clean),
no more python process. The `codesign WARN (rc=1)` during install is just the info line
"replacing existing signature" — the signature is valid.

## Sources
- Commits on dev: `37ce26c` (refactor), `437d09e` (install), `b9d1465` (bootstrap-retry), `af5ac48` (docs)
- The menubar-restart-broken topic (footgun history)
- `src/menubar/DOCS.md` (`setup_menubar.py` + `setup_py2app.py` entries)
