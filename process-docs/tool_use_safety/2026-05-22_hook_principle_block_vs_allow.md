# Hook Principle: Block vs Allow — Damage-Centric Reframe (2026-05-22)

## Context

Session 2026-05-22 sharpened the Hook-System operating principle. Until today, 18 PreToolUse-Hooks all used exit 2 (block) on rule violation. User observation during the session: red blocks feel high-FP / borderline-FP. Sometimes literal pattern strings inside QUOTED command arguments (e.g. worker-cli send carrying a smoke-test instruction) triggered Hooks that scan the raw command text.

Two empirical incidents this session:
- `block_broad_grep.py` blocked `worker-cli send` because the message body contained a recursive-grep pattern as documentation for the worker. Hook saw the pattern in raw command, didn't strip the quoted region first.
- `block_broad_grep.py` ALSO blocked a `bd create` call with the same pattern in the description. Same FP-class.
- `rewrite_git_ambiguous.py` blocked `git branch --show-current` because the regex matched `show` inside `--show-current` (negative-lookbehind missing).

Both got fixed today (`shell-strip` worker for the first class, `hook-sweep` follow-up for the second), but they prompted the bigger question: what SHOULD hooks block?

## Sharpened Principle

**Hooks block on Damage. Damage has two classes:**

1. **Irreversible action damage** — `pkill -f` killing workers, `git push --force` destroying history, `worker-cli spawn opus` burning 20-40× billing, `git add venv/` permanently poisoning the repo.
2. **Context-window flooding damage** — `grep -rn` over .git/node_modules dumping 10MB+ into context, python script output without `>` redirect, Read on a worktree CLAUDE.md re-injecting ~50KB tokens. Token-burn is irreversible on the session context.

Anti-patterns that are NOT damage (just friction, suboptimal style, edge-case-bug-indicator) — let them through. The hook system should be a positive guardrail, not constant FP-noise.

## FP-Rate Evidence (from `dev/hook_firing/reports/2026-05-22_012326.md`)

Period: 2026-05-15 to 2026-05-22. Total blocks: 87.

| Hook | Blocks | TP | FP | FP-Rate |
|---|---|---|---|---|
| **block_chained_sleep** | 29 | 4 | **13** | **45%** |
| block_unauthorized_background | 2 | 1 | 1 | 50% (kleines Sample) |
| block_dangerous_kill | 16 | 15 | 0 | 0% |
| block_broad_grep | 7 | 7 | 0 | 0% (pre-shell-strip; today: 2 neue FPs) |
| block_path_typo | 7 | 0 | 0 | 0% (alle uncertain) |
| block_except_pass | 5 | 0 | 0 | 0% (alle uncertain) |
| block_read_worktree | 11 | 1 | 0 | 0% (10 uncertain) |
| Alle anderen | <5 each | meist TP | 0 | 0% |

`block_chained_sleep` ist der primäre FP-Generator. `launchctl bootout ... ; cmd` Patterns + `rag-cli ... && sleep ; cmd` Patterns fallen in seine Trigger-Regex obwohl die `&&`-Chain bzw `;`-Chain semantisch keine "sleep N && X" Form ist.

## Mapping aller 18 Hooks gegen das Prinzip

### KEEP BLOCK — 11 Hooks (echte Damage-Verhinderung)

| Hook | Damage-Klasse | Begründung |
|---|---|---|
| block_dangerous_kill | irreversible | pkill-f killt Worker irreversibel |
| block_git_destructive | irreversible | force-push / amend zerstört history |
| block_worker_spawn_opus | irreversible | 20-40× Billing + zerstört Verifikations-Architektur |
| block_git_add_deps | irreversible | committed deps verseuchen Repo |
| block_bd_cli_worker | irreversible | Worker manipuliert Opus-only-State |
| block_dev_imports_src | irreversible | architektonische Verletzung mit Dep-Chaos |
| block_except_pass | irreversible | silent error swallowing = Debug-Nightmare |
| block_broad_grep | context-flood | grep -rn dumpt 10MB+ in Context |
| block_venv_no_redirect | context-flood | python stdout ohne `>` flooded direct in Context |
| block_read_oversize | context-flood | Read auf >256KB File würde 256KB+ laden |
| block_read_worktree | context-flood | CLAUDE.md re-injection ~50KB |

