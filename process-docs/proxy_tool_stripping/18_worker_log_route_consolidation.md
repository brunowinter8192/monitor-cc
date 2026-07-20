# Worker Log Route Consolidation

Continuation of the main-log-elimination entry in this area. That entry documented the Stage-3
elimination of the main-log write path. This file documents the corresponding read-side cleanup:
collapsing `find_worker_proxy_log` from three routes to one.

## Context

`find_worker_proxy_log(worker_name, project_filter)` in `src/proxy_display/parser.py` (pre-change
lines 29–61) resolved a worker's proxy log through three successive globs:

- **Route 1 (lines 36–42):** `dual_log/api_requests_worker_{project_session_id}_{worker_name}_*_forwarded.jsonl`
- **Route 2 (lines 43–49, "Unprefixed forwarded fallback"):** `dual_log/api_requests_worker_{worker_name}_*_forwarded.jsonl`
- **Route 3 (lines 50–61, "Legacy fallback"):** `logs/` top-level, `api_requests_worker_{...}*.jsonl`

## Route-Liveness Analysis

### session_id Semantics (decisive question)

Source: `tmux_spawn.sh` (iterative-dev plugin), `_worker_proxy_setup()` lines 393–422.

```bash
local proxy_project_path="$project_path"
if [[ "$project_path" == */.claude/worktrees/* ]]; then
    proxy_project_path="${project_path%%/.claude/worktrees/*}"   # strip worktree suffix → project root
fi
proxy_session_id=$(echo -n "$proxy_project_path" | md5 | head -c 8)
local worker_log_id="worker_${proxy_session_id}_${name}_$(date +%s)"
```

The `session_id` in `worker_{session_id}_{name}_{ts}` filenames is **md5(monitored project root
path)[:8]** — identical formula to `_proxy_session_id_for_project(project_filter)` in `parser.py:22`.
Not the worker's own worktree hash. Not a per-run session id. Stable per monitored project.

### Route 1 — PRIMARY

- Read-side glob: `dual_log/api_requests_worker_{md5(project_filter)[:8]}_{name}_*_forwarded.jsonl`
- Write-side output: `worker_${md5(project_root)[:8]}_${name}_$(date +%s)` (`tmux_spawn.sh:422`)
- Both computations are identical (same input, same algorithm, same truncation)
- On-disk confirmation: all current files are session_id-prefixed, e.g.:
  - `api_requests_worker_25c51a2e_badge-fix_1781031838_forwarded.jsonl`
  - `api_requests_worker_25c51a2e_route-consol_1781035256_forwarded.jsonl`
  - `api_requests_worker_1dda1c81_litconform_1781030793_forwarded.jsonl`

Route 1 matches every file the write path currently produces. **PRIMARY.**

### Route 2 — (a) DEAD

- Glob: `dual_log/api_requests_worker_{worker_name}_*_forwarded.jsonl` (no session_id prefix)
- The write side (`tmux_spawn.sh:422`) unconditionally injects `proxy_session_id` — there is no
  code path that produces an unprefixed `worker_{name}_{ts}` filename.
- On-disk: zero unprefixed worker files exist in `dual_log/`.
- **Classification: (a) DEAD. Safe to remove.**

### Route 3 — (a) DEAD

- Glob: `logs/` top-level, `api_requests_worker_{...}*.jsonl`
- Write side (`addon.py:_resolve_dual_log_file`, line 319) always writes to `logs/dual_log/`.
  Stage 3 (documented in the main-log-elimination entry in this area) removed the top-level main-log write path entirely.
- On-disk: `ls src/logs/api_requests_worker_*.jsonl` → no matches. Zero top-level worker files.
- **Classification: (a) DEAD. Safe to remove.**

### Caller Gating Confirmation

`worker_proxy_pane.py` lines 283–324:

```python
_worker_proxy_workers = list_workers(monitor.active_project_filter) if monitor.active_project_filter else []
if not _worker_proxy_workers:
    worker_name = None
...
if worker_name:
    log_path = find_worker_proxy_log(worker_name, monitor.active_project_filter)
```

Double gate: empty `active_project_filter` → `_worker_proxy_workers = []` → `worker_name = None`
→ `if worker_name:` is False. `find_worker_proxy_log` is **never** called with `project_filter`
absent or empty. Route 1's `if not project_filter: return None` guard is defensive only.

## Change Made

Collapsed `find_worker_proxy_log` from 33 LOC (lines 29–61) to 15 LOC. Removed Routes 2 and 3.
Single deterministic route: glob `dual_log/api_requests_worker_{session_id}_{name}_*_forwarded.jsonl`,
return None on no match. `parser.py` 530 → 512 LOC.

No behavior change for callers: Route 1 was always the path that fired under live conditions.
Routes 2 and 3 were unreachable dead code post-Stage-3.

## Files Touched

- `src/proxy_display/parser.py` — `find_worker_proxy_log` collapsed to single route
- `src/proxy_display/DOCS.md` — Public Interface (line ~23) and parser.py module description
  (line ~74) updated to reflect single-route behavior; fallback references removed
