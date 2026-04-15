## proxy_display/

Proxy pane package — displays live API request structure from mitmproxy logs.

## pane.py

**Purpose:** Event loops for the proxy pane and worker-proxy pane. Reads `api_requests_*.jsonl` log entries incrementally, handles mouse/keyboard input (click expand/collapse, scroll, hover), and delegates rendering to `format.py`.
**Input:** Module-level state (entries, expand states, scroll offset); reads from `parse_proxy_log` and `_parse_log_file`.
**Output:** Prints formatted pane content to stdout via `format_proxy_block`.

## format.py

**Purpose:** Main rendering function `format_proxy_block` — takes proxy entries, groups them by turn, applies scroll/viewport windowing, and produces the final ANSI string. Also contains shared helpers: `_shorten_model`, `_format_delta`, `_assign_turns_to_entries`.
**Input:** `entries` list, expand states dict, line map dict, hover row, pane dimensions, scroll offset, turns list, optional `item_positions_out` dict (keyed by line_map key → absolute line index in pre-viewport `all_lines`; used by pane.py auto-jump on expand).
**Output:** `(ansi_string, total_lines)` tuple — rendered pane content + pre-viewport total line count for scroll math.

## parser.py

**Purpose:** Reads and parses proxy log JSONL files. Extracts rich fields from `raw_payload` (system blocks, tools, messages, schema warnings) into flat entry dicts, then discards the raw payload to save memory.
**Input:** Project filter string or log file path, last byte position.
**Output:** List of parsed entry dicts, updated byte position.

## render_entry.py

**Purpose:** Renders a single proxy request entry (collapsed or expanded) into a list of display lines. Shows model, message count, cache breakpoints, change warnings, delta breakdown, and per-message detail when expanded. When expanded, shows ALL messages (old messages in DIM, new messages in WHITE). Delta line is expandable for both positive and negative deltas (added/removed tools and messages).
**Input:** Entry index, entry dict, all entries (for prev-entry lookup), expand states, pane width, indent, num label.
**Output:** `(lines, keys)` tuple.

## render_turn.py

**Purpose:** Renders all per-request rows for an expanded turn group. Iterates over grouped entry pairs, numbering requests, and delegates system/tools/messages rendering to the section modules.
**Input:** Group dict, all entries, expand states, pane width, previous entry for delta, request counters.
**Output:** `(lines, keys, opus_req_num, sub_req_num)` tuple.

## render_sections.py

**Purpose:** Renders system blocks section (`render_system_blocks`) and tools section (`render_tools`) for an expanded request entry. Handles unchanged detection, expand/collapse per block, change highlights, and TOOL_BLOCKLIST stripping markers.
**Input:** Entry index, entry dict, previous entry, expand states, pane width, modifications list.
**Output:** `(lines, keys)` tuple per function.

## render_messages.py

**Purpose:** Renders new/modified/removed messages for an expanded request entry (turn-view). Handles two cases: more messages than previous (new additions with full block content) and same/fewer messages (diffs with full content_tail). For stripped messages prefers `entry['stripped_msg_removed']` (only the chunks actually removed, rendered yellow) and falls back to `entry['stripped_msg_originals']` (full pre-modification text) for old log files. Shows block-level detail with full_text (not truncated previews), and content tails.
**Input:** Entry dict, previous entry, all entries, expand states, pane width.
**Output:** `(lines, keys)` tuple.
