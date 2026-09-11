# dev/display/jsonl_exploration/

## Role

Scripts that map the full structure of Claude Code session JSONL files, each exporting an MD
report. Touch this directory when investigating a new JSONL message/content shape not already
covered by `01`-`03`'s reports.

## Modules

### 01_map_message_types.py (163 LOC)

**Purpose:** For each top-level `type` value in a session JSONL: count, top-level keys, subtypes,
`isMeta` distribution, one truncated example.
**Reads:** a session JSONL path (argv[1], default hardcoded).
**Writes:** `01_reports/message_types_<timestamp>.md`.
**Called by:** none — run manually.

---

### 02_map_content_blocks.py (239 LOC)

**Purpose:** Deep-dive into `message.content` blocks — for each `msg_type`/`content_type`
combination: count, keys, nested structure, tool names, one truncated example.
**Reads:** a session JSONL path (argv[1], default hardcoded).
**Writes:** `02_reports/content_blocks_<timestamp>.md`.
**Called by:** none — run manually.

---

### 03_scan_instructions.py (237 LOC)

**Purpose:** Scans for anything rules/instructions-related — `isMeta` messages, "Contents of",
CLAUDE.md references, `system-reminder` tags, command tags, file-history-snapshot structure.
**Reads:** a session JSONL path (argv[1], default hardcoded).
**Writes:** `03_reports/instructions_<timestamp>.md`.
**Called by:** none — run manually.

---

## Gotchas

**Session JSONL contains no rules/instructions data** — `Contents of`: 0 hits, `system-reminder`:
0 hits (injected at API call time, not persisted), `claudeMd`: 0 hits; the system prompt itself is
never written to JSONL. The InstructionsLoaded hook (`hook_outputs.jsonl`) is the only
Claude-infrastructure source for rules data.
