# dev/dual_log_cli/

## Role

Regression suite plus one measurement probe for `src/dual_log_cli/`. The suite proves each
`msgs`/`reqs`/`search`/`sessions`/`expand` rendering rule byte-for-byte against hand-built or
temp-file fixtures, driving the real `src.dual_log_cli.*` functions directly rather than
re-implementing their logic. The probe measures a real corpus question that informed a design
decision (whether the last `_original` request's own `system`/`tools` lists are a reliable source
for an earlier request's pre-strip size) and writes a report rather than asserting pass/fail.
Touch this directory when changing any `src/dual_log_cli/` rendering, filtering, or boundary rule;
each test file targets one feature area and is runnable standalone. Do NOT add fixtures that
require a live `MONITOR_CC_ROOT` or real `~/.claude/projects/` tree — every test file here builds
its own synthetic or temp-file fixtures precisely so it needs neither.

## Flow

A test script builds synthetic dicts shaped like `render_msgs`/`render_reqs` expect, or writes a
temp `_forwarded.jsonl`-shaped file and runs the real `request_boundaries` over it, then calls the
`src.dual_log_cli` function under test and compares the string/dict result against an expected
value via a local `check()` helper; a failure list drives the exit code. The probe instead globs
the real dual-log directory for every `*_original.jsonl`/`*_stripped.jsonl` stem pair, runs four
corpus-wide measurements, and writes a dated Markdown report to `md/`.

## Modules

### probe_sys_tool_original_chars.py (296 LOC)

**Purpose:** Measures, across every session on disk, whether the last `_original` request's own
`system`/`tools` lists reliably recover an earlier request's pre-strip size, and whether
system/tools writes lag the way a trailing-msg token strip does — backing the design behind
`overlay.build_sys_tool_overlay` and `render._req_delta_lines`.
**Reads:** every `*_original.jsonl`/`*_stripped.jsonl` pair under the resolved dual-log directory
(`MONITOR_CC_ROOT`, else the repo's own `src/logs/dual_log`, else the main checkout's copy when run
from a worktree).
**Writes:** `dev/dual_log_cli/md/probe_sys_tool_original_chars_<date>.md`; "no sessions found" and
exit 0 if the directory has no sessions.
**Called by:** none — run manually.
**Calls out:** none — deliberately self-contained; its `_infer_family`/`_delta_hash` are simplified
re-implementations, not `src.dual_log_cli.reader.infer_family` / `src.proxy.logging._delta_hash`.

---

### tests/test_local_time.py (148 LOC)

**Purpose:** Proves the UTC-to-local conversion (`reader.local_datetime`) matches an independently
computed `datetime.astimezone()`, that every renderer built on it (`render_format._clock`/
`fmt_timestamp`/`_window_date`, `discovery.filter_sessions`, `usage._epoch_from_iso`) agrees with
it, and that a day-boundary-crossing timestamp is filed under its LOCAL calendar day — the crossing
case is built dynamically from the running machine's own UTC offset, never hardcoded.
**Reads:** nothing external — literal ISO strings plus the running machine's own timezone.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_format`, `.usage`.

---

### tests/test_msgs_blocks.py (215 LOC)

**Purpose:** Proves `msgs`' block sub-lines (one indented line per block under a multi-block msg,
untouched single-block format, `tool_use[Name]`/`tool_result!err` labels sourced through the real
`timeline_turns.build_turns` pipeline, unchanged REQ separators).
**Reads:** nothing external — hand-built `render_msgs` input dicts, one case via the real
`build_turns` pipeline.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_turns`.

---

### tests/test_msgs_overlay.py (189 LOC)

**Purpose:** Proves `msgs`' strip/inject delta tail (`−N +M → Wc`, digit-grouped, real minus sign)
computed from `overlay.build_overlay`'s `{(msg_idx, blk_idx): {...}}` shape: untouched lines stay
byte-identical, a multi-block parent sums its blocks' figures, `by REQ n` appears only when the
touched request differs from the group's own and is omitted when a msg's blocks disagree on it.
**Reads:** nothing external — hand-built `render_msgs` input dicts and overlay fixtures.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`.

