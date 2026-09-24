# dev/proxy_dual_log/proxy_176_bg_launch_ack_tests/

## Role
Unit tests for the CC 2.1.176 background-launch-ack strip across all three observed wordings. One unit of `dev/proxy_dual_log/`, split out because its files import only each other.

## Public Interface
No `__init__.py`. Entry path: `./venv/bin/python dev/proxy_dual_log/proxy_176_bg_launch_ack_tests/proxy_176_bg_launch_ack_tests.py`.

## Flow
Synthetic fixture texts of the three wordings run through the real proxy strip pipeline. Each case asserts the expected replacement, false-positive safety and attribution code and prints pass/fail to stdout.

## Modules

### proxy_176_bg_launch_ack_tests.py (77 LOC)

**Purpose:** CLI runner that imports and sequences every test case.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** none; manual CLI.
**Calls out:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py`.

---

### proxy_176_bg_launch_ack_fixtures.py (106 LOC)

**Purpose:** Fixture texts of the three wordings, their expected replacements and false-positive fixtures.
**Reads:** nothing; constants.
**Writes:** nothing.
**Called by:** both case modules.
**Calls out:** none.

---

### proxy_176_bg_launch_ack_report.py (8 LOC)

**Purpose:** Shared pass/fail line printer with its color codes.
**Reads:** nothing.
**Writes:** stdout only.
**Called by:** both case modules.
**Calls out:** none.

---

### proxy_176_bg_launch_ack_cases.py (256 LOC)

**Purpose:** Replacement, false-positive and attribution tests for wordings 1 and 2.
**Reads:** nothing; fixtures module.
**Writes:** stdout only.
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** the message-pass, delta, diff, logging, rule and vocab modules of `src/proxy`.

---

### proxy_176_bg_launch_ack_cases_w3.py (172 LOC)

**Purpose:** Wording 3 (auto-backgrounded on timeout) tests plus span-shape and main-versus-worker wording pins.
**Reads:** nothing; fixtures module.
**Writes:** stdout only.
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** the same `src/proxy` modules plus the launch-ack strip module.

---

## State
No shared or mutating state. The runner resolves the project root once at import time solely to put `src` on the path for the proxy imports.
