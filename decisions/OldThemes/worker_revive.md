# Worker Revive — Implementation (2026-05-20)

## Was es ist

`worker-cli revive <name>` — bringt einen toten Worker (claude.exe SIGTERM oder context-limit-Tod) zurück mit voller prior conversation context. Nutzt CC's session-resume Mechanismus.

## Trigger

Worker `rag-truncation` starb mit status 143 (SIGTERM) während Menubar-Bug Phase-A Investigation. SIGTERM-Quelle nicht-deterministisch lokalisiert — Verdacht: Side-Effect von Opus chained Bash mit `worker-cli kill + worker-cli send` zusammen, aber `worker-cli kill <other-name>` macht nur `tmux kill-session` auf seine eigene Session. Mechanismus blieb unklar. Without revive Capability hätten wir Phase-A Investigation komplett verloren.

## Mechanik

CC speichert jede Session in `~/.claude/projects/<encoded-worktree-path>/<session-id>.jsonl`. Resume via:

```bash
cd <worktree> && claude --resume <session-id> --model <model> --dangerously-skip-permissions
```

Wichtig: `--resume` ist working-directory-sensitiv — runner muss `cd '$WORKTREE'` vor dem claude-Aufruf machen, sonst sucht CC die JSONL relativ zu cwd und findet sie nicht.

## Revive-Flow

`bin/worker-cli` revive case (im blank repo, ~55 LOC):

1. **Gate**: tmux session existiert (`tmux has-session`) — sonst spawn nötig
2. **Gate**: pane dead (`#{pane_dead}` = 1) — sonst send nötig
3. **Gate**: worktree existiert (`[ -d $WORKTREE ]`)
4. **Gate**: JSONL existiert (newest `*.jsonl` in encoded dir)
5. Worker-Metadata retten aus `tmux show-environment` (WORKER_MODEL, WORKER_PURPOSE, WORKER_PARENT)
6. Kill old tmux session
7. Runner-Script erstellen (`/tmp/.worker_<name>_revive.XXX`) mit EXIT-trap für death-logging
8. `tmux new-session` mit Runner + `set-option remain-on-exit on`
9. Re-set tmux env vars (incl. `WORKER_REVIVED = now`)
10. Re-set pane-died hook for death-logging
11. Open tmux viewer

## Pane-Kill Logging

Zwei orthogonale Mechanismen, beide schreiben in `~/.claude/worker-deaths.log`:

**1. tmux pane-died Hook** (set in worker-cli spawn case + revive case):

```bash
tmux set-hook -t "$SESSION" pane-died \
  "run-shell 'echo \"$(date -Iseconds) worker=$NAME ... status=#{pane_dead_status} signal=#{pane_dead_signal}\" >> $DEATH_LOG'"
```

Feuert wenn der Prozess im Pane stirbt — `remain-on-exit on` verhindert das Schließen aber der Hook löst trotzdem aus.

**2. Runner EXIT-Trap** (in revive case runner):

```bash
trap '_cleanup' EXIT
_cleanup() {
    local _s=$?
    echo "$(date -Iseconds) worker=$NAME session=$SESSION status=$_s signal=EXIT" >> "$DEATH_LOG"
}
```

Format: `<ISO-timestamp> worker=<name> session=<tmux-session> status=<code> signal=<name>`

## Live-Test (2026-05-20)

**Test 1:** `rag-truncation` tot (status 143, JSONL erhalten) → `worker-cli revive rag-truncation` → flow durchgelaufen, pane back alive at 100% context. Worker hatte vollen prior context der Menubar-Phase-A; das mid-thinking war nicht im resume payload (resume kommt at-last-completed-message), Phase A musste vom Worker neu angestoßen werden.

**Test 2 (Meta):** User Ctrl-C'd den revive-worker selbst → `worker-cli revive revive` brachte ihn zurück mit 100% context.

## Edge Cases

| Fall | Reaktion |
|---|---|
| tmux session weg | Fehler "use spawn" |
| Pane lebt noch | Fehler "use send" |
| Worktree weg | Fehler "context unrecoverable" |
| JSONL weg | Fehler "session-context lost" |
| Branch gelöscht | Warnung, fortfahren wenn Worktree existiert |
| JSONL leer (no messages) | claude --resume startet trotzdem (frische Session) |

## Was NICHT implementiert

- **zsh-args-Parsing der `/tmp/claude-XXX-cwd` Datei** für deterministische cwd-Resolution (würde PID-Recycling Edge case in bg_timer.py auch fixen — "more invasive", deferred bis tatsächlich beobachtet)
- **Automatic revive on detection** — derzeit muss User/Opus explizit `worker-cli revive` aufrufen. Auto-detect + auto-revive wäre denkbar (menubar erkennt pane-dead, prompted user).

## Quellen

- `bin/worker-cli` revive case (blank repo, commit `5c9b50c` on master)
- Bead `Monitor_CC-gei1` (closed)
- `~/.claude/worker-deaths.log` (zentrale death log)
