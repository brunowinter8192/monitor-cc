# Block Parallel Bash Timer — Hook Design Rationale (2026-05-25)

**Topic:** Neuer Hook `block_parallel_bash_timer.py` der den Silent-SIGTERM-Fail verhindert wenn Opus in derselben Response einen Sleep-Timer UND einen weiteren Bash-Call dispatched.

---

## Triggering Evidence

RAG-Session 2026-05-25 ~20:46. Opus dispatched in EINER Assistant-Response zwei getrennte Bash-tool_use-Blocks:

```
Block 1 (foreground): worker-cli send eval-sweep2 "<Go Phase B prompt>"
Block 2 (background, run_in_background=true): sleep 480 && echo "8min check eval-sweep2 Phase B"
```

Beobachtetes Verhalten: erster Block lief durch (worker-cli send committete sauber), zweiter Block kam mit Exit 143 (SIGTERM) zurück. Der Timer wurde stumm gekillt bevor er starten konnte.

Konsequenz im Workflow: Opus dachte "Timer läuft, ich warte" und ging in Idle. Tatsächlich gab es keinen wartenden Timer — der Worker arbeitete weiter, aber Opus hatte keine Wake-Up-Quelle. Der User merkte irgendwann manuell dass der Worker schon idle ist, und musste "idle" tippen um Opus zu wecken. Reiner Observability-Verlust.

Bestehende Hooks katchten das Problem NICHT:
- `block_unauthorized_background.py` sieht nur einzelne tool_input-Commands — kann die Beziehung zwischen mehreren Bash-tool_uses in derselben Response nicht erkennen
- `rewrite_chained_sleep.py` operiert auf einem einzelnen Command-String und strippt nur triviale Sync-Sleeps innerhalb desselben Commands
- Beide Hook-Klassen waren strukturell unfähig für cross-tool_use Detection

`hook_firing.jsonl` bestätigt die Vorgeschichte: vor dem SIGTERM-Event wurde der Timer-Command von `block_unauthorized_background` rewritten (`run_in_background: true → false`), weil mein typisches Timer-Format `sleep N && echo "<quoted-string>"` nicht der strikten Canonical-Regex `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+done\s*$` entspricht. Der Timer lief also bereits als Foreground-Block. Aber da er der zweite Bash-tool_use in der Response war, kassierte er bei Dispatch das SIGTERM.

---

## The Real Failure Mode

CC's tool_use-Dispatcher kann pro Assistant-Response nur EINEN Bash-tool_use parallel verarbeiten. Werden zwei Bash-tool_use-Blocks in derselben Response gefunden, wird der zweite mit SIGTERM gekillt. Der Mechanismus existiert wahrscheinlich um Race-Conditions zu verhindern (cwd-shared state, sequential dependency).

Für die meisten Bash-Pairs ist das Verhalten LAUT: zweiter Block returnt exit 143, Opus sieht den Failure im Tool-Result, kann reagieren. Damage gering — Opus retried oder splittet.

