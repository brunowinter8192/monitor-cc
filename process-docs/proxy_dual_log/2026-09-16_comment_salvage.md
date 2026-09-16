# proxy_dual_log comment/docstring salvage — 2026-09-16

## Context

Module-standards conformance pass over `dev/proxy_dual_log/` (38 `.py` files on disk — the
milestone prompt's measured state said 34; the directory's own DOCS.md Modules section already
listed 38 module entries before this pass, so the count had drifted upward before this session
started, not because of anything done here). The project standard allows exactly three comment
lines per module — `# INFRASTRUCTURE`, `# ORCHESTRATOR`, `# FUNCTIONS` — and no docstrings
anywhere. Every other comment and every docstring found in this directory is captured verbatim
below, then was deleted from the code. The three section markers were left untouched in the
code and are NOT repeated here — nothing was lost for them.

Comment/docstring counts verified with the same `ast`+`tokenize` script used for the prior
`dual_log_cli` milestone: 367 raw comment tokens (80 of them the three markers: 36×
`# INFRASTRUCTURE`, 12× `# ORCHESTRATOR`, 32× `# FUNCTIONS`) → 287 non-marker comments,
matching the milestone's measured count exactly. 24 docstrings total, also matching exactly:
14 module-level + 10 function-level (5 in `groundtruth_spans_algorithm.py`, 4 in
`groundtruth_spans_cases.py`, 1 in `groundtruth_spans_report.py`). Zero class docstrings —
no classes exist anywhere in this directory.

## Load-bearing docstring check

Grepped the whole directory for `__doc__` and `argparse` before deleting anything: exactly
3 hits, all module-level docstrings passed into argparse, all inside an
`if __name__ == "__main__":` block:
- `verify_delta.py` — `epilog=__doc__`
- `diff_strip_inject.py` — `epilog=__doc__`
- `tt_delta_skip_replay.py` — `description=__doc__`

Each of these 3 module docstrings was moved verbatim into a module-level `_MODULE_DOC`
string constant in that file's INFRASTRUCTURE section, and the argparse call rewired to
reference the constant instead of `__doc__`. Verified equivalence programmatically: parsed
the ORIGINAL file (via `git show HEAD:<path>`) with `ast.get_docstring(tree, clean=False)`,
`exec`'d the NEW file's source to pull out its `_MODULE_DOC` value, and asserted the two
strings are `==` — not just "looks the same", byte-identical Python string equality. All 3
matched. The remaining 21 docstrings (11 module + 10 function) are pure documentation never
read at runtime — deleted outright, salvaged verbatim first, same as every comment.

## Script classification

