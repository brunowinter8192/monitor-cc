# Script Tauglichkeit — dev/hook_firing/ + dev/tool_use_errors/ (2026-05-24)

**Frage:** Welche der existierenden dev-Scripts behalten ihren Wert sobald die zwei
neuen Logs (`src/logs/hook_firing.jsonl`, `src/logs/tool_errors.jsonl`) live sind?

**Methodik:** Pro Script die Funktionseinheiten zerlegen, einzeln gegen die neue
Datenbasis prüfen. Drei Urteilskategorien: KEEP (Funktion unabhängig von neuer
Datenbasis wertvoll), REPLACE (Funktion via einzeilen-`jq`/`grep` ersetzbar),
EVOLVE (Code-Wert vorhanden, aber Datenquelle wechselt — Re-Implementation auf
neuer Basis sinnvoll).

Re-Eval erfolgt erst NACH Log-Build — diese Bewertung ist forward-looking
Hypothese. Tatsächliche Entscheidung nach Live-Daten.

---

## dev/hook_firing/analyze.py (398 LOC)

### Funktionseinheiten

| Block | LOC | Was es macht | Tauglichkeit post-logs |
|---|---|---|---|
| Pass 1: uuid_map + tool_use_id_map build | ~30 | Iteriert CC Session-JSONLs, baut Indices um BLOCKED-Events ihrem auslösenden Command zuzuordnen | **REPLACE** — hook_firing.jsonl hat command direkt im Event, keine Zuordnung nötig |
| Pass 2: BLOCKED regex extraction | ~35 | Greppt `"PreToolUse:<Tool> hook error: ... BLOCKED:"`, parsed Hook-Name + Reason | **REPLACE** — Log hat `hook`, `decision`, `reason` als Felder |
| `_find_trigger` fallback (parentUuid) | ~15 | Wenn tool_use_id resolved nicht, fällt auf parent-message-first-tool_use zurück | **REPLACE** — Fallback unnötig, Log enthält Command immer direkt |
| `_classify_fp` per-Hook FP/TP heuristics | ~60 | Per-Hook (7 hooks abgedeckt): regex-checks für `_LOOP_RE`, `_SIDE_EFFECT_RE`, sleep-numerics, heredoc-in-$() gap, etc. | **KEEP/EVOLVE** — encoded domain knowledge, jede Heuristik ist eine echte Erkenntnis aus vorherigen Sessions |
| Friction-cluster detection | ~25 | Temporal clustering (≥3 blocks vom gleichen hook/project/branch in 30min Fenster) | **KEEP/EVOLVE** — datasource-agnostic, braucht nur (ts, hook, project, branch) Tupel die im neuen Log da sind |
| Report-building (MD output) | ~80 | Per-Hook Summary, Top-Trigger-Patterns, Events-Table | **EVOLVE** — Struktur bleibt, Renderer-Input wechselt von events-list-from-regex zu events-list-from-jsonl |
| Project-from-cwd derivation | ~10 | Strips worktree path | **KEEP** — Helper, datasource-agnostic |
| CLI args (--since, --project, --hook, --output) | ~25 | argparse | **KEEP** — User-facing interface bleibt sinnvoll |
| File-traversal infrastructure | ~30 | `PROJECTS_DIR.glob`, mtime pre-filter | **REPLACE** — eine einzige JSONL statt N session-JSONLs, kein glob nötig |

### Net Tauglichkeit

| Verdict | LOC | Anteil |
|---|---|---|
| KEEP (verbatim wiederverwendbar) | ~35 | 9% |
| EVOLVE (Logic gut, neue Datenquelle) | ~165 | 41% |
| REPLACE (via jq ersetzbar, code obsolet) | ~110 | 28% |
| Boilerplate / glue | ~88 | 22% |

**Vorschlag:** REWRITE statt DELETE. Neues Script ~150 LOC (vs heute 398), nutzt
`src/logs/hook_firing.jsonl` als Input, behält die `_classify_fp` Heuristics + die
Friction-Cluster-Detection + die Report-Struktur. Nimmt den Namen `analyze.py`
weiter, ersetzt das alte File.

