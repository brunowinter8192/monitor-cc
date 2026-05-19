# 2026-05-20 — `pkill -f` Recurrence Mid-Implementation

Fortsetzung von `2026-05-12_session_findings.md`. Während der Implementations-Vorbereitung des `pkill -f`-Block-Hooks selbst (gleiche Session) reproduzierte sich der Antipattern — concrete Evidenz dass strukturelle Prävention nötig ist, weil Disziplin nicht skaliert.

## Vorfall

Während laufender Cursor-Edges Investigation:

- Foreground-Probe `dev/cursor_edges/probe.py` lief im Background-Bash, sollte gekillt werden vor Worker-Folge-Send
- Opus rief: `pkill -f "cursor_edges/probe.py"`
- Pattern matchte den Python-Interpreter-Prozess UND zusätzlich den `claude.exe` Worker-Prozess `worker-Monitor_CC-cursor-fix`, weil dessen Command-Line den Worker-Prompt-Inhalt enthält der mehrfach `"cursor_edges/probe.py"` als Substring referenziert
- Worker `cursor-fix` SIGTERM, exited bei 72% Context
- Verlorenes Context-Budget: 72% Restkapazität + bereits aufgebauter Cursor-Edges Mental Model
- Recovery: kill-cleanup über `worker-cli kill cursor-fix`, fresh-spawn `leaf-rects` als Ersatz

`worker-cli list` Output direkt nach dem Vorfall:
```
cursor-edges: exited 66%
cursor-probe: unknown
cursor-fix: exited 72%
```

## Korrekter Kill-Pattern wäre gewesen

```bash
pkill -f "venv/bin/python3 dev/cursor_edges/probe.py"
```

Der Interpreter-Pfad als Anker macht das Pattern eindeutig — claude.exe matcht das nicht, weil dort kein `venv/bin/python3` in der Command-Line steht. Aber: auch dieses präzisere Pattern ist fragil. Der Hook blockt den `pkill -f`-Aufruf unabhängig vom Pattern-Tightness, weil cmdline-Substring-Matching bei beliebigem Pattern unsicher ist sobald Worker-Prompts beliebige Text-Snippets enthalten.

## Konvergenz mit 2026-05-12-Befund

Beide Vorfälle, sechs Tage Abstand, identisches Muster:

- `pkill -f <substring>` mit dem Ziel einen Python/Tool-Prozess zu killen
- cmdline-Substring matched zusätzlich claude.exe Worker dessen Prompt das Substring als Text enthält
- Worker SIGTERM, Context-Verlust
- Recovery via fresh-spawn

Aus `2026-05-12_session_findings.md`:

> "Kritisch: das Pattern feuerte direkt nach Selbst-Erklärung des Antipatterns. Disziplin reichte nicht — strukturelle Prävention nötig."

Heute identisch: nach dem 2026-05-12-Befund war das Hook-Design schon dokumentiert + im Bead `weyg` als TODO. Opus kannte das Risiko und reproduzierte das Antipattern trotzdem. Disziplin-Layer ist nachweislich unzureichend.

## Bekannte erlaubte Kill-Pfade (unverändert seit 2026-05-12)

| Pattern | Erlaubt? | Begründung |
|---|---|---|
| `worker-cli kill <name>` | ja | Wrapper kennt Worker-Namen → tmux session-name → exact-kill |
| `kill <numeric_pid>` | ja | Direkt-PID-Referenz, kein Substring-Matching |
| `kill -SIGNAL <pid>` | ja | Selbe Direkt-PID-Logik |
| `pkill -x <exact_name>` | ja | Exact-Match-Flag, kein Substring |
| `launchctl bootout`, `kickstart` | ja | Service-spezifisch über Label |
| `pkill -f <substring>` | **nein** | Substring-Match auf cmdline, trifft Worker mit dem Substring im Prompt |
| `ps … \| grep … \| kill …` | **nein** | Selbes Substring-Problem |

## Status der Implementation

- Dispatch: Worker `safety-hooks` baut `src/hooks/block_dangerous_kill.py` + `src/hooks/hook_setup.py` + `src/hooks/DOCS.md` + `decisions/pipe0?_safety_hooks.md`
- Registrierung: global in `~/.claude/settings.json` mit absolutem Pfad (kein Plugin)
- Erste live-Verifikation: nach Setup-Run einen `pkill -f`-Aufruf versuchen, exit 2 + stderr-Alternative erwarten

Wenn der Hook nach diesem Vorfall funktioniert, sind beide historischen Vorfälle (12.05 + 20.05) der Auslöser für strukturelle Korrektur die alle künftigen Reproduktionen verhindert.

## Quellen

- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — initiale Quantifizierung (267 calls in 6 Tagen), Hook-Design-Vorschlag, Allow/Block-Nuance
- Bead `Monitor_CC-weyg` — Migrations-Tracker "Negativregeln raus aus tool-use.md, in Hooks rein"
- anthropics/claude-code `plugins/security-guidance/hooks/security_reminder_hook.py` — PreToolUse-Reference-Pattern (matcher, stdin-JSON-Format, exit-Codes)
- `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/Hooks_Reference/AntrophicDocs.md` — Hooks Reference (settings.json structure, matcher semantics, exit-code semantics)