All 38 scripts are read-only regression tests or one-off design/bug-repro probes. None import
`pyautogui`/`AppKit`/`Quartz` or anything that drives the real macOS desktop, switches
Spaces, sends hotkeys, or restarts the monitor. All 38 were safe to run directly for behaviour
verification. Every script only reads JSONL log files (real corpus data under
`src/logs/dual_log/`, gitignored, living in the main checkout rather than this worktree — see
the existing DOCS.md's own Gotchas, salvaged below) or synthetic in-script fixtures, and writes
only its own report file under `dev/proxy_dual_log/*_reports/` or `md/`.

## Verification strategy and what it found

Split into three groups by what "identical input" means for each script, per the milestone's
own instruction ("where no real input exists, compare pre and post functions on identical
synthetic input"):

**Group A (15 files)** — synthetic/committed-fixture scripts run end to end before/after,
stdout+exit code diffed byte-for-byte: `A_render_refactor_proof.py`+`_cases.py`+`_fixtures.py`,
`proxy_176_agent_types_tests.py`, `proxy_176_strip_tests.py`,
`proxy_176_bg_launch_ack_tests.py`+`_cases.py`+`_cases_w3.py`+`_fixtures.py`+`_report.py`,
`test_composition_invariant.py`+`composition_probe.py`+`_ops.py`+`_passes.py`+`_corpus.py`.
All matched exactly.

**Group B (19 files)** — real (non-hardcoded) live-corpus or real-file-pair scripts:
`attribution_coverage.py`+`_analyse.py`+`_classify.py`+`_report.py`; `verify_delta.py` and
`diff_strip_inject.py` (real `_original`/`_forwarded` pair from the main checkout as CLI
args); `tt_delta_skip_replay.py` (`single_workflow` against a real stem);
`main_log_elimination_probe.py`+`_io.py`+`_reconstruct.py`+`_questions.py`+`_report.py`;
`green_overlay_probe.py`+`_diff.py`+`_cases.py`; `groundtruth_message_spans_probe.py`+
`_algorithm.py`+`_cases.py`+`_report.py`.

**IMPORTANT — a real false alarm caught and resolved:** the first end-to-end run of
`attribution_coverage.py` before vs. after the edit showed DIFFERENT coverage numbers (e.g.
28.3% -> 28.2%, 1506/5320 -> 1512/5363 strip-attributed). This was NOT caused by the comment
strip — it was caused by another agent's live session actively writing new dual-log entries to
`src/logs/dual_log/` in the shared main checkout WHILE this verification ran (confirmed: the
new rows all trace to `api_requests_worker_25c51a2e_c2_1789539350`, a session stem absent from
the 'before' run's file listing but present in the 'after' run's). This is exactly the
instability the OLD DOCS.md's own Gotchas section already documented ("the dual-log corpus... is
live and growing from concurrent real sessions") — resolved by freezing a snapshot
(`cp *_stripped.jsonl *_injected.jsonl` into a temp dir) and calling `_find_pairs`/
`_analyse_all_pairs`/`_build_report` directly against that frozen snapshot for BOTH the
pre-edit code (checked out via `git stash`, run in place, then `git stash pop`) and the
post-edit code. Byte-identical. **Lesson for the next agent: never trust a live-corpus diff in
this directory without freezing the corpus first — this is a shared environment, other agents'
sessions write to the same `src/logs/dual_log/` you are reading.**

`main_log_elimination_probe.py`'s default hardcoded session and `green_overlay_probe.py`'s /
`groundtruth_message_spans_probe.py`'s hardcoded stems (e.g.
`api_requests_worker_25c51a2e_badge-recap_1780678180`,
`api_requests_opus_monitor_cc_1780517466`) do NOT exist on disk any more (old/rotated
sessions) — but every one of these three scripts degrades gracefully (a clean `sys.exit(1)`
with a printed message in `main_log_elimination_probe.py`, or a caught-and-reported
`FileNotFoundError` inside `green_overlay_probe.py`/`groundtruth_message_spans_probe.py`'s own
`try/except` blocks), so their before/after diffs are still clean and deterministic — just
mostly "ERROR loading X case" content rather than real findings. This is pre-existing behavior,
not something this pass changed.

**Group C (4 files)** — `span_inline_probe.py`+`_reconstruct.py`+`_blocks.py`+`_report.py`.
Unlike Group B's probes, `span_inline_probe_workflow()` calls `open()` directly with no
existence check and no surrounding `try/except`, so its missing hardcoded stem
(`api_requests_opus_monitor_cc_1780517466`) produces an UNCAUGHT traceback whose line numbers
shift after comment deletion — not a reliable byte-diff target. Verified instead by feeding a
small synthetic `orig_entries`/`fwd_entries` fixture directly into
`_reconstruct_chains`/`_match_requests`/`_find_sys2_block`/`_find_sys3_block`/
`_find_msg_wordlevel_block`/`_build_report` before and after — byte-identical output.

## How the strip was done

Identical tooling to the `dual_log_cli` milestone (see that area's own process-docs for the
script internals): an `ast`+`tokenize` script extracted every comment/docstring by exact
`(lineno, col)` position into this file, then a second script physically deleted them —
full-line comments and docstring line ranges removed entirely, trailing inline comments trimmed
off their code line, 3+ consecutive resulting blank lines collapsed to one. 34 of the 38 files
were actually touched by the strip; 4 files
(`A_render_refactor_proof_fixtures.py`, `span_inline_probe_reconstruct.py`,
`proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_report.py`) had zero comments
beyond the section markers to begin with, so `git status` correctly shows them unmodified —
this is expected, not a missed file.

## DOCS.md rewrite

The previous DOCS.md already used a Purpose/Reads/Writes/Called by/Calls out shape per module,
but every Purpose ran well past the 25-word limit and the file carried a longer Role paragraph,
a longer Flow paragraph, and a whole Gotchas section not in the mandated format. As with the
`dual_log_cli` milestone, rather than diff paragraph-by-paragraph against the reworded/
compressed version, the FULL previous DOCS.md is salvaged verbatim below in one block. New LOC
figures were measured with `wc -l` AFTER the comment/docstring strip, e.g. `verify_delta.py`
294 -> 279, `tt_delta_skip_replay.py` 299 -> 277, `span_inline_probe_report.py` 384 -> 370 —
every one of the 38 headings was checked against its file's actual post-strip `wc -l`, zero
mismatches.

## For the next agent

- `src/logs/dual_log/` is SHARED, live, and growing across concurrent agent sessions in this
  environment — see the "real false alarm" note above. Any before/after comparison in this
  directory that scans the live corpus (globbing `*_stripped.jsonl` etc., not a single named
  stem) needs a frozen snapshot, not a live re-scan, or you will chase a phantom regression.
- The comment-stripping and docstring-extraction scripts lived in `/tmp/` for this session and
  were never staged. Rebuild them the same way as documented in the `dual_log_cli` area's own
  process-docs if another pass is needed: `ast.get_docstring` for docstrings,
  `tokenize.COMMENT` for comments, both keyed by `(lineno, col)`.
- A generic "run a script as a subprocess and normalize its traceback" harness was built for
  this session (replace `File "<path>", line <N>, in <func>` with a version that keeps the
  line number for files OUTSIDE the edited set but blanks it for files INSIDE the edited set) —
  needed because several scripts here (`A_render_refactor_proof.py` in `--mode verify`,
  `diff_strip_inject.py` against current corpus data) hit PRE-EXISTING, unrelated bugs in
  production code (a stale baseline JSON expecting a `_stripped_spans` key
  `render_sections.py` no longer always sets; `_diff_messages` no longer emitting a `spans`
  key some call sites still expect) and crash with an uncaught traceback both before AND after
  this pass — a raw stdout/stderr diff would have falsely flagged these as regressions purely
  because the crash's OWN file's line numbers shifted when its comments were deleted. Neither
  bug is in scope for this milestone; both are pre-existing and reproduce identically on the
  unedited HEAD version of the file.
- `proxy_176_agent_types_tests.py` and `proxy_176_strip_tests.py` have NO section markers at
  all (not even `# INFRASTRUCTURE`) — this predates this pass (confirmed against `git show
  HEAD`) and is out of this milestone's negative scope ("do not restructure code"); they were
  left exactly as structurally bare as found, only their comments/docstrings were removed.
- `tt_delta_skip_replay.py`'s own docstring (now `_MODULE_DOC`) references
  `dev/proxy_dual_log/verify_strip_inject.py`, a filename that does not exist in this
  directory (probably an old name for `diff_strip_inject.py` or `verify_delta.py` from before
  a rename) — left untouched since salvaging/rewiring a docstring is not the same as auditing
  its factual claims, and the milestone's negative scope forbids content changes beyond
  comment/docstring removal.

## Salvage from dev/proxy_dual_log/verify_delta.py

Docstring (module, lines 1-23):
```

verify_delta.py — Verify forwarded delta log for losslessness and self-consistency.

Reads an _original + _forwarded JSONL pair, reconstructs each request's full forwarded
payload from the delta stream (per model-family chain), and checks two invariants:

  Check 1 (HARD): reconstructed counts == declared counts in the delta entry.
                  A violation is a delta-builder bug — always FAIL.

  Check 2 (SOFT diagnostic): forwarded counts.messages vs message count in the original.
                  A mismatch is reported with context but does NOT fail the script —
                  the proxy legitimately changes message count (msg0-strip).

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/verify_delta.py \
        src/logs/dual_log/api_requests_<id>_original.jsonl \
        src/logs/dual_log/api_requests_<id>_forwarded.jsonl

Or with named flags:
    ./venv/bin/python dev/proxy_dual_log/verify_delta.py \
        --original src/logs/dual_log/api_requests_<id>_original.jsonl \
        --forwarded src/logs/dual_log/api_requests_<id>_forwarded.jsonl

```

Comment (line 46):
```
# Load JSONL file — skip blank lines and non-JSON lines with a warning
```

Comment (lines 61-62):
```
# Build index: request_id → message count from original payload
# Falls back to per-family line-order list for empty request_ids
```

Comment (line 65):
```
# model_family → [message_count, ...]
```

Comment (line 78):
```
# Advance one model-family chain by one forwarded entry — returns (family, curr_state, model, is_first, counts)
```

Comment (line 107):
```
# Check 1 (hard): reconstructed counts == declared counts in the delta entry
```

Comment (line 120):
```
# Check 2 (soft diagnostic): forwarded counts.messages vs original message count
```

Comment (line 131):
```
# Reconstruct per-model-family chains and run both checks for every forwarded entry
```

Comment (lines 133-134):
```
# model_family → {"system": [...], "tools": [...], "messages": [...]}
# model_family → next index into original_index by_family_order
```

Comment (line 170):
```
# Lookup original message count by request_id, falling back to family-order index
```

Comment (line 174):
```
# Fallback: consume next entry in family order
```

Comment (line 183):
```
# Convert {"0": elem, "2": elem} delta dict to a list of declared_count length
```

Comment (line 193):
```
# Rough byte size of delta payload (system+tools+messages deltas only)
```

Comment (line 201):
```
# Infer model family from model string (mirrors addon.py logic)
```

Comment (line 211):
```
# Format one result row for the per-request table
```

Comment (line 243):
```
# Print the PASS/FAIL summary line after the per-request table
```

Comment (line 259):
```
# Print per-request table and PASS/FAIL summary
```

---

## Salvage from dev/proxy_dual_log/tt_delta_skip_replay.py

Docstring (module, lines 1-30):
```

tt_delta_skip_replay.py — before/after replay proving the total_tokens delta-skip.

Replays a recorded _original.jsonl through the REAL production pass pipeline
(`apply_modification_rules`, which is what produces `all_ops` in `addon.py`), then feeds
(orig_payload, fwd_payload, all_ops) into the REAL `_build_stripped_injected_deltas` — the same
call `addon.py` makes. The resulting dual-log lines are then run through the REAL read-side
`accumulate_dual_log`, so the reported badge signal is the one the pane would compute.

The suppression is READ-SIDE ONLY (`parser._msgs_delta_is_substantial`): the delta entries
themselves are written unchanged, so the expanded view keeps rendering every span. This replay
therefore checks two separate things — that the written entries are byte-identical before/after
(they must be, the writer is untouched), and that the BADGE signal drops for the noise classes.

Why a dedicated replay: `dev/proxy_dual_log/verify_strip_inject.py` calls the delta builder
WITHOUT `all_ops`, so its message section produces no spans at all and it is structurally blind
to this change (independently, it raises KeyError 'spans' on current logs — `_diff_messages` no
longer emits that key; pre-existing, untouched). `dev/proxy_instrumentation/p2_badge_words_probe.py`
and `p3_badge_inline_probe.py` reference recorded sessions that no longer exist on disk.

`--baseline` restores the pre-fix badge behavior by monkeypatching `parser._msgs_delta_is_substantial`
to the old `bool(messages_delta)` rule, so both sides of the comparison run identical code otherwise.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem>
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem> --baseline
    ./venv/bin/python dev/proxy_dual_log/tt_delta_skip_replay.py <stem> --compare

`--compare` runs both modes in one process and diffs every entry byte-wise (json, sort_keys).

```

Comment (line 43):
```
# Recorded dual-logs are untracked data living in the main checkout, not duplicated into worktrees.
```

Comment (lines 47-49):
```
# Lazy import — this module is imported both at top-level (WORKTREE_ROOT already on sys.path from
# the block above) and reused this way inside `_is_tt_msg`, mirroring `replay()`'s own late-import
# convention below (src imports deferred so this file can be inspected without src/ importable).
```

Comment (lines 70-74):
```
# True when the message is a genuine role='system' total_tokens marker OR the same marker preceded
# only by known CC nudge prose (2026-09-05, claude-f trailing-nudge widening) — delegates to the
# real `parser._is_total_tokens_nuke_text` rather than keeping a second, narrower copy of the shape
# test here, so this replay's own classification stays in agreement with the production code it is
# verifying against.
```

Comment (line 89):
```
# Replay every request of one session; returns list of (request_id, stripped_entry, injected_entry)
```

Comment (lines 119-121):
```
# Run the REAL read-side accumulator over the replayed entries -> {flow_id: has_content}.
# baseline=True restores the pre-fix rule (any non-empty messages_delta badges).
# noqa: C901
```

Comment (line 143):
```
# {flow_id: set(msg_idx)} for one side, via the same real accumulator
```

Comment (line 161):
```
# The badge pair the REQ header actually renders, via the real parser.badge_flags
```

Comment (line 180):
```
# Classify a request by what its ORIGINAL payload + baseline delta contained
```

Comment (line 230):
```
# Compute + print the per-class verdict; returns True iff every class matches expectations
```

Comment (line 236):
```
# pure total_tokens: BOTH words off
```

Comment (line 239):
```
# every other nuke / real strip: `strip` on, and `inject` on whenever a span was injected
```

Comment (lines 241-243):
```
# Implication, not equality: a green span in the messages MUST light `inject`. The converse
# does not hold — a system-section injection (proxy rules into system[2]) legitimately lights
# `inject` with no injected messages_delta at all, so equality would false-alarm on those.
```

Comment (line 277):
```
# flow_ids whose INJECTED side touched at least one message block (i.e. a span renders green there)
```

---

## Salvage from dev/proxy_dual_log/diff_strip_inject.py

Docstring (module, lines 1-22):
```

diff_strip_inject.py — Span-level strip/inject diff of Original vs Forwarded proxy logs.

Shows what the proxy stripped (STRIPPED spans) and injected (INJECTED spans) per request.
Reads _original + _forwarded JSONL pair, reconstructs the full forwarded payload from the
delta chain (per model-family), aligns blocks (system by index, tools by name, messages by
index), and classifies spans as equal / stripped / injected using difflib.

Diff strategy: word-level when SequenceMatcher.ratio() >= 0.1 (partial edits, e.g. wakeup
text injected into a message block); whole-block 2-span replacement when ratio < 0.1 (full
replacements like sys[2]: CC prompt → proxy rules, or tool descriptions stripped to "").

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \
        src/logs/dual_log/api_requests_<id>_original.jsonl \
        src/logs/dual_log/api_requests_<id>_forwarded.jsonl

Or with named flags:
    ./venv/bin/python dev/proxy_dual_log/diff_strip_inject.py \
        --original src/logs/dual_log/api_requests_<id>_original.jsonl \
        --forwarded src/logs/dual_log/api_requests_<id>_forwarded.jsonl

```

Comment (line 66):
```
# Inline of verify_delta.py reconstruction logic — same algorithm, self-contained
```

---

## Salvage from dev/proxy_dual_log/span_inline_probe.py

Docstring (module, lines 1-17):
```

span_inline_probe.py — Form A vs Form B inline-render data model probe.

Validates that Form B (full ordered span list per log) is the minimal enrichment
that lets the read-side render strip/inject inline without content duplication.
Shows Form A's empirical failure via concrete offset/substring mismatches on real data.

Probes 3 representative blocks from log api_requests_opus_monitor_cc_1780517466:
  B1 — sys[2] full-replace (CC prompt → proxy rules, ratio<0.1, no equal spans)
  B2 — sys[3] strip-to-dot (whole original stripped, '.' injected, no equal spans)
  B3 — msg[N][0] word-level mixed (equal + stripped + injected, with cache_control diff)

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/span_inline_probe.py

Output: dev/proxy_dual_log/span_inline_probe_reports/<YYYYMMDD>.md

```

Comment (line 27):
```
# Load diff_engine directly from path — keeps probe independent of src/ package structure
```

---

## Salvage from dev/proxy_dual_log/span_inline_probe_reconstruct.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_dual_log/span_inline_probe_blocks.py

Comment (line 6):
```
# Inline: mirrors src/proxy/logging.py:_strip_cache_control — strip "cache_control" keys recursively
```

Comment (line 28):
```
# sys[2] full-replace: CC prompt → proxy rules. ratio<0.1, 2 spans.
```

Comment (line 52):
```
# sys[3] strip-to-dot: whole text → '.'. ratio<0.1, 2 spans.
```

Comment (lines 76-79):
```
# First message block with equal+stripped+injected spans AND cache_control diff present.
#
# The cc_diff requirement ensures the block shows the cache_control normalization
# mismatch that makes Form A's equal-span text invalid as a raw-text anchor.
```

Comment (line 99):
```
# no cache_control diff — skip
```

---

## Salvage from dev/proxy_dual_log/span_inline_probe_report.py

Comment (line 16):
```
# Text mock: [=] gray  [-] yellow  [+] green. Each content unit once.
```

Comment (lines 26-29):
```
# Split full span sequence into per-log Form B views.
#
# _stripped_log: equal + stripped spans in order (equal spans duplicated as anchors)
# _injected_log: equal + injected spans in order (equal spans duplicated as anchors)
```

Comment (lines 36-39):
```
# Merge per-log Form B into 3-color sequence by equal-anchor alignment.
#
# Lock-step: consume stripped spans from stripped_log and injected from injected_log;
# advance through equal anchors together.
```

Comment (lines 71-75):
```
# Compute Form A positions and test whether they survive cache_control normalization.
#
# For each span: locate text as substring in the relevant reference text (normalized
# and raw). 'equal' span key test: exact span text NOT found in fwd_raw = Form A breaks.
# Texts >500c are probed via prefix only (marked probe_len<text_len).
```

---

## Salvage from dev/proxy_dual_log/main_log_elimination_probe.py

Docstring (module, lines 1-30):
```

main_log_elimination_probe.py — Feasibility probe for eliminating the main log.

Answers two questions on a real session:

  Question A (Forwarded reconstruction):
    Accumulate _forwarded delta log into a full forwarded payload per request.
    Diff against main log raw_payload (pre-cache-ops) after normalising cache_control.
    Report content match, BP-count divergence, and missing top-level fields.

  Question B (Error extraction):
    Extract is_error==True tool_result blocks from _original payloads.
    Dedup by tool_use_id. Compare against tool_errors.jsonl for this session.

Session data:
  Main log:     src/logs/api_requests_<session>.jsonl
  Quartet:      src/logs/dual_log/api_requests_<session>_{original,forwarded,...}.jsonl
  Tool errors:  src/logs/tool_errors.jsonl

Matching strategy: positional — entry N in _forwarded == request entry N in main log.
Both are written by the same serial proxy request() hook in identical order.
Request IDs are empty in quartet (CC sends no x-request-id header); main log uses UUID4.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/main_log_elimination_probe.py <session_suffix>

    <session_suffix> is the log_id portion, e.g. opus_monitor_cc_1780602018

    Paths are resolved relative to the project root (MONITOR_CC_ROOT or auto-detected).

```

Comment (line 61):
```
# Resolve log file path from session suffix
```

---

## Salvage from dev/proxy_dual_log/main_log_elimination_io.py

Comment (line 9):
```
# Resolve project root from env or __file__
```

Comment (line 17):
```
# Build all log file paths for the session
```

Comment (line 31):
```
# Fail-fast if any required log file is missing
```

Comment (line 40):
```
# Load JSONL, skip blank lines and bad JSON
```

Comment (line 55):
```
# Load main log — return only request entries (no type field), preserving order
```

Comment (line 61):
```
# Load tool_errors.jsonl — filter by proxy_file containing session suffix
```

---

## Salvage from dev/proxy_dual_log/main_log_elimination_questions.py

Comment (line 11):
```
# Compare one main-log request entry against its reconstructed forwarded counterpart
```

Comment (line 61):
```
# Run Question A: compare reconstructed forwarded payloads against main log raw_payloads
```

Comment (line 94):
```
# Scan _original payloads for is_error tool_result blocks, dedup by tool_use_id
```

Comment (line 133):
```
# Run Question B: extract is_error tool_result blocks from _original, dedup by tool_use_id
```

---

## Salvage from dev/proxy_dual_log/main_log_elimination_reconstruct.py

Comment (line 4):
```
# Fields classification: which raw_payload top-level fields are needed by proxy pane vs metadata-only
```

Comment (line 21):
```
# system / tools / messages are reconstructed from the delta; model is in the delta entry header
```

Comment (line 26):
```
# Recursively strip cache_control keys — verbatim copy of src/proxy/logging.py:_strip_cache_control
```

Comment (line 35):
```
# Mirror of cache._normalize_user_content_shape — verbatim copy of src/proxy/logging.py:_normalize_msg_shape_for_hash
```

Comment (line 50):
```
# Infer model family from model string — mirrors src/proxy_display/parser.py:_infer_model_family
```

Comment (line 60):
```
# Count cache_control markers recursively in a payload element
```

Comment (lines 70-72):
```
# Reconstruct full forwarded payloads from the delta stream, per-model-family.
# Returns list of dicts matching order of forwarded entries:
#   {model, system, tools, messages, is_first, counts}
```

Comment (line 74):
```
# family → {system: [], tools: [], messages: []}
```

Comment (line 115):
```
# Expand {idx_str: elem} dict into list of length n, filling gaps with None
```

Comment (line 125):
```
# Normalize a reconstructed element for comparison: strip cache_control + normalize msg shape
```

Comment (line 133):
```
# Return list of (idx, note) for element-level divergences between two normalized lists
```

Comment (line 144):
```
# Classify raw_payload keys into delta-covered, proxy-pane-needed, metadata-only, other
```

---

## Salvage from dev/proxy_dual_log/main_log_elimination_report.py

Comment (lines 17-18):
```
# Question A: Method + Content Match Summary + Cache_control (BP) divergence table.
# Returns (lines, all_content_lossless).
```

Comment (lines 81-82):
```
# Field classification table + must-add + metadata-only lists.
# Returns (lines, must_add, meta_only).
```

Comment (line 200):
```
# Write the markdown report and return its path
```

---

## Salvage from dev/proxy_dual_log/green_overlay_probe.py

Docstring (module, lines 1-8):
```

Probe: green-overlay false-injection bug in _diff_text (word-level path).
Reproduces the bug on real log data and validates the char-level candidate fix.
Self-contained — all helpers copied from src/; no src/ imports at module level.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/green_overlay_probe.py

```

Comment (line 195):
```
# Build and write the probe report (Level 2: gating soundness + three-variant comparison)
```

---

## Salvage from dev/proxy_dual_log/green_overlay_probe_diff.py

Comment (line 5):
```
# from src/proxy/diff_engine.py
```

Comment (line 7):
```
# Copied from src/proxy/strip_vocab.py RULES — marker substrings only (attribution needs them)
```

Comment (line 18):
```
# skip — no markers
```

Comment (line 29):
```
# Copied from src/proxy/logging.py
```

Comment (line 45):
```
# Copied from src/proxy/diff_engine.py — exact production implementation
```

Comment (line 59):
```
# Copied from src/proxy/logging.py — strips cache_control recursively
```

Comment (line 68):
```
# Copied from src/proxy/logging.py — normalizes single-text-block user messages
```

Comment (line 83):
```
# Current (buggy) word-level _diff_text — exact copy of src/proxy/diff_engine.py
```

Comment (line 109):
```
# Candidate fix: char-level _diff_text — keeps early-exit branches, replaces word-level path
```

Comment (line 134):
```
# Copied from src/proxy/strip_vocab.py:attribute_chunk — marker-based rule attribution
```

Comment (line 147):
```
# Mirrored from src/proxy/logging.py inject-attribution block (~line 421)
```

Comment (lines 157-159):
```
# Level-2 fix: char-level diff + gate phantom injected spans via attribution
# Injected span with fn="unknown" → reclassify to equal (grey).
# Injected span with known fn → keep green. Maintains fidelity (gated equal still in fwd recon).
```

Comment (line 165):
```
# phantom → grey
```

Comment (line 171):
```
# Verify char-level reconstruction fidelity — equal+stripped must rebuild o_text, equal+injected must rebuild f_text
```

Comment (line 178):
```
# Format span list for report (truncate long values)
```

Comment (line 187):
```
# Run all three variants on a pair and return comparison record
```

Comment (line 193):
```
# gated fidelity: gated equal (was injected) counts toward fwd; stripped+equal count toward orig
```

---

## Salvage from dev/proxy_dual_log/green_overlay_probe_cases.py

Comment (lines 9-10):
```
# Main project layout:  <project>/dev/proxy_dual_log/  → parents[1] = project root
# Worktree layout:      <project>/.claude/worktrees/<name>/dev/proxy_dual_log/ → parents[4] = project root
```

Comment (line 17):
```
# Scan live _injected logs: classify msg.* unknown entries as phantom vs potentially-real
```

Comment (line 50):
```
# Load first matching entry by flow_id from a JSONL file
```

Comment (line 60):
```
# Extract primary bug case: badge-recap worker, msg[18] blk[0], system-reminder stripped
```

Comment (line 79):
```
# Helper: get (o_text, f_text) for a given flow_id + msg index + block index
```

Comment (line 105):
```
# Extract 3 regression cases from badge-recap worker log — all ratio >= 0.1 (word-level path)
```

Comment (line 110):
```
# R1: stripped log line 3 — msg[2] blk[0], ratio=0.764, partial JSON token replacement
```

Comment (line 118):
```
# R2: stripped log line 4 — msg[4] blk[0], ratio=0.993, tiny edit in large block
```

Comment (line 124):
```
# R3: stripped log line 21 — msg[38] blk[0], ratio=0.951, another system-reminder strip
```

Comment (line 130):
```
# R4: synthetic whitespace-collapse test — word-level joins with single space, losing original spacing
```

---

## Salvage from dev/proxy_dual_log/groundtruth_message_spans_probe.py

Docstring (module, lines 1-24):
```

Probe: ground-truth message span construction — validates the GT algorithm as a replacement
for the blind _diff_text span builder.

Builds spans from GROUND TRUTH (exact stripped chunks from apply_modification_rules) instead
of diffing, and verifies fidelity + zero phantom on real log data.

Algorithm under test (build_message_spans):
  1. Split orig_text at exact positions of each stripped_chunk → alternating EQUAL + STRIPPED.
  2. Walk fwd_text matching each EQUAL segment in sequence.
  3. Text in fwd_text between matched EQUAL segments = INJECTED (real placeholder).
  4. Emit spans: equal / stripped / injected.

Data source: option (b) — re-run apply_modification_rules on _original dual-log payload.
  Rationale: stripped_msg_removed not yet written to main logs (Stage-3 write-side pending).
  Re-running on the same original payload regenerates the exact chunks. Validation:
  mod_payload content == forwarded_delta content (checked per case).
  Caveat: later-pass chunks extracted from intermediate (not original) content — may be nested
  inside earlier-pass chunks (detected and flagged as NESTED_CHUNK).
  Env-context SR stripped as side effect of SK pass is NOT recorded (RECORDING_GAP).

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/groundtruth_message_spans_probe.py

```

---

## Salvage from dev/proxy_dual_log/groundtruth_spans_algorithm.py

Comment (line 5):
```
# from src/proxy/diff_engine.py
```

Comment (line 9):
```
# ── helpers (minimal copies from src/) ───────────────────────────────────────
```

Docstring (function `_get_text`, lines 34-34):
```
Production _get_text from diff_engine.py — returns JSON dump for non-text blocks.
```

Docstring (function `_get_inner_text`, lines 48-52):
```
Inner content text the proxy actually operates on — used for GT spans.
    text blocks        → block["text"] (raw string, same as _get_text)
    tool_result blocks → block["content"] (raw string, avoids JSON-escape mismatch)
    other dicts        → json.dumps (same as _get_text)
    
```

Comment (line 71):
```
# ── diff_text_word (current production, copied from green_overlay_probe) ─────
```

Comment (line 98):
```
# ── GT algorithm under test ───────────────────────────────────────────────────
```

Comment (line 100):
```
# Step 1: split orig_text at stripped_chunk positions → equal_segs + stripped_segs + flags
```

Comment (lines 109-110):
```
# Chunk not found at or after pos — may be nested inside a prior stripped segment
# or a recording gap from intermediate-pass extraction
```

Comment (line 115):
```
# skip: already covered or unresolvable
```

Comment (line 119):
```
# final equal segment (may be "")
```

Comment (line 123):
```
# Step 2 + 3: walk fwd_text matching each equal segment; gaps = injected
```

Comment (line 130):
```
# Emit preceding stripped segment (if any)
```

Comment (line 138):
```
# best-effort
```

Comment (line 145):
```
# Any remaining fwd_text = injected
```

Comment (lines 149-150):
```
# Safety: if the loop emitted nothing (all equal_segs empty AND stripped_segs non-empty),
# emit stripped_segs directly. This handles the full-replace case where o_text == chunk.
```

Docstring (function `build_message_spans`, lines 161-166):
```
Build ground-truth spans from exact stripped chunks.

    Returns: (spans, flags) where
      spans = [(tag, text), ...] tags: 'equal' / 'stripped' / 'injected'
      flags = list of issue strings (NESTED_CHUNK / EQUAL_NOT_IN_FWD / CHUNK_NOT_IN_ORIG)
    
```

Comment (line 170):
```
# no-strip fallback
```

Comment (line 178):
```
# ── fidelity check ─────────────────────────────────────────────────────────
```

Docstring (function `check_fidelity`, lines 181-181):
```
Lossless: equal+stripped must rebuild orig_text; equal+injected must rebuild fwd_text.
```

Docstring (function `check_fidelity_diff`, lines 188-188):
```
Fidelity for diff_text_word — same check but compensates for whitespace join loss.
```

---

## Salvage from dev/proxy_dual_log/groundtruth_spans_cases.py

Comment (line 14):
```
# ── data loading ─────────────────────────────────────────────────────────────
```

Comment (line 30):
```
# ── case builders ─────────────────────────────────────────────────────────────
```

Docstring (function `get_bug_case`, lines 33-33):
```
Primary bug case: badge-recap, msg[18] blk[0], tool_result with SR strip.
```

Comment (line 56):
```
# Validate mod == fwd (re-run matches forwarded log)
```

Comment (line 63):
```
# JSON-dump level texts for phantom demo (production diff_engine path)
```

Docstring (function `get_text_block_replace_case`, lines 74-74):
```
badge-recap, msg[0] blk[0]: pure text block that is entirely the DEF SR → replaced with '.'
```

Comment (line 91):
```
# Assign per-block chunks: chunk[0] belongs to blk[0] (DEF SR = full block text)
```

Comment (line 96):
```
# Recording-gap check for blk[2]
```

Comment (line 112):
```
# validated manually in probe data analysis
```

Docstring (function `get_bg_exit_replace_case`, lines 118-118):
```
monitor_cc, msg[78] blk[0]: TN stripped + BG command stripped + wakeup injected.
```

Docstring (function `get_multi_chunk_case`, lines 150-150):
```
badge-recap msg[0] blk[1]: SK SR (5776/5777 chars) — tests large-SR strip fidelity.
```

---

## Salvage from dev/proxy_dual_log/groundtruth_spans_report.py

Comment (line 6):
```
# ── formatting helpers ────────────────────────────────────────────────────────
```

Docstring (function `phantom_green_check`, lines 17-17):
```
Return injected spans that look like phantom JSON structure artefacts.
```

Comment (line 22):
```
# Phantom pattern: JSON structural chars (comma, brace, bracket, quote)
```

Comment (line 29):
```
# ── run a single case ─────────────────────────────────────────────────────────
```

Comment (line 32):
```
# diff_text_word on inner-content level (same input as GT, fair comparison)
```

Comment (lines 35-36):
```
# For tool_result blocks: also run diff_text_word on json.dumps level
# (the actual production path) to show the phantom green
```

Comment (line 89):
```
# ── report sections ───────────────────────────────────────────────────────────
```

Comment (line 193):
```
# Separate precision-gap cases from true failures
```

---

## Salvage from dev/proxy_dual_log/composition_probe.py

Docstring (module, lines 1-19):
```

Probe: multi-pass composition — position-anchored ops rebased over C0.

Validates that per-pass ops (offset_in_Ck, removed, injected) derived from
(before_pass, after_pass) block-text pairs compose into a single span list
over C0 satisfying byte-exact reconstruction:

  Inv1: "".join(t for tag,t in spans if tag in ("equal","stripped")) == C0_block_text
  Inv2: "".join(t for tag,t in spans if tag in ("equal","injected")) == Cfwd_block_text

Op extraction: common-prefix/suffix on each pass's (before_pass, after_pass) block-text pair.
Stand-in for what production passes would record directly; validated by the invariants.

Also models _dedup_wakeup_blocks as a final composition pass (Layer-1 payload modification)
and proves the money-shot: msg[100] TN+BG double-inject produces exactly ONE injected wakeup.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/composition_probe.py

```

Comment (line 37):
```
# Format span list for report output
```

Comment (line 109):
```
# Runs the full corpus, emits the summary table + failing cases; returns R (or None on error)
```

---

## Salvage from dev/proxy_dual_log/composition_probe_ops.py

Comment (line 6):
```
# Recursively strip cache_control keys
```

Comment (line 15):
```
# Inner content text the proxy actually operates on (mirrors diff_engine._get_inner_text)
```

Comment (line 35):
```
# Extract inner text for a specific block index from a message content value
```

Comment (lines 46-48):
```
# Extract minimal (offset, removed, injected) op from a single-pass (before, after) pair.
# Uses common-prefix/suffix — handles all pass types including TN transform.
# In production each pass records its op directly; this is the probe stand-in.
```

Comment (lines 64-72):
```
# Apply one edit op (offset_in_Ck, removed, injected) to a span list.
#
# Ck = "".join(t for tag,t in spans if tag in ("equal","injected"))
#
# Rules for Ck bytes in [offset, offset+len(removed)):
#   "equal"    → "stripped"  (C0 bytes being removed from forwarded content)
#   "injected" → disappears  (prior injection being re-removed by a later pass)
# "stripped" spans are invisible to Ck — copied unchanged.
# Both invariants maintained after every call.
```

Comment (line 106):
```
# mid_t with tag="injected" disappears (prior injection re-removed)
```

Comment (line 118):
```
# Return [(blk_idx, before_text, after_text)] for changed blocks
```

Comment (line 139):
```
# Compose all ops for one block into a single span list over C0
```

Comment (line 147):
```
# Check both reconstruction invariants; return (ok, details_str)
```

---

## Salvage from dev/proxy_dual_log/composition_probe_passes.py

Comment (line 12):
```
# Use directly-recorded ops from the pass's 6th return value
```

Comment (line 20):
```
# Stand-in for passes not yet migrated to op recording
```

Comment (lines 28-31):
```
# Run all passes sequentially, collecting per-block ops in Ck coordinates.
# Lazy-imports src/ pass functions to avoid top-level hook block.
# Returns (final_messages, ops_by_msg_blk) where
#   ops_by_msg_blk[msg_idx][blk_idx] = [(pass_name, offset, removed, injected), ...]
```

Comment (line 38):
```
# Passes with real op recording (result[5]) — 1A: po_preview, hook_prefix, git_lock, bd_noise; 1B: bg_exit; 1C: cumulative_sr, final_sr; 1D: first_pass — ALL passes now real, no stand-in
```

Comment (line 63):
```
# Dedup wakeup — Layer-1 payload modification, uses real ops from _dedup_wakeup_blocks (1B)
```

---

## Salvage from dev/proxy_dual_log/composition_probe_corpus.py

Comment (line 23):
```
# Check one block's invariants; update pass_stats/failed_cases; return (ok, is_multi, is_double_inject)
```

Comment (line 55):
```
# Scan one corpus entry, updating stats in place
```

Comment (line 85):
```
# Run all entries across all stems; return stats + failing cases
```

Comment (line 122):
```
# Detailed trace for msg[100] TN+BG double-inject money-shot case
```

---

## Salvage from dev/proxy_dual_log/attribution_coverage.py

Docstring (module, lines 1-11):
```

attribution_coverage.py — Function-attribution coverage analysis for _stripped/_injected dual-logs.

Answers: can every strip AND inject entry in the dual-logs be attributed to a responsible
function?  Key output: RESIDUAL (entries no named function claims) + json_reserialization bug.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/attribution_coverage.py

Output: dev/proxy_dual_log/attribution_coverage_reports/<YYYYMMDD>.md

```

Comment (line 21):
```
# Load strip_vocab from src via path — block_dev_imports_src hook forbids literal `from src.`
```

Comment (line 29):
```
# Logs live in main repo — if not in worktree direct path, navigate up from .claude/worktrees/<name>/
```

---

## Salvage from dev/proxy_dual_log/attribution_coverage_classify.py

Comment (line 3):
```
# Inject function map for sys delta and fields delta
```

Comment (line 25):
```
# Detect new injected span format: first item in a list is a [tag, text] pair
```

Comment (line 33):
```
# Extract plain text from an injected list (handles both old flat-string and new span-tuple formats)
```

Comment (lines 42-44):
```
# Check if an inject block value is a json_reserialization artifact
# Old format: first item is a JSON string starting with '[{"type":'
# New format: the injected span text starts with '[{"type":'
```

Comment (lines 57-60):
```
# Classify a stripped message block → (tier, category)
# tier: 'vocab' | 'residual' | 'false_pos' | 'unattr'
# Vocab/residual checks run FIRST: a TN block whose message was also json_reserialized
# should be classified TN (the proxy strip), not json_reser (the format-change side-effect).
```

Comment (line 62):
```
# Known strip_vocab markers: check each stripped text chunk independently
```

Comment (lines 68-70):
```
# False positive: json_reserialization (string content → block-list, cache.py side effect)
# Only checked AFTER all proxy-strip patterns fail — json_reser is the fallback for
# blocks whose injected counterpart is a block-list JSON string but carry no strip marker.
```

Comment (line 77):
```
# Classify an inject message block → (tier, category)
```

Comment (line 79):
```
# json_reserialization artifact (appears at same midx/bidx as a stripped entry)
```

Comment (line 82):
```
# BGK replacement injection: background done text
```

Comment (line 91):
```
# Compute coverage percentage numerics
```

---

## Salvage from dev/proxy_dual_log/attribution_coverage_analyse.py

Comment (line 12):
```
# Discover all paired (stripped, injected) paths
```

Comment (line 22):
```
# Load a JSONL file — returns list of dicts
```

Comment (line 120):
```
# Analyse all pairs and return aggregated stats
```

Comment (line 122):
```
# strip_stats[section][fn_or_cat] = count
```

Comment (line 125):
```
# residuals: list of (pair_name, section, location_key, content_preview)
```

Comment (line 127):
```
# false_positives: list of (pair_name, section, location_key, s_text, i_text) for evidence
```

Comment (line 134):
```
# Index injected by request_id
```

---

## Salvage from dev/proxy_dual_log/attribution_coverage_report.py

Comment (line 8):
```
# Load strip_vocab from src via path — block_dev_imports_src hook forbids literal `from src.`
```

Comment (line 236):
```
# Build the Markdown report
```

---

## Salvage from dev/proxy_dual_log/A_render_refactor_proof.py

Docstring (module, lines 1-15):
```

Render refactor proof harness: byte-identical differential test for proxy_display render cluster.

Usage (from project root):
    ./venv/bin/python dev/proxy_dual_log/A_render_refactor_proof.py --mode capture
    ./venv/bin/python dev/proxy_dual_log/A_render_refactor_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- run all 14 cases, write (ansi_string, total_lines) to baseline JSON
    verify   -- run all 14 cases, assert byte-identical against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: format_proxy_block(entries, expand_states, ...) — exercises all 5 targets
transitively: render_messages, _render_entry_lines, render_tools, render_turn_expanded,
format_proxy_block itself.

```

Comment (line 108):
```
# Iterates: render → expand all visible keys → repeat until line_map stable (fixpoint)
```

---

## Salvage from dev/proxy_dual_log/A_render_refactor_proof_fixtures.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_dual_log/A_render_refactor_proof_cases.py

Comment (line 25):
```
# Branch 1: new messages, no dual, two blocks including thinking
```

Comment (line 38):
```
# Branch 1: stripped messages — EFF path (removed_chunks present) + IDX path (originals only)
```

Comment (lines 42-43):
```
# stripped idx=1: EFF path
# stripped idx=2: IDX path
```

Comment (line 56):
```
# Branch 2: content_tail fallback (no blocks, modified message with tail)
```

Comment (line 66):
```
# Branch 2: removed_from_prev tail (prev has more messages)
```

Comment (line 76):
```
# Dual spans new-format: i_blk as list of (tag, text) tuples; s_blk as plain strings
```

Comment (line 90):
```
# Dual spans legacy: i_blk as plain strings; s_blk as plain strings
```

Comment (line 104):
```
# Tools section: first request (prev has no tools_hash) — tool header + desc + schema
```

Comment (line 123):
```
# Tools section: tools changed (added 'python', removed 'bash')
```

Comment (line 142):
```
# System blocks section: two blocks, both expanded
```

Comment (line 156):
```
# Standalone haiku entry (is_standalone_entry = True, num_label = 'H')
```

Comment (line 163):
```
# copy_feedback ON: frozen future timestamp → always shows '✓' flash
```

Comment (line 174):
```
# hover_row + scroll_offset: smaller pane forces scrolling, row 2 is hovered
```

Comment (line 185):
```
# Collision: two turn groups both produce label '#0.1' → COLLISION_BG path
```

Comment (line 197):
```
# Expand-ALL fixpoint: kitchen-sink two entries, iterated until stable
```

---

## Salvage from dev/proxy_dual_log/proxy_176_agent_types_tests.py

Docstring (module, lines 1-8):
```
Unit tests for CC 2.1.176 agent-types SR strip (Item 3).

Fixture: standalone <system-reminder>-wrapped text block in a role='user' message,
~2353 chars, starts '<system-reminder>
Available agent types for the Agent tool:'.

Run from project root:
    ./venv/bin/python dev/proxy_176_agent_types_tests.py

```

Comment (line 26):
```
# Realistic fixture: agent-types SR as a text block in a list-content user message
```

Comment (line 36):
```
# pad to ~2353c
```

Comment (line 40):
```
# messages[0].content is a list (block-array), block[0] is a tool_result, block[1] is the agent-types SR
```

Comment (line 49):
```
# Pure-string content variant
```

Comment (line 61):
```
# SR block removed from the text block
```

Comment (line 129):
```
# Simulate: original user message has SR; modified has it stripped
```

---

## Salvage from dev/proxy_dual_log/proxy_176_bg_launch_ack_tests.py

Docstring (module, lines 1-8):
```
Unit tests for CC 2.1.176 background-launch-ack strip (Item 4).

Fixtures: launch-ack as tool_result string AND as standalone text block.
Marker: 'running in background with ID'.

Run from project root:
    ./venv/bin/python dev/proxy_176_bg_launch_ack_tests.py

```

---

## Salvage from dev/proxy_dual_log/proxy_176_bg_launch_ack_fixtures.py

Comment (line 3):
```
# Realistic fixture text (~130c, stable prefix)
```

Comment (lines 11-12):
```
# 2026-07-29: replacement is now 3 lines (msg + Output: <path> + ID: <id>, both recovered from
# _LAUNCH_ACK above), not a single-sentence "." placeholder.
```

Comment (line 20):
```
# Completion notification — must NOT be falsely triggered
```

Comment (lines 23-24):
```
# FP fixtures — each CONTAINS the marker phrase but does NOT start with the ack prefix.
# Simulates large tool_result / pasted user content that quotes the phrase as data.
```

Comment (lines 60-62):
```
# Wording 2 (2026-07-29 milestone-2) — user manually backgrounds an already-running Bash call.
# No trailing ". You will be notified..." sentence; ack IS the complete block in the only
# measured corpus occurrence (dev/bg_wakeup_id_line/md/launch_ack_wordings_20260729.md).
```

Comment (line 75):
```
# FP fixture — CONTAINS the wording-2 marker phrase but does NOT start with the ack prefix.
```

Comment (lines 88-93):
```
# Wording 3 (2026-09-14 milestone) — CC auto-backgrounds a Bash call that exceeded its own
# timeout (not a deliberate/manual launch). Exact text taken verbatim from
# src/logs/dual_log/api_requests_opus_monitor_cc_1789383190_original.jsonl. Unlike wording 1/2, this
# one carries a trailing "Session cwd remains ..." sentence in the SAME block — the strip discards it
# along with the rest of the matched ack, same as it already discards any trailing content for
# wording 2 (see W24 in dev/proxy/test_strip_fix.py).
```

Comment (line 112):
```
# FP fixture — CONTAINS the wording-3 marker phrase but does NOT start with the ack prefix.
```

---

## Salvage from dev/proxy_dual_log/proxy_176_bg_launch_ack_report.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_dual_log/proxy_176_bg_launch_ack_cases.py

(no comments or docstrings in this file)

---

## Salvage from dev/proxy_dual_log/proxy_176_bg_launch_ack_cases_w3.py

Comment (lines 22-28):
```
# ── LAUNCH-ACK WORDING 3: AUTO-BACKGROUNDED ON TIMEOUT (2026-09-14 milestone) ─────────────────
# Third CC wording — Bash exceeded its own timeout and CC moved it to the background on its own,
# distinct from wording 1 (deliberate run_in_background) and wording 2 (user manually backgrounds
# an already-running call). The replacement message must still say "timeout" so the reader can
# tell this apart from a deliberate background launch (see process-docs/proxy_dual_log/ area note
# for the 2026-09-14 entry) — this is why wording 3 gets its OWN message constant
# (_BG_AUTO_TIMEOUT_MSG/_MAIN) rather than reusing _BG_LAUNCH_ACK_MSG.
```

Comment (lines 131-138):
```
# ── FULL-REPLACEMENT SPAN SHAPE (2026-07-29 milestone-3) ──────────────────────
# _apply_bg_launch_ack_strip is one of the 3 full_replace=True call sites in message_passes.py
# (src/proxy/rule_ops.py::_extract_block_op). Before this milestone, the recorded op trimmed the
# shared "Command " prefix between the ack and its replacement, so the pane rendered "Command "
# unhighlighted on its own line, then the rest green below (live-observed 2026-07-29). This test
# pins BOTH the op shape (one contiguous op, no trim) and the composed span shape (one contiguous
# stripped span + one contiguous injected span — no interleaved "equal" fragment) against the real
# launch-ack fixture, through the real production functions.
```

Comment (lines 169-174):
```
# ── MAIN-CONTEXT WORDING SHARPENING (2026-08-06 milestone-2) ──────────────────
# Folded in from dev/timer-loop/p2_pending_bg_state_probe.py (Test 12) when that probe was
# deleted (Milestone 3, 2026-08 — its subject module src/proxy/pending_bg_state.py was removed
# and this was the one still-relevant, otherwise-uncovered case in it: is_main is unrelated to
# pending_bg_state, it selects strip_bg_launch_ack.py's replacement wording via
# _apply_bg_launch_ack_strip's own is_main param). See process-docs/timer-loop/ for the removal.
```

---

## Salvage from dev/proxy_dual_log/proxy_176_strip_tests.py

Docstring (module, lines 1-8):
```
Unit tests for CC 2.1.176 proxy drift fixes.

Fix 1: 'Workflow' added to TOOL_BLOCKLIST → _strip_unused_tools removes it.
Fix 2: _apply_role_system_strip strips role='system' messages unconditionally.

Run from project root:
    ./venv/bin/python dev/proxy_176_strip_tests.py

```

Comment (line 34):
```
# Fix 1 — Workflow removed by _strip_unused_tools
```

Comment (line 53):
```
# Fix 2 — _apply_role_system_strip
```

Comment (line 130):
```
# Attribution — role-based code='RS' in _process_messages_section
```

Comment (line 139):
```
# Build ops the same way the pass does
```

---

## Salvage from dev/proxy_dual_log/test_composition_invariant.py

Docstring (module, lines 1-17):
```

CI regression test: composition invariant over synthetic fixture corpus.

Asserts that for every modified block across all 9 fixture entries:
  Inv1: "".join(t for tag,t in spans if tag in ("equal","stripped")) == C0_block_text
  Inv2: "".join(t for tag,t in spans if tag in ("equal","injected")) == Cfwd_block_text

A future pass that mutates content without recording an op breaks these invariants.
The fixture covers all 8 proxy passes + dedup_wakeup, including the money-shot
double-inject pattern (fix-3: TN with BG summary → first_pass + bg_exit + dedup_wakeup).

Run (from project root):
    ./venv/bin/python dev/proxy_dual_log/test_composition_invariant.py

Exit 0 = all blocks pass both invariants.
Exit 1 = at least one invariant violation (prints which entry/block/pass/detail).

```

Comment (line 39):
```
# Load fixture entries — hard-fail if file absent (absent fixture = broken test, not a skip)
```

Comment (line 66):
```
# Run both invariants for every modified block across all fixture entries
```

---

## Salvage from dev/proxy_dual_log/DOCS.md

Full previous content of dev/proxy_dual_log/DOCS.md before the module-standards conformance
rewrite (Role/Flow prose reworded, Modules compressed to fit the word limits, and the
Gotchas section removed entirely since it is not part of the mandated DOCS.md format):

```markdown
# dev/proxy_dual_log/

## Role
Verification suite for the dual-log quartet (`_original`/`_forwarded`/`_stripped`/`_injected`)
written by `src/proxy/addon.py` under src/logs/dual_log. Proves losslessness and self-consistency of
the forwarded-delta log against the original log, and completeness of the strip/inject diff engine
(`src/proxy/diff_engine.py`). Touch when changing the dual-log write side, the diff engine, or the
read-side badge/render logic that consumes `_stripped`/`_injected`.

## Flow
Each script reads one or more dual-log JSONL files (or synthetic fixtures), replays the delta chain
or the real modification pipeline, and either asserts an invariant (exit 1 on violation) or writes a
findings report to `md/`. Every top-level probe/test script here is a thin CLI entry point whose
INFRASTRUCTURE/ORCHESTRATOR/FUNCTIONS live in the file itself; scripts over ~400 LOC or with a
function at 50+ lines are split into same-directory sibling modules by concern (algorithm, case
data, report rendering, I/O) — each sibling is a plain `INFRASTRUCTURE` + `FUNCTIONS` helper module
(no `ORCHESTRATOR`, per the Utility-module exception) imported back into the CLI entry point.

## Modules

### verify_delta.py (294 LOC)

**Purpose:** Reconstructs the full forwarded payload from a `_forwarded.jsonl` delta stream
(per-model-family chain) and verifies element counts match the delta entry's own declared counts
(hard check), plus a soft diagnostic comparing message counts against the original log.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** a per-request table and PASS/FAIL summary to stdout.
**Called by:** none — manual CLI, exits 1 on a hard-check failure.
**Calls out:** none at import time — parses JSONL directly.

---

### tt_delta_skip_replay.py (299 LOC)

**Purpose:** Before/after proof for the read-side `<total_tokens>N tokens left</total_tokens>` badge
suppression (including its trailing-nudge variant). Replays an `_original.jsonl` through the real
`apply_modification_rules`, feeds the result into the real `_build_stripped_injected_deltas`, and
runs the resulting dual-log lines through the real `accumulate_dual_log`/`badge_flags`, comparing the
old one-to-one badge rule against the current one via `--compare`.
**Reads:** a dual-log stem's `_original.jsonl`/`_stripped.jsonl`/`_injected.jsonl` triplet under the
main checkout's src/logs/dual_log (gitignored runtime data).
**Writes:** PASS/FAIL classification report to stdout.
**Called by:** none — manual CLI, exits 1 if a class regresses.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`), `src.proxy_display.dual_log_accumulator`,
`src.proxy_display.proxy_badge`.

