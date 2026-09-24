# dev/display/

## Role

Tests and differential-proof harnesses for the display layer: tmux pane layout, session-JSONL
rule scanning, pane screenshots, cache-tracker formatting, hover-map correctness, and the
strip-marker pipeline. Touch when changing tmux pane geometry, the token formatter,
proxy and worker line-map logic, or the strip marker. `jsonl_exploration/` is a separate
sub-suite (own DOCS.md).

## Public Interface

No `__init__.py` in this directory. Entry path: run each script directly, e.g.
`./venv/bin/python dev/display/test_hover_map.py` (all commands assume CWD = the project root).

## Flow

A script reads either live tmux pane state, a session/proxy-log JSONL (positional or
auto-discovered), or synthetic in-script fixtures. It exercises one specific piece of the display
pipeline (pane geometry, cache-tracker formatting, hover-map line map, strip-marker highlighting)
via the real production function under test. It writes a PASS/FAIL summary, a PNG, or a
Markdown/JSON report to stdout or a file under this directory.

## Modules

### test_tmux_layout.sh (28 LOC)

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

### A_format_cache_tracker_proof.py (117 LOC)

**Purpose:** Verification, not a test: differential proof the cache tracker's serialized return is byte-identical to a captured baseline. Reads live JSONLs.
**Reads:** real session JSONLs under `~/.claude/projects/`.
**Writes:** `A_format_cache_tracker_proof_reports/baseline_<timestamp>.json` (capture mode).
**Called by:** none — run manually (`--mode capture` then `--mode verify [--baseline PATH]`).
**Calls out:** `src.jsonl.jsonl_cache_turns`, `src.format.token_format` (imported via
`sys.path.insert` + local import, not a module-level `from src.` line).

---

### test_hover_map.py (274 LOC)

**Purpose:** Synthetic and frozen-fixture assertion suite for expand-model line-map correctness and the stripped-span dual-color overlay pairing.
**Reads:** `fixtures/api_requests_fixture_forwarded.jsonl` and its sibling `_stripped.jsonl`, a frozen dual-log pair; the pairing test asserts the fixture yields exactly 5 entries so it cannot pass vacuously.
**Writes:** stdout verdict per strand; `md/test_hover_map.md` (fixed name); exits 1 if any strand aborts.
**Called by:** none, run manually.
**Calls out:** `src.proxy_display.format`, `src.proxy_display.render_messages`, `src.format.token_format`, `dev/refactoring/strand_runner.py` (one subprocess per test function, fail-fast).

---

### test_strip_markers.py (89 LOC)

**Purpose:** Visual and assertion test for the strip-marker highlighter (basic and multi-line cases); two parallel strands.
**Reads:** nothing external, synthetic strings built in-script.
**Writes:** stdout (ANSI-colored) per strand; `md/test_strip_markers.md` (fixed name).
**Called by:** none, run manually.
**Calls out:** `src.format.strip_marker`, `src.colors`, `dev/refactoring/strand_runner.py`.

---

## State

No shared state across modules — each script owns its own module-level constants (pane layout,
thresholds, synthetic fixtures). The strand-based tests keep no results state; each strand is its own process.
