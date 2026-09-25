# dev/workers/

## Role
Regression checks for `src/workers/` and the worker-selection readers in `src/proxy_display/`. Touch when changing worker status probes, the selection file IPC or the fields the worker list returns; not for pane rendering.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/workers/test_worker_probes.py`.

## Flow
The parent starts one subprocess per case, each case patches subprocess calls or the selection path with fakes (no tmux, no files outside a temp dir), and the parent prints one pass/fail line per strand.

## Modules

### test_worker_probes.py (126 LOC)

**Purpose:** Four parallel strands: selection write failure logged, selection read swallows only a missing file, worker status probe states, worker list carries no model field.
**Reads:** fakes only; an env var selects the source tree so the file can run against an older tree.
**Writes:** stdout only.
**Called by:** none; manual test.
**Calls out:** `src.workers`, `src.proxy_display.worker_proxy_pane`.

---

## State
None.
