# Display Layer Tests

Scripts for testing and verifying the display layer (tmux layout, rules rendering, pane management).

## Working Directory

**CRITICAL:** All commands assume CWD = `Monitor_CC/` (project root)

## Scripts

### test_tmux_layout.sh

Tests tmux 3-pane layout for the monitor: main (left) | rules (top-right) + subagents (bottom-right).

**Purpose:** Verify pane indices after nested splits, confirm `-l` percentage behavior, validate `-b` flag for top/bottom placement.

**Usage:**
```bash
bash dev/display/test_tmux_layout.sh
```

**Output:** Pane index table showing dimensions and positions. Session auto-cleans after output.

**Source:** tmux man page (github.com/tmux/tmux `tmux.1` L3591-3648) — `-l size%` = percentage of target pane's available space.

### scan_jsonl_rules.py

Scans a Claude Code session JSONL to find how loaded rules appear in the data.

**Purpose:** Verify whether "Contents of" lines (indicating loaded CLAUDE.md / .claude/rules/*.md files) are present in the JSONL and in what message type/structure.

**Usage:**
```bash
python3 dev/display/scan_jsonl_rules.py
```

**Output:** All unique "Contents of" entries found, with message type, line number, and parsed rule name/scope.

**Status:** Concluded — confirmed that Session-JSONL contains NO rules/instructions data (Contents of: 0, system-reminder: 0, claudeMd: 0). InstructionsLoaded hook is the only viable Claude-infrastructure source. Superseded by jsonl_exploration/ suite for detailed structure analysis.

## Documentation Tree

- [jsonl_exploration/DOCS.md](jsonl_exploration/DOCS.md) — JSONL structure exploration suite (3 scripts, MD reports)
