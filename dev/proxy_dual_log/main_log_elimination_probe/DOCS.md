# dev/proxy_dual_log/main_log_elimination_probe/

## Role
Feasibility probe on eliminating the main proxy log in favor of the dual-log quartet. One unit of `dev/proxy_dual_log/`, split out because its files import only each other.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe/main_log_elimination_probe.py [session]`.

## Flow
A dual-log quartet plus the flat main proxy log of one session are loaded. Question A asks whether forwarded reconstruction matches the main-log payload, question B whether error extraction matches the tool-errors log. Both answers go into one dated Markdown report.

## Modules

### main_log_elimination_probe.py (45 LOC)

**Purpose:** CLI entry point of the feasibility probe.
**Reads:** a dual-log quartet plus the main proxy log of one session.
**Writes:** `main_log_elimination_probe_reports/<date>.md` at the area root, not in this subfolder.
**Called by:** none; manual one-off probe.
**Calls out:** `main_log_elimination_io.py`, `main_log_elimination_questions.py`, `main_log_elimination_report.py`.

---

### main_log_elimination_io.py (63 LOC)

**Purpose:** Root and log-path resolution, required-file check and JSONL loaders.
**Reads:** the monitor root env var or an area-relative fallback; log files.
**Writes:** nothing; exits 1 if a required log is missing.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** none.

---

### main_log_elimination_reconstruct.py (143 LOC)

**Purpose:** Delta-chain reconstruction, cache-control-aware element comparison and payload field classification tables.
**Reads:** nothing; pure transforms.
**Writes:** nothing.
**Called by:** `main_log_elimination_questions.py`, `main_log_elimination_report.py`.
**Calls out:** none.

---

### main_log_elimination_questions.py (149 LOC)

**Purpose:** Answers questions A and B against the main log, forwarded deltas, original entries and tool-error records.
**Reads:** entries passed in by the entry script.
**Writes:** nothing; returns result dicts.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

---

### main_log_elimination_report.py (216 LOC)

**Purpose:** Builds the Markdown report: match, divergence and field-classification sections and the migration verdict.
**Reads:** the result dicts of both questions.
**Writes:** the report file; returns its path.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

---

## State
No shared or mutating state. The I/O and report modules each resolve the area root independently. The root fallback without the env var is the project or worktree root and is deliberately not main-checkout-aware (see process-docs).
