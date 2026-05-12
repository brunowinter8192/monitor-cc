# Tool-Use Safety

## Status Quo (IST)

Tool-Use-Disziplin wird auf zwei Wegen erzwungen:

1. **`~/.claude/shared-rules/global/tool-use.md`** — 16 Hard Rules + Soft Rules. Text-basiert, prompt-injected via `SessionStart` hooks in `~/.claude/scripts/session-start-rule-inject.sh`. Werden auf jedem REQ-Prefix mitgesendet (kostet Input-Tokens, gecached). Mischung aus positiven Anleitungen ("Verwende X") und negativen Verboten ("Tu nicht Y").

2. **`dev/tool_use_analysis/rule_compliance.py`** (Monitor_CC, 2026-05-12) — Detection-Pipeline. Parst tool-use.md, scannt Proxy-JSONLs auf 8 von 16 Rules mit mechanischen Signaturen, reportet Compliance pro Rule + Uncategorized-Bucket. **Nur Detection, keine Prevention.** Output: Markdown-Report pro Run.

3. **Keine PreToolUse-Hooks** aktuell aktiv. `~/.claude/settings.json` hat `"hooks": {}` (leer). Frühere Hook-Konfiguration im Backup-File (`settings.json.hooks-backup`) zeigt working format für PreToolUse/SubagentStop/SessionStart/InstructionsLoaded.

## Evidenz

### Quantifizierung des `pkill -f`-Antipatterns (2026-05-12)

Run von `grep '"command":[^,]*pkill -f' src/logs/api_requests_*.jsonl` über 67 Proxy-Logs (Zeitraum 2026-05-06 18:20 — 2026-05-12 20:59, ≈6 Tage):

| Metric | Wert |
|---|---|
| Total `pkill -f` calls | 267 |
| Top concentration single session | 246 (searxng 2026-05-08) |
| Heutige Session (Monitor_CC) | 18 |
| Heutige Worker-Kills derselbe Antipattern | 3 (menubarfix, mbarfix2, mbarlive) |

### Worker-Kill-Mechanismus (verifiziert in dieser Session)

Worker-Prozess hat cmdline `claude.exe --model sonnet --dangerously-skip-permissions # Worker — <FULL PROMPT TEXT>`. Wenn Prompt-Text Strings wie `workflow.py --mode menubar` enthält (z.B. im Smoke-Test-Block), matcht `pkill -f "workflow.py --mode menubar"` AUCH den Worker-Prozess. SIGTERM → Worker tot mit Status 143.

3-malige Reproduktion in einer Session, davon einmal direkt NACH Selbst-Erklärung des Antipatterns → Disziplin ist nicht ausreichend, strukturelle Prävention nötig.

### rule_compliance.py-Output heute

Run auf heutige 4 Sessions (224 tool_use blocks):
- 4 von 16 Rules violated (Rule 3 grep scope, Rule 9 Read-before-Edit, Rule 12 sleep, Rule 13 .claire/ typo)
- 6 Uncategorized failures
- Report: `dev/tool_use_analysis/20260512_rule_compliance.md`

Wichtig: `pkill -f`-Antipattern wird von Rule 3 NICHT erfasst (Rule 3 zielt auf grep für Source-Code-Suche, nicht auf Process-Kill-Pipes). Aktueller Uncategorized-Bucket würde es enthalten falls als Failure (`is_error=True`) protokolliert — aber `pkill -f` SUCCEEDS typischerweise (exit 0) und schreibt nichts in tool_result. Damit ist es destructive-but-silent: keine error-Spur, nur Side-Effect.

## Recommendation (SOLL)

Pending — Migration vom rein-textuellen Rule-System zu hybridem System:

- **Hook-based prevention** für strukturell-erkennbare destruktive Patterns (`pkill -f`, `ps|grep|kill` chains). Block + Hinweis auf Alternative.
- **tool-use.md** wird auf positive Anleitungen reduziert ("verwende `pgrep -x <exact>`", "capture PID at launch in PID-File"). Negativregeln raus.
- **rule_compliance.py** bleibt für Detection von Pattern die NICHT mechanisch geblockt werden können (behavioral, judgment-required).

Konkret in nächster Session:
1. Erste Hook-Implementation: PreToolUse Bash matcher → script `~/.claude/scripts/block-dangerous-process-kill.py`. Block `pkill -f` + ps-grep-kill-Pipes. Allow `worker-cli kill`, allow direkter PID-Kill (`kill <numeric_pid>`).
2. Nuance-Design: distinguish intentional kill (CLI-wrapper, PID-direct) von accident (textual pattern match).
3. Cache-Cost dokumentieren: jeder Edit von `~/.claude/settings.json` invalidiert CC-Prefix-Cache → einmaliger Full-Rebuild pro Hook-Migration-Welle.
4. tool-use.md negative Rules entfernen sobald entsprechender Hook live + verifiziert.

## Offene Fragen

- Wie distinguish "intentional kill via PID" von "textual pattern match"? Heuristik: blocken wenn KILL-target via grep/awk-Pipe bestimmt wurde; allowen wenn PID direkt referenziert (numerisch oder `$(cat pid-file)`).
- Wie viele weitere Antipatterns sind Migration-Kandidaten? Erst nach Phase-1-Hook-Erfahrung beurteilen.
- Sollen Hook-Blocks zwingend hart blockieren oder optionaler "Warning + bestätige mit Y" Modus? — hart ist konsistenter, weniger Disziplin-abhängig.

## Quellen

- Bead `Monitor_CC-weyg` — tracker für die Hook-Migration
- `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md` — Discussion-Trail dieser Session
- `~/.claude/shared-rules/global/tool-use.md` — Quelle der aktuellen Hard Rules
- `~/.claude/settings.json.hooks-backup` — funktionierende Hook-Format-Referenz
- `dev/tool_use_analysis/rule_compliance.py` — Detection-Tool (committed 2026-05-12)
- `dev/tool_use_analysis/20260512_rule_compliance.md` — heutiger Compliance-Run-Output
