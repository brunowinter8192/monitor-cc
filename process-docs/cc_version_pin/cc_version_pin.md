# CC Version Pin — proxy-launched Claude Code (2026-05-30)

## State (as of 2026-06-22)
Mains + workers run on pinned **CC 2.1.176** (newest stable), no auto-update. Bump cadence: **monthly to newest stable**, no rollback retention (only the current version exists).

**Pin convention (established, history 101→109→110→114→149→176):**
- Isolated npm install per version: `~/cc-cache-fix-<v>/node_modules/@anthropic-ai/claude-code/` — vanilla `npm install --prefix ~/cc-cache-fix-<v> @anthropic-ai/claude-code@<v>`. "cc-cache-fix" is just the directory name (historical); the actual cache fix is done by the proxy via cache_control override, NOT a binary patch.
- Wrapper `~/.local/bin/claude-<v>`: sets `DISABLE_AUTOUPDATER=1`, execs `~/cc-cache-fix-<v>/.../bin/claude.exe "$@"`.
- **Mains:** `CLAUDE_BIN` default in `src/claude_proxy_start.sh` → `${CLAUDE_BIN:-$HOME/.local/bin/claude-<v>}`. Overridable via `CLAUDE_BIN` env (user starts `PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project <ROOT>`).
- **Workers:** spawn via `tmux_spawn.sh` with its own default `${CLAUDE_BIN:-$HOME/.local/bin/claude-<v>}` (two spots: line 510 `spawn_claude_worker` + 699 `worker_revive`) — NOT bare `claude` (that was the state before 2026-06, now superseded). `tmux_spawn.sh` lives in the iterative-dev plugin: source `Meta/iterative-dev/src/spawn/tmux_spawn.sh`, live cache `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/src/spawn/tmux_spawn.sh`. `worker-cli` (itself in the cache) sources the cache copy → the cache MUST be synced (via `plugin-publish`).
- **npm-global** (`~/.npm-global/bin/claude`): bare `claude` in the user's terminal; also kept at `<v>` so nothing hangs on an old version. Workers no longer need it (they use the wrapper via tmux_spawn.sh).
- Auto-update globally off: env `DISABLE_AUTOUPDATER=1` (+ redundant in the wrapper).

