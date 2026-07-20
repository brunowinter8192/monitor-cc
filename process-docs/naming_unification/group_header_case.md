# Group Header Case Mismatch (Monitor-CC → monitor-cc)

## Symptom

Menubar group header showed `Monitor-CC`; session row below showed `monitor-cc`. Projects never
renamed (e.g. `gh-cli`) showed header and row consistently.

## Root Cause

`_classify_encoded_dir()` → `_decode_dir_name()` was the sole source of `project_name` for both
mains and workers. The encoded dir (`~/.claude/projects/-Users-…-Monitor-CC`) retained the case
from when the project was first registered with Claude. macOS's case-insensitive filesystem never
physically renamed this directory when the project was renamed `Monitor_CC` → `monitor-cc`.
`_decode_dir_name` reassembled `Monitor-CC` from the stale encoded path parts:

```
parts = ['Users', '…', 'ai', 'Monitor', 'CC']
len('CC') == 2 ≤ 4 and len(parts) ≥ 2  →  "Monitor-CC"
```

The session row name (`SessionInfo.name`) derives independently from `os.path.basename(proc_cwd)`
(mains) / `os.path.basename(cwd)` (workers) — both reflect the actual live filesystem path →
`monitor-cc`. Hence the discrepancy.

## Fix (`src/menubar/discover.py`, commit c4f7ff5)

`project_name` now derives from the live cwd basename:

**Mains** — after `proc_cwd` confirmed non-None:
```python
project_name = os.path.basename(proc_cwd.rstrip('/'))
```

**Workers** — inside `if cwd and '/.claude/worktrees/' in cwd:`:
```python
project_name = os.path.basename(cwd.partition('/.claude/worktrees/')[0]) or project_name
```

**Worker fallback** (cwd unreadable from JSONL): `project_name` from `_classify_encoded_dir` /
`_decode_dir_name` preserved as last resort — no tmux check occurs in this branch so stale case
is moot for aliveness logic.

Main + worker now produce the same `project_name` for the same project → `groupby` keeps them
together under the correct header.

## Proxy Writer as Authoritative Source

`src/claude_proxy_start.sh` lines 36–37:
```bash
PROJECT_BASENAME="$(basename "$PROJECT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '_' | sed 's/^_*//;s/_*$//')"
LOG_ID="opus_${PROJECT_BASENAME}_$(date +%s)"
```

`discover.py` line 197: `project_key = project_name.lower().replace('-', '_').replace(' ', '_')`

For `monitor-cc`: both paths produce `monitor_cc`. The `.lower()` in the proxy_key derivation
neutralised the capitalisation difference pre-fix; post-fix the key is still `monitor_cc` —
**unchanged**.

## Bonus: Latent Nested-Path Misalignment Eliminated

`_decode_dir_name` two-part heuristic: last part ≤ 4 chars → `penultimate-last`. For a path
`…/Meta/ClaudeCode/MCP/RAG`, decode gave `MCP-RAG` while `basename(live_cwd)` gives `RAG`.
Under the old scheme the group header read `MCP-RAG` while the row and tmux session name used
`RAG` (different decoded vs live-basename values). The fix produces `RAG` for both — consistent
header, row, and grouping for any project whose live cwd is readable.
