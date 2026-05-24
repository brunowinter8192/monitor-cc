# Hook Classification + FP-Potenzial Audit — 2026-05-24

**Topic:** Strukturierte Klassifikation aller 19 aktiven Hooks nach Purpose, Decision-Type,
Trigger-Specificity und FP-Risk. Output: drei Buckets — KEEP (solider Purpose + niedriges
FP-Risiko, kein Handlungsbedarf), MONITOR (jung, Daten fehlen) und REPORT (bekannte FP
oder kritisches Kipp-Status, braucht User-Entscheidung).

**Bead:** `Monitor_CC-8ggr` Thread 1.

**Prinzip (User-Direktive 2026-05-24):** Anzahl der Hooks ist KEIN Qualitäts-Indikator.
Eine schmale Hook pro selten-feuerndem Command ist besser als eine breite Hook die
versucht alles zu fangen und mehr bricht als repariert. Bewertet wird pro Hook:
solider Purpose + akzeptables FP-Risiko = KEEP, ansonsten Review.

---

## Klassifikations-Dimensionen

### A) Purpose-Klasse

| Klasse | Bedeutung |
|---|---|
| **Damage-Prevention** | Verhindert irreversible Operationen (wrong-process-killed, force-pushed, amended) |
| **Context-Flood** | Verhindert Output das den Agent-Kontext zerstört (oversize Reads, recursive grep, background-hidden output) |
| **State-Corruption** | Verhindert Writes die State zerstören (worktree-cd-drift, bd-from-worktree, wrong --repo bd-init, dep-symlinks in git-add) |
| **Workflow-Friction-Prevention** | Surfaced Errors die CC sonst per round-trip wirft (noop edit, read-on-directory, path-typo, git-ambiguous) |
| **Code-Style** | Erzwingt Projekt-Konventionen (dev/ imports src/, except: pass) |
| **Cost/Correctness** | Wirtschaftlich kritische Operationen (Opus als Worker = 20-40× Billing-Burn) |

### B) Decision-Type

| Type | Mechanism | Reversibilität |
|---|---|---|
| **block-stderr** | exit 2 + stderr, Agent sieht Reason | Agent kann anders retryen |
| **silent-rewrite** | exit 0 + updatedInput JSON, Agent sieht NICHTS | Rewrite ist final, Agent retryt nicht |

### C) Trigger-Specificity (primärer FP-Indikator)

| Stufe | Charakteristik | FP-Risiko |
|---|---|---|
| **Field-Check** | Einzelnes Bool/String-Feld checken (`run_in_background=true`, `isdir(path)`, `file_size > 256KB`, `old == new`) | **NULL** — deterministic |
| **Narrow-Regex** | Exakte Form-Match (`worker-cli spawn ... opus`, `except [Type]:\n    pass`, `git push --force`) | **Sehr niedrig** |
| **Pattern-mit-Exceptions** | Breitere Pattern mit expliziten Allow-Lists (broad-grep mit git-grep + --include= exemption) | **Niedrig** wenn Exemptions vollständig |
| **Heuristik-Pattern** | Pattern das fundamental rät (sleep cmd_before Semantik, bare-ref vs path) | **Mittel-Hoch** — bewertungsabhängig |

### D) Damage-on-Miss (Severity wenn der Hook eine echte Violation durchließe)

| Stufe | Beispiel |
|---|---|
| **Workflow-Friction** | API Round-Trip wasted (noop edit, read-directory) |
| **Context-Flood** | 10MB+ Output, 256KB+ Read, CLAUDE.md re-injection |
| **Data-Damage** | Wrong process killed, force-pushed branch, corrupted bd-state |

---

## Pro-Hook Klassifikation

### Damage-Prevention (3 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `block_dangerous_kill` | block | Narrow-Regex + explicit allow-list (pkill -x, numeric kill, worker-cli kill) | catastrophic (wrong process killed) | known scanner-gap heredoc-in-$() (catalog) | **KEEP** |
| `block_git_destructive` | block | Narrow-Regex (--amend, --force, --no-verify, --allow-empty, config-modify) | data-damage (history loss) | zero — explicit destructive flag matching | **KEEP** |
| `block_worker_spawn_opus` | block | Narrow-Regex (`worker-cli spawn ... opus`) | cost-damage (20-40× billing) | zero — explicit token check after spawn | **KEEP** |

### Context-Flood (5 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `block_read_oversize` | block | Field-Check (size + offset/limit/pages absent) | context-flood (256KB+) | zero — deterministic | **KEEP** |
| `block_read_worktree` | block | Path-Check + cwd-equality (own-worktree exemption) | context-flood (~50KB CLAUDE.md re-injection) | own-worktree exemption handles primary FP | **KEEP** |
| `block_broad_grep` | block | Pattern-mit-Exceptions (git-grep + --include= + file-target alle exempted) | context-flood (10MB+) | low — Exemptions explicit | **KEEP** |
| `block_venv_no_redirect` | block | Pattern (venv python .py without > redirect / `| tee`) | context-flood (python verbose output) | low — redirect/tee exemption | **KEEP** |
| `block_unauthorized_background` | block | Field-Check (run_in_background=true) + Narrow-Regex (canonical sleep N && echo done allowed) | context-flood (silent bg hides output) | **DOCUMENTED FP — Catalog: worker-cli send/echo/true/pwd in bg sind fast-returning legitimate** | **REPORT** |

