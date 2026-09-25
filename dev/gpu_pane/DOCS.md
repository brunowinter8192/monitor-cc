# dev/gpu_pane/

## Role
Regression harness for `src/gpu_pane/`: a byte-identity hash for refactors and failure-path checks. Add a script here when a `src/gpu_pane/` refactor needs a before/after proof not covered by `dev/click_ui/` or `dev/pane_error_log/`.

## Public Interface
No `__init__.py`. Entry points are direct invocations: `./venv/bin/python dev/gpu_pane/render_byte_identity.py` and `dev/gpu_pane/fallback_tripwire_checks.py`.

## Flow
Synthetic fixtures are built in-script, the real pane renderer is driven at two widths with and without a search query, and the output is hashed (identity harness) or asserted (failure-path checks).

## Modules

### render_byte_identity.py (115 LOC)

**Purpose:** Hashes the rendered pane output and its button regions across many synthetic scenarios so two runs before and after a change can be compared.
**Reads:** nothing external; synthetic fixtures built in-script.
**Writes:** stdout only (one hash line).
**Called by:** none; run manually before and after a refactor.
**Calls out:** `src.gpu_pane.pane`, imported lazily to satisfy the dev-imports-src hook.

---

### fallback_tripwire_checks.py (168 LOC)

**Purpose:** Proves the traced-skip, retry and tripwire paths of `src/gpu_pane/` with a fake `rag-cli` on PATH.
**Reads:** nothing external; state files and the pane error log live in a temp dir.
**Writes:** temp dir; the gpu pane module's own log in this checkout.
**Called by:** none; run manually. The four check groups run as parallel strands.
**Calls out:** `src.gpu_pane.status`, `.gpu_actions`, `.gpu_render`, `src.pane_error_log` (via `importlib`); the strand runner and check helper in `dev/refactoring/`.

---

## State
No persistent state. The checks patch the clock and the toggle state during a run and restore them afterward. The identity harness is a verification aid, not a test: it asserts nothing.
