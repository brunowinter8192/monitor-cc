# Menubar Worker — cwd Subdir-Drift Bug (2026-05-28)

## Symptom

A worker whose Claude Code tmux session is alive disappears entirely from the menubar session
panel. Its row is not shown at all (not merely shown with wrong status). A downstream effect is
that the per-project auto-abort of Opus background sleep-timers stops firing for the affected
project — the timer runs to full expiry instead of being aborted when workers go idle.

See also: `decisions/OldThemes/menubar_focus_cwd_drift.md` — the same JSONL cwd-drift root
cause previously fixed for **main** sessions (there the consequence was wrong display name +
broken hotkey focus; fix was `_proc_cwd_for_encoded_dir` in the main-session branch). Workers
cannot use that fix because they have no stable OS process cwd to fall back on; the fix here
is instead to extract the stable part of the JSONL cwd itself.

## Diagnostic Data

Worker `jhao104-probe` in worktree
`/Users/.../searxng-cli/.claude/worktrees/jhao104-probe`, tmux session
`worker-searxng-cli-jhao104-probe`. Its JSONL `cwd` field across entries:

| cwd | count |
|---|---|
| `.../searxng-cli/.claude/worktrees/jhao104-probe` | 91 |
| `.../searxng-cli/.claude/worktrees/jhao104-probe/dev/news_pipeline/theblock/jhao104/upstream` | 132 |
| `.../searxng-cli/.claude/worktrees/jhao104-probe/dev/news_pipeline/theblock/jhao104` | 34 |
| `.../searxng-cli/.claude/worktrees/jhao104-probe/dev/news_pipeline/theblock` | 26 |

Most-recent (last) cwd: `.../theblock` — deepest subdir.

## Root Cause

`src/menubar/discover.py`, **line 143** (pre-fix), worker branch of `_process_project_dir`:

```python
display_name = os.path.basename(cwd)   # BUG: yields subdir name when cwd drifts
```

`_cwd_from_jsonl` returns the most-recent non-empty `cwd` from the JSONL tail — which, after the
worker executed Bash `cd dev/news_pipeline/theblock`, is
`.../jhao104-probe/dev/news_pipeline/theblock`. `os.path.basename` of that path is `theblock`.

This `display_name` is then passed directly to `_worker_tmux_session(cwd, display_name)` at
**line 147**:

```python
# _worker_tmux_session builds: f'worker-{basename(project_path)}-{worker_name}'
tmux_session = _worker_tmux_session(cwd, display_name) or ''
# → 'worker-searxng-cli-theblock'   (WRONG — actual session is worker-searxng-cli-jhao104-probe)
```

`_tmux_session_exists('worker-searxng-cli-theblock')` returns False → `return None` → worker
dropped from `list_alive_sessions()` result.

The invariant the code assumed — `os.path.basename(cwd)` equals the worktree leaf name — holds
only when the worker has never `cd`'d into a subdirectory of its worktree.

## Auto-Abort Causal Link

`focus_controller.py:tick()` builds `workers_by_project` from the returned sessions. With the
worker absent, `workers_by_project.get(proj, [])` returns `[]`:

```python
all_idle = bool(workers) and all(...)   # bool([]) = False → all_idle = False every tick
```

`all_idle = False` → the `else` branch fires every tick:
```python
self._all_workers_idle_since_ts.pop(proj, None)   # debounce reset each tick
```

`_abort_bg_sleep_timers` is never reached. The Opus bg sleep timer runs to full expiry.

## Fix

**File:** `src/menubar/discover.py`, worker branch of `_process_project_dir`.

The stable worker name is always the **first path component immediately after `/.claude/worktrees/`**,
regardless of how deep the worker subsequently `cd`'d.

```python
# BEFORE (buggy):
display_name = os.path.basename(cwd)
project_name = os.path.basename(cwd.partition('/.claude/worktrees/')[0]) or project_name

# AFTER (fixed):
project_path, _, worktree_rest = cwd.partition('/.claude/worktrees/')
display_name = worktree_rest.split('/')[0] or worker_name
project_name = os.path.basename(project_path) or project_name
```

`worktree_rest` for the drifted cwd is `jhao104-probe/dev/news_pipeline/theblock`;
`worktree_rest.split('/')[0]` is `jhao104-probe` regardless of depth. One partition call is also
cheaper than two (the old code re-partitioned for `project_name`).

### Verification against diagnostic data

All four cwd values from the diagnostic produce the correct result post-fix:

| cwd (drifted) | OLD display_name | NEW display_name | OLD tmux | NEW tmux |
|---|---|---|---|---|
| `.../jhao104-probe` | `jhao104-probe` ✓ | `jhao104-probe` ✓ | correct | correct |
| `.../jhao104-probe/dev/.../upstream` | `upstream` ✗ | `jhao104-probe` ✓ | wrong | correct |
| `.../jhao104-probe/dev/.../jhao104` | `jhao104` ✗ | `jhao104-probe` ✓ | wrong | correct |
| `.../jhao104-probe/dev/.../theblock` | `theblock` ✗ | `jhao104-probe` ✓ | wrong | correct |

## Edge Case: Worker `cd`s Entirely Outside Its Worktree

If a worker runs e.g. `cd /tmp`, the JSONL cwd becomes `/tmp`. The condition
`if cwd and '/.claude/worktrees/' in cwd:` is **False** — falls to the `else:` branch:

```python
else:
    if now - mtime > ALIVE_WINDOW_SECS:
        return None
```

- No tmux alive check is performed.
- `display_name` stays as the encoded-dir-derived `worker_name` (lossy: underscores → hyphens).
- Worker remains visible for up to `ALIVE_WINDOW_SECS` (3600s) even if the tmux session ended.

**Decision: do NOT extend the fix to this branch.** Correctly deriving the tmux session name
from the encoded-dir `worker_name` is unreliable for worker names containing underscores (the
encoding is lossy: `_` → `-`), which is the exact bug this fix addresses. The outside-worktree
case is operationally rare; the degraded-but-not-catastrophic fallback (1h visibility, wrong
display name) is acceptable. Fixing it properly would require either a separate `lsof`/`ps`
lookup on the worker process (not available — workers are CC subprocesses without a stable PID
reference in this context) or storing the worktree name separately from the JSONL cwd.