### State-Corruption (4 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `block_bd_cli_worker` | block | Conditional (only from worktree CWD) | silent bead corruption on merge | should be near-zero — bd in worktree IS wrong | **KEEP** |
| `block_git_add_deps` | block | Narrow-Pattern (git add + venv|.venv|node_modules target) | broken merge (circular symlinks) | very low | **KEEP** |
| `rewrite_bd_invalid_repo` | rewrite | Field-Validation (path exists + has .beads/) | silent .beads/ init at wrong path | near-zero — validation deterministic | **KEEP** |
| `block_cd_drift` | block | Pattern (cd worktree as LAST cd target without cd-back) | wrong-dir-ops in next Bash call | **KIPP-KANDIDAT** (per pipe07_safety_hooks): "borderline could lead to wrong-dir-ops but rare" — unklare aktuelle Relevanz | **REPORT** |

### Workflow-Friction-Prevention (4 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `block_noop_edit` | block | Field-Check (old_string == new_string) | API round-trip wasted | zero — deterministic equality | **KEEP** |
| `block_read_directory` | block | Field-Check (os.path.isdir) | API round-trip wasted | zero — deterministic | **KEEP** |
| `block_path_typo` | rewrite (since 2026-05-22) | Narrow-Pattern (.claire/, ..letter) | retry with corrected path | very low — Edit-Matcher Anomalie dokumentiert betrifft NICHT-Firing nicht FP | **KEEP** |
| `rewrite_git_ambiguous` | rewrite | Heuristik-Pattern (bare-ref vs path-only detection + chain-op-position for `--` insertion) | confusing git error | **DOCUMENTED ACTIVE BUG (Bead Thread 1)** — inserted `--` an falscher Shell-Position wenn Command nicht mit `git` startet (variable-assignment, chained command) → produziert "command not found: --" | **REPORT** |

### Context-Flood — Rewrite (1 Hook, gerade gelandet)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `rewrite_chained_sleep` | rewrite | Heuristik-Pattern mit explicit narrow allow-list (nur `echo`+`true` cmd_before, loop-bodies + load-bearing pass-through) | output-hiding via missed sleep | low (narrow allow-list per audit) — **2026-05-24 gelandet, keine live Daten** | **MONITOR** |

### Code-Style (2 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP-Status | Verdict |
|---|---|---|---|---|---|
| `block_dev_imports_src` | block | Pattern (file_path matches /dev/ + content has `^from src\.` or `^import src\.`) | dev/ script becomes non-runnable | very low — clear architectural rule | **KEEP** |
| `block_except_pass` | block | Narrow-Regex (`except [Type]:\n    pass`) | silent exception swallow | very low — bare except-pass ist universal bad | **KEEP** |

---

## Verdict-Summary

| Verdict | Count | Hooks |
|---|---|---|
| **KEEP** (solider Purpose + niedriges FP-Risk, kein Action) | 15 | block_dangerous_kill, block_git_destructive, block_worker_spawn_opus, block_read_oversize, block_read_worktree, block_broad_grep, block_venv_no_redirect, block_bd_cli_worker, block_git_add_deps, rewrite_bd_invalid_repo, block_noop_edit, block_read_directory, block_path_typo, block_dev_imports_src, block_except_pass |
| **MONITOR** (jung, Daten fehlen — 1-2 Wochen abwarten) | 1 | rewrite_chained_sleep |
| **REPORT** (dokumentierte FP oder Kipp-Status, braucht User-Entscheidung) | 3 | rewrite_git_ambiguous, block_unauthorized_background, block_cd_drift |

15 von 19 Hooks haben soliden Purpose ohne nennenswerte FP-Wahrscheinlichkeit — diese
brauchen keine weitere Diskussion. Per User-Prinzip: KEEP, fertig.

`rewrite_chained_sleep` ist heute (2026-05-24) gelandet, hat noch keine Live-Daten. Audit
basiert auf historischen Sleep-Patterns (`dev/sleep_pattern_analysis/`), narrow Allow-Liste
(`echo`/`true` cmd_before only) hält theoretisches FP-Risiko niedrig. Re-Eval in ~7 Tagen
sobald Live-Daten im neuen `hook_firing.jsonl` (Bead Thread 2) sichtbar sind.

Die 3 REPORT-Hooks werden separat im Chat mit Detail-Analyse und Entscheidungs-Optionen
an den User vorgelegt.

---

## Quellen

- `src/hooks/DOCS.md` (komplette Hook-Map, Purpose/Reads/Writes/Allowed/Blocked Patterns
  pro Hook)
- `decisions/pipe07_safety_hooks.md` (Hook IST + KIPP-Kandidaten-Liste 2026-05-22)
- `decisions/OldThemes/tool_use_safety/2026-05-22_hook_principle_block_vs_allow.md`
  (Klassifikations-Vorgänger: TILT-Hooks vs KIPP-Kandidaten)
- `decisions/OldThemes/audit_logging/failure_patterns_catalog.md` (per-Hook
  FP/TP-Heuristiken die heutige FP-Status-Spalte fundieren)
- Bead `Monitor_CC-8ggr` Thread 1 Description (konkret bekannter rewrite_git_ambiguous
  Bug — shell-position FP bei variable-assignment-prefix)
