# Menubar Per-Project — Phase A (2026-05-20)

## Trigger

Cross-project Timer-Attribution observed: Monitor_CC opus `sleep N && echo done` background timer wurde der searxng Session-Row zugeordnet statt Monitor_CC. Symptom: `[B M:SS]` Countdown unter falscher Project-Row im Menubar Panel. Konsequenz: searxng's worker-idle Auto-Abort killte Monitor_CC's Timer.

Zweites Symptom: globaler "abort timer" Button am Panel-Top — bei click killt er ALLE Timer cross-project.

## Attribution-Investigation

Live ps-Tree captured während aktiver Worker-Session:

```
PID    PPID   ARGS
sleep-pid → zsh-pid (eval 'sleep N && echo done') → CC-pid
```

Chain depth = 2 in normal case (ppid_of_zsh = CC process pid).

`bg_timer.py:_scan_bg_sleep_timers` attribution path:

```python
parent = pid_info.get(ppid, ...)   # zsh
gppid = parent[0]                   # CC pid expected
cc_entry = _cc_proc_cache.get(gppid)
cwd = cc_entry[1] if cc_entry else ''
project_name = cwd_to_project.get(cwd, 'unknown')
```

**Scenarios diskutiert:**

| Scenario | Pattern | Attribution-Result | Wahrscheinlichkeit |
|---|---|---|---|
| A | CC → sh -c → zsh → sleep (3-Layer chain) | gppid = sh, miss → `'unknown'` | Niedrig (CC normalerweise direct zsh exec) |
| B | PID recycling: CC exits + other project's CC reuses PID + cache TTL window | gppid maps to OLD project that owned PID before recycle | Narrow timing window — produziert das genau-observed cross-project symptom |

`_auto_abort_check` (app.py 217-237) ist BEREITS per-project — operates on `bg_by_project` dict. Nur globaler manueller Abort-Button war strukturell das eigentliche cross-project Problem.

## UI Options diskutiert

| Option | Layout | Höhen-Kosten | Implementierung |
|---|---|---|---|
| A | Abort-Row direkt unter project separator | +21pt pro Project mit Timer | Einfach (NSButton-as-subview-in-stackview) |
| B | Abort-Button im Separator-View, rechts inline | 0pt | Separator-View interaktiv machen |
| C | Abort-Row unter Session-Rows pro Project | +21pt pro Project mit Timer | Logisch "belongs to project" |

User-Vote: **B** ("inline bei jedem project name").

## Empfohlener Fix-Scope

- **Ancestry-chain walk** (depth ≤ 5) in `_scan_bg_sleep_timers` — fängt Scenario A ab (intermediate shell layers)
- **bg_by_project Dict pass-through** statt `_aggregate_bg` in panel.py + app.py
- **Per-project NSButton im separator** (Option B layout)
- **PID-recycling (Scenario B) nicht direkt gefixt** — zsh-args-Parsing der `/tmp/claude-XXX-cwd` Datei wäre der robuste Weg, "more invasive", deferred. Per-project UI begrenzt blast radius auf einen Project-Bucket.

## Quellen

- `src/menubar/bg_timer.py:_scan_bg_sleep_timers`
- `src/menubar/panel.py:_make_separator_view`
- `src/menubar/app.py:_PanelController.abortBgTimer_`
- Live ps-tree captured Session 2026-05-20
