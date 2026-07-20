# Menubar Overhaul Session — 2026-05-19

Iteration history and process findings from the session in which the 5 remaining tracked issues were worked through + a module-split refactor + a skill extension. The state of the code at the time lived in `src/menubar/DOCS.md` (post-split: 8 modules). This file documents how we got there.

## Hook-Based Activity Detection (resolves Issue 1 / Thinking Phase)

**Starting point:** discover.py used JSONL mtime as the working indicator (≤10s = working). While Opus reasons (Anthropic-side, no streaming output), the JSONL doesn't update → falsely "idle".

**Iteration 1 (before this session):** proxy-log mtime as an override. Condition was `(now - proxy_mtime) <= 10s`. Worked for the first 10s of a thinking phase, then idle.

**Iteration 2 (same session):** condition corrected to `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) <= 300s`. Structural signal: the proxy writes a request entry on receipt BEFORE the response comes back → proxy_mtime stays ahead of jsonl_mtime for the entire thinking phase. Held for ~30-120s thinking phases.

**Iteration 3 (final, this session):** user correction: "the proxy only writes when requests go through; during thinking phases the model works server-side at Anthropic, nothing comes through — we need to capture movement in the terminal." Pivot to the CC hook system (UserPromptSubmit / Stop / StopFailure). hook_writer.py writes session status synchronously to `~/.monitor_cc_menubar_hooks.json`, discover.py reads it with priority 1 (over JSONL and the proxy override). The window between UserPromptSubmit and Stop = working — fully covers thinking + tool-use + response.

**Implementation detail:** the hook-setup script (`src/menubar/hook_setup.py`) installs idempotently into `~/.claude/settings.json`. Hooks only activate on a CC restart (catch: the user's current CC session doesn't fire hooks until it restarts).

**Source for the pattern:** github.com/onikan27/claude-code-monitor — the same approach for a menubar tracker with an Ink-based TUI.

## launchd PATH Gotcha (resolves the worker-display bug)

**Symptom:** workers are NOT shown in discover (n=2 instead of n=6 in the tick log). From the terminal CLI, discover sees them correctly.

**Investigation:** tick diagnostics in `_tick()` showed `n=2 sessions=['Monitor_CC', 'wise2627']`. The discover-CLI test gave n=6. Difference: launchd-spawned vs terminal-spawned Python.

**Root cause:** launchd's default PATH = `/usr/bin:/bin:/usr/sbin:/sbin`. tmux at `/opt/homebrew/bin/tmux` is NOT in it. `_tmux_session_exists()` calls `tmux has-session` → command not found → returns False → workers filtered out in `_process_project_dir`.

**Fix:** `EnvironmentVariables/PATH` in the plist set to `/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`. Covers arm64 Homebrew + Intel fallback.

**Lesson:** launchd-spawned scripts do NOT inherit the user-shell PATH. Every subprocess call to a non-system binary must either use an absolute path or explicitly set PATH via the plist env.

## Restart Button Doesn't Kill the Old Process (resolves the double-bar-icon bug)

**Symptom:** clicking the restart button → two bar icons visible. The old process survives, a new one is additionally spawned.

**Investigation:** restart called `launchctl kickstart -k gui/<uid>/<label>`. The `-k` flag sends SIGTERM. Python signal handlers are blocked by the NSApp runloop. The process doesn't die, launchd spawns a new one (KeepAlive=true).

**Fix:** restart via `os.execv(sys.executable, [sys.executable] + sys.argv)` — an in-place replace, same PID, atomic. No launchd detour, no race. The fcntl lock must have FD_CLOEXEC so the new execv can re-acquire the lock.

**Bonus:** singleton enforcement via an fcntl lock in `_acquire_singleton_lock()` prevents parallel spawns from other sources. Exit code 0 when the lock is held — otherwise launchd's KeepAlive respawns endlessly.

## Panel Grow-Only Resize Semantics (resolves the worker-disappears-on-status-change bug)

**Symptom:** while the user types with Opus, worker rows disappear from the panel, then come back later.

**Root cause:** `_truncate_and_height` with atomic logic (`continue` instead of `break`) skipped entire projects when the panel was too small. Every status flip triggered `_tick`'s `_rebuild_panel` → re-truncation → the Monitor-CC group (3 sessions) suddenly no longer fit → dropped entirely.

