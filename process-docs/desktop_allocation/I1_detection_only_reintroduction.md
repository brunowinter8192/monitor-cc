# I1 — Detection-Only Display Reintroduction (2026-06-13)

## Context

The full desktop-number machinery (detection + display + sidecar) was rolled back in commits
`466f327` + `f81b283` (2026-06-01) because the **window-MOVE** is impossible on macOS 26.5 SIP
without a SIP-off Dock injection (proven in G4, documented in H1). The rollback was a blanket
removal — detection, display, AND sidecar went together, even though detection itself always
worked correctly.

The TCC blocker that previously prevented detection in bundle context — exec chain losing bundle
identity, `kCGWindowName` stripped by TCC — was solved in `bff8c0e` (2026-05-28) via the py2app
migration. That fix is still the current architecture. Detection-only
is therefore fully unblocked: the bundle has the right TCC identity, the py2app-built binary
holds Screen Recording grant, and `desktop_detection.py`'s three-strategy resolver was proven
functional by two earlier probes.

Root cause of the earlier block: the exec chain caused audit-token loss, so TCC stripped
`kCGWindowName`. The window-move mechanism was separately proven impossible (SIP-free move APIs
are no-ops on macOS 26.5), while detection itself stayed functional throughout — hence
reintroducing detection-only here.

## What Was Rolled Back vs. What Stays Dead

| Component | Status |
|---|---|
| `desktop_detection.py` (CGS/AS/OSC-2 resolver) | RESTORED |
| `SessionInfo.desktop_no` field | RESTORED |
| `[N]` / `[!N]` slot display in panel | RESTORED |
| `_desktop_to_cwd` mapped to real desktop numbers | RESTORED |
| `NSScreenCaptureUsageDescription` in py2app plist | RESTORED |
| `_write_cwd_desktop_sidecar()` | NOT restored — served cross-repo desktop_targeting which stays dead |
| `paths.py CWD_DESKTOP_FILE` | NOT restored — no sidecar, no consumer |
| Window move (`CGSMoveWindowsToManagedSpace` etc.) | NOT restored — proven impossible (H1/G4) |
| Spawn/file-open placement (Meta/blank, `desktop_targeting.py`) | NOT restored — different repo |

## Files Changed

### `src/menubar/desktop_detection.py` — RESTORED verbatim
Recovered from `git show 466f327^:src/menubar/desktop_detection.py` (pre-rollback state).
350 lines, detection-only — no move code was ever in this file. Three-strategy resolver:
(1) name-unique `kCGWindowName` → single-candidate match; (2) space-elimination via
`CGSCopySpacesForWindows` per candidate, drop already-claimed; (3) OSC-2 injection —
write `__DET_<hex>` marker to tty, re-match after 500ms propagation delay. Results cached
for `_DET_CACHE_TTL=10s`, force-invalidated when main-cwd set changes. Transition logging
on desktop-number change (not per-cycle spam).

### `src/menubar/discover.py` — 3 additions, no rewrites

- **Import:** `from .desktop_detection import detect_main_desktop_numbers` — `_cwd_desktop_lkg`
  NOT imported (only needed by sidecar writer which stays removed).
- **`SessionInfo.desktop_no`:** trailing optional field `Optional[int] = None`. Default means
  all existing `SessionInfo(...)` construction sites that omit it continue to work — no change
  to `_process_project_dir` required.
- **Batch detection call** in `list_alive_sessions()` after the per-project loop:
  builds `cwd_tty_map` and `cwd_uuid_map` from `_cc_proc_cache` + `_ghostty_tty_to_id`, calls
  `detect_main_desktop_numbers(cwd_uuid_map, cwd_tty_map, now)`, populates `desktop_no` via
  `_replace`. No sidecar write. Worker sessions pass through unmodified (guarded by `if not
  s.is_worker`). Today's worker-branch fix (`worktree_rest.split('/')[0]`) is in the worker
  branch of `_process_project_dir` and is untouched.

### `src/menubar/panel.py` — 2 changes

- `_GRID_COL0_W` 33 → 40: `[!N]` is 4 chars; 33 pts clips it.
- `_project_desktop_no(sessions, project_name)` restored: returns `min()` of `desktop_no`
  across all mains of the project, or `None` if all-None. `min()` handles the rare case of
  2 mains in the same project (uses the lower desktop number for sort/grouping).

### `src/menubar/panel_manager.py` — pre-rollback rendering restored

- `Counter` import re-added; `_project_desktop_no` import re-added.
- **Sort key:** `(_pdn[project_name] or _INF, project_name, is_worker, name)` — projects sort
  by their lowest detected desktop number, with `None`-desktop projects last (`_INF`).
- **`dno_counts` / `conflict_set`:** `Counter` of `desktop_no` across all non-worker sessions
  with a known number; `conflict_set` = desktop numbers with count > 1 (2+ mains on same desktop).
- **Slot display:**
  - `dno is None` → `slot_str = ''`, orange (detection failed or Screen Recording not granted)
  - `dno in conflict_set` → `slot_str = f'[!{dno}]'`, red (conflict marker)
  - otherwise → `slot_str = f'[{dno}]'`, orange (real desktop number)
- **`_desktop_to_cwd`:** `{dno: cwd}` only for non-conflicted mains. `HotkeyController.
  reregister_digits(_desktop_to_cwd)` maps Cmd+N to the session on Mission Control desktop N.
  Conflicted sessions excluded (ambiguous focus target).

### `setup_py2app.py` — `NSScreenCaptureUsageDescription` restored

Needed for `CGWindowListCopyWindowInfo` + `kCGWindowName` in the py2app bundle. Identical
wording to the pre-rollback text. Affects py2app rebuilds only; no runtime change to existing
bundles (the TCC grant must be re-granted by the user after the first rebuild with this key).

## Integration Notes

The current `discover.py` differs from the pre-rollback state by the worker-branch fix
(`worktree_rest.split('/')[0]` — committed today). The detection additions apply
only in `list_alive_sessions()` (after the loop) and in the `SessionInfo` NamedTuple — neither
touches the worker branch. The adaptation is a strict addition, not a rewrite.

`_desktop_to_cwd` semantics changed: pre-rollback `{dno: cwd}`, rollback `{slot: cwd}`,
reintroduction `{dno: cwd}` again. Cmd+1 now focuses the session on Mission Control desktop 1,
Cmd+2 on desktop 2, etc. — intent-correct. When detection fails (Screen Recording not granted,
Ghostty not running), `desktop_no=None` for all mains → `slot_str=''`, `_desktop_to_cwd={}` →
Cmd+N hotkeys produce no-ops, but the panel still renders all sessions correctly without
numbers.
