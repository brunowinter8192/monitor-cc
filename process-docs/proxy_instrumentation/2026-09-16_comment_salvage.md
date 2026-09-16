# proxy_instrumentation comment/docstring salvage — 2026-09-16

## Context

Module-standards conformance pass over `dev/proxy_instrumentation/` (15 `.py` files on disk —
the milestone prompt's measured state said 10; the directory's own DOCS.md already documented
all 15 modules before this pass, so the count had drifted upward before this session started,
not because of anything done here — same pattern as every prior module-standards milestone).
The project standard allows exactly three comment lines per module — `# INFRASTRUCTURE`,
`# ORCHESTRATOR`, `# FUNCTIONS` — and no docstrings anywhere. No file in this directory has a
shebang. Every other comment and every docstring found in this directory is captured verbatim
below, then was deleted from the code. The three section markers were left untouched in the
code and are NOT repeated here — nothing was lost for them.

Comment/docstring counts verified with the same `ast`+`tokenize` script used for the four
prior milestones: 144 raw comment tokens (41 of them the three markers) → **103 non-marker
comments, matching the milestone's measured count exactly**. 6 docstrings total, also matching
exactly — all module-level (`p1_measure_full_replacement_blast_radius.py`,
`p4_blocklist_223_probe.py`, `p5_mid_turn_user_msg_preserve_probe.py`,
`p6_no_flow_extra_prepend_probe.py`, `p7_blocklist_258_probe.py`,
`post_restart_verification.py`). Zero function/class docstrings, zero classes anywhere in this
directory.

5 of the 15 files (`p8_answering_model_probe_test.py`, `p9_response_entry_abort_survival_test.py`,
`p10_model_mismatch_warning_test.py`, `p11_request_identity_encoding_test.py`,
`response_model_corpus_report.py`) had ONLY the three canonical markers as their comments to
begin with — the strip made zero changes to these 5 files, and `git status` correctly shows
them unmodified after this pass. This is expected, not a missed file: verified by re-checking
each one's pre-strip comment/marker count (3 comments, 3 markers, 0 non-marker) before
concluding they needed no edit.

## Load-bearing docstring check

Grepped the whole directory for `__doc__` and `argparse`: zero hits for either, anywhere.
No test runner or `help()` call consumes any docstring. **Zero load-bearing docstrings** — all
6 were deleted outright after salvaging, none needed rewiring to a constant.

## Script classification and the tracked-report-artifact discipline

All 15 scripts are read-only w.r.t. the real system. None import `pyautogui`/`AppKit`/
`Quartz`, none touch the desktop/Spaces/hotkeys, and `post_restart_verification.py` only
CHECKS the aftermath of a restart performed elsewhere — it never restarts anything itself.
Safe to run all 15.

**6 scripts write to a fixed-path, currently-tracked report file** (no per-run timestamp in
the filename): `p4_blocklist_223_probe.py` -> `md/blocklist_223_probe_report.md`,
`p5_mid_turn_user_msg_preserve_probe.py` -> `md/mid_turn_user_msg_preserve_probe_report.md`,
`p6_no_flow_extra_prepend_probe.py` -> `md/no_flow_extra_prepend_report.md`,
`p7_blocklist_258_probe.py` -> `md/blocklist_258_probe_report.md`,
`p1_measure_full_replacement_blast_radius.py` -> `md/full_replacement_blast_radius_20260729.md`,
`response_model_corpus_report.py` -> `md/response_model_corpus_report.md`. Per this session's
explicit instruction (reinforced from the `tool_use_analysis` milestone): backed up all 6
files' content to `/tmp/pi_tracked_backup/` BEFORE any test run, then `diff -q` each one
against its backup after every run that could plausibly touch it — all 6 confirmed byte-
identical to their pre-session committed content at the end of this pass. Only
`p6_no_flow_extra_prepend_probe.py`'s report was ever actually rewritten during testing (it
writes unconditionally, even when every session is skipped) — restored via `git checkout --`
immediately after confirming its content, both times (once before the strip, once after).
`p1` and `p5` never reach their own `write_text` call at all (see below — both crash first),
so their tracked files were never at real risk, but were backed up and re-diffed anyway, out of
caution.

## Two pre-existing, already-rotated hardcoded corpora (no freezing needed)

