# Menubar Focus — cwd-Drift Bug (2026-05-27)

## Symptom

Cmd+digit Hotkeys (Cmd+1..9) lösen für manche Main-Sessions keinen Focus-Jump aus. Konkret beobachtet: Cmd+1 (Monitor_CC) und Cmd+4 (searxng) springen sofort zum Ghostty-Terminal; Cmd+2 (Reddit) und Cmd+3 (Trading) tun nichts sichtbares.

Carbon-Handler-Reception + App-Callback fires sind für ALLE vier Sessions korrekt (sichtbar im neuen `src/logs/menubar.log` Hotkey-Logging, Commit `b840f16`).

## Evidenz

**Hotkey-Log (src/logs/menubar.log):**
- Jeder Press generiert `[hotkey] cmd+N` (Carbon-Layer) + `[hotkey] cmd+N → focus <cwd>` (App-Layer)
- cwd-Werte für [1] und [4]: Project-Root (`/Users/.../Monitor_CC`, `/Users/.../searxng`) → Focus klappt
- cwd-Werte für [2] und [3]: tiefe Subdirs (`/Users/.../Reddit/dev/subreddit_discovery/08_layer4_top5_per_sub_reports`, `/Users/.../Trading/concepts/phase_b_signal_exploration/ai/plots/01_signal_exploration`) → Focus läuft ins Leere

**Focus-Log (`/tmp/monitor_cc_menubar_focus.log`):**
- [1]/[4]: `OK id=<UUID>` — Path A in `_focus_session()` (Ghostty-UUID-Lookup) hat gegriffen
- [2]/[3]: `OK cwd=<deep-subdir>` — Path A liefert None, fällt auf Path B (AppleScript `focus first terminal whose working directory is "<cwd>"`); Path B's `try/on error/end try` swallowt den No-Match silent, returnt rc=0 — daher fälschlich "OK"

**JSONL-Inspection (Trading-Session):**
- Letzte Einträge (`type=assistant`, `type=system`) enthalten alle das gleiche `cwd`-Feld mit der TIEFEN Subdirectory
- CC schreibt in JEDE Message-Zeile das aktuelle Working-Directory zum Zeitpunkt des Eintrags
- Sobald User in der CC-Session via Bash `cd <subdir>` ausführt, "wandert" das cwd-Feld in nachfolgende JSONL-Zeilen

## Root Cause

`_cwd_from_jsonl()` (`src/menubar/discover.py` L63) liest die letzten 10 JSONL-Einträge und returnt das letzte populated `cwd`-Feld. Das ist die "aktuelle Position" der Session — semantisch der Wert für "wo arbeitet die Session jetzt", aber NICHT der Launch-cwd des Terminals.

`_cc_proc_cache` keyed by claude-PID, value `(tty, proc_cwd)`. `proc_cwd` ist der laufende OS-Process-cwd, der sich während der Session NICHT ändert (User-`cd` läuft in Bash-Subprocess, exit). Heißt: proc_cwd = Launch-cwd = stabil.

Ghostty-Terminal-UUID-Lookup in `_tty_for_cwd()` (`src/menubar/ghostty.py` L120) macht EXAKT-Match zwischen passed-cwd und proc_cwd. Passed-cwd = JSONL-cwd (drifted). proc_cwd = Launch-cwd. Mismatch ist strukturell für jede Session in der User je `cd`'d hat.

## Launch-Pattern Invariant

User startet alle Main-Sessions via `./src/claude_proxy_start.sh --project <ROOT>`. Das Script:
- `cd "$PROJECT"` vor `claude` Invocation (L238)
- garantiert dass CC-Prozess-cwd = PROJECT-Root
- CC's encoded JSONL-Dir = encode(launch_cwd) per CC-Pfad-Encoding (`/`, `_`, `.` → `-`)

Heißt: für jede Main-Session können wir das Mapping `encoded_dir → launch_cwd` via Iteration über `_cc_proc_cache` rekonstruieren — für jeden Pid `encode(proc_cwd)` berechnen und mit encoded_dir vergleichen → Match liefert den kanonischen Launch-cwd.

**Weitere Invarianten (user-confirmed):**
- Nie 2 Main-Sessions im selben Projekt
- Nie 2 Main-Sessions auf demselben Desktop
- Workers leben per Definition immer in `.claude/worktrees/<name>` Subdirs → eigene encoded_dirs, kein Konflikt mit Main-Mapping

## Fix-Entscheidung (pending Dispatch)

