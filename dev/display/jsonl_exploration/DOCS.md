# JSONL Structure Exploration

Scripts to map the full structure of Claude Code session JSONL files. Each script exports results as MD reports.

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

## Scripts

### 01_map_message_types.py

Maps all message types in a session JSONL.

**Purpose:** For each `type` value: count, top-level keys, subtypes, isMeta distribution, one truncated example.

**Usage:**
```bash
python3 dev/display/jsonl_exploration/01_map_message_types.py [path/to/session.jsonl]
```

**Output:** `01_reports/message_types_<timestamp>.md`

### 02_map_content_blocks.py

Deep-dive into `message.content` blocks.

**Purpose:** For each msg_type/content_type combination: count, keys, nested structure, tool names, one truncated example.

**Usage:**
```bash
python3 dev/display/jsonl_exploration/02_map_content_blocks.py [path/to/session.jsonl]
```

**Output:** `02_reports/content_blocks_<timestamp>.md`

### 03_scan_instructions.py

Scans for anything rules/instructions-related.

**Purpose:** Searches for isMeta messages, "Contents of", CLAUDE.md references, system-reminder tags, command tags, file-history-snapshot structure.

**Usage:**
```bash
python3 dev/display/jsonl_exploration/03_scan_instructions.py [path/to/session.jsonl]
```

**Output:** `03_reports/instructions_<timestamp>.md`

## Key Finding

Session-JSONL contains NO rules/instructions data:
- `Contents of`: 0 hits
- `system-reminder`: 0 hits (injected at API call time, not persisted)
- `claudeMd`: 0 hits
- System prompt is NOT written to JSONL

The InstructionsLoaded hook (via `hook_outputs.jsonl`) is the only Claude-infrastructure source for rules data.
