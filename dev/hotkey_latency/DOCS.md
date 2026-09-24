# dev/hotkey_latency/

## Role
Measurement tooling for menubar hotkey lag (intermittent slow response of the panel hotkeys). Verifies a Carbon event-time technique and parses the latency instrumentation the menubar writes to its log. Measurement only; neither script touches `src/`.

## Public Interface
No `__init__.py`. Entry paths: `./venv/bin/python3 dev/hotkey_latency/probe_get_event_time.py` (interactive, registers a real global hotkey) and `./venv/bin/python3 dev/hotkey_latency/analyze_latency.py [path/to/menubar.log]`.

## Flow
The probe takes no data in: it registers a live hotkey and prints a delay per key press. The analyzer reads the menubar log, parses latency lines into four buckets and writes a distribution report to `md/`.

## Modules

### probe_get_event_time.py (111 LOC)

**Purpose:** Standalone Carbon event-time probe: a non-interactive symbol check and an interactive throwaway hotkey that prints queue delay per press.
**Reads:** nothing; standalone GUI probe.
**Writes:** stdout only.
**Called by:** none; run manually, the interactive part needs a GUI session.
**Calls out:** `rumps`; duplicates the Carbon boilerplate instead of importing from `src/`.

---

### analyze_latency.py (141 LOC)

**Purpose:** Parses the menubar log's latency lines into tick, hotkey and focus buckets and writes a distribution report.
**Reads:** the menubar log (default path from `src.menubar`, override via first argument).
**Writes:** `md/latency_report_<timestamp>.md`.
**Called by:** none; run manually.
**Calls out:** `src.menubar.menubar_log`, imported via a path insert to satisfy the dev-imports-src hook.

---

## State
No persistent state. The analyzer writes one timestamped report per run; the probe holds its hotkey callback only for one interactive run.
