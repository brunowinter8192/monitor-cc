# Menubar Per-Project — Phase B Iterations (2026-05-20)

## Iteration 1 — Initial Refactor

Commits `6bf7ea0` (ancestry walk) + `14b0d9a` (per-project button + bg_by_project pass-through) + `c0bb1ac` (DOCS).

- `bg_timer.py`: ancestry-chain walk (depth ≤ 5, replaces `gppid = parent[0]`)
- `panel.py`: `bg_by_project` dict pass-through, the `_aggregate_bg` import removed from app.py
- `app.py`: `_abort_btn` (single) → `_abort_btns_by_project: Dict[str, NSButton]` + `_abort_project_for_tag: Dict[int, str]`
- `panel.py`: `_make_separator_view(project_name, panel_width, proj_min_remaining)` returns `(view, optional_button)` — Option B layout
- `abortBgTimer_(sender)` per-project via a `sender.tag() → _abort_project_for_tag` lookup

The sleep-hook worker hit its context limit mid-Phase-B but all 3 commits landed incrementally (per the go-message checkpoint strategy). The worker auto-compacted to a fresh 100% post-recovery.

## Iteration 2 — Crash Fix

Commit `ebdc4ad`.

Live-verify after merge + menubar restart: the panel was completely empty + an AttributeError on every tick:

```
File "src/menubar/panel.py", line 294, in _make_separator_view
    abort_btn.setDrawsBackground_(True)
AttributeError: '_CursorlessButton' object has no attribute 'setDrawsBackground_'
```

Root cause: `setDrawsBackground_` is an NSTextField-only API; `_CursorlessButton` subclasses NSButton. The worker had copy-pasted from the underlying `tf = _CursorlessLabel` block (line 305-306).

Fix: `setDrawsBackground_(True)` → `setWantsLayer_(True)` (makes a borderless NSButton layer-backed → `setBackgroundColor_` actually takes effect). Net: 1 line, intent preserved (button background covers the separator line).

**Process lesson:** Opus skipped phase-4 code review (diff-read) before merging — relied on the completion checklist + git log + `--stat`. The workers-rules § Code Review (MANDATORY) was sharpened mid-session: diff-read is non-skippable EVEN for ad-hoc / one-line / context-recovery merges.

## Iteration 3 — Session-Row Badge

Commit `2b32814`.

Live-verify after Iteration 2: per-project abort buttons were correct (Monitor_CC `⊗ 6:57` + searxng `⊗ 3:17`) BUT:
- The Monitor_CC session row showed `[B 3:17]` (wrong — should be 6:57)
- The searxng session row showed `[ ]` (no badge despite an active timer)

Two bugs identified:

**Bug 1 — the session-row badge used the global `min_remaining`** instead of `proj_bg.min_remaining`:
```python
min_remaining = min(info.min_remaining for info in bg_by_project.values())
...
badge = _format_bg_badge(min_remaining) if s.has_bg else _NO_BG
```
Fix: drop the global computation, use `_format_bg_badge(proj_bg.min_remaining) if proj_bg else _NO_BG`.

**Bug 2 — `has_bg` and `bg_by_project` are independent data sources**:
- `has_bg` comes from `_has_active_bg(encoded_dir, session_id)` in discover.py — checks `tasks/*.output` files with `st_size == 0`
- `bg_by_project` comes from `_scan_bg_sleep_timers()` — scans running sleep processes

The two can desync → the abort button renders (sleep is running) but the row badge doesn't (task file missing/full). Fix: derive badge visibility entirely from `bg_by_project`, drop `has_bg` from the badge decision (it stays in the struct for other consumers).

Net: −2 LOC in panel.py, single commit, smoke test (py-import) passes.

## End State

Both live-verified after `launchctl kickstart`:
- Per-project countdowns show each project's own time
- Per-project abort buttons inline in the separator (Option B)
- Cross-project auto-abort eliminated (it was already per-project — the manual button was the problem)

## Sources

- Commits `6bf7ea0`, `14b0d9a`, `c0bb1ac`, `ebdc4ad`, `2b32814` (Monitor_CC dev branch)
- A tracking task closed live-verified
- `~/.claude/shared-rules/opus/workers-2.md` § Code Review — sharpened mid-session
