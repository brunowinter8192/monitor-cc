# 2026-09-25 - Launcher split, shell comment removal, launcher fall-through logging (worker mc6a)

Session of worker mc6a, branch `mc6a`. Task: the confirmed Phase 6 findings for the shell side of monitor-cc: split `src/claude_proxy_start.sh` and extract helpers from its janitor (structure), remove comments from shell code (content salvaged below), remove the Linux branches, log the silent model-config fall-throughs, abort on a failed mitmdump start. Three code commits, one per group, plus this recap.

## Scope decisions (from Main)

- Module-layout gaps (section order, orchestrator purity, stepdown order) are tracked elsewhere; here only the two size findings were handled, and the new layout follows the section markers anyway.
- The launcher starts the live proxy. It was never run for real; every proof runs in a sandbox.
- An absent `model_selection.json` stays silent (normal state before the Models tab first writes it). Only jq missing, unreadable file and malformed JSON are logged. A missing or empty `main` key in a valid file is also silent (valid state, same as before).
- The robot emoji inside the `.githooks/commit-msg` regex stays: it is a match pattern, not decoration.
- mitmdump stderr stays `2>/dev/null` (the proxy has its own error log file).

## Launcher layout after the split

- `src/claude_proxy_start.sh` (207 LOC): INFRASTRUCTURE (constants, two `source` lines), ORCHESTRATOR `proxy_start_workflow "$@"` (only function calls, in the original execution order), FUNCTIONS below. Variables stay global exactly like in the old inline script (`PROJECT`, `CLAUDE_ARGS`, `PROXY_PORT`, `MARKER_FILE`, `TMP_MARKER`, `LIVE_ADDON`, `LIVE_DIR`, `PROXY_PID`, `HEARTBEAT_PID`); `$$` is still the script PID, so the marker contents, the trap and the heartbeat behave the same. The script is the last command of the workflow so its exit status is claude's exit status, as before.
- `src/proxy_start_janitor.sh` (112 LOC, sourced): live-copy sweep, dual-log rotation. `_janitor_cleanup_jsonl_logs` (was 62 lines) is now an orchestrator-style function over `_rotate_original_logs <opus|worker>`, `_surviving_log_ids`, `_delete_unlisted_dual_logs`, `_remove_legacy_logs`. The helpers print their counts on stdout and are called in command substitutions, so they must not echo anything else. `DUAL_LOG_DIR` is still a `local` of `_janitor_cleanup_jsonl_logs` read by the callees through bash dynamic scope (as the version-purge function always did).
- `src/proxy_start_markers.sh` (78 LOC, sourced): `_proxy_pid_is_live`, `_marker_is_stale <file> <pid_line>` (replaces the two near-identical inline blocks; per-project marker keeps the PID on line 3, the `/tmp` marker on line 4), `_write_project_marker`, `_write_tmp_marker`, `_marker_heartbeat`, `_remove_marker_if_owned`, `cleanup`.
- `dev/proxy/marker_race_repro.sh` extracts `_proxy_pid_is_live` with awk from a script path; it now points at `src/proxy_start_markers.sh` (verified: 12 passed, 0 failed).
- `dev/hook_smoke/test_version_purge.sh` carries a hand-mirrored copy of `_compute_proxy_hash`; its md5 line was changed to the macOS-only form to stay in sync (8 assertions pass).

## Fall-through and tripwire changes (P5-6)

- Linux branches removed: `md5sum` in the session id and in `_compute_proxy_hash`, `stat -c %Y` in the marker staleness check. The project runs on macOS only (py2app, osascript, Ghostty); no Linux run was ever recorded.
- `_resolve_config_model` now prints one stderr line and continues without `--model` for each of: jq not on PATH, file not readable, file not valid JSON. Line format: `claude_proxy_start: <file> ... , no --model injected`. Observed in the sandbox for a `{not json` file: `claude_proxy_start: <HOME>/.claude/shared-rules/model_selection.json is not valid JSON, no --model injected`.
- Tripwire: after `sleep 1` the launcher checks `kill -0 $PROXY_PID`; if the proxy died it prints `claude_proxy_start: mitmdump failed to start on port <port>, aborting` to stderr and exits 1. The EXIT trap is already set at that point, so live copies and owned markers are removed. Sandbox observation with a stub mitmdump that exits 1: the base ref still launched claude (exit 0); the new script exits 1, never starts claude, leaves no live copy, no `.proxy_session_*` and no `/tmp` marker.
- Not changed on purpose: the `>/dev/null 2>&1` sweeps, `sed ... 2>/dev/null` marker reads, `2>/dev/null` on deletes, the silent skip of the combined CA bundle when the system CA file is missing (listed in the scan, not in the confirmed list).

