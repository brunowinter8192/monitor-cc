# dev/proxy_analysis/

## Role
Human-readable session summary (overview, anomalies, per-request timeline) over a proxy request log. Touch only to revive support for the flat single-file log schema it reads, which no current `src/` writer produces.

## Public Interface
`__init__.py` is empty; no exports. Entry path: `./venv/bin/python dev/proxy_analysis/01_session_summary.py [session_id]`.

## Flow
Reads one flat request log (or auto-discovers the newest under `src/logs/`), computes overview stats, anomaly buckets and a per-request timeline, and prints ANSI-colored sections to stdout.

## Modules

### 01_session_summary.py (251 LOC)

**Purpose:** Prints overview, anomalies and a one-line-per-request timeline for one proxy log file.
**Reads:** a flat `api_requests_<session_id>.jsonl` under `src/logs/`; the schema is obsolete (see process-docs).
**Writes:** stdout only.
**Called by:** none; run manually.
**Calls out:** none; stdlib only.

---

## State
None. All data is derived fresh from the one log file per run.
