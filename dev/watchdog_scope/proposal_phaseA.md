# Watchdog-Scope Phase A Proposal

## IST Summary

### SERVERS dict — `server_manager.py:34-70`
Three fixed entries: `embedding` (port 8081 default / 61974 live), `reranker` (8082), `splade` (8083).
Each entry: `port`, `health_url`, `cmd[]`, `timeout`, `required_for[]`. Splade is uvicorn, not llama-server.

### Timestamp mechanism — `server_manager.py:255-266`
- `touch_timestamp(name)` — writes `~/.rag-locks/rag-server-{name}-last-used` (float epoch string)
- `get_last_used(name)` — reads same file, returns 0.0 if missing
- Called exclusively from `ensure_ready()` (line 197, 215) — only managed servers in SERVERS get touched

### Watchdog loop — `server_manager.py:291-304`
```
_watchdog_loop():
  while True:
    sleep(30)
    for name, cfg in SERVERS.items():   ← hardcoded iteration
      if not check_health(name): continue
      last_used = get_last_used(name)
      if last_used == 0: continue
      if now - last_used > IDLE_TIMEOUT:
        stop(name)
```
One-off processes: invisible to this loop, never stopped, never logged.

### rag-locks state (live)
```
~/.rag-locks/
  rag-server-embedding.port          (PID 72409, port 61974)
  rag-server-embedding-last-used     (float, written 23:32)
  rag-server-reranker-last-used      (float, last write 02:05 yesterday)
  rag-server-splade-last-used        (float, last write 02:05 yesterday)
  watchdog.pid
```
No `.port` files for discovered PIDs 81881 (8090) or 91212 (8092).

### GPU pane display contract

**`status.py:9`** — `SERVERS = ['embedding', 'reranker', 'splade']` — hardcoded list.
**`status.py:15-16`** — `all_statuses()` iterates only this list.
**`status.py:21-39`** — `server_status(name)`: reads `~/.rag-locks/rag-server-{name}.port` JSON →
  `{name, status, port, pid, rss_mb, healthy}`.

**`pane.py:32-98`** — `run_gpu_loop()`: 2s tick, calls `all_statuses()` → `_render_pane()`.
**`pane.py:202-254`** — `_render_pane()`: iterates `statuses` list, builds one row per server,
  digit 1/2/3 indexed directly into `SERVERS[idx]` (`pane.py:51-53`).

Current row format (visual example):
```
[1] embedding     ● running          stops in 27:18  port 61974     pid 72409       RSS 4096 MB     errors today: 0  [stop]
[2] reranker      ○ stopped                          port 8082      -               -               errors today: 0  [start]
[3] splade        ○ stopped                          port 8083      -               -               errors today: 0  [start]
```

### Live discovered processes (probe, 2026-05-10)
| PID   | Port  | Model (basename, .gguf stripped)      | Mode        | In SERVERS? |
|-------|-------|---------------------------------------|-------------|-------------|
| 72409 | 61974 | Qwen3-Embedding-8B-Q8_0               | --embedding | YES (embedding) |
| 81881 | 8090  | Qwen3-Embedding-0.6B-Q8_0             | --embedding | NO          |
| 91212 | 8092  | qwen3-reranker-0.6b-q8_0              | --rerank    | NO          |

Discovery mechanism verified: `pgrep llama-server` → `ps -o args= -p PID` → parse `--port NNN` + `-m /path`. Reliable on macOS. `lsof -i :PORT -sTCP:LISTEN` cross-validates port→PID. Model name extractable via `basename -s .gguf`.

No discovery helpers exist in `RAG/src/rag/` — new code required in both projects.

---

## Q1: Auto-Stop — Recommendation

**Recommendation: NO auto-stop for discovered processes. Visibility + manual [stop] button only.**