## Proof design (reusable)

- `dev/proxy/proxy_start_sandbox.py`: builds per case a temp root (copy of `src/proxy_addon.py`, `src/proxy/`, the launcher), a temp HOME with a fixture CA and optional `model_selection.json`, and a private PATH directory that contains only symlinks to the real tools the launcher needs plus stubs for `mitmdump`, `claude`, `lsof`, `worker-cli`. jq is symlinked only when the case wants it, which is how "jq missing" is produced without touching the machine. The stub claude records its args, the proxy env, cwd, parent PID (= launcher PID) and the marker files as they exist while claude runs; the stub mitmdump records args and env and then `exec sleep 30` so the launcher can kill it.
- `dev/proxy/verify_proxy_start_equivalence.py`: 12 strands (default, explicit `--model`, config main injected, explicit wins over config, malformed config, empty main, absent config, busy ports 8080 and 8081, first-run CA generation, live marker with fresh log, dead-PID marker, janitor fixture). Each strand runs the base-ref launcher (`git show integration:src/claude_proxy_start.sh`) and the working-tree launcher on identical frozen input and compares return code, stdout, stderr (with the new `claude_proxy_start:` lines dropped), stub records, the whole `src/logs` tree with contents, active plugins file, combined CA presence and left-over `/tmp` marker. Epochs, launcher PID, live PID and the variant directory are normalized. Result: 12/12 identical after the split and again after the P5-6 edits.
- Janitor fixture (observed output, identical old and new): 20 stale plus 40 fresh opus originals with forwarded/errors siblings, 32 worker originals with responses, one orphan forwarded file, legacy files, two orphan live copies, stale `.proxy_version`. Stdout: `Janitor: cleaned 2 orphan live-copies`, `Janitor: version change (40 stale dual-logs purged)`, `Janitor: rotated 35 dual-log files`.
- Sensitivity check (mutation): changing `-lt 60` to `-lt 0` in the marker library and `JANITOR_KEEP=30` to `29` made exactly `case_marker_live_fresh` and `case_janitor_fixture` abort (10/12 passed); the mutations were reverted. A comparison that cannot fail proves nothing, so repeat this kind of check when the harness is extended.
- `dev/proxy/test_proxy_start_fallbacks.py`: 7 strands for the intended changes (jq missing, unreadable, malformed, absent silent, empty main silent, valid config silent and injects, mitmdump start failure aborts and contrasts with the base ref). All pass.
- Harness pitfall that cost a run: `\b` does not match between `_` and a digit, so epoch and PID normalization must use digit look-arounds (`(?<![0-9])...(?![0-9])`).
- Comment removal proof: `bash -n` on every file, plus a comparison of old and new with full-line comments, trailing whitespace and blank runs normalized: identical for all nine files except the two intentional edits (`marker_race_repro.sh` path, three trailing comments in two dev files). The three scripts that can run safely (`test_version_purge.sh`, `verify_launcher_model_precedence.sh`, `p1_arg_parse_dry_run.sh`) produced identical output before and after apart from the report path of the old copy run from `/tmp`. `test_tmux_layout.sh` (needs tmux) and `dump_all.sh` (signals real panes) were only syntax checked.
- The dry-run scripts write a timestamped report into their `md/` directory on every run; the stray file from the proof run was deleted.

## Notes for a successor

- `.githooks/*` have no section markers and are not required to have them; only comments were removed.
- The `dev/` shell scripts mirror launcher logic by hand (`p1_arg_parse_dry_run.sh`, `verify_launcher_model_precedence.sh` mirror the argument parsing and the config precedence; they do not include the new log lines). If the parsing changes, they need the same edit.
- The equivalence harness compares against the `integration` ref (`BASE_REF` in the sandbox module). After this branch is merged into `integration` that ref is the new launcher and the comparison becomes vacuous; point `BASE_REF` at the merge-base commit `0c837c41` (or any pre-split commit) to rerun it.
- Hypothesis, never observed: a slow machine where mitmdump needs more than one second to fail would pass the new liveness check and behave as before.

