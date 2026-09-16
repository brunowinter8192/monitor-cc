# dev/strip_fp_tool_result/

## Role
Measurement-only audit for the false-positive-nuke bug class as it applies to `tool_result` content
specifically: which strip passes remove text from inside a `tool_result` block, split into the
system-reminder strip family vs. unrelated non-SR passes (bg_launch_ack, hook_prefix, po_preview).
Touch when extending this measurement or building a fix milestone's regression baseline; do not touch
to change strip behavior itself — that lives in `src/proxy/`.

## Flow
Streams every recorded request payload, threads it through the real per-message pass functions in
their production order, and records every removal whose pre-pass block type is `tool_result`,
classified by template — writes a findings report to `md/`.

## Modules

### audit_tool_result_sr_strips.py (54 LOC)

**Purpose:** Entry point — wires corpus discovery, scanning, and report rendering into one run.
**Reads:** nothing directly; delegates to `audit_scan.py`.
**Writes:** nothing directly; delegates to `audit_report.py`.
**Called by:** none — manual CLI (`python3 dev/strip_fp_tool_result/audit_tool_result_sr_strips.py`).
**Calls out:** none directly — imports `audit_scan.py` and `audit_report.py`.

---

### audit_scan.py (301 LOC)

**Purpose:** Loads the real `_apply_*` pass functions and `strip_sr.py`/`strip_git_lock.py` registries,
threads every dual-log request through them in production order, and records every removal whose
pre-pass block type is `tool_result`. Also runs the git-lock ground-truth reproduction check.
**Reads:** all `*_original.jsonl` files under src/logs/dual_log in the main checkout (gitignored
runtime data, not per-worktree).
**Writes:** nothing — returns occurrence/assertion data structures to the caller.
**Called by:** `audit_tool_result_sr_strips.py`, `audit_report.py` (imports `LOGS_DIR`).
**Calls out:** `src.proxy.message_passes`, `src.proxy.message_passes_simple`, `src.proxy.strip_sr`,
`src.proxy.content_strip`, `src.proxy.rule_ops`, `src.proxy.strip_git_lock` — all via `importlib`, per
the `block_dev_imports_src` hook.

---

### audit_report.py (387 LOC)

**Purpose:** Renders the occurrence/assertion/ground-truth data collected by `audit_scan.py` into the
markdown findings report, split per report section, and writes it to disk.
**Reads:** the data structures returned by `audit_scan.py`'s scan functions; `_MANUAL_VERDICTS` from
`audit_verdicts.py`.
**Writes:** `dev/strip_fp_tool_result/md/audit_tool_result_sr_strips.md`.
**Called by:** `audit_tool_result_sr_strips.py`.
**Calls out:** none beyond `audit_scan.py` (for `LOGS_DIR`) and `audit_verdicts.py`.

---

### audit_verdicts.py (53 LOC)

**Purpose:** Hand-written quoted-data / genuine-CC-injection / ambiguous verdict table, keyed by
`(file, msg_idx, blk_idx, first_line_idx)`, filled in after reviewing a first run's raw output.
**Reads:** nothing.
**Writes:** nothing — pure constant data.
**Called by:** `audit_report.py`.
**Calls out:** none.

---

## Gotchas
- Self-session exclusion is by filename, not automatic — any file matching the marker
  `sr-fp-audit` is excluded, since this script's own dual-log grows live while it runs and its own
  Read/Bash calls would otherwise appear as fake evidence.
- The corpus is live — other sessions' dual-logs keep growing between runs; occurrence counts are a
  snapshot at scan time, not a fixed total.
- `tool_result_list_joined` offsets are into the JOINED sub-block text, not any single sub-block —
  reuse `_block_inner_text` (from `rule_ops.py`) for context slicing, matching what
  `_ops_from_content_change` computed the offset against.
- The SR-family vs. non-SR split is load-bearing for the report's headline conclusion — pooling
  `bg_launch_ack`/`hook_prefix`/`po_preview` (unrelated markers, correct-by-design tool_result
  descent) together with actual SR-template passes produces a false "genuine injections found"
  conclusion.