---

### diff_strip_inject.py (252 LOC)

**Purpose:** Span-level strip/inject diff of an original vs. forwarded proxy log pair — reconstructs
the forwarded payload from the delta chain, aligns blocks (system by index, tools by name, messages
by index), and classifies spans as equal/stripped/injected via `difflib`. Word-level diff when
`SequenceMatcher.ratio() >= 0.1`, whole-block 2-span replacement below that threshold.
**Reads:** an `_original.jsonl` + `_forwarded.jsonl` pair (positional or `--original`/`--forwarded`).
**Writes:** per-request diff sections with IDENTICAL/REPLACED/STRIPPED/INJECTED tags to stdout.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.diff_engine`.

---

### span_inline_probe.py (68 LOC)

**Purpose:** CLI entry point for the Form A vs Form B inline-render data model probe — validates that
a full ordered span list per log (Form B) is the minimal data model letting the read side render
strip/inject inline without content duplication, by showing Form A's (offset+text anchor) empirical
failure on real diff data across three probed blocks from a fixed recorded session.
**Reads:** a fixed recorded session's dual-log files (hardcoded session reference).
**Writes:** `span_inline_probe_reports/<YYYYMMDD>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `src.proxy.diff_engine` (`_diff_text`, loaded via `importlib`, standalone);
`span_inline_probe_reconstruct.py`, `span_inline_probe_blocks.py`, `span_inline_probe_report.py`.

