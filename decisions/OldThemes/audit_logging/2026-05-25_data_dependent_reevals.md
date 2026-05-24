# Data-Dependent Re-Evaluations — Consolidated Tracker (2026-05-25)

**Topic:** Drei separate Hook-/Strip-Themen die alle auf Akkumulation von Live-Daten
in `src/logs/hook_firing.jsonl` und/oder `src/logs/tool_errors.jsonl` warten bevor
Folge-Entscheidungen sinnvoll sind. Konsolidiert in Bead `Monitor_CC-mjkt` weil die
gemeinsame Trigger-Bedingung "log accumulation reicht für empirische Auswertung"
bei allen drei identisch ist.

---

## Re-Eval 1 — CC Noise Prefix Strip (Original mjkt-Scope)

**Source:** `decisions/OldThemes/audit_logging/cc_noise_strip_investigation.md`

**Frage:** Welche weiteren CC-wrapper-Patterns in tool_result content (jenseits des
schon adressierten `PreToolUse:<Tool> hook error: [python3 <path>]:` prefix) sind
strippbar ohne agent-relevant content zu verlieren?

**Datenquelle:** `src/logs/tool_errors.jsonl` (live seit 2026-05-24 ~23:32 UTC).

**Trigger-Datum:** ab ~2026-06-07 (≥ 2 Wochen Akkumulation).

**Eval-Methode:**
1. Grep über tool_errors.jsonl, Cluster nach distinct Error-Prefix-Shapes
2. Pro Pattern decide: pure Noise (strippbar) vs context-bearing (keep, bias conservativ)
3. Implementation in `src/proxy/strip_hook_prefix.py` ODER neues Strip-Modul für andere Klassen

---

## Re-Eval 2 — rewrite_chained_sleep Audit

**Source:** `decisions/OldThemes/tool_use_safety/2026-05-24_hook_classification_audit.md`
(Verdict: MONITOR — jung, Daten fehlen)

**Frage:** War die narrow trivial-sync Allow-Liste (`echo`, `true` als cmd_before)
das richtige Maß für den Hook? Gibt es load-bearing Patterns die fälschlich
gestrippt werden, oder trivial-sync Patterns die fälschlich pass-through bleiben?

**Datenquelle:** `src/logs/hook_firing.jsonl` filter auf
`hook=rewrite_chained_sleep AND decision=rewrite`.

**Trigger-Datum:** ab ~2026-06-01 (≥ 7 Tage Live-Daten).

**Eval-Methode:**
1. Grep hook_firing.jsonl für alle rewrite_chained_sleep fires
2. Pro Fire: original command vs rewritten command vergleichen
3. False-Positives: rewritten command führt zu unerwartetem Verhalten (verify via
   cross-reference mit dem Session-JSONL des gleichen sessions)
4. Missed cases: tool_errors.jsonl nach sleep-related Errors greppen die NICHT durch
   die Allow-Liste gefangen worden wären
5. Falls FP-Rate > akzeptabel: Allow-Liste enger ziehen ODER zurück zu block-with-hint
6. Falls coverage zu niedrig: Allow-Liste erweitern um mixed tokens (rag-cli search,
   bd ohne dolt-start, etc.) per Subcommand-Inspection

---

## Re-Eval 3 — block_polling_loop Hook Audit

**Source:** `decisions/OldThemes/tool_use_safety/2026-05-25_block_polling_loop_design.md`
(Angriffsfläche A — single-call signature, gewählt mit explizitem Hinweis dass
andere Polling-Varianten vorbeischlüpfen können)

**Frage:** Catched die Single-Call-Signature (ps -p + tail -N im selben command) den
Großteil real-auftretender Polling-Loops? Oder gibt es regelmäßig andere Varianten
(`while sleep; do tail; done`, reines repeated tail ohne ps-check, Python/jq polling
pipelines) die durchschlüpfen?

**Datenquelle:** `src/logs/hook_firing.jsonl` (filter auf
`hook=block_polling_loop AND decision=block` für gefangene Cases) PLUS gegen-check
über raw Session-JSONLs (`~/.claude/projects/*/*.jsonl`) für nicht-gefangene Cases
mit ähnlichem repetition-Pattern.

**Trigger-Datum:** ab ~2026-06-07 (≥ 2 Wochen Live-Daten).

**Eval-Methode:**
1. Count fires von block_polling_loop — wie oft hat er getroffen?
2. Forensik der Polling-Anti-Pattern in Session-JSONLs des gleichen Zeitraums:
   - Grep nach "tail -N /tmp/" mit monoton inkrementierendem N (≥ 5 calls in 60s)
   - Grep nach "while ... sleep ... done"
   - Grep nach "for ... do sleep ... done"
   - Sonstige repetitive Bash-Pattern
3. False-Negatives: Patterns die in Session-JSONLs sichtbar aber NICHT von Hook
   gefangen wurden
4. Falls False-Negative-Rate substantiell:
   - Angriffsfläche B (cross-call repetition detection via per-session state-file)
   - ODER Angriffsfläche C (Session-JSONL frequency analysis on each Bash call)
   - Trade-off-Analyse erneut prüfen mit den dann verfügbaren Daten

---

## Gemeinsame Aktion bei Trigger-Datum

Eine einzelne Session in ~2 Wochen kann alle drei Re-Evals auf einmal abarbeiten —
alle drei Datenquellen sind dann ausreichend gewachsen, alle drei haben dieselbe
analytische Form (log greppen, pattern detection, FP/FN-Bewertung, Folge-Action
entscheiden). Konsolidierung in einer Session spart Setup-Overhead.

**Vorschlag:** Beim Re-Eval-Trigger eine Session pro Topic im Konsolidierungs-Mode,
Output als ein Update zu jeweils der ursprünglichen OldThemes-File (CHANGE-Block
mit den empirischen Findings + entschiedener Folge-Action). Falls Folge-Action
substantielle Implementation braucht: Worker-Dispatch pro Topic.

---

## Sources

- `decisions/OldThemes/audit_logging/cc_noise_strip_investigation.md`
- `decisions/OldThemes/tool_use_safety/2026-05-24_hook_classification_audit.md`
- `decisions/OldThemes/tool_use_safety/2026-05-25_block_polling_loop_design.md`
- `decisions/OldThemes/audit_logging/architecture.md` (Log-Infrastruktur)
- `src/logs/hook_firing.jsonl` (Datenquelle 1)
- `src/logs/tool_errors.jsonl` (Datenquelle 2)
