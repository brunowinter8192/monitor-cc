# dev/proxy_analysis/

## Role
Human-readable session summary (overview, anomaly sections, per-request timeline) over a proxy
request log. Touch this directory only if reviving support for the flat single-file log schema it
reads — the schema is not produced by any current `src/` writer (see the module's own `**Reads:**`
line and process-docs for background).

## Public Interface
`__init__.py` is empty — no exports. Entry path: `./venv/bin/python
dev/proxy_analysis/01_session_summary.py [session_id]`.

## Flow
Reads one `api_requests_<session_id>.jsonl` file (or auto-discovers the newest under `src/logs/`)
-> computes overview stats, anomaly buckets, and a per-request timeline -> prints ANSI-colored
sections to stdout.

## Modules

### 01_session_summary.py (234 LOC)

**Purpose:** Prints an overview (session id, timespan, model counts), an anomalies section
(non-opus calls, cache rebuilds, compression events, input jumps over 20%), and a compact
one-line-per-request timeline for one proxy log file.
**Reads:** `src/logs/api_requests_<session_id>.jsonl` (or the most recently modified
`api_requests_*.jsonl` under `src/logs/` if no session id is given); resolves `src/logs/` via
`MONITOR_CC_ROOT`, else script-relative, else cwd-relative. Expects a flat per-entry schema
(`total_input_chars`/`diff_from_prev`/`message_count`/`cache_breakpoints`) that no current `src/`
writer produces — `src/proxy/addon_dual_log.py` writes the six-stream dual-log split instead.
**Writes:** stdout (ANSI-colored report sections).
**Called by:** none — run manually.
**Calls out:** none (stdlib only).

---

## State
No persistent state — all data is derived fresh from the one log file read per invocation.