### span_inline_probe_reconstruct.py (88 LOC)

**Purpose:** JSONL loading, per-model-family forwarded-delta chain reconstruction, and
original/forwarded request matching (by request_id, falling back to family-order position).
**Reads:** JSONL file objects passed in by the caller.
**Writes:** nothing — pure data transforms.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_blocks.py (115 LOC)

**Purpose:** Locates the three representative probe blocks (B1 sys full-replace, B2 sys
strip-to-dot, B3 message word-level-mixed-with-cache_control-diff) in a matched request list.
**Reads:** matched `(orig_entry, fwd_entry, fwd_state)` tuples; takes the diff function as a
parameter rather than importing `diff_engine` itself.
**Writes:** nothing — returns block-description dicts.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

### span_inline_probe_report.py (384 LOC)

**Purpose:** Builds the Markdown report — per-block span sequence, inline render mock, Form A
position-offset empirical analysis, Form B per-log views + storage-cost table, plus the fixed
design-tension and recommendation sections.
**Reads:** block-description dicts from `span_inline_probe_blocks.py`.
**Writes:** returns the report as a list of lines.
**Called by:** `span_inline_probe.py`.
**Calls out:** none.

---

### main_log_elimination_probe.py (77 LOC)

**Purpose:** CLI entry point for the feasibility probe on eliminating the single main proxy log in
favor of the dual-log quartet — wires path resolution, both questions, and report writing together.
**Reads:** a dual-log quartet plus the corresponding main proxy log for one session (session suffix
via positional arg, default hardcoded).
**Writes:** `main_log_elimination_probe_reports/<date>.md`.
**Called by:** none — manual, one-off feasibility probe.
**Calls out:** `main_log_elimination_io.py`, `main_log_elimination_questions.py`,
`main_log_elimination_report.py`.

