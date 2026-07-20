# Watchdog Idle Detection — State-File mtime Switch

## Failure Mode 1: SPLADE /health Pollution

SPLADE runs under uvicorn, which logs every HTTP request to `splade_server.log` — including the watchdog's own `/health` probes fired every 30 seconds. This keeps `splade_server.log` mtime perpetually fresh (within ~30s), so the idle counter never grows past the probe interval. SPLADE therefore never triggers the auto-stop path regardless of how long it sits idle between real client requests. By contrast, llama-server filters `/health` from its stdout entirely, so the log-mtime approach worked correctly for embedding and reranker servers — the bug was SPLADE-specific but latent for any future server type that logs health probes.

## Failure Mode 2: RAG-bdt Stale log_path

State files written before the `LOG_DIR` path fix carried `log_path` entries pointing into worker-worktree directories that were subsequently deleted. On every watchdog tick, `Path(state["log_path"]).stat()` raised `FileNotFoundError`; the watchdog logged a WARNING and skipped the idle check with `continue` — the server ran indefinitely. This class was not active on disk at fix time but would recur whenever a state file outlived its worktree's log directory.

## Architectural Decision: State-File mtime as Idle Anchor

The fix moves the idle clock from log-file mtime to the state-file's own mtime (`~/.rag-locks/server-port-{N}.json`). Client modules (embedder, sparse_embedder, reranker) call `_touch_state_file(port)` immediately before each `httpx.post` inference request, bumping the state-file mtime. The watchdog reads `state_file.stat().st_mtime` directly from the `pathlib.Path` object it already holds during iteration — no new path resolution needed. Touch happens before the request (not after) so that even a failed inference attempt counts as real activity: the server was contacted and load was exercised.

## Why State-File is the Right Anchor

Three properties make the state file uniquely suited as the idle source:

1. **Lifecycle-stable location.** State files live under `~/.rag-locks/`, independent of which worktree spawned the server. They survive worktree cleanup by design — the same guarantee that LOG_DIR provides for log files, but without requiring any new path.

2. **/health immunity.** Watchdog probes call `_check_health_port` which calls `httpx.get(.../health)` — a pure network call that never touches the filesystem. State-file mtime is updated only by `_write_state_file` (on start), `_touch_state_file` (on real client request), and `_stop_by_state`/`_unlink_state_file` (on stop/unlink). The polling loop cannot inflate the idle timer.

3. **Eliminates the FileNotFoundError class.** The watchdog already holds a valid `pathlib.Path` for each state file it just read; `state_file.stat().st_mtime` cannot raise `FileNotFoundError` unless the watchdog itself unlinked the file earlier in the same tick — which can't happen since the dead-PID check exits via `continue` before reaching the idle block. The entire `except FileNotFoundError: ... continue` branch is removed.

## Cross-Project Symmetry

Monitor_CC's GPU pane (`status.py:_log_idle`) previously read the same log-path mtime for the idle countdown display. The parallel fix — renaming `_log_idle` → `_state_file_idle` and switching to state-file mtime — was implemented on Monitor_CC branch `watchdog-idle-state-mtime` (commit `161e7d6`) synchronously with this RAG worker change. Both branches are merged together so the idle source is consistent across the watchdog stop path (RAG) and the display path (Monitor_CC).
