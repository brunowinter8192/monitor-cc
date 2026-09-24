# dev/pane_flicker/

## Role
Tests and measurements for the flicker fix on the tokens, worker-tokens, proxy and worker-proxy panes: the in-place synchronized frame write (M1) and the frozen-turn cache for the tokens panes (M2), and the frozen turns of the proxy panes (M3). Touch when changing `src/frame_writer.py`, `src/format/turn_cache.py`, `src/proxy_display/frozen_turns.py`, or the frame-write / turn-cache wiring in the four panes.

## Public Interface
No `__init__.py`. Each `*_test.py` and `m2_hover_timing.py` is run directly: `python3 dev/pane_flicker/<script>.py`. They compare the working tree against a `git archive` of a reference ref extracted to a temp directory. All `m1_*`/`m2_*` test and timing scripts pin the pre-fix commit `0ce370df` as the old tree.

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

### m1_frame_e2e_test.py (342 LOC)

**Purpose:** Old-vs-new end-to-end check of the frame write path for all four panes, plus raw-byte assertions (no 2J/3J, sync pairs) and cursor-hide checks (`#{cursor_flag}` per step, during a hover burst, after `respawn-pane`, after Ctrl+C).
**Reads:** `git archive 0ce370df`; tmux capture output.
**Writes:** `md/m1_frame_e2e_test.md` (fixed name, no wall clock in the body). Waits are deadline polls (`wait_quiet`: raw output and screen unchanged for 0.6 s; `start_pane`: first frame marker; `wait_flag`), never fixed sleeps. Each strand kills its tmux server in a `finally`, the temp directory is a `TemporaryDirectory`, and a strand that raises is reported as an aborted strand while its siblings finish.
**Called by:** none, manual.
**Calls out:** `tmux` (private sockets), `git`, `m1_frame_e2e_driver.py`.

---

### m1_strand_abort_test.py (43 LOC)

**Purpose:** Shows that a strand of `m1_frame_e2e_test.py` which cannot start is recorded as aborted, its tmux server is killed, and the verdict fails instead of the run crashing.
**Reads:** nothing; provokes the condition with a nonexistent tree root and a 2 s deadline.
**Writes:** stdout only.
**Called by:** none, manual.
**Calls out:** `m1_frame_e2e_test.py`, `tmux` (private socket `flk_m1_tokens_new`).

---

### m2_state_sequence_driver.py (252 LOC)

**Purpose:** Replays a scripted state sequence (hover, expand, scroll, search, width change, feedback, growth, reset) on the tokens or worker-tokens pane and dumps output, line map, copy rows and nav per step.
**Reads:** argv (root, pane, session JSONL, output path).
**Writes:** the JSON dump at the given path.
**Called by:** `m2_byte_identity_test.py`.
**Calls out:** `src.*` loaded via `importlib` from the given root.

---

### m2_byte_identity_test.py (97 LOC)

**Purpose:** Runs the sequence driver against old and new trees for two real sessions and both panes; asserts identical output and that hover steps recompute zero turns.
**Reads:** `git archive 0ce370df`; the two frozen session excerpts `fixtures/many_calls.jsonl` and `fixtures/many_turns.jsonl` (each cut at a line boundary to about 2 MB from a real session; the excerpt of the many-turns session keeps 7 turns, the many-calls excerpt keeps a 91-call turn).
**Writes:** `md/m2_byte_identity_test.md` (fixed name, no wall clock in the body).
**Called by:** none, manual.
**Calls out:** `git`, `m2_state_sequence_driver.py`.

---

### m2_hover_timing.py (112 LOC)

**Purpose:** Measures one hover-triggered pane build (CPU time) old vs new on real sessions and a 10x repeated variant.
**Reads:** `git archive 0ce370df`; session JSONLs.
**Writes:** `md/m2_hover_timing.md`.
**Called by:** none, manual.
**Calls out:** `git`; re-invokes itself as a child process per measurement.

---

### scenario_lib.py (246 LOC)

**Purpose:** `Sim` replays the proxy pane's data flow (growing forwarded/stripped/injected/response logs in a temp dir, synthetic turns) and renders through `_render_and_scroll_body`.
**Reads:** the largest real dual-log quartet (env `PANE_FLICKER_LOG_DIR`, `PANE_FLICKER_STEM`).
**Writes:** a temp dir it removes; `render` returns a hash and the number of group renders.
**Called by:** `scenario_run.py`, `bench_hover_render.py`.
**Calls out:** `src.proxy_display.*` from the given root.

---

### scenario_run.py (238 LOC)

**Purpose:** One M3 scenario (hover, grow, late response, late overlay, expand, search, width, copy feedback, reparse, unsorted turns, tripwire) per process, writes per-step hashes as JSON.
**Reads:** argv (root, scenario, out).
**Writes:** the JSON file.
**Called by:** `run_scenarios.py`.
**Calls out:** `scenario_lib.py`.

---

### run_scenarios.py (80 LOC)

**Purpose:** Runs every scenario against the old tree (`/tmp/pf_old`, a `git archive` of the pre-M3 commit, must be extracted first) and the working tree in parallel; checks byte identity and group-render counts.
**Reads:** the per-process JSON files.
**Writes:** `md/run_scenarios.md`.
**Called by:** none, manual.
**Calls out:** `scenario_run.py`.

---

### bench_hover_render.py (81 LOC)

**Purpose:** Times hover renders (`--mode block` for `format_proxy_block`, `--mode pane` for `_build_proxy_output`, needs a tty), optional `--scale` replicates entries.
**Reads:** argv; the real log via `scenario_lib.py`.
**Writes:** a JSON file at `--out`.
**Called by:** none, manual.
**Calls out:** `scenario_lib.py`.

---

### observe_timestamp_order.py (66 LOC)

**Purpose:** Reports whether entry timestamps of forwarded logs or turn timestamps of transcripts were ever unsorted.
**Reads:** all `*_forwarded.jsonl` under the main `src/logs` and all transcripts under `~/.claude/projects`.
**Writes:** `md/observe_timestamp_order.md`.
**Called by:** none, manual.
**Calls out:** `src.jsonl`.

---

## State
No state persists between runs. Every strand uses its own tmux socket, temp directory and project filter.
