# dev/proxy_instrumentation/

## Role
Reconstructs and measures the proxy's real strip/inject pipeline output straight from recorded
dual-log payloads, through the real production code (`src/proxy/message_passes.py`, `rule_ops.py`,
`diff_engine.py`, `src/proxy_display/render_messages.py`) — no live proxy required. Touch when
validating a pane-render or span-computation change against real recorded data; use
`dev/proxy_dual_log/` instead for the dual-log invariant/verification suite.

## Flow
Each script loads one or more recorded dual-log JSONL files, drives the real pass functions or
render path over the payloads, and either asserts an invariant or writes a findings report to `md/`.

## Modules

### render_recorded_request.py (129 LOC)

**Purpose:** Reconstructs the pane render for one specific recorded request (by `request_id`)
straight from the on-disk dual-log, to verify a span-render fix for block-less messages.
**Reads:** a fixed recorded session's forwarded/stripped/injected dual-log files (hardcoded stem and
request_id) under src/logs/dual_log.
**Writes:** rendered output to stdout.
**Called by:** none — manual, one-off verification script.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.parser`,
`src.proxy_display.render_messages`.

---

### p4_blocklist_223_probe.py (150 LOC)

**Purpose:** Verifies the CC 2.1.223 `TOOL_BLOCKLIST` extension (Artifact, ReportFindings,
DeferredToolPlaceholder) end-to-end — runs the real `_strip_unused_tools` on a recorded session's
original payload and asserts the post-strip tool set is exactly the expected core set plus any
MCP-injected names.
**Reads:** a fixed recorded session's original/forwarded dual-log pair under src/logs/dual_log.
**Writes:** `md/blocklist_223_probe_report.md`.
**Called by:** none — manual, historical pin-bump verification.
**Calls out:** `proxy.tools` (`_strip_unused_tools`), `constants` (`TOOL_BLOCKLIST`),
`src.proxy_display.forwarded_parser` (`_parse_forwarded_log`).

---

### p5_mid_turn_user_msg_preserve_probe.py (132 LOC)

**Purpose:** Verifies the CC 2.1.223 mid-turn-user-message preserve guard in
`_apply_role_system_strip` — drives the real function against a recorded incident message that must
survive byte-for-byte, plus a regression case confirming unrelated `role='system'` noise still
strips to `"."`.
**Reads:** two recorded sessions' original dual-log files under src/logs/dual_log.
**Writes:** `md/mid_turn_user_msg_preserve_probe_report.md`.
**Called by:** none — manual, historical incident-verification probe.
**Calls out:** `src.proxy.message_passes` (`_apply_role_system_strip`).

---

### p6_no_flow_extra_prepend_probe.py (294 LOC)

**Purpose:** Verifies that an expanded request body is exactly the request's own payload delta and
nothing else, after the out-of-window prepend mechanism was removed — asserts no entry's body carries
a header below its own delta-window start, that the removed mechanism's functions/attachments are
fully absent (reintroduction guard), that substantial out-of-window touches still badge, and that
in-window spans still render.
**Reads:** two recorded sessions' forwarded/stripped/injected dual-log files under src/logs/dual_log
(overridable via argv).
**Writes:** `md/no_flow_extra_prepend_report.md`.
**Called by:** none — manual regression guard for the removed prepend mechanism.
**Calls out:** `src.proxy_display.forwarded_parser`, `src.proxy_display.parser`,
`src.proxy_display.render_messages`, `src.proxy_display.render_turn`.

---

### p7_blocklist_258_probe.py (145 LOC)

**Purpose:** Verifies the CC 2.1.258 `TOOL_BLOCKLIST` extension (SendFeedback, ListAgents)
end-to-end against the current full dual-log corpus (glob-driven, not one hardcoded session) — runs
the real `_strip_unused_tools` on the newest main-session log and scans the whole corpus for any live
`tool_use` invocation of either newly-blocked name.
**Reads:** all `*_original.jsonl` files present under src/logs/dual_log at run time.
**Writes:** `md/blocklist_258_probe_report.md`.
**Called by:** none — manual, historical pin-bump verification.
**Calls out:** `proxy.tools` (`_strip_unused_tools`), `constants` (`TOOL_BLOCKLIST`).

---

### p1_measure_full_replacement_blast_radius.py (541 LOC)

**Purpose:** Classifies each `_ops_from_content_change` call site in `message_passes.py`'s pass
functions as FULL (whole-block-independent replacement) vs. PARTIAL vs. STRUCTURAL by reading the
underlying strip function (not by a ratio threshold), and quantifies how many FULL-class ops are
recorded as a trimmed/split span due to `_extract_block_op`'s prefix/suffix trim.
**Reads:** four recorded sessions' original dual-log files under src/logs/dual_log.
**Writes:** `md/full_replacement_blast_radius_20260729.md`.
**Called by:** none — manual, one-off measurement.
**Calls out:** `src.proxy.message_passes`, `src.proxy.rule_ops`, `src.proxy.diff_engine`,
`src.proxy.payload_helpers`, `src.proxy.content_strip`, `src.proxy_display.render_messages`.

---

## Gotchas
- `pN_*.py` scripts import from `src/` directly — this filename prefix is a project convention: only
  `pN_*.py` dev scripts may `from src...`/`import src...`; unprefixed scripts in `dev/` must copy the
  logic or import from an existing `pN_` module.
- `src.proxy_display` pulls in a 2-level relative import (`from ..constants` in `pane.py`,
  transitively via `proxy_display/__init__.py`) and must be imported with the project root on
  `sys.path`, not `src/` directly (which is what plain `src.proxy.*` imports use). Mixing both roots
  on `sys.path` in the same script is safe — `src.proxy_display` and the flat `proxy` package never
  collide.
- `p1_measure_full_replacement_blast_radius.py` feeds each pass function only the new-message delta
  per dual-log request, not the full cumulative message list — safe only because none of the pass
  functions in `message_passes.py` read any other message's content.
- All dual-log reads in this directory point at src/logs/dual_log, which is gitignored runtime data
  absent from a fresh worktree and live-growing from concurrent sessions — re-running a corpus-wide
  script shifts absolute counts without changing the underlying finding.
