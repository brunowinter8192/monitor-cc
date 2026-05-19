# Menübar Overhaul Session — 2026-05-19

Iteration history und Process-Findings der Session in der die 5 verbleibenden zv6s-Issues abgearbeitet wurden + Modul-Split-Refactor + Skill-Erweiterung. Aktueller IST-Zustand des Codes lebt in `src/menubar/DOCS.md` (post-split: 8 Module). Diese Datei dokumentiert wie wir dahin kamen.

## Hook-basierte Activity Detection (löst Issue 1 / Thinking-Phase)

**Ausgangslage:** discover.py nutzte JSONL-mtime als Working-Indikator (≤10s = working). Während Opus reasont (Anthropic-side, kein streaming output) wird JSONL nicht aktualisiert → fälschlich "idle".

**Iteration 1 (vor dieser Session):** Proxy-Log-mtime als Override. Bedingung war `(now - proxy_mtime) <= 10s`. Funktionierte für die ersten 10s einer Thinking-Phase, danach idle.

**Iteration 2 (gleiche Session):** Bedingung korrigiert zu `proxy_mtime > jsonl_mtime AND (now - proxy_mtime) <= 300s`. Strukturelles Signal: Proxy schreibt Request-Entry bei Empfang BEVOR Response kommt → proxy_mtime steht ahead von jsonl_mtime während der gesamten Thinking-Phase. Hielt für ~30-120s Thinking-Phasen.

**Iteration 3 (final, diese Session):** User-Korrektur: "der proxy schreibt nur wenn reqs durchkommen, in thinking-phasen arbeitet das modell server-seitig bei Anthropic, da kommt nichts durch — wir müssen bewegungen im terminal erfassen". Pivot zu CC-Hook-System (UserPromptSubmit / Stop / StopFailure). Hook-writer.py schreibt Session-Status synchron zu `~/.monitor_cc_menubar_hooks.json`, discover.py liest mit Priority-1 (über JSONL und Proxy-Override). Window zwischen UserPromptSubmit und Stop = working — deckt Thinking + Tool-Use + Response vollständig ab.

**Implementierungs-Detail:** Hook-setup-Script (`src/menubar/hook_setup.py`) installiert idempotent in `~/.claude/settings.json`. Hooks aktivieren erst bei CC-Restart (Catch: aktuelle CC-Session des Users feuert keine Hooks bis sie neu startet).

**Quelle für den Pattern:** github.com/onikan27/claude-code-monitor — gleicher Ansatz für menubar-Tracker mit Ink-basiertem TUI.

## launchd PATH Gotcha (löst Worker-Display-Bug)

**Symptom:** Worker werden in discover NICHT angezeigt (n=2 statt n=6 in Tick-Log). Aus Terminal-CLI sieht discover sie korrekt.

**Investigation:** Tick-Diagnostik in `_tick()` zeigte `n=2 sessions=['Monitor_CC', 'wise2627']`. discover-CLI-Test gab n=6. Unterschied: launchd-spawned vs Terminal-spawned Python.

**Root Cause:** launchd's default PATH = `/usr/bin:/bin:/usr/sbin:/sbin`. Tmux at `/opt/homebrew/bin/tmux` ist NICHT drin. `_tmux_session_exists()` ruft `tmux has-session` → command not found → returns False → Worker filtered out in `_process_project_dir`.

**Fix:** `EnvironmentVariables/PATH` in plist gesetzt auf `/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`. Deckt arm64-Homebrew + Intel-Fallback ab.

**Lesson:** launchd-spawned scripts erben NICHT user-shell PATH. Jeder Subprocess-Call mit nicht-system-Binary muss entweder absoluten Pfad nutzen oder via plist-Env explizit PATH setzen.

## Restart-Button doesn't kill old process (löst Doppel-Bar-Icon)

**Symptom:** Restart-Button klick → zwei Bar-Icons sichtbar. Alter Process überlebt, neuer wird zusätzlich gespawnt.

**Investigation:** Restart rief `launchctl kickstart -k gui/<uid>/<label>`. Das `-k` Flag sendet SIGTERM. Python-Signal-Handler werden von NSApp-Runloop blockiert. Process stirbt nicht, launchd spawnt neuen (KeepAlive=true).

**Fix:** Restart via `os.execv(sys.executable, [sys.executable] + sys.argv)` — In-place-Replace, gleicher PID, atomic. Kein launchd-Detour, kein Race. fcntl-Lock muss FD_CLOEXEC haben damit der neue execv den Lock re-acquiren kann.

**Bonus:** Singleton-Enforcement via fcntl-Lock in `_acquire_singleton_lock()` verhindert parallele Spawns aus anderen Quellen. Exit-Code 0 wenn Lock besetzt — sonst respawnt launchd KeepAlive endlos.

## Panel-Grow-Only Resize Semantik (löst Worker-disappear-on-status-change)

**Symptom:** Während User mit Opus tippt verschwinden Worker-Zeilen aus dem Panel, kommen später wieder.

**Root Cause:** `_truncate_and_height` mit atomic-Logik (`continue` statt `break`) skippte ganze Projekte wenn Panel zu klein. Bei jedem Status-Flip triggerte `_tick` ein `_rebuild_panel` → Re-Truncation → Monitor-CC-Gruppe (3 Sessions) passte plötzlich nicht mehr → komplett raus.

**Fix Iterations:**

**v1:** Atomic-truncation eingebaut (continue statt break). Aber: Status-Change triggert Rebuild → Truncation re-rechnet → Workers verschwinden trotzdem wenn Panel zu klein.

