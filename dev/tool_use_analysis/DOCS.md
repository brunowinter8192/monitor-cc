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

## extract_patterns.py

**Purpose:** Reads one or more Proxy JSONL files, pairs every `tool_use` block with its `tool_result`, applies ratio + input-size filtering (ratio≥3, input≥50 chars) to identify waste calls, normalizes tool inputs to grouping signatures (paths→`<PATH>`, log filenames→`<LOG>`, bead IDs→`<BEAD_ID>`, hex IDs→`<HEX>`, epoch timestamps→`<TS>`, long strings→`<TEXT>`), aggregates by `(tool_name, signature)`, and outputs a 6-section Markdown report: per-source summary, tool breakdown, Bash pattern groups (top 15), other tool patterns (Grep/Glob/Read), failed-call groups, wrapper candidates.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: Source JSONLs block (CONVENTION.md), per-source summary, tool breakdown, Bash pattern groups, other-tool patterns, failed calls, wrapper candidates.

**Usage:**
```bash
./venv/bin/python dev/tool_use_analysis/extract_patterns.py \
  src/logs/api_requests_opus_monitor_cc_1776797402.jsonl \
  src/logs/api_requests_worker_extract-tool-defs_1776798488.jsonl \
  --output dev/tool_use_analysis/20260422_session_waste_patterns.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Waste filter:** `ratio = input_chars / max(output_chars, 1) >= 3.0` AND `input_chars >= 50`. Failed calls (`is_error=True`) tracked separately regardless of ratio. `CONTENT_TRANSFER_TOOLS = {'Write', 'Edit'}` plus Bash(`bd *`) and `worker_send`/`worker_merge` MCP calls are excluded from waste pairs (large input by design) and reported in Section 2b instead.

**Normalization order:** paths → log filenames → bead IDs → hex IDs → epoch timestamps → long double-quoted strings → long single-quoted strings → worker session names (context-anchored after `worker-cli`).

**Section 6 (Wrapper Candidates):** Write/Edit/worker_send excluded (content-driven); heredoc/`python3 -c` patterns classified as `structural`; other Bash patterns classified by presence of `|`/`&&`/`bd`. Sorted by `total_input_chars / complexity_weight` (trivial=1, medium=2, structural=4).

## waste_repetition.py

**Purpose:** Reads a single Proxy JSONL file, finds the entry with the highest `message_count` (the cumulative session snapshot), extracts all deduplicated Bash `tool_use` blocks from that entry, and analyzes waste along two independent dimensions:

1. **Repetition Signature Groups** — normalizes each command to a stable signature (home paths → `<HOME>/`, log filenames → `<LOG>`, quoted strings → `<STR>`, hex/digit runs → `<HEX>`/`<N>`, worker names → `<WORKER>`), groups by signature, ranks by `count × avg_chars` descending, reports all groups with `count ≥ --min-count`.

2. **Known-Shortcut Path Fragments** — scans every command for replaceable path fragments using a four-rule table (`KNOWN_SHORTCUTS`): (a) any `abs-path ~/Documents/ai/<project>` in a worker-cli/git-check/dev-sync argument → `c`; (b) same for `~`-form; (c) `/Users/brunowinter2000/Documents/ai/Monitor_CC` in any context → `~/…`; (d) generic `/Users/brunowinter2000/` → `~/`. Per-rule counts are independent; the grand total deduplicates overlapping matches (best/highest-savings rule wins per fragment position).

**Input:** Single Proxy JSONL path (positional). Entries with `raw_payload == null` skipped. The entry with the most messages is used as the cumulative session snapshot.

**Output:** Markdown report to stdout (redirect recommended). Sections: summary line (total calls, distinct sigs, total chars, repeated-sig chars, path-shortcut-saveable), Family Overview (per first-token family with sum counts/chars), Repetition Groups table (top K), Replaceable Path Fragments table with grand total, Full Samples (top 10 expanded commands).

**Usage:**
```bash
./venv/bin/python dev/tool_use_analysis/waste_repetition.py \
  src/logs/api_requests_opus_monitor_cc_1776855140.jsonl \
  > /tmp/waste_rep.md 2>&1
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional)* Single Proxy JSONL path | required |
| `--min-count N` | Minimum occurrence count for a repetition group | 2 |
| `--top K` | Show top K groups in the signature table | 20 |

