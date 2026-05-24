# Sleep Pattern Audit — block_chained_sleep
Generated: 2026-05-24 20:31  
Period analysed: 2020-01-01 → today  
Actual date range in data: 2026-05-20 – 2026-05-24  
Total blocked events: 50  
Total sleep occurrences parsed: 54 (8 inside heredoc bodies — hook FP, excluded from histograms)  
Shell-level sleep occurrences (used for histograms): 46  

## cmd_before Histogram (top 25)

| Rank | Token | Count | % | Example commands |
|---|---|---|---|---|
| 1 | `echo` | 12 | 26.1% | `git -C /Users/brunowinter2000/Documents/ai/Monitor_CC push 2>&1 \| tail -3 echo "=== restart menubar with new code ===" P` / `# Wait for indexer to release lock — poll every 20s for i in $(seq 1 30); do   STATUS=$(rag-cli status 2>/dev/null)   if` / `worker-cli send phase-c "$(cat <<'EOF' Go — with two clarifications:  ## Task A: implement as proposed  The diff looks c` |
| 2 | `(empty)` | 5 | 10.9% | `sleep 15 && rag-cli server list 2>&1 \| head -20` / `sleep 6 && bd comments add Monitor_CC-22wq "Source-Inventory updated: + decisions/OldThemes/tool_use_safety/2026-05-22_h` / `sleep 3 && cat /tmp/menubar_worktree_smoke.log 2>/dev/null \| head -30; echo "---"; ps aux \| grep "workflow.py --mode men` |
| 3 | `launchctl` | 5 | 10.9% | `git status --short && worker-cli merge queue-redesign && echo "---restart---" && launchctl kickstart -k gui/$(id -u)/com` / `launchctl bootout gui/$(id -u)/com.brunowinter.monitor_cc_menubar 2>&1; sleep 1; pgrep -f "workflow.py --mode menubar" \|` / `launchctl bootout gui/$(id -u)/com.brunowinter.monitor_cc_menubar 2>&1 \| tail -3 ; launchctl bootstrap gui/$(id -u) ~/Li` |
| 4 | `kill` | 4 | 8.7% | `worker-cli kill grid-migration && echo "---" && PROD_PID=$(pgrep -f "workflow.py --mode menubar" \| head -1) && echo "old` / `git status --short && echo "---merge---" && worker-cli merge queue-redesign && echo "---killing worktree menubars---" &&` / `kill 60586 2>&1 sleep 2 rag-cli status 2>&1 \| head -3 echo "" echo "=== Re-run update_docs (foreground, with explicit ti` |
| 5 | `true` | 2 | 4.3% | `echo "=== Dolt server retry ===" bd dolt start 2>&1 \| tail -5 \|\| true sleep 2 bd --repo /Users/brunowinter2000/Documents` / `launchctl bootout gui/$(id -u)/com.brunowinter.monitor_cc_menubar 2>&1 \|\| true; sleep 1; echo "prod killed"` |
| 6 | `rag-cli` | 2 | 4.3% | `rag-cli server restart embedding-0.6b 2>&1 \| tail -5; sleep 3; echo "---status---"; rag-cli server status 2>&1; echo "--` / `rag-cli server restart reranker-0.6b 2>&1; sleep 8; rag-cli server status 2>&1 \| head -20` |
| 7 | `bd` | 2 | 4.3% | `bd dolt start 2>&1 \| tail -5; sleep 2; bd list -s open 2>&1 \| head -80` / `bd label list Monitor_CC-0ehl --json 2>&1; echo "--- pre kuo4 ---"; bd label list Monitor_CC-kuo4 --json 2>&1; echo "---` |
| 8 | `#` | 2 | 4.3% | `pgrep -fl "dolt sql-server" 2>&1 \| head -5 echo "---" ls -la /tmp/.dolt-* 2>&1 \| head -5 echo "---" # Try one more time ` / `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/ccwrap-phase1 python3 -m src.ccwrap --project /tmp 2` |
| 9 | `pkill` | 2 | 4.3% | `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/panel-fixes2 pkill -f "workflow.py --mode menubar" 2` / `pkill -f "menubar_app.py" 2>/dev/null; sleep 1; pgrep -fl "menubar_app" \|\| echo "prod stopped"` |
| 10 | `tmux` | 2 | 4.3% | `# Check Python environment in worktree ls /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/status-probe/` |
| 11 | `cmd` | 2 | 4.3% | `WT=/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tracker-fixes  cat > $WT/src/menubar/app.py << 'PYEO` |
| 12 | `delay` | 2 | 4.3% | `WT=/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tracker-fixes  python3 - << 'PYEOF' import sys conte` |
| 13 | `cd` | 1 | 2.2% | `cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claude/worktrees/refactor-cli-server sleep 3 ./venv/bin/` |
| 14 | `Bash` | 1 | 2.2% | `worker-cli spawn hookable-scan /tmp/spawn-worker-searxng-hookable-scan.md /Users/brunowinter2000/Documents/ai/Meta/Claud` |
| 15 | `dolt` | 1 | 2.2% | `echo "=== bd config / port info ===" find /Users/brunowinter2000/Documents/ai/Monitor_CC/.beads -type f 2>&1 \| head -10 ` |
| 16 | `worker-cli` | 1 | 2.2% | `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/phase-c ; worker-cli kill nonexistent 2>/dev/null ; ` |

