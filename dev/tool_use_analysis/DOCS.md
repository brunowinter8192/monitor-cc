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

## cc_injection_audit.py

**Purpose:** CC injection catalog via proxy-log / session-JSONL cross-reference. For each user-role message in the delta range of each opus REQ, checks whether the message content appears as a real user event in the matching CC session JSONL. Unmatched messages are CC-injected; classified by `startswith` pattern. Produces a Markdown catalog of injection types and frequencies, revealing which injections inflate the context budget.

**Input:** One or more proxy log paths (positional, optional). Default: newest 5 `src/logs/api_requests_opus_monitor_cc_*.jsonl`. CC session JSONL auto-discovered by mtime proximity (max 90 min); override with `--cc-session`.

**Output:** `dev/tool_use_analysis/<YYYYMMDDHHMM>_cc_injection_catalog.md`. Path printed to stdout.

**Usage:**
```bash
# Auto-pick newest 5 proxy logs
./venv/bin/python3 dev/tool_use_analysis/cc_injection_audit.py

# Explicit proxy log + explicit CC session JSONL
./venv/bin/python3 dev/tool_use_analysis/cc_injection_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl \
  --cc-session ~/.claude/projects/-Users-.../session.jsonl
```

---

## tag_presence_audit.py

**Purpose:** Per-REQ, delta-scoped forensic audit for leftover tag occurrences (`<SR>`, `<TN>`, `<ND>`, `<PO>`) in `raw_payload.messages`. Complements `sr_bypass_audit.py` (which is aggregate and multi-counts persistent messages) and `strip_audit.py` (which is delta-scoped but truncated and mixed with EFF/INERT noise). This audit emits only REQs with tag occurrences, shows full content without truncation, and pairs each REQ with its `stripped_msg_removed` delta entries so the reader can answer per-REQ: "tag X was in delta msg[N] — was it stripped (visible in `stripped_msg_removed[N]`) or did it bypass?"

**Input:** Single Proxy JSONL path (positional, optional). Auto-picks newest `api_requests_opus_monitor_cc_*.jsonl` from `src/logs/`.

**Output:** `dev/tool_use_analysis/<YYYYMMDDHHMM>_tag_presence_audit.md`. Path printed to stdout. Sections: per-REQ blocks (only for REQs with tag occurrences) + `## Aggregate (delta-scoped)` footer with tag-type count table and SR template bypass_rate table.

**Usage:**
```bash
# Auto-pick newest log
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py

# Explicit log
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py \
  src/logs/api_requests_opus_monitor_cc_1777294641.jsonl

# Explicit output path
./venv/bin/python3 dev/tool_use_analysis/tag_presence_audit.py \
  src/logs/api_requests_opus_monitor_cc_1777294641.jsonl \
  --output /tmp/my_audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `jsonl` | *(positional, optional)* Proxy JSONL path | auto-picks newest in `src/logs/` |
| `--output FILE` | Output markdown file path | `dev/tool_use_analysis/<YYYYMMDDHHMM>_tag_presence_audit.md` |

**Per-REQ block format:** header line with timestamp + message counts + delta_start; one occurrence block per tag found (label: `<SR>/template_id`, `<TN>`, `<ND>`, or `<PO>`; full content indented 4 spaces); then `STRIPPED` blocks from `stripped_msg_removed` for all delta-range indices. Layer labels: `text`, `tool_result_str`, `tool_result_nested`, `tool_use`, `plain_str`. SR blocks starting with `_PRESERVE_PREAMBLE` (claudeMD context) are silently skipped. Unmatched SR blocks labeled `/?`.

---

## sr_bypass_audit.py

**Purpose:** SR bypass audit — per-template count of bypassed vs captured SR blocks. Scans `raw_payload.messages` for SR blocks still present after proxy processing (bypassed) and `stripped_msg_removed` for SR blocks successfully removed (captured). Reports `bypass_rate` per template per log file + aggregate summary table. Designed to identify which SR templates the proxy strip pipeline is missing.

**Methodology note:** The proxy `stripped_all_sr_msg0` final-pass strips all templates from `msg[0]` but does NOT write to `stripped_msg_removed`. SR blocks captured only by the final pass show as `(captured=0, bypassed=0, n/a)`. SR blocks in `msg[N>0]` that bypass the elif chain are counted as bypassed.

**Input:** JSONL paths (positional, optional). Default: newest 3 `api_requests_opus_monitor_cc_*.jsonl`.

**Output:** `dev/tool_use_analysis/<YYYYMMDDHHMM>_sr_bypass_audit.md`. Path printed to stdout.

**Usage:**
```bash
# Auto-pick newest 3 proxy logs
./venv/bin/python3 dev/tool_use_analysis/sr_bypass_audit.py