## strip_audit.py

**Purpose:** Reads a single Proxy JSONL file, filters to claude-opus-* entries only (skips Haiku subagents and null-model `sent_meta` entries), iterates requests in order, and classifies each REQ into five buckets using rule-counter deltas and marker-based chunk attribution from `src/proxy/strip_vocab.py`. Solves four flaws in the old format: (1) index-diff NEW-STRIP detection missed mc=1 secondary calls where `smi=[0]` in both prev and curr; (2) chunk attribution used template `startswith` instead of the proxy's actual capture marker, misattributing "As you answer…" claudeMd blocks; (3) `pass_mods` inert firings were indistinguishable from real strips; (4) pauschal FP flag on any tool_result was too broad.

**Input:** Single Proxy JSONL path (positional, optional). Auto-picks newest `src/logs/api_requests_opus_monitor_cc_*.jsonl` when no path is given.

**Output:** `dev/tool_use_analysis/<YYYYMMDDHHMM>_strip_audit.md`. Report path is also printed to stdout. Four sections:

1. **Legend** — generated by `strip_vocab.legend_markdown()`. Three sub-tables: Buckets (EFF/INERT/IDX/LEAK/SUS with descriptions), Rules (code → full modifications[] name → attribution markers), Tag Literals (PO/SR/TN/ND → raw tag). Compact notation note at the bottom.
2. **Rule Catalog** — deeper reference: SR Templates table (`_SR_TEMPLATES` → `modifications[]` rule name, identifier, mode); Non-SR Rules table (`trimmed_task_notification`, `stripped_rejection_message`, `<persisted-output>` no-rule marker); Attribution Note explaining the marker-inversion logic.
3. **Delta Log** — one block per opus REQ in compact `BUCKET:RULE` notation:
   - `EFF:CODE  msg[idx] [tool_result:Name]  N chunk(s)  Xc` — rule newly fired + chunks attributed. Followed by `chunk[i] "head..."` per chunk.
   - `INERT:CODE` — rule newly fired, 0 attributable chunks (phantom firing from `pass_mods` sibling).
   - `IDX  msg[idx] [tool_result:Name]` — index newly in `smi` but `stripped_msg_removed[idx]` empty/missing (Final-Pass tracking gap; rules.py:197-208 updates `stripped_msg_indices` but not `stripped_msg_removed`).
   - `LEAK:<SR>/CODE  "head"` — SR tag in raw_payload after rule fired. `LEAK:<TN>` for TN tag.
   - `SUS:<PO>` / `SUS:<SR>/CODE  "head"` / `SUS:<TN>` — tag in raw_payload, no rule fired.
4. **Summary** — total REQs, REQs with EFF strips, INERT count, IDX count, SUS/LEAK occurrences.

**Attribution:** Chunk→rule attribution (`strip_vocab.attribute_chunk`) inverts the proxy's capture logic. `_find_system_reminder_blocks(content, MARKER)` captures SR blocks containing MARKER anywhere. Attribution checks each chunk for the MARKER substring; first match in `RULES` order wins. `TN` uses starts-with check (chunks always begin with `<task-notification>`). `ALL` (Final-Pass) has no markers and never appears in EFF — always INERT or triggers IDX.

