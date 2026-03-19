# Pipe Section: Entry & Startup

## Status Quo

- `workflow.py`: `--mode all` → tmux 3-Pane (main | rules + subagent), `--mode main|subagent|rules` → einzelner Prozess
- `startup.py`: argparse mit choices `['all', 'main', 'subagent', 'rules']`, `--project`, `--ui`
- `tmux_launcher.py`: `split-window -h` dann `split-window -v -b` → 3 Panes, history 50000, keybindings (Ctrl-Q scroll, mouse, M-m/M-s copy, M-r rules-pane copy)

tmux Layout (verifiziert via dev/display/test_tmux_layout.sh):
```
┌─────────────────┬──────────────────┐
│                 │ Pane 1 (rules)   │  25% Höhe
│  Pane 0 (main)  │──────────────────│
│                 │ Pane 2 (subs)    │  75% Höhe
│    50% Breite   │   50% Breite     │
└─────────────────┴──────────────────┘
```

Split-Sequenz:
1. `new-session -d -s $session $main_cmd` → Pane 0 (links, volle Höhe)
2. `split-window -h -t $session:0.0 -l 50% $subagent_cmd` → Pane 1 (rechts, volle Höhe)
3. `split-window -v -t $session:0.1 -b -l 25% $rules_cmd` → Pane 1 (rechts-oben 25%), Pane 2 = alter Pane 1 (rechts-unten 75%)

## Evidenz

Pending — needs evaluation.

## Recommendation (SOLL)

Pending — needs evaluation.

## Offene Fragen

- tmux Keybinding für 3. Pane: M-r für Rules-Pane Copy implementiert, Verhalten bei unterschiedlichen Pane-Indices noch zu verifizieren

## Quellen

- (keine)
