# dev/display/jsonl_exploration/

## Role
Scripts that map the full structure of Claude Code session JSONL files, each exporting a Markdown report. Touch when investigating a JSONL message or content shape not covered by the existing reports.

## Public Interface
No `__init__.py`. Each script is run directly with an optional session path, e.g. `python3 dev/display/jsonl_exploration/01_map_message_types.py [session.jsonl]`.

## Flow
Each script reads a session JSONL (argument, or the newest file of the newest project directory), streams every line collecting statistics or pattern hits, writes a timestamped report to its own report directory and prints the path.

## Modules

### 01_map_message_types.py (174 LOC)

**Purpose:** Per top-level message type: count, keys, subtypes, meta-flag distribution and one truncated example.
**Reads:** a session JSONL path (argument or auto-discovered).
**Writes:** `01_reports/message_types_<timestamp>.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

### 02_map_content_blocks.py (259 LOC)

**Purpose:** Deep-dive into message content blocks per message-type and content-type combination: count, keys, nesting, tool names, example.
**Reads:** a session JSONL path (argument or auto-discovered).
**Writes:** `02_reports/content_blocks_<timestamp>.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

### 03_scan_instructions.py (248 LOC)

**Purpose:** Scans for rules and instruction related content: meta messages, rule-file references, system-reminder tags, file-history snapshots.
**Reads:** a session JSONL path (argument or auto-discovered).
**Writes:** `03_reports/instructions_<timestamp>.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

## State
None shared. Each script owns its report directory and streams its input independently; no module imports another.
