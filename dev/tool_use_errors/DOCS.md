# dev/tool_use_errors/

## Role

Empirical audit suite for `src/logs/tool_errors.jsonl`. Determines which error patterns
are agent-relevant (KEEP) vs strippable CC-wrapper noise, and verifies that
`strip_hook_prefix.py` strips the hook-error prefix before it reaches Anthropic.

## Scripts

### A_error_cluster_audit.py

Loads `tool_errors.jsonl` → clusters by error shape → classifies each bucket → cross-checks
via available proxy logs whether `strip_hook_prefix.py` modifications reach Anthropic.

```bash
./venv/bin/python dev/tool_use_errors/A_error_cluster_audit.py
# Output: dev/tool_use_errors/reports/YYYY-MM-DD_error_cluster_audit.md
```

**Buckets produced:**

| Bucket | Match rule | Verdict |
|--------|-----------|---------|
| `hook_prefixed` | `^PreToolUse:\w+ hook error: \[python3 ` | HISTORICAL (pre-strip-hook) |
| `tool_use_error` | `^<tool_use_error>` | KEEP |
| `exit_code_nonzero` / `exit_code_0` | `^Exit code \d+` | KEEP |
| `rejection` | contains `doesn't want to proceed` | ALREADY_STRIPPED by proxy |
| `bare_guidance` | residual (hook guidance text + CC tool errors without wrapper) | KEEP |

**Cross-check:** Scans `src/logs/api_requests_*.jsonl` for `stripped_hook_error_prefix`
modification entries to confirm the proxy strip reaches Anthropic. Also compares
`hook_prefixed` timestamps against the first strip occurrence to verify historical status.

## Reports

Output: `reports/2026-05-30_error_cluster_audit.md` (first run; subsequent runs add `YYYY-MM-DD_error_cluster_audit.md`)

**Key findings (2026-05-30 run):**
- 495 entries total; no new strippable patterns found
- 59 hook_prefixed entries are historical (pre-strip-hook, 2026-05-24T20:59 – 2026-05-25T01:26)
- `strip_hook_prefix.py` confirmed active in 2,970 requests across 65 proxy log files
- All content after stripping is agent-relevant (KEEP) — `strip_hook_prefix.py` is sufficient
