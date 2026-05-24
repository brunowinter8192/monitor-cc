# Audit Logging — Two Persistent Logs (2026-05-24)

**Topic:** Build two persistent JSONL logs that capture the data CC currently only
exposes transient (session-JSONL strings) or in-memory (warnings_pane). Closes the
audit blindspots for (a) silent hook fires and (b) cross-session tool errors.

**Bead:** `Monitor_CC-8ggr` Thread 2.

---

## Original Framing (refuted)

Bead-Description framed dies als "Hook output visibility — Opus sieht Rewrite-Hooks
nicht im API tool_result". GH-Research auf anthropics/claude-code lieferte den
CC-Output-Channel-Split:

| Field | Routing |
|---|---|
| `systemMessage` | Terminal/UI display ONLY (CC pane). NIE im Modell-Kontext. |
| `hookSpecificOutput.additionalContext` | Wird in Modell-Kontext injected (PreToolUse seit CC 2.1.9, CHANGELOG line 2549). |
| `stderr` + exit 2 | Block-Error, Modell sieht es. |

Quellen: anthropics/claude-code issues #41285, #47692, #61109; CHANGELOG lines 929,
2549, 3486; `plugins/plugin-dev/skills/hook-development/SKILL.md` lines 130-220.

Damit wäre die Visibility-Asymmetrie technisch lösbar via `additionalContext`-Feld
in den Rewrite-Hooks. **User-Veto 2026-05-24:** das ist explizit NICHT gewünscht.
Rewrite-Hooks sollen silent bleiben — der Agent braucht keine Context-Pollution
darüber dass `git diff dev` zu `git diff dev --` rewritten wurde. Hook-Output zum
Modell ist nur bei Blocks gerechtfertigt wo der Agent verstehen muss WARUM blockiert
wurde um anders zu retryen.

Original-File-Name aus Bead (`hook_visibility_problem.md`) damit obsolet — der echte
Pain ist nicht Visibility-für-den-Agent sondern persistentes Audit-Logging als
Datengrundlage für künftige Analysen. Topic-Name auf `audit_logging.md` korrigiert
(vorher transient: `hook_firing_audit_log.md`).

---

## Reframed Pain — Zwei Blindspots

**Blindspot 1: Hook-Fires.**

| Heutige Quelle | Was sie sieht | Was sie nicht sieht |
|---|---|---|
| CC Session-JSONLs (`~/.claude/projects/*/*.jsonl`) | Block-Events (greppt `"PreToolUse:<Tool> hook error: ... BLOCKED:"`) | Rewrites (silent updatedInput), Silent-Allow-Passthroughs, Rewrite-FPs der Form "Command kaputt-rewritten" |

Block-Hooks sind nur accidentally audit-bar — CC serialisiert ihre stderr-Outputs in
die Session-Transkripte. Das ist ein Implementation-Detail-Glück, kein Design.
Sobald ein Hook silent arbeitet (was per User-Direktive das gewünschte Verhalten ist)
ist er strukturell unsichtbar. `rewrite_chained_sleep.py` (heute gelandet) ist der
erste Hook der das demonstriert — wir können nicht messen ob er die 30.4% trivial-sync
Violations wie geplant rewrited oder ob er FPs produziert die wir nie sehen.

**Blindspot 2: Tool-Errors cross-session.**

| Heutige Quelle | Was sie sieht | Was sie nicht sieht |
|---|---|---|
| Monitor warnings_pane | Tool-Errors der **aktuellen** Session in-memory (Proxy-JSONL `is_error: true` Blocks) | Alles vor Session-Start (gecleared bei jedem Wechsel — `src/panes/warnings_pane.py:213,234`), keine Worker-Session-Aggregation, keine cross-session Historie |

`warnings_pane` extrahiert via `_is_tool_error()` (`src/panes/warnings_parse.py:43`)
genau die richtige Klasse von Events — aber persistiert sie nirgends. `tool_errors`
ist eine module-level Liste, append-only innerhalb einer Session, gecleared bei
Session-Switch. Null Disk-Persistence.

