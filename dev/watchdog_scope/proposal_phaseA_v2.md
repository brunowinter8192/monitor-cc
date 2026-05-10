# Watchdog-Scope Phase A v2 Proposal — Box Architecture

Retained from v1: IST analysis (file structure, SERVERS dict, rag-locks state, GPU pane contract,
empirical disqualification of ESTABLISHED-connection-count and HTTP-poll-latency as idle sources).

## IST Summary

### server_manager.py — key structures

`SERVERS` dict: `server_manager.py:34-70` — three fixed entries (`embedding`, `reranker`, `splade`).
Each entry: `port`, `health_url`, `cmd[]`, `timeout`, `required_for[]`. Splade is uvicorn, not llama-server.

`start()`: `server_manager.py:90-127` — `subprocess.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)`.
No log file. After health confirmed, returns — no state file written.

`stop()`: `server_manager.py:131-161` — finds PIDs via `lsof -ti :PORT`, SIGTERM → SIGKILL. No state file cleanup.

`touch_timestamp(name)`: `server_manager.py:255-258` — writes `~/.rag-locks/rag-server-{name}-last-used`.
Only called from `ensure_ready()`, only for SERVERS-registered names.

`_watchdog_loop()`: `server_manager.py:291-304` — `for name, cfg in SERVERS.items()` (hardcoded).
Reads `get_last_used(name)` → file mtime as idle signal. Currently dead for all three servers
(reranker/splade last-used are from 2026-05-09 02:05, predating current session).

### rag-locks live state (probed 2026-05-10)

```
~/.rag-locks/
  rag-server-embedding.port          (PID 72409, port 61974 — non-default, started outside server_manager)
  rag-server-embedding-last-used     (float, 23:32 yesterday)
  rag-server-reranker-last-used      (float, 02:05 yesterday)
  rag-server-splade-last-used        (float, 02:05 yesterday)
  watchdog.pid
```

No state files for discovered PIDs 81881 (8090) or 91212 (8092).
No `.port` files for reranker or splade (not running in managed mode).

### GPU pane display contract

`status.py:9` — `SERVERS = ['embedding', 'reranker', 'splade']` hardcoded.
`status.py:15-39` — `all_statuses()` iterates this list only; `server_status(name)` reads
`~/.rag-locks/rag-server-{name}.port` JSON for pid+port.

`pane.py:32-98` — `run_gpu_loop()`: 2s tick, `all_statuses()` → `_render_pane()`.
`pane.py:50-53` — digit 1/2/3 mapped directly to `SERVERS[idx]` index.
`pane.py:209-228` — one row per server with `[i+1]` prefix, countdown, port, pid, RSS, button.

---

## NQ3: Log Redirection — Empirical Confirmation

**Result: DEFAULT verbosity logs per-request. No extra flags needed.**

Probed against PID 81881 (Qwen3-Embedding-0.6B, port 8090), which was started with stdout/stderr
redirected to `/private/tmp/llama-emb-0.6b.log` (confirmed via `lsof -p 81881`).

### Per-request log lines (8 lines per embedding request):
```
slot update_slots: id  0 | task N | new prompt, n_ctx_slot=2048, n_keep=0, task.n_tokens=4
slot update_slots: id  0 | task N | n_tokens=0, memory_seq_rm [0, end)
slot update_slots: id  0 | task N | prompt processing done, n_tokens=4, batch.n_tokens=4
slot      release: id  0 | task N | stop processing: n_tokens=4, truncated=0
slot get_availabl: id  0 | task -1 | selected slot by LRU, t_last=...
slot launch_slot_: id  0 | task N+1 | processing task, is_child=0
srv  update_slots: all slots are idle
srv  log_server_r: done request: POST /v1/embeddings 127.0.0.1 200
```

### Mtime update confirmed:
- `mtime before=1778359803 → after=1778370968` — changed=YES after one POST /v1/embeddings
- `lines: 1474 → 1482` — delta=8

