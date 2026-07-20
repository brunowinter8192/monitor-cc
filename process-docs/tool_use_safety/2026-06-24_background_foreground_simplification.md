# Background/Foreground Simplification — force-all-foreground, remove polling + force-bg hooks (2026-06-24)

Resolves the open question in `2026-06-24_block_log_read_too_broad.md` (narrow vs kill `block_log_read` → **killed**, comprehensively) and converges the foreground-forcing direction left Pending in `2026-06-23_polling_foreground_structural.md`. Status: CONVERGED + SHIPPED (Stage 1 merged to dev `87fb096`, live-verified).

## Decision — two-layer model, everything else removed

1. **Force ALL non-timer background → foreground** (Hook 3 `block_unauthorized_background`, whitelist trimmed to the sleep-timer only).
2. **Proxy injection carries the rest** — the two existing injections ARE the whole signalling layer:
   - `strip_bg_launch_ack` (BL): CC's `Command running in background with ID:` → replaced with *"Command is running in the background. Do NOT check, poll… (you will get a completion notice)."*
   - `strip_bg_completed` (`_WAKEUP_TEXT`): CC's bg-exit notice → *"background done — check worker or other process."*

Polling-prevention + force-to-background hooks DELETED — redundant once foreground is universal and the injection handles the rest. Proxy untouched (the injections already existed; no proxy change).

## Evidence that closed the structural blocker

The prerequisite left open in `2026-06-23_polling_foreground_structural.md`: does CC's auto-background-after-foreground-timeout emit the same ack `strip_bg_launch_ack` catches? **Confirmed YES** (user screenshot, trading session, 2026-06-24): `rag-cli index --collection trading-reference` ran FOREGROUND (`timeout 600000`, no `run_in_background`); after the 10-min foreground timeout CC auto-backgrounded it and emitted `Command running in background with ID: bu15k7bdy. Output is being written to: /private/tmp/claude-501/…` — the exact ack the anchor matches. → Long jobs (index/scrape) ARE covered by the injection model: foreground → CC auto-bg → "go idle" inject → idle → "background done" inject on completion. The earlier "CC kills foreground at 10min" retraction stands; the real behavior (auto-background, emits ack) is what makes the model work.

## What shipped (Stage 1)

Removed (renamed `.py.disabled`, dropped from `_HOOK_SCRIPTS`, swept from `~/.claude/settings.json`):
- Hook 8 `block_polling_loop` — frequency poll-blocker
- Hook 21 `block_busywait_loop` — single-call busywait poll-blocker
- Hook 33 `block_log_read` — the `.log` read funnel (the call#187 collateral source)
- Hook 25 `rewrite_reddit_index_background` — force reddit-indexer → bg
- Hook 26 `rewrite_pipe_background` — force pipe_scraper/theblock → bg

Hook 3 `block_unauthorized_background`: deleted `_INDEXER_CANONICAL` / `_RAG_INDEXER_CANONICAL` / `_PIPELINE_CANONICAL`; `_is_canonical` = `_CANONICAL.match` only (sleep-timer). Smoke 9/9 (`test_block_unauthorized_background.py`; the 2 ex-whitelist cases now assert foreground-force). `log_janitor.py` `polling_state` LogSpec removed. Kept: Hook 3 (trimmed), Hook 18 `rewrite_background_sleep`, Hook 24 `block_worker_send_background`.

Merge mechanics: FF merge onto dev; `.githooks/post-merge` fired on the FF and ran `hook_setup.py`; `_sweep_stale_hooks` removed the 5 registrations (their `.py` paths now `.disabled`). Verified: ZERO stale registrations (no global Bash exit-2 lockout). Live-verify: `cat`/`tail` on a `.log` now passes (was `block_log_read` Branch B exit-2).

## Stage 2 (shell-`&` foreground hook) — EVALUATED, NOT BUILT

Considered: a hook forcing trailing single `&` (shell-level background) → foreground, since shell-`&` bypasses Hook 3 (flag-only) and produces NO CC ack → NO injection.

Live test (2026-06-24): `nohup sleep 15 > /tmp/x.log 2>&1 & echo …` with `run_in_background=false` → Bash returned immediately with normal stdout, NO go-idle injection. Confirms shell-`&` / nohup detach is invisible to CC; the proxy has nothing to catch.

Distinction a shell-`&` hook would face:
- `nohup/setsid … &` = deliberate detached daemon (debug launches; prod daemons use launchd, NOT Bash-`&`). Returns immediately, agent verifies. Foreground-forcing BREAKS this (daemon blocks → auto-bg → "go idle" → never completes → no wake). Would need exemption.
- `work-cmd &` = the only anti-pattern (hide a work job, then poll the log). Rare; no frequency evidence.

**Decision: do NOT build Stage 2.** The detached case is correct fire-and-forget (no problem). The `work-cmd &`-and-poll case cannot be cleanly closed (detached = invisible to CC) without breaking daemon launches, has no evidence of occurring, and a hook + nohup-exemption re-adds the complexity Stage 1 removed — violating the project's block-on-evidence hook principle. **Accepted residual:** an agent could shell-background a work job and poll it unguarded (block_polling_loop/block_log_read are gone); revisit with a targeted hook only if fire-log shows it.

## Mental model (user framing, canonical)

CC knows only foreground vs background for commands ASSIGNED to its session (the `run_in_background` flag + auto-background-after-timeout). Background-in-the-CC-sense → proxy injection. Foreground → irrelevant (visible, completes). Detached (shell-`&` / nohup / launchd) → not assigned to the session → invisible → unhookable, but rarely a problem.

## Session incident (noted, not root-caused)

During this session, after the Stage-1 FF-merge onto dev (`87fb096`), the main repo working tree was found checked out back to `main` (`28b9e5a`) via an external `checkout: moving from dev to main` (reflog `HEAD@{0}`) that the orchestrator did NOT issue. Effect: a stale read of `pipe07` (main/original content). No data loss — work preserved on `dev` + `bg-fg-hooks` at `87fb096`, `settings.json` correctly swept (5 hooks unregistered) throughout. Recovery: `git checkout dev`. Trigger unknown (other terminal / menubar / automation) — flagged for awareness; latent risk is `hook_setup.py` re-running from a main-state working tree (would re-add the 5 entries), neutralised permanently once dev→main lands.
