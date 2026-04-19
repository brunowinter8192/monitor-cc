# dev/tool_use_analysis/ — Script & Report Convention

## 1. Script Docstring (mandatory)

Every script under `dev/tool_use_analysis/` starts with a module-level docstring:

```python
"""<One sentence: what this script analyzes.>

Input:  src/logs/api_requests_*.jsonl  (or describe the subset/pattern)
Output: dev/tool_use_analysis/<report_name>_<YYYYMMDD>.md  (or stdout)
"""
```

## 2. Report Source Block (mandatory)

Every generated Markdown report starts with a Source block immediately after the title:

```markdown
# <Report Title> — <ISO timestamp>

## Source JSONLs

- `src/logs/api_requests_opus_monitor_cc_1776544522.jsonl` (N events, M tool_use blocks)
- `src/logs/api_requests_worker_warnings-zero_1776554195.jsonl` (N events, M tool_use blocks)
- ...

Total sessions analyzed: N. Total tool_use blocks: N.
```

**Rules:**
- List every JSONL file that was passed to `load_proxy()` (or equivalent).
- Include event count (lines with `raw_payload != null`) and deduplicated tool_use block count per file.
- If a script loads a glob pattern, expand and list individual files.

## 3. No Shared Library

Each script is standalone. A script may copy 10–30 LOC of helper code inline (JSONL parsing,
tool_use extraction, char counting) — that is acceptable. Do NOT create a shared module for
forensic primitives. The former `src/proxy_forensics.py` was removed on 2026-04-19; helpers
are now inlined in `extract_long_calls.py`.

## 4. Retroactive Source Blocks (existing reports)

Reports created before this convention was established are marked with an unknown-source note.
For future reports this will not happen — the Source block is generated at run time.

Pre-convention reports missing exact source lists:
- `20260419_baseline.md` — Source: unknown (pre-convention, sessions=17 per header)
- `20260419_bash_deepdive.md` — Source: unknown (pre-convention, sessions=17 per header)
- `20260419_ratio_analysis.md` — Source: unknown (pre-convention, sessions=17 per header)

Reports with known sources (listed explicitly in file or header):
- `20260418_github_cli_failures.md` — `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`
- `20260419_waste_classification_raw.txt` — 13 files listed in the file header