### /health is SILENT:
- `curl /health` → lines: 1482 → 1482, delta=0. mtime unchanged.
- Critical: watchdog's own health checks do NOT falsely extend the idle clock.

### Startup output only: channels `ggml_metal_`, `llama_model_loader`, `sched_reserve`, `print_info`.
These appear only at startup, not per-request. No noise concern for mtime tracking.

### Implementation:
- `subprocess.Popen(cmd, stdout=open(log_path, 'w'), stderr=subprocess.STDOUT)` — no extra flags
- Do NOT add `--log-disable` (would suppress all per-request logging)
- Do NOT add `--log-file FNAME` (untested whether it captures `srv`/`slot` lines vs internal logger only;
  shell-level redirect confirmed to work)
- Log path convention: `RAG_ROOT/src/rag/logs/llama-port-{N}.log` for all processes (preset or arbitrary)

### Existing evidence:
PID 72409 (managed embedding, port 61974) already has `fd 1 → RAG_ROOT/src/rag/logs/llama-embedding.log`
— this server was started outside `server_manager.py`'s `start()` function (current code uses DEVNULL).
The box architecture formalizes what was already done ad-hoc.

---

## NQ1: rag-cli Command Surface — Recommendation

**Recommendation: Extend `start` with inline spec flags; add `list`; extend `stop`/`restart` with `--port`.**

### Current surface (preserved as-is for presets):
```
rag-cli server start {embedding|reranker|splade}
rag-cli server stop  {embedding|reranker|splade}
rag-cli server restart {embedding|reranker|splade}
rag-cli server status [NAME]
```

### New subcommands:
```
# Arbitrary model start (flag-based to distinguish from preset names)
rag-cli server start --model PATH --port N --mode {embedding|rerank|splade} [--name LABEL]

# Port-based stop/restart (works for any registered server, preset or arbitrary)
rag-cli server stop --port N
rag-cli server restart --port N

# List all box-managed (reads state files, not SERVERS dict)
rag-cli server list
```

### Argument parsing:
`start` dispatcher: if first arg is a known preset name → preset path. If `--model` flag present → arbitrary path.
`stop`/`restart` dispatcher: if first arg is preset name → SERVERS-dict port lookup. If `--port N` → direct.

### `--name LABEL` on arbitrary start:
Stored in the state file. Allows `rag-cli server stop emb-small` as shorthand if the user gave a name.
Without `--name`, only `--port N` works for stop/restart.

### `list` output (table from state files):
```
name              mode        port   pid     model                           idle        status
embedding         embedding   61974  72409   Qwen3-Embedding-8B-Q8_0         12m 03s     healthy
emb-small         embedding   8090   81881   Qwen3-Embedding-0.6B-Q8_0       2h 26m      healthy
rerank-small      rerank      8092   91212   qwen3-reranker-0.6b-q8_0        2h 24m      healthy
```

### Rationale:
- Presets unchanged → zero breakage for existing callers (`ensure_ready`, `pane.py` toggle, `start.sh`)
- `--model/--port/--mode` flags are unambiguous with preset names (no positional collision)
- Port is always sufficient to target a stop/restart — user doesn't need to remember arbitrary labels
- `list` replaces the GPU-pane-only visibility requirement from bead scope

### Edge cases:
- `rag-cli server start --model PATH --port 8081` where 8081 is the default EMBEDDING_PORT: box detects port
  conflict with existing state file → error, do not start a second process on the same port
- `--mode splade` for llama-server: splade is uvicorn-based, not llama-server. Box should reject
  `--mode splade` for arbitrary starts (splade start is preset-only) or handle as separate code path

---

## NQ2: State-File Format and Naming — Recommendation

**Recommendation: Always port-based filename. Write AFTER health confirmed. Unlink on clean stop or crash detection.**

### Filename:
`~/.rag-locks/server-port-{N}.json` for ALL processes (presets and arbitrary).