## Salvaged comments (verbatim, removed from the code)

Full-line comments of every file that lost its comments, in file order. Trailing comments are marked `(trailing)`. Divider lines are omitted.

### src/claude_proxy_start.sh (before the split, from the base ref)

```
Start Claude Code with API request logging via mitmproxy
Usage: ./src/claude_proxy_start.sh [--project <path>] [claude args...]

No CLI model shortcuts (2026-09-23, removed) — the model is steered exclusively through the
menubar's Models tab. Precedence, highest first: (1) an explicit --model (anywhere in the args)
always wins; (2) "main" from ~/.claude/shared-rules/model_selection.json (2026-08, model-selector
milestone 3 — the menubar's Models tab writes this file); (3) nothing — no --model is injected
at all, byte-identical to today's no-flag behavior. A missing/unreadable file, malformed JSON,
or a missing/empty "main" key all fall through to (3) silently — this launcher must never fail
because of that file.
Trigger a background stale-worker sweep on every main-session start (worker-cli janitor).
Fully detached — never delays/blocks session start. Guarded so a machine without
worker-cli installed doesn't break the script.
Trigger a background stale-monitor sweep on every main-session start (src/monitor_janitor.py).
Fully detached — never delays/blocks session start. Kills tmux sessions named monitor_cc_*
older than 24h (nine panes each); this is a same-repo module, no command -v guard needed.
cd into MONITOR_CC_ROOT first so `-m src.monitor_janitor` resolves regardless of the caller's
CWD (--project may point anywhere). Also runs independently once a day via a LaunchAgent
(see setup_monitor_sweep.py) so monitors accumulate across projects/reboots even when no
main session ever starts.
Parse --project argument; remaining args (incl. an explicit --model) passed to claude
(trailing) set when the user passes --model directly, anywhere in the args
Second tier: no explicit --model — fall back to "main" from the shared model-selection config
(menubar Models tab). jq is used here because it's already a real dependency of the sibling
worker-spawn script that reads this same file — hand-parsing JSON with grep/sed would be more
fragile exactly where robustness matters (the malformed-JSON degradation case). command -v jq
guards a machine without jq installed (same idiom as the worker-cli guard above); a
missing/unreadable file, malformed JSON, or a missing/empty "main" key all leave CONFIG_MODEL
empty, so no --model is injected — degrades silently to the no-injection case, never aborts
the launcher.
Generate session_id from project path: first 8 chars of md5 of the NORMALIZED path (matches
monitor.py's hash logic and tmux_launcher.py:generate_session_name's
os.path.normpath(os.path.expanduser(project_path)) byte-for-byte, so a trailing slash, a
relative path, or a leading ~ can never make the proxy-side and tmux-side hashes diverge).
Per-start unique id: project hash + pid + epoch — prevents live-copy collision when two
sessions run in the same project simultaneously (SESSION_ID stays per-project for worker discovery)
Generate per-start log id: opus_ prefix + sanitized project basename + unix timestamp
Find a free port starting at 8080
Generate CA cert if first run
Build combined CA bundle (system CAs + mitmproxy CA) for Python MCP servers
Write marker file so monitor can discover port and log_id for this session
Check if a stored marker PID belongs to a live claude_proxy_start.sh session.
kill -0 alone is insufficient: PID reuse by an unrelated process produces false-positives
(same class of bug as the retired port-reuse guard). Secondary identity check via ps args
ensures the process is actually claude_proxy_start.sh, not an unrelated recycled PID.
Only overwrite marker if its referenced session is no longer active.
Parallel sessions for the same project must NOT clobber a live marker.
Primary liveness: stored PID + process-identity (prevents PID-reuse false-positives).
Secondary liveness: log mtime < 60s (belt-and-suspenders for alive sessions).
Every marker on disk carries the PID line — no PID line means no liveness signal, stale.
Verify PID is a live claude_proxy_start.sh process
PID dead or not a claude_proxy_start.sh process: stale regardless of log mtime
Also write to /tmp for cross-repo discovery (workers find proxy via this)
Format: line 1 = port, line 2 = log_id, line 3 = MONITOR_CC_ROOT, line 4 = owner PID
Same guard: PID+identity primary, mtime secondary — every marker on disk carries the PID line.
PID dead or not a claude_proxy_start.sh process: stale regardless of log mtime
Copy addon and entire proxy/ package to isolated live copies — prevents git merge hot-reload
Use PROXY_SESSION_UID (not SESSION_ID) so parallel sessions in the same project don't overwrite each other
Janitor: remove orphan live-copies left by sessions that exited without cleanup.
Runs before this session's own live-copies are created so they cannot be self-evicted.
Pass 1: iterate shim files — each shim is the authoritative reference for its pair
Skip if any mitmdump process is running with this shim's full path
Pass 2: remove live dirs whose shim was already removed (or never created)
Compute stable content hash over proxy source: proxy_addon.py + .py/.json files under proxy/
Excludes __pycache__/*.pyc (noise on recompile), DOCS.md, .DS_Store — code + schemas only.
Phase 0 of the janitor: delete stale (>60min) dual-logs when proxy source changed.
Called from _janitor_cleanup_jsonl_logs; reads $DUAL_LOG_DIR + $SCRIPT_DIR from caller scope.
Janitor: rotate dual-log files (keep 30 opus + 30 worker by _original count) + legacy cleanup.
Phase 0: version-aware purge (runs before count-rotation)
Phase 1a: rotate opus _original files — keep 30 newest, delete older
Phase 1b: rotate worker _original files — keep 30 newest, delete older
Phase 2: union surviving log_ids from remaining _original files after rotation
Phase 3: delete other dual-log files not in surviving set
suffix list includes 'errors' (pre-existing bug: was missing, causing _errors to always be deleted)
Remove legacy api_error_payload_*.json files (writer switched to api_errors.jsonl)
Remove legacy proxy_errors_*.log files (mitmdump uses 2>/dev/null since 2026-05-28)
Remove legacy tool_use_errors.jsonl (no writer; superseded by _errors dual-log)
Reset active_plugins.json to default — only iterative-dev injected at session start
Start proxy in background
Background heartbeat: if the primary session exits (cleanup or crash), secondary sessions reclaim
the marker within ~10s instead of remaining blind forever.
kill -0 $PROXY_PID uses plain liveness (our OWN process — no PID-reuse risk, we just forked it).
$$ inside the subshell expands to the parent shell's PID (bash spec: $$ in subshell = invoking PID).
Cleanup on exit: kill proxy and heartbeat, remove live-copies, conditionally the per-project marker
Remove per-project marker only if we own it (our PID is on line 3).
A parallel session may have reclaimed the marker via heartbeat — don't clobber it.
Remove /tmp marker only if we own it (our PID is on line 4).
Pinned to v2.1.280 via ~/.local/bin/claude-280 wrapper (bumped 2026-09-23 — claude-opus-5-5,
selectable via the menubar's Models tab, is absent from 2.1.258 and stable-tag 2.1.267, present
in 2.1.280 / npm latest). Override with CLAUDE_BIN env var if needed.
Claude Code uses cwd as working directory — switch to target project
Start Claude Code with proxy settings
```

