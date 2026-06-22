# Block Polling Loop — Hook Design Rationale (2026-05-25)

**Topic:** Neuer Hook `block_polling_loop.py` der den Canonical Polling-Loop
Anti-Pattern verhindert wo ein Worker repeated kurze Bash-Calls macht um einen
asynchron-gestarteten Background-Process zu polluen.

**Bead:** `Monitor_CC-8ggr` Thread 1 (hook FP-audit + ergänzende neue Hooks).

---

## Triggering Evidence

RAG-Worker `mode-topk-sweep` Session 2026-05-24 22:26–~23:00:
- Worker startete einen Sweep-Process im shell-background via `cmd ... &` Suffix
  (NICHT via CC's `run_in_background=true` Flag — unsere `block_unauthorized_background`
  Hook konnte daher nicht greifen)
- Captured PID, dann **371 sequenzielle Polls** im Pattern:
  ```
  ps -p <PID> > /dev/null 2>&1 && echo "still running" || echo "done"; \
  wc -l /tmp/cross_sweep_output.log; tail -N /tmp/cross_sweep_output.log
  ```
- Alle Polls hatten `bg=False` (CC-Flag), Cadence 2-5 Sekunden, tail-N monoton
  inkrementierend von 18 → 36+
- Pro Poll: ~2000 Zeichen Log-Inhalt als Tool-Result + Thinking-Tokens zwischen
  Calls für "ist der Prozess noch da?" Bewertung
- Schätzung Token-Verbrauch nur für Poll-Loop: 30-40k. Bei 200k-Window blieb
  am Ende kein Budget für den Report-Write

Worker hatte mehrere saubere Alternativen verfügbar:
1. **Foreground mit `timeout=900000`** — Bash-Tool unterstützt 10-15 min Timeouts
2. **Background + `wait $PID`** — bash-native Block bis Process endet
3. **Background + EIN langer `sleep`** statt 371 kleinen Polls

Worker hat keine davon genutzt — naive Default-Strategie "ich check öfter ob's
fertig ist" gewählt. Reine Worker-Disziplin-Lücke, nicht durch Hook erzwungen.

Bestehende Hooks blieben blind: `block_unauthorized_background` sieht nur das
CC-Flag, nicht shell-`&`; alle anderen Hooks targeting different Antipatterns.

---

## Three Angriffsflächen Considered

### A) Single-Call Signature (chosen — implement now)

Pattern-Match auf den smoking-gun Fingerprint im einzelnen Bash-Command:
- `ps -p <num>` (Process-Existenz-Check)
- KOMBINIERT mit `tail -<num>` (Log-Read mit konkretem N)
- BEIDE im selben tool_input.command

Eine PreToolUse-Hook erkennt das beim ALLERERSTEN Poll, bevor der Loop überhaupt
anläuft. Stateless, single-call, fail-open. Folgt der etablierten Pattern-Familie
von `block_dangerous_kill` / `block_broad_grep`.

**Stärken:**
- Stateless — keine cross-session/cross-call State-Files nötig
- Catches the loop on first attempt (vor wasted Polls)
- Trivial zu implementieren (~50 LOC analog zu block_dangerous_kill)
- Klar definierte Failure-Class — keine fuzzy Heuristik

**Schwächen:**
- Catched nur diese eine Polling-Form. Andere Varianten würden vorbeischlüpfen:
  - `while sleep 1; do tail -n 3 /tmp/log; done` (shell-loop)
  - `for i in $(seq 1 100); do sleep 5; check; done` (counter-loop)
  - Wiederholtes `tail -N` ohne `ps -p` check (reines Log-Polling)
  - Polling via Python/jq pipelines die anders shaped sind

**Wann zu erweitern:** sobald `hook_firing.jsonl` zeigt dass andere Polling-Patterns
real auftreten (kein Fire dieses Hooks, aber Anti-Pattern empirisch sichtbar in den
Session-JSONLs), würden wir Angriffsfläche B oder C bauen. Bis dahin: dieser eine
Hook + Worker-Disziplin-Regel-Hinweis in `~/.claude/shared-rules/worker/worker-rules.md`.

### B) Cross-Call Repetition Detection (deferred)

