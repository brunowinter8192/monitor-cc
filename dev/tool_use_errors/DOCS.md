# dev/tool_use_errors/

## Role

Analysis of tool-use failures and rule violations from Proxy JSONL logs. Consolidates failure detection (`extract_failed.py` logic) with rule-violation matching (`rule_compliance.py` logic) and adds a **hookability classification** as the primary organizing dimension. Primary question: which failures are actionable via new hooks?

## Modules

### analyze.py (397 LOC)

**Purpose:** Load one or more Proxy JSONL files, pair tool_use + tool_result blocks, classify each pair against mechanical failure patterns and rule-violation signatures, assign a hookability bucket per pattern, and write a structured MD report. Covers 18 distinct failure/violation patterns across 6 hookability buckets.
**Reads:** `src/logs/api_requests_*.jsonl` (Proxy JSONL, `raw_payload` field).
**Writes:** stdout (default) or `--output` file.
**Called by:** user (CLI). Never imported.
**Calls out:** stdlib only (`argparse`, `json`, `re`, `os`, `collections`, `datetime`, `pathlib`).

**Hookability buckets:**

| Bucket | Meaning |
|---|---|
| `already-hooked` | Pattern has a live `src/hooks/` script — documented as reference |
| `pre-blockable` | Deterministic regex match on `tool_input` → exit-2 hook style |
| `pre-rewritable` | Pattern detected AND `updatedInput` rewrite would fix it (e.g. add `--` to git diff) |
| `prompt-hook-candidate` | Regex too brittle; short LLM check would decide (30s timeout) |
| `not-statically-hookable` | Requires session state not in `tool_input` (read-history, file contents) |
| `runtime-only` | CC dispatches before PreToolUse fires (parallel-cancel) |

**Patterns covered:**

| Pattern ID | Hookability |
|---|---|
| `parallel-cancel` | runtime-only |
| `read-before-edit` | not-statically-hookable |
| `file-modified` | not-statically-hookable |
| `user-rejected` | not-statically-hookable |
| `hook-blocked` | already-hooked |
| `git-ambiguous` | pre-rewritable |
| `edit-string-not-found` | prompt-hook-candidate |
| `validation-error` | pre-blockable |
| `tool-unavailable` | pre-blockable |
| `read-oversize` | pre-blockable (256KB already hooked; 25k-token gap) |
| `noop-edit` | already-hooked |
| `cat-heredoc` | pre-blockable |
| `broad-grep` | already-hooked |
| `sleep-noncanonical` | already-hooked |
| `claire-typo` | already-hooked |
| `bg-trivial` | already-hooked |
| `venv-no-redirect` | already-hooked |
| `diag-chain-and` | prompt-hook-candidate |

## Usage

```bash
# Single Proxy JSONL → stdout
./venv/bin/python dev/tool_use_errors/analyze.py \
  src/logs/api_requests_opus_monitor_cc_1779403060.jsonl

# All monitor_cc logs → file
./venv/bin/python dev/tool_use_errors/analyze.py \
  --input-glob "src/logs/api_requests_opus_monitor_cc_*.jsonl" \
  --output /tmp/tool_errors.md > /dev/null; cat /tmp/tool_errors.md | head -60

# Opus + workers combined
./venv/bin/python dev/tool_use_errors/analyze.py \
  src/logs/api_requests_opus_monitor_cc_1779403060.jsonl \
  src/logs/api_requests_worker_*.jsonl \
  --output /tmp/tool_errors.md > /dev/null
```

## CLI Flags

| Flag | Description | Default |
|---|---|---|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) | required |
| `--input-glob GLOB` | Glob pattern (expanded in addition to positional) | — |
| `--output FILE` | Output MD file path | stdout |

## Report Sections

Header (lines 1–2 of every report):
```
# Tool-Use Error Analysis — <YYYY-MM-DD HH:MM:SS>
Audit cutoff: <max_session_unix_ts> (<ISO-UTC>) — next delta-audit starts AFTER this
```
`max_session_unix_ts` = largest Unix timestamp embedded in the audited JSONL filenames
(pattern `_(\d{10,})\.jsonl$`). Use this value as the exclusive lower bound when
selecting logs for the next delta-audit. Fallback if no timestamp is extractable:
`Audit cutoff: <not-extractable> — see Source JSONLs list for delta computation`.

1. **Source JSONLs** — files analyzed, event + tool_use counts per file
2. **Hookability Overview** — all 18 patterns sorted by hookability bucket with violation counts
3. **Coverage Gaps** — pre-blockable/pre-rewritable patterns with ≥1 violation and no live hook
4. **Violations Detail** — per-pattern: hookability rationale + up to 5 concrete examples with input/error previews
5. **Uncategorized Failures** — `is_error=True` pairs not matched by any pattern (candidates for new signatures)