### .githooks/commit-msg

```
Global commit guard — enforces a single author identity and a trailer-free commit message.
Installed machine-wide via `git config --global core.hooksPath ~/.githooks`.

Rejects (never silently rewrites — a visible abort shows that something TRIED to write it):
1. Co-Authored-By / Signed-off-by-style attribution trailers, and "Generated with" tool banners
2. An author or committer identity other than the expected one

A repo with its own core.hooksPath overrides this file — such repos need their own copy.
1. Attribution trailers / tool banners in the message body
2. Identity — `git var` resolves the same values git will actually record,
including env overrides (GIT_AUTHOR_NAME etc.) that a plain config read would miss.
macOS ships bash 3.2 — no ${var,,}; label is passed explicitly instead.
```

### .githooks/post-commit

```
Auto-run hook_setup.py when src/hooks/* files change on commit.
Fail-silent — git commit must not fail due to this hook.
```

### .githooks/post-merge

```
Auto-run hook_setup.py when src/hooks/* files change on merge.
Fail-silent — git merge must not fail due to this hook.
```

### dev/proxy/marker_race_repro.sh

```
dev/proxy/marker_race_repro.sh
Deterministic repro probe for proxy marker lifecycle race conditions.

_proxy_pid_is_live() is sourced from the real claude_proxy_start.sh (no logic duplication).
_is_stale() in this probe mirrors the inline write-guard logic in the real script and calls
_proxy_pid_is_live as its primary check — it is test harness, not duplicated production code.

Scenarios:
S1: restart-within-60s      dead PID + fresh log  → must be stale   (pre-fix mtime-only: live = BUG)
S2: parallel session        alive clone + fresh    → must be live    (no clobber)
S2b: clone dies             same marker, dead PID  → now stale       (heartbeat reclaim trigger)
S3: crash / kill-9          dead PID + stale log   → must be stale
S4: PID-reuse (new)         alive unrelated PID    → must be stale   (pre-fix kill-0 only: live = BUG)
S5a: heartbeat, missing     marker absent          → reclaims
S5b: heartbeat, dead PID    dead PID in marker     → reclaims
S5c: heartbeat, live owner  alive clone in marker  → keeps (no clobber)

Usage (from project root):
bash dev/proxy/marker_race_repro.sh

Exit: 0 if all PASS, 1 if any FAIL.
── Source _proxy_pid_is_live from the real script ─────────────────────────────────────────
Extract the function block (awk range: header → closing brace at column 0)
── Test environment ───────────────────────────────────────────────────────────────────────
Create a fake forwarded log with controllable mtime
Simulate write-guard staleness decision (mirrors inline guard in claude_proxy_start.sh).
Calls _proxy_pid_is_live (sourced from real script) as primary check.
Old format: mtime-only fallback
Simulate heartbeat reclaim decision (mirrors _marker_heartbeat body in claude_proxy_start.sh).
Find a reliably dead PID (high range, validate)
Fallback: start and immediately reap a subprocess
── S1: restart-within-60s ─────────────────────────────────────────────────────────────────
Symptom scenario: old session dead, log fresh (within 60s). Pre-fix mtime-only guard
returns "live" (bug). Fixed guard sees dead PID → stale → new session claims.
Document the pre-fix bug: mtime-only check would have returned "live"
── S2: parallel session (alive clone, no clobber) ────────────────────────────────────────
A second session starts while first is alive. Must defer (not clobber).
Spawn process with argv[0]=claude_proxy_start.sh (exec -a sets argv[0] without launching the real script)
(trailing) allow exec to complete
── S2b: clone dies → heartbeat reclaim ───────────────────────────────────────────────────
Remove from CLEANUP_PIDS (already dead) — bash arrays: rebuild without it
── S3: crash / kill-9 (no cleanup, stale log) ───────────────────────────────────────────
── S4: PID-reuse by unrelated process (Opus amendment) ──────────────────────────────────
The old kill-0-only guard has the same false-positive class as the retired port-reuse guard:
an alive but unrelated process with a recycled PID passes kill-0 and causes permanent deferral.
New identity check (ps args must contain claude_proxy_start.sh) correctly rejects it.
Confirm the process IS alive (kill -0 would pass — that's the bug)
── S5: heartbeat reclaim logic ───────────────────────────────────────────────────────────
S5a: marker missing → reclaim
S5b: marker has dead PID → reclaim
S5c: marker has alive clone → keep (don't clobber live primary)
── Summary ───────────────────────────────────────────────────────────────────────────────
```