`render_recorded_request.py` (stem `api_requests_opus_posts_1785266871`),
`p5_mid_turn_user_msg_preserve_probe.py` (stems `api_requests_opus_posts_1786051932` /
`api_requests_opus_websearch_1786052022`), `p1_measure_full_replacement_blast_radius.py`
(4 hardcoded 2026-07-29-era filenames), and `p6_no_flow_extra_prepend_probe.py`'s
`DEFAULT_STEMS` (2026-08-era) all reference session stems confirmed ABSENT from the live
`src/logs/dual_log/` corpus (checked directly with `ls` before writing any test driver) — old
sessions get rotated out over time, exactly as this directory's own (now-salvaged) Gotchas
section already documented for `p4_blocklist_223_probe.py`'s own now-fixed former hardcoded
stem. `render_recorded_request.py`, `p5`, and `p1` each crash with a clean, deterministic
`FileNotFoundError`/`AssertionError` BEFORE reaching any report-write call — verified
byte-identical via the edited-file-line-number-normalizing traceback harness (from the
`proxy_dual_log`/`tool_use_analysis`/`display` milestones), no corpus freezing needed.
`p6` degrades gracefully instead (prints `SKIP <stem> — no recorded forwarded log` for each
missing stem, still writes a trivial all-SKIPPED/ALL-PASS report) — also deterministic without
freezing, verified byte-identical stdout AND report content.

## Live-corpus scripts: frozen once, monkeypatched `LOG_DIR`

`p4_blocklist_223_probe.py`, `p7_blocklist_258_probe.py`, and
`response_model_corpus_report.py` all glob the LIVE, shared, actively-growing
`src/logs/dual_log/` corpus with no hardcoded stem — the same class of risk documented in
three prior milestones' process-docs (a concurrent agent's session can add or grow a file
between the "before" and "after" test runs, producing a false diff unrelated to the comment
strip). Resolved by copying the ENTIRE current corpus (143 files) into
`/tmp/pi_frozen_duallog/` ONCE, then reassigning each module's own `LOG_DIR` global (a plain
`Path`, read fresh by every function call, never captured as a default-argument value at
import time) to point at the frozen copy after importing the module but before calling its
functions — no source-code changes needed, just a post-import attribute rebind in the test
driver. All three produced byte-identical results before and after the comment strip against
the frozen snapshot.

