# dev/pane_flicker/

## Role
Tests and measurements for the flicker fix on the tokens, worker-tokens, proxy and worker-proxy panes: the in-place synchronized frame write (M1) and the frozen-turn cache for the tokens panes (M2). Touch when changing `src/frame_writer.py`, `src/format/turn_cache.py`, or the frame-write / turn-cache wiring in the four panes.

## Public Interface
No `__init__.py`. Each `*_test.py` and `m2_hover_timing.py` is run directly: `python3 dev/pane_flicker/<script>.py`. They compare the working tree against a `git archive` of a reference ref extracted to a temp directory. all `m1_*`/`m2_*` test and timing scripts pin the pre-fix commit `0ce370df` as the old tree.

## Flow
M1: the driver runs a real pane loop with seeded state inside a private tmux server (`tmux -L flk_m1_<pane>_<tree>`), the test sends hover/click/scroll/search keys, records raw bytes with `pipe-pane` and `capture-pane` after every step, and compares old against new. M2: the driver replays a scripted state sequence against `_build_*_output()` with a real session JSONL and dumps every step; the test diffs old against new; the timing script measures hover builds.

## Modules

### m1_frame_e2e_driver.py (141 LOC)

**Purpose:** Runs one real pane loop against seeded synthetic state with refresh patched out, inside the caller's tmux pane.
**Reads:** argv (source root, pane name, project filter).
**Writes:** stdout frames (the pane's own output); the worker-selection IPC file for a private project filter.
**Called by:** `m1_frame_e2e_test.py`.
**Calls out:** `src.*` loaded via `importlib` from the given root.

---

### m1_frame_e2e_test.py (296 LOC)

**Purpose:** Old-vs-new end-to-end check of the frame write path for all four panes, plus raw-byte assertions (no 2J/3J, sync pairs) and cursor-hide checks (`#{cursor_flag}` per step, during a hover burst, after `respawn-pane`, after Ctrl+C).
**Reads:** `git archive integration`; tmux capture output.
**Writes:** `md/m1_frame_e2e_test.md`.
**Called by:** none, manual.
**Calls out:** `tmux` (private sockets), `git`, `m1_frame_e2e_driver.py`.

---

### m2_state_sequence_driver.py (252 LOC)

**Purpose:** Replays a scripted state sequence (hover, expand, scroll, search, width change, feedback, growth, reset) on the tokens or worker-tokens pane and dumps output, line map, copy rows and nav per step.
**Reads:** argv (root, pane, session JSONL, output path).
**Writes:** the JSON dump at the given path.
**Called by:** `m2_byte_identity_test.py`.
**Calls out:** `src.*` loaded via `importlib` from the given root.

---

### m2_byte_identity_test.py (96 LOC)

**Purpose:** Runs the sequence driver against old and new trees for two real sessions and both panes; asserts identical output and that hover steps recompute zero turns.
**Reads:** `git archive integration`; the two session JSONLs under `~/.claude/projects`.
**Writes:** `md/m2_byte_identity_test.md`.
**Called by:** none, manual.
**Calls out:** `git`, `m2_state_sequence_driver.py`.

---

### m2_hover_timing.py (112 LOC)

**Purpose:** Measures one hover-triggered pane build (CPU time) old vs new on real sessions and a 10x repeated variant.
**Reads:** `git archive integration`; session JSONLs.
**Writes:** `md/m2_hover_timing.md`.
**Called by:** none, manual.
**Calls out:** `git`; re-invokes itself as a child process per measurement.

---

## State
No state persists between runs. Every strand uses its own tmux socket, temp directory and project filter.
