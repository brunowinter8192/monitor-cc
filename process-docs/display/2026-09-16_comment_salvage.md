# display comment/docstring salvage — 2026-09-16

## Context

Module-standards conformance pass over `dev/display/` (8 `.py` files: 5 top-level +
3 under `dev/display/jsonl_exploration/`, matching the milestone prompt's measured file count
exactly; `dev/display/test_tmux_layout.sh` is a shell script and out of scope for comment
removal, but its DOCS.md entry was kept and re-verified against `wc -l` like every other
module). The project standard allows exactly three comment lines per module —
`# INFRASTRUCTURE`, `# ORCHESTRATOR`, `# FUNCTIONS` — plus a line-1 shebang, and no
docstrings anywhere. Every other comment and every docstring found in this directory is
captured verbatim below, then was deleted from the code. The three section markers and the 5
shebangs were left untouched in the code and are NOT repeated here — nothing was lost for them.

Comment/docstring counts verified with the same `ast`+`tokenize` script used for the three
prior milestones (with the shebang-skip fix from the `tool_use_analysis` milestone already
applied): 125 raw comment tokens excluding shebangs, of which 5 are literal canonical markers
(2 in `test_hover_map.py` — `# INFRASTRUCTURE` and `# ORCHESTRATOR`, no `# FUNCTIONS`; 3 in
`A_format_cache_tracker_proof.py` — one of each) → **120 non-marker comments, matching the
milestone's measured count exactly**. 16 docstrings total, also matching exactly — all module-
or function-level, zero class docstrings (no classes anywhere in this directory).

## A decorated-marker case: `screenshot_panes.py`'s `# --- INFRASTRUCTURE ---` lines

`screenshot_panes.py` uses `# --- INFRASTRUCTURE ---`, `# --- FUNCTIONS ---`, and
`# --- ORCHESTRATOR ---` (dashes and spacing added) instead of the literal three-word
canonical markers. This is the first time this exact shape has come up across all four
module-standards milestones so far. Decision made per the milestone's own "you decide
nothing" instruction: these do NOT literally match `# INFRASTRUCTURE`/`# ORCHESTRATOR`/
`# FUNCTIONS` character-for-character, so they were treated as ordinary comments — salvaged
verbatim below, then deleted like any other comment. `screenshot_panes.py` now has ZERO
section-marker comments left in it, matching the same pattern already established for files
with no markers at all (e.g. `scan_jsonl_rules.py` in this same directory,
`proxy_176_agent_types_tests.py` from the `tool_use_analysis` milestone) — no new marker text
was invented or normalized into the canonical form, since doing so would be "deciding" a
structural fix outside this milestone's negative scope ("do not restructure code"). Only the
5 genuinely-literal `# INFRASTRUCTURE`/`# ORCHESTRATOR` markers in `test_hover_map.py` (1 each
— it has no `# FUNCTIONS` marker either, pre-existing, untouched) and
`A_format_cache_tracker_proof.py` (3, one of each) survived as literal markers; every other
file in this directory already had zero or partial markers before this pass and still does
after it.

## Load-bearing docstring check

Grepped the whole directory for `__doc__`, `argparse`, `help(`, `pytest`, and `unittest`
before deleting anything. 2 files use `argparse` (`A_format_cache_tracker_proof.py`,
`screenshot_panes.py`), and neither passes `__doc__` to `description=`/`epilog=` — both use
either no description at all or a separate string literal. Zero uses of `__doc__` anywhere in
the directory. No test runner or `help()` call consumes any docstring either. **Zero
load-bearing docstrings** — all 16 were deleted outright after salvaging, none needed rewiring
to a constant.

## Script classification and two pre-existing production-drift bugs found

All 8 scripts are read-only. None mutate any tracked file, and none drive the real macOS
desktop, open/move windows, switch Spaces, or send hotkeys. `screenshot_panes.py` reads live
tmux pane text via `tmux capture-pane -p` (a passive scrollback-buffer read, sends no input
to the pane) and renders it OFFLINE via `termshot --raw-read` (per `termshot --help`:
`--raw-read` reads a file INSTEAD OF executing a command — no live process is spawned, no
window is opened) — classified as safe to run against the real, currently-attached
`monitor_cc_*` tmux sessions in this shared environment, since it cannot disturb them.