Per-session state-file der letzten N Bash-Commands mit timestamp + command-hash.
Bei jedem incoming call: check "haben wir die letzten 3+ Commands mit ≥80%
Ähnlichkeit innerhalb der letzten 30s?" → block.

**Stärken:** catched JEDE Polling-Variante unabhängig vom konkreten Mechanismus.

**Schwächen:**
- Substantieller State-Overhead (file IO pro Call, hashing, threshold-tuning,
  race conditions zwischen parallel sessions)
- False-Positive-Risiko: legitime use-cases wie live-tail eines Build-Logs
  während verbose-output gerade rauskommt würden geblockt
- Mehr Implementierungs-Komplexität als die anderen Hooks im Bestand
- Threshold-tuning braucht empirische Daten die wir noch nicht haben

### C) Session-JSONL Frequency Analysis (deferred)

Hook öffnet `$transcript_path` aus dem CC stdin payload, parsed die letzten 10
tool_use Entries, prüft auf Repetition. Variante von B aber ohne eigenes
State-File.

**Stärken:** keine eigene State-Persistence nötig — nutzt CC's Session-JSONL die
eh existiert.

**Schwächen:**
- Session-JSONLs sind MB-große Files, parsing on every Bash-Call ist nicht billig
- Pattern-Match zwischen Commands müsste sauber definiert sein
- Gleicher False-Positive-Class wie B

---

## Chosen Architecture — Angriffsfläche A

**Module:** `src/hooks/block_polling_loop.py`

**Pattern family:** block-with-stderr (exit 2). Folgt block_dangerous_kill als
Vorbild — ähnliche "smoking gun single-call signature" Klasse.

**Detection regex (combined check):**
- `_PS_P_CHECK = re.compile(r'\bps\s+-p\s+\d+')`
- `_TAIL_N_FILE = re.compile(r'\btail\s+-\d+\s+\S+')`
- Block IFF beide matches im selben (post-quote-stripped) command

Beide Patterns müssen present sein — sonst false positive auf legitime Single-Use
(`ps -p <PID>` alleine ist ein normaler check, `tail -50 file.log` alleine ist ein
normaler read).

**Quote-stripping:** via `_shell_strip._strip_non_shell_active` analog zu den
anderen Pattern-Match Hooks — verhindert false-positives wenn das Pattern in
heredoc-body oder quoted-string als Beispiel-Text steht.

**Stderr message (one-liner per User-Direktive 2026-05-24):**
```
polling loop antipattern — use `wait $PID` then single `tail file` instead of repeated polls
```

**Logging:** ruft `_fire_log.log_fire("block_polling_loop", "block", "Bash", command, reason=<msg>, session_id=<id>)` analog zu allen anderen Block-Hooks vor dem `sys.exit(2)`.

**Registration:** `hook_setup.py` `_HOOK_SCRIPTS` Liste, `("block_polling_loop.py", "Bash")`.

**Smoke test:** `dev/hook_smoke/test_block_polling_loop.py` mit positive case (das
exact cross_sweep Pattern) + negative cases (nur `ps -p` allein, nur `tail -N`
allein, beide in heredoc-body, beide in quoted-string).

---

## Open Question (post-implementation, data-driven)

Nach 2 Wochen Live-Daten in `hook_firing.jsonl`:
- Wie oft hat der Hook gefeuert?
- Gab es Polling-Varianten die im Logfile auftauchen aber NICHT diesen Pattern
  matchen (gegen-check via grep über raw Session-JSONLs)?
- Falls ja → Re-Eval ob Angriffsfläche B oder C lohnt

Entscheidung darüber dann mit konkreten Daten, nicht hypothetisch.

---

## 2026-06-22 — Live-FP (frequenz-Version) + Fix: pipe-gefüttertes tail hat kein Target

**Kontext:** Der oben beschriebene Single-Call-Ansatz (A) wurde nicht die finale Form — die laufende Implementierung ist die frequenz-basierte Variante (Entscheidung 2026-05-29, `hook_fp_audit/2026-05-29.md`): `_extract_target` liest `ps -p <N>` → `pid:N` ODER `tail -<N> <file>` → `file:path`, zählt pro (session,target) im 30s-Fenster, blockt ab dem 3. Treffer.

