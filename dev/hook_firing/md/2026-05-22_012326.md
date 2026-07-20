# Hook Block Analysis
Generated: 2026-05-22 01:23:26  
Period: 2026-05-15 → today  
Total blocks: 87  

## Summary by Hook

| Hook | Total | Main | Worker | TP | FP | Uncertain | FP rate |
|---|---|---|---|---|---|---|---|
| block_chained_sleep | 29 | 10 | 19 | 4 | 13 | 12 | 45% |
| block_dangerous_kill | 16 | 7 | 9 | 15 | 0 | 1 | 0% |
| block_read_worktree | 11 | 1 | 10 | 1 | 0 | 10 | 0% |
| block_broad_grep | 7 | 2 | 5 | 7 | 0 | 0 | 0% |
| block_path_typo | 7 | 0 | 7 | 0 | 0 | 7 | 0% |
| block_except_pass | 5 | 0 | 5 | 0 | 0 | 5 | 0% |
| block_dev_imports_src | 3 | 0 | 3 | 0 | 0 | 3 | 0% |
| block_unauthorized_background | 2 | 1 | 1 | 1 | 1 | 0 | 50% |
| block_cd_drift | 2 | 2 | 0 | 2 | 0 | 0 | 0% |
| block_venv_no_redirect | 2 | 1 | 1 | 1 | 0 | 1 | 0% |
| block_bd_cli_worker | 2 | 0 | 2 | 0 | 0 | 2 | 0% |
| block_read_oversize | 1 | 1 | 0 | 0 | 0 | 1 | 0% |

## Friction Candidates (≥3 blocks in 30min, same hook+branch)

| Hook | Branch | Project | Count | Window |
|---|---|---|---|---|
| block_read_worktree | bead-tracker | Monitor_CC | 3 | 2026-05-20 22:08–22:08 |
| block_read_worktree | panel-fixes2 | Monitor_CC | 3 | 2026-05-20 23:43–23:43 |
| block_dangerous_kill | safety-hooks | Monitor_CC | 3 | 2026-05-19 23:36–23:37 |
| block_chained_sleep | tracker-fixes | Monitor_CC | 3 | 2026-05-20 22:58–23:03 |

## Top Trigger Patterns by Hook

### block_chained_sleep

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `(empty)` | 4 | 0 | 3 | worker |
| `launchctl bootout gui/$(id -u)/com.brunowinter.monitor_cc_menubar` | 3 | 3 | 0 | main, worker |
| `rag-cli server restart embedding-0.6b 2>&1 | tail -5; sleep 3; ec` | 1 | 0 | 0 | main |
| `worker-cli spawn hookable-scan /tmp/spawn-worker-searxng-hookable` | 1 | 0 | 1 | main |
| `worker-cli kill grid-migration && echo "---" && PROD_PID=$(pgrep ` | 1 | 1 | 0 | main |

### block_dangerous_kill

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktre` | 3 | 0 | 3 | worker |
| `(empty)` | 2 | 0 | 2 | main, worker |
| `kill $(pgrep -f "sleep 480") 2>/dev/null; ls -la /Users/brunowint` | 1 | 0 | 0 | main |
| `pgrep -f "workflow.py --mode menubar" | xargs -I {} echo "killing` | 1 | 0 | 1 | main |
| `worker-cli kill queue-redesign 2>&1; pkill -f "monitor_cc_menubar` | 1 | 0 | 1 | main |

### block_read_worktree

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 5 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 3 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 1 | 0 | 1 | main |
| `src/hooks/block_chained_sleep.py` | 1 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 1 | 0 | 0 | worker |

### block_broad_grep

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `(empty)` | 2 | 0 | 2 | worker |
| `echo "=== Pipeline-Smoke (Full-Stack Prod-Config Test) ==="; ls -` | 1 | 0 | 1 | main |
| `grep -rn "idle\|working\|ALIVE_WINDOW\|WORKING_THRESHOLD\|10s\|tm` | 1 | 0 | 1 | main |
| `# Understand the PostToolUse hook payload format` | 1 | 0 | 1 | worker |
| `grep -rn "System Events" /Users/brunowinter2000/Documents/ai/Moni` | 1 | 0 | 1 | worker |

### block_path_typo

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/` | 2 | 0 | 0 | worker |
| `cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxn` | 1 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng/.` | 1 | 0 | 0 | worker |
| `wc -l /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/sea` | 1 | 0 | 0 | worker |
| `(empty)` | 1 | 0 | 0 | worker |