---

### tests/test_msgs_req_range.py (171 LOC)

**Purpose:** Proves `msgs --req F [T]` (`timeline_markers.request_msg_range`/`resolve_req_range`)
resolves a single REQ or a range to the correct msg-index span, runs the last REQ to the session's
last msg index, and raises `UnknownRequestNumberError`/`AmbiguousRequestNumberError` for an unknown
or duplicate REQ number (the duplicate case reproduced via a non-adding re-fire, without a restart).
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_delta.py (237 LOC)

**Purpose:** Proves `msgs`' sys/tool delta lines (`timeline._sys_lines`/`_tool_lines`/
`request_boundaries`/`request_markers`, rendered by `render._req_delta_lines`): the family's first
request lists everything untagged, a later request tags `changed`/`new` and drops the excluded
billing header (system index 0) and any byte-identical carried entry, and a re-fire group shows
only the owning boundary's lines.
**Reads:** a temp `_forwarded.jsonl`-shaped file, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.timeline_boundaries`, `.timeline_markers`.

---

### tests/test_msgs_sys_tool_overlay.py (253 LOC)

**Purpose:** Proves the sys/tool strip-inject delta tail (`overlay.build_sys_tool_overlay`,
rendered by `render._req_delta_lines`/`_delta_line`): a transformed system/tool line shows the
ORIGINAL size (looked up in `data["payload"]`) with the tail's wire figure being the MEASURED wire
chars, never derived from the raw stripped-text length; system index 0 stays untouched; a
whole-stripped tool (absent from the wire delta entirely) is synthesized as its own line scoped to
the owning flow_id; an unresolvable whole-stripped name is skipped, not guessed.
**Reads:** nothing external — hand-built `render_msgs` input dicts with a `data["payload"]` added.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_msgs_usage.py (245 LOC)

**Purpose:** Proves the `CR c  CC c` prompt-cache separator renders when a marker's flow_id
resolves in the usage map and stays plain otherwise (never a placeholder), that
`usage.build_usage_by_flow` resolves both a main-stem (label-matched) and a worker-stem (sid8 ->
cwd -> worktree cwd) session end to end against a fixture `~/.claude/projects/`-shaped tree, and
that a non-200-status flow is dropped.
**Reads:** a fixture `projects_root` tree (temp dir) and a temp `_response.jsonl`-shaped file.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_msgs`, `.usage`, `src.proxy_display.forwarded_parser`.

---

### tests/test_project_display.py (262 LOC)

