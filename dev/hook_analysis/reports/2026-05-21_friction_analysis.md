# Hook Block Analysis
Generated: 2026-05-21 02:06:21  
Period: 2026-05-14 → today  
Total blocks: 39  

## Summary by Hook

| Hook | Total | Main | Worker |
|---|---|---|---|
| block_chained_sleep | 11 | 4 | 7 |
| block_read_worktree | 10 | 0 | 10 |
| block_dangerous_kill | 9 | 4 | 5 |
| block_broad_grep | 3 | 0 | 3 |
| block_except_pass | 2 | 0 | 2 |
| block_cd_drift | 1 | 1 | 0 |
| block_unauthorized_background | 1 | 1 | 0 |
| block_bd_cli_worker | 1 | 0 | 1 |
| block_path_typo | 1 | 0 | 1 |

## Friction Candidates (≥3 blocks in 30min, same hook+branch)

| Hook | Branch | Project | Count | Window |
|---|---|---|---|---|
| block_read_worktree | bead-tracker | Monitor_CC | 3 | 2026-05-20 22:08–22:08 |
| block_read_worktree | panel-fixes2 | Monitor_CC | 3 | 2026-05-20 23:43–23:43 |
| block_dangerous_kill | safety-hooks | Monitor_CC | 3 | 2026-05-19 23:36–23:37 |
| block_chained_sleep | tracker-fixes | Monitor_CC | 3 | 2026-05-20 22:58–23:03 |

## Top Trigger Patterns by Hook

### block_chained_sleep

| Pattern | Count | Session Types |
|---|---|---|
| `(empty)` | 4 | worker |
| `worker-cli spawn hookable-scan /tmp/spawn-worker-searxng-hookable-sc` | 1 | main |
| `grep -B2 -A8 "block_chained_sleep\|BLOCKED" /tmp/worker-tracker-fixe` | 1 | main |
| `bd show Monitor_CC-mlpb 2>&1 | head -1 && bd show Monitor_CC-hh40 2>` | 1 | main |
| `worker-cli send hook-heredoc "$(cat <<'EOF'` | 1 | main |

### block_read_worktree

| Pattern | Count | Session Types |
|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/pan` | 5 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/bea` | 3 | worker |
| `src/hooks/block_chained_sleep.py` | 1 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tra` | 1 | worker |

### block_dangerous_kill

| Pattern | Count | Session Types |
|---|---|---|
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 3 | worker |
| `(empty)` | 2 | main, worker |
| `echo "trying to run: pkill -f some_pattern" && pkill -f some_pattern` | 1 | main |
| `bd comments add Monitor_CC-q6e5 "Session 2026-05-20: Cursor-edges It` | 1 | main |
| `pkill -f "cursor_edges/probe.py" ; sleep 1 ; cd /Users/brunowinter20` | 1 | main |

### block_broad_grep

| Pattern | Count | Session Types |
|---|---|---|
| `(empty)` | 2 | worker |
| `# Understand the PostToolUse hook payload format` | 1 | worker |

### block_except_pass

| Pattern | Count | Session Types |
|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/bea` | 1 | worker |
| `dev/hook_analysis/analyze_blocks.py` | 1 | worker |

### block_cd_drift

| Pattern | Count | Session Types |
|---|---|---|
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 1 | main |

### block_unauthorized_background

| Pattern | Count | Session Types |
|---|---|---|
| `worker-cli send panel-fixes2 "Go. Plan ist klar. Implement, smoke (M` | 1 | main |

### block_bd_cli_worker

| Pattern | Count | Session Types |
|---|---|---|
| `which bd ; bd --help 2>&1 | head -30` | 1 | worker |

### block_path_typo

| Pattern | Count | Session Types |
|---|---|---|
| `(empty)` | 1 | worker |

## By Project × Hook

| Project | Hook | Total | Main | Worker |
|---|---|---|---|---|
| Monitor_CC | block_chained_sleep | 10 | 3 | 7 |
| Monitor_CC | block_read_worktree | 10 | 0 | 10 |
| Monitor_CC | block_dangerous_kill | 9 | 4 | 5 |
| Monitor_CC | block_broad_grep | 3 | 0 | 3 |
| Monitor_CC | block_except_pass | 2 | 0 | 2 |
| Monitor_CC | block_bd_cli_worker | 1 | 0 | 1 |
| Monitor_CC | block_cd_drift | 1 | 1 | 0 |
| Monitor_CC | block_path_typo | 1 | 0 | 1 |
| Monitor_CC | block_unauthorized_background | 1 | 1 | 0 |
| searxng | block_chained_sleep | 1 | 1 | 0 |

## Timeline

| Date | Hook | Count |
|---|---|---|
| 2026-05-19 | block_dangerous_kill | 4 |
| 2026-05-20 | block_chained_sleep | 11 |
| 2026-05-20 | block_read_worktree | 10 |
| 2026-05-20 | block_dangerous_kill | 5 |
| 2026-05-20 | block_broad_grep | 3 |
| 2026-05-20 | block_except_pass | 2 |
| 2026-05-20 | block_cd_drift | 1 |
| 2026-05-20 | block_unauthorized_background | 1 |
| 2026-05-20 | block_bd_cli_worker | 1 |
| 2026-05-20 | block_path_typo | 1 |

## Events (newest first, max 50)

