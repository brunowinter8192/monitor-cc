# dev/tool_use_analysis/

Forensic extraction and analysis of tool_use blocks from Claude Code sessions. Two complementary scripts: one measures context cost by input length (Proxy JSONL → which calls burn the most chars), the other detects zero-result searches (Session JSONL → which searches found nothing).

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
| `--top N` | Top-N longest calls in detail section | 30 |
| `--min-chars N` | Only include calls with total input chars ≥ N | 500 |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

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

## Historical Reports

### 20260418_github_cli_failures.md

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`

Documents four categories of GitHub CLI (`gh-cli` Skill / `grep_repo` / `grep_file`) failures encountered during the warnings-pane-fixes session: missing `repo:` qualifier in `search_code`, POSIX `\|` vs Python `|` regex escaping confusion, wrong file path argument to `grep_file`, and wrong constant names (`WheelUp` vs `MOUSE_WHEEL_UP`). Includes root-cause analysis and fix directions for each failure.