# Explicit log
./venv/bin/python3 dev/tool_use_analysis/sr_bypass_audit.py \
  src/logs/api_requests_opus_monitor_cc_1776871226.jsonl
```

---

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

---

## sr_session_audit.py

**Purpose:** Longitudinal SR audit across all Claude Code session JSONLs under `~/.claude/projects/*/*.jsonl`. For each user-role message, extracts `<system-reminder>` blocks (linestart-anchored, mirror of `_STANDALONE_SR_RE` in `src/proxy/strip_sr.py`), classifies against the live strip catalog imported from `_SR_TEMPLATES` in `src/proxy/strip_sr.py` + `_PRESERVE_PREAMBLE` (no duplication), and reports known/preserved/unknown buckets with per-bucket layer split (text vs tool_result), date timeline (first/last seen), and CC version attribution. Designed to surface (a) which catalog templates have empirical hits in modern CC versions, (b) which SR templates are leaking through (gap candidates for catalog extension).

**Input:** `~/.claude/projects/*/*.jsonl` (all CC project session files). Optional positional substring filter on project directory name.

**Output:** Markdown report at `dev/tool_use_analysis/<YYYYMMDDHHMM>_sr_session_audit.md` (auto-generated, override via `--output`). Path printed to stdout. Sections: header (run metadata), Scan Parameters (incl. noise filter description), Known Templates table, Preserved table, Unknown / Gap Candidates table (top N), Top-N Unknown sample text (full inner text up to 600 chars per bucket).

**Usage:**
```bash
# Default: all projects, since 2026-04-16 (Opus 4.7 / CC 2.1.x cutoff)
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py

# All sessions (pre-cutoff included)
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py --since 2026-03-01

# Single project
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py Monitor-CC --since 2026-04-16

# Custom output path
./venv/bin/python3 dev/tool_use_analysis/sr_session_audit.py --output /tmp/audit.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `project_filter` | *(positional, optional)* Substring match on project dir name | `''` (all projects) |
| `--since YYYY-MM-DD` | Skip messages older than this date | `2026-04-16` |
| `--output FILE` | Output Markdown path | `dev/tool_use_analysis/<ts>_sr_session_audit.md` |
| `--top N` | Show top-N Unknown buckets in detail tables | `30` |

**Noise filters:**
- **code-heuristic** — drops SR matches whose inner text starts with regex syntax (`.*?`, `\s*`, `(.*`, `...`, `\n`, `\d+\t` line-number prefix) or contains code markers (`re.compile`, `re.escape`, `_SR_TEMPLATES`, `_TAG_`, `_STRIP_`, ` def `). Applies to ALL classifications. Counted under `n_code_noise`.
- **data-file-noise (Option A)** — UNKNOWN-bucket only. Drops SR when the 120 chars of context BEFORE the `<system-reminder>` tag contains `\d+\t` (Read-tool line-number prefix). Indicates the SR was read FROM a data file (e.g. old session JSONL excerpts in `/tmp/`, audit reports referencing the SR text) rather than INJECTED by CC. Known/Preserved templates are never filtered by this rule. Counted under `n_data_file_noise`.

**Classification logic (mirrors `_match_template()` in `src/proxy/strip_sr.py`):**
1. Inner stripped of leading/trailing whitespace.
2. If matches `_PRESERVE_PREAMBLE` (`"As you answer the user's questions, you can use the following context:"`) → `PRESERVED`.
3. For each template in `_SR_TEMPLATES`, identifier(s) checked via `inner.startswith(ident)`. List identifiers tried with OR semantics (e.g. `claudemd-contents` has `["As you answer the user's questions", "Contents of "]`). First match wins. → `KNOWN:<template_id>`.
4. Otherwise → `UNKNOWN` (after data-file-noise check).

