# C3 — Detection Logging: Log-Path Bug + Transition Observability

## Log-Path Bug (menubar_log.py)

### Root Cause

`menubar_log.py:5-6` (pre-fix):
```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MENUBAR_LOG  = PROJECT_ROOT / 'src' / 'logs' / 'menubar.log'
```

In the py2app bundle, `__file__` for `menubar_log.py` is:
```
.../Monitor_CC_Menubar.app/Contents/Resources/lib/python3.14/src/menubar/menubar_log.py
```
→ `parents[2]` = `.../Contents/Resources/lib/python3.14/`
→ `MENUBAR_LOG` = `.../lib/python3.14/src/logs/menubar.log`

That is inside the `.app` bundle — wiped by `_prune_bundle_bloat()`, never visible to the
user, never readable. Dev mode happens to hit the correct path (project root /
`src/logs/menubar.log`); bundle mode silently writes to an inaccessible path.

All other APP_SUPPORT files (settings.json, hooks.json, menubar.pid, etc.) correctly use
`_APP_SUPPORT = ~/Library/Application Support/com.brunowinter.monitor_cc_menubar` from
`paths.py`.

### Fix

`menubar_log.py` imports `_APP_SUPPORT` from `.paths`:
```python
from .paths import _APP_SUPPORT
MENUBAR_LOG = _APP_SUPPORT / 'menubar.log'
```

No circularity: `paths.py` imports nothing from the menubar package. `_migrate_from_dotfiles()`
runs on `paths.py` import and already creates `_APP_SUPPORT` — `MENUBAR_LOG.parent.mkdir()`
in `log_menubar()` becomes a no-op. Dev + bundle both write to
`~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log`.

---

## Logging Too Coarse — Partial Failure Invisible

### State (pre-fix)

`detect_main_desktop_numbers` (desktop_detection.py) only logs:
- `all_failed` — when ALL mains are None (line 94)
- Sub-resolution events in `_resolve_cgwindow_id` (`resolve_no_name_match`, `resolve_no_tty`,
  osc2 events) — per-call, without cwd context, without transition-gating → spam under a
  stable situation

When a single main loses its number (Monitor_CC `[2]` → None, while other mains stay
visible): **no log**. Likewise: success / recovery is never logged.

### Confirmed Trigger (user, 2026-05-28)

Every worker task (worker spawn AND `worker-cli send` to an existing worker) makes the
desktop number disappear immediately. Expected transition-log pattern:

```
[detection] transition Monitor_CC/Monitor_CC 2->None win='Monitor_CC — Claude Code' n_cand=0
```

`n_cand=0` means: AppleScript returns the Ghostty window name, but after the worker
spawn `_cgwindow_list_ghostty` finds no CGWindow with that title. Hypothesis: the worker
spawn opens a new Ghostty window → the window landscape changes → the SkyLight title
cache of the existing window becomes briefly invalid, or the CGWindowList snapshot
lands at the wrong moment.

Recovery: after the next successful 10s cycle (or when the user focuses the tab):
```
[detection] transition Monitor_CC/Monitor_CC None->2 win='Monitor_CC — Claude Code' n_cand=1
```

### Fix: Transition Logging

Module-level: `_last_result: Dict[str, Optional[int]] = {}` in `desktop_detection.py`.

In the orchestrator loop: `_cwd_ctx[cwd] = {'win': win_name, 'n_cand': len(candidates)}`
per cwd after `_resolve_cgwindow_id()` (no signature change to the function).

Post-loop transition check (before the cache update):
```python
for cwd, new_no in result.items():
    old_no = _last_result.get(cwd)
    if new_no == old_no:
        continue
    label  = os.path.basename(os.path.dirname(cwd)) + '/' + os.path.basename(cwd)
    ctx    = _cwd_ctx.get(cwd, {})
    detail = f'win={repr(ctx.get("win", ""))[:40]} n_cand={ctx.get("n_cand", "?")}'
    log_menubar('detection', f'transition {label} {old_no}->{new_no} {detail}')
_last_result = dict(result)
```

Transition-gated: no log for a stable state. `_cwd_ctx` is local per cycle (no state
leak). On an exception (Ghostty down / error), `_cwd_ctx` stays empty → `detail = win=''
n_cand=?` (signals: info unavailable, error path).

**Not implemented:** strategy-used (`name-unique / space-elim / osc2`) parked as a
nice-to-have — would require a return-tuple change to `_resolve_cgwindow_id` + all 5
exit paths. `n_cand` is enough as a first diagnostic step: `n_cand=0` isolates the
CGWindowList mismatch, `n_cand>1` would point at space-elimination / OSC2 fallback.
