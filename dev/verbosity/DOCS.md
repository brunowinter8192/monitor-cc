# dev/verbosity/

## Role
Holds analysis of redundancy in this assistant's chat output, applying a process-efficiency measurement to Opus turn exchanges, plus the frozen extraction it ran against. The clustering is a manual semantic judgment, not a reusable pipeline.

## Public Interface
No `__init__.py`. Entry point: `python3 dev/verbosity/extract_turns.py`.

## Flow
The extractor reads real session JSONLs, reconstructs Opus turns and writes numbered exchanges to a fixed scratch path. The frozen corpus and its manual clustering live under `corpus/` and `md/`.

## Modules

### extract_turns.py (71 LOC)

**Purpose:** Reconstructs Opus turns from session JSONLs, splits them into numbered exchanges and keeps turns with many exchanges.
**Reads:** session JSONLs under the user's Claude projects directory (hardcoded path).
**Writes:** a fixed scratch path under the system temp directory.
**Called by:** none; manual CLI. Re-running reads the live sessions, not the frozen copies.
**Calls out:** none; stdlib only.

---

## State
None. The corpus files are frozen snapshots; do not regenerate them without a new dated report (see process-docs).
