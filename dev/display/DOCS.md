# dev/display/

## Role

Tests and differential-proof harnesses for the display layer: tmux pane layout, session-JSONL
rule scanning, pane screenshots, cache-tracker formatting, expand-model hover-map correctness, and
the strip-marker highlight pipeline. Touch this directory when changing tmux pane geometry,
`src/format/token_format.py`, `src/proxy_display/`/`src/workers/` line-map logic, or
`src/format/strip_marker.py`. `display/jsonl_exploration/` is the session-JSONL structure-mapping
sub-suite (see its own DOCS.md). All commands assume CWD = the project root.

## Modules

### test_tmux_layout.sh (55 LOC)

**Purpose:** Verifies the tmux pane layout (window/pane indices, `-l` percentage splits, `-b`
top/bottom placement) by building the target layout in a temporary session and listing panes.
**Reads:** nothing — creates its own temporary tmux session.
**Writes:** stdout pane-index table; session auto-cleans after output.
**Called by:** none — run manually (`bash dev/display/test_tmux_layout.sh`).

---

### scan_jsonl_rules.py (108 LOC)

**Purpose:** Scans a Claude Code session JSONL for "Contents of" lines (loaded CLAUDE.md /
`.claude/rules/*.md` markers) to check whether rules/instructions data is present in session
JSONL and in what message shape.
**Reads:** a session JSONL (path hardcoded/passed in-script).
**Writes:** stdout — all unique "Contents of" entries found, with message type/line/parsed name.
**Called by:** none — run manually.

---

### screenshot_panes.py (142 LOC)

**Purpose:** Captures all tmux panes of a running Monitor_CC session and combines them into one
PNG for visual review.
**Reads:** live tmux session state.
**Writes:** `/tmp/monitor_cc_screenshot.png`.
**Called by:** none — run manually (`--session <name>` to target a non-default session).
**Calls out:** `termshot` (external binary, `brew install homeport/tap/termshot`), `Pillow`.

---

### A_format_cache_tracker_proof.py (128 LOC)

**Purpose:** Differential-proof harness for `format_cache_tracker` — loads real session JSONLs
via `extract_cache_turns`, calls `format_cache_tracker(turns, pane_height, pane_width)` across
multiple height/width combinations, and verifies the serialized 5-tuple return is byte-identical
against a captured baseline.
**Reads:** real session JSONLs under `~/.claude/projects/`.
**Writes:** `json/baseline_<timestamp>.json`.
**Called by:** none — run manually (`--mode capture` then `--mode verify [--baseline PATH]`).
**Calls out:** `src.jsonl.jsonl_cache_turns` (`extract_cache_turns`), `src.format.token_format`
(`format_cache_tracker`) — imported via `sys.path.insert` + local import, not a module-level
`from src.` line.

---

### test_hover_map.py (437 LOC)

**Purpose:** Synthetic + real-log assertion suite for expand-model `line_map` correctness — every
visible row maps to exactly one `phys_row`, monotonic, no duplicates — plus a `render_messages`
`len(lines) == len(keys)` pairing check for the stripped-span dual-color overlay path against
real forwarded/stripped dual-log pairs.
**Reads:** `src/logs/dual_log/*_forwarded.jsonl` + sibling `*_stripped.jsonl` (newest-first glob).
**Writes:** stdout PASS/FAIL lines + `Results: N passed, M failed` summary; exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.proxy_display.format` (`format_proxy_block`), `src.workers.worker_format`
(`format_workers_block`), `src.format.token_format` (`format_cache_tracker`).

---

### test_strip_markers.py (210 LOC)

**Purpose:** Visual test for `src/format/strip_marker.py` — feeds synthetic proxy entries and
session events through the strip-marker highlight pipeline and prints ANSI-colored output to the
terminal for manual review.
**Reads:** nothing external — synthetic entries built in-script.
**Writes:** stdout (ANSI-colored) only.
**Called by:** none — run manually.
**Calls out:** `src.format.strip_marker` (`highlight_stripped`, `get_stripped_data`,
`build_tool_result_strip_lookup`, `build_tool_id_strip_lookup`), `src.colors`.

---

## Gotchas

**`test_hover_map.py`'s dual-log alignment case skips (PASS, not FAIL) when no dual-log pair with
stripped content exists in `src/logs/dual_log/`** — a green run can mean "skipped due to missing
data", not "verified"; check the printed reason, not just the exit code.

**Session JSONL carries no rules/instructions data** (`scan_jsonl_rules.py`'s own finding: zero
"Contents of", zero `system-reminder`, zero `claudeMd` hits — the system prompt is never written
to JSONL). The InstructionsLoaded hook (`hook_outputs.jsonl`) is the only Claude-infrastructure
source for rules data; don't add a JSONL-based rules scanner expecting to find it there.