Why port-based:
- Port is the OS-unique runtime identifier — no two processes can share a port
- Preset port can be env-overridden at launch (72409 runs on 61974, not default 8081) — filename tracks actual port
- Watchdog can glob `server-port-*.json` and extract port from filename without parsing JSON first
- Deduplication is automatic: two state files for same port is impossible

### JSON schema:
```json
{
  "pid": 72409,
  "port": 61974,
  "model_path": "/full/path/to/Qwen3-Embedding-8B-Q8_0.gguf",
  "model_name": "Qwen3-Embedding-8B-Q8_0",
  "mode": "embedding",
  "start_time": 1747007384.123,
  "log_path": "/full/path/RAG/src/rag/logs/llama-port-61974.log",
  "name": "embedding"
}
```

`name`: preset name (`embedding`/`reranker`/`splade`) OR user-provided `--name LABEL` OR `null` for anonymous.
`log_path`: absolute path — used by watchdog for mtime check, by GPU pane for display.

### Write timing:
IMMEDIATELY after `subprocess.Popen()` returns — PID is known, state file is written before the
health-check loop starts. Rationale: prevents the watchdog tick-level purge from killing an in-flight
startup process (it would appear as an unregistered llama-server PID without an early state write).
If health-check times out, `start()`'s exception handler unlinks the state file. No `pending` flag needed.

### Cleanup story:
| Event | Action |
|---|---|
| Graceful stop (`rag-cli server stop`) | SIGTERM → 5s wait → SIGKILL → `unlink(state_file)` |
| Watchdog idle stop | SIGTERM → 5s wait → SIGKILL → `unlink(state_file)` |
| `start()` health-check timeout (RuntimeError) | Exception handler `unlink(state_file)` |
| Watchdog tick: PID dead | `unlink(state_file)` (no kill needed) |
| Watchdog tick: PID alive, port mismatch | SIGTERM the PID → `unlink(state_file)` |
| Tick purge: alive llama-server PID not in any state file | SIGTERM → 5s wait → SIGKILL |
| Tick purge: stale state file (PID dead) | `unlink(state_file)` |

### Migration: old `.port` JSON files:
`~/.rag-locks/rag-server-{name}.port` files (existing format) can coexist during migration.
`status.py` switches to reading `server-port-*.json`. Old `.port` files stop being written once
`start()` writes state files; they can be deleted manually or auto-cleaned after first migration tick.

### Edge cases:
- Two state files for same model but different ports: allowed (intentional multi-instance)
- State file exists but log_path file doesn't: `stat()` raises FileNotFoundError → watchdog skips idle check,
  does NOT stop the process (could be a legitimate startup with no requests yet). Log is created at first request.
  Actually log IS created at start (stdout open in write mode) — startup lines appear immediately.
  FileNotFoundError means the log was deleted externally. Handle: skip idle, log a warning.

---

## NQ4: Out-of-Box Purge Mechanism — Recommendation

**Recommendation: Run on EVERY watchdog tick (not just on spawn). Shared `_purge_orphans()` helper called from both first-entry and each tick.**

### When to run:
Every tick. An orphan process that starts between watchdog spawns would otherwise survive until the next
machine boot or watchdog restart. Tick-level purge enforces the box invariant continuously: any orphan
dies within ~30s (one `WATCHDOG_INTERVAL`).

Cost: one `pgrep llama-server` per tick (~2ms on macOS) + set-diff against in-memory state-file PIDs.
No kills happen unless an actual orphan exists. Acceptable overhead.

`_purge_on_startup()` as a separate function is unnecessary — the tick-level purge covers first-entry too
(it runs before the `while True: sleep()` loop).