### main_log_elimination_io.py (66 LOC)

**Purpose:** Project-root/log-path resolution, required-file existence check, and JSONL loaders
(main log, tool_errors, generic).
**Reads:** `MONITOR_CC_ROOT` env var or `__file__`-relative fallback; log files on disk.
**Writes:** nothing — pure I/O helpers; exits 1 via `_check_paths` if a required log is missing.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** none.

### main_log_elimination_reconstruct.py (156 LOC)

**Purpose:** Delta-chain reconstruction (`_reconstruct_forwarded`), cache_control-aware element
normalization/comparison, and the top-level raw_payload field classification tables/maps
(delta-covered / must-add / metadata-pane-only).
**Reads:** nothing — pure data transforms over passed-in entries.
**Writes:** nothing.
**Called by:** `main_log_elimination_questions.py`, `main_log_elimination_report.py`.
**Calls out:** none — inlines the cache-control-strip and shape-normalization helpers from
`src/proxy/logging.py` verbatim.

### main_log_elimination_questions.py (153 LOC)

**Purpose:** Answers Question A (forwarded-reconstruction vs. main-log `raw_payload` content match,
per-request) and Question B (is_error tool_result extraction from `_original`, dedup by
tool_use_id, compared against `tool_errors.jsonl`).
**Reads:** main-log entries, forwarded-delta entries, `_original` entries, tool_errors records.
**Writes:** nothing — returns result dicts.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py`.

### main_log_elimination_report.py (218 LOC)

**Purpose:** Builds the Markdown report — header, Question A content-match/BP-divergence/
field-classification sections, Question B section, and the migration verdict.
**Reads:** the Question A/B result dicts.
**Writes:** the report file; returns its path.
**Called by:** `main_log_elimination_probe.py`.
**Calls out:** `main_log_elimination_reconstruct.py` (`_DELTA_COVERED`).

---

### green_overlay_probe.py (222 LOC)

**Purpose:** CLI entry point that reproduces a green-overlay false-injection bug in the word-level
diff path (JSON-escaped `\n` sequences merged into single "words" by `.split()`, causing a shared
prefix to be mis-tagged as both stripped and injected) and validates a char-level `SequenceMatcher`
fix against real log data plus synthetic regression cases.
**Reads:** one recorded session's dual-log files (hardcoded session reference).
**Writes:** `green_overlay_probe_reports/green_overlay_probe.md`.
**Called by:** none — manual, one-off bug-repro probe.
**Calls out:** `green_overlay_probe_diff.py`, `green_overlay_probe_cases.py`.

### green_overlay_probe_diff.py (210 LOC)

**Purpose:** The three diff variants under comparison (`diff_text_word` current-production,
`diff_text_char` candidate fix, `diff_text_char_gated` attribution-gated fix), the marker-based
attribution copies (`_STRIP_RULES_MARKERS`/`_MSG_CODE_TO_FN`), fidelity checking, and span
formatting/comparison helpers.
**Reads:** nothing — pure text-diff functions.
**Writes:** nothing.
**Called by:** `green_overlay_probe.py`, `green_overlay_probe_cases.py` (`_fn_for_inject`).
**Calls out:** none — self-contained, no `src/` imports at module level.

### green_overlay_probe_cases.py (135 LOC)

**Purpose:** Live `_injected.jsonl` gating-soundness scan, and the primary bug case +
3 real-log regression cases + 1 synthetic whitespace-collapse case used by the report.
**Reads:** one recorded session's dual-log files (hardcoded session reference); all
`*_injected.jsonl` files under `src/logs/dual_log` for the soundness scan.
**Writes:** nothing — returns case tuples / dicts.
**Called by:** `green_overlay_probe.py`.
**Calls out:** `green_overlay_probe_diff.py`.

---

### groundtruth_message_spans_probe.py (115 LOC)

**Purpose:** CLI entry point validating `build_message_spans(orig_text, fwd_text, stripped_chunks)`,
the ground-truth span-construction algorithm that replaces blind diffing for messages — builds spans
directly from the chunks `apply_modification_rules` recorded as stripped, rather than diffing
original against forwarded text.
**Reads:** recorded `_original.jsonl` dual-log payloads (re-runs `apply_modification_rules` on them
to regenerate `stripped_msg_removed`).
**Writes:** `groundtruth_message_spans_probe_reports/groundtruth_spans_<timestamp>.md`.
**Called by:** none — manual, one-off design-validation probe.
**Calls out:** `groundtruth_spans_cases.py`, `groundtruth_spans_report.py`.

### groundtruth_spans_algorithm.py (191 LOC)

**Purpose:** The GT algorithm under test (`build_message_spans`, split into
`_split_stripped_chunks`/`_walk_forward_spans`), the current-production `diff_text_word` baseline,
minimal src/ mirror helpers (`_strip_cache_control`/`_normalize_msg_shape`/`_get_text`/
`_get_inner_text`), and the two fidelity checks.
**Reads:** nothing — pure text/span functions.
**Writes:** nothing.
**Called by:** `groundtruth_spans_cases.py`, `groundtruth_spans_report.py`.
**Calls out:** none.

### groundtruth_spans_cases.py (179 LOC)

**Purpose:** `apply_modification_rules` re-run wrapper and the 4 real-log case builders (bug case,
text-block-replace case, bg-exit-replace case, multi-chunk/large-SR case).
**Reads:** recorded `_original.jsonl`/`_forwarded.jsonl` dual-log payloads (two hardcoded stems).
**Writes:** nothing — returns case dicts.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `src.proxy.rules` (`apply_modification_rules`, lazy import inside `run_rules`);
`groundtruth_spans_algorithm.py`.

### groundtruth_spans_report.py (253 LOC)

**Purpose:** Runs one case through both algorithms (`run_case`) and builds every report section
(summary table, per-case GT/diff/bug/replace detail, fidelity summary, zero-phantom summary,
recording-gaps summary, conclusion).
**Reads:** case dicts from `groundtruth_spans_cases.py`.
**Writes:** nothing — appends to the caller's `emit`-collected line list.
**Called by:** `groundtruth_message_spans_probe.py`.
**Calls out:** `groundtruth_spans_algorithm.py`.

---

### composition_probe.py (233 LOC)

**Purpose:** CLI entry point proving multi-pass span composition over the original content (C0) —
models each proxy pass as an `Op(offset, removed, injected)` and composes all passes into one span
list, validating two reconstruction invariants (`equal+stripped == C0`, `equal+injected == Cfwd`)
across every modified block in the corpus, including double-inject and multi-pass-per-block cases.
Also re-imports `_strip_cache_control`/`_block_text`/`compose_block`/`check_invariants`/
`run_passes_and_collect_ops` from its sibling modules so `import composition_probe as _probe`
(used by `test_composition_invariant.py`) keeps working unchanged.
**Reads:** the full dual-log corpus (`*_original.jsonl` and siblings) present at run time.
**Writes:** `01_reports/composition_probe_<date>.md`.
**Called by:** `test_composition_invariant.py` (imports it as a module for its own synthetic-fixture
check); otherwise run manually.
**Calls out:** `src.proxy.strip_bg_completed` (`_WAKEUP_TEXT`); `composition_probe_ops.py`,
`composition_probe_passes.py`, `composition_probe_corpus.py`.

### composition_probe_ops.py (164 LOC)

**Purpose:** The span algebra — cache_control strip, inner-text extraction, prefix/suffix op
extraction from a (before, after) pair, `apply_edit_to_spans` (the core span-list edit primitive),
block-pair diffing, `compose_block`, and `check_invariants`.
**Reads:** nothing — pure data transforms.
**Writes:** nothing.
**Called by:** `composition_probe.py`, `composition_probe_passes.py`, `composition_probe_corpus.py`,
`test_composition_invariant.py` (via `composition_probe`'s re-export).
**Calls out:** none.

### composition_probe_passes.py (69 LOC)

**Purpose:** Runs the 8 production proxy passes plus `_dedup_wakeup_blocks` in sequence, collecting
per-block ops from each pass's real op-recording return value (all passes now real, no stand-in).
**Reads:** message list passed in by the caller.
**Writes:** nothing — returns `(final_messages, ops_by_msg_blk)`.
**Called by:** `composition_probe.py`, `composition_probe_corpus.py`,
`test_composition_invariant.py` (via `composition_probe`'s re-export).
**Calls out:** `src.proxy.rules` (lazy import inside `run_passes_and_collect_ops`);
`composition_probe_ops.py`.

### composition_probe_corpus.py (139 LOC)

**Purpose:** Scans the 5 fixed corpus stems, running every modified block through
`run_passes_and_collect_ops` + `compose_block` + `check_invariants` and aggregating pass-level
pass/fail stats and failing cases; also the msg[100] TN+BG double-inject money-shot case lookup.
**Reads:** the 5 fixed `LOG_STEMS`' `_original.jsonl` files under `src/logs/dual_log`.
**Writes:** nothing — returns stats dicts.
**Called by:** `composition_probe.py`.
**Calls out:** `composition_probe_ops.py`, `composition_probe_passes.py`.

---

### attribution_coverage.py (53 LOC)

**Purpose:** CLI entry point for the read-only coverage analysis — can every entry in the
`_stripped`/`_injected` dual-logs be attributed to a responsible proxy function?
**Reads:** all `*_stripped.jsonl`/`*_injected.jsonl` pairs under src/logs/dual_log.
**Writes:** `attribution_coverage_reports/<YYYYMMDD>.md`.
**Called by:** none — manual CLI.
**Calls out:** `src.proxy.strip_vocab` (`attribute_chunk`, loaded via
`importlib.util.spec_from_file_location`); `attribution_coverage_analyse.py`,
`attribution_coverage_report.py`.

### attribution_coverage_classify.py (101 LOC)

**Purpose:** Owns the only `_FIELD_STRIP_FN`/`_FIELD_INJECT_FN` maps left for top-level-field
attribution (`model`/`max_tokens`/`thinking`/`output_config`/`context_management`) — this is the
live attribution mechanism for those fields; `src/proxy/strip_inject_delta.py` used to hold an
unread, already-drifted copy of the same two maps, removed as dead code (see that module's own
DOCS.md entry). Also the span-format detection, strip/inject message classification, and coverage
percentage calculation.
**Reads:** nothing — pure classification functions.
**Writes:** nothing.
**Called by:** `attribution_coverage_analyse.py`, `attribution_coverage_report.py`,
`attribution_coverage.py` (`_SYS_INJECT_FN` via `attribution_coverage_analyse.py`).
**Calls out:** none.

### attribution_coverage_analyse.py (147 LOC)

**Purpose:** Pair discovery, JSONL loading, and the per-section (sys/tools/messages/fields)
strip+inject analysers that build the aggregated coverage stats.
**Reads:** paired `*_stripped.jsonl`/`*_injected.jsonl` files.
**Writes:** nothing — returns `(strip_stats, inject_stats, residuals, false_positives)`.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`.

