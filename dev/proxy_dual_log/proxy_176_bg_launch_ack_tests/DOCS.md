# dev/proxy_dual_log/proxy_176_bg_launch_ack_tests/

## Role
Unit tests for the CC 2.1.176 background-launch-ack strip across all 3 observed wordings. One unit
of `dev/proxy_dual_log/` (see the area's own DOCS.md); split out because its 5 files import only
each other.

## Public Interface
No `__init__.py` in this directory. Entry path: `./venv/bin/python
dev/proxy_dual_log/proxy_176_bg_launch_ack_tests/proxy_176_bg_launch_ack_tests.py`.

## Flow
Synthetic fixture texts (Wording 1/2/3 launch-ack variants) run through the real
`proxy.message_passes_simple`/`strip_inject_delta`/`diff_engine`/`strip_bg_launch_ack` strip
pipeline; each case asserts the expected replacement, false-positive safety, and attribution code,
printing PASS/FAIL to stdout.

## Modules

### proxy_176_bg_launch_ack_tests.py (72 LOC)

**Purpose:** CLI runner for the CC 2.1.176 background-launch-ack strip unit tests — imports and
sequences every test case.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.

---

### proxy_176_bg_launch_ack_fixtures.py (106 LOC)

**Purpose:** Wording 1/2/3 launch-ack fixture texts, their expected hold-message replacements, and
false-positive fixtures.
**Reads:** nothing — pure constants.
**Writes:** nothing.
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.
**Calls out:** none.

---

### proxy_176_bg_launch_ack_report.py (10 LOC)

**Purpose:** The shared `check()` PASS/FAIL-line printer and its ANSI color constants.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `_cases_w3.py`.
**Calls out:** none.

---

### proxy_176_bg_launch_ack_cases.py (256 LOC)

**Purpose:** Wording 1/2 launch-ack replacement, false-positive, and attribution tests for the
background-launch-ack strip.
**Reads:** nothing — synthetic fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops`, `.strip_vocab`.

---

### proxy_176_bg_launch_ack_cases_w3.py (172 LOC)

**Purpose:** Wording 3 (auto-backgrounded-on-timeout) tests plus the full-replacement-span-shape
and main-vs-worker wording pins.
**Reads:** nothing — synthetic fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `.strip_inject_delta`, `.diff_engine`, `.logging`,
`.rule_ops`, `.strip_vocab`, `.strip_bg_launch_ack`.

---

## State
No shared or mutating state across modules. `proxy_176_bg_launch_ack_tests.py` resolves
`_AREA_ROOT`/`_PROJECT_ROOT` (by walking up from `__file__` until the directory named
`proxy_dual_log` is found) once at import time, solely to put `_PROJECT_ROOT/src` on `sys.path` so
`proxy.*` imports resolve; nothing else is mutable.