**Primär — discover.py `_process_project_dir()` Main-Branch:**
- Nach dem `is_worker == False` Branch: SessionInfo.cwd nicht via `_cwd_from_jsonl()` sondern via neuer Helper `_proc_cwd_for_encoded_dir(encoded_dir, cc_proc_cache)` setzen
- Helper iteriert `_cc_proc_cache`, encodet jeden `proc_cwd`, vergleicht mit `encoded_dir`, returnt match
- Fallback bei keinem Match (Stale-Process, race): bestehendes `_cwd_from_jsonl()` Verhalten

**Härtung — system.py `_focus_session()` Path B:**
- AppleScript `try/on error number errnum from ... end try` Block so umbauen dass No-Match-Errors detektiert und propagiert werden
- Bei Miss: focus-log Eintrag `MISS cwd=<...> reason=no-terminal-with-this-pwd` statt fälschlich `OK`

## Konsequenzen

- Display-Name (`os.path.basename(SessionInfo.cwd)`) stoppt zu wandern → [3] heißt im Menubar wieder `Trading` statt `01_signal_exploration`
- Hook-Writer Queue-Delivery (auch Konsument von `get_ghostty_terminal_id`) profitiert transparent — der Bug hat dort vermutlich unentdeckte Edge-Cases erzeugt
- Workers bleiben unverändert: ihr JSONL-cwd wandert in der Praxis nicht außerhalb der Worktree-Pfade, und `_worker_tmux_session()` (`src/menubar/discover.py` L109) partitioniert auf `/.claude/worktrees/` und bleibt damit robust

## Phase B — Implementation (2026-05-27)

### Was implementiert wurde

**Fix 1 — `src/menubar/discover.py`:**
- Added `encode_project_path` to top-level import from `..session_finder`
- New helper `_proc_cwd_for_encoded_dir(encoded_dir)`: iterates `_cc_proc_cache`, calls `encode_project_path(proc_cwd)` per entry, returns `proc_cwd` on match, `None` if no running CC process matches
- `_process_project_dir()` Main-branch: replaced `cwd = _cwd_from_jsonl(jsonl)` with `cwd = _proc_cwd_for_encoded_dir(encoded_dir) or _cwd_from_jsonl(jsonl)`
- Workers unverändert (is_worker branch stays on JSONL cwd)

**Fix 2 — `src/menubar/system.py`:**
- Path B AppleScript: added `return "MATCH"` on success + `on error errMsg number errNum → return "MISS:" & errNum & ":" & errMsg` instead of silent `end try`
- Result parsing: `out.startswith('MISS:')` → logs `MISS {label} reason={...}`; `r.returncode != 0` → logs `ERR`; else `OK`
- Path A unverändert (no try/on error, no MATCH token) — `elif out.startswith('MISS:')` hits only Path B

**Import smoke-test:**
```
./venv/bin/python -c "from src.menubar.discover import _proc_cwd_for_encoded_dir; print('OK')"
# → OK
```

### Verifikation (user-seitig nach Menubar-Restart)

```bash
launchctl kickstart -k gui/$(id -u)/com.brunowinter.monitor_cc_menubar
```

1. Menubar öffnen → `[2]` sollte `Reddit` heißen, `[3]` sollte `Trading` heißen (statt Subdir-Namen)
2. Cmd+2 drücken → Reddit-Terminal sollte focusen
3. Cmd+3 drücken → Trading-Terminal sollte focusen
4. `tail src/logs/menubar.log` nach Press → cwd in `[hotkey] cmd+N → focus <cwd>` sollte Project-Root sein, nicht Subdir
5. `/tmp/monitor_cc_menubar_focus.log` → Path A Entries (`OK id=<UUID>`) für alle Mains die im proc-cache sind; Path B Entries nur im Edge-Case (stale process), dann `MISS` statt false `OK`

## Quellen

- `src/menubar/discover.py:_cwd_from_jsonl`, `_process_project_dir`, `_classify_encoded_dir`
- `src/menubar/ghostty.py:_tty_for_cwd`, `get_ghostty_terminal_id`
- `src/menubar/system.py:_focus_session`
- `src/menubar/proc_cache.py` (`_cc_proc_cache`-Struktur)
- `src/claude_proxy_start.sh` (Launch-Pattern Garant)
- `src/logs/menubar.log` (Hotkey + Abort live data)
- `/tmp/monitor_cc_menubar_focus.log` (Focus-Attempts)