**Purpose:** Proves the PROJECT-over-CONTEXT rework: `discovery.project_for_stem` resolves a
worker's sid8 to the PROJECT's own cwd (never the worker's worktree cwd) via a fixture
`project_index`, with sid8/label/raw-stem fallbacks when nothing resolves; `display_stem` strips a
worker's sid8 while preserving the epoch; `resolve_stem` matches either the full on-disk stem or
its displayed form and raises ambiguity across their union; `filter_sessions` matches the PROJECT
path OR the stem; `render_sessions`/`render_expand_full` print the new PROJECT column/header.
**Reads:** a real temp directory of empty stem-shaped files (for `resolve_stem`).
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.render_expand`, `.render_sessions`,
`src.proxy_display.forwarded_parser`.

---

### tests/test_reqs.py (552 LOC)

**Purpose:** Proves `reqs`' fixed `REQ n   HH:MM:SS  CR c  CC c` line form and every filter/selector
built on it: CR padded to the widest value per session, re-fires collapsed, multi-session
blank-line separation, `--gap` pairing (inclusive threshold, "prints once" for a shared REQ),
`--merged` cross-session chronological interleave (a within-session gap bridged by another session
does not qualify), `--rebuild`/`--drop` predicates (strict-inequality boundaries, REQ 1 never
qualifying for `--drop`, the same-session predecessor rule under `--merged`), `--turn` narrowing
ahead of the other filters, and `filter_by_family`.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.render_reqs`, `.timeline_boundaries`.

---

### tests/test_search_chars.py (138 LOC)

**Purpose:** Proves `search`'s hit-line format (`search.find_matches`, `render.render_search`)
reports a block's original-payload chars instead of an occurrence count or snippet — one hit per
matching block regardless of how many occurrences it contains — and that hit-line columns align
across sessions with different label/chars widths.
**Reads:** nothing external — hand-built payloads run through the real `find_matches`/
`render_search` pipeline.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_search`, `.search`.

---

### tests/test_sidecar_exclusion.py (192 LOC)

**Purpose:** Proves a zero-tool, non-haiku sidecar `forwarded_delta` entry seeds no boundary, no
restart, and does not pollute the sys/tool delta comparison of the request after it
(`timeline._is_sidecar`/`request_boundaries`); that `discovery.build_session`'s request/message
counts skip the same entry; and that `reader.load_last_request` walks past a trailing sidecar line
exactly like a haiku one.
**Reads:** temp JSONL files shaped like the real dual-log streams, written and deleted per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.discovery`, `.reader`, `.timeline_boundaries`.

---

### tests/test_tool_name_comparison.py (214 LOC)

**Purpose:** Proves `msgs`' NAME-based tool comparison (`timeline._tool_lines`): a tool that shifts
INDEX with byte-identical content prints nothing (the `skill-help_1788343931` REQ 196
false-positive under index-based comparison), a removed name prints `tool[Name] removed` with no
chars column, a name's own content change at its new position still prints `changed`, and a
reintroduced name is tagged `new` again rather than silently dropped.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.render_msgs`, `.timeline_boundaries`.

---

### tests/test_turns.py (324 LOC)

**Purpose:** Proves `reqs`' always-on turn grouping: opener classification
(`timeline_grouping._is_turn_opener`/`turn_openers`), preview is the opener's LAST text block, the
turn-assignment rule (a request's `message_count` reaching past the next opener assigns it to the
NEXT turn even when its own `start_index` sits before that opener), `_fmt_duration`'s bands, the
turn separator's exact worked-example format, `--turn N` selecting one turn, and the
separator-survival rule under an active `--gap`/`--rebuild`/`--drop` filter.
**Reads:** a temp `_forwarded.jsonl`-shaped file per case.
**Writes:** stdout (pass/fail per check); exits 1 on any failure.
**Called by:** none — run manually.
**Calls out:** `src.dual_log_cli.reader`, `.render_format`, `.render_reqs`, `.timeline_boundaries`,
`.timeline_grouping`.

---

## Gotchas

**A real minus sign (U+2212), not an ASCII hyphen, appears in every delta-tail string** —
`test_msgs_overlay.py` asserts on it literally; grepping for a hyphen instead silently finds
nothing.

**A tool's wire chars and its raw stripped-description-text length are NOT the same unit**
(JSON-encoding vs. raw characters) — `test_msgs_sys_tool_overlay.py` deliberately sets them to
disagree to catch code that derives the tail's wire figure from the wrong one; the correct source
is always the measured `item["chars"]`.

**`probe_sys_tool_original_chars.py`'s `_infer_family`/`_delta_hash` are intentionally simplified,
NOT the production helpers** (`reader.infer_family`, `src.proxy.logging._delta_hash`) — good enough
for one probe run's own internal comparisons, not a byte-identical substitute; do not import them
elsewhere expecting production behavior.

**The probe resolves a worktree's dual-log directory by indexing `parents[4]`** off its own
`__file__` path, assuming the fixed `<main>/.claude/worktrees/<name>/...` layout — silently falls
back to the (nonexistent, in a worktree) direct path if that layout ever changes.

**Every day-boundary case in `test_local_time.py` is built from the machine's OWN current UTC
offset at run time, never hardcoded** — on a UTC+0 machine the crossing assertion is vacuously
true rather than wrong, so a green run there is not full coverage of the crossing logic.