### dev/display/test_tmux_layout.sh

```
test_tmux_layout.sh — Verify tmux 3-pane layout for Monitor_CC

Creates a temporary tmux session with the target layout:
Left (50%)  |  Right-Top (25% of right) — rules pane
|  Right-Bottom (75% of right) — subagent pane

Outputs: tmux list-panes showing pane indices, dimensions, positions.
This tells us which pane index maps to which screen position,
so tmux_launcher.py can target the correct panes with commands.

Source: tmux man page (github.com/tmux/tmux tmux.1 L3591-3648)
- split-window -h: horizontal split, new pane to the right
- split-window -v -t X: vertical split of pane X, new pane below
- -b flag: place new pane above/left instead of below/right
- -l 25%: percentage of the TARGET pane's available space

Usage: bash dev/display/test_tmux_layout.sh
Cleanup any previous test session
Step 1: Create session with first pane (will be "main" — left side)
Step 2: Horizontal split — creates right pane (pane 1)
-h = horizontal, -l 50% = right pane gets 50% of window width
Step 3: Vertical split of the RIGHT pane (pane 1) — creates rules pane
-v = vertical split, -t pane 1, -b = new pane ABOVE (top-right)
-l 25% = new pane gets 25% of pane 1's height
Output: show all pane info
Also show which pane is where by position
Cleanup
```

