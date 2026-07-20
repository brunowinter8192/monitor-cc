# menubar_worker_underscore_detection

## Root Cause

`encode_project_path` in `session_finder.py:70` encodes a project path to a flat `~/.claude/projects/` directory name by replacing `/`, `_`, and `.` all with `-`:

```python
encoded = path.replace('/', '-').replace('_', '-').replace('.', '-')
```

This encoding is **lossy**: `_` and `-` in the original path both become `-`. The encoded dir name cannot be reversed unambiguously.

`_classify_encoded_dir` in `discover.py` splits the encoded dir at the `--claude-worktrees-` marker to extract `worker_name`. For a worker at `.../worktrees/capture-gh_reference`, the encoded dir contains `capture-gh-reference` (underscore lost). This `worker_name` was then passed directly to:
1. `_worker_tmux_session(cwd, worker_name)` → builds `worker-github-capture-gh-reference`
2. `SessionInfo.name` → displayed in the menubar panel as `capture-gh-reference`

The real tmux session is `worker-github-capture-gh_reference` (underscore). `_tmux_session_exists` returned False → `_process_project_dir` returned None → worker invisible in the panel.

## Evidence

Concrete values from the live `capture-gh_reference` worker (github project):

| Source | Value |
|---|---|
| `~/.claude/projects/` dir | `-Users-...-github--claude-worktrees-capture-gh-reference` |
| `_classify_encoded_dir` → `worker_name` | `'capture-gh-reference'` (hyphen, lossy) |
| JSONL `cwd` field | `.../github/.claude/worktrees/capture-gh_reference` (underscore, real) |
| tmux reconstructed (lossy) | `worker-github-capture-gh-reference` → `_tmux_session_exists` = False |
| tmux real | `worker-github-capture-gh_reference` → `_tmux_session_exists` = True |

## Why hyphen-only workers are unaffected

`rag-tab` encodes to `rag-tab` (no underscore to corrupt). Round-trip is lossless for hyphen-only names. Only worker names containing `_` diverge between the encoded dir and the real worktree basename.

## Why worker-cli is unaffected

`worker-cli list` queries tmux directly via `tmux list-sessions` and pattern-matches against the real session list. It never reconstructs a tmux name from the encoded-dir path, so the encoding lossiness never enters the picture.

## Fix

In `discover.py:_process_project_dir`, when `cwd` is a valid worktree path, derive the worker name from `os.path.basename(cwd)` instead of from `_classify_encoded_dir`'s `worker_name`. The JSONL `cwd` field contains the real filesystem path — `basename` preserves underscores exactly.

```python
display_name = worker_name   # fallback: lossy encoded-dir name
if cwd and '/.claude/worktrees/' in cwd:
    display_name = os.path.basename(cwd)   # real name — underscores preserved
    tmux_session = _worker_tmux_session(cwd, display_name) or ''
```

`_worker_tmux_session` is unchanged; it already accepts `worker_name` as a parameter, so passing the real name is sufficient.

## Fallback branch (cwd unavailable)

When `_cwd_from_jsonl` returns None or the cwd does not contain `/.claude/worktrees/`, there is no tmux alive check (JSONL age guard only) and no tmux reconstruction. `display_name` stays as the lossy `worker_name`. Display is slightly wrong (hyphens instead of underscores) but this branch only applies to sessions with unreadable JONSOLs — the alive check doesn't depend on the name.

## Live test result (post-fix)

```
is_worker=True  project='github'  name='capture-gh_reference'  status=idle  tmux='worker-github-capture-gh_reference'
```

Worker now visible with real underscore name and resolved tmux session.