**Usage:**
```bash
# Auto-pick newest log
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py

# Explicit JSONL path
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl

# Explicit output path
./venv/bin/python3 dev/tool_use_analysis/strip_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl \
  --output dev/tool_use_analysis/20260422_strip_audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `jsonl` | *(positional, optional)* Proxy JSONL path | auto-picks newest in `src/logs/` |
| `--output FILE` | Output markdown file path | `dev/tool_use_analysis/<YYYYMMDDHHMM>_strip_audit.md` |

**LEAK vs SUSPECT classification:**
- `LEAK` — known tag found in `raw_payload.messages` AND the relevant strip rule appears in `modifications[]`: rule fired but tag survived (strip missed the occurrence, e.g. embedded in tool_result content not at line-start).
- `SUSPECT` — known tag found in `raw_payload.messages` AND no relevant rule fired: no rule applies (new tag type, or rule disabled). `<persisted-output>` is always SUSPECT (rule rolled back, no replacement).
- Unrecognized SR blocks (inner text matches no `_SR_TEMPLATES` identifier) are intentional non-strips and are NOT flagged.

**False-positive heuristic:** removed. The old pauschal `⚠ SUSPECT FALSE POSITIVE` flag was emitted on any stripped message with `tool_result` content — too broad (legitimate task-tools-nag strips in Read tool_results were misflagged). Tool_result context (`[tool_result:Read]`) is now shown inline in `EFF:*` and `IDX` lines for information, without attaching a suspect label.

## Generated Reports

### 202604221808_strip_audit.md
Per-REQ strip delta audit (`strip_audit.py`) for session `api_requests_opus_monitor_cc_1776871226.jsonl`. 38 opus REQs. 8 REQs with new strips. Key signals: `trimmed_task_notification` leaking `<task-notification>` into `raw_payload` on every REQ from #6 onward (rule fires but TN blocks survive in tool_result content). `<persisted-output>` present in every REQ from #2 (no active rule). False-positive strips: 5 (Read/Bash/Write tool_results containing SR tags from source code or docs).

### 20260422_session_waste_patterns.md
Signature-normalized analysis (`extract_patterns.py`) across 6 JSONLs (4 from 2026-04-21 evening + 2 from 2026-04-22). 528 unique tool_use blocks. Content-transfer excluded: Write (30 calls, 176k chars), Edit (38 calls, 46k chars), Bash(`bd*`) (19 calls, 12k chars), worker_send (15 calls, 9k chars). Actionable waste: Bash 99.3% (89 calls, 51k chars), Grep 0.7% (2 calls). Top Bash patterns: heredoc-python (structural) + `worker-cli status` (8 calls, 1k, trivial). 9 failed-call patterns; 11 failed calls total.

## Archived Reports (→ archive/)

Reports moved to `archive/` — findings preserved, no longer in active directory.

### archive/20260418_github_cli_failures.md

**Source:** Worker proxy log `api_requests_worker_warnings-pane-fixes_1776546048.jsonl`

Documents four categories of GitHub CLI (`gh-cli` Skill / `grep_repo` / `grep_file`) failures encountered during the warnings-pane-fixes session: missing `repo:` qualifier in `search_code`, POSIX `\|` vs Python `|` regex escaping confusion, wrong file path argument to `grep_file`, and wrong constant names (`WheelUp` vs `MOUSE_WHEEL_UP`). Includes root-cause analysis and fix directions for each failure.

### archive/20260419_baseline.md
Baseline run on all 17 Proxy JSONLs (default mode, `--min-chars 500`). Top offenders: Write (Ø 6,775 chars), Edit (Ø 1,854 chars), Bash (Ø 1,391 chars).

### archive/20260419_bash_deepdive.md
Bash-only deep-dive (`--tool Bash --top 50 --min-chars 500`) on all 17 Proxy JSONLs. Includes Command-Prefix Clustering. Top clusters by total_chars: `python3 [heredoc]` (35 calls, 69k chars), `bd` (36 calls, 59k chars), `python3` inline (39 calls, 52k chars).

### archive/20260419_ratio_analysis.md
Ratio analysis (`--ratio --top 50`) on all 17 Proxy JSONLs — 1,207 matched pairs. Bash leads with max ratio 191.62 (3k chars input → 16 chars output). Read is most efficient (median ratio 0.02).