**CC version extraction:** session JSONL entries carry top-level `version` field (e.g. `"2.1.114"`). Per-bucket `versions` set tracks all distinct CC versions where the SR appeared. Entries lacking `version` field are recorded as `unknown`.

---

## rule_compliance.py

**Purpose:** Reads one or more Proxy JSONL files, pairs every `tool_use` block with its `tool_result`, matches each pair against mechanical signatures for the Hard-Rules in `tool-use.md`, and outputs a Markdown compliance report. Covers all pairs (not just failures) — input-based rules (2, 3, 12, 14) fire on successful calls too. An uncategorized-failures bucket collects `is_error=True` calls that matched no rule signature.

**Input:** One or more Proxy JSONL paths under `src/logs/` (positional, variadic). Entries with `raw_payload == null` are skipped.

**Output:** Markdown report to stdout by default, or a file via `--output`. Sections: Source JSONLs, Summary (total tool_use, failures, rules violated), Per-Rule Compliance table (all 16 rules, status ✅/⚠/—), Violations Detail (per-rule with evidence), Uncategorized Failures, Recommendations.

**Usage:**
```bash
./venv/bin/python3 dev/tool_use_analysis/rule_compliance.py \
  src/logs/api_requests_opus_monitor_cc_1778596205.jsonl \
  --output dev/tool_use_analysis/20260512_rule_compliance.md

# Multiple logs
./venv/bin/python3 dev/tool_use_analysis/rule_compliance.py \
  src/logs/api_requests_opus_monitor_cc_*.jsonl \
  src/logs/api_requests_worker_*.jsonl

# Custom rules path
./venv/bin/python3 dev/tool_use_analysis/rule_compliance.py \
  src/logs/api_requests_opus_monitor_cc_1778596205.jsonl \
  --rules ~/.claude/shared-rules/global/tool-use.md
```

| Flag | Description | Default |
|------|-------------|---------|
| `proxy_jsonl` | *(positional, variadic)* Proxy JSONL path(s) under `src/logs/` | required |
| `--rules PATH` | Path to `tool-use.md` Hard-Rules file | `~/.claude/shared-rules/global/tool-use.md` |
| `--output FILE` | Output markdown file path (default: stdout) | stdout |

**Mechanical signatures (v1 — 8 of 16 rules):**
- **Rule 2** (No heredoc file creation): Bash command matches `cat\s*(?!>)>\s*\S+\s*<<\s*['"]?EOF`. Fires on any call (success or failure).
- **Rule 3** (Grep scope hygiene): Bash command has recursive `-r` flag AND no `--include=` AND last non-flag token has no known file extension. Fires on any call.
- **Rule 6** (No parallel Bash): `is_error=True` AND `Cancelled: parallel tool call` in error text.
- **Rule 9** (Read before Edit/Write): `is_error=True` AND `File has not been read yet` in error text.
- **Rule 10** (Branch ambiguity): `is_error=True` AND `fatal: ambiguous argument` in error text (Bash only).
- **Rule 12** (No sleep): Bash command matches `\bsleep\s+\d`. Exception: exact form `sleep N && echo done` with `run_in_background=True`. Fires on any call.
- **Rule 13** (.claire/ typo): `is_error=True` AND `.claire/` in error text OR `.claire/` in `file_path` field for Read/Write/Edit tools.
- **Rule 14** (Background Bash trivial): Bash with `run_in_background=True` AND command starts with `grep|cat|ls|wc|git status|head|tail`. Fires on any call.

Rules 1, 4, 5, 7, 8, 11, 15, 16 have no mechanical signature in v1 — reported as `(no signature)` in the compliance table.

**False-positive guards:**
- Rule 3: last non-flag token with extension in `{.py, .md, .sh, .json, .ts, .jsonl, .txt, .yaml, .yml, .toml, .cfg, .ini, .js, .go, .rs}` → skip (explicit file target, not broad-scope).
- Rule 12: `re.fullmatch(r'sleep\s+\d+\s*&&\s*echo done', cmd.strip())` + `run_in_background=True` → canonical worker-polling form, skip.
- Rule 13: requires `is_error=True`; checks error text and `file_path` field only — never full JSON dump (avoids FP from tool inputs that discuss the typo in documentation text).

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
