# dev/system_load/

## Role
Mac-wide load snapshot tool `sysload` plus its skill draft. It measures every process, attributes it to our tooling and sorts it into killable, doubtful or essential. It never terminates anything. Touch when changing the classification rules or the collectors; not for menubar or janitor behavior.

## Public Interface
`sysload/__init__.py` is empty. Entry path: `PYTHONPATH=dev/system_load python3 -m sysload snapshot|confirm|diff` (the package directory is the only location dependency). `SKILL.md` is the draft of the skill that drives it; `verify_against_ps.py` is the live cross-check.

## Flow
`snapshot` collects ps, top, tmux, lsof and system numbers, classifies them with pure rules, prints a report and writes a JSON result. `confirm` re-checks one target's identity right before a termination done by the caller. `diff` compares two result files.

## Modules

### sysload/config.py (61 LOC)

**Purpose:** Shared thresholds, protect and killable lists, path prefixes, group and action names.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** every other module in `sysload/`.
**Calls out:** none.

---

### sysload/collect.py (178 LOC)

**Purpose:** All process, tmux, lsof, top and memory collection and the parsing of their output.
**Reads:** `ps`, `top`, `tmux`, `lsof`, `memory_pressure`, `sysctl`, task output file stats.
**Writes:** nothing.
**Called by:** `sysload/snapshot.py`, `sysload/confirm.py`.
**Calls out:** none.

---

### sysload/classify.py (485 LOC)

**Purpose:** Pure classification of a snapshot dict into killable, doubtful and essential rows, kill actions and a summary.
**Reads:** the snapshot dict only.
**Writes:** nothing.
**Called by:** `sysload/snapshot.py`, `tests/`.
**Calls out:** none.

---

### sysload/render.py (97 LOC)

**Purpose:** Text report of a classified result.
**Reads:** the result dict.
**Writes:** nothing; returns text.
**Called by:** `sysload/snapshot.py`, `tests/`.
**Calls out:** none.

---

### sysload/snapshot.py (85 LOC)

**Purpose:** `snapshot` command: collect, classify, write the JSON result, print the report.
**Reads:** live machine state through `collect.py`.
**Writes:** `/tmp/sysload/<timestamp>.json` or the `--out` file; stdout.
**Called by:** `sysload/cli.py`.
**Calls out:** none.

---

### sysload/confirm.py (45 LOC)

**Purpose:** `confirm` command: read-only identity check of one pid start time or one tmux session creation stamp.
**Reads:** `ps -p`, `tmux list-sessions`.
**Writes:** stdout `ok` or `changed`; exit code 0 or 1.
**Called by:** `sysload/cli.py`, `tests/`.
**Calls out:** none.

---

### sysload/diff.py (81 LOC)

**Purpose:** `diff` command: system and group deltas, per-action outcome and new killable actions between two result files.
**Reads:** two JSON result files.
**Writes:** stdout.
**Called by:** `sysload/cli.py`, `tests/`.
**Calls out:** none.

---

### sysload/cli.py (34 LOC)

**Purpose:** Subcommand dispatch of the package.
**Reads:** the argument list.
**Writes:** usage text on stderr.
**Called by:** `sysload/__main__.py`.
**Calls out:** none.

---

### sysload/__main__.py (7 LOC)

**Purpose:** Module entry for `python3 -m sysload`.
**Reads:** `sys.argv`.
**Writes:** the process exit code.
**Called by:** the interpreter.
**Calls out:** none.

---

### verify_against_ps.py (109 LOC)

**Purpose:** Compares a live snapshot result against an independent `ps` dump and independent tmux and Firefox listings.
**Reads:** a result JSON and a saved `ps` dump given as arguments; live `tmux` and `ps`.
**Writes:** stdout; `md/verify_against_ps.md`.
**Called by:** none; run manually.
**Calls out:** none.

---

## Sub-directories

- `tests/`: hermetic tests for the classification, parsers, confirm, diff and the no-termination guard. See its own `DOCS.md`.

## State
No persistent state in the tool. Result files live under `/tmp/sysload/`. `md/` holds the test and verification reports, one fixed-name file per script.