**FP entdeckt (Session CC-Version-Bump 149→176):** Befehl `cd … && plugin-publish 2>&1 | tail -25` (+ angehängte `echo`/`grep`) wurde mit "polling loop — ≥3 checks …" geblockt. Reine Output-Kürzung, kein Poll.

**Evidenz:**
- `src/logs/hook_firing.jsonl`: zwei Blocks 2026-06-22 15:58:56 (`block_manual_worker_cleanup`, gleiche Kette) + 15:59:13 (`block_polling_loop`).
- `src/logs/polling_state.jsonl`: extrahiertes Target = `file:echo;` — der Hook hielt den String `echo;` für eine "gepollte Datei".

**Mechanismus (verifiziert):** `_TAIL_N_FILE = r'\btail\s+-\d+\s+(\S+)'` greift das Token NACH `tail -25`. Bei pipe-gefüttertem Tail (`… | tail -25`) gibt es KEIN Dateiargument — Tail liest stdin —, also fängt `(\S+)` (über den Zeilenumbruch hinweg) das nächste verkettete Kommando `echo;`. Gewohnheits-Stil `cmd | tail -N` direkt gefolgt von `echo "…"` ⇒ dasselbe Pseudo-Target `file:echo;` lief 3× im 30s-Fenster auf (Merge-Befehl + 2 plugin-publish-Versuche) ⇒ Schwelle 3 gerissen. Echter FP: ein pipe-gefüttertes Tail hat keine Datei zum Pollen.

**Fix-Richtung (User-green-lit 2026-06-22):** Ein pipe-gefüttertes `tail -N` (preceded by `|`, liest stdin) liefert KEIN Poll-Target. Whitelistet `cmd | tail -N` (+ verkettete Kommandos, auch wiederholt). Echtes `tail -N <file>` (ohne Pipe) bleibt als Watch-Loop-Target erkannt; `ps -p`-Pfad unberührt.

**Umsetzung (committed `48e1504`, Worker `pollfix`):** Zwei-Bedingungen-Diskriminator —
- **C1** `_TAIL_N_FILE = r'\btail\s+-\d+[^\S\n]+(\S+)'`: Whitespace vor dem Datei-Arg auf Space/Tab beschränkt (kein Newline) → das Folgezeilen-Kommando wird nicht mehr als Datei gefangen.
- **C2** in `_extract_target`: wenn `stripped[:m.start()].rstrip()` auf einzelnes `|` endet (nicht `||`) → `return None` (pipe-gefüttert, liest stdin).
- C1 fängt die Newline-Variante (`| tail -N\necho`), C2 die Gleiche-Zeile-Variante (`| tail -N ; echo`). Echtes `tail -N <file>` (kein Pipe davor) + `ps -p`-Pfad unberührt.
- Smoke `dev/hook_smoke/test_block_polling_loop.py`: +Gruppe `_run_group_pipe_fed_tail` (5 Fälle), **20/20 grün**. IST `decisions/pipe07_safety_hooks.md` Hook 8 + `src/hooks/DOCS.md` + `dev/hook_smoke/DOCS.md` angeglichen.
- **Akzeptierter Nicht-Fall:** `cmd | tail -N <file>` (pipe-gefüttert MIT File-Arg — Tail liest dann die Datei, nicht stdin) wird von C2 mit-whitelistet. Kein real geschriebenes Poll-Pattern; bewusst keine Extra-Logik.

**Bezug Re-Eval 3** (`audit_logging/2026-05-25_data_dependent_reevals.md`): Dieser FP ist genau ein Datenpunkt der FP-Seite von Re-Eval 3. Die FN-Seite (andere Polling-Varianten, die durchschlüpfen) bleibt offen.

---

## Sources

- Forensik der `mode-topk-sweep` Worker-Session (RAG-Projekt, 2026-05-24):
  - `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-MCP-RAG--claude-worktrees-mode-topk-sweep/530a3eda-df84-4537-ac7c-9201412dd658.jsonl`
  - 371 Polls mit identem Pattern, alle bg=False, monoton inkrementierendes tail-N
- `src/hooks/block_dangerous_kill.py` (Vorbild für Single-Call Signature Hook)
- `src/hooks/_shell_strip.py` (Quote-Stripping Module)
- `src/hooks/_fire_log.py` (Logging Module)
- Bead `Monitor_CC-8ggr` Thread 1 (Hook FP-Audit Container)
