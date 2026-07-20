# Failure-Patterns Catalog — Historical Reference (2026-05-24)

**Topic:** static archive of the failure-class fingerprints and hook-FP heuristics that
were encoded in the deleted scripts `dev/hook_firing/analyze.py` and
`dev/tool_use_errors/analyze.py`. Reference material for hook iteration.

**Status:** Historical. NOT maintained as code, NOT auto-updated. Consulted manually by
the implementer when needed. Snapshot reflects state at 2026-05-24 (last commit before
script deletion).

---

## Part 1 — Failure-Class Fingerprints
*(ex `dev/tool_use_errors/analyze.py`, 18 patterns × 6 hookability buckets)*

Regex/tag constants matched against `tool_result.content` strings to identify a given
failure class. `is_error: true` precondition per pattern (except for Bash-command
patterns like the cat-heredoc one, which match directly on `tool_input`).

### Hookability Buckets

| Bucket | Meaning |
|---|---|
| `pre-blockable` | Deterministic regex match on tool_input → exit-2 hook possible |
| `pre-rewritable` | Pattern detected AND an updatedInput rewrite would fix it |
| `prompt-hook-candidate` | Regex too brittle, needs a short LLM-check decision |
| `not-statically-hookable` | Needs session state not present in tool_input |
| `runtime-only` | CC dispatches before PreToolUse fires |
| `already-hooked` | Pattern has a live `src/hooks/` script |

### Patterns

| ID | Hookability | Hook (if any) | Fingerprint |
|---|---|---|---|
| `parallel-cancel` | runtime-only | — | `is_error AND "Cancelled: parallel tool call" in err` |
| `read-before-edit` | not-statically-hookable | — | `is_error AND "File has not been read yet" in err` |
| `file-modified` | not-statically-hookable | — | `is_error AND "File has been modified since read" in err` |
| `user-rejected` | not-statically-hookable | — | `is_error AND "The user doesn't want to proceed" in err` |
| `hook-blocked` | already-hooked | (any hook) | `is_error AND regex r'PreToolUse:\w+ hook error:.*BLOCKED'` |
| `git-ambiguous` | pre-rewritable | rewrite_git_ambiguous.py | `is_error AND regex r'fatal: ambiguous argument'` |
| `edit-string-not-found` | prompt-hook-candidate | — | `is_error AND ("String to replace not found" OR <tool_use_error> with same)` |
| `validation-error` | pre-blockable | — | `is_error AND ("Input validation error" OR <tool_use_error> with 'validation')` |
| `tool-unavailable` | pre-blockable | — | `is_error AND ("Error: No such tool available" OR "Unknown skill:")` |
| `read-oversize` | pre-blockable | block_read_oversize.py (256KB only) | `is_error AND regex r'exceeds maximum allowed (size\|tokens)'` |
| `noop-edit` | already-hooked | block_noop_edit.py | `is_error AND "No changes to make: old_string and new_string" in err` |
| `cat-heredoc` | pre-blockable | — | `tool=Bash AND regex r'cat\s*(?!>)>\s*\S+\s*<<\s*[\'"]?EOF'` |
| `broad-grep` | already-hooked | block_broad_grep.py | `tool=Bash AND grep -r without --include= AND not git-grep` |
| `sleep-noncanonical` | already-hooked | rewrite_chained_sleep.py (ex block_chained_sleep.py) | `tool=Bash AND regex r'\bsleep\s+\d' AND not canonical "sleep N && echo done"+run_in_bg` |
| `claire-typo` | already-hooked | block_path_typo.py | `'.claire/' in cmd OR in file_path` |
| `bg-trivial` | already-hooked | block_unauthorized_background.py | `tool=Bash AND run_in_bg=true AND regex r'\s*(grep\|cat\|ls\|wc\|git\s+status\|head\|tail)\b'` |
| `venv-no-redirect` | already-hooked | block_venv_no_redirect.py | `tool=Bash AND regex r'\.?\.?/?venv/bin/python\s+\S+\.py\b' AND no '>' redirect` |
| `diag-chain-and` | prompt-hook-candidate | — | `tool=Bash AND '&&' in cmd AND regex r'(^\|&&\|\|\|)\s*(grep\|ls\|wc\|test\|[\s+-fd])\s*&&'` |

---

## Part 2 — Per-Hook FP/TP Heuristics
*(ex `dev/hook_firing/analyze.py:_classify_fp`)*

These heuristics classified fired block events as FP/TP/uncertain. Based on concrete
audit findings between 2026-05-12 and 2026-05-24.

### block_chained_sleep
| Condition | Verdict | Rationale |
|---|---|---|
| `"$(cat <<"` or `"$( cat <<"` in cmd | **FP** | heredoc-in-$() scanner gap: sleep in $(...) body not stripped |
| sleep in while/for/until loop body | **TP** | real polling pattern |
| `run_in_background=true` + non-canonical sleep | **TP** | not the canonical `sleep N && echo done` form |
| `sleep N > 10` in foreground | **TP** | intentional wait, no output hiding |
| `sleep N ≤ 5` directly after a side effect (pkill/launchctl/kickstart/bootout/`kill -N`/worker-cli kill/systemctl) | **FP** | settling-time before verification, rule too strict |
| `sleep N ≤ 10` without clear context | **uncertain** | — |

### block_dangerous_kill
| Condition | Verdict |
|---|---|
| `"$(cat <<"` in cmd | **FP** (scanner gap) |
| `pkill -f` in active command | **TP** |
| otherwise | **uncertain** |

### block_cd_drift
| Condition | Verdict |
|---|---|
| `.claude/worktrees/` in cmd | **TP** (cd into worktree without cd-back) |
| otherwise | **uncertain** (worktree path not visible in trigger) |

### block_read_worktree
| Condition | Verdict |
|---|---|
| main-session reads worktree-path | **TP** |
| worker-session reads worktree-path | **uncertain** (own vs cross worktree unclear) |

### block_broad_grep
| Condition | Verdict |
|---|---|
| `git grep` in cmd | **FP** (hook exempts git grep) |
| `--include=` in cmd | **FP** (hook should not block) |
| otherwise | **TP** (recursive grep without scope) |

### block_unauthorized_background
| Condition | Verdict |
|---|---|
| cmd matches `worker-cli send` / `echo` / `true` / `pwd` | **FP** (fast-returning command) |
| otherwise | **TP** (non-canonical bg) |

### block_venv_no_redirect
| Condition | Verdict |
|---|---|
| venv script + `>` redirect or `\| tee` | **FP** (redirect present) |
| venv script without redirect | **TP** |
| otherwise | **uncertain** |

### Hooks Without a Heuristic
`block_path_typo`, `block_noop_edit`, `block_read_directory`, `block_read_oversize`,
`block_dev_imports_src`, `block_except_pass`, `block_git_add_deps`,
`block_git_destructive`, `block_bd_cli_worker`, `block_worker_spawn_opus`,
`rewrite_git_ambiguous`, `rewrite_bd_invalid_repo`, `rewrite_chained_sleep` — no
built-in FP classifier in the deleted script, always "uncertain" or not covered.

---

## How This Catalog Is Consumed

When building a new hook or refining an existing one:

1. **Catalog lookup:** is the targeted failure class already documented here? If so →
   pattern + hookability bucket as a starting point.
2. **Heuristic lookup for existing hooks:** when working on an existing hook — which
   FP/TP patterns were established in audit rounds? Read directly from Part 2.
3. **Build a probe hook** per the hook-iteration workflow.
4. **Pattern update:** if a new failure class is discovered during hook work — append it
   here manually. Append-only, timestamped edits.
