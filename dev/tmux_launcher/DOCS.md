# dev/tmux_launcher/

## Role
Regression harness for the window and pane layout of `src/tmux_launcher.py`. Add a script here when a launcher refactor needs a correctness proof of the argv sequence it issues. Prefer explicit named checks over a single opaque hash (see process-docs).

## Public Interface
No `__init__.py`. Entry points: `./venv/bin/python dev/tmux_launcher/layout_regression_checks.py` and `fallback_tripwire_checks.py`.

## Flow
Each scenario is a parallel fail-fast strand (strand runner in `dev/refactoring/`) that patches subprocess calls with a stateful fake tmux, drives the launcher and asserts named properties of the recorded argv. The failure-path script uses a real tmux server on a private socket.

## Modules

### layout_regression_checks.py (287 LOC)

**Purpose:** Regression checks for fresh launch, all-present restart and self-heal restart, asserting creation sequences, titles, bindings and zero-create invariants.
**Reads:** nothing external; fixtures are inline.
**Writes:** stdout per check and strand; `md/layout_regression_checks.md`; exits 1 if a strand aborts.
**Called by:** none; run before and after a launcher refactor.
**Calls out:** `src.tmux_launcher`, imported lazily to satisfy the dev-imports-src hook.

---

### fallback_tripwire_checks.py (131 LOC)

**Purpose:** Proves the failure paths of the launcher and the monitor janitor against a real tmux server on a private socket.
**Reads:** nothing external; the monitor root points at a temp dir.
**Writes:** temp dir with a sweep log; one throwaway tmux server, killed at the end.
**Called by:** none; run manually.
**Calls out:** `src.tmux_launcher`, `src.monitor_janitor` via `importlib`.

---

## State
No persistent state. Fakes are created per scenario and every scenario runs in its own process, so no patch leaks.
