# Menubar Per-Project — Phase A (2026-05-20)

## Trigger

Cross-project timer attribution observed: Monitor_CC opus's `sleep N && echo done` background timer was attributed to the searxng session row instead of Monitor_CC. Symptom: the `[B M:SS]` countdown appeared under the wrong project row in the menubar panel. Consequence: searxng's worker-idle auto-abort killed Monitor_CC's timer.

Second symptom: a global "abort timer" button at the panel top — clicking it kills ALL timers cross-project.

## Attribution Investigation

Live ps-tree captured during an active worker session:

```
PID    PPID   ARGS
sleep-pid → zsh-pid (eval 'sleep N && echo done') → CC-pid
```

Chain depth = 2 in the normal case (ppid_of_zsh = the CC process pid).

`bg_timer.py:_scan_bg_sleep_timers` attribution path:

```python
parent = pid_info.get(ppid, ...)   # zsh
gppid = parent[0]                   # CC pid expected
cc_entry = _cc_proc_cache.get(gppid)
cwd = cc_entry[1] if cc_entry else ''
project_name = cwd_to_project.get(cwd, 'unknown')
```

**Scenarios discussed:**

| Scenario | Pattern | Attribution result | Likelihood |
|---|---|---|---|
| A | CC → sh -c → zsh → sleep (3-layer chain) | gppid = sh, miss → `'unknown'` | Low (CC normally execs zsh directly) |
| B | PID recycling: CC exits + another project's CC reuses the PID + the cache TTL window | gppid maps to the OLD project that owned the PID before the recycle | A narrow timing window — produces exactly the observed cross-project symptom |

`_auto_abort_check` (app.py 217-237) is ALREADY per-project — it operates on the `bg_by_project` dict. Only the global manual abort button was structurally the actual cross-project problem.

## UI Options Discussed

| Option | Layout | Height cost | Implementation |
|---|---|---|---|
| A | Abort row directly under the project separator | +21pt per project with a timer | Simple (NSButton-as-subview-in-stackview) |
| B | Abort button in the separator view, inline right | 0pt | Make the separator view interactive |
| C | Abort row under the session rows per project | +21pt per project with a timer | Logically "belongs to project" |

User vote: **B** ("inline next to each project name").

## Recommended Fix Scope

- **Ancestry-chain walk** (depth ≤ 5) in `_scan_bg_sleep_timers` — catches Scenario A (intermediate shell layers)
- **bg_by_project dict pass-through** instead of `_aggregate_bg` in panel.py + app.py
- **Per-project NSButton in the separator** (Option B layout)
- **PID recycling (Scenario B) not directly fixed** — parsing the zsh args of the `/tmp/claude-XXX-cwd` file would be the robust way, "more invasive," deferred. The per-project UI limits the blast radius to one project bucket.

## Sources

- `src/menubar/bg_timer.py:_scan_bg_sleep_timers`
- `src/menubar/panel.py:_make_separator_view`
- `src/menubar/app.py:_PanelController.abortBgTimer_`
- Live ps-tree captured 2026-05-20
