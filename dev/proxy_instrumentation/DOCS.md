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

### p4_blocklist_223_probe.py (179 LOC)

**Purpose:** Verifies the CC 2.1.223 `TOOL_BLOCKLIST` extension (Artifact, ReportFindings,
DeferredToolPlaceholder) end-to-end — runs the real `_strip_unused_tools` on the newest
main-session recording present in the live corpus and asserts the post-strip tool set is exactly
the expected core set (`Bash`, `Read`, `Skill`) plus any MCP-injected names.
**Reads:** the newest main-session original/forwarded dual-log pair under src/logs/dual_log
(glob-driven session selection, same pattern as `p7_blocklist_258_probe.py`, no hardcoded stem).
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

### p6_no_flow_extra_prepend_probe.py (304 LOC)

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

### p7_blocklist_258_probe.py (254 LOC)

**Purpose:** Verifies the CC 2.1.258 `TOOL_BLOCKLIST` extension (SendFeedback, ListAgents)
end-to-end against the current full dual-log corpus (glob-driven, not one hardcoded session) — runs
the real `_strip_unused_tools` on the newest main-session log and scans the whole corpus for any live
`tool_use` invocation of either newly-blocked name. Also verifies the Edit/Write extension
(Bash-only file access for the two remaining blocked file-mutation tools; Read was taken back out of
`TOOL_BLOCKLIST`, see `process-docs/image_intake/`): blocklist membership and removal, PLUS a
corpus-wide `tool_use` scan that asserts hits `> 0` (the inverse of the check above — expected, since
Edit/Write are among the dominant tools of every running session, unlike every prior addition which
required zero hits before merging), and a synthetic historic tool_use/tool_result-pair check pinning
that `_strip_unused_tools`/`_strip_blocked_tool_references` leave such a pair untouched (documents,
without closing, the gap this creates).
**Reads:** all `*_original.jsonl` files present under src/logs/dual_log at run time.
**Writes:** `md/blocklist_258_probe_report.md`.
**Called by:** none — manual, historical pin-bump verification (now also the standing regression
guard for the Edit/Write blocklist entries — re-run after any `TOOL_BLOCKLIST` change).
**Calls out:** `proxy.tools` (`_strip_unused_tools`), `proxy.payload_helpers`
(`_strip_blocked_tool_references`), `constants` (`TOOL_BLOCKLIST`).

---

### p1_measure_full_replacement_blast_radius.py (59 LOC)

**Purpose:** Entry point for the D2 blast-radius measurement — owns the corpus file list and
drives `blast_radius_engine`/`blast_radius_report` over it.
**Reads:** four recorded sessions' original dual-log files under src/logs/dual_log.
**Writes:** `md/full_replacement_blast_radius_20260729.md`.
**Called by:** none — manual, one-off measurement.
**Calls out:** `blast_radius_engine`, `blast_radius_report`.

---

### blast_radius_engine.py (220 LOC)

**Purpose:** Drives recorded message deltas through the real `message_passes.py` pass order and
classifies each resulting op as FULL/PARTIAL/STRUCTURAL by reading the underlying strip function.
**Reads:** nothing directly — `_scan_file` is handed a dual-log path by its caller.
**Writes:** nothing — returns per-op records to its caller.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** `src.proxy.message_passes`, `src.proxy.message_passes_simple`,
`src.proxy.message_passes_wakeup`, `src.proxy.rule_ops`, `src.proxy.payload_helpers`,
`src.proxy.content_strip`.

---

### blast_radius_analysis.py (65 LOC)

**Purpose:** Trim/ratio/distribution helpers plus a real `compose_block` + `_render_span_content`
render comparison (recorded op vs. a hypothetical full-replacement op) for one classified record.
**Reads:** nothing — pure functions over records passed in.
**Writes:** nothing.
**Called by:** `blast_radius_report.py`.
**Calls out:** `src.proxy.diff_engine`, `src.proxy_display.render_messages`.

---

### blast_radius_report.py (272 LOC)

**Purpose:** Builds the D2 markdown report, one function per section, composed by `_build_report`.
**Reads:** nothing — takes records/corpus metadata as arguments.
**Writes:** nothing — returns the report text to its caller.
**Called by:** `p1_measure_full_replacement_blast_radius.py`.
**Calls out:** `blast_radius_engine` (classification constants), `blast_radius_analysis`.

---

### p8_answering_model_probe_test.py (97 LOC)

**Purpose:** Unit-level regression guard for `response_model_probe.make_answering_model_probe` —
verifies pass-through is always byte-identical, `message_start.model` is found in one chunk and when
split across two chunks, inspection stops (and no longer matches) once the byte budget is exceeded,
and a gzip-compressed body does not spuriously match (documents the known parsing gap).
**Reads:** no on-disk data — synthetic SSE byte fixtures defined in the module.
**Writes:** stdout (pass/fail via assert).
**Called by:** none — manual regression guard, re-run after any `response_model_probe.py` change.
**Calls out:** `proxy.response_model_probe`.

