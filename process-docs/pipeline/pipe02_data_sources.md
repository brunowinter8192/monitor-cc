# Pipe Section: Data Sources

## State as of this section's audit

- `session_finder.py`: `~/.claude/projects/` → glob `*.jsonl` + `*/subagents/agent-*.jsonl`, sorted by mtime
- `jsonl_parser.py`: tool_use/tool_result correlation via cache, extracts 8 data types (tools, prompts, media, thinking, skills, warnings, usage, system) via a 9-tuple return
- `constants.py`: 25 hook-event constants (`HOOK_SESSION_START`, `HOOK_SESSION_END`, `HOOK_POST_TOOL`, `HOOK_POST_TOOL_FAILURE`, `HOOK_PERMISSION_REQUEST`, `HOOK_PERMISSION_DENIED`, `HOOK_SUBAGENT_START`, `HOOK_SUBAGENT_STOP`, `HOOK_TEAMMATE_IDLE`, `HOOK_TASK_CREATED`, `HOOK_TASK_COMPLETED`, `HOOK_STOP`, `HOOK_STOP_FAILURE`, `HOOK_FILE_CHANGED`, `HOOK_CWD_CHANGED`, `HOOK_CONFIG_CHANGE`, `HOOK_PRE_COMPACT`, `HOOK_POST_COMPACT`, `HOOK_ELICITATION`, `HOOK_ELICITATION_RESULT`, `HOOK_NOTIFICATION`, `HOOK_WORKTREE_CREATE`, `HOOK_WORKTREE_REMOVE` + the existing 3) and a `HOOK_EVENT_CATEGORIES` dict for color mapping
- `jsonl_parser.py`: `extract_system_messages()` extracts `type=system` messages and their text content; returned as the 9th (last) element of the 9-tuple
- `session-start-rules.sh`: reads stdin (JSON with `source`, `cwd`), logs via `hook_logger.py` with `source=$SOURCE`; uses `$CWD` from JSON instead of `$(pwd)` for the worktree check (NOTE: filename stale — not present in the repo; verify against the actual global hook, cf. `session-start-project-rules.sh`)


### Session Discovery — Filesystem Scan per Poll (category: performance)

`find_active_sessions()` in `src/session_finder.py:16-26` is called every poll cycle (every 0.5s). Sequence per call:
1. `get_project_directories()` (session_finder.py:31-42): `CLAUDE_PROJECTS_DIR.iterdir()` — reads the whole `~/.claude/projects/` directory
2. `collect_jsonl_files()` (session_finder.py:45-60): two globs per project dir:
   - `project_dir.glob('*.jsonl')` — session files
   - `project_dir.glob('*/subagents/agent-*.jsonl')` — subagent files
3. `sort_by_modification_time()` (session_finder.py:74-76): `sorted(..., key=lambda f: f.stat().st_mtime, reverse=True)` — a `stat()` syscall per file

No caching between polls. With many projects/sessions: O(N) syscalls per 0.5s.
`CLAUDE_PROJECTS_DIR` is hardcoded: `Path.home() / '.claude' / 'projects'` (session_finder.py:9).

### JSONL Parsing — 7 Separate Iterations (category: performance)

`parse_new_tool_calls()` in `src/jsonl/jsonl_parser.py:75-87` iterates the `messages` list 7x:
1. `extract_tool_calls(messages, tool_use_cache)` — tool_use/tool_result pairs (jsonl_parser.py:79)
2. `extract_user_prompts(messages)` — external user prompts (jsonl_parser.py:80)
3. `extract_user_media(messages)` — images, documents (jsonl_parser.py:81)
4. `extract_thinking_blocks(messages)` — thinking blocks (jsonl_parser.py:82)
5. `extract_skill_activations(messages)` — skill/command activations (jsonl_parser.py:83)
6. `extract_usage_data(messages)` — token usage per assistant message (jsonl_parser.py:84)
7. `extract_system_messages(messages)` — type=system messages (jsonl_parser.py:85)

Each function iterates fully over all messages. No shared iteration with switch-dispatch.

**9-tuple return and extensibility:**
`parse_new_tool_calls()` returns:
`(tool_calls, new_position, malformed_warnings, user_media, thinking_blocks, user_prompts, skill_activations, usage_data, system_messages)`

