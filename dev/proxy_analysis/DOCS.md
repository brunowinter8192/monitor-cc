# dev/proxy_analysis/

## Role

Human-readable session summary (overview, anomaly sections, per-request timeline) over a proxy
request log. Touch this directory only if reviving support for the flat single-file log schema it
reads — see Gotchas before assuming it works against a current log.

## Public Interface

`__init__.py` is empty — no exports. Entry path: `./venv/bin/python dev/proxy_analysis/01_session_summary.py [session_id]`.

## Modules

### 01_session_summary.py (249 LOC)

**Purpose:** Prints an overview (session id, timespan, model counts), an anomalies section
(non-opus calls, cache rebuilds, compression events, input jumps over 20%), and a compact
one-line-per-request timeline for one proxy log file.
**Reads:** `src/logs/api_requests_<session_id>.jsonl` (or the most recently modified
`api_requests_*.jsonl` under `src/logs/` if no session id is given); resolves `src/logs/` via
`MONITOR_CC_ROOT`, else script-relative, else cwd-relative.
**Writes:** stdout (ANSI-colored report sections).
**Called by:** none — run manually.
**Calls out:** none (stdlib only).

---

## Gotchas

**The log schema this script expects is not produced by any current `src/` writer.** It reads a
flat JSONL file whose entries carry top-level `total_input_chars`, `diff_from_prev`,
`message_count`, and `cache_breakpoints` keys — none of these appear in `src/` as log-entry fields
(`cache_breakpoints` elsewhere in `src/proxy/addon.py` is an outgoing request-payload field, not a
log key). The current logger (`src/proxy/addon_dual_log.py`) writes the six-stream split
(`_original`/`_forwarded`/`_stripped`/`_injected`/`_response`/`_errors`) under
`src/logs/dual_log/`, not a flat `api_requests_<id>.jsonl` entry list. Running this script against
a real `src/logs/` tree will find no matching file or parse entries missing every field it reads,
printing zeros/blanks rather than raising.