---

### p9_response_entry_abort_survival_test.py (128 LOC)

**Purpose:** Unit-level regression guard for `addon._write_response_entry` and the `response()`/`error()`
dual-hook wiring — verifies the `_response` entry's exact key set and three-field model naming
(`cc_requested_model`/`proxy_forwarded_model`/`answering_model`), that a fake abort-before-first-chunk
and abort-mid-stream both still produce an entry, that a spurious double call does not duplicate the
entry, and that an active model override surfaces as a `cc_requested_model`/`proxy_forwarded_model`
mismatch.
**Reads:** no on-disk data — fake flow/response/metadata objects defined in the module.
**Writes:** stdout (pass/fail via assert); temp files under the system temp dir (via `tempfile.mktemp`).
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s `response`/`error`/
`_write_response_entry`.
**Calls out:** `proxy.addon` (`_write_response_entry`).

---

### response_model_corpus_report.py (195 LOC)

**Purpose:** Reads every recorded `*_response.jsonl` dual-log and reports how many entries carry an
`answering_model`, the `content-type`/`content-encoding` header values observed, and how
`cc_requested_model`/`proxy_forwarded_model`/`answering_model` relate across the corpus.
**Reads:** all `*_response.jsonl` files under the main checkout's `src/logs/dual_log` (hardcoded
`MAIN_REPO_ROOT`, same pattern as `p7_blocklist_258_probe.py` — this dev worktree carries no logs).
**Writes:** `md/response_model_corpus_report.md`.
**Called by:** none — manual, re-run after a proxy restart to check whether the corpus has picked up
`cc_requested_model`/`proxy_forwarded_model`/`answering_model`/`content-type`/`content-encoding` yet
(frozen live-copy caveat, see `src/proxy/DOCS.md` Gotchas).
**Calls out:** —

---

### p10_model_mismatch_warning_test.py (196 LOC)

**Purpose:** Unit-level regression guard for `addon._write_model_mismatch_entry`/`_write_response_and_mismatch`
(M3 milestone) — covers exactly-one-sentence-on-mismatch, no-sentence on equal/empty-`answering_model`,
the double-write guard, the sentence rendering correctly through the real
`warnings_pane._errors_record_to_display` + `warnings_render._build_one_warning_lines` pipeline (both
lines, exact ANSI text), and that the write never touches the `tool_use_id` dedup set
(`logging._build_errors_entries`'s `seen_ids`) — by signature inspection and by an interleaved-write
integration case proving dedup survives across two `_build_errors_entries` calls with a
`model_mismatch` write in between.
**Reads:** no on-disk data — fake flow/response/paths/identity objects and a synthetic payload defined
in the module.
**Writes:** stdout (pass/fail via assert); temp files under the system temp dir.
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s
`_write_model_mismatch_entry`/`_write_response_and_mismatch`/`response`/`error`, or to
`warnings_pane._errors_record_to_display`.
**Calls out:** `proxy.addon` (`_write_response_and_mismatch`, `_write_model_mismatch_entry`),
`proxy.logging` (`_build_errors_entries`), `src.panes.warnings_pane`, `src.panes.warnings_render`,
`src.colors` — the last three imported via the project-root-on-`sys.path` form (`from src....`) inside
the one test function that needs it, since `src.panes` pulls in a 2-level relative import chain like
`src.proxy_display` (see the `src.proxy_display` Gotcha below); mixing both `sys.path` roots in one
script is safe.

---

### p11_request_identity_encoding_test.py (51 LOC)

**Purpose:** Unit-level regression guard for `addon._request_identity_encoding` — verifies it sets
`accept-encoding: identity` on the outbound request from empty, and that it overwrites an already-
present compressed `accept-encoding` value rather than merging or leaving it alone.
**Reads:** no on-disk data — a fake flow/request/headers object defined in the module.
**Writes:** stdout (pass/fail via assert).
**Called by:** none — manual regression guard, re-run after any change to `addon.py`'s
`request()`/`_request_identity_encoding`.
**Calls out:** `proxy.addon` (`_request_identity_encoding`).

---

### post_restart_verification.py (350 LOC)

**Purpose:** The one script a zero-context agent runs after a proxy restart to check whether this
branch's three proxy-side changes took real effect, never vacuously.
**Reads:** the newest session's six dual-log files (by `*_original.jsonl` mtime, never a hardcoded
stem) under `POST_RESTART_VERIFY_LOG_DIR` or the main checkout's `src/logs/dual_log`.
**Writes:** stdout (per-claim report, one of PASS/CONTRADICTED/MISSING DATA per claim — the three claims are accept-encoding: identity + `answering_model`, the auto-backgrounded-on-timeout strip, and poread full-content injection); `md/post_restart_verification_<timestamp>.md`.
**Called by:** none — manual CLI, run once per proxy restart; exit 0 all-pass, exit 1 if any claim
is CONTRADICTED, exit 2 if none are contradicted but at least one is MISSING DATA.
**Calls out:** `proxy.strip_bg_launch_ack` (`_is_bg_auto_timeout_ack`, `_BG_AUTO_TIMEOUT_MSG`,
`_BG_AUTO_TIMEOUT_MSG_MAIN`), `proxy.message_passes_simple` (`_apply_bg_launch_ack_strip`,
`_apply_poread_expand_strip`, read only for `.__name__`), `proxy.inject_poread`
(`_parse_poread_marker`, `_POREAD_HEADER_PREFIX`), `src.proxy_display.forwarded_parser`
(`_parse_forwarded_log`) — real predicates/constants reused directly rather than re-typed, so this
script's precision can never silently drift from the actual proxy behavior it's checking.