### dev/hook_smoke/test_version_purge.sh

```
Smoke test: version-aware dual-log purge (Phase 0 of _janitor_cleanup_jsonl_logs).
Functions below mirror _compute_proxy_hash() and _janitor_version_purge_jsonl_logs()
from src/claude_proxy_start.sh — keep in sync when editing either.

Usage (from project root): bash dev/hook_smoke/test_version_purge.sh
---- Functions mirrored from src/claude_proxy_start.sh ----
Compute stable content hash over proxy source: proxy_addon.py + .py/.json files under proxy/
Excludes __pycache__/*.pyc (noise on recompile), DOCS.md, .DS_Store — code + schemas only.
Phase 0 of the janitor: delete stale (>60min) dual-logs when proxy source changed.
Called from _janitor_cleanup_jsonl_logs; reads $DUAL_LOG_DIR + $SCRIPT_DIR from caller scope.
---- Test infrastructure ----
Set file mtime to 2 hours ago (macOS: date -v-2H; GNU fallback: date -d)
---- Test cases ----
(a) version change purges stale (>60min) logs
(b) same version — no purge
(c) fresh (<60min) logs survive a version-change purge
(trailing) fresh (mtime = now)
(trailing) stale
(d) absent marker triggers first-run cleanup
```

### dev/model_selector/verify_launcher_model_precedence.sh

```
Dry-run for the --model/--project/config-file precedence chain in src/claude_proxy_start.sh, as
of the 2026-09-23 shortcut removal (--fable/--opus dropped — the menubar is now the only way to
steer the model). Mirrors the exact parse loop + precedence resolution from that script — keep
in sync when editing either. A narrower, config-file-unaware version of the pre-shortcut-removal
parse loop is also mirrored in dev/native-model-start/p1_arg_parse_dry_run.sh (milestone-native-
model-start's own dry run, predates the config tier and stays valid for the tiers it covers).
Pure argument-parsing simulation: never starts the proxy or claude, never touches the real
~/.claude/shared-rules/model_selection.json — all config-file cases use a temp path.

Usage (from project root or worktree root): bash dev/model_selector/verify_launcher_model_precedence.sh
---- Parse loop + precedence resolution mirrored from src/claude_proxy_start.sh ----
---- Test infrastructure ----
---- Tier 1 sanity re-checks (no config file in play) ----
---- Tier 2: config file (main key) ----
---- Tier 3: degradation cases (config present but unusable, or absent) -> nothing injected ----
---- Report ----
```

### dev/native-model-start/p1_arg_parse_dry_run.sh

```
Dry-run for the --fable/--opus/--model argument-parsing logic in src/claude_proxy_start.sh.
Mirrors the exact parse loop from that script — keep in sync when editing either.
Pure argument-parsing simulation: never starts the proxy or claude.

2026-08 (model-selector milestone 3): the real script grew a THIRD, lower-precedence tier
(config-file fallback via ~/.claude/shared-rules/model_selection.json) below the two tiers
this file covers. This file's own tiers and assertions are still accurate as-is; the full
current precedence chain (all 4 tiers) is covered by
dev/model_selector/verify_launcher_model_precedence.sh instead of duplicating it here.

Usage (from project root or worktree root): bash dev/native-model-start/p1_arg_parse_dry_run.sh
---- Parse loop mirrored from src/claude_proxy_start.sh ----
---- Test infrastructure ----
---- Report ----
```

### dev/ram_audit/dump_all.sh

```
Trigger SIGUSR1 RAM dump on all running monitor_cc panes.
PID files: /tmp/.monitor_cc_pid_<pane>  (written by register_ram_dump at loop entry)
Dumps land in: dev/ram_audit/dumps/<YYYYmmdd_HHMMSS>_<pane>.txt
```