## cmd_after Histogram (top 15)

| Rank | Token | Count | % |
|---|---|---|---|
| 1 | `echo` | 10 | 21.7% |
| 2 | `bd` | 6 | 13.0% |
| 3 | `pgrep` | 4 | 8.7% |
| 4 | `tail` | 4 | 8.7% |
| 5 | `rag-cli` | 3 | 6.5% |
| 6 | `done` | 3 | 6.5% |
| 7 | `cat` | 3 | 6.5% |
| 8 | `python3` | 2 | 4.3% |
| 9 | `launchctl` | 2 | 4.3% |
| 10 | `'` | 2 | 4.3% |
| 11 | `python` | 1 | 2.2% |
| 12 | `tmux` | 1 | 2.2% |
| 13 | `ls` | 1 | 2.2% |
| 14 | `#` | 1 | 2.2% |
| 15 | `ps` | 1 | 2.2% |

## In-loop vs Naked vs Canonical

- In-loop (`while`/`for`/`until` body): **4** (8.7%)
- Canonical (`sleep N && echo done` standalone): **0** (0.0%)
- Naked (neither): **42**

## Sleep Duration Distribution

| Bucket | Count | % | Example |
|---|---|---|---|
| 1s | 17 | 37.0% | `git status --short && echo "---merge---" && worker-cli merge queue-redesign && e` |
| 2–5s | 21 | 45.7% | `git -C /Users/brunowinter2000/Documents/ai/Monitor_CC push 2>&1 \| tail -3 echo "` |
| 6–15s | 5 | 10.9% | `sleep 15 && rag-cli server list 2>&1 \| head -20` |
| 16–60s | 1 | 2.2% | `# Wait for indexer to release lock — poll every 20s for i in $(seq 1 30); do   S` |
| 60s+ | 2 | 4.3% | `worker-cli spawn hookable-scan /tmp/spawn-worker-searxng-hookable-scan.md /Users` |

## Classification

### Candidate trivial-sync tokens (safe to strip)

Each token below returns synchronously on completion: no background process is spawned and no externally-visible state needs settling time before the next command can safely proceed. A rewrite hook can strip `sleep N` following these tokens without risk.

- **`echo`** (12) — prints to stdout and returns; no process spawned, no state mutation. Example: `git -C /Users/brunowinter2000/Documents/ai/Monitor_CC push 2>&1 \| tail -3 echo "=== restart menubar with new code ===" P`
- **`true`** (2) — exits 0 immediately; appears as `|| true; sleep N` — the `true` is a swallowed-error guard, not async work. Example: `echo "=== Dolt server retry ===" bd dolt start 2>&1 \| tail -5 \|\| true sleep 2 bd --repo /Users/brunowinter2000/Documents`

### Clearly load-bearing tokens

Sleep after these tokens is doing real work. Do not strip.

- **`launchctl`** (5) — kickstart/bootout are async — the service reaches 'running' state asynchronously; pgrep checks after sleep verify the daemon is up. Example: `git status --short && worker-cli merge queue-redesign && echo "---restart---" && launchctl kickstart -k gui/$(id -u)/com`
- **`kill`** (4) — sends signal to process; OS scheduler needs time to deliver SIGKILL and reap the child — polling immediately after kill will see the process still alive. Example: `worker-cli kill grid-migration && echo "---" && PROD_PID=$(pgrep -f "workflow.py --mode menubar" \| head -1) && echo "old`
- **`pkill`** (2) — same as kill; pattern-based, may target multiple processes. Example: `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/panel-fixes2 pkill -f "workflow.py --mode menubar" 2`
- **`tmux`** (2) — some tmux commands mutate session state asynchronously (pipe-pane, new-session, send-keys); sleep ensures the operation has propagated. Example: `# Check Python environment in worktree ls /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/status-probe/`

### Mixed tokens (require per-subcommand inspection)

- **`rag-cli`** (2) — MIXED — `rag-cli server restart/start` is async (server spawn); read-only subcommands (search, list) are sync. Example: `rag-cli server restart embedding-0.6b 2>&1 \| tail -5; sleep 3; echo "---status---"; rag-cli server status 2>&1; echo "--`
- **`bd`** (2) — MIXED — `bd dolt start` spawns the Dolt server (async); label/comment/list ops are sync. Example: `bd dolt start 2>&1 \| tail -5; sleep 2; bd list -s open 2>&1 \| head -80`
- **`worker-cli`** (1) — MIXED — `worker-cli kill/spawn` are async; status/list are sync. Example: `cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/phase-c ; worker-cli kill nonexistent 2>/dev/null ; `

### Unclassifiable tail

| Token | Count | Example |
|---|---|---|
| `(empty)` | 5 | `sleep 15 && rag-cli server list 2>&1 \| head -20` |
| `#` | 2 | `pgrep -fl "dolt sql-server" 2>&1 \| head -5 echo "---" ls -la /tmp/.dolt-* 2>&1 \|` |
| `cmd` | 2 | `WT=/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tracker-fixe` |
| `delay` | 2 | `WT=/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tracker-fixe` |
| `cd` | 1 | `cd /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claude/worktrees` |
| `Bash` | 1 | `worker-cli spawn hookable-scan /tmp/spawn-worker-searxng-hookable-scan.md /Users` |
| `dolt` | 1 | `echo "=== bd config / port info ===" find /Users/brunowinter2000/Documents/ai/Mo` |