### block_except_pass

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 2 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 1 | 0 | 0 | worker |
| `dev/hook_analysis/analyze_blocks.py` | 1 | 0 | 0 | worker |
| `/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/` | 1 | 0 | 0 | worker |

### block_dev_imports_src

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxng/.` | 2 | 0 | 0 | worker |
| `dev/search_pipeline/cdp_starvation_probe.py` | 1 | 0 | 0 | worker |

### block_unauthorized_background

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/searxn` | 1 | 0 | 1 | worker |
| `worker-cli send panel-fixes2 "Go. Plan ist klar. Implement, smoke` | 1 | 1 | 0 | main |

### block_cd_drift

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktre` | 1 | 0 | 1 | main |
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktre` | 1 | 0 | 1 | main |

### block_venv_no_redirect

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `tail -100 /tmp/worker-msg-queue-pane.txt | sed -E '/^[│▁─]+$/d; /` | 1 | 0 | 0 | main |
| `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktre` | 1 | 0 | 1 | worker |

### block_bd_cli_worker

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `bd --db ~/.beads/dolt show Monitor_CC-hh40 --json | python3 -c "i` | 1 | 0 | 0 | worker |
| `which bd ; bd --help 2>&1 | head -30` | 1 | 0 | 0 | worker |

### block_read_oversize

| Pattern | Count | FP | TP | Session Types |
|---|---|---|---|---|
| `/Users/brunowinter2000/Documents/wise2627/master/Augsburg/Data_sc` | 1 | 0 | 0 | main |


## Events (newest first, max 40)

