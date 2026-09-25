# dev/menubar/

## Role
Byte-identity harnesses for `src/menubar/` module splits, plus parallel strands proving the phase 5 fallback and tripwire changes against a pristine source tree for before/after comparison. Add a script here when a menubar refactor needs a proof not covered by sibling dev areas.

## Public Interface
No `__init__.py`. Entry paths: the three `*_byte_identity.py` scripts, and `dev/menubar/p5_run_all.py`, which runs all phase 5 strands in parallel.

## Flow
Each identity script imports its `src/menubar/` target via `importlib`, drives it against synthetic or patched-I/O fixtures and hashes the resulting state to one stdout line. Each phase 5 strand asserts its group's behavior and prints pass/fail and digest lines.

## Modules

### discover_byte_identity.py (152 LOC)

**Purpose:** Identity harness for the project-directory scan of `discover.py`: patches every I/O boundary and hashes four scenarios.
**Reads:** nothing external; inline fixtures.
**Writes:** stdout only (hash line).
**Called by:** none; verification aid that asserts nothing, run before and after a change.
**Calls out:** `src.menubar.discover`, imported lazily.

---

### model_controller_byte_identity.py (169 LOC)

**Purpose:** Identity harness for the model controller: hashes a sandboxed persistence cycle and a headless UI subview dump.
**Reads:** the real proxy rules file under the user's shared-rules directory (read-only seed), so a changed file changes the hash.
**Writes:** stdout only, plus its own temp dir.
**Called by:** none; verification aid, run before and after a change.
**Calls out:** `src.menubar.model_controller`, `src.menubar.model_selection`, imported lazily.

---

### panel_manager_byte_identity.py (176 LOC)

**Purpose:** Identity harness for the panel manager: hashes a synthetic multi-project rebuild and an in-place update, dumping every grid row and lookup map.
**Reads:** nothing external; synthetic session data.
**Writes:** stdout only (hash line or a skip line plus a smoke line).
**Called by:** none; verification aid, run before and after a change.
**Calls out:** `src.menubar.panel_manager`, `src.menubar.discover`, imported lazily.

---

### p5_common.py (49 LOC)

**Purpose:** Shared helpers of the phase 5 strands: source-tree switch, module import, stderr capture, digest and check.
**Reads:** an env var selecting an alternate source tree.
**Writes:** nothing.
**Called by:** the `p5_g*` strands.
**Calls out:** `src.menubar.*` via `importlib`.

---

### p5_g1_log.py (57 LOC)

**Purpose:** Strand for the menubar log module: append and retention unchanged, write and cleanup failures reach stderr.
**Reads:** a temp directory it creates.
**Writes:** stdout pass/fail lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.menubar_log`.

---

### p5_g2_state.py (151 LOC)

**Purpose:** Strand for state and config readers and writers: missing file silent, unreadable file logged, unreadable rules file never overwritten.
**Reads:** temp directories with synthetic JSON.
**Writes:** stdout pass/fail and digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** the settings, selection, cache, scheduler, controller, hook writer and paths modules of `src.menubar`.

---

### p5_g3_app.py (145 LOC)

**Purpose:** Strand for app wiring, restart route, panel cycle errors and Carbon hotkey failures, driven by fake objects.
**Reads:** nothing external.
**Writes:** stdout pass/fail lines.
**Called by:** `p5_run_all.py`.
**Calls out:** the app, panel lifecycle and hotkey modules of `src.menubar`.

---

### p5_g4_detection.py (100 LOC)

**Purpose:** Strand for desktop detection: key handling, route logging on change, removed last-known-good state, digest-compared normal results.
**Reads:** nothing external; fake CoreGraphics dicts.
**Writes:** stdout pass/fail and digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.desktop_detection`.

---

### p5_g5_discover.py (143 LOC)

**Purpose:** Strand for session discovery, the discovery worker and a panel guard: skipped projects logged once, worker loop error handling.
**Reads:** temp JSONL files.
**Writes:** stdout pass/fail and digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.discover`, `src.menubar.discovery_worker`; AST read of `panel.py`.

---

### p5_g6_caches.py (304 LOC)

**Purpose:** Strand for the process cache, ghostty, background timer and orphan modules: subprocess failures logged, unknown activity is None.
**Reads:** temp directories; fake subprocess results.
**Writes:** stdout pass/fail and digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** the proc cache, ghostty, timer, orphan and discover modules of `src.menubar`.

---

### p5_g7_model.py (74 LOC)

**Purpose:** Strand for the model controller: every cycle handler dispatches and refreshes as before, failures land in the menubar log.
**Reads:** nothing external; fake selection and buttons.
**Writes:** stdout pass/fail lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.model_controller`.

---

### p5_g8_system.py (109 LOC)

**Purpose:** Strand for the system and skill-discovery modules: singleton lock, python resolution, viewer tty, skill fallback routes.
**Reads:** temp directories.
**Writes:** stdout pass/fail and digest lines.
**Called by:** `p5_run_all.py`.
**Calls out:** `src.menubar.system`, `src.menubar.skill_discovery`.

---

### p5_run_all.py (45 LOC)

**Purpose:** Runs all phase 5 strands in parallel subprocesses; each stops at its first failing check, siblings finish, the parent reports aborted strands.
**Reads:** nothing.
**Writes:** stdout summary line per strand.
**Called by:** none; run manually.
**Calls out:** `subprocess`, `concurrent.futures`.

---

## State
No persistent state. Identity scripts build fresh throwaway fixtures per process; only the model-controller script writes files, inside a temp dir it discards. Phase 5 strands point the menubar log and the module under test at a temp dir and never touch the real app-support directory.