`dev/tool_use_errors/analyze.py` versucht das Loch zu stopfen durch on-demand-Parse
der Proxy-JSONLs mit eingebauter Pattern-Classification (18 Failure-Patterns × 6
Hookability-Buckets). Das ist over-engineered: User-Direktive ist *raw data + ad-hoc
grep* statt *eingebaute Klassifikation*. Patterns ändern sich, Klassifikation wird
schnell stale, ein dünnes append-only JSONL ist die robustere Datengrundlage.

---

## Chosen Architecture — Zwei Logs

**Log A — Hook Firing Log:** `src/logs/hook_firing.jsonl`

Each hook calls a shared `_fire_log.log_fire()` at its decision point (vor
`sys.exit(2)` für Blocks, vor `print(json.dumps(...))` für Rewrites). Schema:

```json
{"ts":"2026-05-24T14:23:11Z","hook":"rewrite_git_ambiguous","decision":"rewrite","tool":"Bash","command":"git diff dev..HEAD","rewritten":"git diff dev..HEAD --","session":"<cc_session_id>"}
{"ts":"2026-05-24T14:23:45Z","hook":"block_chained_sleep","decision":"block","tool":"Bash","command":"sleep 5 && echo foo","reason":"BLOCKED: chained sleep — use separate calls"}
```

`session_id` kommt aus dem CC-stdin-Payload gratis. Cross-Reference mit
Session-JSONLs damit möglich.

Shared-Module: `src/hooks/_fire_log.py` parallel zu `_shell_strip.py`. Fail-silent
(try/except → drop, Hook läuft normal weiter). 18 aktive Hooks × ~3 Zeilen Change.
Pattern uniform.

**Log B — Tool Error Log:** `src/logs/tool_errors.jsonl`

Mirror der `warnings_pane`-Extraktion auf Disk, aber cross-session und cross-worker.
Schema:

```json
{"ts":"2026-05-24T14:30:22Z","session_id":"<id>","worker":"main|<worker-name>","tool_name":"Bash","tool_use_id":"<id>","error_preview":"<truncated error text>","error_full":"<complete text>","proxy_file":"src/logs/api_requests_..._....jsonl","request_id":"<rid>"}
```

Extraction-Logic ist bereits in `src/panes/warnings_parse._is_tool_error()` etabliert
— check `type=='tool_result'` UND `is_error is True`. Logic wird in ein neues
Schreib-Modul mirrored (NICHT in warnings_pane.py selbst eingehängt — warnings_pane
soll seine in-memory UI-Logik behalten, das Logging ist ein orthogonaler Pfad).

Architektur-Optionen für den Writer (offene Sub-Entscheidung siehe unten):
1. **Tail-side Daemon:** standalone Process tailt alle Proxy-JSONLs, schreibt
   Error-Log. Entkoppelt vom Monitor.
2. **Monitor-side Hook:** warnings_pane (oder eine sister-component) schreibt jeden
   neu detektierten Error zusätzlich auf Disk. Bestehende UI bleibt unverändert.
3. **Proxy-side Inline:** Proxy schreibt parallel zur regulären JSONL einen
   error-only JSONL. Tightest coupling, real-time.

Empfehlung Option 2 — minimalster neuer Code-Footprint, die Extraction-Logic
existiert bereits an genau einer Stelle, wir hängen einen Schreib-Pfad parallel an.

---

## Script Deletion (resolved 2026-05-24)

User-Entscheidung nach Tauglichkeits-Bewertung: BEIDE Scripts werden gelöscht
sobald die zwei Logs live sind. Begründung in einem Satz: die Meta-FP-Problematik.
Hooks sind nicht-trivial — ein Script das Hook-Fires analysiert produziert
genauso viele FPs in seiner Analyse wie die Hooks selbst. Der Script-Layer addiert
eine zweite Schicht brüchiger Heuristik on top of der ersten.

