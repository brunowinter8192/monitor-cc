# Hook Classification + FP-Potential Audit — 2026-05-24

**Topic:** structured classification of all 19 active hooks by purpose, decision type,
trigger specificity, and FP risk. Output: three buckets — KEEP (solid purpose + low
FP risk, no action needed), MONITOR (young, data missing), and REPORT (known FP
or a critical flip-status, needs a user decision).

**Principle (user directive 2026-05-24):** hook count is NOT a quality indicator.
A narrow hook per rarely-firing command is better than a broad hook that tries to
catch everything and breaks more than it fixes. Evaluated per hook: solid purpose
+ acceptable FP risk = KEEP, otherwise review.

---

## Classification Dimensions

### A) Purpose Class

| Class | Meaning |
|---|---|
| **Damage-Prevention** | Prevents irreversible operations (wrong-process-killed, force-pushed, amended) |
| **Context-Flood** | Prevents output that destroys agent context (oversize reads, recursive grep, background-hidden output) |
| **State-Corruption** | Prevents writes that destroy state (worktree-cd-drift, bd-from-worktree, wrong --repo bd-init, dep-symlinks in git-add) |
| **Workflow-Friction-Prevention** | Surfaces errors CC would otherwise throw via a round-trip (noop edit, read-on-directory, path-typo, git-ambiguous) |
| **Code-Style** | Enforces project conventions (dev/ imports src/, except: pass) |
| **Cost/Correctness** | Economically critical operations (Opus as a worker = 20-40× billing burn) |

### B) Decision Type

| Type | Mechanism | Reversibility |
|---|---|---|
| **block-stderr** | exit 2 + stderr, agent sees the reason | agent can retry differently |
| **silent-rewrite** | exit 0 + updatedInput JSON, agent sees NOTHING | rewrite is final, agent doesn't retry |

### C) Trigger Specificity (Primary FP Indicator)

| Level | Characteristic | FP risk |
|---|---|---|
| **Field-Check** | Checks a single bool/string field (`run_in_background=true`, `isdir(path)`, `file_size > 256KB`, `old == new`) | **NULL** — deterministic |
| **Narrow-Regex** | Exact form match (`worker-cli spawn ... opus`, `except [Type]:\n    pass`, `git push --force`) | **Very low** |
| **Pattern-With-Exceptions** | Broader pattern with explicit allow-lists (broad-grep with git-grep + --include= exemption) | **Low** when exemptions are complete |
| **Heuristic-Pattern** | A pattern that fundamentally guesses (sleep cmd_before semantics, bare-ref vs path) | **Medium-high** — evaluation-dependent |

### D) Damage-on-Miss (Severity If the Hook Let a Real Violation Through)

| Level | Example |
|---|---|
| **Workflow-Friction** | Wasted API round-trip (noop edit, read-directory) |
| **Context-Flood** | 10MB+ output, 256KB+ read, CLAUDE.md re-injection |
| **Data-Damage** | Wrong process killed, force-pushed branch, corrupted bd state |

---

## Per-Hook Classification

### Damage-Prevention (3 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `block_dangerous_kill` | block | Narrow-Regex + explicit allow-list (pkill -x, numeric kill, worker-cli kill) | catastrophic (wrong process killed) | known scanner-gap heredoc-in-$() (catalog) | **KEEP** |
| `block_git_destructive` | block | Narrow-Regex (--amend, --force, --no-verify, --allow-empty, config-modify) | data-damage (history loss) | zero — explicit destructive flag matching | **KEEP** |
| `block_worker_spawn_opus` | block | Narrow-Regex (`worker-cli spawn ... opus`) | cost-damage (20-40× billing) | zero — explicit token check after spawn | **KEEP** |

### Context-Flood (5 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `block_read_oversize` | block | Field-Check (size + offset/limit/pages absent) | context-flood (256KB+) | zero — deterministic | **KEEP** |
| `block_read_worktree` | block | Path-check + cwd-equality (own-worktree exemption) | context-flood (~50KB CLAUDE.md re-injection) | own-worktree exemption handles the primary FP | **KEEP** |
| `block_broad_grep` | block | Pattern-with-exceptions (git-grep + --include= + file-target all exempted) | context-flood (10MB+) | low — exemptions explicit | **KEEP** |
| `block_venv_no_redirect` | block | Pattern (venv python .py without > redirect / `| tee`) | context-flood (python verbose output) | low — redirect/tee exemption | **KEEP** |
| `block_unauthorized_background` | block | Field-Check (run_in_background=true) + Narrow-Regex (canonical sleep N && echo done allowed) | context-flood (silent bg hides output) | **DOCUMENTED FP — catalog: worker-cli send/echo/true/pwd in bg are fast-returning, legitimate** | **REPORT** |

