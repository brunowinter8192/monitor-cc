# dev/monitor_root/

## Role
Tests for the single repo-root resolver `src/monitor_root.py` and for the modules that report through it. Touch this directory when the resolver or one of its callers changes; the proxy live-copy layout is tested in `dev/proxy/`.

## Public Interface
No `__init__.py`. `test_monitor_root.py` is its own entry point: `python3 dev/monitor_root/test_monitor_root.py`.

## Flow
Each case runs in its own subprocess (parallel), builds a temp directory and fake reporters, and prints PASS/FAIL; the parent prints a case count and exits non-zero on any failure.

## Modules

### test_monitor_root.py (198 LOC)

**Purpose:** Proves env-wins, computed-is-repo-root, empty env as unset, missing-directory raise, report-once, a second env var name, and the reporter wiring of `monitor_janitor`, `proxy_display`, `ram_audit`, `dual_log_cli` and the menubar.
**Reads:** the repo sources; nothing persistent.
**Writes:** nothing outside temp directories — stdout only.
**Called by:** none — manual test.
**Calls out:** `src.monitor_root`, `src.monitor_janitor`, `src.proxy_display`, `src.ram_audit`, `src.dual_log_cli`.

---

## State
None.