**Bug 1 (pre-existing, found by `screenshot_panes.py`):** the script's hardcoded
`PANE_TARGETS`/`PANE_LAYOUT` assume a fixed 5-window/10-pane Monitor_CC layout
(`0.0`=main … `4.0`=warnings). Every live `monitor_cc_*` session in this environment
currently has 6 windows, not 5 — running the script against `monitor_cc_25c51a2e` fails
cleanly with `RuntimeError: ... can't find pane: 1` on the very first non-trivial pane lookup
(`0.1`). This is real pane-geometry drift between the script and the live monitor, not
something this pass caused — verified byte-identical (via the same edited-file
line-number-normalizing harness used in the `proxy_dual_log`/`tool_use_analysis` milestones)
before and after the comment strip. Not fixed here — out of scope.

**Bug 2 (pre-existing, found by `test_strip_markers.py`):** `src/format/strip_marker.py`
currently exports ONLY `highlight_stripped` — `get_stripped_data`,
`build_tool_result_strip_lookup`, and `build_tool_id_strip_lookup` (all three imported by
`test_strip_markers.py` at module load) have been removed from production code since this test
was last run successfully. The script now fails immediately with
`ImportError: cannot import name 'get_stripped_data'` before any of its own logic executes.
This is NOT documented in the old DOCS.md's Gotchas (a genuinely new finding from this pass,
not a known issue), so it is recorded here rather than invented into the new DOCS.md's
Purpose/Calls-out fields (DOCS.md stays structural; this kind of currently-broken-import fact
belongs in process-docs, matching how the `proxy_dual_log` milestone's `strip_audit.py`
`KeyError` and this same milestone's `agent-types` gap were handled). Verified byte-identical
`ImportError` before and after the comment strip via the same normalized-traceback harness.
**Whoever next touches `src/format/strip_marker.py` or wants a working visual strip-marker
check should know this script cannot run at all right now — it needs restoring the three
missing functions or rewriting the test to only exercise `highlight_stripped`, neither of
which is in scope for a comment-standards pass.**

## Live-corpus risk avoided (twice)

Two of `test_hover_map.py`'s/`A_format_cache_tracker_proof.py`'s real-data code paths read
from directories that are SHARED and ACTIVELY GROWING in this environment (same class of risk
as the `proxy_dual_log`/`tool_use_analysis` milestones' documented false alarms):

- `A_format_cache_tracker_proof.py`'s `_find_sessions()` globs the newest 10 files from
  `~/.claude/projects/-Users-brunowinter2000-Documents-ai-Monitor-CC/` — THIS SESSION'S OWN
  transcript lives in that exact directory and grows with every tool call made while this
  milestone runs. Running the CLI's `main()` twice, minutes apart, would almost certainly
  pick up new turns and produce a false diff unrelated to the comment strip. Avoided by
  freezing 3 already-closed (previous-day) session files into `/tmp/display_frozen_sessions/`
  ONCE and calling `_load_turns`/`_run_one_case` directly against that frozen set, both
  before and after — byte-identical full JSON output.
- `test_hover_map.py`'s `test_stripped_msg_pair_alignment` globs
  `src/logs/dual_log/*_forwarded.jsonl` newest-first; the newest match on this run was
  `api_requests_worker_25c51a2e_c2_1789539350` — this worker's own ("c2"'s own) live dual-log
  stream, actively written by this very session. Avoided by freezing the 8 newest
  forwarded+stripped pairs into `/tmp/display_frozen_duallog/` ONCE and calling
  `_collect_stripped_pair_entries(frozen_dir)` + `render_messages` directly against that
  frozen directory (the function already takes `dual_dir` as a plain parameter — no
  monkeypatching needed) — byte-identical `lines"=="keys` results for all 5 matched entries,
  both before and after.

**Lesson for the next agent, reinforced a third time: in this shared environment, ANY script
that auto-discovers "the newest file/session/project" is reading data that may include this
very agent's own currently-running session. Always freeze a snapshot before diffing
before/after runs of anything that globs by mtime.**

## How the strip was done

Identical tooling to the three prior milestones (see `process-docs/dual_log_cli/`,
`process-docs/proxy_dual_log/`, and `process-docs/tool_use_analysis/` for the script
internals, including the shebang-skip fix applied to `extract_ordered.py` last milestone,
reused here unchanged and re-verified against this directory's 5 shebangs): an `ast`+
`tokenize` script extracted every comment/docstring by exact `(lineno, col)` position into
this file, then a second script physically deleted them — full-line comments and docstring
line ranges removed entirely, trailing inline comments trimmed off their code line, 3+
consecutive resulting blank lines collapsed to one, line-1 shebangs left completely untouched.
All 8 files were touched by the strip.

## DOCS.md rewrite

TWO DOCS.md files exist in this area — `dev/display/DOCS.md` and
`dev/display/jsonl_exploration/DOCS.md` — both rewritten to the mandated format per the
milestone's explicit note. `dev/display/DOCS.md` kept its non-`.py` module
(`test_tmux_layout.sh`) as a documented module using the same header shape (just with a
`.sh` suffix instead of `.py`, since the file genuinely is a shell script and cutting real,
accurate documentation of an actual file in the directory is not what "cut what doesn't fit
the format" is for) — its LOC (55) was re-verified against `wc -l` unchanged, since shell
scripts are out of this milestone's comment-removal scope. Both DOCS.md files already used a
Purpose/Reads/Writes/Called-by/Calls-out shape per module; `dev/display/DOCS.md`'s Role ran
past 50 words and both files carried a Gotchas section not in the mandated format — cut and
salvaged verbatim below. `dev/display/A_format_cache_tracker_proof.py`'s `Writes:` line was
corrected from the old DOCS.md's stale `json/baseline_<timestamp>.json` (a path that does not
match anything in the current source — the actual code writes to
`A_format_cache_tracker_proof_reports/baseline_<timestamp>.json`, verified directly against
`_run_capture`'s source) to the path the code actually uses, confirmed by running `--mode
capture` against the frozen fixture. New LOC figures were measured with `wc -l` AFTER the
comment/docstring strip, e.g. `A_format_cache_tracker_proof.py` 128 -> 113, `test_hover_map.py`
358 -> 298, `test_strip_markers.py` 210 -> 186 — every one of the 9 headings (6 in
`dev/display/DOCS.md` including the `.sh` file, 3 in `jsonl_exploration/DOCS.md`) was checked
against its file's actual current `wc -l`, zero mismatches.

## For the next agent

- `test_strip_markers.py` cannot run at all right now (ImportError, see Bug 2 above) — do not
  assume a clean run proves the strip-marker highlight pipeline works; it proves nothing until
  `src/format/strip_marker.py` regains the three missing functions or the test is rewritten.
- `screenshot_panes.py`'s pane geometry (5 windows/10 panes) does not match any live
  `monitor_cc_*` session in this environment (all have 6 windows) — see Bug 1 above. Anyone
  asked to fix or extend this script should re-derive `PANE_TARGETS`/`PANE_LAYOUT` from the
  CURRENT tmux window list first, not from the old DOCS.md's Modules section (which still
  described the 5-window assumption as fact).
- The old `dev/display/DOCS.md` claimed `A_format_cache_tracker_proof.py` writes to
  `json/baseline_<timestamp>.json` — this was already stale before this pass (the actual
  output directory is `A_format_cache_tracker_proof_reports/`); the tracked file
  `dev/display/json/baseline_20260610_030639.json` is an orphaned artifact from whatever
  earlier version of the script used to write there. Not touched by this pass (not a comment,
  not a docstring, out of scope) but worth knowing before trusting that path.
- Frozen fixture directories (`/tmp/display_frozen_sessions/`, `/tmp/display_frozen_duallog/`)
  and the synthetic session JSONL (`/tmp/disp_fixtures/session1.jsonl`) were never staged and
  are throwaway for this session only.

## Salvage from dev/display/A_format_cache_tracker_proof.py

Docstring (module, lines 1-14):
```

Differential proof harness for format_cache_tracker decomposition.

Usage (from project root):
    ./venv/bin/python dev/display/A_format_cache_tracker_proof.py --mode capture
    ./venv/bin/python dev/display/A_format_cache_tracker_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- parse N session JSONLs, call format_cache_tracker on each, write 5-tuple to baseline JSON
    verify   -- call same inputs, assert byte-identical 5-tuple against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: format_cache_tracker(turns, ...) from src/format/token_format.py
Exercises all 3 extraction targets transitively: _render_expanded_call_lines, _compute_cache_viewport, _fmt_rl_reset_time.

```

---

## Salvage from dev/display/scan_jsonl_rules.py

Docstring (module, lines 2-17):
```
Scan a Claude Code session JSONL to find how loaded rules appear in system-reminders.

Purpose: Verify the exact pattern/format of "Contents of" lines in system-reminder
tags within tool_result content blocks. This tells us whether we can reliably parse
loaded rules (CLAUDE.md, .claude/rules/*.md) from the JSONL instead of relying on
the InstructionsLoaded hook (which has known bugs: #33275, #30973, #31017).

Usage:
    python3 dev/display/scan_jsonl_rules.py

Scans the most recent JSONL from the RAG project (not Monitor_CC, to avoid
self-referential noise from this session's own messages).

Output: All unique "Contents of" lines found in system-reminder tags,
with the message type and line number they appear in.

```

Comment (line 24):
```
# auto-discover newest project
```

Comment (line 61):
```
# Search through all content for system-reminder tags
```

Comment (line 68):
```
# Deduplicate
```

Comment (line 91):
```
# Extract: path and scope from "path/to/file.md (scope description):"
```

Comment (line 97):
```
# Determine [P] or [G]
```

---

## Salvage from dev/display/screenshot_panes.py

Docstring (module, lines 2-2):
```
Capture all 10 tmux panes of a running Monitor_CC session (5 windows) and combine into a single PNG.
```

Comment (line 10):
```
# --- INFRASTRUCTURE ---
```

Comment (lines 12-17):
```
# (window.pane, label) for each of the 10 panes across 5 windows:
#   Window 0 "main":    0.0=MAIN,    0.1=TOKENS
#   Window 1 "proxy":   1.0=PROXY,   1.1=METADATA
#   Window 2 "rules":   2.0=RULES,   2.1=HOOKS
#   Window 3 "workers": 3.0=WORKERS, 3.1=WORKER-PROXY, 3.2=WORKER-METADATA
#   Window 4 "debug":   4.0=WARNINGS
```

Comment (lines 35-36):
```
# Layout ratios: (x_start, y_start, width, height) as fractions of combined image
# 5 rows, one per window — each row occupies 20% of total height
```

Comment (lines 38-52):
```
# Row 0: Window 0 "main"    — main (70%) | tokens (30%)
# 0: main
# 1: tokens
# Row 1: Window 1 "proxy"   — proxy (70%) | metadata (30%)
# 2: proxy
# 3: metadata
# Row 2: Window 2 "rules"   — rules (50%) | hooks (50%)
# 4: rules
# 5: hooks
# Row 3: Window 3 "workers" — workers (34%) | worker-proxy (33%) | worker-metadata (33%)
# 6: workers
# 7: worker-proxy
# 8: worker-metadata
# Row 4: Window 4 "debug"   — warnings (100%)
# 9: warnings
```

Docstring (function `run`, lines 60-60):
```
Run subprocess, raise on failure, return stdout.
```

Comment (line 67):
```
# --- FUNCTIONS ---
```

Docstring (function `detect_session`, lines 70-70):
```
Auto-detect running monitor_cc_* session from tmux ls.
```

Docstring (function `get_pane_width`, lines 80-80):
```
Return pane width as string for termshot --columns. pane is 'window.pane' e.g. '0.0'.
```

Docstring (function `capture_pane_text`, lines 85-85):
```
Capture pane content including ANSI escapes to temp file, return path. pane is 'window.pane' e.g. '0.0'.
```

Docstring (function `render_pane_png`, lines 93-93):
```
Render ANSI text file to PNG via termshot, return output path.
```

Docstring (function `compose_layout`, lines 105-105):
```
Load 10 pane PNGs and compose into combined layout image.
```

Comment (line 119):
```
# --- ORCHESTRATOR ---
```

---

## Salvage from dev/display/test_hover_map.py

Docstring (module, lines 1-8):
```
Synthetic line_map assertion tests for expand-model correctness.

Verifies that after flatten: every visible row has exactly one phys_row in
line_map, phys_row increments monotonically, and no row is duplicated.

Usage (from project root):
    ./venv/bin/python dev/display/test_hover_map.py

```

Comment (line 25):
```
# Assert helper — prints PASS/FAIL and updates counts
```

Comment (line 36):
```
# Check line_map: monotonic rows, no duplicates, all in [1..pane_height-1]
```

Comment (line 46):
```
# Build minimal synthetic proxy entry dict
```

Comment (line 71):
```
# Build synthetic cache turn dicts (for grouping)
```

Comment (line 79):
```
# TESTS
```

Comment (line 94):
```
# All req keys should be in line_map
```

Comment (line 106):
```
# Expand entry 1 (req key = ('req', 1))
```

Comment (line 113):
```
# Critically: rows must start at ≥ 1 (turn headers before first req are key=None)
```

Comment (line 144):
```
# First, discover which row req for entry 0 lands on
```

Comment (line 150):
```
# Re-render with hover at that row
```

Comment (line 153):
```
# 0-indexed
```

Comment (line 155):
```
# Check adjacent rows are NOT hovered
```

Comment (lines 161-166):
```
# (2026-09, panesplit) test_workers_viewport_clipping / test_no_expanded_worker_overflow removed.
# Both exercised format_workers_block's outer viewport math over several SIMULTANEOUSLY stacked
# worker blocks -- a concern that no longer exists once the all-workers list is gone. The single
# remaining worker view's own viewport clipping is format_cache_tracker's, exercised the same way
# for every caller (token_pane.py, worker_tokens_pane.py); there is no separate outer-list
# composition step left to test here.
```

Comment (line 168):
```
# Task 1 — header-wrap tests
```

Comment (lines 174-176):
```
# Build a header that wraps at narrow pane width
# Simulate what _format_worker_proxy_header produces: 'WORKER-PROXY  [1*]alpha [2]beta [3]gamma [4]delta [5]epsilon'
# Use narrow pane (64 chars) so header wraps to ≥2 lines
```

Comment (line 184):
```
# First render to discover req(0) body row
```

Comment (lines 190-197):
```
# With single-line header (120 px pane), body_hover = terminal_hover - 1
# Simulate what worker_proxy_pane does after shift:
# line_map already contains body-relative rows from format_proxy_block.
# After shift by header_lines=1: terminal_row = body_row + 1
# After shift by header_lines=2: terminal_row = body_row + 2
# Assert: for narrow pane, req(0) body row same regardless (format_proxy_block is pane-width-aware)
# Key test: body_hover = terminal_hover - header_lines (not -1)
# Construct fake header of ~70 chars visible to force wrap at 64
```

Comment (lines 203-204):
```
# body_hover formula: terminal_hover - header_lines (must match req(0) body row)
# Simulate: terminal hover = req0_body_row + header_lines
```

Comment (line 211):
```
# Guard: when hover_row <= header_lines → body_hover must be None
```

Comment (line 220):
```
# Minimal header string with known visible length
```

Comment (line 222):
```
# forces wrap
```

Comment (line 228):
```
# Simulate the shift for narrow pane
```

Comment (line 233):
```
# Simulate shift by header_lines
```

Comment (line 238):
```
# Simulate shift by 1 (old behavior) for comparison
```

Comment (lines 244-250):
```
# (2026-09, panesplit) test_workers_pane_scroll_offset removed -- it exercised the outer
# multi-worker list's own bottom-anchored viewport math (format_workers_block), gone with the
# list. test_workers_scroll_reset_on_expand removed too -- it never called real worker_pane code
# to begin with (a hand-set `simulated_scroll_offsets` dict, not `worker_scroll_offsets` itself),
# so it had nothing genuine to retarget. The real successor concept -- scroll state resetting on
# a worker switch -- is asserted against real worker_tokens_pane.py code in
# dev/pane_search/p7_workers_pane_parity_test.py's worker-switch-reset test.
```

Comment (line 258):
```
# Running from a git worktree — navigate up to main repo (.claude/worktrees/<name>/../../../)
```

Comment (lines 270-274):
```
# Newest-first: current forwarded-log architecture reconstructs messages from
# <log_id>_forwarded.jsonl deltas; stripped-span content lives in the sibling
# <log_id>_stripped.jsonl overlay (attached to entries as _stripped_spans, mirroring
# pane.py's accumulate_dual_log wiring — NOT entry['stripped_msg_indices'], which
# _parse_forwarded_log always sets to [] for forwarded-reconstructed entries).
```

Comment (lines 299-300):
```
# Mirror pane.py's per-entry overlay wiring (_stripped_spans/_injected_spans +
# ownership lookups) so render_messages exercises the real production dual-color path.
```

---

## Salvage from dev/display/test_strip_markers.py

Docstring (module, lines 1-9):
```

Visual test script for strip_marker.py helper.

Usage (from repo root):
    ./venv/bin/python dev/display/test_strip_markers.py

Feeds synthetic proxy entries and session events through the strip-marker pipeline,
prints ANSI-colored output to terminal — no live proxy required.

```

Comment (line 26):
```
# ── helpers ─────────────────────────────────────────────────────────────────
```

Comment (line 34):
```
# ── synthetic data ───────────────────────────────────────────────────────────
```

Comment (lines 41-42):
```
# Pre-strip: user message whose content is [text_block(SR), tool_result_block]
# _summarize_content_for_log joins text + tool_result content → flat string
```

Comment (line 95):
```
# ── test 1: highlight_stripped ───────────────────────────────────────────────
```

Comment (line 124):
```
# ── test 1b: multi-line chunk — every split line must carry DIM_YELLOW_BG ────
```

Comment (lines 135-136):
```
# Lines 1, 2, 3 correspond to A, B, C (the chunk)
# PREFIX is line 0, chunk occupies lines 1-3, SUFFIX is line 4
```

Comment (line 143):
```
# "C" line
```

Comment (line 149):
```
# ── test 2: get_stripped_data ────────────────────────────────────────────────
```

Comment (line 167):
```
# ── test 3: build_tool_result_strip_lookup (waste_pane) ──────────────────────
```

Comment (line 179):
```
# ── test 4: build_tool_id_strip_lookup (main-pane) ───────────────────────────
```

Comment (line 188):
```
# ── test 5: warnings_pane scan simulation ────────────────────────────────────
```

Comment (line 191):
```
# Simulate what _scan_proxy_entries_for_errors does with msg_idx=2 (tool_result)
```

Comment (line 199):
```
# ── test 6: user_prompt timestamp bucket ─────────────────────────────────────
```

Comment (lines 202-203):
```
# "2026-04-21T10:00:00.000Z"
# "2026-04-21T10:00:00"
```

Comment (lines 207-208):
```
# Note: exact match on seconds — proximity matching handled by monitor._refresh_strip_cache
# scanning incrementally, so prompt naturally precedes next proxy entry it would match
```

---

## Salvage from dev/display/jsonl_exploration/01_map_message_types.py

Docstring (module, lines 2-12):
```
Map all message types in a Claude Code session JSONL.

For each message type: count, top-level keys, subtypes, isMeta distribution,
and one truncated example.

Usage:
    python3 dev/display/jsonl_exploration/01_map_message_types.py [path/to/session.jsonl]

Default: latest JSONL from RAG project.
Output: dev/display/jsonl_exploration/01_reports/message_types_<timestamp>.md

```

Comment (line 21):
```
# auto-discover newest project
```

Comment (line 29):
```
# Auto-discover: newest project directory
```

---

## Salvage from dev/display/jsonl_exploration/02_map_content_blocks.py

Docstring (module, lines 2-12):
```
Map content block types in a Claude Code session JSONL.

For each msg_type/content_type combination: count, keys, nested structure,
tool names, and one truncated example.

Usage:
    python3 dev/display/jsonl_exploration/02_map_content_blocks.py [path/to/session.jsonl]

Default: latest JSONL from RAG project.
Output: dev/display/jsonl_exploration/02_reports/content_blocks_<timestamp>.md

```

Comment (line 21):
```
# auto-discover newest project
```

Docstring (function `describe_nested`, lines 51-51):
```
Recursively describe nested structure.
```

Comment (line 94):
```
# Check tool_result for nested content
```

Comment (line 153):
```
# Summary table
```

Comment (line 196):
```
# Detailed sections
```

Comment (line 227):
```
# Show sub-blocks if any
```

---

## Salvage from dev/display/jsonl_exploration/03_scan_instructions.py

Docstring (module, lines 2-12):
```
Scan JSONL for anything rules/instructions-related.

Searches for: isMeta messages, "Contents of", CLAUDE.md references,
system-reminder tags, command tags, file-history-snapshot structure.

Usage:
    python3 dev/display/jsonl_exploration/03_scan_instructions.py [path/to/session.jsonl]

Default: latest JSONL from RAG project.
Output: dev/display/jsonl_exploration/03_reports/instructions_<timestamp>.md

```

Comment (line 22):
```
# auto-discover newest project
```

Docstring (function `extract_content_text`, lines 65-65):
```
Extract all text content from a message for pattern searching.
```

Comment (line 124):
```
# isMeta messages
```

Comment (line 135):
```
# file-history-snapshot
```

Comment (line 146):
```
# Pattern search across the raw line
```

Comment (line 154):
```
# Pattern hits summary
```

Comment (line 168):
```
# isMeta messages
```

Comment (line 190):
```
# file-history-snapshot
```

Comment (line 203):
```
# Show first snapshot example
```

Comment (line 217):
```
# Detailed pattern hits
```

---

## Salvage from dev/display/DOCS.md

Full previous content of dev/display/DOCS.md before the module-standards conformance rewrite
(Role prose reworded, Modules compressed to fit the word limits, and the Gotchas section
removed entirely since it is not part of the mandated DOCS.md format):

```markdown
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

### scan_jsonl_rules.py (120 LOC)

**Purpose:** Scans a Claude Code session JSONL for "Contents of" lines (loaded CLAUDE.md /
the rules-file markers under the user's .claude directory) to check whether rules/instructions data is present in session
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

### test_hover_map.py (358 LOC)

**Purpose:** Synthetic + real-log assertion suite for expand-model `line_map` correctness — every
visible row maps to exactly one `phys_row`, monotonic, no duplicates — plus a `render_messages`
`len(lines) == len(keys)` pairing check for the stripped-span dual-color overlay path against
real forwarded/stripped dual-log pairs. (2026-09) The four worker-list tests
(`test_workers_viewport_clipping`, `test_no_expanded_worker_overflow`,
`test_workers_pane_scroll_offset`, `test_workers_scroll_reset_on_expand`) were removed — they
exercised `format_workers_block`'s outer multi-worker viewport composition, which no longer
exists now that the all-workers list pane is gone (see `src/workers/DOCS.md`); the surviving
proxy-side tests are unaffected.
**Reads:** `src/logs/dual_log/*_forwarded.jsonl` + sibling `*_stripped.jsonl` (newest-first glob).
**Writes:** stdout PASS/FAIL lines + `Results: N passed, M failed` summary; exits 1 on failure.
**Called by:** none — run manually.
**Calls out:** `src.proxy_display.format` (`format_proxy_block`), `src.format.token_format`
(`format_cache_tracker`).

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
```

## Salvage from dev/display/jsonl_exploration/DOCS.md

Full previous content of dev/display/jsonl_exploration/DOCS.md before the module-standards
conformance rewrite (the Gotchas section removed entirely since it is not part of the mandated
DOCS.md format; Role/Modules text was already within the word limits and needed no rewording):

```markdown
# dev/display/jsonl_exploration/

## Role

Scripts that map the full structure of Claude Code session JSONL files, each exporting an MD
report. Touch this directory when investigating a new JSONL message/content shape not already
covered by `01`-`03`'s reports.

## Modules

### 01_map_message_types.py (186 LOC)

**Purpose:** For each top-level `type` value in a session JSONL: count, top-level keys, subtypes,
`isMeta` distribution, one truncated example.
**Reads:** a session JSONL path (argv[1], default hardcoded).
**Writes:** `01_reports/message_types_<timestamp>.md`.
**Called by:** none — run manually.

---

### 02_map_content_blocks.py (275 LOC)

**Purpose:** Deep-dive into `message.content` blocks — for each `msg_type`/`content_type`
combination: count, keys, nested structure, tool names, one truncated example.
**Reads:** a session JSONL path (argv[1], default hardcoded).
**Writes:** `02_reports/content_blocks_<timestamp>.md`.
**Called by:** none — run manually.

---

### 03_scan_instructions.py (268 LOC)

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
```

