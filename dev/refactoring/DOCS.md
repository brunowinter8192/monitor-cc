# dev/refactoring/

## Role
Holds the reports produced while refactoring this project against the code standard. Touch it when a refactor pass produces a finding list that a later session has to act on. Do not put refactor scripts here; the passes are driven by workers, not by committed tooling.

## Public Interface
No `__init__.py` and no `.py` modules. The directory is report storage only.

## Flow
A refactor pass reads `src/` or `dev/`, a worker writes its finding list to `md/`, and a later session reads that list and decides what to change.

## Modules

None. This directory holds no Python.

---

## State
No state. `md/` holds dated report files, each written once and never mutated.