`extract_usage_data()` extracts per assistant message: `output_tokens`, `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, content-block type (thinking/tool_use/text), tool name (for tool_use), `requestId`. Return: `[{type, tool_name, output_tokens, input_tokens, cache_creation_input_tokens, cache_read_input_tokens, request_id}]`. Filter: skip when BOTH output_tokens AND input_tokens == 0.

Every new JSONL data format requires:
1. A new `extract_*()` function
2. A new return value in the 9-tuple
3. New unpacking in `process_session_file()` (core/monitor_session.py)
4. A new display function (panes/ or core/monitor.py)

The tuple grows linearly with the number of extracted data types.

### tool_use_cache — No Orphan Cleanup (category: memory)

`tool_use_caches: Dict[Path, dict]` in core/monitor.py:30 — one cache dict per session file.
The per-file cache (`cache` in `extract_tool_calls()`, jsonl_parser.py:141) is a `dict` keyed by `tool_use_id`:
- An entry is added on a `tool_use` block (jsonl_parser.py:176): `tool_use_cache[tool_data['tool_use_id']] = tool_data`
- An entry is deleted on a matching `tool_result` (jsonl_parser.py:187): `del tool_use_cache[tool_use_id]`
- No TTL, no cleanup for orphaned entries (tool_use without a matching tool_result)

Effect: if Claude Code crashes or a tool call never gets a result, the cache grows unbounded. It gets fully cleared on session removal via `del tool_use_caches[removed_file]` (core/monitor.py:113).

### EXCLUDED_TOOLS — the Only Filter Point (category: configuration)

`EXCLUDED_TOOLS = {'Edit'}` in `src/constants.py:121`.
Applied in `filter_excluded_tools()` (jsonl_parser.py:251-252), called at the end of `extract_tool_calls()` (jsonl_parser.py:191).
Only a single tool name excluded. No wildcard pattern, no category filter.

### Byte-Offset Tracking — No Truncation Handling (category: robustness)

`read_new_lines()` in `src/jsonl/jsonl_parser.py:105-116`:
- `f.seek(last_position)` (jsonl_parser.py:109) — jumps directly to the stored byte offset
- New position after reading: `filepath.stat().st_size` (jsonl_parser.py:120)
- No handling when `file_size < last_position` (e.g. on JSONL rotation or file truncation by Claude Code)

In the truncation case, `seek()` would jump to the end of the file and `f.read()` would return an empty string — no error, but silent data loss.

### Content Polymorphism (category: format stability)

Two spots handle `content` as either a string or an array:
- `extract_user_prompts()` (jsonl_extractors.py:30-63): `isinstance(content, list)` → concatenate text blocks; `isinstance(content, str)` → use directly
- `extract_result_content()` (jsonl_parser.py:242-248): `isinstance(content, list)` → first element; `str(content)` as fallback

No explicit format versioning.


## Evidence

### Session Discovery I/O (finding 1)

`dev/pipeline/io_profile/01_reports/poll_cycle_20260322_152817.md` (script: `dev/pipeline/io_profile/01_poll_cycle_cost.py`, dataset: 70 projects, 1479 JSONL files in `~/.claude/projects/`, 2026-03-22):

- Without a project filter: cycle duration **9.58ms** (±0.99), **1479 stat() calls**, 140 glob() calls per cycle
- With a project filter (Monitor_CC): **0.25ms** (±0.05), 0 stat() calls
- Filtering reduces cycle overhead by 9.33ms (97%)

### JSONL Multi-Pass Parsing (finding 2)

`dev/pipeline/parsing_profile/01_reports/multipass_20260322_152816.md` (script: `dev/pipeline/parsing_profile/01_multipass_cost.py`, dataset: session `35ca8892`, 351 messages, 10 measurement runs):

| Function | Mean (µs) | % |
|---|---|---|
| `extract_tool_calls` | 1773.6 | 93.6% |
| `extract_skill_activations` | 39.9 | 2.1% |
| `extract_user_prompts` | 37.3 | 2.0% |
| `extract_thinking_blocks` | 26.9 | 1.4% |
| `extract_user_media` | 17.8 | 0.9% |
| **Total (5 passes)** | **1895.5** | 100% |

Average 5.40 µs/message. Single-pass savings estimate: 70.2 µs.

Scope note: this measurement captured **5 passes (pre-refactor)** — before `extract_usage_data` + `extract_system_messages` were added. The 2 additional passes are lightweight (analogous to `extract_user_media`/`extract_thinking_blocks`, <1% share each). The pass count at the time of this audit is **7** (see above).

### tool_use_cache Orphan Behavior (finding 3)

`dev/pipeline/memory_profile/01_reports/cache_growth_20260322_152818.md` (script: `dev/pipeline/memory_profile/01_cache_growth.py`, dataset: session `35ca8892`, 357 messages):
- Peak cache entries: 1; final orphaned: **1** (a Bash call without a matching tool_result)
- Estimated memory per 1000 messages: 515 bytes

### Format Stability / Unknown Types (finding 7)

`dev/pipeline/format_stability/01_reports/unknown_types_20260322_152802.md` (script: `dev/pipeline/format_stability/01_unknown_types.py`, dataset: **1479 JSONL files**, 222,636 lines, 52 parse errors, 2026-03-22):
- Known top-level type coverage: **91.9%**
- 5 unknown top-level types: `file-history-snapshot`, `queue-operation`, `last-prompt`, `custom-title`, `agent-name`
- Unknown content-block types: **0** (100% known)

Findings 4 (`EXCLUDED_TOOLS`), 5 (truncation handling), 6 (content polymorphism), 8 (logging 0) are code-read-derived — no dev/ benchmark backing.

## Recommendation (target state)

Pending — needs evaluation.

## Open Questions

- InstructionsLoaded does not fire after compaction (issue #30973) or `/clear` (issue #31017) — the rules pane only shows initially-loaded rules
- ASSUMPTION: skill activation does NOT trigger InstructionsLoaded (the CHANGELOG defines scope as CLAUDE.md and project-rules files)
- Project-rules files are not captured by the hook (bug #33275) — only global rules + CLAUDE.md fire
- The system prompt (with "Contents of" lines) is NOT written to the session JSONL — an alternative source is needed

## Sources

- Claude Code #30973: github.com/anthropics/claude-code/issues/30973 (InstructionsLoaded + compaction)
- Claude Code #33275: github.com/anthropics/claude-code/issues/33275 (InstructionsLoaded session_start bug)
- Claude Code #31017: github.com/anthropics/claude-code/issues/31017 (InstructionsLoaded + /clear)
- Claude Code #12151: github.com/anthropics/claude-code/issues/12151 (plugin hook output bug — not applicable, native hook)
- Claude Code CHANGELOG L340: InstructionsLoaded added v2.1.64
- GitHub anthropics/claude-code #27724: JSONL format undocumented, changes without changelog
- GitHub anthropics/claude-code #27361: token counts ~2x too low in JSONL (affects `usage` fields in tool_use messages)
- GitHub unified-cowork JSONL spec: community reverse-engineered spec for Cowork audit.jsonl (related format, not identical to Monitor_CC JSONL)
- GitHub anthropics/claude-code #33414: FireHose monitoring feature request (no official monitoring API)
