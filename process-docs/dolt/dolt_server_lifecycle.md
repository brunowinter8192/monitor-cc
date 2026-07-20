# Dolt Server Lifecycle — bd↔dolt Restart War (2026-05-29)

## RESOLVED 2026-05-30 — bd v0.60.0 → v1.0.4 upgrade, loop dead, zero data loss

**Fix:** bd upgraded (Option A) — the restart loop is fixed. v1.0.4 keeps the auto-started dolt server alive (the PR #2655 class of fix) instead of churning it per command. So it was the #2655/#2675 mechanism, not a v0.60-specific variant — the open gate from the "correction" section below is resolved.

### Install — controlled single version (no auto-update)
- Binary `beads_1.0.4_darwin_arm64.tar.gz` (checksum-verified against `checksums.txt`, `0c53479…`) placed at `~/.local/bin/bd` (PATH position 1, ahead of `/opt/homebrew/bin`). `bd version` → 1.0.4 (ce242a879).
- `brew uninstall bd` (old tap formula `steveyegge/beads`, v0.60.0 removed, symlink gone). **`brew pin dolt`** (dolt 1.83.5 frozen — bd needs it as a subprocess).
- No package manager anymore, no self-update: `bd upgrade` is only a local version-change DETECTOR (`cmd/bd/upgrade.go`, no network/download — only writes `metadata.json` + compares). The npm package `@beads/bd` deliberately NOT used (it publishes the locked 1.0.5 + a Node shim layer). Homebrew: no `autoupdate` tap, no launchd jobs → binaries never upgrade themselves.
- **Locked out:** v1.0.5 (prerelease) contains migration `0043`, which destroys multi-machine `bd dolt` sync "silently and unrecoverably" (upstream issue #4259) — Homebrew rolled back to v1.0.4. Irrelevant to us: no dolt remotes (`bd dolt remote list` = none) + v1.0.4 ≠ v1.0.5.

### Migration — in-place on the server store, no data loss
- v1.0.4 RESPECTS `metadata.json: dolt_mode=server` → migrates in-place onto `.beads/dolt/` (server mode stays, NO switch to `.beads/embeddeddolt/`). Schema stamp 0.60.0 → 1.0.4 via `bd migrate --yes`.
- **Data-loss risk ruled out via a throwaway sandbox:** a copy of Monitor_CC's `.beads` was migrated → the most recent issue (05-29, not yet flushed into the week-old `issues.jsonl`) survived, issue count 248 preserved. Proof that migration operates on the real DB data, not on the stale JSONL. The `auto_import_upgrade` JSONL recovery is emptiness-guarded + insert-if-new (`importFromLocalJSONLConflictSkip`, upstream GH#3955) → a harmless no-op on a non-empty DB, cannot overwrite live data.
- **7 project DBs migrated** (all to 1.0.4, counts preserved): Monitor_CC 248, Trading 15, blank 38, searxng 83, RAG 88, github 32, Reddit 35. `bd migrate` flushes the JSONL back to current as a side effect.
- **arxiv + linkedin** deliberately excluded, migration failed (no data loss): arxiv's `.beads/dolt/` contains only `config.yaml` (no real DB); linkedin is on a fixed port 3307 / shared server (offline). The menubar logs harmless open-errors for these. Not pursued further.

### Verification — loop dead
- 3× `bd list` in a row (= the menubar polling command) → identical port 61785, identical server PID 72690, 1 server, 20s stable, **0 circuit breakers**. On the old v0.60, the same polling would have restarted the server every ~8s.
- The menubar was cleanly taken out via `launchctl bootout` for the migration window, then `launchctl bootstrap` back in — 1 healthy instance (`state = running`).

### Backup (safety net, can be removed after stability is confirmed)
`~/beads-upgrade-backup-20260530-213148/` (86 MB): raw `.beads/dolt` dirs of all 9 projects + the old v0.60.0 binary + JSONL.

---

## CORRECTION 2026-05-30 — Homebrew was a red herring, root cause NOT fixed

The conclusion documented below (Homebrew dolt service = cause, `brew services stop dolt` = fix) is **wrong**. Evidence: the 53351 loop came back (20,715 restarts, +744 after the "fix", 8s cadence) — **without** the Homebrew service being back (`launchctl` confirms it was not loaded). The loop only paused around 2026-05-29 ~22:55 due to launchd's respawn throttle (a timing coincidence, 5 min before `brew services stop`); the lockstep timestamps were NOT proof of coupling. `brew services stop dolt` remains sensible (removes a redundant service), but is NOT the fix.

### Real Root Cause (finding 2026-05-30)
An internal bd server-lifecycle instability, **cross-project** (Monitor_CC, searxng, … each with its own ephemeral port — proxy log `src/logs/tool_errors.jsonl` shows circuit breakers on 56857/59469/53351):
- **Per-command auto-start/auto-stop** (refcounted): bd commands open/close a DoltStore and spin the server up/down. Driver: the **menubar polls bd continuously per project** (`bd list -l tracked --json --db <proj>`) — every poll is a start/stop cycle.
- **Circuit breaker** (`internal/storage/dolt/circuit.go`): 5 errors/60s → OPEN; state lives in `/tmp/beads-dolt-circuit-<port>.json`, **survives bd calls + reboots**.
- **`IsRunning` checks the PID file, not TCP** (beads issue #2341): reports "not running" even though a process is alive (a stale PID/port file from the constant restarts) → triggers KillStaleServers + restart → loop. Reproduced live: `bd dolt status` = "not running" while a live process sits on 53351.
- Local bd version: **0.60.0** (91df6ef6).

### Fix Options
- **A (chosen, deferred to next session): upgrade bd.** Fixed upstream: #2636 (v0.61.0 regression, infinite restart loop) via PR #2675 (doctor shares ONE store instead of per-check) + #2655 ("keep repo-local auto-started servers alive"). **Uncertain:** #2636 is a v0.61.0 regression, we are on v0.60.0 (before that) — unclear whether our loop is exactly the #2636 mechanism or a v0.60.0 variant. **Before upgrading:** check the bd changelog/releases from v0.60.0 to current for what else the upgrade would pull in (rough history: v0.49→v0.58 removed SQLite).
- **B: disable auto-start + a persistent server per project** (`dolt.auto-start: false` / `BEADS_DOLT_AUTO_START=0`). No per-command churn; bd connects to the standing server. No bd upgrade needed; the server must be kept reliably up.
- **C: throttle menubar polling** (our own code, the trigger). Reduces frequency, doesn't fix the root cause.

### Next Session — CLARIFY before upgrading (otherwise the upgrade is blind)
Two verification steps before executing Option A (upgrade):
1. **Pin down the actual 8s trigger.** Does the restart loop keep going when NO bd calls come in? Test: pause the menubar's bd polling briefly (or watch `dolt-server.log` restart timing with zero bd calls). Loop stops → per-command lifecycle (= the #2636 mechanism, the upgrade hits the cause). Loop keeps going → a different driver (bd daemon / health checker / menubar side), the upgrade might NOT hit it. **Open contradiction:** 5 rapid `bd list` calls produced 0 additional restarts — suggesting that a bd read does NOT stop the server on v0.60.0 (so possibly NOT the #2636 mechanism).
2. **Read the bd changelog/releases from v0.60.0 to current.** What actually sits between our version and the #2636/#2655 fix; which breaking changes (rough history: v0.49→v0.58 removed SQLite).

**Gate:** only upgrade if the trigger pinned down under (1) matches what the upgrade fixes — otherwise it's a blind upgrade.

### Recovery (temporary)
Delete the breaker files `/tmp/beads-dolt-circuit-*.json` + kill dolt processes + remove stale LOCK/pid/port files + clean restart. Doesn't hold as long as the trigger (polling) + lifecycle churn persist.

### Sources (correction)
beads issues #2636 (loop), #2341 (circuit-breaker recovery guide), #2598 (breaker before auto-start); PRs #2675 (merged), #2655. Proxy log `src/logs/tool_errors.jsonl` (cross-project breaker errors). `IsRunning`/`Start` in `internal/doltserver/doltserver.go`.

---

*Everything below this point is HISTORICAL / SUPERSEDED — kept as the iteration record (the two-server observation was real, but NOT the root cause).*

## State as of 2026-05-29 — SUPERSEDED (see the correction above)
- One dolt sql-server per project, lazily started by bd, its own ephemeral port (recorded in `.beads/dolt-server.port`). Live at the time: Monitor_CC 53351, Meta/blank 63303, Trading 65511 — distinct, no collision.
- Ports are dynamic/ephemeral: NO port config in `.beads/config.yaml` or `metadata.json`. bd allocates via an OS ephemeral port, records it in the port file; clients (menubar/Opus/worker) find the port via the port file.
- The Homebrew launchd dolt service `homebrew.mxcl.dolt` was permanently removed via `brew services stop dolt` (it was `RunAtLoad`+`KeepAlive`, `dolt sql-server` on `localhost:3306` + `/tmp/mysql.sock`).
- bd server stable at the time: restart counter frozen at 19,971, >16 min without a restart after removing the Homebrew competitor (previously 1 restart / ~8s).

## Symptom (Starting Point)
bd operations periodically failed with "circuit breaker open." Working assumption: "dolt sql-server dies after ~2 min uptime + leaves orphans."

## False First Root Cause (discarded)
Theory as of 2026-05-28: TIME_WAIT buildup on the fixed port 53351 (connection churn from the menubar's 7s polling + worker + Opus) + orphan dolt processes + a 10s bind timeout → bind fail → client circuit breaker. The fix idea at the time: delete the `.port` file so bd picks a fresh port instead of the TIME_WAIT port.
→ **Discarded.** The server never crashes (clean log), and the port isn't fixed-configured at all (ephemeral, only recorded in the port file). Idle shutdown is also off (`idle-timeout: "0"` in `config.yaml`). That also makes the "fresh port" idea moot.

## Real Root Cause (finding 2026-05-29): Two-Server Kill War
- **Log finding:** the bd server (53351) NEVER crashes — 0 hits for panic/signal/oom/killed across 34 MB of log spanning 2.5 months — but gets freshly restarted every ~8s (19,857 "Server ready" entries since March).
- **bd mechanics** (`gastownhall/beads`, formerly `steveyegge/beads`, `internal/doltserver/doltserver.go`):
  - `EnsureRunningDetailed` adopts the running server ONLY when `IsRunning()==true`; otherwise → `Start()`.
  - `Start()` calls `KillStaleServers()` (stderr message "Info: cleaned up N orphaned dolt sql-server process(es)") and kills, via `proc.Kill()` (SIGKILL), any `dolt sql-server` processes that aren't the canonical PID. Cleanup runs inside the lock (upstream GH#2430: otherwise journal corruption under concurrent bd processes).
  - **Routine reads do NOT trigger the restart:** 5 rapid `bd list --db .../.beads/dolt` calls (exactly the menubar command) → 0 restarts, all adopt cleanly. This refutes menubar polling as the driver (that was the first sub-theory, also wrong).
- **Second actor:** the Homebrew launchd service `homebrew.mxcl.dolt` (`~/Library/LaunchAgents/homebrew.mxcl.dolt.plist`): `KeepAlive=true`, `RunAtLoad=true`, `dolt sql-server --config /opt/homebrew/etc/dolt/config.yaml` on `localhost:3306` + `/tmp/mysql.sock`. `launchctl list` showed exit status `-9` (SIGKILL).
- **Coupling proven (lockstep timestamps):** bd server's last restarts …22:55:30 / :37 / :45; Homebrew's …22:55:30 / :41 / :52 — both in lockstep, both stopped at the same time (7s apart).
- **War mechanics:** bd's `KillStaleServers` shoots the Homebrew dolt (the SIGKILL / `-9`) → launchd respawns it (KeepAlive) → the resulting population of `dolt sql-server` processes makes bd's adoption fail → bd reboots its own server → an ~8s loop, on both sides.
- **Why it stopped on its own around 22:55** (before the manual intervention at 23:00:43): launchd's respawn throttle — the Homebrew service died too fast too often, launchd gave up respawning it → Homebrew dolt gone → bd's opponent gone → the bd loop ends. **Temporary:** `RunAtLoad` would have revived it on the next login and restarted the war.

## Fix
`brew services stop dolt` — removes the service from the boot set (no more `RunAtLoad` respawn). The dolt **binary** stays installed (bd needs it). Permanent + reboot-safe.
- **Verification:** `launchctl list` no longer lists `homebrew.mxcl.dolt`; the only live `dolt sql-server` = bd's project server (53351); the bd restart counter is frozen.
- **Leftover:** an orphaned `/tmp/mysql.sock` (harmless).

## Dynamic Ports — Assessment
Already dynamic/ephemeral (3 distinct ports, no config). "Force fully dynamic ports / a fresh port per restart (delete the port file)" → **not recommended**: doesn't address the real cause (the two-server war, now fixed) and introduces a client-race risk during the port-change window. Port collision between projects was not present at the time; `.beads/` is gitignored → no accidental port-file copying. The design at the time (ephemeral + port-file rendezvous) was correct.

## Remaining Follow-On Topics
- **Worker-spawn hardening:** spawn passes the prompt as a command-line argument (`claude "$(cat prompt)"`) → the worker cmdline carries arbitrary prompt text → vulnerable to ANY cmdline-match kill. Concretely: bd's dolt cleanup killed a worker twice at startup because its prompt contained the string "dolt sql-server". Real fix: pass the prompt via stdin/file instead of an argument (spawn infra `tmux_spawn.sh` in the iterative-dev plugin, cross-project). Urgency after the Homebrew fix is low (cleanup rarely fires anymore). **NO hook fix possible:** bd's kill is internal Go (`proc.Kill()`), invisible to PreToolUse Bash hooks.
- **Orphan-cleanup message:** after the Homebrew fix, just a one-liner on the real initial start, no more constant noise. (General tool-error noise stripping remains a separate, data-dependent topic.)
- **Related (project blank):** bd/dolt auto-start fragility (port collisions + 10s timeout + no fallback) — its own topic there.

## Sources
- `gastownhall/beads` (formerly `steveyegge/beads`) `internal/doltserver/doltserver.go`: `EnsureRunningDetailed`, `Start`, `KillStaleServers` / `killStaleServersForDir`, `IsAutoStartDisabled`, `IsRunning`, `allocateEphemeralPort`. GH#2430 (journal corruption → cleanup-in-lock), GH#2554 (shared server), GH#2641 (auto-start disable), GH#3142 (10s `readyTimeout`).
- Live: `.beads/dolt-server.log`, `/opt/homebrew/var/log/dolt.error.log`, `~/Library/LaunchAgents/homebrew.mxcl.dolt.plist`, `launchctl list`.