**Fix iterations:**

**v1:** atomic truncation built in (continue instead of break). But: a status change triggers a rebuild → truncation recomputes → workers disappear anyway when the panel is too small.

**v2 (final):** truncation removed entirely. Panel size becomes:
- `max(user_dragged_height, content_required_height)`
- Grows with new workers (content_required_height increases)
- Never shrinks (user_dragged_height stays as the floor)
- Status change: only badges via `_update_panel_inplace`, NO rebuild, NO resize

`_panel_max_height` renamed → `_panel_min_height` (semantically correct floor instead of cap). `_hidden_count` and the `· N hidden` auto-jump label suffix removed — no more hidden concept needed.

## NSPanel Cursor Rabbit Hole (4 iterations, DEFERRED)

**Symptom:** hovering over panel edges shows no resize cursor (`↕`/`↔`). Bottom works partially (I-Beam switches to arrow), sides don't.

**Iteration 1:** hypothesis that `setAcceptsMouseMovedEvents_(True)` is missing. Added → 3441 mouseMoved fires logged → still visually I-Beam.

**Iteration 2:** NSView subclass `_PanelContentView` with an `updateTrackingAreas` override, owner=self. Confirmed mouseMoved fires via a per-iteration log. Cursor visually unchanged.

**Iteration 3:** switched from mouseMoved-NSCursor.set to the canonical resetCursorRects pattern. NSTextField subclass `_CursorlessLabel` with a no-op resetCursorRects against the I-Beam override. Bottom edge suddenly worked, sides still I-Beam.

**Iteration 4 (diagnosis):** detailed logging (x, y, w, branch). The `left-right` branch fired 92x at x<8 or x>372, but the cursor didn't visually change. Root cause: the layout covers edge regions with NSStackView/footer/top-bar. Our cursor rects on `_PanelContentView` only apply when the mouse is over EMPTY contentView pixels. The edge strips are covered.

**Status:** DEFERRED (NOT accepted). Next session after the refactor: try the NSPanel sendEvent-override pattern OR install cursor rects on every leaf subview. Drag-resize currently still works — only the visual indicator is missing.

## Iteration 5 (2026-05-20) — Probe-based Diagnosis

### What the probe showed

Worker `cursor-edges` built `dev/cursor_edges/probe.py` — foreground NSPanel mirroring production layout exactly. User ran it interactively (2026-05-20). Key observations:

| Signal | Count | Interpretation |
|---|---|---|
| `NSEventMonitor mouseMoved_` | ~280 | Mouse events reach the window normally |
| `mouseMoved_` on ContentView | ~280 | Tracking area delivers events correctly |
| `hitTest_` on left edge | Correct view | View hierarchy resolves the edge position |
| `cursorUpdate_` on ANY view | **0** | AppKit never dispatched a cursor-rect event |
| `resetCursorRects` cascade | 10 views | All rects installed correctly at startup |

### Why Iteration 4's hypothesis was wrong

Iteration 4 concluded "child views win the cursor-rect race because they cover the edge strips". This is refuted: the race never happens. `cursorUpdate_` fired **zero times** on every view, including ContentView over uncovered regions. The rects are installed, tracking areas fire, but AppKit's cursor-rect dispatch mechanism is not engaged at all.

### New root-cause hypothesis

`NSWindowStyleMaskNonactivatingPanel` blocks cursor-rect dispatching at the window level.

Normal NSWindow path: `becomeKeyWindow → enableCursorRects()` — this activates the cursor-rect dispatch mechanism. NonactivatingPanel never becomes key → `enableCursorRects()` is never called internally → cursor rects sit installed but are not dispatched when the mouse enters them.

### Probe `--fix` flag

`dev/cursor_edges/probe.py --fix` adds one call after `setContentView_`:

```python
panel.enableCursorRects()
enabled = panel.areCursorRectsEnabled()
_log(f'[--fix]  enableCursorRects() called — areCursorRectsEnabled={enabled}')
```

Startup smoke (2026-05-20): `areCursorRectsEnabled=True` — the call was accepted, no AttributeError, panel confirms dispatch is now enabled.

### Verification path

User runs:

```bash
venv/bin/python3 dev/cursor_edges/probe.py --fix
```

