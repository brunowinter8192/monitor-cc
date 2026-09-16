#!/usr/bin/env python3
"""Audit: which SR-strip-family passes remove content from INSIDE tool_result blocks.

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
'\\n'. This script recomputes `_block_inner_text(block)` on the same (old, unmodified)
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
"""

# INFRASTRUCTURE
from audit_report import _render_report, _write_report
from audit_scan import _discover_corpus_files, _scan_files, _scan_ground_truth_git_lock


# ORCHESTRATOR

def main():
    included, excluded = _discover_corpus_files()
    per_file_stats, occurrences, assertion_hits = _scan_files(included)
    ground_truth = _scan_ground_truth_git_lock(included)
    report = _render_report(included, excluded, per_file_stats, occurrences, assertion_hits, ground_truth)
    _write_report(report)


if __name__ == '__main__':
    main()
