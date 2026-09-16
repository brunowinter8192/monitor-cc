# dev/display/jsonl_exploration/

## Role

Scripts that map the full structure of Claude Code session JSONL files, each exporting an MD
report. Touch this directory when investigating a new JSONL message/content shape not already
covered by `01`-`03`'s reports.

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`python3 dev/display/jsonl_exploration/01_map_message_types.py [path/to/session.jsonl]`.

## Flow

Each script reads a session JSONL path (argv[1], or auto-discovers the newest file from the newest
project directory under `~/.claude/projects/`). It streams every line, collecting per-type or
per-block-type statistics or pattern hits. It writes a timestamped Markdown report to its own
`<NN>_reports/` directory and prints the report path to stdout.

## Modules

### 01_map_message_types.py (174 LOC)

**Purpose:** For each top-level `type` value in a session JSONL: count, top-level keys, subtypes,
`isMeta` distribution, one truncated example.
**Reads:** a session JSONL path (argv[1], default hardcoded/auto-discovered).
**Writes:** `01_reports/message_types_<timestamp>.md`.
**Called by:** none — run manually.
**Calls out:** none.

---

### 02_map_content_blocks.py (259 LOC)

**Purpose:** Deep-dive into `message.content` blocks — for each `msg_type`/`content_type`
combination: count, keys, nested structure, tool names, one example.
**Reads:** a session JSONL path (argv[1], default hardcoded/auto-discovered).
**Writes:** `02_reports/content_blocks_<timestamp>.md`.
**Called by:** none — run manually.
**Calls out:** none.

---

### 03_scan_instructions.py (248 LOC)

**Purpose:** Scans for anything rules/instructions-related — `isMeta` messages, "Contents of",
CLAUDE.md references, `system-reminder` tags, file-history-snapshot structure.
**Reads:** a session JSONL path (argv[1], default hardcoded/auto-discovered).
**Writes:** `03_reports/instructions_<timestamp>.md`.
**Called by:** none — run manually.
**Calls out:** none.

---

## State

No shared state across the three scripts — each owns its own `REPORTS_DIR` constant and streams
its input file independently; no module imports another.
