# dev/system_load/tests/

## Role
Hermetic tests of `sysload`: fixed process-table fixtures go through the real classification, parsing, confirm and diff code. No real processes, tmux or files outside temp paths. Touch when changing a rule or a parser.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python dev/system_load/tests/test_classify.py` and `dev/system_load/tests/test_parsers_and_guards.py`.

## Flow
One strand per rule family or parser group, run in parallel through the shared strand runner; each strand stops at its first failed check. Reports go to `../md/<script>.md`.

## Modules

### fixtures.py (50 LOC)

**Purpose:** Builders for process rows and snapshot dicts using command-line shapes observed on the machine.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `test_classify.py`, `test_parsers_and_guards.py`.
**Calls out:** none.

---

### test_classify.py (233 LOC)

**Purpose:** Nine strands over the classification rules: system, caller exclusion, sessions, Firefox, proxies, task-file holders, MinerU protection, doubtful cases, action merging.
**Reads:** fixtures only.
**Writes:** `../md/test_classify.md`.
**Called by:** none; run manually.
**Calls out:** `dev.refactoring.strand_runner`.

---

### test_parsers_and_guards.py (129 LOC)

**Purpose:** Six strands over the output parsers, the confirm identity check, the diff outcomes, the report and the scan that the package contains no termination code.
**Reads:** literal samples captured from the machine; the package sources.
**Writes:** `../md/test_parsers_and_guards.md`.
**Called by:** none; run manually.
**Calls out:** `dev.refactoring.strand_runner`.

---

## State
None. Each strand builds its own fixtures in memory.
