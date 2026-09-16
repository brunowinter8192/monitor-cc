# process-docs/bg_wakeup_id_line/2026-09-16_comment_salvage.md

Session: dev/bg_wakeup_id_line/ module-standards conformance (comment/docstring removal + DOCS.md rewrite).
Date: 2026-09-16.

## Purpose of this file

Every comment and docstring deleted from `dev/bg_wakeup_id_line/*.py` during this milestone,
copied verbatim before deletion, plus the full pre-rewrite content of
`dev/bg_wakeup_id_line/DOCS.md`. Nothing judged and dropped — see the milestone rules in the
calling agent's prompt (module-standards conformance: relocate then delete, decide nothing).

File count (3) and comment/docstring totals (63 comments, 3 docstrings) matched the prompt's
stated measured state exactly — no discrepancy this session.

Grep for `__doc__`/`argparse`/`description=`/`epilog=`/`.help(` across
`dev/bg_wakeup_id_line/*.py` before deletion: zero matches. The 3 module-level docstrings are
plain narrative, never read at runtime. All 3 deleted outright, no constant-rewiring needed.

## Execution-safety note for this session

`p2_bg_escape_probe.py`'s Test 6 (`test_real_tmux_roundtrip`) really creates a throwaway tmux
session (`__bg_escape_probe_<epoch>`), sends it a real `Escape` keystroke via `tmux send-keys`,
reads it back via `tmux capture-pane`, then kills the session — against the real tmux server on
this machine, not a sandboxed one. Main confirmed this is NOT the same class of risk as the
OSC-2 tty-retitle case from an earlier session in this cycle (that one retitled a real,
currently-visible terminal tab; this one's target pane is never attached to or displayed by
anything) and explicitly said to run it. **Caveat from main, recorded here as instructed:** the
menubar's real monitor enumerates tmux sessions live, so this throwaway session can flicker
through the user's workers pane for the brief moment it exists between `new-session` and
`kill-session`. This is cosmetic and was accepted as a known, acceptable side effect of running
this test — not a regression, not something to fix, not something future readers should try to
"solve" by sandboxing the test further.