Then hovers slowly over the left edge (x < 8) and right edge (x > 372). Watch for `cursorUpdate_` in stderr.

- `cursorUpdate_` fires → hypothesis confirmed, `enableCursorRects()` was the missing call
- `cursorUpdate_` still fires 0 times → dispatch blocked at a lower level; next candidates: NSApp-level cursor-rect enable, window-server event routing, or the NonactivatingPanel style-mask overriding our call

### Recommended src/ port (pending verification)

If verified: one-line addition to `_make_nspanel()` in `src/menubar/panel.py`, after the `panel.setContentView_(...)` call:

```python
panel.enableCursorRects()
```

**NOT yet implemented** — user decides after running the `--fix` probe.

## Iteration 6 (2026-05-20) — Leaf-Rect Approach

### API clarification: cursorUpdate_ ≠ cursor-rect signal

`cursorUpdate_` is the NSTrackingArea callback. `addCursorRect_cursor_` dispatches directly at AppKit window level — it does **not** fire `cursorUpdate_`. The Iteration 5 log showing 0 `cursorUpdate_` calls was measuring the wrong thing. The correct signal is the visual cursor shape change, which DID happen (I-Beam→Arrow on panel entry with `--fix`).

### Iteration 5b interactive result

User ran `probe.py --fix` and hovered the left edge:

| Signal | Result |
|---|---|
| I-Beam → Arrow on panel entry | ✅ NOW works (broken before --fix) |
| Resize `↔` at left/right edge | ❌ still missing |
| `cursorUpdate_` count | 0 — irrelevant metric (see above) |

`enableCursorRects()` was genuinely the missing call — confirmed visually. Arrow cursor in the interior is now correct. The `↔` resize cursor at the edges is still absent → a second blocker exists.

### New hypothesis: subview coverage

The Iteration 4 child-view-race hypothesis is **back on the table**. The reason it appeared refuted (zero `cursorUpdate_`) was a measurement error: we were checking the wrong signal. The underlying geometry is still true: StackView, FooterView, and TopBarView physically cover the edge strips where ContentView's cursor rects were installed. AppKit's deepest-subview-first cursor-rect dispatch means ContentView's rects are shadowed whenever a covering subview does not install its own rects for the same strip.

**Fix approach:** install resize cursor rects directly on each covering leaf subview in its own `resetCursorRects`, in addition to super's rects. Super first, leaf rects after (to let super install its default arrow rect, then override the edge strips with our resize rect).

### --leaf-rects flag (2026-05-20)

`dev/cursor_edges/probe.py --leaf-rects` (requires `--fix`) adds to each subclass's `resetCursorRects`:

| View | Leaf rects |
|---|---|
| `_LoggingStackView` (frame.y=30, h=409) | LEFT x=0..8 + RIGHT x=372..380, full local height |
| `_LoggingFooterView` (frame.y=0, h=30) | LEFT + RIGHT (full height) + BOTTOM y=0..8 (full width) |
| `_LoggingTopBarView` (frame.y=439, h=21) | LEFT + RIGHT (no top rect) |
| `_LoggingButton` | LEFT x=0..8 if `frame.origin.x < EDGE` (Auto-Jump, session rows; Kill/Restart excluded) |

Module-level `_LEAF_RECTS_ENABLED` flag set in `main()` before panel construction; all subclasses check it in their `resetCursorRects`.

**Smoke (2026-05-20):** starts clean, `areCursorRectsEnabled=True`, all `[leaf]` lines logged, no AttributeError.

### Verification path

```bash
venv/bin/python3 dev/cursor_edges/probe.py --fix --leaf-rects
```

Hover left edge (x < 8), right edge (x > 372), bottom edge (y < 8) slowly. Watch stderr for cursor shape change.

- `↔` appears at left/right → subview-coverage was the blocker → leaf-rect approach confirmed
- Still Arrow/I-Beam → coverage is NOT the issue; next candidate: `NSPanel.sendEvent_` override or `NSWindowDelegate.windowShouldClose_` -level intercept

### src/ port recipe (pending user verification)

If `--leaf-rects` verifies the hypothesis, the production fix in `src/menubar/panel.py` is:

**Step 1:** Add `panel.enableCursorRects()` after `panel.setContentView_(cv)` in `_make_nspanel()`.

