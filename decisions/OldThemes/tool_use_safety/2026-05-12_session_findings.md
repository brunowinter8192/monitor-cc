# Tool-Use Safety — Session 2026-05-12

## Was passierte in der Session

Drei Beobachtungen in einer Session bauten den Bead `Monitor_CC-weyg` und das Thema "Tool-Use Safety" auf.

### 1. RAG-First-Rule durchsetzen

Mid-Session-Code-Exploration auf src/menubar umging die RAG-First-Mandat aus `workers-1.md` § PLAN Step 2. Grund: PLAN Step 2 ist als Teil des formalen PLAN-Zyklus formuliert; mid-session "Scope Extension During IMPLEMENT" mini-scoping erwähnte RAG nicht. Opus sprang direkt zu `find` + `Read src/menubar/menubar.py` + `Read src/menubar/discover.py` (~580 LOC) statt erstmal `src/menubar/DOCS.md` via RAG zu lesen (~500 Tokens, klare Modulübersicht).

→ Neue Rule "RAG-First on Code Exploration (NON-NEGOTIABLE)" in `workers-1.md` § Core Rules + Anker in `workers-2.md` § Scope Extension Mini-scoping. Live in Production (`~/.claude/shared-rules/opus/workers-1.md`, workers-2.md).

### 2. Worker-Kill durch grep-on-cmdline-Antipattern

Dreimal in dieser Session denselbe Worker-Tod-Mechanismus:

| Worker | Zeitpunkt | Methode |
|---|---|---|
| menubarfix | 2026-05-12 ~17:30 | `ps -A \| grep "workflow.py --mode menubar" \| awk \| xargs kill` |
| mbarfix2 | 2026-05-12 19:42 | gleiches Pattern |
| mbarlive | 2026-05-12 ~20:15 | `pkill -f "workflow.py --mode menubar"` |

Root-Cause-Mechanik: Worker-Prozess hat `claude.exe --dangerously-skip-permissions # Worker — <FULL PROMPT TEXT>` als cmdline. Prompt-Text enthält oft Strings wie `workflow.py --mode menubar` (z.B. im Smoke-Test-Block). `grep`/`pkill -f` matcht gegen volle cmdline → Worker stirbt mit SIGTERM (Status 143 = 128+15).

Konvergenz mit `extract_failed.py` Output für heute: 1 Rule-9-Verletzung (`File has not been read yet`), 2 Rule-3-Verletzungen (broad recursive grep), 11 Rule-12-Verletzungen (sleep in worker-cli-send-Prompts — vermutlich False-Positive durch Heredoc-Content matching), 3 Rule-13-Verletzungen.

**Kritisch:** das Pattern feuerte direkt nach Selbst-Erklärung des Antipatterns. Disziplin reichte nicht — strukturelle Prävention nötig.

### 3. Quantifizierung über 67 Logs / 6 Tage

```
ALL src/logs/api_requests_*.jsonl (2026-05-06 → 2026-05-12):
- 267 `pkill -f` Calls insgesamt
- 246 davon konzentriert in EINER Session (searxng 2026-05-08)
- 18 in heutiger Session 2026-05-12
- 9 in Monitor_CC 2026-05-09
```

Burst-artiger Konzentration: 246/267 = 92% aus einem Tag → wenn der Antipattern losgeht, geht er viele Male los. Mit Hook eingebaut hätten wir alle 246 vermieden.

## Hook-Design-Vorschlag (deferred)

Geplant aber NICHT umgesetzt — kommt in nächste Session:

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      { "type": "command",
        "command": "~/.claude/scripts/block-dangerous-process-kill.py",
        "timeout": 5 }
    ]
  }
]
```

Script-Logik: liest tool_input.command von stdin (JSON), regex-Check auf `pkill -f` + `ps.*grep.*kill`-Pipes, bei Match → stderr mit Alternativen (PID-File, `pgrep -x` exact-comm) + exit 1 zum Block.

### Komplikation — intentional kill

User-Feedback: "manchmal haben wir ja auch worker absichtlich gekillt". Bedeutet das Design braucht Nuance:

- `worker-cli kill <name>` ist intentional + sicher → soll erlaubt bleiben
- Manuelle Process-Cleanup (PID bekannt, gezielter Kill) → soll erlaubt sein
- `pkill -f <pattern>` → blocken weil cmdline-substring matching ist unscharf
- `ps | grep | kill`-Pipe → blocken

Heuristik vermutlich: blockieren wenn das KILL-Target via TEXTUELLEM MATCH (grep) bestimmt wurde statt via PID-Direktreferenz oder kontrolliertem CLI-Wrapper. Konkrete Implementierung in nächster Session.

### Cache-Cost-Hinweis

Edit auf `~/.claude/settings.json` zur Hook-Aktivierung bustet den CC-Prompt-Cache (full message rebuild auf nächstem REQ). Wie bei RAG-First-Rule-Edit heute. User hatte explizit zugestimmt — gleiche Logik beim Hook-Edit.

## Übergeordnetes Konzept

User-Vorschlag (in Bead Monitor_CC-weyg festgehalten): `tool-use.md` strukturell aufteilen.

- "Wie du vorgehen sollst" → bleibt in tool-use.md (positive Anleitungen)
- "Wie du NICHT vorgehen sollst" → wandert in Hooks (strukturelle Prävention)

Vorteile:
- Spart Input-Tokens jeder REQ (weniger Rule-Text)
- Strukturell zuverlässig statt disziplin-abhängig
- Antipatterns die wir nicht selbst diszipliniert vermeiden können (siehe heutige 3-fach-Reproduktion) sind so unmöglich

Migration-Pfad (nächste Session): erste Welle 1-2 klare Antipatterns (`pkill -f`-Block) implementieren, entsprechende Negativregeln aus tool-use.md raus, Erfahrung sammeln, dann weitere.

## Status der Session

- Bead `Monitor_CC-weyg` offen für Migration-Arbeit
- rule_compliance.py committed in Monitor_CC dev (`dev/tool_use_analysis/rule_compliance.py`)
- Heute-Report: `dev/tool_use_analysis/20260512_rule_compliance.md`
- Hook-Design diskutiert + Deferral entschieden
- Menubar live-update Fix in Arbeit (separat von Tool-Use Safety)

## Quellen

- Bead `Monitor_CC-weyg` (tracker für Migration)
- `~/.claude/shared-rules/global/tool-use.md` (Ziel der Migration)
- `~/.claude/settings.json.hooks-backup` (working hook-Format Referenz vom User)
- Proxy-Logs `src/logs/api_requests_*.jsonl` 2026-05-06 bis 2026-05-12 (Quantifizierungs-Quelle)