### `_purge_orphans()` helper (pseudocode from amendment):
```python
def _purge_orphans():
    """Kill llama-server PIDs not in the state-file registry."""
    registered_pids = set()
    for state_file in TIMESTAMP_DIR.glob("server-port-*.json"):
        try:
            registered_pids.add(json.loads(state_file.read_text())["pid"])
        except (json.JSONDecodeError, FileNotFoundError, KeyError):
            continue
    live_pids = set(_pgrep_llama_server())
    orphan_pids = live_pids - registered_pids
    if not orphan_pids:
        return
    for pid in orphan_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for _ in range(10):
        time.sleep(0.5)
        still_alive = {pid for pid in orphan_pids if _pid_alive(pid)}
        if not still_alive:
            break
        orphan_pids = still_alive
    for pid in orphan_pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    logging.info(f"Watchdog purge: killed {len(live_pids - registered_pids)} orphan llama-server PIDs")
```

### Stale state file cleanup (separate from `_purge_orphans()`):
Handled per-state-file in `_watchdog_tick()`: if `os.kill(pid, 0)` raises `ProcessLookupError` →
`state_file.unlink()`. This is already in the per-state-file loop (NQ5), no separate cleanup pass.

### Port-mismatch cleanup:
Also in `_watchdog_tick()` per-file: if `lsof -ti :PORT` doesn't include the state file's PID →
SIGTERM the PID + unlink state file. Kept in tick logic, not in `_purge_orphans()`.

### Edge cases:
- pgrep returns empty: `orphan_pids` is empty, returns immediately (<1ms).
- Race: `rag-cli server start --model PATH --port N` — `subprocess.Popen` returns PID, state file is
  written IMMEDIATELY (before health-check loop). Purge running concurrently sees the state file, skips
  the PID. No race window. See NQ2 write-timing rationale.
- Watchdog crashes mid-purge after SIGTERM but before SIGKILL: next tick re-runs `_purge_orphans()`,
  issues SIGKILL to still-alive orphan. Idempotent.
- `pgrep` returns a PID that dies between `pgrep` and `os.kill`: `ProcessLookupError` is caught, skipped.

---

## NQ5: Watchdog New Logic — Recommendation

**Replace SERVERS-dict iteration with state-file glob + log-mtime idle check.**

### Pseudocode:
```python
LOG_PATH = Path(RAG_ROOT) / "src/rag/logs"

def _watchdog_loop():
    _purge_orphans()   # runs immediately on first entry; no separate _purge_on_startup needed
    while True:
        time.sleep(WATCHDOG_INTERVAL)
        _watchdog_tick()

def _watchdog_tick():
    _purge_orphans()   # continuous enforcement — orphan dies within one interval
    now = time.time()
    for state_file in TIMESTAMP_DIR.glob("server-port-*.json"):
        try:
            state = json.loads(state_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            continue

        pid   = state["pid"]
        port  = state["port"]
        label = state.get("name") or f"port-{port}"
        log   = Path(state["log_path"])

        # 1. PID liveness (crash detection)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            logging.info(f"Watchdog: {label} PID {pid} dead, cleaning state")
            state_file.unlink(missing_ok=True)
            continue

        # 2. Health check (skip idle-stop for unhealthy/starting servers)
        if not _check_health_port(port):
            continue

        # 3. Idle check via log mtime (/health requests do NOT update mtime — verified)
        try:
            idle = now - log.stat().st_mtime
        except FileNotFoundError:
            logging.warning(f"Watchdog: {label} log file missing at {log}, skipping idle check")
            continue

        if idle > IDLE_TIMEOUT:
            logging.info(f"Watchdog: {label} idle {idle:.0f}s (>{IDLE_TIMEOUT}s), stopping")
            _stop_by_state(state, state_file)

def _stop_by_state(state: dict, state_file: Path) -> None:
    pid, port = state["pid"], state["port"]
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        state_file.unlink(missing_ok=True)
        return
    for _ in range(10):
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            state_file.unlink(missing_ok=True)
            return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    state_file.unlink(missing_ok=True)

def _check_health_port(port: int) -> bool:
    # Same logic as check_health() but port-based, no SERVERS lookup
    try:
        resp = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False
```