**Step 2:** Add `resetCursorRects` overrides to each production subclass:

- `_PanelContentView(NSView)` — already has 4-zone rects; no change needed
- Production `stack` → subclass `NSStackView`, add `resetCursorRects`:
  ```python
  def resetCursorRects(self):
      super().resetCursorRects()
      h = self.bounds().size.height; w = self.bounds().size.width
      self.addCursorRect_cursor_(NSMakeRect(0, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
      self.addCursorRect_cursor_(NSMakeRect(w - EDGE, 0, EDGE, h), NSCursor.resizeLeftRightCursor())
  ```
- Production `footer` → subclass `NSView`, add `resetCursorRects` with LEFT + RIGHT + BOTTOM
- Production `top_bar` → subclass `NSView`, add `resetCursorRects` with LEFT + RIGHT
- Production toggle button (`_toggle_btn`) → if `NSButton` subclass, add LEFT rect guard

All changes in `src/menubar/panel.py`. No other files touched.

**NOT yet implemented** — user decides after running `probe.py --fix --leaf-rects`.

## Iteration 7 (2026-05-20) — H7 No-Resizable Test + enableCursorRects Port

### Iteration 6 outcome: leaf-rects approach refuted

User ran `probe.py --fix --leaf-rects` interactively. Result: no `↔`/`↕` resize cursors appeared at any edge. The I-Beam→Arrow transition (from `enableCursorRects`) still worked, but the resize cursors did not.

This refutes the subview-coverage hypothesis. Leaf rects were installed on every covering view (StackView, FooterView, TopBarView, left-edge Buttons) and none produced a visible resize cursor. The blocker is upstream of `addCursorRect_cursor_` dispatch — the rects are installed, cursor-rect dispatch is enabled, but the cursor shape does not change at the edges.

### H7 hypothesis: NSWindowStyleMaskResizable claims edge regions

**Hypothesis:** When `NSWindowStyleMaskResizable` is present on a `NonactivatingPanel`, WindowServer intercepts the edge pixel strips and handles resize drag-start natively. For a normal resizable window this would show OS resize cursors at the edges; for NonactivatingPanel the window never gets key focus so WindowServer neither shows its resize cursors nor yields the edge strips to AppKit's cursor-rect dispatch. Result: edges are a dead zone — no OS resize cursors, no our cursor rects.

**Test:** create the panel with ONLY `NSWindowStyleMaskNonactivatingPanel` (no resizable mask). Without the resizable flag WindowServer has no reason to claim the edge strips, and our cursor rects should fire normally.

**Trade-off:** no native window drag-resize when the resizable mask is absent. This is acceptable for cursor-appearance-only, but it also removes the user's ability to drag-resize the panel. That is a UX regression; whether it's acceptable is a user decision.

### --no-resizable flag (2026-05-20)

`dev/cursor_edges/probe.py --no-resizable` (requires `--fix`) creates the panel with:

```python
style_mask = NSWindowStyleMaskNonactivatingPanel  # no NSWindowStyleMaskResizable
```

All other flags (`--leaf-rects`) remain combinable.

**Smoke (2026-05-20):** all combos (`--fix`, `--fix --leaf-rects`, `--fix --no-resizable`, `--fix --leaf-rects --no-resizable`) start clean, correct MODE lines, `areCursorRectsEnabled=True`, no AttributeError.

### enableCursorRects() port to src/menubar/panel.py (2026-05-20)

Independent of H7 outcome: `enableCursorRects()` restores the I-Beam→Arrow cursor transition when entering the panel. This is a real UX improvement — without it, hovering anywhere on the panel keeps the I-Beam cursor from outside. It was missing because NonactivatingPanel never calls `becomeKeyWindow`, which is the normal trigger for `enableCursorRects()` internally.

**Ported:** one line + comment added to `_make_nspanel()` in `src/menubar/panel.py`, immediately after `panel.setContentView_(cv)`:

```python
# NonactivatingPanel never calls becomeKeyWindow → enableCursorRects() is never invoked
# automatically → cursor-rect dispatch is silently disabled (no cursor changes anywhere).
# Explicit call here restores dispatch; confirmed via dev/cursor_edges/probe.py --fix.
panel.enableCursorRects()
```

