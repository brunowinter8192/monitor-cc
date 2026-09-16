## Salvage from dev/tmux_launcher/argv_byte_identity.py

```
"""
Byte-identity harness for src/tmux_launcher.py's subprocess.run argv sequences (function-LOC
split of launch_split_screen/restart_panes).

Monkeypatches subprocess.run to record every argv list issued (real tmux is never invoked) and to
return scenario-appropriate canned stdout/returncode, for 3 scenarios:
(1) launch_split_screen — session doesn't pre-exist (has-session returncode != 0, so no
    kill_session call), attach-session stubbed (the fake never blocks).
(2) restart_panes — all 6 windows + every layout pane already present (pure respawn path, no
    new-window/split-window calls at all).
(3) restart_panes — window 2 entirely missing (recreate-from-scratch path, exercises the
    pane_specs[1:] split-after-create loop) AND window 5 present but missing its second pane
    'news-log' (single-missing-pane split path). A stateful fake tmux tracks observed
    new-window/split-window calls so a LATER list-panes call in the same run reflects them,
    exactly like real tmux would — this is what actually exercises the "refresh pane list so
    subsequent iterations see the new pane" comment in restart_panes.

Usage (from project root):
    ./venv/bin/python dev/tmux_launcher/argv_byte_identity.py

Prints one HASH line. Run before and after the tmux_launcher.py split; the hash must match.
"""
```

```
# Loaded via importlib (not a literal 'from src.' module-level line) — dev/ scripts may not use
# that form (block_dev_imports_src).
```

```
# Stateful fake tmux: tracks which windows/panes "exist" and how new-window/split-window calls
# extend that state, so a list-panes call issued later in the same run reflects a just-created
# pane exactly like real tmux would.
```

```
# All 6 windows + every layout pane already present -> pure respawn path
```

```
# Window 2 entirely missing from panes_by_window (caller also excludes it from `windows`);
# window 5 present but missing its second pane ('news-log')
```

## Salvage from dev/tmux_launcher/DOCS.md

Nothing cut — the pre-existing `## Role`, `## Flow`, and `## Modules` sections already fit the required format. No `## Gotchas` or other section existed to relocate.

## Notes for successor

- 1 file, 8 comments + 1 docstring — matches the measured state exactly. All 4 comment blocks are standalone (one 2-line, one 3-line, one 1-line, one 2-line), none trailing/inline.
- No load-bearing docstring: grepped `__doc__` — zero hits. Docstring deleted outright.
- **Run directly** (safe): this harness monkeypatches `subprocess.run` itself before calling `src.tmux_launcher.launch_split_screen`/`restart_panes` — real tmux is never invoked, by design (that's the whole point of the harness). No file writes, stdout-only (`HASH:` line).
- Verification: ran before and after the comment/docstring strip — `HASH:` line identical (deterministic: all three scenarios use fixed synthetic state, `json.dumps` without `sort_keys` on the recorded argv lists but argv order itself is deterministic since it comes from the code path being tested, not from any unordered container).
