# dev/tool_use_analysis/

Forensic extraction and analysis of tool_use blocks from Claude Code sessions. `extract_long_calls.py` for full Markdown reports; `extract_zeros.py` for zero-result search detection; `extract_failed.py` for is_error tool_result detection classified by failure type. Each script is standalone (no shared library — helpers inlined per script).

## extract_long_calls.py

**Purpose:** Reads one or more Proxy JSONL files from `src/logs/`, collects every `tool_use` block from `raw_payload.messages[].content[]`, deduplicates by `tool_use.id` (each unique call counted once), measures the JSON-serialized `input` dict in characters, and outputs a Markdown report ranked by input size. Used to identify which tool calls burn the most context budget.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: summary by tool, char-bucket distribution, top-N detail entries.

**Usage:**
```bash
# Single file → stdout
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  src/logs/api_requests_opus_monitor_cc_1776615410.jsonl

# All proxy logs → file
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  /path/to/src/logs/api_requests_*.jsonl \
  --output dev/tool_use_analysis/20260419_baseline.md

# Top 10 only, threshold 1000 chars
./venv/bin/python3 dev/tool_use_analysis/extract_long_calls.py \
  src/logs/api_requests_*.jsonl \
  --top 10 --min-chars 1000
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--tool NAME` | Filter by tool name (e.g. `Bash`, `Read`, `Grep`) | all tools |
| `--ratio` | Ratio mode: match tool_use with tool_result, report input/output ratio; excludes Edit/Write/worker_send | off |
| `--top N` | Top-N entries in detail section (char-sorted normally, ratio-sorted in `--ratio` mode) | 30 |
| `--min-chars N` | Min input chars filter; ignored in `--ratio` mode | 500 |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Modes:**
- Default: all tools, char-sorted, `--min-chars` filter applies
- `--tool Bash`: adds **Command-Prefix Clustering** section (extract_prefix per call, aggregated by prefix → total_chars)
- `--ratio`: input/output ratio per matched pair; summary table shows mean/median/max ratio per tool
- `--tool NAME --ratio`: combined — ratio mode for one specific tool (exclusion list bypassed)

## extract_zeros.py

**Purpose:** Reads one or more Claude Code session JSONL files, detects every Grep / Glob / Read call that returned a zero result, and outputs a Markdown report with each call's tool name, input parameters, raw result, and preceding assistant text (context for the search intent).

**Input:** One or more session JSONL paths (positional, variadic) under `~/.claude/projects/<encoded>/<session>.jsonl`.

**Output:** Markdown report to stdout by default, or a file via `--output`.

**Usage:**
```bash
# Single session → stdout
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<session>.jsonl

# Multiple sessions — parent + worker sessions combined
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<parent>.jsonl \
  ~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/<worker1>.jsonl

# Write to file
./venv/bin/python3 dev/tool_use_analysis/extract_zeros.py <session.jsonl> --output /tmp/zeros.md
```

| Flag | Description |
|------|-------------|
| `session_jsonl` | *(positional, variadic)* One or more session JSONL file paths |
| `--output FILE` | Output markdown file path (default: stdout) |

**Zero-result detection logic:**
- Grep: result contains `"No matches found"` or `"No files found"`
- Glob: result contains `"No files found"`
- Read: result contains `"File does not exist"` or `"does not exist"` AND does not start with a line-number prefix (`\d+\t`)

**Preceding text extraction:** walks the `parentUuid` chain from the tool_use event back to the nearest preceding assistant text block — gives context for what Opus was trying to accomplish.

## extract_failed.py

**Purpose:** Reads one or more Proxy JSONL files from `src/logs/`, pairs each `tool_use` block with its matching `tool_result`, detects failures via `is_error: true` at the tool_result block level, classifies failure type, and outputs a Markdown report with per-tool / per-type aggregations plus concrete examples.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: per-source failure counts, per-tool breakdown, per-failure-type breakdown, 5 concrete failure examples with input preview and error text.

**Usage:**
```bash
./venv/bin/python3 dev/tool_use_analysis/extract_failed.py \
  src/logs/api_requests_opus_monitor_cc_1776797402.jsonl \
  --output dev/tool_use_analysis/20260421_session_failed.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Failure classification logic:**
- `parallel-cancel` — `<tool_use_error>Cancelled: parallel tool call ...</tool_use_error>` marker
- `tool-unavailable` — `<tool_use_error>Error: No such tool available: ...</tool_use_error>` marker
- `edit-string-not-found` — `String to replace not found in file` marker
- `validation-error` — validation-related error text
- `bash-exit-nonzero` — `is_error: true` without specific `<tool_use_error>` tag (raw shell exit)

Only counts failures where the tool_result block itself has `is_error: true` — guards against false positives from file content that happens to contain error-marker strings.

## Generated Reports

### 20260419_baseline.md
Baseline run on all 17 Proxy JSONLs (default mode, `--min-chars 500`). Top offenders: Write (Ø 6,775 chars), Edit (Ø 1,854 chars), Bash (Ø 1,391 chars).

### 20260419_bash_deepdive.md
Bash-only deep-dive (`--tool Bash --top 50 --min-chars 500`) on all 17 Proxy JSONLs. Includes Command-Prefix Clustering. Top clusters by total_chars: `python3 [heredoc]` (35 calls, 69k chars), `bd` (36 calls, 59k chars), `python3` inline (39 calls, 52k chars).

### 20260419_ratio_analysis.md
Ratio analysis (`--ratio --top 50`) on all 17 Proxy JSONLs — 1,207 matched pairs. Bash leads with max ratio 191.62 (3k chars input → 16 chars output). Read is most efficient (median ratio 0.02).

### 20260421_session_waste_failed.md
Session-level analysis (2026-04-21 tool-use consolidation session) across 4 JSONLs — opus + 3 workers. Known quality issues: Top-10 table filtered Opus-only which produced zircular claims about worker behavior — tracked under bead `Monitor_CC-qfr`. Rewrite needs cross-source top-N and separate source-split tables.

## Historical Reports

### 20260418_github_cli_failures.md

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`

Documents four categories of GitHub CLI (`gh-cli` Skill / `grep_repo` / `grep_file`) failures encountered during the warnings-pane-fixes session: missing `repo:` qualifier in `search_code`, POSIX `\|` vs Python `|` regex escaping confusion, wrong file path argument to `grep_file`, and wrong constant names (`WheelUp` vs `MOUSE_WHEEL_UP`). Includes root-cause analysis and fix directions for each failure.