This is the ONLY src/ change. Leaf-rects approach is NOT ported (refuted). `--no-resizable` approach is NOT ported (awaiting H7 verification AND user decision on the drag-resize trade-off).

### Verification path

```bash
venv/bin/python3 dev/cursor_edges/probe.py --fix --no-resizable
```

Hover left edge (x < 8), right edge (x > 372), bottom edge (y < 8).

- `↔`/`↕` appears → H7 confirmed; user decides whether no-drag-resize is acceptable for the resize-cursor UX gain
- Still Arrow/I-Beam → H7 refuted; remaining hypotheses:

| Hypothesis | Description | Cost |
|---|---|---|
| H8 custom resize | Intercept `NSWindowDidResizeNotification` + manual drag tracking in `mouseDown_`/`mouseDragged_` | High |
| H9 `sendEvent_` override | Intercept `NSWindow.sendEvent_` at panel level, inject cursor change before AppKit processes the event | High |

Both H8 and H9 are explicitly deferred until H7 is resolved. If H7 confirms the trade-off is unacceptable (user needs drag-resize), H8 or H9 become the path forward.

### Iteration 7b — Production test result + H10 fix (2026-05-20)

**Production test result:** restarted production menubar with `enableCursorRects()` in `_make_nspanel()` (panel.py). I-Beam→Arrow transition does NOT appear on panel open. Probe with `--fix` DID show it.

**Asymmetry:** probe calls `panel.orderFront_(None)` (normal window show). Production calls `panel.orderFrontRegardless()` at toggle-open time (LSUIElement=1, no app activation). The two differ in AppKit's internal window-activation path.

**H10 hypothesis:** `orderFrontRegardless()` does not activate the app → AppKit re-disables cursor-rect dispatch on each show → `enableCursorRects()` called once at panel-create is not enough. Must be re-called after every `orderFrontRegardless()`.

**Fix:** one line added to `_PanelController.togglePanel_` in `src/menubar/app.py`, immediately after `orderFrontRegardless()`:

```python
app._panel.enableCursorRects()
# orderFrontRegardless doesn't activate the app → cursor-rect dispatch gets
# re-disabled on each show; re-enable explicitly (initial call in panel.py
# _make_nspanel covers first show only; this covers every subsequent open).
```

**Status:** committed; user tests by restarting production menubar via `launchctl kickstart` and hovering panel on open.

## launchctl bootstrap I/O Error (Recurring)

**Symptom:** `launchctl bootstrap gui/<uid> <plist>` fails with `Bootstrap failed: 5: Input/output error` on the first attempt — succeeds directly on the second attempt after 1-2s.

**Workaround in this session:** manual retry. Pattern: bootout → bootstrap (fails) → bootstrap (succeeds).

**Pending:** a worker builds `setup_menubar.py` with built-in 2nd-try retry logic. Should go into every plist-setup script for this project.

## Refactor Split (Module Isolation)

**Trigger:** bug iteration on cursor.py code required reading hotkey/focus/singleton context — concerns were mixed together. User's own words: "that's exactly the problem, that we can't work on bugs in isolation without breaking 1000 other things."

**menubar.py 590 LOC → 4 modules:** app.py (235), panel.py (259), hotkey.py (54), system.py (75). 15 imports → ≤6 per module. State distributed across concern modules.

**discover.py 501 LOC → 4 modules:** discover.py (179), ghostty.py (125), bg_timer.py (96), proc_cache.py (145). 8 imports → ≤6 per module. proc_cache.py as a leaf of the DAG.

Both splits are structural changes with no behavioral difference — the tick log post-merge shows `n=8 sessions` identically.

**Three-solution pattern for circular imports (split-menubar):**
- Lazy import in `system.run()` for `from .app import CCMenuBarApp` (breaks app→system→app)
- `bg_result` passed explicitly instead of re-scanned in the module (panel.py needs no discover import)
- Hotkey-API refactor: zero-arg callback instead of an app param (hotkey.py knows no app class)

## Refactor-Skill Extension

`/Users/brunowinter2000/Documents/ai/Meta/blank/skills/refactor/SKILL.md` extended with:

