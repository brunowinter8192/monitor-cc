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

### audit_tool_result_sr_strips.py (659 LOC)

**Purpose:** Streams every request payload in the dual-log corpus, threads it through the 11 real
`_apply_*` pass functions in `apply_modification_rules`'s exact order, and — using each pass's own
per-block diff — records every removal whose pre-pass block type is `tool_result`. Classifies via the
real `strip_sr.py` template registry; non-SR passes get their fixed mod name. Quoted-data vs.
genuine-CC-injection verdicts for ambiguous cases are hand-written into a manual verdicts table after
review, then folded into later runs.
**Reads:** all `*_original.jsonl` files under src/logs/dual_log in the main checkout (gitignored
runtime data, not per-worktree).
**Writes:** `dev/strip_fp_tool_result/md/audit_tool_result_sr_strips.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.message_passes`, `src.proxy.strip_sr`, `src.proxy.content_strip`,
`src.proxy.rule_ops`, `src.proxy.strip_git_lock` — all via `importlib`, per the
`block_dev_imports_src` hook.

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
