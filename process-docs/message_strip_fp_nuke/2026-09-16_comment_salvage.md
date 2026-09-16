# process-docs/message_strip_fp_nuke/2026-09-16_comment_salvage.md

Session: dev/strip_fp_tool_result/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/strip_fp_tool_result/*.py` during this milestone,
copied verbatim before deletion, plus the full pre-rewrite content of
`dev/strip_fp_tool_result/DOCS.md`. Nothing judged and dropped — see the milestone rules in the
calling agent's prompt (module-standards conformance: relocate then delete, decide nothing).

Note on location: this milestone's process-docs directory is `process-docs/message_strip_fp_nuke/`
(matching the area name used by this code's own prior investigative history — see
`2026-07-28_tool_result_sr_audit.md` and siblings in this same directory), not
`process-docs/strip_fp_tool_result/`, per the milestone prompt's explicit instruction. This is
the first file this session added to that directory; every other file there predates this session
and was not touched.

File count (4) and comment/docstring totals (43 comments, 1 docstring) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across
`dev/strip_fp_tool_result/*.py` before deletion: zero matches. The 1 module-level docstring (in
`audit_tool_result_sr_strips.py`) is plain narrative, never read at runtime. Deleted outright, no
constant-rewiring needed.

## Execution-safety note for this session

`audit_tool_result_sr_strips.py` writes to a FIXED-name tracked report
(`md/audit_tool_result_sr_strips.md` — no timestamp in the filename). It was snapshotted before
any run and restored from that snapshot after verification, regardless of diff outcome, so no
tracked artifact carries this session's run-to-run corpus drift (the dual-log corpus this script
reads is a live, rotating window per this directory's own DOCS.md Gotchas — a re-run's occurrence
counts legitimately differ from the committed report; this is expected, not a regression).

Comment/docstring counts confirmed via AST + tokenize before deletion: 43 comments, 1 docstring,
matching the task's stated measured state exactly.

## Salvage from dev/strip_fp_tool_result/DOCS.md

Full content of dev/strip_fp_tool_result/DOCS.md as it stood before this rewrite (77 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / State sections added).

```markdown
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
```

## Salvage from dev/proxy/audit_report.py

COMMENT L11:
```
# The SR strip family this issue actually audits — _apply_first_pass's SR-producing branches
```

COMMENT L12:
```
# (task-tools-nag / deferred-tools / user-interrupt), _apply_cumulative_sr_strips, and
```

COMMENT L13:
```
# _apply_final_sr_pass all descend via _content_contains + strip_sr.py's line-anchored
```

COMMENT L14:
```
# <system-reminder> matching. bg_launch_ack / hook_prefix / po_preview match their OWN, unrelated
```

COMMENT L15:
```
# markers (none imports strip_sr) — their tool_result descent is correct and out of this issue's
```

COMMENT L16:
```
# scope, reported separately, never pooled into the SR-family verdict.
```

## Salvage from dev/proxy/audit_scan.py

COMMENT L11:
```
# Import via importlib — avoids block_dev_imports_src hook pattern (from src.)
```

COMMENT L14:
```
# Structural passes (own logic) stayed in message_passes.py; template passes (generic pass
```

COMMENT L15:
```
# runner + declarative spec) moved to message_passes_simple.py (2026-09, helper-extraction milestone).
```

COMMENT L47:
```
# Actual runtime dual-log location (main checkout, not this worktree — src/logs/ is gitignored
```

COMMENT L48:
```
# per-worktree; the corpus only exists here).
```

COMMENT L51:
```
# This worker's own live session log — excluded, see module docstring.
```

COMMENT L54:
```
# Real pipeline order — copied from src/proxy/rules.py::apply_modification_rules `_passes` list.
```

COMMENT L70:
```
# Passes whose OWN source explicitly documents they do NOT descend into tool_result
```

COMMENT L71:
```
# (role_system only ever touches role=='system' messages, which never carry tool_result blocks).
```

COMMENT L72:
```
# Any tool_result hit attributed to these three is an anomaly against the code's own design intent.
```

COMMENT L75:
```
# Passes with exactly one fixed mod name regardless of which idx/branch fired.
```

COMMENT L123:
```
# Build tool_use_id -> {name, input_preview} from all assistant tool_use blocks in one payload's
```

COMMENT L124:
```
# full (pre-strip) message list — tool_use blocks are never touched by any strip pass.
```

COMMENT L141:
```
# Classify a removed chunk's template/rule using the REAL registries from strip_sr.py /
```

COMMENT L142:
```
# content_strip.py (imported, not reinvented) — falls back to the pass's fixed mod name for
```

COMMENT L143:
```
# non-SR-shaped removals (git-lock, hook-prefix, bd-noise, po-preview, ...).
```

COMMENT L160:
```
# True if an odd number of ``` fences precede the offset — signals "inside an open fence".
```

COMMENT L164:
```
# Slice before/after context around [offset, offset+removed_len) from flat_text — the SAME
```

COMMENT L165:
```
# joined representation _ops_from_content_change computed offset against (see module docstring).
```

COMMENT L264:
```
# Reproducibility check for the task-stated ground truth ("quoted git-lock advice block out of
```

COMMENT L265:
```
# retrieved reference material"): counts, per file, how many requests have the git-lock MARKER
```

COMMENT L266:
```
# substring anywhere in a tool_result vs. how many have the full literal _GIT_LOCK_ADVICE (real
```

COMMENT L267:
```
# newlines) present — only the latter would ever actually get stripped by `_strip_git_lock_advice`
```

COMMENT L268:
```
# (exact-substring match). A marker hit with no literal-advice hit is a source-code / escaped
```

COMMENT L269:
```
# quote (e.g. Read of strip_git_lock.py itself, where `\n` is two literal characters, not a
```

COMMENT L270:
```
# newline byte) that the exact-match guard already protects against, by construction.
```

## Salvage from dev/proxy/audit_tool_result_sr_strips.py

DOCSTRING L2-36:
```
Audit: which SR-strip-family passes remove content from INSIDE tool_result blocks.

Measurement only — does not modify src/. Runs the 11 real `_apply_*` pass functions
from `src.proxy.message_passes`, threaded forward in the EXACT order
`rules.py::apply_modification_rules` uses (`_passes` list), over every request payload
in `src/logs/dual_log/*_original.jsonl`.

Why individual passes instead of `apply_modification_rules` directly: behaviorally
identical (same functions, same order, same inputs/outputs) but each pass call also
returns `pass_ops_by_msg_blk` — {msg_idx: {blk_idx: [(offset, removed, injected), ...]}}
— which `apply_modification_rules` discards. That per-block diff is what lets us check
the block's ORIGINAL `type` at (msg_idx, blk_idx) before the pass ran, i.e. whether the
removed text came out of a `tool_result` block specifically.

Offset representation: `_ops_from_content_change` (rule_ops.py) computes the diff on
`_block_inner_text(block)` — for `tool_result` with str content that IS the string; for
`tool_result` with list-of-text sub-blocks, it is those sub-blocks' text JOINED with
'\n'. This script recomputes `_block_inner_text(block)` on the same (old, unmodified)
block object before slicing context around `offset`, so the excerpt is always taken
from the same representation the offset was computed against. `block_shape` in each
occurrence record states which of the two it was.

Self-session handling: this worker's OWN dual-log (name contains 'sr-fp-audit') is
EXCLUDED from the scan — it is being written live while this script runs and would
make the script's own tool calls (Read/Bash on this very investigation) show up as
"evidence". Excluded files are named explicitly in the report, not silently dropped.

Classification (quoted data / genuine CC injection / ambiguous) is NOT automated: the
script surfaces template, tool, verbatim text, and context; the verdict + evidence is
written by hand into `_MANUAL_VERDICTS` below after reviewing a first run's output,
then the script is re-run to fold verdicts into the final report and aggregate counts.

Usage: python3 dev/strip_fp_tool_result/audit_tool_result_sr_strips.py
Output: dev/strip_fp_tool_result/md/audit_tool_result_sr_strips.md

```

## Salvage from dev/proxy/audit_verdicts.py

COMMENT L3:
```
# Manual quoted-data / genuine-injection / ambiguous classification, filled in by hand after
```

COMMENT L4:
```
# reviewing a first run's raw occurrence context (see report body). Keyed by
```

COMMENT L5:
```
# (file_name, msg_idx, blk_idx, first_line_idx) — practical to hand-write, unlike the full
```

COMMENT L6:
```
# removed_text used for dedup. verdict in {'quoted data', 'genuine CC injection', 'ambiguous'}.
```

COMMENT L7:
```
# Evidence for each verdict is in the Occurrences section render — see _render_report.
```

COMMENT L13:
```
# monitor_cc — hook-prefix / bg-launch-ack: all real Bash commands genuinely hitting the
```

COMMENT L14:
```
# hook or genuinely launched in background; context_before is empty (hook prefix) or the
```

COMMENT L15:
```
# literal 'Command ' stub (bg-ack), i.e. the removed text is the ENTIRE real tool_result.
```

COMMENT L32:
```
# posts
```

COMMENT L45:
```
# wise2627
```

COMMENT L50:
```
# capture-monitor-cc-ref
```