- **2.5b State Sprawl** — AST-count instance attrs per class (≥10 = flag). Would have caught CCMenuBarApp's 13 attrs.
- **2.5c Constant Concern-Clustering** — regex prefix-clustering (≥2 clusters of ≥3 each = flag). Would have caught the UI/SYSTEM/BADGE constants in menubar.py.
- **2.6 Operational Hygiene** — 3 sub-checks: ungated diagnostics, install friction (placeholder-tokens-no-setup-script), scattered application state.
- **2.7 Refactor Residue** — dead imports, scripts in the library tree, dev-tooling gap.

The phase-3 severity table extended accordingly. Written abstractly — no Monitor_CC examples in the skill definition.

## Tracking-Task Transition

The 3 remaining issues from a prior session (2026-05-12) → CLOSED. All 6 issues addressed (4-5 done in this session, 6 carried over).

A new follow-up tracking item was opened: cursor edges (deferred), kill button (carryover), refactor cleanup (a worker was active at session end), column alignment, operational-hygiene findings.

## Iteration 8 (2026-05-20) — NSTrackingArea cursorUpdate Pattern (FINAL)

### The breakthrough

GitHub search via skill (`sw33tLie/macshot` + `lifedever/PasteMemo-app`) found two converged references for cursor handling in non-key NSPanel windows:

| Ref | File | Pattern |
|---|---|---|
| `sw33tLie/macshot` | `RecordingHUDPanel.swift` | `.nonactivatingPanel + .borderless`, NSTrackingArea + `.cursorUpdate` + `.activeAlways` |
| `lifedever/PasteMemo-app` | `RelayFloatingWindowController.swift` | Same setup; adds `NSCursor.push()/.pop()` pattern |

Both repos use `.nonactivatingPanel + .borderless` (non-key windows), both use NSTrackingArea with `.cursorUpdate` + `.activeAlways`. PasteMemo adds `NSCursor.push()/.pop()` — essential because NSHostingView / NSTextField / NSButton call `super.cursorUpdate_` in their own mouse handlers and reset the cursor. `push()` on edge-enter + `pop()` on edge-exit maintains our cursor against child views that would otherwise override it.

Key insight: the tracking-area `.cursorUpdate` option fires `cursorUpdate_` regardless of key-window status when combined with `.activeAlways`. This is why the earlier `mouseMoved_` + `NSCursor.set()` approach failed — NSTextField/NSButton's `cursorUpdate_` (dispatched after the view hierarchy resolves) overwrote every `set()` call. The push/pop stack has higher precedence than `set()`.

### dev/ probe verification

`_TrackingContentView` added to `dev/cursor_edges/probe.py` under `--tracking` flag. Uses `NSTrackingCursorUpdate | NSTrackingMouseMoved | NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways | NSTrackingInVisibleRect`. `hitTest_` override claims L/R/bottom edge zones so child views don't intercept events at the edges.

Live tests (user-confirmed 2026-05-20):

| Command | Result | Interpretation |
|---|---|---|
| `probe.py --fix --tracking` | ✅ cursor `↔`/`↕` at L/R/Bottom edges | Pattern confirmed — push/pop + cursorUpdate_ works |
| `probe.py --tracking --no-resizable` | ❌ no cursor switch (only I-Beam→Arrow) | `enableCursorRects()` is the dispatch enabler even for the tracking pattern; without it, `cursorUpdate_` does not fire |

The `--no-resizable` result refutes the "drop NSWindowStyleMaskResizable" branch (Iteration 7 H7). We keep `NSWindowStyleMaskResizable` and `enableCursorRects()`. Custom drag-resize (`mouseDown_`/`mouseDragged_` in the probe) is NOT ported to production.

### src/ migration

**File changed:** `src/menubar/panel.py` — single file, 92 insertions / 14 deletions.

**What was replaced (cursor-rects path):**
- `resetCursorRects` method with its 4 `addCursorRect_cursor_` calls — deleted entirely
- Inline `EDGE = 8` inside `resetCursorRects` — promoted to module-level constant

**What was added (tracking pattern):**
- `import objc` (new top-level import)
- `NSTrackingActiveAlways`, `NSTrackingArea`, `NSTrackingCursorUpdate`, `NSTrackingInVisibleRect`, `NSTrackingMouseEnteredAndExited`, `NSTrackingMouseMoved` (AppKit imports)
- Module-level `EDGE = 8` and `_TA_TRACKING_OPTS` constant
- `_PanelContentView` methods: `initWithFrame_` (state init), `updateTrackingAreas`, `_cursor_for_edge`, `_set_hovered_edge` (push/pop), `_edge_for_point`, `cursorUpdate_`, `mouseMoved_`, `mouseExited_`, `hitTest_`

