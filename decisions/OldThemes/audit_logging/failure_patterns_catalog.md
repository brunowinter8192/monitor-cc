# Failure-Patterns Catalog — Historical Reference (2026-05-24)

**Topic:** Statisches Archiv der Failure-Klassen-Fingerprints und Hook-FP-Heuristiken
die in den gelöschten Scripts `dev/hook_firing/analyze.py` und
`dev/tool_use_errors/analyze.py` encoded waren. Reference-Material für
Hook-Iteration — siehe `architecture.md` "Future Hook-Iteration Workflow" für
den Workflow der diese Patterns konsumiert.

**Status:** Historical. Wird NICHT als Code maintained, NICHT auto-updated. Bei
Bedarf vom Implementierenden manuell konsultiert. Snapshot reflects state at
2026-05-24 (last commit before script deletion).

---

## Teil 1 — Failure-Klassen-Fingerprints
*(ex `dev/tool_use_errors/analyze.py`, 18 Patterns × 6 Hookability-Buckets)*

Regex/Tag-Konstanten die in `tool_result.content` strings matchen um eine bestimmte
Failure-Klasse zu identifizieren. `is_error: true` Vorbedingung pro Pattern
(ausser bei Bash-Command-Pattern wie cat-heredoc die direkt auf `tool_input` matchen).

### Hookability-Buckets

| Bucket | Bedeutung |
|---|---|
| `pre-blockable` | Deterministischer Regex-Match auf tool_input → exit-2 Hook möglich |
| `pre-rewritable` | Pattern detected AND updatedInput Rewrite würde es fixen |
| `prompt-hook-candidate` | Regex zu brittle, kurze LLM-Check Entscheidung |
| `not-statically-hookable` | Braucht Session-State der nicht in tool_input ist |
| `runtime-only` | CC dispatched bevor PreToolUse feuert |
| `already-hooked` | Pattern hat live `src/hooks/` Script |

### Patterns

| ID | Hookability | Hook (falls existent) | Fingerprint |
|---|---|---|---|
| `parallel-cancel` | runtime-only | — | `is_error AND "Cancelled: parallel tool call" in err` |
| `read-before-edit` | not-statically-hookable | — | `is_error AND "File has not been read yet" in err` |
| `file-modified` | not-statically-hookable | — | `is_error AND "File has been modified since read" in err` |
| `user-rejected` | not-statically-hookable | — | `is_error AND "The user doesn't want to proceed" in err` |
| `hook-blocked` | already-hooked | (jeder Hook) | `is_error AND regex r'PreToolUse:\w+ hook error:.*BLOCKED'` |
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

## Teil 2 — Per-Hook FP/TP-Heuristiken
*(ex `dev/hook_firing/analyze.py:_classify_fp`)*

Diese Heuristiken klassifizierten gefeuerte Block-Events als FP/TP/uncertain.
Basieren auf konkreten Audit-Befunden zwischen 2026-05-12 und 2026-05-24.

### block_chained_sleep
| Bedingung | Verdict | Begründung |
|---|---|---|
| `"$(cat <<"` oder `"$( cat <<"` in cmd | **FP** | heredoc-in-$() Scanner-Gap: sleep in $(...) body wird nicht gestrippt |
| sleep in while/for/until loop body | **TP** | real polling pattern |
| `run_in_background=true` + non-canonical sleep | **TP** | nicht der canonical `sleep N && echo done` form |
| `sleep N > 10` in foreground | **TP** | intentional wait, kein Output-Hiding |
| `sleep N ≤ 5` direkt nach side-effect (pkill/launchctl/kickstart/bootout/`kill -N`/worker-cli kill/systemctl) | **FP** | settling-time vor verification, rule-too-strict |
| `sleep N ≤ 10` ohne klaren Kontext | **uncertain** | — |

### block_dangerous_kill
| Bedingung | Verdict |
|---|---|
| `"$(cat <<"` in cmd | **FP** (Scanner-Gap) |
| `pkill -f` in active command | **TP** |
| sonst | **uncertain** |

### block_cd_drift
| Bedingung | Verdict |
|---|---|
| `.claude/worktrees/` in cmd | **TP** (cd into worktree ohne cd-back) |
| sonst | **uncertain** (worktree path nicht visible in trigger) |

### block_read_worktree
| Bedingung | Verdict |
|---|---|
| main-session reads worktree-path | **TP** |
| worker-session reads worktree-path | **uncertain** (own vs cross worktree unklar) |

### block_broad_grep
| Bedingung | Verdict |
|---|---|
| `git grep` in cmd | **FP** (Hook exempted git grep) |
| `--include=` in cmd | **FP** (Hook sollte nicht blocken) |
| sonst | **TP** (recursive grep ohne scope) |

### block_unauthorized_background
| Bedingung | Verdict |
|---|---|
| cmd matches `worker-cli send` / `echo` / `true` / `pwd` | **FP** (fast-returning command) |
| sonst | **TP** (non-canonical bg) |

### block_venv_no_redirect
| Bedingung | Verdict |
|---|---|
| venv script + `>` redirect oder `| tee` | **FP** (redirect present) |
| venv script ohne redirect | **TP** |
| sonst | **uncertain** |

### Hooks ohne Heuristik
`block_path_typo`, `block_noop_edit`, `block_read_directory`, `block_read_oversize`,
`block_dev_imports_src`, `block_except_pass`, `block_git_add_deps`,
`block_git_destructive`, `block_bd_cli_worker`, `block_worker_spawn_opus`,
`rewrite_git_ambiguous`, `rewrite_bd_invalid_repo`, `rewrite_chained_sleep` —
kein eingebauter FP-Classifier, immer "uncertain" oder nicht abgedeckt im
gelöschten Script.

---

## Wie dieser Katalog konsumiert wird

Beim Bauen eines neuen Hooks oder Refinement eines existierenden:

1. **Lookup im Catalog:** ist die anvisierte Failure-Klasse hier schon dokumentiert?
   Wenn ja → Pattern + Hookability-Bucket als Startpunkt.
2. **Heuristik-Lookup für existierende Hooks:** wenn man am bestehenden Hook
   arbeitet — welche FP/TP-Pattern sind in Audit-Runden festgestellt worden?
   Direkt aus Teil 2 ablesen.
3. **Probe-Hook bauen** wie im `architecture.md` Workflow beschrieben.
4. **Pattern-Update:** wenn eine neue Failure-Klasse während der Hook-Arbeit
   entdeckt wird — manuell hier in den Catalog appendieren. Append-only,
   timestamped Edits.

Catalog ist `decisions/OldThemes/` Material — wird automatisch in
`Monitor_CC-features` RAG-indexed bei `update_docs`.
