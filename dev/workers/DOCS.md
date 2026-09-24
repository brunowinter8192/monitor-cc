# dev/workers/

## Role
Regression checks for `src/workers/` and the worker-selection readers in `src/proxy_display/`. Touch when changing worker status probes, the selection file IPC or the fields `list_workers` returns; not for pane rendering.

## Public Interface
No `__init__.py` in this directory. Entry path: `python3 dev/workers/test_worker_probes.py`.

## Flow
The parent starts one subprocess per case, each case patches `subprocess.run` or the selection path with fakes (no tmux, no real files outside a temp directory), and the parent prints one `PASS`/`FAIL` line per strand.

## Modules

### test_worker_probes.py (     102 LOC)

**Purpose:** Four parallel strands: selection write failure logged, selection read swallows only a missing file, worker status probe states (`unknown`, `working`, `idle`, `exited`), `list_workers` carries no `model` field.
**Reads:** Fakes only; `MCFIX_TREE` selects the source tree so the same file runs against an extracted older tree.
**Writes:** stdout only (`PASS`/`FAIL` per strand).
**Called by:** none — manual test.
**Calls out:** `src.workers` (`worker_selection`, `worker_tokens_pane`, `worker_tmux`), `src.proxy_display.worker_proxy_pane`.

---

## State
None.
