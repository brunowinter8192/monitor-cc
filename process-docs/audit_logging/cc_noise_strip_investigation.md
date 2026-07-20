# CC Noise Prefix Strip — Tool Error Display Investigation (2026-05-24)

**Topic:** proxy-display-layer stripping of CC-added noise prefixes from tool-error
messages. Initial known case: hook-block errors with a
`PreToolUse:<Tool> hook error: [python3 <full-path>]: ` wrapper. Goal: generalize to
other CC error-class patterns producing similar noise.

**Status:** CONCLUDED 2026-05-30 — empirical audit complete. No new strippable patterns.
`strip_hook_prefix.py` is sufficient. See Evidence section below.

---

## Background

CC wraps various tool-error messages with metadata prefixes before they reach the
agent's `tool_result`. Some of these prefixes are pure display noise that doesn't help
the agent debug. Others may contain context that must not be stripped.

**Confirmed noise case:** hook-block errors get `PreToolUse:<Tool> hook error:
[python3 <full-path>]: ` prepended to what the hook emits on stderr. Demonstrated live
on 2026-05-24 in `src/logs/hook_firing.jsonl` and in parallel in the Monitor display.
The full path prefix is visual noise — the hook name is redundantly available from the
hook log, the filesystem path is never actionable info. **This one pattern class is
safely strippable.**

**Suspected but unconfirmed at the time:** further CC-added wrapper prefixes for other
error classes (MCP-tool-error, parallel-cancel, validation-error) — resolved via the
investigation below.

## Investigation Plan (as scoped at the time)

1. **Pattern discovery:** grep `src/logs/tool_errors.jsonl` clusters for distinct
   error-prefix shapes. Identify CC-wrapper patterns vs agent-relevant content.
2. **Per-pattern decision:** pure noise (strippable) vs context-bearing (keep). Bias
   conservative — when in doubt, KEEP.
3. **Implementation:** strip logic in the proxy-display component, NOT in
   `tool_errors.jsonl` itself. The audit log keeps everything; only the display shows
   the cleaned version.

## Implementation Constraints

- The strip must be unambiguous — the pattern must be CC-wrapper-specific, no collision
  risk with agent-emitted content.
- No stripping of error content the agent needs for debugging.
- Strip happens at the proxy display formatting layer, NOT in `tool_errors.jsonl` itself
  (the audit log keeps originals for future re-analysis).
- An uncertain pattern is documented, not stripped.

## Data-Source Bootstrap

At the time: `tool_errors.jsonl` started 2026-05-24 ~23:32 UTC after a Monitor restart.
1-2 weeks of accumulation = ~2026-06-07 target for the audit.

`hook_firing.jsonl` already contained hook-originated events, giving sample data for the
hook-prefix-strip question early; other CC-noise classes needed data from
`tool_errors.jsonl` which was still thin at the time.

---

## Evidence — Empirical Audit 2026-05-30

**Script:** `dev/tool_use_errors/A_error_cluster_audit.py`
**Report:** `dev/tool_use_errors/reports/2026-05-30_error_cluster_audit.md`
**Dataset:** `src/logs/tool_errors.jsonl` (495 entries, 2026-05-24 → 2026-05-30)
**Proxy logs scanned:** 65 `api_requests_*.jsonl` files

### Cluster Table (495 total entries)

| Bucket | Count | % | Verdict |
|--------|------:|---:|---------|
| `hook_prefixed` | 59 | 11.9% | HISTORICAL — pre-strip-hook; confirmed below |
| `tool_use_error` | 113 | 22.8% | KEEP |
| `exit_code_nonzero` | 202 | 40.8% | KEEP |
| `exit_code_0` | 0 | 0% | — |
| `rejection` | 12 | 2.4% | ALREADY_STRIPPED by proxy `_apply_first_pass` |
| `bare_guidance` | 109 | 22.0% | KEEP |

**bare_guidance hook breakdown** (hook guidance + CC Read errors without wrapper):
`block_broad_grep` 42, `block_except_pass` 16, `block_cd_drift` 10, `cc_Read_error_no_wrapper` 7,
`block_read_oversize (post-strip)` 7, `block_polling_loop` 6, `block_dev_imports_src` 6,
`block_venv_no_redirect` 5, `block_dangerous_kill` 5, `block_git_destructive` 2,
`block_read_oversize` 2, `block_bd_cli_worker` 1.

### Cross-Check: strip_hook_prefix.py reaches Anthropic

- `stripped_hook_error_prefix` confirmed in **2,970 requests** (4,892 modification items) across 65 proxy log files
- First occurrence: `2026-05-25T15:14:57.745Z`
- All 59 hook_prefixed entries predate first strip: latest `2026-05-25T01:26:48.049Z` < `2026-05-25T15:14:57`
- All 4 proxy files referenced by hook_prefixed entries are rotated (missing) — confirms pre-strip historical set

### Conclusion

**No new strippable patterns.** `strip_hook_prefix.py` is sufficient:
- Post-strip, hook guidance appears in `bare_guidance` WITHOUT the path-noise prefix — agent sees only actionable text
- `rejection` (12) already handled by `_apply_first_pass`
- `tool_use_error` (113) + `exit_code_nonzero` (202) + `bare_guidance` (109) are all agent-relevant KEEP

## Sources

- `src/logs/tool_errors.jsonl` (primary source for pattern discovery)
- `src/logs/hook_firing.jsonl` (cross-reference for hook-originated errors)
