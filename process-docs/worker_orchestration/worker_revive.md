# Worker Revive — Implementation (2026-05-20)

## What it is

`worker-cli revive <name>` — brings a dead worker (claude.exe SIGTERM or context-limit death) back with full prior conversation context. Uses CC's session-resume mechanism.

## Trigger

Worker `rag-truncation` died with status 143 (SIGTERM) during Menubar-bug Phase-A investigation. SIGTERM source not deterministically localized — suspected: side effect of Opus chaining `worker-cli kill` + `worker-cli send` together, but `worker-cli kill <other-name>` only does `tmux kill-session` on its own session. Mechanism remained unclear. Without revive capability, Phase-A investigation would have been completely lost.

## Mechanics

CC stores every session in `~/.claude/projects/<encoded-worktree-path>/<session-id>.jsonl`. Resume via:

```bash
cd <worktree> && claude --resume <session-id> --model <model> --dangerously-skip-permissions
```

Important: `--resume` is working-directory-sensitive — the runner must `cd '$WORKTREE'` before the claude call, otherwise CC looks for the JSONL relative to cwd and doesn't find it.

## Revive Flow

`bin/worker-cli` revive case (in the blank repo, ~55 LOC):

1. **Gate**: tmux session exists (`tmux has-session`) — otherwise spawn needed
2. **Gate**: pane dead (`#{pane_dead}` = 1) — otherwise send needed
3. **Gate**: worktree exists (`[ -d $WORKTREE ]`)
4. **Gate**: JSONL exists (newest `*.jsonl` in encoded dir)
5. Rescue worker metadata from `tmux show-environment` (WORKER_MODEL, WORKER_PURPOSE, WORKER_PARENT)
6. Kill old tmux session
7. Create runner script (`/tmp/.worker_<name>_revive.XXX`) with EXIT trap for death logging
8. `tmux new-session` with runner + `set-option remain-on-exit on`
9. Re-set tmux env vars (incl. `WORKER_REVIVED = now`)
10. Re-set pane-died hook for death logging
11. Open tmux viewer

## Pane-Kill Logging

Two orthogonal mechanisms, both write to `~/.claude/worker-deaths.log`:

**1. tmux pane-died hook** (set in worker-cli spawn case + revive case):

```bash
tmux set-hook -t "$SESSION" pane-died \
  "run-shell 'echo \"$(date -Iseconds) worker=$NAME ... status=#{pane_dead_status} signal=#{pane_dead_signal}\" >> $DEATH_LOG'"
```

Fires when the process in the pane dies — `remain-on-exit on` prevents closing but the hook still triggers.

**2. Runner EXIT trap** (in revive-case runner):

```bash
trap '_cleanup' EXIT
_cleanup() {
    local _s=$?
    echo "$(date -Iseconds) worker=$NAME session=$SESSION status=$_s signal=EXIT" >> "$DEATH_LOG"
}
```

Format: `<ISO-timestamp> worker=<name> session=<tmux-session> status=<code> signal=<name>`

## Live Test (2026-05-20)

**Test 1:** `rag-truncation` dead (status 143, JSONL preserved) → `worker-cli revive rag-truncation` → flow completed, pane back alive at 100% context. Worker had the full prior context of the Menubar Phase-A investigation; the mid-thinking state was not in the resume payload (resume comes from the last completed message), Phase A had to be re-triggered by the worker.

**Test 2 (Meta):** User Ctrl-C'd the revive-worker itself → `worker-cli revive revive` brought it back with 100% context.

## Edge Cases

| Case | Reaction |
|---|---|
| tmux session gone | Error "use spawn" |
| Pane still alive | Error "use send" |
| Worktree gone | Error "context unrecoverable" |
| JSONL gone | Error "session-context lost" |
| Branch deleted | Warning, continue if worktree exists |
| JSONL empty (no messages) | claude --resume starts anyway (fresh session) |

## Not Implemented

- **zsh-args parsing of the `/tmp/claude-XXX-cwd` file** for deterministic cwd resolution (would also fix the PID-recycling edge case in bg_timer.py — "more invasive", deferred until actually observed)
- **Automatic revive on detection** — currently the User/Opus must explicitly call `worker-cli revive`. Auto-detect + auto-revive would be conceivable (menubar detects pane-dead, prompts user).

## Sources

- `bin/worker-cli` revive case (blank repo, commit `5c9b50c` on master)
- `~/.claude/worker-deaths.log` (central death log)
