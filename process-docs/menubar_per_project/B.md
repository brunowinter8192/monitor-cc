# Menubar Per-Project — Phase B Iterationen (2026-05-20)

## Iteration 1 — Initial Refactor

Commits `6bf7ea0` (ancestry walk) + `14b0d9a` (per-project button + bg_by_project pass-through) + `c0bb1ac` (DOCS).

- `bg_timer.py`: ancestry-chain walk (depth ≤ 5, replaces `gppid = parent[0]`)
- `panel.py`: `bg_by_project` Dict pass-through, `_aggregate_bg` import entfernt aus app.py
- `app.py`: `_abort_btn` (single) → `_abort_btns_by_project: Dict[str, NSButton]` + `_abort_project_for_tag: Dict[int, str]`
- `panel.py`: `_make_separator_view(project_name, panel_width, proj_min_remaining)` returns `(view, optional_button)` — Option B layout
- `abortBgTimer_(sender)` per-project via `sender.tag() → _abort_project_for_tag` lookup

Sleep-hook worker hit context limit mid-Phase-B aber alle 3 Commits inkrementell gelandet (per Go-Message Checkpoint-Strategie). Worker auto-compacted to fresh 100% post-recovery.

## Iteration 2 — Crash Fix

Commit `ebdc4ad`.

Live-Verify nach merge + menubar restart: Panel komplett leer + AttributeError jedem Tick:

```
File "src/menubar/panel.py", line 294, in _make_separator_view
    abort_btn.setDrawsBackground_(True)
AttributeError: '_CursorlessButton' object has no attribute 'setDrawsBackground_'
```

Root cause: `setDrawsBackground_` ist NSTextField-only API; `_CursorlessButton` subclasses NSButton. Worker hat copy-paste vom darunterliegenden `tf = _CursorlessLabel` Block (line 305-306) gemacht.

Fix: `setDrawsBackground_(True)` → `setWantsLayer_(True)` (macht borderless NSButton layer-backed → `setBackgroundColor_` wirkt tatsächlich). Net: 1 line, intent erhalten (button background covers separator line).

**Process-Lesson:** Opus skipped Phase 4 Code-Review (diff-read) before merge — verließ sich auf Completion-Checklist + git log + `--stat`. Workers-2.md § Code Review (MANDATORY) wurde mid-session geschärft: diff-read non-skippable EVEN für ad-hoc / one-line / context-recovery merges.

## Iteration 3 — Session-Row Badge

Commit `2b32814`.

Live-Verify nach Iteration 2: per-project Abort-Buttons korrekt (Monitor_CC `⊗ 6:57` + searxng `⊗ 3:17`) ABER:
- Monitor_CC Session-Row zeigt `[B 3:17]` (wrong — sollte 6:57 sein)
- searxng Session-Row zeigt `[ ]` (kein Badge obwohl Timer aktiv)

Two bugs identifiziert:

**Bug 1 — Session-Row Badge nutzt globales `min_remaining`** statt `proj_bg.min_remaining`:
```python
min_remaining = min(info.min_remaining for info in bg_by_project.values())
...
badge = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
```
Fix: drop global computation, use `_format_bg_badge(proj_bg.min_remaining) if proj_bg else _NO_BG`.

**Bug 2 — `has_bg` und `bg_by_project` sind unabhängige Datenquellen**:
- `has_bg` kommt von `_has_active_bg(encoded_dir, session_id)` in discover.py — prüft `tasks/*.output` Files mit `st_size == 0`
- `bg_by_project` kommt von `_scan_bg_sleep_timers()` — scannt running sleep processes

Beide können desyncen → Abort-Button rendered (sleep läuft) aber Row-Badge nicht (task file fehlt/voll). Fix: Badge-Visibility komplett aus `bg_by_project` ableiten, `has_bg` raus aus Badge-Entscheidung (bleibt im Struct für andere consumer).

Net: −2 LOC in panel.py, single commit, smoke-test (py-import) passes.

## End-State

Beide live-verified post `launchctl kickstart`:
- Per-project Countdowns zeigen pro Projekt eigene Zeit
- Per-project Abort-Buttons inline im Separator (Option B)
- Cross-project Auto-Abort eliminiert (war schon per-project — manueller Button war Problem)

## Quellen

- Commits `6bf7ea0`, `14b0d9a`, `c0bb1ac`, `ebdc4ad`, `2b32814` (Monitor_CC dev branch)
- Bead `Monitor_CC-s7zk` (closed live-verified)
- `~/.claude/shared-rules/opus/workers-2.md` § Code Review — geschärft mid-session
