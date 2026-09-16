# dev/proxy_dual_log/main_log_elimination_probe/

## Role
Feasibility probe on eliminating the main proxy log in favor of the dual-log quartet. One unit of
`dev/proxy_dual_log/` (see the area's own DOCS.md); split out because its 5 files import only each
other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/main_log_elimination_probe/main_log_elimination_probe.py [session]`.

## Flow
A dual-log quartet plus the corresponding flat main proxy log for one session are loaded;
Question A asks whether forwarded-reconstruction matches the main-log payload, Question B whether
`is_error` tool_result extraction matches `tool_errors.jsonl`; both answers are written to one
dated Markdown report.

## Modules

### main_log_elimination_probe.py (45 LOC)

**Purpose:** CLI entry point for the feasibility probe on eliminating the main proxy log in favor
of the dual-log quartet.
**Reads:** a dual-log quartet plus the corresponding main proxy log for one session.
**Writes:** `main_log_elimination_probe_reports/<date>.md` (the reports directory stays at the
area root, `dev/proxy_dual_log/`, not in this subfolder).
**Called by:** none — manual, one-off feasibility probe.
**Calls out:** `main_log_elimination_io.py`, `_questions.py`, `_report.py`.

---

### main_log_elimination_io.py (63 LOC)

**Purpose:** Project-root/log-path resolution, required-file existence check, and JSONL loaders.
**Reads:** `MONITOR_CC_ROOT` env var or an area-root-relative fallback; log files on disk.
**Writes:** nothing — exits 1 via `_check_paths` if a required log is missing.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** none.

---

### main_log_elimination_reconstruct.py (143 LOC)

**Purpose:** Delta-chain reconstruction, cache_control-aware element normalization/comparison, and
raw_payload field classification tables.
**Reads:** nothing — pure data transforms over passed-in entries.
**Writes:** nothing.
**Called by:** `main_log_elimination_questions.py`, `_report.py`.
**Calls out:** none.

---

### main_log_elimination_questions.py (149 LOC)

**Purpose:** Answers whether forwarded-reconstruction matches the main-log payload, and whether
is_error tool_result extraction matches `tool_errors.jsonl`.
**Reads:** main-log entries, forwarded-delta entries, `_original` entries, tool_errors records.
**Writes:** nothing — returns result dicts.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

---

### main_log_elimination_report.py (217 LOC)

**Purpose:** Builds the Markdown report — header, content-match/divergence/field-classification
sections, and the migration verdict.
**Reads:** the question A/B result dicts.
**Writes:** the report file; returns its path.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

---

## State
No shared or mutating state across modules. `main_log_elimination_io.py` and
`main_log_elimination_report.py` each independently resolve `_AREA_ROOT` (by walking up from
`__file__` until the directory named `proxy_dual_log` is found); `_resolve_root`'s fallback (when
`MONITOR_CC_ROOT` is unset) returns `_AREA_ROOT.parent.parent` — the project/worktree root, matching
its pre-move behavior exactly (this fallback does not derive the main checkout; it was never
main-checkout-aware, and preserving its scope was a deliberate choice, not an oversight).
