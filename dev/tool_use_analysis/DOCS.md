# dev/tool_use_analysis/

Forensic extraction and analysis of tool_use blocks from Claude Code sessions. Library (`queries.py`) + thin CLI (`query.py`) for ad-hoc forensic queries; `extract_long_calls.py` for full Markdown reports; `extract_zeros.py` for zero-result search detection.

## queries.py

**Purpose:** Proxy JSONL forensic primitives. No I/O side effects outside `load_proxy`. Import for inline `-c` queries or from other scripts to avoid repeating boilerplate.

**Input:** Proxy JSONL paths (via `load_proxy`). Entries with `raw_payload == null` are skipped automatically.

**Key exports:**

| Export | Kind | Description |
|--------|------|-------------|
| `load_proxy(paths)` | fn | Load + tag events from one or more JSONL paths |
| `tool_use_blocks(events)` | generator | Deduplicated ToolUse objects (first occurrence wins) |
| `tool_result_blocks(events)` | fn | `dict[tool_use_id, ToolResult]` |
| `pairs(events)` | generator | Matched `Pair(ToolUse, ToolResult)` objects |
| `filter_by(items, tool, min_input_chars, ratio_gt, exclude_tools, …)` | fn | Composable filter for ToolUse or Pair iterators |
| `aggregate_by_tool(pair_iter)` | fn | `dict[name, ToolStats]` with count/total/mean/median/max ratio |
| `aggregate_by_prefix(bash_uses)` | fn | `list[PrefixBucket]` sorted by total_chars desc |
| `extract_prefix(command_str)` | fn | `(prefix, tags)` — strips env-assigns, cd-chains, detects heredoc/abs-venv/sourced-fn |
| `bucket_distribution(items)` | fn | `list[(label, count)]` per CHAR_BUCKETS |
| `format_timestamp_local(ts_str)` | fn | UTC ISO → local HH:MM:SS |
| `ToolUse`, `ToolResult`, `Pair`, `ToolStats`, `PrefixBucket` | dataclass | Typed containers with computed properties |

**Inline usage example:**
```bash
./venv/bin/python3 -c "
import sys; sys.path.insert(0, 'dev/tool_use_analysis')
from queries import load_proxy, tool_use_blocks, filter_by
evs = load_proxy(['src/logs/api_requests_opus_monitor_cc_1776615410.jsonl'])
bash = list(filter_by(tool_use_blocks(evs), tool='Bash'))
print(f'Bash calls: {len(bash)}, total chars: {sum(u.input_chars for u in bash):,}')
"
```

## query.py

**Purpose:** Thin CLI over `queries.py` for short ad-hoc queries. Not a report builder (that's `extract_long_calls.py`). Output: compact plaintext to stdout.

**Usage:**
```bash
# Count unique Bash calls across all logs
./venv/bin/python3 dev/tool_use_analysis/query.py count --tool Bash src/logs/api_requests_*.jsonl

# Top 5 ratio offenders with ratio > 10
./venv/bin/python3 dev/tool_use_analysis/query.py ratio --top 5 --ratio-gt 10 src/logs/api_requests_*.jsonl

# Bash prefix aggregation (top 10)
./venv/bin/python3 dev/tool_use_analysis/query.py prefix --top 10 src/logs/api_requests_*.jsonl

# Char-bucket distribution for Grep
./venv/bin/python3 dev/tool_use_analysis/query.py bucket --tool Grep src/logs/api_requests_*.jsonl

# Dump single pair as JSON
./venv/bin/python3 dev/tool_use_analysis/query.py pair --id toolu_01ABC src/logs/api_requests_*.jsonl

# Via wrapper (post-merge, from any CWD)
proxy-query ratio --top 5 src/logs/api_requests_*.jsonl
```

| Subcommand | Flags | Description |
|------------|-------|-------------|
| `count` | `--tool NAME` | Count unique tool_use blocks |
| `ratio` | `--top N`, `--tool NAME`, `--ratio-gt X` | Highest input/output ratio pairs |
| `prefix` | `--top N` | Bash command-prefix aggregation |
| `bucket` | `--tool NAME` | Input char-bucket distribution |
| `pair` | `--id ID` *(required)* | Dump single pair as JSON |

## proxy-query wrapper

Shell wrapper at `~/.local/bin/proxy-query`. Sets `$PROJECT` from `$MONITOR_CC_ROOT` (default: `~/Documents/ai/Monitor_CC`), `cd`s there, then calls `./venv/bin/python3 dev/tool_use_analysis/query.py "$@"`. Works from any CWD after the worktree is merged to main.

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

## Generated Reports

### 20260419_baseline.md
Baseline run on all 17 Proxy JSONLs (default mode, `--min-chars 500`). Top offenders: Write (Ø 6,775 chars), Edit (Ø 1,854 chars), Bash (Ø 1,391 chars).

### 20260419_bash_deepdive.md
Bash-only deep-dive (`--tool Bash --top 50 --min-chars 500`) on all 17 Proxy JSONLs. Includes Command-Prefix Clustering. Top clusters by total_chars: `python3 [heredoc]` (35 calls, 69k chars), `bd` (36 calls, 59k chars), `python3` inline (39 calls, 52k chars).

### 20260419_ratio_analysis.md
Ratio analysis (`--ratio --top 50`) on all 17 Proxy JSONLs — 1,207 matched pairs. Bash leads with max ratio 191.62 (3k chars input → 16 chars output). Read is most efficient (median ratio 0.02).

## Historical Reports

### 20260418_github_cli_failures.md

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`

Documents four categories of GitHub CLI (`gh-cli` Skill / `grep_repo` / `grep_file`) failures encountered during the warnings-pane-fixes session: missing `repo:` qualifier in `search_code`, POSIX `\|` vs Python `|` regex escaping confusion, wrong file path argument to `grep_file`, and wrong constant names (`WheelUp` vs `MOUSE_WHEEL_UP`). Includes root-cause analysis and fix directions for each failure.
