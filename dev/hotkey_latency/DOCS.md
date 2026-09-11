# dev/hotkey_latency/

## Role

Measurement tooling for menubar hotkey lag (Cmd+K/L/1..9 intermittent slow response). Verifies
the Carbon `GetEventTime` technique and parses the `[latency]` instrumentation
`src/menubar/app.py`, `hotkey_controller.py`, `discover.py`, `system.py`, and
`discovery_worker.py` write to `menubar.log`. Measurement-only — neither script touches `src/`.
Background: `process-docs/hotkey_latency/`.

## Modules

### probe_get_event_time.py (131 LOC)

**Purpose:** Standalone Carbon `GetEventTime`/`GetCurrentEventTime` symbol probe — Check 1
(non-interactive) resolves both symbols and asserts a plausible, monotonically-increasing
`GetCurrentEventTime()`; Check 2 (interactive) registers a throwaway global hotkey (Cmd+Shift+9)
and prints `queue_delay_ms` on each press.
**Reads:** nothing — standalone GUI probe.
**Writes:** stdout only.
**Called by:** none — run manually; Check 2 requires an interactive GUI session.
**Calls out:** `rumps` — duplicates the minimal Carbon ctypes boilerplate rather than importing
`hotkey_controller.py` (dev-import-from-src is blocked repo-wide).

---

### analyze_latency.py (168 LOC)

**Purpose:** Parses `menubar.log`'s `[latency]` lines into four buckets — main-thread tick phase
breakdowns, background discovery-worker cycle breakdowns, hotkey queue-delays, focus
lookup/osascript splits — and writes a distribution report (mean/median/p90/p95/max per phase,
slowest N entries, per-hotkey percentiles).
**Reads:** `menubar.log` (default: `menubar.menubar_log.MENUBAR_LOG`, override via `argv[1]`).
**Writes:** `md/latency_report_<timestamp>.md`.
**Called by:** none — run manually.
**Calls out:** `src.menubar.menubar_log` (`MENUBAR_LOG`) — imported via `sys.path.insert(0,
WORKTREE_ROOT / 'src')` + `from menubar....`, not `from src.menubar...` (blocked by
`block_dev_imports_src`).
