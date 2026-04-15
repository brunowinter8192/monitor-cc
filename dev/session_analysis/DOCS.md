# dev/session_analysis/

Standalone forensic analysis suite for Claude Code session JSONL and proxy log data. Used to investigate cache behavior, token attribution, and cache rebuild root causes. Scripts are not part of the production pipeline — they read raw data files directly and write Markdown reports or print to stdout. All scripts assume CWD = `Monitor_CC/` (project root).

## 01_extract.py

**Purpose:** Multi-level extraction and summary of tool calls from session JSONL files. Supports four zoom levels: all projects (aggregate), single project, single session, single session filtered by tool name.

**Input:** `~/.claude/projects/**/*.jsonl` session files. Optionally filtered by `--project` (absolute path) and `--session` (JSONL file path).

**Output:** Markdown table of tool call counts and input/output token usage — printed to stdout.

**Usage:**
```bash
# All projects (aggregate)
python3 dev/session_analysis/01_extract.py

# Single project
python3 dev/session_analysis/01_extract.py --project /path/to/project

# Single session
python3 dev/session_analysis/01_extract.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session, single tool
python3 dev/session_analysis/01_extract.py --session <path> --tool Bash
```

| Flag | Description |
|------|-------------|
| `--project` | Absolute project path — filters to that project's sessions |
| `--session` | Path to a single session JSONL file |
| `--tool` | Tool name filter (requires `--session`) |

---

## 02_cache_timeline.py

**Purpose:** Visualizes cache and token behavior turn-by-turn or minute-by-minute across a session or project. Detects anomalies (large CC spikes, time gaps > TTL, drops in CR). Useful for spotting when and why cache rebuilds occur at a coarse granularity.

**Input:** `~/.claude/projects/**/*.jsonl` session files, optionally a full project path.

**Output:** Markdown table with per-turn CR/CC/D/Out metrics, anomaly flags, bar chart — printed to stdout.

**Usage:**
```bash
# Single session — turn-by-turn
python3 dev/session_analysis/02_cache_timeline.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session — anomalies only
python3 dev/session_analysis/02_cache_timeline.py --session <path> --anomalies-only

# Single session — per-minute aggregation
python3 dev/session_analysis/02_cache_timeline.py --session <path> --aggregate

# Project summary (one row per session)
python3 dev/session_analysis/02_cache_timeline.py --project /path/to/project

# Include worker sessions
python3 dev/session_analysis/02_cache_timeline.py --project /path/to/project --workers
```

| Flag | Description |
|------|-------------|
| `--session` | Path to session JSONL file |
| `--project` | Absolute project path — one summary row per session |
| `--aggregate` | Per-minute aggregation view (requires `--session`) |
| `--workers` | Include worker sessions (requires `--project`) |
| `--anomalies-only` | Show only turns with detected anomalies (requires `--session`) |

---

## 03_cache_rebuild_context.py

**Purpose:** Detects cache rebuilds (turns where CR drops and CC spikes disproportionately) and displays surrounding message context for root cause analysis. Outputs pattern summary (how many rebuilds, time-gap triggered vs payload-triggered) and delta statistics.

**Input:** `~/.claude/projects/**/*.jsonl` session files. Single session or all projects scan.

**Output:** Per-rebuild context blocks (N messages before/after) + pattern summary — printed to stdout.

**Usage:**
```bash
# Single session, full context
python3 dev/session_analysis/03_cache_rebuild_context.py --session ~/.claude/projects/<encoded>/session.jsonl

# Single session, wider context window
python3 dev/session_analysis/03_cache_rebuild_context.py --session <path> --context 10

# Single session, summary only (no context blocks)
python3 dev/session_analysis/03_cache_rebuild_context.py --session <path> --summary-only

# All sessions across all projects
python3 dev/session_analysis/03_cache_rebuild_context.py --all
```