**Alternative:** komplett DELETE, FP-Klassifikation via ad-hoc grep-Cookbook im
README. Funktioniert aber verliert die 60 LOC encoded heuristics — User müsste die
jedes Mal neu im Kopf rekonstruieren ("ist `sleep 3 && launchctl ...` ein FP weil
≤5s settling, oder TP weil in loop?"). Domain-Knowledge-Loss.

**Empfehlung:** REWRITE wenn FP-Audits weiter ein wiederkehrender Workflow sind.
DELETE wenn die zukünftige Praxis ist "jeder schaut mal selbst grep in den Log".
Entscheidung hängt davon ab wie oft Audits gefahren werden.

---

## dev/tool_use_errors/analyze.py (397 LOC)

### Funktionseinheiten

| Block | LOC | Was es macht | Tauglichkeit post-logs |
|---|---|---|---|
| Proxy-JSONL parse + tool_use/tool_result collection | ~50 | Lädt `raw_payload`, sammelt tool_use Blocks deduped by id, sammelt tool_result Blocks deduped by tool_use_id | **REPLACE** — tool_errors.jsonl hat extracted errors direkt, keine raw-payload-Navigation nötig |
| `_build_pairs` (tool_use ↔ tool_result via id) | ~30 | Verknüpft die zwei Maps | **REPLACE** — Log persistiert die Paarung schon |
| 18 signature patterns + lambda predicates | ~95 | Pattern-Library: `_HOOK_BLOCK_RE`, `_GIT_AMBIG_RE`, `_PARALLEL_TAG`, ... 18 patterns insgesamt | **EXTRACT-AS-COOKBOOK** — der Wert sind die Pattern-Regexes selbst, nicht die Script-Maschinerie drumherum |
| `_run_sigs` evaluation loop | ~25 | Pro Pair: alle 18 Patterns durchprobieren, ersten Match nehmen | **REPLACE** — `jq + grep` über tool_errors.jsonl macht dasselbe |
| Hookability-bucket grouping | ~20 | 6 Buckets, sortiert nach Priorität | **EXTRACT-AS-DOC** — die Bucket-Klassifikation ist konzeptuelle Doku, kein Code-Wert |
| Report-building (MD output) | ~120 | Hookability-grouped findings, top-error-patterns, uncategorized-patterns | **REPLACE** — `jq | sort | uniq -c | sort -rn | head` macht das equivalent |
| CLI args (proxy_jsonl positional, --input-glob, --output) | ~25 | argparse + glob expansion | **REPLACE** — kein glob nötig, single log file |
| Log-label derivation (opus / worker:<name>) | ~10 | Filename parsing | **EXTRACT-AS-LOGIC** — Worker-Attribution wird im Log-Writer (Phase 1) selbst gebraucht, gleiche Logic |

### Net Tauglichkeit

| Verdict | LOC | Anteil |
|---|---|---|
| EXTRACT-AS-COOKBOOK (Pattern-Defs als Doku) | ~115 | 29% |
| EXTRACT-AS-LOGIC (in Log-Writer einbauen) | ~10 | 3% |
| REPLACE (via jq direkt ersetzbar) | ~220 | 55% |
| Boilerplate / glue | ~52 | 13% |

**Vorschlag:** DELETE Script + DOCS. Die 18 Pattern-Definitionen als Cookbook
nach `decisions/OldThemes/audit_logging/pattern_cookbook.md` rüberziehen — pro
Pattern: Name + Regex/Tag + Beispiel-jq-Befehl gegen tool_errors.jsonl. Cookbook
ist statisch wartbar, kein Code-Maintenance, User kann ad-hoc `jq -f cookbook/<pattern>.jq`.

Die Worker-Attribution-Logic (`_log_label`) wandert in den Tool-Error-Log-Writer
(Phase 1 Implementation) — wird dort sowieso gebraucht.

**Empfehlung:** DELETE. Cookbook + jq deckt alle bisherigen Use-Cases. Der einzige
Verlust ist die "wenn ich nur einen Befehl tippe kriege ich einen kompletten Report"
Convenience — die jq-Cookbook-Befehle sind aber ebenso einzeilen-Calls.

---

## Zusammenfassung (Final 2026-05-24)

| Script | Verdict | Rationale |
|---|---|---|
| `dev/hook_firing/analyze.py` | **DELETE** | Meta-FP-Problematik (siehe unten) wiegt schwerer als Domain-Knowledge-Wert der Heuristics. Heuristics wandern in `failure_patterns_catalog.md` als Archiv. |
| `dev/tool_use_errors/analyze.py` | **DELETE** | 55% Code via jq ersetzbar + Meta-FP-Problematik. 18 Pattern-Definitionen wandern in `failure_patterns_catalog.md`. |
| `dev/hook_firing/DOCS.md` | **DELETE** | Folgt Script. |
| `dev/tool_use_errors/DOCS.md` | **DELETE** | Folgt Script. |
| `dev/hook_firing/reports/*` | **KEEP** | Historische Snapshot-Artefakte mit konkreten Datums-Findings. |
| `dev/tool_use_errors/reports/*` | **KEEP** | Wie oben. |
| `dev/sleep_pattern_analysis/` | **KEEP** | Audit-Lauf abgeschlossen, Evidenz für `rewrite_chained_sleep.py` Design. |
| `dev/hook_smoke/` | **KEEP + EXTEND** | Smoke-Tests aktiv, bekommen neue Tests für die zwei Logs. |

## Korrektur der initialen Empfehlung

Die ursprüngliche LOC-Zerlegung oben empfahl REWRITE für `hook_firing/analyze.py`
auf Basis der ~60 LOC encoded FP-Heuristics. Diese Empfehlung wurde durch das
User-Feedback verworfen:

> "Hooks sind generell nicht trivial und zu versuchen die analyse zu scripten
> macht keinen sinn weil man in der analyse dann genauso viele fps hat wie in den
> hooks. ... Wie wir es bisher gemacht haben war dogshit."

**Meta-FP-Problematik:** Ein Script das Hook-Fires klassifiziert ist selbst eine
zweite Schicht heuristischer Logik on top of der ersten (den Hooks). Beide Schichten
haben ihre eigenen FP-Raten. Die Analyse-FPs verschleiern die Hook-FPs — wir
debuggen dann zwei Heuristik-Layer parallel statt einen.

Die per-Hook Heuristics in `_classify_fp` sind echtes Wissen — aber als
**dokumentiertes Wissen** im Catalog wertvoller als als **maintained Code**. Im
Code-Form müssen sie pro Hook-Update synchron gehalten werden; im Doc-Form sind
sie ein statischer Reference den der Implementierende beim Probe-Hook-Bauen
liest und im Kopf anwendet.

Asymmetrie zwischen den zwei Scripts (oben: hook_firing REWRITE vs tool_use_errors
DELETE) ist damit aufgelöst — beide DELETE.

**Re-Eval-Trigger:** entfällt. Der workflow-shift (script-driven → human-in-the-loop
mit grep + heredoc + Probe-Hooks) ist die finale Richtung, keine Hypothese mehr.
Siehe `architecture.md` "Future Hook-Iteration Workflow".