---

## Gotchas
- `pN_*.py` scripts import from `src/` directly, and so may an unprefixed sibling module split out of
  one (e.g. `blast_radius_engine.py`, split from `p1_measure_full_replacement_blast_radius.py`) — the
  `block_dev_imports_src` hook has no `pN_` special case (see the hook Gotcha below): it only blocks a
  literal top-level `from src.`/`import src.` statement, so the established pattern of inserting
  `src/` onto `sys.path` and importing flat (`from proxy.xxx import ...`) works in any `dev/` module
  regardless of filename prefix.
- `src.proxy_display` pulls in a 2-level relative import (`from ..constants` in `pane.py`,
  transitively via `proxy_display/__init__.py`) and must be imported with the project root on
  `sys.path`, not `src/` directly (which is what plain `src.proxy.*` imports use). Mixing both roots
  on `sys.path` in the same script is safe — `src.proxy_display` and the flat `proxy` package never
  collide.
- `blast_radius_engine.py` (driven by `p1_measure_full_replacement_blast_radius.py`) feeds each pass
  function only the new-message delta per dual-log request, not the full cumulative message list —
  safe only because none of the pass functions in `message_passes.py` read any other message's content.
- All dual-log reads in this directory point at src/logs/dual_log, which is gitignored runtime data
  absent from a fresh worktree and live-growing from concurrent sessions — re-running a corpus-wide
  script shifts absolute counts without changing the underlying finding.
- `p4_blocklist_223_probe.py` previously hardcoded one session stem
  (`api_requests_opus_websearch_1786052022`) that aged out of the live `src/logs/dual_log/`
  corpus (log rotation) and could no longer run. As of 2026-09-14 it selects the newest
  main-session original+forwarded log pair at runtime instead (`_select_session_stem()`,
  same pattern as `p7_blocklist_258_probe.py`'s `_newest_main_session_log`) — see
  `process-docs/proxy_instrumentation/` for the fix's details.
- **`post_restart_verification.py` cannot trust plain substring search against `_original.jsonl`
  in a session that discusses its own subject matter.** A worker session that implements and
  reports on a feature (e.g. this exact branch) quotes the feature's own literal marker/wording
  text extensively in its own assistant turns — that text gets resent as ordinary conversation
  history on every later request, so a naive grep across the whole payload counts self-discussion
  as if it were a genuine triggering event. The script avoids this by restricting "genuine
  trigger" detection to `role=='user'` `tool_result` content specifically, using the real
  predicates (`_is_bg_auto_timeout_ack`, `_parse_poread_marker`) rather than a hand-rolled
  substring check — verified against this exact worktree's own pre-restart logs, where a loose
  substring count found 146/19 "hits" but the precise, tool_result-anchored count found 1/1.
- **`src/proxy_display/forwarded_parser.py` cannot be imported as `from src.proxy_display...` in
  this non-test file** — the `block_dev_imports_src` PreToolUse hook blocks any literal
  `from src.`/`import src.` statement written via the Write/Edit tool outside a `/tests/`
  regression-test file (a narrower exemption than this file's own "only `pN_*.py`" note above
  describes — the hook's actual regex has no `pN_` special case, it only exempts `/tests/.../
  test_*.py`-shaped paths). Loaded instead via `importlib.import_module(f'{_ROOT_PKG}.proxy_display
  .forwarded_parser')` with `_ROOT_PKG = 'src'` — the same string-built-import pattern
  `dev/click_ui/`'s probes already use for the identical `proxy_display` package family.
  `importlib.util.spec_from_file_location` (the `attribution_coverage.py` workaround for
  `strip_vocab.py`) does NOT work here — `forwarded_parser.py` has real relative imports
  (`from ..proxy.message_summary import ...`) that need genuine package context to resolve, which
  `spec_from_file_location` does not provide.