### Health check rationale:
Kept. `/health` is silent in logs (confirmed) so it does NOT refresh idle clock. It serves as a guard
against stopping a process that's mid-startup (health returns non-200 until ready). Also catches zombies
that hold the port without serving. Health-fail → skip idle stop → process will either recover or the
user stops it manually.

### Crash recovery:
State files are the persistent layer. After watchdog restart:
- `_purge_orphans()` runs immediately on `_watchdog_loop()` first entry — cleans orphans (rogue processes)
  and stale state files (PID dead) in the per-file loop
- `_watchdog_tick()` resumes normal idle monitoring for remaining state files
- No in-memory state to restore — everything is re-read from disk each tick
- Fully correct after restart, no special handling needed

### Removal of old mechanism:
`get_last_used(name)` and `touch_timestamp(name)` become dead code in the watchdog path.
They can be kept for the migration period (GPU pane `_format_countdown` still reads them during
migration) and removed in cleanup phase.

---

## NQ6: Migration Path — Recommendation

**Recommendation: Incremental, four independent phases. No big-bang.**

Rationale: big-bang changes SERVERS-dict iteration everywhere simultaneously. Any regression leaves
the system in a mixed state where some callers use state files and others don't. Incremental phases
are each independently deployable and rollback-safe.

### Phase order:

**Phase 1 — State-file plumbing in server_manager.py** (foundation, required before anything else):
- Add `_write_state_file(pid, port, model_path, model_name, mode, name, log_path)` — writes `server-port-{N}.json`
- Add `_unlink_state_file(port)` — deletes state file
- Modify `start()`: change `stdout=DEVNULL → stdout=open(log_path, 'w'), stderr=STDOUT`; call `_write_state_file()` after health confirmed
- Modify `stop()`: call `_unlink_state_file(port)` after kill
- SERVERS dict stays unchanged — still used for cmd templates and `required_for` lookup
- Old `touch_timestamp()` / `get_last_used()` stay, called in parallel (GPU pane still reads them during migration)

**Phase 2 — Watchdog switch** (depends on Phase 1 state files existing):
- Replace `_watchdog_loop()` body with state-file glob + log-mtime logic (pseudocode above)
- Add `_purge_on_startup()` called once at watchdog start
- Add `_check_health_port(port)`, `_stop_by_state(state, state_file)`
- `watchdog_main.py` unchanged (still calls `_watchdog_loop()`)
- Old `get_last_used()` no longer called from watchdog; stays in file for GPU pane countdown

**Phase 3 — CLI extension** (depends on Phase 1; parallel with Phase 2):
- Add `start_arbitrary(model_path, port, mode, name=None)` in `server_manager.py` — same flow as `start()`
  but without SERVERS lookup; writes state file
- Extend `cli_server()` in `workflow.py` to parse `start --model/--port/--mode/--name`, `stop --port`, `list`
- `list` reads `server-port-*.json` files, prints table
- Existing `start NAME` / `stop NAME` path unchanged

**Phase 4 — GPU pane switch** (depends on Phase 1; parallel with Phases 2+3):
- Add `state_file_statuses() -> list[dict]` in `gpu_pane/status.py` — globs `server-port-*.json`,
  reads pid+port+model_name+mode+log_path, adds `rss_mb` + `healthy` per entry
- Remove hardcoded `SERVERS = [...]` from `status.py`; `all_statuses()` calls `state_file_statuses()`
- Update `pane.py`: remove fixed digit-key 1/2/3 mapping; add dynamic index by sorted port order;
  `_format_countdown()` switches from `get_last_used(name)` to log-mtime idle computation;
  variable-length server list handled in render loop
- `pane.py` `_toggle_server()` / `_fire_button()` work by state-file `name` or port, not SERVERS index

**Phase 5 — Cleanup** (after all four phases deployed and stable):
- Remove `touch_timestamp()`, `get_last_used()`, old `rag-server-{name}.port` JSON writes
- Remove old `rag-server-{name}-last-used` files from `~/.rag-locks/`
- Remove `check_health(name)` (replaced by `_check_health_port(port)`)
- Update DOCS.md (server_manager, gpu_pane, watchdog)