`p1_scan_launch_ack_wordings.py` writes to a FIXED-name tracked report
(`md/launch_ack_wordings_20260729.md` — no timestamp in the filename, same shape as the
`model_selector` area's fixed-name reports earlier this cycle). It was snapshotted before any
run and restored from that snapshot after verification, regardless of diff outcome, so no
tracked artifact carries this session's run-to-run noise.

Comment/docstring counts confirmed via AST + tokenize before deletion: 63 comments, 3
docstrings, matching the task's stated measured state exactly.

## Salvage from dev/bg_wakeup_id_line/DOCS.md

Full content of dev/bg_wakeup_id_line/DOCS.md as it stood before this rewrite (70 lines),
preserved verbatim since the whole file is being replaced with the mandated leaner format
(Role capped at 50 words, Purpose capped at 25 words per module, no Gotchas section in the
new format, Public Interface / Flow / State sections added).

```markdown
# dev/bg_wakeup_id_line/

## Role

Measurement and regression scripts for the CC background-launch-ack family: the raw ack text CC
sends (`p1_`), the tmux-Escape mechanism the proxy fires on that ack (`p2_`,
`src/proxy/bg_escape.py`), and the interrupt marker CC records in the conversation when that
Escape lands mid-tool-call (`p3_`, `src/proxy/strip_interrupt_marker.py`). Touch this area when
changing `bg_escape.py`, `strip_bg_launch_ack.py`, or `strip_interrupt_marker.py`. `md/` holds
every script's report.

## Modules

### p1_scan_launch_ack_wordings.py (327 LOC)

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
```

## Salvage from dev/proxy/p1_scan_launch_ack_wordings.py

DOCSTRING L1-12:
```

D1 — inventory distinct CC background-launch-ack wordings in the real recorded corpus.

Measurement only: scans src/logs/dual_log/*_original.jsonl for messages that look like a
CC background-launch acknowledgement, dedups cumulative dual-log duplication, buckets by
normalized wording, and evaluates the 3 real recognition mechanisms from
src/proxy/strip_bg_launch_ack.py against each wording. Writes report to
dev/bg_wakeup_id_line/md/.

Usage (from project root or worktree root):
    ./venv/bin/python dev/bg_wakeup_id_line/p1_scan_launch_ack_wordings.py

```

COMMENT L32:
```
# Recorded dual-log corpus lives in the main checkout (untracked data, not duplicated into
```

COMMENT L33:
```
# worktrees) — code under test is imported from WORKTREE_ROOT above.
```

COMMENT L38:
```
# Corpus: completed proxy sessions from today (2026-07-29), excluding the currently-live
```

COMMENT L39:
```
# session and this worker's own worktree activity (see report EXCLUDED_FILES section).
```

COMMENT L54:
```
# Live-observed text from the milestone prompt (2026-07-29), verbatim, for cross-check
```

COMMENT L83:
```
# Extract (shape, text) candidate blocks from one message's content — mirrors the 4-shape
```

COMMENT L84:
```
# walk in _strip_bg_launch_ack._strip_bg_launch_ack (str / text block / tool_result str /
```

COMMENT L85:
```
# tool_result list[text]), so shape labels match the production replacement walker exactly.
```

COMMENT L107:
```
# Structural candidate filter: block-INITIAL "Command" + both family markers. Positional
```

COMMENT L108:
```
# (lstripped text must START with "Command", not contain it anywhere) — this is what filters
```

COMMENT L109:
```
# out source-code / dev-report / Read-tool-dump mentions of the ack text (those never start
```

COMMENT L110:
```
# the block at position 0 with "Command": Read dumps start with line numbers, docstrings/
```

COMMENT L111:
```
# reports start with other prose). "with ID:" + "Output is being written to:" are shared by
```

COMMENT L112:
```
# both known wordings and any structurally-similar unknown one, without hardcoding either
```

COMMENT L113:
```
# exact wording.
```

COMMENT L125:
```
# Mask volatile id/path tokens so occurrences of the same wording bucket together regardless
```

COMMENT L126:
```
# of the concrete task id / output path
```

COMMENT L133:
```
# Scan one corpus file: dedup via prev-message-count delta (each request's dual-log line is a
```

COMMENT L134:
```
# cumulative snapshot; a message once introduced reappears verbatim in every later request of
```

COMMENT L135:
```
# the same session — only the delta [prev_count:] is genuinely new per request).
```

COMMENT L162:
```
# Raw (non-deduped) occurrence count across the whole file, for the dedup-importance callout
```

COMMENT L174:
```
# Evaluate the 3 real recognition mechanisms against one example text
```

COMMENT L194:
```
# Build the markdown report
```

## Salvage from dev/proxy/p2_bg_escape_probe.py

DOCSTRING L1-11:
```

P2 — verifies the launch-ack-triggered tmux-Escape mechanism (src/proxy/bg_escape.py).

Covers: dedup-by-task-id across repeated acks (real 142/169 shape), two-distinct-ids → two
sends, both CC ack wordings, main-context never fires, tmux session name derivation (incl.
hyphenated worker names), a real tmux round trip, and failure isolation (dead session, missing
tmux binary — both at the unit level and through the real ProxyAddon.request() path).

Run from project root or worktree root:
    ./venv/bin/python dev/bg_wakeup_id_line/p2_bg_escape_probe.py

```

COMMENT L59:
```
# Test 1 — dedup across repeated acks: the SAME ack (same task id) fed across 169 simulated
```

COMMENT L60:
```
# requests (142 carrying the ack, real 142/169 shape) fires the Escape exactly once.
```

COMMENT L74:
```
# Test 2 — two distinct task ids → two Escapes.
```

COMMENT L87:
```
# Test 3 — both CC wordings trigger.
```

COMMENT L100:
```
# Test 4 — main context never triggers.
```

COMMENT L112:
```
# Test 5 — tmux session name derivation from PROXY_LOG_ID + PROXY_PROJECT_PATH, including a
```

COMMENT L113:
```
# hyphenated worker name.
```

COMMENT L134:
```
# Test 5b — a fire writes one JSONL trace line to bg_escape_events.jsonl (MONITOR_CC_ROOT-scoped),
```

COMMENT L135:
```
# carrying task id, derived tmux session, and the send result — the trace the rolled-back menubar
```

COMMENT L136:
```
# mechanism had and this one lacked until now.
```

COMMENT L155:
```
# Same request-shape, main context this time — this IS a matter-of skip case, so it must ALSO
```

COMMENT L156:
```
# log (not silently no-op), reason == 'main_context'.
```

COMMENT L166:
```
# A request with no bg-launch-ack chunk at all must never touch the log sink.
```

COMMENT L174:
```
# Test 6 — real tmux round trip: spawn a throwaway session running a raw-mode 1-byte reader,
```

COMMENT L175:
```
# call the PRODUCTION _send_escape_key against it, confirm the Escape byte (0x1b) arrived via
```

COMMENT L176:
```
# capture-pane.
```

COMMENT L203:
```
# the PRODUCTION function, not a re-implementation
```

COMMENT L215:
```
# Test 7 — failure isolation: dead/missing tmux session and a missing tmux binary must not raise,
```

COMMENT L216:
```
# and the real ProxyAddon.request() path must still complete (forward the request) when the
```

COMMENT L217:
```
# tmux binary itself is absent.
```

COMMENT L235:
```
# Entry-point level: real ProxyAddon.request() with a payload carrying a genuine ack, tmux
```

COMMENT L236:
```
# binary simulated absent — the request must still forward (flow.request.content gets set).
```

COMMENT L272:
```
# Minimal real-shaped payload whose user turn carries a genuine bg-launch ack tool_result block —
```

COMMENT L273:
```
# exercises the real apply_modification_rules -> _trigger_bg_escape wiring end to end.
```

## Salvage from dev/proxy/p3_strip_interrupt_marker_probe.py

DOCSTRING L1-20:
```

P3 — verifies src/proxy/strip_interrupt_marker.py and its full wiring (message_passes.py,
rules.py, strip_vocab.py, strip_inject_delta.py).

The proxy sends a tmux Escape into a worker's pane when one of its calls is backgrounded
(src/proxy/bg_escape.py). Claude Code records that interruption in the conversation as a block
whose (whitespace-stripped) text is EXACTLY one of two real wordings — "[Request interrupted by
user]" or "[Request interrupted by user for tool use]", both always trailing-newline-terminated
in the corpus — no user interrupted anything, but a worker reading the marker halts and waits for
an instruction nobody intended to give. This probe proves the marker never reaches the model.

Covers: the measured real payload shape (3 blocks: tool_result / marker(+'\n') / injected
wake-up, neighbors byte-identical after strip), all 4 content shapes for both wordings, the
false-positive class (marker embedded inside longer text must survive untouched, incl. a real
corpus-derived 180-char quote), and attribution resolving to a named function through the real
apply_modification_rules -> _build_stripped_injected_deltas path.

Run from project root or worktree root:
    ./venv/bin/python dev/bg_wakeup_id_line/p3_strip_interrupt_marker_probe.py

```

COMMENT L36:
```
# Real corpus wordings (src/logs/dual_log/*_original.jsonl, 2026-07-31 re-measurement) — both
```

COMMENT L37:
```
# always trailing-newline-terminated; 10x base wording, 1x "for tool use" wording, 11/11 total.
```

COMMENT L55:
```
# Test 1 — real measured shape: tool_result / marker / injected wake-up, 3 blocks. Marker block
```

COMMENT L56:
```
# emptied to '.'; the two neighbor blocks are byte-identical afterwards (dict equality).
```

COMMENT L71:
```
# Test 2 — all 4 content shapes strip the exact-match marker.
```

COMMENT L92:
```
# Test 2b — the 2nd real wording ("for tool use", 1/11 measured occurrences) strips too — this
```

COMMENT L93:
```
# wording was never covered before the 2026-07-31 fix and is why the false negative shipped.
```

COMMENT L103:
```
# Test 3 — false-positive class: marker embedded inside longer text (top-level text block and
```

COMMENT L104:
```
# tool_result data) must be left byte-identical, no removal recorded. Includes a real
```

COMMENT L105:
```
# corpus-derived 180-char user message that quotes the bracketed marker mid-sentence
```

COMMENT L106:
```
# (src/logs/dual_log/api_requests_opus_monitor_cc_1785431184_original.jsonl, msg 11).
```

COMMENT L129:
```
# Test 4a — message-pass level: gate fires only for role='user', mod name is stripped_interrupt_marker.
```

COMMENT L149:
```
# Test 4b — vocabulary + attribution: attribute_chunk resolves to 'IM', and IM maps to a named
```

COMMENT L150:
```
# function (not 'unknown') in strip_inject_delta's _MSG_CODE_TO_FN.
```

COMMENT L160:
```
# Test 5 — full pipeline: real apply_modification_rules -> real _build_stripped_injected_deltas,
```

COMMENT L161:
```
# fn_map for the stripped block resolves to '_apply_interrupt_marker_strip', never 'unknown'.
```