### KIPP-KANDIDATEN — 7 Hooks (Friction ohne Schaden)

| Hook | Aktueller Status | Reasoning |
|---|---|---|
| block_chained_sleep | 45% FP, höchster Absolutwert | `sleep N && X` versteckt Output, aber kein Damage. FP-Pattern: legitimate launchctl chains. |
| block_unauthorized_background | borderline | Background-mode kann indirekt floodig sein via worker_capture, aber primary effect ist Output-hiding |
| rewrite_git_ambiguous | borderline | git selbst handelt echte Ambiguität — Hook ist redundant |
| block_path_typo | clean | Tool errored bei typo eh sauber (file not found = klare Meldung) |
| block_cd_drift | borderline | Könnte zu wrong-dir-ops führen, aber rare |
| block_noop_edit | clean | Indiziert Bug aber kein Damage; user gets info ohne block |
| block_read_directory | clean | Tool errored eh sauber |

## Decision (Defer until Data)

Hook-System läuft seit 2026-05-21 — eine einzige Woche. Vor einer Konsolidierung der 7 Kipp-Kandidaten brauchen wir mehr Daten:

1. mindestens 2-3 Wochen FP/TP-Klassifikation in `dev/hook_firing/reports/`
2. delta-Audits per Cutoff-Marker (heute eingebaut in `dev/tool_use_errors/analyze.py`)
3. pro Kipp-Kandidat: FP-Count, TP-Count, Frequency-per-Session
4. dann entscheiden: exit 2 zu exit 0 konvertieren ODER aus `hook_setup.py` deregistrieren

User-Direktive ("ab jetzt sammeln wir daten") + status-quo-Belassung von 2026-05-22.

Bead `Monitor_CC-22wq` trackt diesen Audit-Zyklus.

## Per-Incident Workflow (until Audit-Cycle reached)

Sobald ein roter Block-Event auftritt:
1. Analyse: macht der unblockierte Call wirklich Damage (irreversible ODER context-flood)?
2. Wenn ja: Hook hat seinen Job gemacht, Workflow-Retry akzeptiert.
3. Wenn nein: Daten-Punkt für 22wq, evtl. ad-hoc Hook auf Allow kippen.

Datengetrieben, niedrige Risk-Exposure, pro Hook entscheidbar statt big-bang Migration.

## CC-API Constraint

Auto-Rewrite via `PreToolUse + allow + updatedInput` für general Bash ist EMPIRISCH REFUTED (CC CHANGELOG line 1324 — scoped to AskUserQuestion tool). `permissionDecision: "ask"` produziert User-Dialog (Workflow-Tax, abgelehnt). Für general PreToolUse Bash bleiben nur: exit 0 (allow silent) oder exit 2 (block stderr). Silent-Rewrite kein Option — die Konvertierung wird daher exit 2 → exit 0 für die 7 Kipp-Kandidaten.

## Quellen

- `dev/hook_firing/reports/2026-05-22_012326.md` (FP/TP Evidenz)
- `dev/tool_use_analysis/20260522_rule_compliance.md` (Pattern-Frequency mit Audit-Cutoff)
- `decisions/OldThemes/tool_use_safety/2026-05-22_hook_api_capabilities.md` (CC-API Constraint)
- `decisions/pipe07_safety_hooks.md` (Hook IST)
- `src/hooks/DOCS.md` (Hook-Liste)
- Bead `Monitor_CC-22wq` (Audit-Trigger-Conditions + Action-Plan)