| Script | Verdict | Wann |
|---|---|---|
| `dev/hook_firing/analyze.py` | DELETE | Mit dem Log-Build (gleicher Commit) |
| `dev/hook_firing/DOCS.md` | DELETE | Gleicher Commit |
| `dev/tool_use_errors/analyze.py` | DELETE | Gleicher Commit |
| `dev/tool_use_errors/DOCS.md` | DELETE | Gleicher Commit |
| `dev/hook_firing/reports/*` | KEEP | Historische Snapshots mit konkreten Datum-Findings |
| `dev/tool_use_errors/reports/*` | KEEP | Gleiche Begründung |
| `dev/sleep_pattern_analysis/` | KEEP | Audit-Lauf abgeschlossen, Evidenz für `rewrite_chained_sleep.py` Design |
| `dev/hook_smoke/` | KEEP + EXTEND | Smoke-Tests aktiv, neue Tests für die beiden Logs |

**Wissens-Erhalt:** die encoded Pattern-Library aus beiden Scripts wandert NICHT
verloren — `failure_patterns_catalog.md` (gleicher OldThemes-Ordner) archiviert
die 18 Failure-Class-Fingerprints aus `tool_use_errors/analyze.py` plus die
per-Hook FP/TP-Heuristiken aus `hook_firing/analyze.py` als statisches
historisches Wissen.

Detaillierte LOC-Zerlegung pro Script in `script_tauglichkeit.md`.

## Future Hook-Iteration Workflow (replaces script-driven analysis)

Statt persistenter dev-Scripts ist der Workflow für künftige Hook-Arbeit
human-in-the-loop auf den zwei Logs:

1. **Failure-Klasse picken.** Roh in `tool_errors.jsonl` greppen, eine spezifische
   Klasse identifizieren (`is_error: true` + Pattern XYZ).
2. **Konkretes Beispiel ziehen.** Aus dem Log das tool_use_id extrahieren,
   im entsprechenden Proxy-JSONL aus `src/logs/api_requests_*.jsonl` den
   vollständigen Tool-Call-Kontext lesen (was hat der Agent davor gemacht, was
   war der Trigger, was war intentioniert).
3. **Hook-Reaktion durchdenken.** Wie würde ein Hook auf diese Failure-Klasse
   reagieren? Welcher Tool-Input würde geblockt/rewritten? Welche Side-Effects?
4. **Probe-Hook bauen.** Implementiert das Pattern als Hook-Script, wird in
   `dev/hook_smoke/` mit synthetischen Inputs gegen-getestet.
5. **Replay auf historische Daten.** Probe-Hook wird gegen die existierenden
   Proxy-JSONLs in `src/logs/` retroaktiv gefahren — sehen wie oft er gefeuert
   hätte, in welchem Anteil davon zu Recht, in welchem zu Unrecht.
6. **FP-Rate-Bewertung.** Wenn die FP-Rate des Probes zu hoch ist → zurück zu
   Schritt 3. Wenn akzeptabel → Promotion zu echtem Hook, Registration via
   `hook_setup.py`.

Live-Daten ab Schritt 5 nutzt das neue `hook_firing.jsonl` weiter — der
Live-Probe-Hook schreibt seine Fires dort hin, wir greppen sie raus.

Der bisherige Approach (dev-Script analysiert pre-aggregiert Hook-Fires mit
eingebauten FP/TP-Heuristiken die als Code maintained werden müssen) wird
explizit verworfen — die Heuristiken sind nicht stabil genug für persistenten
Code, und der Maintenance-Aufwand für die Patterns hat keinen besseren
Outcome geliefert als ad-hoc grep + Domain-Wissen im Kopf des Implementierenden.

## Orphan-Awareness

