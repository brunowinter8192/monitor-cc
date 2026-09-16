# dev/display/

## Role

Tests and differential-proof harnesses for the display layer: tmux pane layout, session-JSONL
rule scanning, pane screenshots, cache-tracker formatting, hover-map correctness, and the
strip-marker pipeline. Touch when changing tmux pane geometry, `token_format.py`,
`proxy_display`/`workers` line-map logic, or `strip_marker.py`. `jsonl_exploration/` is a separate
sub-suite (own DOCS.md).

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/display/test_hover_map.py` (all commands assume CWD = the project root).

## Flow

A script reads either live tmux pane state, a session/proxy-log JSONL (positional or
auto-discovered), or synthetic in-script fixtures. It exercises one specific piece of the display
pipeline (pane geometry, cache-tracker formatting, hover-map `line_map`, strip-marker highlighting)
via the real production function under test. It writes a PASS/FAIL summary, a PNG, or a
Markdown/JSON report to stdout or a file under this directory.

## Modules

### test_tmux_layout.sh (55 LOC)

**Purpose:** Verifies the tmux pane layout (window/pane indices, `-l` percentage splits, `-b`
top/bottom placement) in a temporary session.
**Reads:** nothing — creates its own temporary tmux session.
**Writes:** stdout pane-index table; session auto-cleans after output.
**Called by:** none — run manually (`bash dev/display/test_tmux_layout.sh`).
**Calls out:** `tmux` (external binary).

---

### scan_jsonl_rules.py (100 LOC)

**Purpose:** Scans a Claude Code session JSONL for "Contents of" lines to check whether loaded
rules data is present, and in what message shape.
**Reads:** a session JSONL (auto-discovers the newest project's newest file; no CLI override).
**Writes:** stdout — all unique "Contents of" entries found, with message type/line/parsed name.
**Called by:** none — run manually.
**Calls out:** none.

---

### screenshot_panes.py (119 LOC)

**Purpose:** Captures all tmux panes of a running Monitor_CC session and combines them into one
PNG for visual review.
**Reads:** live tmux session state.
**Writes:** `/tmp/monitor_cc_screenshot.png`.
**Called by:** none — run manually (`--session <name>` to target a non-default session).
**Calls out:** `termshot` (external binary), `Pillow`.

---

### A_format_cache_tracker_proof.py (113 LOC)

**Purpose:** Differential-proof harness for `format_cache_tracker` — verifies its serialized
5-tuple return is byte-identical against a captured baseline.
**Reads:** real session JSONLs under `~/.claude/projects/`.
**Writes:** `A_format_cache_tracker_proof_reports/baseline_<timestamp>.json` (capture mode).
**Called by:** none — run manually (`--mode capture` then `--mode verify [--baseline PATH]`).
**Calls out:** `src.jsonl.jsonl_cache_turns`, `src.format.token_format` (imported via
`sys.path.insert` + local import, not a module-level `from src.` line).

---

### test_hover_map.py (298 LOC)

**Purpose:** Synthetic + real-log assertion suite for expand-model `line_map` correctness and the
stripped-span dual-color overlay pairing.
**Reads:** `src/logs/dual_log/*_forwarded.jsonl` + sibling `*_stripped.jsonl` (newest-first glob).
**Writes:** stdout PASS/FAIL lines + `Results: N passed, M failed` summary; exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.proxy_display.format`, `src.proxy_display.render_messages`,
`src.format.token_format`.

---

### test_strip_markers.py (186 LOC)

**Purpose:** Visual test for the strip-marker highlight pipeline — feeds synthetic proxy entries
through it and prints ANSI-colored output for manual review.
**Reads:** nothing external — synthetic entries built in-script.
**Writes:** stdout (ANSI-colored) only.
**Called by:** none — run manually.
**Calls out:** `src.format.strip_marker`, `src.colors`.

---

## State

No shared state across modules — each script owns its own module-level constants (pane layout,
thresholds, synthetic fixtures). `test_hover_map.py`'s `PASS`/`FAIL` counters are simple global
ints mutated only by its own `assert_true()` helper.
