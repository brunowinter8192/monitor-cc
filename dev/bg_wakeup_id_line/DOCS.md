# dev/bg_wakeup_id_line/

## Role
Measurement and regression scripts for the CC background-launch-ack family: the raw ack text CC
sends, the tmux-Escape mechanism the proxy fires on it, and the interrupt marker CC records when
that Escape lands mid-tool-call. Touch when changing `bg_escape.py`, `strip_bg_launch_ack.py`, or
`strip_interrupt_marker.py`.

## Public Interface
No `__init__.py` in this directory. Each `pN_*.py` script is its own entry point, run directly,
e.g. `python3 dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py`.

## Flow
Recorded dual-log JSONL (`p1`) or synthetic in-process payloads (`p2`, `p3`) go in. Each script
drives real production code (`strip_bg_launch_ack.py`'s recognition mechanisms, `bg_escape.py`'s
real tmux dispatch, or `strip_interrupt_marker.py`'s full pipeline wiring) and asserts specific
invariants. Output is stdout plus a report under `md/`.

## Modules

### p1_scan_launch_ack_wordings.py (308 LOC)

**Purpose:** Inventories distinct CC background-launch-ack wordings in recorded dual-logs, dedups
cumulative duplication, and evaluates the 3 recognition mechanisms against each wording.
**Reads:** `src/logs/dual_log/*_original.jsonl` (main-repo checkout, not the worktree).
**Writes:** `md/launch_ack_wordings_20260729.md`.
**Called by:** none — run manually.
**Calls out:** `src.proxy.strip_bg_launch_ack`.

---

### p2_bg_escape_probe.py (313 LOC)

**Purpose:** Verifies `bg_escape.py` — dedup-by-task-id, both ack wordings, main-context never
fires, tmux session-name derivation, a real tmux round trip, and failure isolation.
**Reads:** nothing persistent — builds fixtures in-process; spawns/kills one throwaway tmux
session for the round-trip test.
**Writes:** `md/p2_bg_escape_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `strip_bg_launch_ack.py` or
`addon.py`'s worker-context derivation.
**Calls out:** `src.proxy.bg_escape`, `src.proxy.addon`, `tmux` binary (round-trip test only).

---

### p3_strip_interrupt_marker_probe.py (215 LOC)

**Purpose:** Verifies `strip_interrupt_marker.py` and its wiring through the message-pass,
rules, vocab, and delta-attribution modules against the real payload shape.
**Reads:** nothing persistent — builds fixtures in-process.
**Writes:** `md/p3_strip_interrupt_marker_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `strip_interrupt_marker.py` or
its wiring.
**Calls out:** `src.proxy.strip_interrupt_marker`, `src.proxy.message_passes_simple`,
`src.proxy.rules`, `src.proxy.strip_vocab`, `src.proxy.strip_inject_delta`.

---

## State
No persistent state lives in this directory. Each script builds its own tempdir/in-memory
fixtures and discards them at exit. `p2`'s round-trip test is the one exception with a real
external side effect: its throwaway tmux session briefly exists on the real tmux server between
`new-session` and `kill-session`, and the menubar's live session enumeration can show it flicker
through the user's workers pane for that moment — cosmetic, accepted, not sandboxed further.
