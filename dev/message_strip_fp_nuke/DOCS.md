# dev/message_strip_fp_nuke/

## Role
Measurement-only audit for the false-positive-nuke bug class inside `tool_result` content: which
strip passes remove text from a `tool_result` block, split into the system-reminder family vs.
unrelated non-SR passes. Touch when extending this measurement; strip behavior itself lives in
`src/proxy/`.

## Public Interface
No `__init__.py` in this directory. `audit_tool_result_sr_strips.py` is the entry point, run
directly: `python3 dev/message_strip_fp_nuke/audit_tool_result_sr_strips.py`.

## Flow
Streams every recorded request payload from `src/logs/dual_log/`, threads it through the real
per-message pass functions in their production order, and records every removal whose pre-pass
block type is `tool_result`, classified by template. Writes a findings report to `md/`.

## Modules

### audit_tool_result_sr_strips.py (19 LOC)

**Purpose:** Entry point — wires corpus discovery, scanning, and report rendering into one run.
**Reads:** nothing directly; delegates to `audit_scan.py`.
**Writes:** nothing directly; delegates to `audit_report.py`.
**Called by:** none — manual CLI.
**Calls out:** none directly — imports `audit_scan.py` and `audit_report.py`.

---

### audit_scan.py (275 LOC)

**Purpose:** Loads the real `_apply_*` pass functions and `strip_sr.py`/`strip_git_lock.py`
registries, threads every request through them in order, records removals from `tool_result`.
**Reads:** all `*_original.jsonl` files under `src/logs/dual_log` in the main checkout (gitignored
runtime data, not per-worktree).
**Writes:** nothing — returns occurrence/assertion data structures to the caller.
**Called by:** `audit_tool_result_sr_strips.py`, `audit_report.py` (imports `LOGS_DIR`).
**Calls out:** `src.proxy.message_passes`, `src.proxy.message_passes_simple`, `src.proxy.strip_sr`,
`src.proxy.content_strip`, `src.proxy.rule_ops`, `src.proxy.strip_git_lock` — all via `importlib`.

---

### audit_report.py (381 LOC)

**Purpose:** Renders the occurrence/assertion/ground-truth data collected by `audit_scan.py` into
the markdown findings report and writes it to disk.
**Reads:** the data structures returned by `audit_scan.py`; `_MANUAL_VERDICTS` from
`audit_verdicts.py`.
**Writes:** `md/audit_tool_result_sr_strips.md`.
**Called by:** `audit_tool_result_sr_strips.py`.
**Calls out:** none beyond `audit_scan.py` (for `LOGS_DIR`) and `audit_verdicts.py`.

---

### audit_verdicts.py (42 LOC)

**Purpose:** Hand-written quoted-data / genuine-CC-injection / ambiguous verdict table, keyed by
`(file, msg_idx, blk_idx, first_line_idx)`, filled in after reviewing a first run's output.
**Reads:** nothing.
**Writes:** nothing — pure constant data.
**Called by:** `audit_report.py`.
**Calls out:** none.

---

## State
No persistent state lives in this directory's code. `audit_verdicts.py` holds the one piece of
hand-maintained data (`_MANUAL_VERDICTS`), read by `audit_report.py` on every run and never
written by any script here.