### Parallelizable in Phase B:
- Phase 2 + Phase 3 can be parallel workers (watchdog and CLI extension don't touch the same code)
- Phase 4 can start as soon as Phase 1 is merged (state files exist to read)
- Phase 1 is a dependency for all others — do it first, solo

---

## Additional Concerns

1. **Splade is NOT a special case.** `splade_server.py:47` — `logging.info(f"Encoded {len(req.input)} texts")`
   fires on every POST `/v1/sparse-embeddings`. `logging.basicConfig(filename=LOG_DIR / "splade_server.log", ...)`
   at `splade_server.py:13-17` routes all log output to `RAG_ROOT/src/rag/logs/splade_server.log`.
   The `/health` endpoint (`splade_server.py:36-37`) has no `logging.info()` call — silent, same as llama-server.
   Mtime tracking via `splade_server.log` works identically. No `idle_source` field needed in the schema.
   State file for splade: `log_path = RAG_ROOT/src/rag/logs/splade_server.log` (existing file written by
   Python's `logging` module — do NOT redirect uvicorn's stdout/stderr; the log is already being written).
   Live mtime-update probe deferred to Phase B — splade not running at time of this analysis.
   Purge implication: `_purge_orphans()` uses `pgrep llama-server` — does NOT find splade (uvicorn process).
   Splade is always box-managed (state file written by `rag-cli server start splade`), so the state-file
   glob covers it for idle tracking. Rogue uvicorn instances outside the box are out of scope for purge.

2. **Log rotation / log growth.** Llama-server logs grow unbounded (1474 lines observed for ~363 requests).
   At high throughput, logs can grow large. Recommend: add `LLAMA_LOG_MAX_MB` env var, watchdog
   rotates log at each tick if size exceeds limit (rename → `.1`, create fresh). Mtime of the fresh
   file starts at 0 — handle gracefully: if log is empty AND server is healthy, treat as startup
   (not idle). This is a Phase 5 concern, not Phase B.

3. **GPU pane digit-key UX change.** Removing fixed 1/2/3 keys breaks existing muscle memory.
   Mitigation: dynamic keys still start at 1 (sorted by port), just the count may exceed 3.
   Document in footer. Not blocking Phase B.

4. **`_ensure_watchdog_process()` is called from `ensure_ready()`, which is called on every RAG request.**
   The watchdog check (PID liveness via `os.kill(pid, 0)`) adds ~1ms per request. Acceptable.
   `_purge_orphans()` now runs every tick (~30s), not startup-only. Cost: one `pgrep llama-server` (~2ms)
   + set-diff. No kills unless an orphan exists. Per-request cost is unchanged (watchdog PID check only).

---

## Phase B Sketch

1. **`RAG/src/rag/server_manager.py`** — Phase 1: `_write_state_file()`, `_unlink_state_file()`,
   modify `start()` (log redirect + immediate state write + exception handler unlink), modify `stop()` (state unlink).
   Phase 2: new `_watchdog_loop()`, `_purge_orphans()`, `_check_health_port()`, `_stop_by_state()`.
   Phase 3: `start_arbitrary()`, extend `cli_server()` with new subcommands.

2. **`RAG/src/rag/watchdog_main.py`** — unchanged (still calls `_watchdog_loop()`).

3. **`Monitor_CC/src/gpu_pane/status.py`** — Phase 4: replace `SERVERS = [...]` + port-file reads
   with `state_file_statuses()` that reads `server-port-*.json`.

4. **`Monitor_CC/src/gpu_pane/pane.py`** — Phase 4: dynamic server list, log-mtime countdown,
   PID-based stop dispatch, updated footer.

5. **`Monitor_CC/src/gpu_pane/DOCS.md`** — update Role, Flow, Modules LOC after Phases 1+4.

Order: Phase 1 solo → Phases 2+3 parallel → Phase 4 → Phase 5 cleanup.