Rationale:
- Discovered processes were started outside the managed framework deliberately. The user knows they did it. Applying the same 1h IDLE_TIMEOUT without any touch-timestamp mechanism would kill processes that are merely quiescent (serving infrequent requests) rather than truly idle.
- `touch_timestamp()` is called from `ensure_ready()` — it only fires when the RAG Python code is the client. One-off probes started from the CLI or a test script will never call `ensure_ready()`, so their timestamp file is never written, `get_last_used()` returns 0.0, and the current watchdog already skips them (`if last_used == 0: continue`). Extending auto-stop to discovered processes would require either (a) writing a synthetic timestamp at discovery time (misleading — "last used" becomes "discovered at") or (b) a different idle mechanism (see Q3).
- Connection-count via `lsof -sTCP:ESTABLISHED` was probed live: all three servers showed 0 ESTABLISHED connections even for the actively managed embedding server. HTTP connections are transient and cannot reliably distinguish "recently used" from "truly idle" on short polling intervals.
- The user's stated requirement is **visibility** ("müssen alle erfasst werden"). Stopping is a separate concern. Visibility with manual control satisfies the requirement without risk.

Edge cases:
- A discovered process on a port that matches a SERVERS entry (e.g., user restarts embedding on 8081 manually): treated as managed, not discovered. Discovery must skip SERVERS-owned ports.
- Discovered process exits on its own: next discovery scan (pgrep) returns no PID for that port → row disappears from pane automatically.
- User wants auto-stop for a one-off: they can add it to SERVERS dict for full lifecycle management.

---

## Q2: Display Format — Recommendation

**Recommendation: Separate "discovered" section below the managed section, unified row format within each, dim section header, no digit key for discovered, [stop]-only button per discovered row.**

Rationale:
- Managed and discovered servers have different control semantics: managed have digit shortcuts + full start/stop/restart lifecycle; discovered are running-only with PID-based stop. Visual separation prevents the user from pressing `[2]` expecting "reranker" and hitting an unrelated one-off.
- When there are no discovered processes the section header is suppressed entirely → zero visual change for clean sessions.
- Uptime (`running Xh Ym`) replaces the idle countdown for discovered (no touch-timestamp → no countdown data). Shows how long the process has been alive, which is the next-best context.
- Model name (shortened) in a dedicated column gives immediate identification without the user having to know port numbers.

Example output (mock, pane_width=120):

```
════════════════════════════════════════════════════════════════  GPU Servers  ─── managed ───
[1] embedding     ● running          stops in 27:18  port 61974     pid 72409       RSS 4096 MB     errors today: 0  [stop]
[2] reranker      ○ stopped                          port 8082      -               -               errors today: 0  [start]
[3] splade        ○ stopped                          port 8083      -               -               errors today: 0  [start]

    ─── discovered ─────────────────────────────────────────────────────────────────────────────────
    llama@8090    ● running          running 2h 26m  port 8090      pid 81881       RSS 512 MB      qwen3-embedding-0.6b            [stop]
    llama@8092    ● running          running 2h 24m  port 8092      pid 91212       RSS 256 MB      qwen3-reranker-0.6b             [stop]
```