### attribution_coverage_report.py (245 LOC)

**Purpose:** Builds the Markdown report — header, strip/inject attribution tables, residual
analysis, false-positive (json_reserialization bug) evidence, and gap-coverage status.
**Reads:** the aggregated stats from `attribution_coverage_analyse.py`.
**Writes:** returns the report as a string.
**Called by:** `attribution_coverage.py`.
**Calls out:** `attribution_coverage_classify.py`; `src.proxy.strip_vocab` (`RULES`, loaded via its
own `importlib.util.spec_from_file_location`, separate from `attribution_coverage.py`'s load).

---

### A_render_refactor_proof.py (125 LOC)

**Purpose:** CLI harness (capture/verify modes) for the byte-identical differential test of the
proxy_display render cluster — `--mode capture` runs the fixture cases through `format_proxy_block`
and writes `(ansi_string, total_lines)` per case to a baseline JSON; `--mode verify` re-runs the
same cases and asserts byte-identity against that baseline.
**Reads:** fixture entries from `A_render_refactor_proof_cases.py`; `--mode verify` also reads a
baseline JSON under `A_render_refactor_proof_reports/`.
**Writes:** `A_render_refactor_proof_reports/<name>.json` (capture mode).
**Called by:** none — manual, run as capture/implement/verify around a render-cluster refactor
(also reused by `dev/proxy_tool_stripping/` for its own regression checks — see that DOCS.md).
**Calls out:** `src.proxy_display.format` (`format_proxy_block`); `A_render_refactor_proof_cases.py`.

### A_render_refactor_proof_fixtures.py (35 LOC)

**Purpose:** The 3 low-level fixture builders (`_mk_entry`/`_mk_msg`/`_mk_blk`) shared by every case.
**Reads:** nothing.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof_cases.py`.
**Calls out:** none.

### A_render_refactor_proof_cases.py (246 LOC)

**Purpose:** The 14 fixed test cases (`_build_cases` + one `_case_*` builder per case) covering
every render branch (new/stripped/tail-fallback messages, dual-span new/legacy format, tools
first-request/changed, system blocks, standalone haiku, copy-feedback, hover/scroll, label
collision, and the expand-all fixpoint).
**Reads:** nothing — synthetic in-script fixture data.
**Writes:** nothing.
**Called by:** `A_render_refactor_proof.py`.
**Calls out:** `A_render_refactor_proof_fixtures.py`.

---

### proxy_176_agent_types_tests.py (155 LOC)

**Purpose:** Unit tests for the CC 2.1.176 agent-types system-reminder strip — a standalone
`<system-reminder>`-wrapped "Available agent types" block in a user message must strip via
`_apply_cumulative_sr_strips` and attribute to code `AT` in `_MSG_CODE_TO_FN`.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI; its own usage comment names a stale top-level `dev/` path that
predates this file's move into `dev/proxy_dual_log/`.
**Calls out:** `proxy.message_passes`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops` — imported after inserting `src/` directly onto `sys.path` (not a
`from src.` line).

---

### proxy_176_bg_launch_ack_tests.py (74 LOC)

**Purpose:** CLI runner for the CC 2.1.176 background-launch-ack strip
(`_apply_bg_launch_ack_strip`) unit tests — imports and sequences every `test_*` case.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py` — both
import `proxy.message_passes_simple`/`proxy.strip_inject_delta`/`proxy.diff_engine`/`proxy.logging`/
`proxy.rule_ops`/`proxy.strip_vocab`/`proxy.strip_bg_launch_ack` after this file inserts `src/`
directly onto `sys.path`.

### proxy_176_bg_launch_ack_fixtures.py (123 LOC)

**Purpose:** Wording 1/2/3 launch-ack fixture texts, their expected 3-line hold-message
replacements, and the false-positive (marker-quoted-mid-content) fixtures for each wording.
**Reads:** nothing — pure constants.
**Writes:** nothing.
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_report.py (10 LOC)

**Purpose:** The shared `check()` PASS/FAIL-line printer and its ANSI color constants.
**Reads:** nothing.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_cases.py`, `proxy_176_bg_launch_ack_cases_w3.py`.
**Calls out:** none.

### proxy_176_bg_launch_ack_cases.py (256 LOC)

**Purpose:** Items 4a–4p — tool_result/text-block/string-content/list-content replacement tests,
non-matching and completion-notification negative tests, BL-code attribution, wording-1
false-positive preservation tests, and the wording-2 tests (replacement, FP, attribution, same
message-line-as-wording-1 check).
**Reads:** nothing — synthetic in-script fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops`, `proxy.strip_vocab`.

### proxy_176_bg_launch_ack_cases_w3.py (193 LOC)

**Purpose:** Items 4q–4x — wording-3 (auto-backgrounded-on-timeout) tests (replacement, FP,
attribution, message-differs-and-names-timeout, main-vs-worker wording, ops-path visibility), the
full-replacement-is-one-contiguous-span-shape pin, and the wording-1 main-vs-worker wording test.
**Reads:** nothing — synthetic in-script fixture text via `proxy_176_bg_launch_ack_fixtures.py`.
**Writes:** PASS/FAIL lines to stdout (via `check`).
**Called by:** `proxy_176_bg_launch_ack_tests.py`.
**Calls out:** `proxy.message_passes_simple`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging`, `proxy.rule_ops`, `proxy.strip_vocab`, `proxy.strip_bg_launch_ack`.

---

### proxy_176_strip_tests.py (181 LOC)

**Purpose:** Unit tests for two CC 2.1.176 proxy drift fixes: `Workflow` added to `TOOL_BLOCKLIST`
(stripped by `_strip_unused_tools`), and `_apply_role_system_strip` stripping `role='system'`
messages unconditionally.
**Reads:** nothing — synthetic in-script fixture text.
**Writes:** PASS/FAIL lines to stdout.
**Called by:** none — manual CLI.
**Calls out:** `proxy.tools`, `proxy.message_passes`, `proxy.strip_inject_delta`, `proxy.diff_engine`,
`proxy.logging` — imported after inserting `src/` directly onto `sys.path`.

---

### test_composition_invariant.py (131 LOC)

**Purpose:** CI-style regression test asserting the two composition invariants (`equal+stripped ==
C0`, `equal+injected == Cfwd`) hold for every modified block across a synthetic 9-entry fixture
corpus covering all 8 proxy passes plus the wakeup-dedup pass.
**Reads:** `fixtures/invariant_corpus.jsonl`.
**Writes:** PASS/FAIL summary to stdout; exits 1 on any invariant violation.
**Called by:** none — manual CLI, exit code suitable for CI use.
**Calls out:** `composition_probe` (same-directory module, imported directly by adding this
directory and the project root to `sys.path` — `composition_probe.py` re-exports
`_strip_cache_control`/`run_passes_and_collect_ops`/`_block_text`/`compose_block`/
`check_invariants` from its own sibling modules for this import to keep working unchanged).

---

## Gotchas
- The dual-log corpus under src/logs/dual_log is live and growing from concurrent real sessions — a
  re-run of any corpus-scanning script here shifts absolute counts without changing the underlying
  correctness finding.
- Session-specific scripts (`span_inline_probe.py`, `green_overlay_probe.py`,
  `main_log_elimination_probe.py`) hardcode one recorded session's stem rather than taking it as an
  argument — they are one-off design-validation probes, not general-purpose regression tools.
- `tt_delta_skip_replay.py`'s inject check is an implication, not an equality — a green message span
  must light `inject`, but a system-section-only injection can legitimately light `inject` with an
  empty injected `messages_delta`.
- Every split-off sibling module (e.g. `composition_probe_ops.py`, `green_overlay_probe_diff.py`,
  `span_inline_probe_reconstruct.py`) duplicates small helpers (`_strip_cache_control`,
  `_infer_family`, delta-chain reconstruction) rather than importing them from another probe's
  sibling — this mirrors the pre-existing cross-script duplication convention in this directory and
  was deliberately not touched by the cohesion split (see process-docs/proxy_dual_log/ for the
  2026-09-15 entry).
```

