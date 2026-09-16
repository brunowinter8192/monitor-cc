# dev/hotkey_latency/

## Role
Measurement tooling for menubar hotkey lag (Cmd+K/L/1..9 intermittent slow response). Verifies
the Carbon `GetEventTime` technique and parses the `[latency]` instrumentation `src/menubar/`
writes to `menubar.log`. Measurement-only — neither script touches `src/`. Background:
`process-docs/hotkey_latency/`.

## Public Interface
No `__init__.py` in this directory. Entry paths: `./venv/bin/python3
dev/hotkey_latency/probe_get_event_time.py` (interactive — registers a real global hotkey, see
Modules below) and `./venv/bin/python3 dev/hotkey_latency/analyze_latency.py [path/to/menubar.log]`.

## Flow
`probe_get_event_time.py` takes no data in — it registers a live hotkey and prints a delta per
real key press. `analyze_latency.py` reads `menubar.log` (default or `argv[1]`), parses `[latency]`
lines into four buckets, and writes a distribution report to `md/`.

## Modules

### probe_get_event_time.py (111 LOC)

**Purpose:** Standalone Carbon `GetEventTime`/`GetCurrentEventTime` symbol probe — Check 1
(non-interactive) resolves both symbols and asserts monotonicity; Check 2 (interactive) registers
a throwaway global hotkey (Cmd+Shift+9) and prints `queue_delay_ms` on each press.
**Reads:** nothing — standalone GUI probe.
**Writes:** stdout only.
**Called by:** none — run manually; Check 2 requires an interactive GUI session.
**Calls out:** `rumps` — duplicates the minimal Carbon ctypes boilerplate rather than importing
`hotkey_controller.py` (dev-import-from-src is blocked repo-wide).

---

### analyze_latency.py (141 LOC)

**Purpose:** Parses `menubar.log`'s `[latency]` lines into four buckets — tick/background-cycle
phase breakdowns, hotkey queue-delays, focus lookup/osascript splits — and writes a distribution
report.
**Reads:** `menubar.log` (default: `menubar.menubar_log.MENUBAR_LOG`, override via `argv[1]`).
**Writes:** `md/latency_report_<timestamp>.md`.
**Called by:** none — run manually.
**Calls out:** `src.menubar.menubar_log` (`MENUBAR_LOG`) — imported via `sys.path.insert(0,
WORKTREE_ROOT / 'src')` + `from menubar....`, not `from src.menubar...` (blocked by
`block_dev_imports_src`).

---

## State
Neither module owns persistent state. `analyze_latency.py` reads a log file and writes one
timestamped report per run under `md/`; `probe_get_event_time.py` holds its hotkey-handler
callback/ref only for the lifetime of one interactive run (kept alive on the `_ProbeApp` instance
as a GC anchor).