Column alignment:
- Name col: `llama@{PORT}` left-padded with 4 spaces (no `[N]` prefix), then same width as managed names (`<12`)
- Status col: `● running` — healthy badge + literal "running" (discovered can't be stopped/starting/unhealthy in the monitored sense; if PID dies the row disappears)
- Uptime col: same width slot as countdown col
- Port, PID, RSS: same widths as managed
- Model col: new rightmost content col before the button; truncated to available width
- Button: `[stop]` only; fires PID-based SIGTERM (not rag-cli)

Footer hint line updated: `[1/2/3] toggle managed  click [start]/[stop]/[restart]  [stop] on discovered = SIGTERM`

---

## Q3: Idle Source — Recommendation

**Recommendation: No idle tracking for discovered processes. Display process uptime (`ps -o lstart=`) instead of a countdown.**

Rationale:
- HTTP-health-poll latency: polling the health endpoint ITSELF constitutes usage from the server's perspective — any poll-based idle mechanism is self-defeating. Rejected.
- `lsof -sTCP:ESTABLISHED` (active connections): probed live — all three live llama-server instances showed 0 ESTABLISHED connections right now, including the actively managed embedding server that had `touch_timestamp` called recently. HTTP/1.1 connections to llama.cpp are too short-lived for connection-count to be a meaningful idle proxy. Rejected.
- TTY-mtime / log-file-mtime: llama-server writes no predictable per-instance log file to a discoverable path. Its stdout/stderr are redirected to DEVNULL in managed starts; one-off starts vary. Not reliable without per-launch log file knowledge. Rejected.
- Process start-time (`ps -o lstart=`): reliable on macOS, no additional mechanism needed, truthful (we know when it started, not when it was last used). Displayed as "running Xh Ym". The user can infer from context whether a process launched 6h ago is still useful.

Q1 and Q3 are coupled: since Q1 recommends no auto-stop for discovered, the idle tracking question reduces to "what do we show in the countdown column?" Process uptime is the honest and implementable answer.

Edge cases:
- Discovered process that handled a request 30 seconds ago: uptime shows "running 3h 42m" — no indication of recent use. Accepted limitation, noted in the pane footer or a tooltip-equivalent.
- Discovered process on port 8080 (non-llama, e.g. a dev HTTP server): `pgrep llama-server` won't find it; not an issue for this feature scope. Discovery is llama-server-binary-specific.
- macOS `ps -o lstart=` format is locale-dependent (day Mon DD HH:MM:SS YYYY); parse with `datetime.strptime` with the standard C locale format.

---

## Additional Concerns

1. **Port collision: discovered vs managed.** PID 72409 runs on port 61974 (not the default EMBEDDING_PORT 8081 — it was started with a custom port override). Discovery would find it as a "discovered" process unless we cross-reference by binary cmdline args matching the SERVERS `cmd[]` lists, OR by matching port against SERVERS ports. Recommended: match by port — simpler, port is the stable identifier. If the user overrides the port at runtime, the managed entry still wins by port. If they override to a completely new port (like 61974), that instance would show in "discovered" even though it IS the managed embedding server. Flag: Phase B should check whether the process's `-m` model path matches a SERVERS entry's cmd model path as a secondary deduplication key.

2. **[stop] for discovered needs new stop path.** `rag-cli server stop <name>` requires a SERVERS-registered name. Discovered processes have no name in rag-cli. Phase B must add a PID-kill path in `pane.py` (e.g., `os.kill(pid, signal.SIGTERM)` directly, or `kill -15 PID` via subprocess). The `_fire_button` / `_button_regions` dict currently stores `(action, server_name)`. For discovered, needs `(action, pid)` or a separate dispatch path.

3. **Digit key N for discovered.** Currently `pane.py:51-53` uses `SERVERS[idx]` for digit keys. If discovered processes are rendered after managed rows, digit 4/5/6... would be natural — but the count is dynamic. Recommend: no digit keys for discovered rows. Click-only.

---

## Phase B Sketch

1. **`RAG/src/rag/server_manager.py`** — Add `discover_llama_processes() -> list[dict]`: runs `pgrep llama-server`, reads `ps -o args= -p PID` per PID, parses `--port` and `-m` from cmdline, skips ports in `SERVERS`, returns list of `{pid, port, model_name, start_time, kind: "discovered"}`. No watchdog changes (Q1: no auto-stop).

2. **`Monitor_CC/src/gpu_pane/status.py`** — Add `discovered_statuses() -> list[dict]`: same discovery logic as above (duplicated, no cross-project import), adds `rss_mb` via `_read_rss_mb(pid)` and `healthy` via `_check_health(port)`, returns list ready for `_render_pane`. Extend `SERVERS` concept to a separate `_DISCOVERED_SERVERS` module-level cache (reset each tick, not persisted).

3. **`Monitor_CC/src/gpu_pane/pane.py`** — (a) Call `discovered_statuses()` in the tick loop alongside `all_statuses()`. (b) Extend `_render_pane(...)` signature to accept `discovered: list`. (c) Add "discovered" section block: dim header, uptime column, `[stop]`-only button mapped to `('kill', pid)` action in `_button_regions`. (d) Add `_uptime_str(start_time_str) -> str` helper. (e) Add `_kill_pid(pid)` for the discovered [stop] action path. `_toggle_state` not needed for discovered (no "starting" state — we don't restart them).

4. **`Monitor_CC/src/gpu_pane/DOCS.md`** — Update Role, Flow (new step: `discovered_statuses()` each tick), Modules (LOC update), State (no new globals needed beyond `discovered: list` as a local in `run_gpu_loop`).
