# dev/pane_flicker/

## Role
Tests and measurements for the flicker fix on four panes: in-place synchronized frame write (M1), frozen-turn cache for the tokens panes (M2), frozen turns for the proxy panes (M3). Touch when changing the frame writer, turn cache, frozen turns or their pane wiring.

## Public Interface
No `__init__.py`. Each `*_test.py` and `m2_hover_timing.py` is run directly: `python3 dev/pane_flicker/<script>.py`. They compare the working tree against a `git archive` of a reference ref extracted to a temp directory. All `m1_*`/`m2_*` test and timing scripts pin the pre-fix commit `0ce370df` as the old tree.

## Flow
M1: the driver runs a real pane loop with seeded state inside a private tmux server (`tmux -L flk_m1_<pane>_<tree>`), the test sends hover/click/scroll/search keys, records raw bytes with `pipe-pane` and `capture-pane` after every step, and compares old against new. M2: the driver replays a scripted state sequence against the pane output builders with a real session JSONL and dumps every step; the test diffs old against new; the timing script measures hover builds.

## Modules

### m1_frame_e2e_driver.py (167 LOC)

**Purpose:** Runs one real pane loop against seeded synthetic state with refresh patched out, inside the caller's tmux pane.
**Reads:** argv (source root, pane name, project filter).
**Writes:** stdout frames (the pane's own output); the worker-selection IPC file for a private project filter.
**Called by:** `m1_frame_e2e_test.py`.
**Calls out:** `src.*` loaded via `importlib` from the given root.

---

### m1_frame_e2e_test.py (380 LOC)

**Purpose:** Old-versus-new end-to-end check of the frame write path for all four panes, with raw-byte assertions and cursor-hide checks.
**Reads:** `git archive 0ce370df`; tmux capture output.
**Writes:** `md/m1_frame_e2e_test.md` (fixed name, no wall clock in the body). Waits are deadline polls, never fixed sleeps. Each strand kills its tmux server in a `finally`, the temp directory is a `TemporaryDirectory`, and a strand that raises is reported as an aborted strand while its siblings finish.
**Called by:** none, manual.
**Calls out:** `tmux` (private sockets), `git`, `m1_frame_e2e_driver.py`.

---

### m1_strand_abort_test.py (52 LOC)

**Purpose:** Shows that a strand of the end-to-end test that cannot start is recorded as aborted, its tmux server killed, and the verdict fails.
**Reads:** nothing; provokes the condition with a nonexistent tree root and a 2 s deadline.
**Writes:** stdout only.
**Called by:** none, manual.
**Calls out:** `m1_frame_e2e_test.py`, `tmux` (private socket `flk_m1_tokens_new`).

---

### m2_state_sequence_driver.py (298 LOC)

**Purpose:** Replays a scripted state sequence on the tokens or worker-tokens pane and dumps output, line map, copy rows and navigation per step.
**Reads:** argv (root, pane, session JSONL, output path).
**Writes:** the JSON dump at the given path.
**Called by:** `m2_byte_identity_test.py`.
**Calls out:** `src.*` loaded via `importlib` from the given root.

---

### m2_byte_identity_test.py (114 LOC)

**Purpose:** Runs the sequence driver against old and new trees for two real sessions and both panes; asserts identical output and no turn recomputation on hover.
**Reads:** `git archive 0ce370df`; the two frozen session excerpts `fixtures/many_calls.jsonl` and `fixtures/many_turns.jsonl` (each cut at a line boundary to about 2 MB from a real session; the excerpt of the many-turns session keeps 7 turns, the many-calls excerpt keeps a 91-call turn).
**Writes:** `md/m2_byte_identity_test.md` (fixed name, no wall clock in the body).
**Called by:** none, manual.
**Calls out:** `git`, `m2_state_sequence_driver.py`.

---

### m2_hover_timing.py (123 LOC)

**Purpose:** Measures one hover-triggered pane build (CPU time), old versus new, on real sessions and a tenfold repeated variant.
**Reads:** `git archive 0ce370df`; session JSONLs.
**Writes:** `md/m2_hover_timing.md`.
**Called by:** none, manual.
**Calls out:** `git`; re-invokes itself as a child process per measurement.

---

### scenario_lib.py (246 LOC)

**Purpose:** Simulator replaying the proxy pane's data flow (growing logs in a temp dir, synthetic turns) and rendering through the pane body renderer.
**Reads:** the largest real dual-log quartet (env `PANE_FLICKER_LOG_DIR`, `PANE_FLICKER_STEM`).
**Writes:** a temp dir it removes; `render` returns a hash and the number of group renders.
**Called by:** `scenario_run.py`, `bench_hover_render.py`.
**Calls out:** `src.proxy_display.*` from the given root.

---

### scenario_run.py (245 LOC)

**Purpose:** Runs one M3 scenario per process and writes per-step hashes as JSON.
**Reads:** argv (root, scenario, out).
**Writes:** the JSON file.
**Called by:** `run_scenarios.py`.
**Calls out:** `scenario_lib.py`.

---

### run_scenarios.py (110 LOC)

**Purpose:** Runs every scenario against the old tree (extracted first) and the working tree in parallel; checks byte identity and render counts.
**Reads:** the per-process JSON files.
**Writes:** `md/run_scenarios.md`.
**Called by:** none, manual.
**Calls out:** `scenario_run.py`.

---

### bench_hover_render.py (87 LOC)

**Purpose:** Times hover renders in block or pane mode (pane mode needs a tty), with optional entry replication.
**Reads:** argv; the real log via `scenario_lib.py`.
**Writes:** a JSON file at `--out`.
**Called by:** none, manual.
**Calls out:** `scenario_lib.py`.

---

### observe_timestamp_order.py (90 LOC)

**Purpose:** Reports whether entry timestamps of forwarded logs or turn timestamps of transcripts were ever unsorted.
**Reads:** all `*_forwarded.jsonl` under the main `src/logs` and all transcripts under `~/.claude/projects`.
**Writes:** `md/observe_timestamp_order.md`.
**Called by:** none, manual.
**Calls out:** `src.jsonl`.

---

## State
No state persists between runs. Every strand uses its own tmux socket, temp directory and project filter.
