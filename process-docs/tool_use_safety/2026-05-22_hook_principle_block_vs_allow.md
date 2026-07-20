# Hook Principle: Block vs Allow — Damage-Centric Reframe (2026-05-22)

## Context

Session 2026-05-22 sharpened the hook-system operating principle. Until today, all 18 PreToolUse hooks used exit 2 (block) on a rule violation. User observation during the session: red blocks feel high-FP / borderline-FP. Sometimes literal pattern strings inside QUOTED command arguments (e.g. a worker-cli send carrying a smoke-test instruction) triggered hooks that scan the raw command text.

Two empirical incidents this session:
- `block_broad_grep.py` blocked a `worker-cli send` because the message body contained a recursive-grep pattern as documentation for the worker. The hook saw the pattern in the raw command, didn't strip the quoted region first.
- `block_broad_grep.py` ALSO blocked a `bd create` call with the same pattern in the description. Same FP class.
- `rewrite_git_ambiguous.py` blocked `git branch --show-current` because the regex matched `show` inside `--show-current` (missing negative lookbehind).

Both were fixed today (a `shell-strip` worker for the first class, a `hook-sweep` follow-up for the second), but they prompted the bigger question: what SHOULD hooks block?

## Sharpened Principle

**Hooks block on damage. Damage has two classes:**

1. **Irreversible action damage** — `pkill -f` killing workers, `git push --force` destroying history, `worker-cli spawn opus` burning 20-40× billing, `git add venv/` permanently poisoning the repo.
2. **Context-window flooding damage** — `grep -rn` over .git/node_modules dumping 10MB+ into context, python script output without a `>` redirect, Read on a worktree CLAUDE.md re-injecting ~50KB tokens. Token burn is irreversible on the session context.

Anti-patterns that are NOT damage (just friction, suboptimal style, an edge-case-bug indicator) — let them through. The hook system should be a positive guardrail, not constant FP noise.

## FP-Rate Evidence (from `dev/hook_firing/reports/2026-05-22_012326.md`)

Period: 2026-05-15 to 2026-05-22. Total blocks: 87.

| Hook | Blocks | TP | FP | FP-Rate |
|---|---|---|---|---|
| **block_chained_sleep** | 29 | 4 | **13** | **45%** |
| block_unauthorized_background | 2 | 1 | 1 | 50% (small sample) |
| block_dangerous_kill | 16 | 15 | 0 | 0% |
| block_broad_grep | 7 | 7 | 0 | 0% (pre-shell-strip; today: 2 new FPs) |
| block_path_typo | 7 | 0 | 0 | 0% (all uncertain) |
| block_except_pass | 5 | 0 | 0 | 0% (all uncertain) |
| block_read_worktree | 11 | 1 | 0 | 0% (10 uncertain) |
| All others | <5 each | mostly TP | 0 | 0% |

`block_chained_sleep` is the primary FP generator. `launchctl bootout ... ; cmd` patterns + `rag-cli ... && sleep ; cmd` patterns fall into its trigger regex even though the `&&`-chain or `;`-chain is semantically not a "sleep N && X" form.

## Mapping All 18 Hooks Against the Principle

### KEEP BLOCK — 11 Hooks (Genuine Damage Prevention)

| Hook | Damage class | Rationale |
|---|---|---|
| block_dangerous_kill | irreversible | pkill-f kills workers irreversibly |
| block_git_destructive | irreversible | force-push / amend destroys history |
| block_worker_spawn_opus | irreversible | 20-40× billing + destroys the verification architecture |
| block_git_add_deps | irreversible | committed deps poison the repo |
| block_bd_cli_worker | irreversible | worker manipulates Opus-only state |
| block_dev_imports_src | irreversible | architectural violation with dep chaos |
| block_except_pass | irreversible | silent error swallowing = debug nightmare |
| block_broad_grep | context-flood | `grep -rn` dumps 10MB+ into context |
| block_venv_no_redirect | context-flood | python stdout without `>` floods directly into context |
| block_read_oversize | context-flood | Read on a >256KB file would load 256KB+ |
| block_read_worktree | context-flood | CLAUDE.md re-injection ~50KB |

### FLIP CANDIDATES — 7 Hooks (Friction Without Damage)

| Hook | Status at the time | Reasoning |
|---|---|---|
| block_chained_sleep | 45% FP, highest absolute count | `sleep N && X` hides output, but no damage. FP pattern: legitimate launchctl chains. |
| block_unauthorized_background | borderline | Background mode can be indirectly flooding via worker_capture, but the primary effect is output-hiding |
| rewrite_git_ambiguous | borderline | git itself handles real ambiguity — the hook is redundant |
| block_path_typo | clean | a typo error from the tool is already clean (file-not-found = a clear message) |
| block_cd_drift | borderline | could lead to wrong-dir ops, but rare |
| block_noop_edit | clean | indicates a bug but no damage; user gets info without a block |
| block_read_directory | clean | tool error is already clean |

## Decision (Defer Until Data)

The hook system had run since 2026-05-21 — a single week. Before consolidating the 7 flip candidates, more data was needed:

1. at least 2-3 weeks of FP/TP classification in `dev/hook_firing/reports/`
2. delta audits per cutoff marker (built into `dev/tool_use_errors/analyze.py` today)
3. per flip candidate: FP count, TP count, frequency-per-session
4. then decide: convert exit 2 to exit 0 OR deregister from `hook_setup.py`

User directive ("from now on we collect data") + status-quo retained as of 2026-05-22.

A tracking task was opened for this audit cycle.

## Per-Incident Workflow (Until the Audit Cycle Is Reached)

Whenever a red block event occurs:
1. Analysis: would the unblocked call really cause damage (irreversible OR context-flood)?
2. If yes: the hook did its job, workflow retry accepted.
3. If no: a data point for the audit, possibly ad-hoc flip the hook to allow.

Data-driven, low risk exposure, decidable per hook instead of a big-bang migration.

## CC-API Constraint

Auto-rewrite via `PreToolUse + allow + updatedInput` for general Bash is EMPIRICALLY REFUTED at the time (CC CHANGELOG line 1324 — scoped to the AskUserQuestion tool). `permissionDecision: "ask"` produces a user dialog (workflow tax, rejected). For general PreToolUse Bash only exit 0 (allow silent) or exit 2 (block stderr) remain. Silent rewrite is not an option — the conversion is therefore exit 2 → exit 0 for the 7 flip candidates.

(Note: this constraint was later found to be incorrect for `acceptEdits` mode — see the hook-API-auto-rewrite-works entry in this area, same date, later session.)

## Sources

- `dev/hook_firing/reports/2026-05-22_012326.md` (FP/TP evidence)
- `dev/tool_use_analysis/20260522_rule_compliance.md` (pattern frequency with audit cutoff)
- The hook-API-capabilities entry in this area (CC-API constraint)
- `src/hooks/DOCS.md` (hook list)