**v2 (final):** Truncation komplett entfernt. Panel-Größe wird:
- `max(user_dragged_height, content_required_height)` 
- Wächst bei neuen Workers (content_required_height steigt)
- Shrinkt nie (user_dragged_height bleibt als Floor)
- Status-Change: nur badges via `_update_panel_inplace`, KEIN Rebuild, KEIN Resize

`_panel_max_height` umbenannt → `_panel_min_height` (semantisch korrekter Floor statt Cap). `_hidden_count` und `· N hidden` Auto-Jump-Label-Suffix entfernt — kein Hidden-Konzept mehr nötig.

## NSPanel Cursor Rabbit Hole (4 Iterationen, DEFERRED)

**Symptom:** Hover über Panel-Edges zeigt keinen Resize-Cursor (`↕`/`↔`). Bottom funktioniert teilweise (I-Beam switcht zu Arrow), Sides nicht.

**Iteration 1:** Hypothese `setAcceptsMouseMovedEvents_(True)` fehlt. Eingebaut → 3441 mouseMoved fires geloggt → trotzdem visuell I-Beam.

**Iteration 2:** NSView-Subclass `_PanelContentView` mit `updateTrackingAreas` Override, owner=self. Konfirmierte dass mouseMoved feuert via per-Iteration Log. Cursor visuell unverändert.

**Iteration 3:** Switch von mouseMoved-NSCursor.set zu kanonischem resetCursorRects-Pattern. NSTextField-Subclass `_CursorlessLabel` mit no-op resetCursorRects gegen I-Beam-Override. Bottom-Edge funktionierte plötzlich, Sides immer noch I-Beam.

**Iteration 4 (Diagnose):** Detailliertes Logging (x, y, w, branch). Branch `left-right` feuerte 92x bei x<8 oder x>372, aber Cursor visuell nicht gewechselt. Root Cause: Layout deckt Edge-Regionen mit NSStackView/Footer/Top-Bar ab. Unsere cursor rects auf `_PanelContentView` greifen NUR wenn Mouse über LEERE contentView-Pixel ist. Edge-Strips sind covered.

**Status:** DEFERRED (NICHT accepted). Nächste Session nach Refactor: NSPanel-sendEvent-Override-Pattern probieren ODER cursor-rects auf jeden Leaf-Subview installieren. Aktuell drag-resize funktioniert weiterhin — nur visuelle Anzeige fehlt.

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

## launchctl bootstrap I/O Error (Recurring)

**Symptom:** `launchctl bootstrap gui/<uid> <plist>` failed mit `Bootstrap failed: 5: Input/output error` beim ersten Versuch — beim zweiten Versuch direkt nach 1-2s success.

**Workaround in dieser Session:** Manuelles Retry. Pattern: bootout → bootstrap (fails) → bootstrap (succeeds).

**Pending:** Worker C baut `setup_menubar.py` mit Built-in 2nd-try-Retry-Logic. Sollte in jedes plist-Setup-Skript für dieses Projekt rein.

## Refactor-Split (Modul-Isolation)

**Anlass:** Bug-Iteration auf cursor.py-Code erforderte Reading von hotkey/focus/singleton context — Concerns vermischt. User-O-Ton: "das ist nämlich genau das problem das wir nicht isoliert an bugs arbeiten ohne 1000 sachen zu brechen".

**menubar.py 590 LOC → 4 Module:** app.py (235), panel.py (259), hotkey.py (54), system.py (75). 15 Imports → ≤6 pro Modul. State distributed über Concern-Module.

**discover.py 501 LOC → 4 Module:** discover.py (179), ghostty.py (125), bg_timer.py (96), proc_cache.py (145). 8 Imports → ≤6 pro Modul. proc_cache.py als Blatt des DAG.

Beide Splits sind Strukturchanges ohne Behavioral Difference — Tick-Log post-merge zeigt `n=8 sessions` identisch.

**Drei-Lösungen-Pattern bei circular import (split-menubar):**
- Lazy import in `system.run()` für `from .app import CCMenuBarApp` (bricht app→system→app)
- `bg_result` explizit übergeben statt im Modul re-scannen (panel.py braucht keinen discover-Import)
- Hotkey-API refactor: zero-arg callback statt app-Param (hotkey.py kennt keine app-Klasse)

## Refactor-Skill Erweiterung

`/Users/brunowinter2000/Documents/ai/Meta/blank/skills/refactor/SKILL.md` erweitert um:

- **2.5b State Sprawl** — AST-Count Instance-Attrs pro Klasse (≥10 = flag). Hätte CCMenuBarApp 13 Attrs gefangen.
- **2.5c Constant Concern-Clustering** — Regex prefix-clustering (≥2 Cluster je ≥3 = flag). Hätte UI/SYSTEM/BADGE constants in menubar.py gefangen.
- **2.6 Operational Hygiene** — 3 Sub-Checks: ungated diagnostics, install friction (placeholder-tokens-no-setup-script), scattered application state.
- **2.7 Refactor Residue** — dead imports, scripts in library tree, dev-tooling gap.

Phase 3 Severity-Tabelle entsprechend ergänzt. Abstract formuliert — keine Monitor_CC-Beispiele in der Skill-Definition.

## Bead-Übergang

`Monitor_CC-zv6s` (3 remaining issues from 2026-05-12) → CLOSED. Alle 6 Issues addressed (4-5 done in dieser Session, 6 als carryover).

`Monitor_CC-q6e5` (NEW): Follow-ups inklusive Cursor-Edges (deferred), Kill-Button (Issue 6 carryover), Refactor-Cleanup (worker C aktiv beim Session-Ende), Column-Alignment, Operational-Hygiene findings.
