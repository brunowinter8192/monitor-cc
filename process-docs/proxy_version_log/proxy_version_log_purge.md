# Proxy Version-Aware Dual-Log Purge

2026-06-09. The proxy-start janitor (`claude_proxy_start.sh`) now purges stale
dual-logs of a PREVIOUS proxy version on a version change, so a fix-restart no longer leaves
old-version renderings in the proxy pane (which caused false "fix failed" conclusions).

## Problem

Dual-logs (`src/logs/dual_log/api_requests_<id>_<suffix>.jsonl`) drive the proxy/worker panes. They
were rotated ONLY count-30 (per opus/worker class) by `_janitor_cleanup_jsonl_logs`. After a proxy
CODE fix + restart, up to 30 old-version logs survived alongside the new ones → the pane read them →
pre-fix renderings → false conclusion the fix failed. (Not the time-based `cleanup_old_jsonl` path —
that only handles hook_firing / api_errors / polling_state.)

## Design (implemented)

Additive Phase 0 in `_janitor_cleanup_jsonl_logs`, before the count-30 rotation:
1. Content-hash the live-copied proxy source: `proxy_addon.py` + `proxy/**/*.py` + `proxy/**/*.json`
   (sort-stable). Marker `dual_log/.proxy_version` = last-seen hash.
2. On hash != marker (or marker absent = first run): delete dual-logs not modified in the last 60min
   (`find -mmin +60`); write the new hash.

## Decisions

**Hash scope = `proxy_addon.py` + `proxy/`** (exactly the live-copied set, what actually runs). Start
script EXCLUDED (orchestration, not request-processing; tweaking the janitor itself shouldn't purge).
`.json` schemas INCLUDED (`proxy/schemas/github-research/*.json` = injected tool definitions =
behavioral; a schema change alters the forwarded payload). `__pycache__/*.pyc`, `DOCS.md`, `.DS_Store`
EXCLUDED (recompile noise / docs — would trigger false version changes).

**Live-session protection = the 60min-mtime rule IS the mechanism, not a fallback** (user, 2026-06-09:
"clear all logs except ones with an entry < 60min"). A running session writes its logs
continuously → fresh mtime → survives the purge even on a version change; a session idle > 60min is
treated as dead. Rejected the deterministic alternative (pgrep + `ps`-env mapping of running
mitmdumps): fragile macOS `ps`-parsing, and any crash-safe liveness signal (sentinel/marker) needs a
time-fallback anyway because a crashed process leaves no clean signal — so the time rule is the
simplest crash-safe option, not a compromise.

**No addon change** — pure `claude_proxy_start.sh`. **First-run auto-cleanup** — an absent marker is
treated as a change, so the very first version-aware restart purges the pre-existing stale logs; no
manual deletion.

## Status

Implemented in `claude_proxy_start.sh` (`_compute_proxy_hash` + `_janitor_version_purge_jsonl_logs`).
Smoke: `dev/hook_smoke/test_version_purge.sh` (4 cases, 8/8). Documented in the logging
current-state docs (Trigger 1 / Phase 0). LIVE-VERIFY pending — requires a real proxy code change + restart.
