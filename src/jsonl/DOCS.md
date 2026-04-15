# src/jsonl/

JSONL parsing pipeline — read session files incrementally, extract tool calls and metadata, detect unknown types.

## Data Flow

```
~/.claude/projects/<project>/<session>.jsonl → jsonl_parser → jsonl_extractors → callers (monitor, token_pane, subagents, workers)
```

## Modules

## jsonl_parser.py

**Purpose:** Core JSONL session file parser. Reads new lines incrementally (by byte offset), extracts correlated tool_use/tool_result pairs with metadata (usage, errors, user prompts, media, thinking, skill activations).

**Input:** `filepath` (Path), `last_position` (byte offset), `tool_use_cache` (dict).

**Output:** Tuple of 10 lists: tool_calls, malformed, prompts, media, thinking, skills, usage, system_messages, unknown_types, new_lines; new file position.

---

## jsonl_extractors.py

**Purpose:** Extract specific data types from parsed JSONL messages: user media (images/documents), user prompts, thinking blocks, skill activations, usage data, system messages, and unknown type detection.

**Input:** List of message dicts (from `parse_jsonl_lines`).

**Output:** Typed lists of extracted items per extractor function.

---

## jsonl_cache_turns.py

**Purpose:** Extract per-turn cache tracking data grouped by user prompts. Used by token_pane, subagent_pane, and worker_pane for cache-turn rendering.

**Input:** List of message dicts.

**Output:** List of cache turn dicts (each containing turn prompt, requests with CR/CC/D/Out metrics).