Bei Sleep-Timern ist das Verhalten STUMM in der Wirkung: Opus erwartet von einem Background-Timer keinen sofortigen Return (er soll ja warten und später echo'en). Der SIGTERM-Kill produziert zwar denselben exit 143, aber semantisch verarbeitet Opus das als "Timer wurde gestartet" und geht in Idle. Erst beim ausbleibenden Wake-Up wird der Fehler offensichtlich — oft viele Minuten später wenn der User selbst nachfragt.

Das ist die eigentliche Damage-Klasse: **stumme Beobachtungs-Lücke statt lautem Fehler**.

---

## Detection Strategy

Strukturell anders als alle bestehenden Bash-Hooks: nicht Pattern-Match im einzelnen Command, sondern Cross-Tool_use Counting in der laufenden Assistant-Message.

Der PreToolUse-Hook bekommt im Payload den `transcript_path` — den Pfad zum JSONL-Transcript der aktuellen CC-Session. Beim Feuern des Hooks ist die aktuelle Assistant-Message bereits vollständig in das JSONL geschrieben (sonst würden die anderen Hooks die ebenfalls den Transcript brauchen könnten nicht funktionieren — wobei tatsächlich keiner der existierenden Hooks bislang `transcript_path` nutzt, dieser Hook ist der erste).

Workflow:

1. Parse stdin-Payload → tool_input.command, transcript_path
2. Lade JSONL, suche von hinten die jüngste `type: "assistant"` Entry
3. In deren `message.content` Array filter alle `type: "tool_use"` mit `name: "Bash"`
4. Wenn Count < 2 → allow (single Bash, kein Konflikt)
5. Wenn Count ≥ 2: check ob mindestens einer der Bashes der Timer-Form entspricht
6. Wenn ja → block (exit 2 + Stderr), sonst allow

Timer-Form-Regex: `^\s*sleep\s+\d+(?:\.\d+)?\s*&&\s*echo\s+\S.*$`. Loser als die strikte Canonical-Regex aus `block_unauthorized_background` (welche `echo done` literal verlangt) — matcht alle realistischen Timer-Formen die Opus tatsächlich emittiert, inklusive `echo "8min check"` mit gequoteten String-Argumenten. Anchor `^...$` schließt false-positives auf zitierten Timer-Text in anderen Commands aus: `echo 'sleep 60 && echo done'` matcht nicht weil `^` auf `echo` triggert nicht auf `sleep`.

---

## Why Narrow

Erste Vorüberlegung war: "blocke jedes Pair von 2+ Bash-tool_uses in einer Response, weil das gegen Rule 6 in tool-use.md verstößt". User hat das verworfen: das wäre ein viel zu breiter Hook der die echte Damage-Klasse mit unzähligen harmlosen Cases mischt.

Konkret harmlos (nicht zu blocken):
- Zwei worker-cli-Calls in derselben Response: einer kriegt SIGTERM, aber lautes Feedback, Opus reagiert sofort
- Ein git-Call + ein Status-Check parallel: zweiter failed laut, kein Information-Loss
- Read + Edit auf demselben File parallel: völlig legitim (verschiedene Tools, kein Bash-Konflikt)

Das einzige stille Damage-Pattern ist Timer + Other. Genau das blockt der Hook, sonst nichts.

False-Positive-Oberfläche durch die Anchor-Regex praktisch null: der Timer muss als STANDALONE-Command in einem eigenen tool_use-Block stehen. Chained Sleeps in größeren Commands (`worker-cli send X done && sleep 5 && worker-cli status X`) matchen nicht, weil das Command nicht mit `sleep` beginnt.

---

## Implementation Notes

**No `_shell_strip` needed.** Andere Hooks nutzen `_strip_non_shell_active` um quoted-Regions vor Pattern-Match zu maskieren. Hier nicht nötig — die Timer-Regex matched die GANZE Command-String (`^...$`), nicht eine Subregion. Ein quoted `sleep ... && echo` innerhalb eines anderen Commands kann den Anchor strukturell nicht aktivieren.

**No state file needed.** Cross-Response-State wäre fragil (wie kennt der Hook die Response-Boundary?). Stattdessen lebt die gesamte benötigte Information in einer einzigen JSONL-Datei zur Hook-Feuer-Zeit: das ganze content-Array der aktuellen Assistant-Message ist da. Stateless, idempotent, race-frei.

**Fail-open auf allen Levels.** Wenn transcript_path fehlt, das JSONL unlesbar ist, kein Assistant-Eintrag existiert, oder das content-Array malformed ist → exit 0. Konsistent mit allen anderen Hooks.

**Erster Hook der `transcript_path` nutzt.** Alle bisherigen Hooks operieren auf tool_input alleine. Damit ist dieser Hook eine neue Pattern-Familie — Cross-Tool_use Detection. Wenn künftig weitere strukturelle Antipatterns gefunden werden die nicht in einem einzelnen Command sichtbar sind (z.B. wiederholter Read auf denselben File über N Tool_uses), folgt das gleiche Schema.

---

## Interaction mit block_unauthorized_background

Beide Hooks treffen Timer-Commands, aber operieren in verschiedenen Dimensionen:

| Hook | Scope | Action |
|---|---|---|
| `block_unauthorized_background` | Einzelner Bash-Call: matcht non-canonical Timer (z.B. `echo "text"` statt `echo done`) → rewrites `run_in_background=true` zu `false` | Rewrite |
| `block_parallel_bash_timer` | Cross-Tool_use: erkennt Timer-Form als einen von ≥2 Bash-Blocks in derselben Response | Block |

Hook-Order in `hook_setup.py`: `block_parallel_bash_timer` direkt nach `block_unauthorized_background`. Hooks feuern nach Ansicht der CC-Dokumentation sequenziell pro tool_use; der Cross-Tool_use-Hook sieht das Original-Command im Transcript (rewrites passieren am Dispatch-Point, das JSONL hat den Original-State). Damit ist die Erkennung robust gegen Rewrite-Order: auch ein zu Foreground-rewriteter Timer würde noch als Timer-Form erkannt weil die Command-String selbst unverändert bleibt.

---

## Test Coverage

`dev/hook_smoke/test_block_parallel_bash_timer.py` — 11 Cases:

**True positives (5, expected exit 2):**
- Strict canonical timer (`sleep 600 && echo done`) + foreground Bash
- Loose timer (`sleep 480 && echo "8min check"`) + foreground Bash
- Three Bashes one is timer
- Thinking + tool_use mix with timer
- Float-second timer (`sleep 1.5`)

**False-positive fixes (6, expected exit 0):**
- Single Bash (no timer in response)
- Single Bash IS timer (no parallel partner)
- Two non-timer Bashes parallel (laut-fail-class, nicht zu blocken)
- Timer-text inside quoted argument of another command
- Sleep chained in middle of larger command (not standalone)
- Missing transcript_path (fail-open)

Smoke-Test schreibt temp JSONL pro Case mit fingiertem assistant-message-content, ruft Hook als Subprocess, vergleicht exit code. Pattern identisch zu `test_block_polling_loop.py`. Test-Run schreibt fire-events in `/tmp/test_block_parallel_bash_timer_fire.jsonl` via `MONITOR_CC_HOOK_FIRING_LOG` env override, vermeidet Pollution des produktiven `src/logs/hook_firing.jsonl`.

---

## Future Extension

Wenn `hook_firing.jsonl` zeigt dass andere stille Damage-Klassen real auftreten (z.B. Background-Process via shell `&` + zweiter Bash-tool_use), könnte derselbe Cross-Tool_use-Detection-Mechanismus erweitert werden. Die Pattern-Familie ist generalisierbar:

> "Block Bash-tool_use N wenn in derselben Response Bash-tool_use M existiert das eine Async-Operation initiiert deren Damage stumm ist."

Aber: erst empirisch belegen, dann erweitern. Vorerst eine einzige Trigger-Klasse — der Sleep-Timer.
