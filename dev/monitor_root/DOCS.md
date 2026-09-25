# dev/monitor_root/

## Role
Tests for the single repo-root resolver `src/monitor_root.py` and for the modules that report through it. Touch when the resolver or one of its callers changes; the proxy live-copy layout is tested in `dev/proxy/`.

## Public Interface
No `__init__.py`. Entry path: `python3 dev/monitor_root/test_monitor_root.py`.

## Flow
Each case runs in its own parallel subprocess, builds a temp directory and fake reporters and prints pass/fail; the parent prints a case count and exits non-zero on any failure.

## Modules

### test_monitor_root.py (210 LOC)

**Purpose:** Proves env precedence, computed root, empty env as unset, missing-directory raise, report-once and the reporter wiring of the callers.
**Reads:** the repo sources; nothing persistent.
**Writes:** nothing outside temp directories; stdout only.
**Called by:** none; manual test.
**Calls out:** `src.monitor_root`, `src.monitor_janitor`, `src.proxy_display`, `src.ram_audit`, `src.dual_log_cli`.

---

## State
None.