| Timestamp | Hook | Project | Type | Branch | Trigger | Message |
|---|---|---|---|---|---|---|
| 2026-05-20 23:58 | block_unauthorized_background | Monitor_CC | main | dev | `worker-cli send panel-fixes2 "Go. Plan i` | `run_in_background=true` on a non-canonical command. |
| 2026-05-20 23:51 | block_chained_sleep | Monitor_CC | main | dev | `worker-cli send hook-heredoc "$(cat <<'E` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:48 | block_dangerous_kill | Monitor_CC | worker | panel-fixes2 | `cd /Users/brunowinter2000/Documents/ai/M` | `pkill -f` and `pgrep -f \| kill` chains match arbitrary cmdline substrings and k |
| 2026-05-20 23:48 | block_chained_sleep | Monitor_CC | worker | panel-fixes2 | `cd /Users/brunowinter2000/Documents/ai/M` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:43 | block_read_worktree | Monitor_CC | worker | panel-fixes2 | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:43 | block_read_worktree | Monitor_CC | worker | panel-fixes2 | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:43 | block_read_worktree | Monitor_CC | worker | panel-fixes2 | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:31 | block_dangerous_kill | Monitor_CC | worker | panel-layout | `(empty)` | `pkill -f` and `pgrep -f \| kill` chains match arbitrary cmdline substrings and k |
| 2026-05-20 23:31 | block_broad_grep | Monitor_CC | worker | panel-layout | `(empty)` | recursive grep without --include scope (Rule 3, tool-use.md). |
| 2026-05-20 23:30 | block_chained_sleep | Monitor_CC | worker | panel-layout | `(empty)` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:30 | block_path_typo | Monitor_CC | worker | panel-layout | `(empty)` | path contains `.claire/` — tokenizer typo of `.claude/`. |
| 2026-05-20 23:21 | block_except_pass | Monitor_CC | worker | hook-heredoc | `dev/hook_analysis/analyze_blocks.py` | silent exception swallow (`except ...: pass`) detected in written code. |
| 2026-05-20 23:18 | block_chained_sleep | Monitor_CC | worker | hook-heredoc | `python3 - <<'PYEOF'` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:17 | block_read_worktree | Monitor_CC | worker | panel-layout | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:17 | block_read_worktree | Monitor_CC | worker | panel-layout | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:12 | block_chained_sleep | Monitor_CC | worker | hook-heredoc | `grep -m 1 "block_chained_sleep" ~/.claud` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:10 | block_chained_sleep | Monitor_CC | main | dev | `bd show Monitor_CC-mlpb 2>&1 \| head -1 &` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:07 | block_read_worktree | Monitor_CC | worker | hook-heredoc | `src/hooks/block_chained_sleep.py` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 23:03 | block_broad_grep | Monitor_CC | worker | tracker-fixes | `(empty)` | recursive grep without --include scope (Rule 3, tool-use.md). |
| 2026-05-20 23:03 | block_chained_sleep | Monitor_CC | worker | tracker-fixes | `(empty)` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 23:03 | block_chained_sleep | Monitor_CC | main | dev | `grep -B2 -A8 "block_chained_sleep\\|BLOCK` | `sleep` detected in a Bash command that is not the canonical orchestration |
| 2026-05-20 23:00 | block_chained_sleep | Monitor_CC | worker | tracker-fixes | `(empty)` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 22:58 | block_chained_sleep | Monitor_CC | worker | tracker-fixes | `(empty)` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 22:45 | block_read_worktree | Monitor_CC | worker | tracker-fixes | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 22:36 | block_cd_drift | Monitor_CC | main | dev | `cd /Users/brunowinter2000/Documents/ai/M` | `cd` into `.claude/worktrees/...` without a cd-back at the end of the chain. |
| 2026-05-20 22:29 | block_except_pass | Monitor_CC | worker | bead-tracker | `/Users/brunowinter2000/Documents/ai/Moni` | silent exception swallow (`except ...: pass`) detected in written code. |
| 2026-05-20 22:10 | block_broad_grep | Monitor_CC | worker | bead-tracker | `# Understand the PostToolUse hook payloa` | recursive grep without --include scope (Rule 3, tool-use.md). |
| 2026-05-20 22:09 | block_bd_cli_worker | Monitor_CC | worker | bead-tracker | `which bd ; bd --help 2>&1 \| head -30` | `bd` CLI command from inside a worker session. |
| 2026-05-20 22:08 | block_read_worktree | Monitor_CC | worker | bead-tracker | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 22:08 | block_read_worktree | Monitor_CC | worker | bead-tracker | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 22:08 | block_read_worktree | Monitor_CC | worker | bead-tracker | `/Users/brunowinter2000/Documents/ai/Moni` | Read on a worktree path silently re-injects CLAUDE.md into context. |
| 2026-05-20 21:21 | block_chained_sleep | searxng | main | dev | `worker-cli spawn hookable-scan /tmp/spaw` | `sleep` detected in a Bash command that is not the canonical orchestration timer |
| 2026-05-20 00:28 | block_dangerous_kill | Monitor_CC | main | main | `pkill -f "cursor_edges/probe.py" ; sleep` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-20 00:11 | block_dangerous_kill | Monitor_CC | main | main | `(empty)` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-20 00:07 | block_dangerous_kill | Monitor_CC | main | dev | `bd comments add Monitor_CC-q6e5 "Session` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-19 23:40 | block_dangerous_kill | Monitor_CC | main | dev | `echo "trying to run: pkill -f some_patte` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-19 23:37 | block_dangerous_kill | Monitor_CC | worker | safety-hooks | `cd /Users/brunowinter2000/Documents/ai/M` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-19 23:36 | block_dangerous_kill | Monitor_CC | worker | safety-hooks | `cd /Users/brunowinter2000/Documents/ai/M` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
| 2026-05-19 23:36 | block_dangerous_kill | Monitor_CC | worker | safety-hooks | `cd /Users/brunowinter2000/Documents/ai/M` | `pkill -f <pattern>` matches arbitrary cmdline substrings and frequently kills t |