| Flag | Description |
|------|-------------|
| `--session` | Path to session JSONL file |
| `--context N` | Messages before/after each rebuild (default: 5) |
| `--summary-only` | Print pattern summary only, no context blocks |
| `--all` | Scan all session JSONLs across all projects |

---

## 04_cache_validation.py

**Purpose:** Validates proxy-side cache breakpoint placement and stability. Reads a proxy JSONL log and shows per-request: CC's original breakpoint positions (system/tools/messages), which messages contain proxy-modified content, whether breakpoints are stable between consecutive requests, and potential invalidation risks from modified content before a breakpoint.

**Input:** A proxy JSONL log file (`src/logs/api_requests_*.jsonl`) as positional argument.

**Output:** Per-request breakpoint analysis table — printed to stdout.

**Usage:**
```bash
# All requests in proxy log
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl

# Limit to first N requests
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl --limit 20

# Only requests with modifications before a breakpoint
python3 dev/session_analysis/04_cache_validation.py src/logs/api_requests_<id>.jsonl --rebuilds-only
```

| Flag | Description |
|------|-------------|
| `log_file` | *(positional)* Path to proxy JSONL log file |
| `--limit N` | Limit output to first N requests (0 = all, default: 0) |
| `--rebuilds-only` | Only show requests where modified content sits before a cache breakpoint |

---

## 05_req_breakdown.py

**Purpose:** Forensic per-segment token attribution for a specific API request. Uses tiktoken (cl100k_base) to tokenize each system block, tool definition, and message individually and compare against session JSONL ground truth (CR, CC, D, Out). Optional cross-session byte-diff (`--prev-proxy-log`) computes which prefix segments were cache-read vs newly created, enabling root cause attribution for cache rebuilds. Writes a timestamped Markdown report to `04_reports/`.

**Input:** A proxy JSONL log (`--proxy-log`) + a session JSONL (`--session-jsonl`) for the same session. Optionally a previous session's proxy log (`--prev-proxy-log`) for byte-diff attribution when CR > 0.

**Output:** `04_reports/<YYYYMMDD_HHMMSS>_req<N>.md` — report path printed to stdout.

**Usage:**
```bash
python3 dev/session_analysis/05_req_breakdown.py \
  --proxy-log src/logs/api_requests_<id>.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
  --req 5

# With cross-session byte-diff attribution
python3 dev/session_analysis/05_req_breakdown.py \
  --proxy-log src/logs/api_requests_<current>.jsonl \
  --session-jsonl ~/.claude/projects/<encoded>/session.jsonl \
  --req 5 \
  --prev-proxy-log src/logs/api_requests_<previous>.jsonl
```

| Flag | Description |
|------|-------------|
| `--proxy-log` | *(required)* Proxy JSONL log file for the session |
| `--session-jsonl` | *(required)* Session JSONL file for ground truth CR/CC/D/Out |
| `--req N` | Request number (1-based, Opus only, default: 1) |
| `--prev-proxy-log` | Previous session proxy log for prefix byte-diff attribution (enables CR breakdown) |

---

## 04_reports/

MD reports written by `05_req_breakdown.py`. One file per run.

**Naming convention:** `<YYYYMMDD_HHMMSS>_req<N>.md` — timestamp of the run + the request number analyzed (e.g., `20260413_004819_req2.md`).

**Report structure:**
1. **Header** — proxy log path, session JSONL path, timestamp
2. **Ground Truth** — CR, CC, D, Out, Total input from session JSONL (deduplicated streaming chunks)
3. **Segment Breakdown** — tiktoken token counts per system block, per tool definition, per message; totals and estimate vs ground truth delta
4. **Prefix Attribution** *(when `--prev-proxy-log` provided)* — byte-diff per segment: which segments are byte-identical to previous session (→ cache-read) vs changed (→ cache-creation)
5. **Rule Edits** — proxy modifications detected between current and previous request (system content changes, injected rules)