### State-Corruption (4 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `block_bd_cli_worker` | block | Conditional (only from worktree CWD) | silent bead corruption on merge | should be near-zero — bd in a worktree IS wrong | **KEEP** |
| `block_git_add_deps` | block | Narrow-Pattern (git add + venv|.venv|node_modules target) | broken merge (circular symlinks) | very low | **KEEP** |
| `rewrite_bd_invalid_repo` | rewrite | Field-Validation (path exists + has .beads/) | silent .beads/ init at the wrong path | near-zero — validation deterministic | **KEEP** |
| `block_cd_drift` | block | Pattern (cd worktree as the LAST cd target without cd-back) | wrong-dir-ops in the next Bash call | **FLIP CANDIDATE** (per the safety-hooks current-state doc): "borderline could lead to wrong-dir-ops but rare" — current relevance unclear | **REPORT** |

### Workflow-Friction-Prevention (4 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `block_noop_edit` | block | Field-Check (old_string == new_string) | wasted API round-trip | zero — deterministic equality | **KEEP** |
| `block_read_directory` | block | Field-Check (os.path.isdir) | wasted API round-trip | zero — deterministic | **KEEP** |
| `block_path_typo` | rewrite (since 2026-05-22) | Narrow-Pattern (.claire/, ..letter) | retry with corrected path | very low — the documented Edit-matcher anomaly affects non-firing, not FP | **KEEP** |
| `rewrite_git_ambiguous` | rewrite | Heuristic-Pattern (bare-ref vs path-only detection + chain-op position for `--` insertion) | confusing git error | **DOCUMENTED ACTIVE BUG** — inserts `--` at the wrong shell position when the command doesn't start with `git` (variable assignment, chained command) → produces "command not found: --" | **REPORT** |

### Context-Flood — Rewrite (1 Hook, Just Landed)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `rewrite_chained_sleep` | rewrite | Heuristic-Pattern with an explicit narrow allow-list (only `echo`+`true` cmd_before, loop-bodies + load-bearing pass-through) | output-hiding via missed sleep | low (narrow allow-list per audit) — **landed 2026-05-24, no live data yet** | **MONITOR** |

### Code-Style (2 Hooks)

| Hook | Decision | Specificity | Damage-on-Miss | FP Status | Verdict |
|---|---|---|---|---|---|
| `block_dev_imports_src` | block | Pattern (file_path matches /dev/ + content has `^from src\.` or `^import src\.`) | dev/ script becomes non-runnable | very low — a clear architectural rule | **KEEP** |
| `block_except_pass` | block | Narrow-Regex (`except [Type]:\n    pass`) | silent exception swallow | very low — bare except-pass is universally bad | **KEEP** |

---

## Verdict Summary

| Verdict | Count | Hooks |
|---|---|---|
| **KEEP** (solid purpose + low FP risk, no action) | 15 | block_dangerous_kill, block_git_destructive, block_worker_spawn_opus, block_read_oversize, block_read_worktree, block_broad_grep, block_venv_no_redirect, block_bd_cli_worker, block_git_add_deps, rewrite_bd_invalid_repo, block_noop_edit, block_read_directory, block_path_typo, block_dev_imports_src, block_except_pass |
| **MONITOR** (young, data missing — wait 1-2 weeks) | 1 | rewrite_chained_sleep |
| **REPORT** (documented FP or flip status, needs a user decision) | 3 | rewrite_git_ambiguous, block_unauthorized_background, block_cd_drift |

15 of 19 hooks have a solid purpose with no notable FP probability — these
need no further discussion. Per the user principle: KEEP, done.

`rewrite_chained_sleep` landed today (2026-05-24), has no live data yet. The audit
is based on historical sleep patterns (`dev/sleep_pattern_analysis/`); the narrow allow-list
(`echo`/`true` cmd_before only) keeps the theoretical FP risk low. Re-eval in ~7 days
once live data is visible in the new `hook_firing.jsonl`.

The 3 REPORT hooks are presented separately in chat with a detailed analysis and
decision options for the user.

---

## Sources

- `src/hooks/DOCS.md` (the complete hook map, purpose/reads/writes/allowed/blocked patterns
  per hook)
- The proxy-cache pipeline's safety-hooks current-state doc (hook state + flip-candidate list as of 2026-05-22)
- The hook-principle-block-vs-allow entry in this area (classification predecessor: TILT hooks vs flip candidates)
- The failure-patterns-catalog entry in the audit_logging area (per-hook FP/TP heuristics that ground today's FP-status column)
- A closed tracking task's thread 1 description (a concretely known rewrite_git_ambiguous
  bug — shell-position FP on a variable-assignment prefix)