**What stayed unchanged (no src/ surgery needed):**
- `NSWindowStyleMaskResizable` in `_make_nspanel()` — kept
- `panel.enableCursorRects()` in `_make_nspanel()` — kept (required for tracking pattern too)
- `app._panel.enableCursorRects()` in `togglePanel_` (`src/menubar/app.py`) — kept (H10 fix, still required)

**Commit:** `c1f497d` on branch `cursor-migrate`

### Sources

- `sw33tLie/macshot` — `RecordingHUDPanel.swift` — GitHub: https://github.com/sw33tLie/macshot
- `lifedever/PasteMemo-app` — `RelayFloatingWindowController.swift` — GitHub: https://github.com/lifedever/PasteMemo-app

## Iteration 9 (2026-05-20) — FINAL: Accessory-App Cursor-Rect Dispatch Blocked

### Migration outcome

Tracking-area pattern, `hitTest_`, state-driven `resetCursorRects` + `invalidateCursorRectsForView_`, `_CursorlessButton` — alle implementiert und mechanisch korrekt. Events feuern perfekt in production:

| Signal | Count | Interpretation |
|---|---|---|
| `mouseMoved_` | 236 / session | Tracking area delivers correctly |
| `mouseEntered_`/`mouseExited_` | balanced | Area install correct |
| `_set_hovered_edge` transitions | 30 in 15s hovering | Edge detection working |
| `invalidateCursorRectsForView_` | 30 calls | Triggered on every state change |
| `resetCursorRects` | **3** — only at view creation / bounds-change | NOT triggered by invalidate calls |
| `cursorUpdate_` | **0** | Despite NSTrackingCursorUpdate option |

AppKit silently ignores dynamic cursor updates (both `invalidateCursorRectsForView_` and `cursorUpdate_` dispatch) in production context.

### Root cause: app activation policy

AppKit cursor-rect dispatch + `cursorUpdate_` fire when EITHER (a) `NSApp.activationPolicy = .regular` AND app active, OR (b) window is key. Production misses both: `LSUIElement=1` in plist → `.accessory`, `NonactivatingPanel` → never key.

| Factor | Probe | Production |
|---|---|---|
| Panel type | NonactivatingPanel | NonactivatingPanel |
| Launch | Terminal (`python3`) | `launchctl` |
| Info.plist | none | `LSUIElement=1` |
| `activationPolicy` | `.regular` (default) | `.accessory` |
| App active at start | Yes | Never |

GitHub refs (`sw33tLie/macshot`, `lifedever/PasteMemo-app`) provide the correct tracking pattern, but both are `.regular` apps — the pattern works there. In `.accessory` context, cursor-rect dispatch is fundamentally blocked at the AppKit level.

### Probe design lesson

Probe mirrored production **panel geometry** exactly but not **app activation context**. A faithful probe would have been launched as an `.app` bundle with `LSUIElement=1` via `launchctl` — the dispatch block would have surfaced immediately instead of after full production migration. Panel-faithfulness ≠ context-faithfulness.

### Status

Migration stands — no regression. Native `NSWindowStyleMaskResizable` drag-resize works as before. Cursor visual feedback at panel edges is not achievable in `LSUIElement` context without `NSApp.activateIgnoringOtherApps_(True)` (rejected: defeats `LSUIElement` semantics).

`_cursor_log` helper retained in `src/menubar/panel.py`, gated behind `MENUBAR_CURSOR_DEBUG=1` env var.

### Sources

- `rust-windowing/winit` — `winit-appkit/src/window_delegate.rs` line 1250 — `invalidateCursorRectsForView_` pattern (battle-tested for `.regular` apps)
- `rohanrhu/MacsyZones` — `MacsyZones/Layout.swift` line 648 — `areCursorRectsEnabled` override
- `/tmp/menubar-cursor.log` diagnostic data — 3 `resetCursorRects` vs 30 `invalidate` calls confirmed dispatch block
