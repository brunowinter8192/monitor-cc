# Ghostty Scroll-Lock — A1 Investigation + Config Fix

## Problem

User's Ghostty viewport auto-scrolls to bottom during long sessions, losing scrollback read
position. Two apparent triggers observed: Bash tool output arriving while scrolled up, and
possibly keystroke events. Massive UX pain — every tool call during a long monitoring session
could knock the user back to bottom mid-read.

## Investigation Findings

### Config.zig packed struct — `scroll-to-bottom`

Source: `ghostty-org/ghostty src/config/Config.zig` lines 923-937 + 10228-10234 (verified via
gh-cli `grep_file`).

`scroll-to-bottom` is a packed struct with two independent boolean fields:
- `keystroke` — default **true** (scroll to bottom on any keystroke)
- `output` — default **false** (do NOT scroll to bottom on terminal output)

String representations accepted by the parser (comma-separated, order-independent):
- `keystroke` / `no-keystroke`
- `output` / `no-output`

### Default state mismatch

User had **no `~/.config/ghostty/config` file** — Ghostty was running on built-in defaults.
Defaults: `keystroke=true, output=false` → auto-scroll on keystrokes, NOT on output.

This contradicts the observed symptom (viewport jumping on Bash tool output). The mismatch is
unresolved — either:
- Ghostty's actual shipped default differs from what Config.zig comments describe, OR
- The trigger is keystroke-induced (a key is being pressed/echoed at the moment output arrives),
  making it look like output-triggered, OR
- The CC TUI itself emits ANSI scroll/cursor directives that bypass Ghostty's config entirely

### Fix applied (Opus-direct, cross-project)

Wrote `~/.config/ghostty/config`:
```
scroll-to-bottom = no-keystroke, no-output
```

Both auto-scroll triggers explicitly disabled. Config applies app-wide — Ghostty runs as a
single process across all windows/tabs, so one reload covers all surfaces.

Reload method: `osascript` scripted click of `Reload Configuration` under the Ghostty menubar
item (`System Events → process "Ghostty" → menu bar → menu bar item "Ghostty" → menu "Ghostty"
→ menu item "Reload Configuration"`).

Note: an earlier attempt used `no-keystroke, no-output` without the space after the comma.
Whether the space is semantically required by the parser is unclear (see Hypotheses).

## Live-Test Observations

| Test | Action | Result |
|---|---|---|
| Test 1 | Scrolled up + `echo` Bash output | Viewport held — PASS |
| Test 2 | After sequence of merges + Ctrl-R in shell | Viewport jumped again — FAIL |
| Test 3 | Config rewritten with `no-keystroke, no-output` (comma+space), reload | Viewport held — PASS |

Whether the space-variant fixed a parse issue OR whether the symptom is intermittent for an
unrelated reason: **UNCLEAR**. User is observing across subsequent sessions.

## Hypotheses (none verified, all open)

| Hypothesis | Status | Evidence |
|---|---|---|
| Parser is whitespace-sensitive — `no-keystroke,no-output` (no space) parses incorrectly, reverting to defaults | Active | Ghostty docs show comma+space in examples; packed-struct parser logic not read in detail |
| Reload only applies to NEW surfaces; existing windows/tabs retain pre-reload config | Active | Ghostty docs on reload scope not checked; one of the failing tests occurred after merges (no new surface) |
| CC TUI emits ANSI cursor/scroll directives (`\033[r`, `\033[H`, etc.) that override Ghostty config | Active | Monitor_CC prints `\033[2J\033[3J\033[H` on every render cycle (monitor.py line 286) — these reset the scroll region and home the cursor, which may cause Ghostty to treat it as a scroll-to-bottom event regardless of config |

## Sources

- `ghostty-org/ghostty src/config/Config.zig` lines 923-937, 10228-10234 — verified via gh-cli
  `grep_file` in this session
- Ghostty `+list-keybinds` output — confirmed no scroll-binding overrides
- Config.zig comments are the primary documentation for the packed-struct field semantics

## Status

**A1 partial-resolved + monitoring.** User confirmed PASS on most recent test. Config is in
place at `~/.config/ghostty/config`. Will observe whether jumping recurs across sessions.

**If symptom recurs:** pivot to Hypothesis 3 — investigate which ANSI sequences Monitor_CC
emits per render cycle and whether any of them trigger Ghostty's internal scroll-to-bottom
independent of the config setting. Starting point: `monitor.py` line 286 (`\033[2J\033[3J\033[H`)
and the render output of all other pane loops.
