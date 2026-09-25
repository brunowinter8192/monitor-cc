# dev/model_selector/

## Role
Verification scripts for the menubar's Models tab in `src/menubar/` and the launcher, worker-spawn and hook changes that make its config file take effect at proxy startup. Touch when changing model selection, the panel tab ring or the launcher precedence chain.

## Public Interface
No `__init__.py`. Each script is its own entry point, run directly (Python scripts with `python3`, the launcher check with `bash`).

## Flow
Synthetic payloads, temp paths or in-memory fixtures go in. Each script drives real production code (or mirrors the launcher parse loop in bash) and asserts invariants. Output is stdout plus a report under `md/` with a fixed name and no clock value in the body.

## Modules

### verify_hook_writer_split.py (85 LOC)

**Purpose:** Regression guard for the hook-state half of the menubar hook writer: status transitions and no queue-file side effect.
**Reads:** nothing persistent; builds its own temp dir.
**Writes:** `md/verify_hook_writer_split.md`.
**Called by:** none; re-run after hook writer changes.
**Calls out:** `src/menubar/hook_writer.py` via `importlib`.

---

### verify_model_cycle_and_io.py (315 LOC)

**Purpose:** Regression guard for model-selection cycle logic and its selection and proxy-rules JSON read-modify-write I/O, as parallel fail-fast strands.
**Reads:** nothing persistent; temp paths or in-memory fixtures.
**Writes:** `md/verify_model_cycle_and_io.md`.
**Called by:** none; re-run after selection I/O changes.
**Calls out:** `src.menubar.model_selection`; the strand runner in `dev/refactoring/`.

---

### verify_four_tab_ring.py (148 LOC)

**Purpose:** Regression guard for the four-tab keyboard ring, driving the real unmocked ring functions against a fake app wrapping real panel controllers.
**Reads:** nothing persistent; HOME is redirected to a temp dir.
**Writes:** `md/verify_four_tab_ring.md`.
**Called by:** none; needs a macOS WindowServer session and mutates the desktop, so do not run casually.
**Calls out:** the menubar panel and tab controller modules in `src/menubar/`, `Foundation`, `dev/session_launcher/test_env.py`.

---

### verify_launcher_model_precedence.sh (163 LOC)

**Purpose:** Dry run of the launcher's model precedence chain: explicit flag, then config-file key, then nothing injected.
**Reads:** nothing persistent outside its own temp dir.
**Writes:** `md/verify_launcher_model_precedence.md`.
**Called by:** none; re-run after launcher precedence changes.
**Calls out:** `jq`; the parse loop of `src/claude_proxy_start.sh` (mirrored, not sourced).

---

### verify_hook17_removal.py (96 LOC)

**Purpose:** Confirms a retired hook's removal: file gone, no longer registered, stale-hook sweep removes a dead entry and keeps a live one.
**Reads:** nothing persistent; synthetic dict.
**Writes:** `md/verify_hook17_removal.md`.
**Called by:** none; re-run if the sweep changes.
**Calls out:** `src/hooks/hook_setup.py`.

---

## State
No persistent state. Every script builds and discards its own fixture and never touches the real model-selection file or Claude settings.
