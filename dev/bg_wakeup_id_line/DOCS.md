# dev/bg_wakeup_id_line/

## Role

Measurement and regression scripts for the CC background-launch-ack family: the raw ack text CC
sends (`p1_`), the tmux-Escape mechanism the proxy fires on that ack (`p2_`,
`src/proxy/bg_escape.py`), and the interrupt marker CC records in the conversation when that
Escape lands mid-tool-call (`p3_`, `src/proxy/strip_interrupt_marker.py`). Touch this area when
changing `bg_escape.py`, `strip_bg_launch_ack.py`, or `strip_interrupt_marker.py`. `md/` holds
every script's report.

## Modules

### p1_scan_launch_ack_wordings.py (291 LOC)

**Purpose:** Inventories distinct CC background-launch-ack wordings in
`src/logs/dual_log/*_original.jsonl`, dedups cumulative dual-log duplication, and evaluates the 3
recognition mechanisms in `src/proxy/strip_bg_launch_ack.py` against each wording.
**Reads:** `src/logs/dual_log/*_original.jsonl` (main-repo checkout, not the worktree).
**Writes:** `md/launch_ack_wordings_<date>.md`.
**Called by:** none — run manually.
**Calls out:** `src.proxy.strip_bg_launch_ack` (`_BG_LAUNCH_ACK_MARKER`, `_BG_LAUNCH_ACK_PREFIX`, `_ACK_ID_RE`, `_ACK_PATH_RE`).

---

### p2_bg_escape_probe.py (339 LOC)

**Purpose:** Verifies `src/proxy/bg_escape.py` — dedup-by-task-id across repeated acks, both CC
ack wordings, main-context never fires, tmux session-name derivation, a real tmux round trip, and
failure isolation (dead session, missing `tmux` binary) both at the unit level and through a real
`ProxyAddon.request()` call.
**Reads:** nothing persistent — builds fixtures in-process; spawns/kills one throwaway tmux
session for the round-trip test; the log-line test scopes `MONITOR_CC_ROOT` to a
`tempfile.TemporaryDirectory()`.
**Writes:** `md/p2_bg_escape_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `strip_bg_launch_ack.py`'s
detection or `addon.py`'s worker-context derivation.
**Calls out:** `src.proxy.bg_escape`, `src.proxy.addon` (`ProxyAddon`, `_derive_worker_context`), `tmux` binary (round-trip test only).

---

### p3_strip_interrupt_marker_probe.py (243 LOC)

**Purpose:** Verifies `src/proxy/strip_interrupt_marker.py` and its wiring through
`message_passes_simple.py` / `rules.py` / `strip_vocab.py` / `strip_inject_delta.py` — the real
payload shape, both known marker wordings, the false-positive class (marker text embedded inside
longer text must survive), and attribution resolving to a named function through the real
`apply_modification_rules` → `_build_stripped_injected_deltas` path.
**Reads:** nothing persistent — builds fixtures in-process.
**Writes:** `md/p3_strip_interrupt_marker_probe_<timestamp>.md`.
**Called by:** none — run manually; re-run after any change to `strip_interrupt_marker.py` or its
wiring.
**Calls out:** `src.proxy.strip_interrupt_marker`, `src.proxy.message_passes_simple`
(`_apply_interrupt_marker_strip`), `src.proxy.rules` (`apply_modification_rules`),
`src.proxy.strip_vocab` (`attribute_chunk`, `RULES`), `src.proxy.strip_inject_delta`
(`_MSG_CODE_TO_FN`, `_build_stripped_injected_deltas`).

---

## Gotchas

**p2's real tmux round trip needs a `tmux` binary on PATH** and creates/destroys one throwaway
session (`__bg_escape_probe_<ts>__`). Not sandboxed away from a real tmux server — if `tmux` is
missing, only that one check fails; the other 6 test groups (pure-Python) still run and report.

**The reader-pane in p2's round-trip test passes a SINGLE shell-string trailing argument to
`tmux new-session`** (`f'python3 {script}; sleep 5'`), not multiple trailing argv words —
multiple words make tmux `execvp` the command directly instead of routing through `$SHELL -c`,
which can tear the pane down before `send-keys` reaches it. See `process-docs/escape_idle_worker/`
for the diagnosis of this failure mode.