`src/logs/hook_outputs.jsonl` existiert bereits (17MB, 31142 Entries, last write
2026-04-19) — Relikt eines älteren Logging-Frameworks (Schema mit
`skill-trigger.py` / `bash-hook.sh` Einträgen, nicht unsere aktuellen Hooks).
Greppt: kein src/-Modul schreibt mehr darauf. Bei Implementation: Orphan-File
entweder löschen oder mit eindeutigem Suffix archivieren (`hook_outputs.jsonl.legacy_2026-04`)
damit Schema-Collisions mit dem neuen `hook_firing.jsonl` ausgeschlossen sind.

---

## Resolved Decisions

| # | Decision | Resolution |
|---|---|---|
| 1 | Log A Pfad | **`src/logs/hook_firing.jsonl`** (User-Direktive 2026-05-24: alle Logs in `src/logs/`) |
| 4 | Log B Pfad | **`src/logs/tool_errors.jsonl`** (gleiche Direktive) |

## Pending Design Decisions

**Log A (Hook):**
2. Schema: oben skizziert (ts/hook/decision/tool/command/reason-or-rewritten/session).
3. Rotation: append-forever (~10MB/Jahr handhabbar).

**Log B (Tool-Errors):**
5. Schema: oben skizziert. Frage ob `error_full` (komplettes Error-Text) immer
   sinnvoll ist oder ob Cap (z.B. 4KB) sinnvoll wäre — manche Tool-Errors sind
   mehrere KB lang (Python tracebacks, big diffs).
6. Writer-Architektur: Option 2 (Monitor-side Hook) als Default-Vorschlag.
7. Backfill: nur forward-from-now (live) ODER initial einmal alle bestehenden
   Proxy-JSONLs scannen und retroaktiv populaten? Backfill kostet einmalige
   Compute aber gibt sofort historische Datengrundlage.

---

## Open Questions

- Soll `_fire_log.log_fire()` ein hook_setup.py-erzwungener Pflicht-Import sein
  (Lint/Hook der missing-import abbricht)? Oder Code-Review-Disziplin?
- Brauchen wir eine `decision="error"` Klasse für Hook-internal-failures
  (Crashed-Hook), oder reicht fail-silent ohne Audit-Entry?
- Sollen die Log-Paths via env var konfigurierbar sein (für test-isolation in
  `dev/hook_smoke/`)? Praktisch ja, aber adds Komplexität.
- Tool-Error-Log: Worker-vs-Main-Session-Attribution — wie wird `worker_name`
  resolved aus dem Proxy-JSONL-Path? Aktueller warnings_pane macht das schon
  (`worker log files` ist in seinem Reads-Set), Logic ist greifbar.

---

## Sources

- Bead Monitor_CC-8ggr (Thread 2)
- `src/panes/warnings_pane.py` (line 213/234/259: in-memory `tool_errors` ohne
  Persistence)
- `src/panes/warnings_parse.py` (line 43: `_is_tool_error()` extraction logic)
- `src/panes/DOCS.md` (warnings_pane Architektur)
- `src/hooks/_shell_strip.py` (Precedent für Shared-Module-Pattern)
- `src/hooks/rewrite_git_ambiguous.py`, `rewrite_chained_sleep.py` (silent Rewrite-Hooks,
  blind spot demonstrators)
- `dev/hook_firing/analyze.py` + DOCS.md (current Block-only audit — Re-Eval pending in `script_tauglichkeit.md`)
- `dev/tool_use_errors/analyze.py` + DOCS.md (Pattern-Classifier — Re-Eval pending in `script_tauglichkeit.md`)
- anthropics/claude-code:
  - `plugins/plugin-dev/skills/hook-development/SKILL.md` lines 130-220
    (Output-Channel-Doc)
  - `plugins/plugin-dev/skills/hook-development/references/advanced.md` line 358
    (Audit-Log-Pattern)
  - CHANGELOG.md lines 929, 2549, 3486 (additionalContext-Field-History — refuted path)
  - Issues #41285, #47692, #61109, #61983 (Visibility + Observability-Gaps)