## Update Procedure (template, monthly to newest stable)
0. Check newest stable: `npm view @anthropic-ai/claude-code dist-tags` → take the `stable` tag (NOT `latest`; they diverge).
1. `npm install --prefix ~/cc-cache-fix-<new> @anthropic-ai/claude-code@<new>` + wrapper `~/.local/bin/claude-<new>` following the claude-<old> pattern, `chmod +x`. (Orchestrator infra, no worker.)
2. `npm install -g @anthropic-ai/claude-code@<new>` (bare `claude` in the terminal).
3. `claude_proxy_start.sh`: `CLAUDE_BIN` default + the comment above it → `claude-<new>` (src/ edit → worker, monitor-cc).
4. `tmux_spawn.sh` lines 510 + 699: `claude-<old>` → `claude-<new>` (src/ edit → worker, iterative-dev). Then `plugin-publish` (rsync source→cache). Do NOT bump the plugin.json version — otherwise the cache-dir path moves and the hardcoded worker-cli cache path (`iterative-dev/1.0.0`) breaks.
5. DELETE the old wrapper + `cc-cache-fix-<old>` dir (no rollback — only the current version is kept). Running processes survive (mmap'd binary).
6. Verify: `ls ~/.local/bin/claude-*` + `ls -d ~/cc-cache-fix-*` = only `<new>`; `grep claude-<old>` in `claude_proxy_start.sh` + cache `tmux_spawn.sh` = empty. Live: new main session → proxy-log system block shows `cc_version=<new>`.

## 2026-05-30: 2.1.114 → 2.1.149
- Before: mains pinned to claude-114; workers bare `claude` = npm-global 2.1.119 (drift). Newest: latest 2.1.158, stable 2.1.149 → **149 (stable) chosen**.
- Motivation: a controlled, stable version so system-prompt/reminder/message changes from the next session on are cleanly observable in the Monitor (not blurred by auto-update drift).
- The running session stayed on 2.1.114 (the effect applies only to new mains/workers).

## 2026-06-22: 2.1.149 → 2.1.176
- npm dist-tags: stable **2.1.176**, latest/next 2.1.185 → **176 (stable) chosen**. Cadence from now on: monthly to newest stable.
- User decision: **no more rollback retention** — delete all pre-versions, keep only the current one (176). npm-global follows along with it (bare `claude` = 176); the earlier "follow along?" question no longer applies.
- Executed: `cc-cache-fix-176` + wrapper `claude-176` installed; `claude_proxy_start.sh` (monitor-cc dev, commit 3391fa3) + `tmux_spawn.sh` lines 510/699 (iterative-dev main, commit 3c8f408 → `plugin-publish`, cache version 1.0.0 unchanged) set to claude-176; `claude-149` wrapper + `cc-cache-fix-149` deleted.
- Doc correction: an earlier current-state claim, "workers run bare `claude` from PATH", was outdated — workers have spawned via `tmux_spawn.sh` with the claude-<v> wrapper (not bare) since the 114→149 round (proxy_tool_stripping, 2026-06-02).
- The running session stayed on 2.1.149 (the effect applies only to new mains/workers).

## 2026-07-20: 2.1.176 → 2.1.205
- npm dist-tags on 2026-07-20: `stable` 2.1.205, `latest`/`next` 2.1.215 → chose **2.1.205** (stable tag, not latest; 2.1.215 was bleeding-edge latest with the open post-compaction 1M→200k regression).
- Motivation — the trigger was the 1M-context question. Workers pinned to `claude-sonnet-5` were capped at 200k while the orchestrator on `claude-opus-4-8` got the full 1M, same proxy/auth/account. Root cause: CC 2.1.176 (2026-06-13) predates Sonnet 5 (shipped CC 2.1.197, 2026-06-30), so its internal context-window table has no `claude-sonnet-5` entry and falls back to a 200k budget — CC caps client-side before the API ever sees a >200k request. Not proxy, not auth, not entitlement (proven by Opus 4.8 getting 1M on the same stack).
- Evidence: `src/logs/api_errors.jsonl` held zero context/"too long" API errors (only 401/400/429/404); the worker died client-side at ~171k tokens (below 200k); the `claude-sonnet-5[1m]` suffix test produced a `not_found_error` 404, confirming the proxy forwards the model string verbatim. The proxy code touches neither `anthropic-beta` headers nor auth (headers pass through as CC sets them).
- Executed: `npm install --prefix ~/cc-cache-fix-205 @anthropic-ai/claude-code@2.1.205`; wrapper `~/.local/bin/claude-205` (claude-176 pattern, `DISABLE_AUTOUPDATER=1`); `npm install -g @anthropic-ai/claude-code@2.1.205`; `claude_proxy_start.sh` CLAUDE_BIN default → claude-205 (monitor-cc, via worker); `tmux_spawn.sh` lines 542 + 734 → claude-205 (iterative-dev main, via worker; the Update-Prozedur template's 510/699 had drifted to 542/734).
- Cache sync: copied the edited `tmux_spawn.sh` directly into the `iterative-dev/1.0.0` cache instead of running `plugin-publish` — `plugin-publish` bumps the plugin version, which would move the cache dir off `1.0.0` and break worker-cli's hardcoded cache path. plugin.json version left at 1.0.0.
- Deferred: deletion of the old `claude-176` wrapper + `cc-cache-fix-176` dir. The bump session itself stayed live on 2.1.176 (its binary is mmap'd and survives), so the 176 cleanup runs after that session ends, not during it.
- Running session stayed on 2.1.176 (effect applies only to new mains/workers started via `claude_proxy_start.sh` / `tmux_spawn.sh`).

## Logging Gate (verified — why Monitor observation is sufficient)
The proxy logs the **modified_payload** (= exactly what goes to the API) to `src/logs/api_requests_<id>.jsonl` as the `raw_payload` field — built in `_build_entry()` (`src/proxy/logging.py`), called with `modified_payload` in the `request()` hook of `src/proxy/addon.py` (after all strip/inject steps). Stripped content is preserved in separate fields: `stripped_msg_originals`, `original_system2_text`, `stripped_sys3_original`, `stripped_tool_descs_originals` + the `modifications` list.
- **Consequence:** nothing is lost; "what goes to the API" is 1:1 in the Monitor. **User decision:** bulletproof pre-modification original capture is NOT needed — `raw_payload` (= API truth) is sufficient for observation.
- Evidence: 46/139 records of an Opus log with `<system-reminder>` in raw_payload; main requests with a 3-block system prompt incl. `x-anthropic-billing-header: cc_version=...`.

## Sources
- npm dist-tags `@anthropic-ai/claude-code` (stable/latest/next), queried 2026-05-30 + 2026-06-22 (stable 2.1.176).
- `tmux_spawn.sh` (worker pin, lines 510/699), iterative-dev plugin (source `Meta/iterative-dev`, cache `iterative-dev/1.0.0`); `plugin-publish` (rsync source→cache).
- `src/proxy/addon.py` (`request()` hook, `modified_payload`), `src/proxy/logging.py` (`_build_entry`, `raw_payload`).
- `src/claude_proxy_start.sh` (`CLAUDE_BIN` default), `~/.local/bin/claude-<v>` wrapper.
