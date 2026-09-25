# Main session 2026-09-25 (afternoon): closing the issues left by the refactor pass

Orchestrator-level record. One Main agent ran from the websearch repo and worked monitor-cc, websearch, trading and iterative-dev in parallel. Worker-level details are in the worker entries of this area and of the areas proxy, model_selector, refactor_sweep (websearch), dev_refactor (trading) and worker_spawn (iterative-dev), all dated 2026-09-25.

## Scope and user instruction

- Input: six issues left by the morning refactor pass (monitor-cc 137 Modulaufbau, 138 Applyblitz, 139 Zeitstempel; websearch 53 Modulaufbau; trading 41 Aeragrenzen; iterative-dev 8 Testfenster, created in this session).
- The user rejected ending the session with new issues. Every finding that surfaced during the work (emoji glyphs, tests writing into live logs, remaining `+00:00Z` writers, dead dev scripts, oversized PNGs, silent dev handlers, the Era-3 peak claim) was fixed in the same session instead of being filed. A successor should expect the same instruction: surface findings, then close them, do not file them.

## Where the four-eyes lists live

The morning four-eyes lists existed only in `/tmp/refscan/` (`mc6_findings.md`, `ws6_findings.md`, `tr6_findings.md`, `p6_confirmed_*.md`). They are gone after a reboot; the worker entries of 2026-09-25 carry the re-measured numbers.

## Worker layout that worked

- monitor-cc: `mcfix` (138, 139), `mcsrc` (src layout, absolute imports), `mcdev` (dev layout). websearch: `wssrc`, `wsdev`. trading: `trera`. iterative-dev: `idwin`.
- Diffs of 0.5 to 1.4 MB per branch were too large for Main to read. Four read-only reviewer workers (`rvmcsrc`, `rvmcdev`, `rvwssrc`, `rvwsdev`) read each diff completely, round by round, and wrote findings to `/tmp/s0925/rv_<branch>.md`. Results: round 1 found 0 behaviour defects but scan blind spots; round 2 found 3 behaviour defects in mcdev (an extracted helper leaving a local unbound, two imports hoisted to module level that needed runtime env); round 4 found one more (a harness reading the real `~/.claude` after `isolate_home` redirected HOME). Each author scan had reported 0 before the reviewer found these. Lesson: an author's own AST scan is only as strong as its rule list; an independent reviewer with fresh-interpreter import and `--help` comparisons against base is what caught behaviour changes.
- Proofs that hide real-home readers: comparisons run under an empty fake HOME cannot see scripts that read `~/.claude`. Use a HOME with the real `.claude` symlinked or copied.

## Production failure after the merge (observed, fixed)

- After merging `mcsrc`, `worker-cli spawn vproxy` aborted: "Worker proxy for 'vproxy' did not come up on port 8104", mitmdump log "Error logged during startup, exiting...". Every new worker spawn in every project failed; running sessions were unaffected.
- Cause: the proxy live copy had two copiers. `claude_proxy_start.sh` (changed to the new `.proxy_live_<id>/src/` layout) and iterative-dev `src/spawn/worker_proxy.sh` `_proxy_launch` (still the old `.proxy_live_<id>/proxy` layout). The shim `proxy_addon.py` requires `src/proxy` under the live dir and raised.
- Fix: one owner, `src/copy_proxy_live.sh` in monitor-cc; both start paths call it. The iterative-dev plugin cache had to be republished before spawns worked again.
- Publishing detail: `plugin-publish` refuses a dirty tree, and the iterative-dev main checkout carried another session's uncommitted `skills/iterative-dev-refactor/SKILL.md`. Publishing ran from a clean detached worktree of `integration` (`/tmp/s0925/idpub`, `plugin-publish --no-push`), with user consent, because it also made that session's merged commits live.
- Second verification passed: a real spawn wrote the new live layout and all five dual-log files.

## Live verifications done

- Applyblitz: user clicked Apply at 14:55; `model_selection.json` written, no `apply success flash failed` line in `menubar.log` after the rebuild with `setup_py2app.py`.
- Proxy timestamps: a real worker proxy wrote `timestamp` values like `2026-09-25T14:02:29.429317+00:00`, parsed by `fromisoformat`.
- Hooks run live from the main checkout: `dev/hook_smoke/run_all.py` 23/23 on the merged tree.

## Other session in the same repos

A second Main session (workers `itdevpath`, `itdevspawn`, `redditgarbage`, `wcli`, registered under monitor-cc) merged into iterative-dev `integration` while this session worked. Its commits rewrote `dev/model_selector/verify_worker_model_precedence.sh`; `idwin` had to merge integration and re-verify. Check `git log <branch>..integration` before merging any worker of a repo that another session also touches.