| Timestamp | Hook | Project | Type | Branch | Trigger | FP? | Heuristic |
|---|---|---|---|---|---|---|---|
| 2026-05-21 21:33 | block_broad_grep | Monitor_CC | worker | ghostty-native | `grep -rn "System Events" /Users/bru` | tp | recursive grep without --include= scope |
| 2026-05-21 21:32 | block_dangerous_kill | Monitor_CC | main | dev | `worker-cli kill queue-redesign 2>&1` | tp | pkill -f in active command |
| 2026-05-21 21:25 | block_chained_sleep | Monitor_CC | main | dev | `launchctl bootout gui/$(id -u)/com.` | fp | sleep N=1.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 21:09 | block_chained_sleep | Monitor_CC | main | dev | `git status --short && worker-cli me` | fp | sleep N=2.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 20:47 | block_except_pass | Monitor_CC | worker | queue-redesign | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 20:35 | block_chained_sleep | Monitor_CC | main | dev | `git status --short && echo "---merg` | uncertain | sleep N=1.0 ≤ 10, context ambiguous |
| 2026-05-21 20:34 | block_dangerous_kill | Monitor_CC | main | dev | `pgrep -f "workflow.py --mode menuba` | tp | pkill -f in active command |
| 2026-05-21 20:28 | block_path_typo | searxng | worker | muell-eval | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 20:03 | block_path_typo | searxng | worker | pooling-eval | `wc -l /Users/brunowinter2000/Docume` | uncertain | no heuristic for this hook |
| 2026-05-21 20:00 | block_chained_sleep | Monitor_CC | worker | queue-redesign | `sleep 3 && cat /tmp/worktree-smoke.` | uncertain | sleep N=3.0 ≤ 10, context ambiguous |
| 2026-05-21 19:51 | block_dev_imports_src | searxng | worker | pooling-eval | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 19:47 | block_chained_sleep | searxng | main | dev | `rag-cli server restart embedding-0.` | uncertain | sleep N=3.0 ≤ 10, context ambiguous |
| 2026-05-21 19:32 | block_dangerous_kill | Monitor_CC | worker | queue-reentry | `pkill -f "menubar_app.py" 2>/dev/nu` | tp | pkill -f in active command |
| 2026-05-21 19:32 | block_chained_sleep | Monitor_CC | worker | queue-reentry | `pkill -f "menubar_app.py" 2>/dev/nu` | fp | sleep N=1.0 ≤ 5 after side-effect ('pkill'):  |
| 2026-05-21 18:59 | block_path_typo | Monitor_CC | worker | queue-features | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 18:00 | block_unauthorized_background | searxng | worker | engine-uniformity | `cd /Users/brunowinter2000/Documents` | tp | non-canonical command with run_in_background= |
| 2026-05-21 17:57 | block_path_typo | Monitor_CC | worker | queue-features | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 17:56 | block_except_pass | Monitor_CC | worker | queue-features | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 17:51 | block_dangerous_kill | Monitor_CC | worker | queue-features | `pkill -f "workflow.py --mode menuba` | tp | pkill -f in active command |
| 2026-05-21 17:51 | block_chained_sleep | Monitor_CC | worker | queue-features | `launchctl bootout gui/$(id -u) com.` | fp | sleep N=2.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 17:27 | block_chained_sleep | Monitor_CC | worker | bead-features | `launchctl bootout gui/$(id -u) /Lib` | fp | sleep N=1.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 17:27 | block_dangerous_kill | Monitor_CC | worker | bead-features | `launchctl bootout gui/$(id -u) /Lib` | tp | pkill -f in active command |
| 2026-05-21 17:19 | block_bd_cli_worker | Monitor_CC | worker | bead-features | `bd --db ~/.beads/dolt show Monitor_` | uncertain | no heuristic for this hook |
| 2026-05-21 16:53 | block_chained_sleep | Monitor_CC | worker | grid-fix | `sleep 3 && cat /tmp/menubar_worktre` | uncertain | sleep N=3.0 ≤ 10, context ambiguous |
| 2026-05-21 16:52 | block_chained_sleep | Monitor_CC | worker | grid-fix | `launchctl bootout gui/$(id -u)/com.` | fp | sleep N=1.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 16:43 | block_path_typo | searxng | worker | acquire-probe | `cd /Users/brunowinter2000/Documents` | uncertain | no heuristic for this hook |
| 2026-05-21 16:30 | block_chained_sleep | Monitor_CC | main | dev | `worker-cli kill grid-migration && e` | fp | sleep N=2.0 ≤ 5 after side-effect ('worker-cl |
| 2026-05-21 16:29 | block_cd_drift | Monitor_CC | main | dev | `cd /Users/brunowinter2000/Documents` | tp | cd into worktree without cd-back |
| 2026-05-21 16:24 | block_dev_imports_src | searxng | worker | acquire-probe | `/Users/brunowinter2000/Documents/ai` | uncertain | no heuristic for this hook |
| 2026-05-21 16:23 | block_dangerous_kill | Monitor_CC | worker | grid-migration | `pkill -f 'workflow.py --mode menuba` | tp | pkill -f in active command |
| 2026-05-21 16:04 | block_chained_sleep | Monitor_CC | worker | grid-migration | `./venv/bin/python3 dev/grid_probe/p` | fp | sleep N=3.0 ≤ 5 after side-effect ('kill -0') |
| 2026-05-21 15:57 | block_read_oversize | wise2627 | main | master | `/Users/brunowinter2000/Documents/wi` | uncertain | no heuristic for this hook |
| 2026-05-21 15:44 | block_dev_imports_src | searxng | worker | prod-smoke | `dev/search_pipeline/cdp_starvation_` | uncertain | no heuristic for this hook |
| 2026-05-21 15:42 | block_broad_grep | Monitor_CC | worker | menubar-timer | `cd /Users/brunowinter2000/Documents` | tp | recursive grep without --include= scope |
| 2026-05-21 15:35 | block_chained_sleep | Monitor_CC | worker | menubar-timer | `launchctl bootout gui/$(id -u)/com.` | fp | sleep N=1.0 ≤ 5 after side-effect ('launchctl |
| 2026-05-21 15:17 | block_broad_grep | Monitor_CC | main | dev | `grep -rn "idle\\|working\\|ALIVE_WIND` | tp | recursive grep without --include= scope |
| 2026-05-21 15:02 | block_dangerous_kill | searxng | main | dev | `kill $(pgrep -f "sleep 480") 2>/dev` | uncertain | pkill pattern not visible in trigger |
| 2026-05-21 14:43 | block_chained_sleep | Monitor_CC | worker | menubar-timer | `sleep 3; tail -20 /tmp/menubar_smok` | uncertain | sleep N=3.0 ≤ 10, context ambiguous |
| 2026-05-21 14:42 | block_broad_grep | searxng | main | dev | `echo "=== Pipeline-Smoke (Full-Stac` | tp | recursive grep without --include= scope |
| 2026-05-21 01:35 | block_chained_sleep | Monitor_CC | worker | queue-panel | `cd /Users/brunowinter2000/Documents` | uncertain | sleep N=4.0 ≤ 10, context ambiguous |