**Real findings surfaced by this frozen-corpus run (both pre-existing, neither caused by or
fixed in this pass):**
- `p4_blocklist_223_probe.py`'s `post_strip_set_is_exact` check FAILS against the current
  corpus and current `src/proxy/tools.py` — its own `EXPECTED_KEPT = {Bash, Read, Skill}`
  predates the later Edit/Write blocklist milestone (`p7`'s own check 4/5), so the real
  `_strip_unused_tools` now correctly keeps Edit/Write too and this probe's stale expectation
  no longer matches. `p7` reproduces the identical stale-expectation failure in its own check 1
  (same `EXPECTED_KEPT` set, same underlying assumption).
- `p7_blocklist_258_probe.py`'s `rw_blocklist_contains_new_entries`/
  `rw_actually_removed_from_representative_payload` checks (4 and 5, verifying Edit/Write ARE
  in `TOOL_BLOCKLIST`) also FAIL against the current corpus/constants — the real
  `constants.TOOL_BLOCKLIST` currently does NOT contain Edit or Write at all (confirmed:
  `_strip_unused_tools` keeps both in the post-strip set). This means the Edit/Write
  file-mutation blocklist entries this probe's own docstring and the old DOCS.md narrate as
  shipped have since been REVERTED or never actually landed in `constants.py` — a real,
  currently-true state fact about production code, discovered by this pass, not altered by it.
  **Whoever next touches `TOOL_BLOCKLIST` or this probe should reconcile this before trusting
  either the probe's PASS/FAIL verdict or its own docstring's narrative.**

## Synthetic coverage for the blast_radius library modules

`blast_radius_engine.py`/`blast_radius_analysis.py`/`blast_radius_report.py` have no
`__main__` entry point and are normally exercised only through
`p1_measure_full_replacement_blast_radius.py` — which crashes immediately on its own missing
hardcoded corpus files (see above) and therefore never actually calls into them during
verification. To get real coverage of the comment-stripped logic (not just "the crash still
crashes"), built a small synthetic message-delta fixture (one `role=system` FULL-replacement
case, one `<task-notification>` PARTIAL-strip case) and called `_drive_passes` +
`_build_report` directly — exercises `blast_radius_engine`'s classification tables,
`blast_radius_analysis`'s real `compose_block`/`_render_span_content` render comparison, and
`blast_radius_report`'s full section-by-section assembly end to end. Byte-identical (excluding
the report's own `Generated: <timestamp>` line) before and after the comment strip.

## DOCS.md rewrite

The previous DOCS.md already used a Purpose/Reads/Writes/Called-by/Calls-out shape per module
and its Role paragraph was already close to (and within) the 50-word limit; the only cut was
the Gotchas section, not part of the mandated format — salvaged verbatim below. New LOC figures
were measured with `wc -l` AFTER the comment/docstring strip, e.g.
`p6_no_flow_extra_prepend_probe.py` 304 -> 249, `blast_radius_engine.py` 220 -> 190,
`render_recorded_request.py` 129 -> 109 — every one of the 15 headings was checked against its
file's actual post-strip `wc -l`, zero mismatches. The 5 files whose comments were markers-only
(see above) kept their pre-existing LOC unchanged.

## For the next agent

- The `TOOL_BLOCKLIST` Edit/Write discrepancy above (p7's checks 4/5 failing against real
  `constants.py`) is a real, currently-true fact, not a test artifact of this pass — confirm
  the actual state of `constants.TOOL_BLOCKLIST` before trusting either `p7`'s report or its
  own docstring narrative about what shipped.
- `p4`'s and `p7`'s shared `EXPECTED_KEPT = {Bash, Read, Skill}` is stale relative to current
  production regardless of the Edit/Write question above — both checks 1 fail today against any
  current corpus session, frozen or live.
- Frozen corpus directory (`/tmp/pi_frozen_duallog/`, 143 files) and tracked-report backups
  (`/tmp/pi_tracked_backup/`) were never staged and are throwaway for this session only.
- The `LOG_DIR`-reassignment-after-import pattern used here (`import module_name as m;
  m.LOG_DIR = Path(frozen_dir)`) works because every one of these scripts reads its own
  `LOG_DIR` global fresh inside each function body — never captures it as a default-argument
  value at function-definition time. Verify this still holds before reusing the pattern if
  either script is ever refactored to take `LOG_DIR` as a parameter default instead.

## Salvage from dev/proxy_instrumentation/render_recorded_request.py

Comment (lines 2-5):
```
# Reconstructs the proxy-pane render for one recorded request straight from the on-disk
# dual-log (_forwarded / _stripped / _injected), through the REAL render path — no live proxy.
# Verifies the span-render fix for "strip/inject spans not rendered for block-less messages":
# request_id b6e4f411-74b2-4b56-8940-bf5ce51e7380, dual-log line 132.
```

Comment (lines 13-14):
```
# Recorded dual-log session lives in the main project checkout (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
```

Comment (lines 25-26):
```
# Confirm dual-log line 132 (0-based) carries TARGET_REQUEST_ID; fail loud if the recorded
# data drifted from what this harness assumes.
```

Comment (line 36):
```
# Walk backward from k-1 to find first non-standalone entry idx (mirrors pane._resolve_prev_same)
```

Comment (lines 44-46):
```
# Build full forwarded-entry list (messages populated for line_idx + its prev_same) and the
# family-level stripped/injected span accumulators, exactly as pane.py's poll loop would
# after reading the whole dual-log (accumulator is cumulative + attached by reference).
```

Comment (line 68):
```
# Call the real render_messages() and return (lines, keys)
```

Comment (lines 76-78):
```
# Extract lines belonging to one msg_idx: from its own "    [idx] role ..." header up to
# (not including) the next message-header line (4-space indent + bracket — distinguishes
# from block sub-lines, which are indented 6/8 spaces and also contain "[bidx]").
```

Comment (lines 114-117):
```
# Control: message 274 is introduced as NEW by the request one line earlier (line 131,
# request 14d58a9a, message_count 275) — that is the entry whose own diff-render actually
# covers msg_idx 274 (target_line's own render only covers [275,278), msg 274 is unchanged
# there and correctly omitted). Render THAT entry to inspect msg 274's yellow strip span.
```

---

## Salvage from dev/proxy_instrumentation/p4_blocklist_223_probe.py

Docstring (module, lines 1-18):
```

Verifies the CC 2.1.223 TOOL_BLOCKLIST extension (Artifact, ReportFindings,
DeferredToolPlaceholder) against the newest main-session recording currently present in the live
src/logs/dual_log/ corpus (glob-driven, same pattern as p7_blocklist_258_probe.py -- no hardcoded
session stem, since a fixed stem ages out of the log-rotated corpus):

  1. The real _strip_unused_tools (src/proxy/tools.py), run on the session's actual ORIGINAL
     payload tools list, leaves exactly {Bash, Read, Skill} + any MCP-injected
     names present in the forwarded log.
  2. Sanity: none of the newly-blocked tool names has a live tool_use invocation anywhere in
     the session's original messages (a stripped def with a live tool_use would 400 the API).
  3. Agent (already blocklisted pre-2.1.223) does not appear in the forwarded/post-strip tools
     list — confirms the earlier live-observation of "Agent" in the tools drill-down was the
     intentional whole-stripped yellow row (render_sections.py), not a strip-path bug.

Usage (from project root):
    ./venv/bin/python dev/proxy_instrumentation/p4_blocklist_223_probe.py

```

Comment (lines 29-30):
```
# Recorded dual-log corpus lives in the main project checkout (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
```

Comment (lines 42-45):
```
# Newest main-session (non-worker) original log that also has a matching forwarded log and at
# least one non-empty tools payload -- same selection pattern as
# p7_blocklist_258_probe.py._newest_main_session_log, extended with the forwarded-pair/non-empty
# requirements this probe additionally needs.
```

Comment (line 62):
```
# One representative original-log payload with a non-empty tools list
```

Comment (line 73):
```
# Union of tool_use names invoked anywhere in the session's original messages
```

Comment (line 90):
```
# Union of forwarded (post-strip, post-MCP-injection) tool names across the whole session
```

---

## Salvage from dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py

Docstring (module, lines 1-15):
```

Verifies the CC 2.1.223 mid-turn-user-message preserve-guard in
src/proxy/message_passes.py::_apply_role_system_strip (issue #61) against two recorded sessions:

  - api_requests_opus_posts_1786051932_original.jsonl: msg 274 (flow 4b4d396b...) is the live
    incident itself — a role='system' message CC used to deliver a mid-turn user message
    ("jetzt"). Real _apply_role_system_strip, run on the REAL recorded message list, must leave
    it byte-for-byte untouched.
  - api_requests_opus_websearch_1786052022_original.jsonl: three unrelated role='system' noise
    messages (deferred-tools, task-tools-nag, date-changed) must still strip to "." exactly as
    before this fix — the guard must not have widened beyond its one marker.

Usage (from project root):
    ./venv/bin/python dev/proxy_instrumentation/p5_mid_turn_user_msg_preserve_probe.py

```

Comment (lines 25-26):
```
# Recorded dual-log sessions live in the main project checkout (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
```

Comment (line 38):
```
# Load the full recorded messages list for one flow_id from an _original.jsonl file
```

Comment (line 49):
```
# Preserve case: msg 274 of the incident flow must survive _apply_role_system_strip untouched
```

Comment (line 74):
```
# Regression case: one real role=system noise message from the websearch session must still nuke to "."
```

---

## Salvage from dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py

Docstring (module, lines 1-40):
```

p6_no_flow_extra_prepend_probe.py — the expanded body is the request's payload delta, nothing else.

Replaces `p6_flow_extra_suppress_probe.py` (2026-08-30). That probe verified a PARTIAL suppression
of the out-of-window prepend (total_tokens nuke only) by rendering each entry twice, once with the
suppression disabled. The prepend mechanism was removed entirely hours later, so there is no second
rendering to compare against any more — the invariants below are self-contained instead, which also
means they keep holding as the recorded logs grow.

Drives the REAL read path (`_parse_forwarded_log` -> `accumulate_dual_log` -> pane-style entry
attach -> `render_messages`) over recorded sessions and asserts:

  1. No entry's body contains a `[N]` message header BELOW that entry's own delta-window start
     (prev_msg_count for the new-messages branch, diff_start for the modified branch). This is the
     property the removal bought: body == payload delta.
  2. `_render_flow_extra_messages` and `_own_msgs` no longer exist in `render_messages`, and no
     entry carries a `_strip_msgs_sub_lookup` / `_inject_msgs_sub_lookup` attachment — a
     reintroduction guard, since a partial revert would otherwise pass check 1 silently.
  3. Every entry whose out-of-window touch is SUBSTANTIAL still badges — those badge words are now
     the ONLY in-pane trace of such a strip. Substantiality is read off the raw dual-log lines via
     `parser._msg_delta_entry_is_substantial`, because a touch that is only the per-request
     total_tokens nuke deliberately badges nothing (the 2026-08-29 divergence) and must not be
     demanded here.
  4. The in-window path still renders spans: at least one entry shows an olive or green span, so a
     regression that killed span rendering outright cannot pass as "no prepend".
  5. The write-side LAG CORRECTION holds (2026-08-30): every coordinate the parser attributes back
     to the flow that actually stripped it carries the total_tokens marker text (never a
     mid-conversation overwrite such as the task-tools nag, which would be neighbour bleed), and
     every such coordinate falling inside its flow's delta window really renders an olive span and
     a green ".". Without the correction those messages render as a bare "." — the defect this
     check guards.

It also REPORTS (never asserts) how many entries have an out-of-window touched index whose stripped
original is therefore invisible in the pane — the accepted cost of the removal, recoverable only
from the dual-log `_stripped` stream (e.g. via the duallog CLI).

Usage (from project root):
    ./venv/bin/python dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py
    ./venv/bin/python dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py <stem> [<stem> ...]

```

Comment (lines 50-51):
```
# Recorded dual-log sessions are untracked data living in the main checkout, never duplicated into
# worktrees — code under test is imported from WORKTREE_ROOT above.
```

Comment (line 72):
```
# Load one recorded session the way pane.py assembles it, messages retained for every entry
```

Comment (lines 95-97):
```
# The first msg index this entry's delta window covers — mirrors render_messages' own branch
# choice, recomputed here rather than imported so the probe cannot drift into agreeing by
# construction with the code it checks
```

Comment (line 115):
```
# Msg indices appearing as top-level headers in a rendered body
```

Comment (line 121):
```
# Render every entry; returns {entry_idx: (body, window_start, out_of_window_touches)}
```

Comment (lines 141-142):
```
# {(flow_id, msg_idx): True} for every delta entry the parser calls substantial, read straight off
# the raw dual-log lines — the same verdict the badge rests on
```

Comment (lines 163-164):
```
# Check 5: the lag correction is marker-only, and the coordinates it fixes really render spans.
# Returns (coords_with_wrong_text, coords_in_window_without_spans, total_corrected).
```

Comment (line 187):
```
# outside this entry's delta window — nothing is drawn there at all
```

Comment (line 193):
```
# Checks 2's source-level half: the removed symbols must not come back
```

Comment (line 225):
```
# One session: render, assert the four invariants, return (rows, stats)
```

---

## Salvage from dev/proxy_instrumentation/p7_blocklist_258_probe.py

Docstring (module, lines 1-35):
```

Verifies the CC 2.1.258 TOOL_BLOCKLIST extension (SendFeedback, ListAgents) against the current
full src/logs/dual_log/*_original.jsonl corpus:

  1. The real _strip_unused_tools (src/proxy/tools.py), run on the newest main-session log's
     original payload, leaves exactly {Bash, Read, Skill} + any MCP-injected names.
  2. Sanity, corpus-wide: no tool_use block in ANY *_original.jsonl file's messages references
     SendFeedback or ListAgents (a stripped tool def with a live tool_use in history would 400
     the API on replay). Reports the number of files scanned and hits found.
  3. Blocklist membership: both names are in TOOL_BLOCKLIST.

Also verifies the Edit/Write TOOL_BLOCKLIST extension (Bash-only file access for the two
remaining blocked file-mutation tools — Read was taken back out of TOOL_BLOCKLIST afterward; see
process-docs/image_intake/ for that decision and process-docs/proxy_tool_stripping/ for the
blocklist's own history), which structurally differs from every addition above and everything
blocklisted before it:

  4. Blocklist membership: Edit, Write are in TOOL_BLOCKLIST; _strip_unused_tools removes both
     from the same representative payload used in check 1.
  5. UNLIKE every prior addition (which all required zero corpus-wide live tool_use hits before
     merging, per checks 2/3 above and the 223 probe), Edit/Write DO have live tool_use hits
     across the corpus — expected, not a failure — because these two are among the dominant
     tools of essentially every turn in every already-running session. This check asserts
     hits > 0 and reports the exact count, so the residual risk is visible rather than silently
     assumed away.
  6. Documents, as a pinned regression check, that this residual risk is real: a synthetic
     tool_use/tool_result pair for a blocked tool already sitting in message history is NOT
     touched by _strip_unused_tools (src/proxy/tools.py) or _strip_blocked_tool_references
     (src/proxy/payload_helpers.py) — both only ever touch the `tools` schema array and
     `tool_reference` content blocks (a ToolSearch-deferred-tools construct), never a real
     `tool_use`/`tool_result` pair. Confirms this is unhandled, not silently fixed elsewhere.

Usage (from project root):
    ./venv/bin/python dev/proxy_instrumentation/p7_blocklist_258_probe.py

```

Comment (lines 46-47):
```
# Recorded dual-log corpus lives in the main project checkout (untracked data, not
# duplicated into worktrees) — code under test is imported from WORKTREE_ROOT above.
```

Comment (line 60):
```
# All *_original.jsonl files currently in the corpus, oldest-independent listing
```

Comment (line 65):
```
# Newest main-session (non-worker) original log, by mtime
```

Comment (line 73):
```
# One representative payload with a non-empty tools list from the given log file
```

Comment (lines 83-84):
```
# Scan every _original.jsonl file for tool_use blocks naming one of target_names.
# Returns (files_scanned, hits) where hits is a list of (file_name, tool_name) tuples.
```

Comment (lines 103-105):
```
# A blocked tool's tool_use + matching tool_result, exactly the shape already sitting in every
# running session's history. Proves _strip_unused_tools/_strip_blocked_tool_references leave it
# untouched — neither function looks at tool_use/tool_result content at all.
```

Comment (line 184):
```
# --- Edit/Write milestone (Bash-only file access; Read restored) ---
```

---

## Salvage from dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py

Docstring (module, lines 1-16):
```

D2 — blast-radius measurement for a full-replacement-aware _extract_block_op.

Measurement only: drives real recorded payloads through the real message-pass functions
(src/proxy/message_passes.py) in src/proxy/rules.py::apply_modification_rules's actual
pass order, capturing every (offset, removed, injected) op _ops_from_content_change
produces, per pass. Classifies each op's SITE semantically (by reading the underlying
strip function: does it construct new block content INDEPENDENTLY of the old — a whole-
content replacement — or does it EXCISE a known chunk from within surrounding text and
keep the remainder?) — not by any len(removed)/len(bt) threshold. The ratio is reported
only as corroborating evidence, never as the classifier. Writes report to
dev/proxy_instrumentation/md/.

Usage (from project root or worktree root):
    ./venv/bin/python dev/proxy_instrumentation/p1_measure_full_replacement_blast_radius.py

```

Comment (line 28):
```
# Same corpus + exclusion rationale as D1 (dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py)
```

---

## Salvage from dev/proxy_instrumentation/blast_radius_engine.py

Comment (lines 9-11):
```
# Structural passes (own logic) stayed in message_passes.py; template passes (generic pass
# runner + declarative spec) moved to message_passes_simple.py; the wake-up concern moved to
# message_passes_wakeup.py (2026-09, helper-extraction milestone).
```

Comment (lines 32-38):
```
# Real pass order from src/proxy/rules.py::apply_modification_rules — _passes list, then the
# _dedup_wakeup_blocks call that follows the loop. Each pass function is called with ONLY the
# per-request NEW message slice (see _scan_file) — legitimate because every pass here decides
# per-message from that message's own content alone (verified by reading message_passes.py: no
# pass reads any OTHER message's content), so feeding only new messages is equivalent to feeding
# the full growing list and produces identical per-message ops without dual-log's cumulative
# duplicate counting (same dedup principle as D1, blessed for that deliverable).
```

Comment (lines 53-58):
```
# Semantic classification per call site — determined by READING the underlying strip function,
# not by any measured ratio. FULL = new block content is constructed independently of the old
# (a fixed literal, or a freshly-derived string) with no attempt to preserve any of the old text
# outside what a template happens to share. PARTIAL = a known marker/chunk is excised from within
# the text (regex.sub / str.replace / slice) and everything else in the block is kept verbatim.
# STRUCTURAL = neither — an index-shift artifact, not a designed content transform.
```

Comment (lines 109-111):
```
# _apply_first_pass is one function with 5 internal elif-branches, each with a DIFFERENT
# classification — sub-classify per message by re-evaluating the same branch conditions the
# real function uses (reusing the real predicate functions, not reimplementing their logic)
```

Comment (lines 129-130):
```
# Re-derive which _apply_first_pass elif-branch fires for one message — mirrors the real
# elif-chain in message_passes.py exactly, reusing the real predicate functions
```

Comment (line 145):
```
# Block text at blk_idx, mirroring _ops_from_content_change's own extraction exactly
```

Comment (lines 154-155):
```
# Drive one delta message-list through all passes in real order, collecting every op with its
# semantic class + evidence + (bt, at) for corroborating-ratio + render reproduction
```

Comment (line 181):
```
# _dedup_wakeup_blocks runs after the pass loop in rules.py, outside _passes
```

Comment (lines 202-206):
```
# Scan one corpus file: dedup via prev-message-count delta (same principle as D1) — each pass
# function decides per-message from that message's own content alone (no cross-message
# dependency in any of the 11 passes, verified by reading message_passes.py), so feeding only
# the newly-introduced messages per request reproduces the exact same per-message ops the real
# cumulative pipeline would produce, without reprocessing (and over-counting) duplicated history.
```

---

## Salvage from dev/proxy_instrumentation/blast_radius_analysis.py

Comment (lines 13-16):
```
# proxy_display/pane.py (pulled in by proxy_display/__init__.py) uses a 2-level relative
# import ("from ..constants") that requires proxy_display to be resolved as a SUBPACKAGE of
# the project root, not as a flat top-level package like the src/proxy/* imports above —
# resolved via a second sys.path root + dynamic import (dodges static "from src." rewriting).
```

Comment (lines 49-52):
```
# Render one op through the REAL compose_block + _render_span_content pipeline — "recorded"
# uses today's actual op (possibly prefix/suffix-trimmed); "hypothetical" uses a synthetic
# full-block op (0, bt, at) to show how a full-replacement-aware _extract_block_op would render
# the SAME underlying change. Returns (recorded_lines, hypothetical_lines), ANSI stripped.
```

---

## Salvage from dev/proxy_instrumentation/blast_radius_report.py

Comment (lines 201-203):
```
# Prefer a PARTIAL op that IS trimmed (offset>0 or suffix trimmed) with ratio<1 — shows
# trimming is CORRECT/desirable there (excises a marker, keeps real surrounding text),
# unlike the FULL sites above where trimming is the defect.
```

Comment (line 253):
```
# Build the markdown report
```

---

## Salvage from dev/proxy_instrumentation/p8_answering_model_probe_test.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_instrumentation/p9_response_entry_abort_survival_test.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_instrumentation/response_model_corpus_report.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_instrumentation/p10_model_mismatch_warning_test.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_instrumentation/p11_request_identity_encoding_test.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_instrumentation/post_restart_verification.py

Docstring (module, lines 1-24):
```

post_restart_verification.py -- the one script a zero-context agent runs after the proxy restarts
to find out whether the three proxy-side changes on this branch (accept-encoding: identity /
answering_model, the auto-backgrounded-on-timeout strip, poread full-content injection) actually
took effect in real traffic.

Picks the newest recorded session by mtime under the dual-log directory (never a hardcoded stem),
checks all three claims against that one session's six dual-log files, and prints one of PASS,
CONTRADICTED, or MISSING DATA per claim -- a claim with no data to test against is never reported
as a pass. Reuses the real proxy predicates/constants (src/proxy/strip_bg_launch_ack.py,
src/proxy/inject_poread.py, src/proxy_display/forwarded_parser.py) wherever a claim's precision
depends on them, rather than re-typing matching logic that could silently drift from the real
implementation.

Run (from project root or this worktree):
    ./venv/bin/python dev/proxy_instrumentation/post_restart_verification.py

Exit 0: all three claims PASS.
Exit 1: at least one claim is CONTRADICTED (checked first -- the worse outcome).
Exit 2: no claim is CONTRADICTED, but at least one has no data to test (MISSING DATA).

POST_RESTART_VERIFY_LOG_DIR overrides the dual-log source directory -- used to pin a run against a
frozen snapshot (e.g. /tmp/pre_restart_logs/) instead of the live, growing main-checkout corpus.

```

---

## Salvage from dev/proxy_instrumentation/DOCS.md

Full previous content of dev/proxy_instrumentation/DOCS.md before the module-standards
conformance rewrite (Role/Flow prose reworded, Modules compressed to fit the word limits, and
the Gotchas section removed entirely since it is not part of the mandated DOCS.md format):

```markdown
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
```

