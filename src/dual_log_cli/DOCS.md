# src/dual_log_cli/

## Role

Read-only command-line inspector for the six-stream dual-log quartet in `src/logs/dual_log/`,
written by `src/proxy/addon.py`. Turns the raw per-request JSONL streams into a session inventory,
a deduplicated msg search, a request-grouped msg listing, a full-content window read (with the
proxy's own strip/inject overlay), and a turn-grouped per-session REQ/CR/CC listing. The
deduplicated msg timeline is the internal structure every command builds on; the user-facing unit
is the msg (one API message) and its blocks, matching the proxy pane's own display grammar.
Touch this package to add a new read-side view over the dual logs. Do NOT add anything here that
writes, creates or locks a path under `src/logs/dual_log/`: the logs are frozen evidence, and the
proxy appends to them live during a session.

## Public Interface

`__init__.py` is a package marker only — no exports. The entry path is the module runner:

```bash
./venv/bin/python -m src.dual_log_cli sessions [PROJECT] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
./venv/bin/python -m src.dual_log_cli msgs <stem-or-substring> [FROM] [TO]
./venv/bin/python -m src.dual_log_cli msgs <stem-or-substring> --req F [T]
./venv/bin/python -m src.dual_log_cli expand <stem-or-substring> <msg> [--before N] [--after N] [--only CLASSIFIER]
./venv/bin/python -m src.dual_log_cli search <term> [SCOPE] [--since D] [--until D] [--only CLASSIFIER] [--case-sensitive]
./venv/bin/python -m src.dual_log_cli reqs [SCOPE] [--since D] [--until D] [--main | --worker] [--turn N] [--gap M] [--merged] [--rebuild] [--drop]
```

Run from the project root. `bin/duallog` (repo root, mode 755) is the PATH-facing form: it cds to
the hardcoded repo root and execs the same module, so `duallog <command>` works from any cwd once
symlinked into PATH.

The log directory is resolved from `MONITOR_CC_ROOT`, else the repo root, else the main checkout
when running inside `.claude/worktrees/<name>/` — the log directory is gitignored and exists only
in the main checkout.

## Flow

`__main__` parses argv → `commands` resolves one or more sessions via `discovery` and loads each
via `timeline.load_timeline` → the matching `render_*` module turns the loaded data into text →
`commands` writes it to stdout. `discovery` groups the raw `*.jsonl` files by session stem and
resolves each stem's real project directory via `project_map` (a scan of CC's own
`~/.claude/projects/` transcript store). `timeline.load_timeline` is the per-session assembly
point: it parses the session's last non-haiku `_original` line (`reader`), derives turn rows
(`timeline_turns`) and request boundaries (`timeline_boundaries`), which `timeline_markers` and
`timeline_grouping` turn into REQ numbers and turn groups. `overlay` reconstructs the proxy's own
strip/inject deltas for `msgs`/`expand`; `usage` joins CC's transcript store for the CR/CC
prompt-cache figures `msgs` and `reqs` both show.

## Modules

### __main__.py (117 LOC)

**Purpose:** `main()` dispatches argv to the five subcommands (`sessions`, `msgs`, `expand`,
`search`, `reqs`); carries the full `--help` usage text as `_USAGE_EPILOG`; the `if __name__`
block runs `main()` and handles a broken output pipe.
**Reads:** `sys.argv`; the resolved dual_log directory via `discovery`.
**Writes:** stdout (rendered text), stderr (resolution, range and empty-term errors). Never touches the log directory.
**Called by:** the user, via `python -m src.dual_log_cli` or `bin/duallog`.
**Calls out:** —

---

### cli_args.py (160 LOC)

**Purpose:** The argparse parser construction — `_parse_args(argv, epilog)` builds the top-level
parser and its five subparsers (`sessions`, `msgs`, `expand`, `search`, `reqs`), one dedicated
helper per command.
**Reads:** Nothing — pure parser construction.
**Writes:** Nothing — returns an `argparse.Namespace`.
**Called by:** `__main__.py` (`_parse_args`, aliased there as `_build_args`).
**Calls out:** —

---

### commands.py (212 LOC)

**Purpose:** The five `_run_*` command implementations (`_run_sessions`, `_run_search`,
`_run_reqs`, `_run_msgs`, `_run_expand`) plus their shared validators (`_valid_day`,
`_reject_bad_days`, `_load_for`, `_window`).
**Reads:** the resolved dual_log directory and the parsed `argparse.Namespace`, both passed in by `__main__.main()`.
**Writes:** stdout (rendered text, via `sys.stdout.write`), stderr (resolution, range and empty-term errors).
**Called by:** `__main__.py` (`main()`, one `_run_*` per `args.command` branch).
**Calls out:** —

---

### project_map.py (66 LOC)

**Purpose:** Resolves the proxy's `md5(project_path)[:8]` session id — the only trace of a
worker's project in its stem — to that project's real cwd, by scanning CC's own transcript store.
`build_project_index` does that walk once and returns it in two shapes: `cwd_to_dir` (a main
stem's label match) and `sid_to_cwd` (a worker stem's sid8 lookup, keeping the real project path),
hashed via `src/proxy_display/forwarded_parser.py`'s `_proxy_session_id_for_project` — the single
source shared with `addon.py`'s own session-id derivation.
**Reads:** `~/.claude/projects/<encoded>/<uuid>.jsonl` (first ~40 lines of up to 3 newest transcripts per project dir).
**Writes:** Nothing — returns `{"cwd_to_dir": ..., "sid_to_cwd": ...}`; degrades to an empty structure on any failure rather than erroring.
**Called by:** `discovery.py`, `commands.py`, `usage.py`.
**Calls out:** —

---

### classifier.py (40 LOC)

**Purpose:** The `--only` vocabulary and its two operations, shared by `expand` and `search`.
`ROLES`/`TYPES` are the block types a msg can carry; `parse_only` turns a spec into a `(role,
type)` pair or raises `BadClassifierError`; `matches_only` applies it, matching the type side
against ANY of a msg's block types.
**Reads:** Nothing — pure vocabulary and predicates.
**Writes:** Nothing.
**Called by:** `cli_args.py` (`ONLY_FORMS`, interpolated into `--only`'s help text), `commands.py` (`parse_only`/`matches_only`/`BadClassifierError`), `search.py` (`matches_only`).
**Calls out:** —

---

### discovery.py (204 LOC)

**Purpose:** Log-directory resolution, stem grouping, stem parsing (`stem_identity` — the one
place every stem-derived value starts from), the session inventory (`build_session`), all session
selection (`filter_sessions` for context/scope/date, `filter_by_family` for `--main`/`--worker`),
and stem/substring resolution with explicit ambiguity and unknown errors.
**Reads:** `MONITOR_CC_ROOT`; the dual_log directory listing; each stem's `_forwarded.jsonl` in full; `stat().st_size` of all six streams.
**Writes:** Nothing — returns dicts.
**Called by:** `__main__.py`, `commands.py`, `usage.py` (`stem_identity`), `render_reqs.py` (`stem_identity`); `dev/dual_log_cli/tests/test_local_time.py`, `test_project_display.py`, `test_reqs.py`, `test_sidecar_exclusion.py`.
**Calls out:** —

---

### reader.py (105 LOC)

**Purpose:** The read-only file primitives — reverse chunked line-offset scanner, cheap model
sniff, last-conversation-request loader, small-file JSONL iterator, `infer_family`, and
`local_datetime` — the one place every UTC dual-log timestamp gets parsed and converted to this
machine's local time.
**Reads:** `_original` (byte ranges only, never whole-file) and any small stream line by line.
**Writes:** Nothing.
**Called by:** `discovery.py`, `timeline.py`, `timeline_boundaries.py`, `render_format.py`, `usage.py`; `dev/dual_log_cli/tests/test_local_time.py`, `test_msgs_blocks.py`, `test_msgs_sys_delta.py`, `test_msgs_usage.py`, `test_reqs.py`, `test_turns.py`, `test_sidecar_exclusion.py`.
**Calls out:** —

---

### timeline.py (30 LOC)

**Purpose:** `load_timeline(session)` — the one call that assembles everything a render needs for
one session: the last-request payload, its model family, its turn rows, and (when a `_forwarded`
stream exists) its request boundaries and turn-times.
**Reads:** The parsed last-request payload; the session's `_forwarded.jsonl` (via the submodules it calls).
**Writes:** Nothing — returns one data dict.
**Called by:** `commands.py`.
**Calls out:** —

---

### timeline_turns.py (109 LOC)

**Purpose:** Turn-row construction for one payload — `build_turns` (the compact per-msg rows
`msgs`/`expand` iterate), `iter_block_texts` (the block-text generator `search` builds on), and
`full_turn` (single-turn full extraction, what `expand` dumps) — each message summarized via
`src/proxy/message_summary.py`'s `_summarize_message`.
**Reads:** The parsed last-request payload.
**Writes:** Nothing — returns row lists or a generator.
**Called by:** `timeline.py` (`build_turns`), `search.py` (`iter_block_texts`), `commands.py` (`full_turn`); `dev/dual_log_cli/tests/test_msgs_blocks.py`.
**Calls out:** —

---

### timeline_boundaries.py (141 LOC)

**Purpose:** Request-boundary derivation from the `_forwarded` delta stream (`request_boundaries`)
plus, per boundary, its `sys_lines`/`tool_lines` — the system blocks and tools that request sent
in full (family's first request) or changed/added since the previous one of the same family,
compared via `src/proxy/logging.py`'s `_delta_hash` — the exact content-hash normalisation the
proxy itself uses, so a read-side "changed" decision matches the proxy's own.
**Reads:** The session's `_forwarded.jsonl`.
**Writes:** Nothing — returns boundary dicts and a `{turn_index: timestamp}` dict.
**Called by:** `timeline.py` (`request_boundaries`, `build_turn_times`), `render_msgs.py` (`_BILLING_HEADER_SYS_INDEX`, `_system_block_chars`, `_tool_chars`); `dev/dual_log_cli/tests/test_msgs_req_range.py`, `test_msgs_sys_delta.py`, `test_msgs_sys_tool_overlay.py`, `test_reqs.py`, `test_sidecar_exclusion.py`, `test_tool_name_comparison.py`, `test_turns.py`.
**Calls out:** —

---

### timeline_markers.py (76 LOC)

**Purpose:** Request markers and numbering. `request_markers` folds boundaries into
`{msg_index: {number, timestamp, refires, flow_id, sys_lines, tool_lines, message_count}}`, what
`msgs` draws its REQ separators from. `request_numbers_by_flow` is what `overlay` uses to name the
request behind a strip. `resolve_req_range`/`request_msg_range` translate a REQ number range into
the equivalent msg-index range for `msgs --req`.
**Reads:** Boundary dicts (from `timeline_boundaries.request_boundaries`) — parameters only, no module state.
**Writes:** Nothing — returns dicts, lists, or a `(start, end)` tuple; raises on an ambiguous/unknown REQ number.
**Called by:** `timeline_grouping.py` (`request_markers`), `overlay.py` (`request_numbers_by_flow`), `render_msgs.py` (`request_markers`), `commands.py` (`resolve_req_range`, the two errors); `dev/dual_log_cli/tests/test_msgs_req_range.py`.
**Calls out:** —

---

### timeline_grouping.py (38 LOC)

**Purpose:** Groups request markers into conversation turns for `reqs` — `turn_openers` finds
every `user` msg carrying a `text` block and no `tool_result` block; `_group_markers_by_turn`
assigns each request to a turn via the count of openers already contained in that request's own
`message_count`.
**Reads:** Turn rows and boundary dicts — parameters only, no module state.
**Writes:** Nothing — returns `(markers, openers, groups)`.
**Called by:** `render_reqs.py` (`_session_entries_and_separators`); `dev/dual_log_cli/tests/test_turns.py`.
**Calls out:** —

---

### overlay.py (121 LOC)

**Purpose:** Reconstructs the proxy's own strip/inject deltas as a read-side overlay: `build_overlay`
for one message block's `{(msg_idx, blk_idx): {stripped, injected, req}}`, `build_sys_tool_overlay`
for the equivalent per-system-index and per-tool-name shape, both by running the session's
`_stripped`/`_injected` delta streams through `src/proxy_display/dual_log_accumulator.py`'s
`accumulate_dual_log` — reused, not re-implemented.
**Reads:** The session's `_stripped.jsonl` and `_injected.jsonl`.
**Writes:** Nothing — returns one dict (`build_overlay`) or a 2-tuple of dicts (`build_sys_tool_overlay`).
**Called by:** `commands.py` (`build_overlay` from `_run_expand`/`_run_msgs`; `build_sys_tool_overlay` from `_run_msgs` only).
**Calls out:** —

---

### usage.py (144 LOC)

**Purpose:** Builds `msgs`' and `reqs`' `{flow_id: (cache_read_input_tokens,
cache_creation_input_tokens)}` map by joining the session's `_response` stream, a stem-scoped
subset of CC's transcript store, and that transcript's own assistant-message usage records.
**Reads:** The session's `_response.jsonl`; a small, stem-derived subset of `~/.claude/projects/*/*.jsonl`.
**Writes:** Nothing — returns one `{flow_id: (cr, cc)}` dict; `{}` on any missing stream, unresolved anchor, a stem that resolves to no known project directory, no candidate file matching, or an unreadable transcript.
**Called by:** `commands.py` (`_run_msgs`, `_run_reqs`); `dev/dual_log_cli/tests/test_local_time.py`, `test_msgs_usage.py`.
**Calls out:** —

---

### search.py (27 LOC)

**Purpose:** The literal-substring matcher over one session's deduplicated timeline. Returns one
hit per matching (turn, block), carrying that block's original-payload chars.
**Reads:** The parsed payload, streamed block by block via `timeline_turns.iter_block_texts`.
**Writes:** Nothing — returns the hit list.
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_search_chars.py`.
**Calls out:** —

---

### render_format.py (47 LOC)

**Purpose:** The shared formatters every renderer imports from — `fmt_chars`, `fmt_timestamp`,
`_clock`, `_window_date`, `_fmt_duration`, `_skipped_lines`. Every timestamp this package renders
routes through `reader.local_datetime`.
**Reads:** Nothing beyond its own arguments.
**Writes:** Nothing — returns strings or a list.
**Called by:** `render_sessions.py`, `render_msgs.py`, `render_reqs.py`, `render_expand.py`, `render_search.py`; `dev/dual_log_cli/tests/test_local_time.py`, `test_turns.py`.
**Calls out:** —

---

### render_sessions.py (20 LOC)

**Purpose:** `render_sessions` — one line per session, newest first (START, PROJECT, SESSION
columns; PROJECT widens to fit the longest resolved path rather than truncating).
**Reads:** Session dicts (from `discovery.list_sessions`/`filter_sessions`) — parameters only.
**Writes:** Nothing — returns the rendered string.
**Called by:** `commands.py` (`_run_sessions`); `dev/dual_log_cli/tests/test_project_display.py`.
**Calls out:** —

---

### render_msgs.py (169 LOC)

**Purpose:** `msgs`' request-grouped classifier listing — a REQ separator per request group
(optionally carrying CR/CC), that request's own sys/tool delta lines, then one `[idx] role type
chars` line per msg (block sub-lines for a multi-block msg), each carrying a strip/inject delta
tail when the proxy transformed it.
**Reads:** The dicts produced by `timeline.load_timeline`, `usage.build_usage_by_flow`, `overlay.build_overlay`/`build_sys_tool_overlay`.
**Writes:** Nothing — returns a string; `commands.py` does the `sys.stdout.write`.
**Called by:** `commands.py` (`_run_msgs`); `dev/dual_log_cli/tests/test_msgs_blocks.py`, `test_msgs_overlay.py`, `test_msgs_sys_delta.py`, `test_msgs_sys_tool_overlay.py`, `test_msgs_usage.py`, `test_tool_name_comparison.py`.
**Calls out:** —

---

### render_search.py (24 LOC)

**Purpose:** `render_search` — search results across one or more sessions: one term line, then a
`session <stem>` line plus its hit lines per matching session.
**Reads:** `(session, hits)` pairs (from `commands._run_search`) — parameters only.
**Writes:** Nothing — returns the rendered string.
**Called by:** `commands.py` (`_run_search`); `dev/dual_log_cli/tests/test_search_chars.py`.
**Calls out:** —

---

### render_reqs.py (178 LOC)

**Purpose:** `reqs`' turn-grouped, CR/CC-annotated REQ listing — `render_reqs`/`render_reqs_merged`
share one pipeline (`_session_entries_and_separators`, `_apply_filters`, `_grouped_lines`) that
turns-groups every session's REQs, then applies `--turn`/`--gap`/`--rebuild`/`--drop` as pure
filters over that one fixed line form; `--merged` flattens every session into one
chronologically-sorted, session-tagged chain instead of one listing per session.
**Reads:** `(session, boundaries)` pairs, `turns_by_stem`, `usage_by_stem` (all from `commands._run_reqs`) — parameters only.
**Writes:** Nothing — returns a string; `commands.py` does the `sys.stdout.write`.
**Called by:** `commands.py` (`_run_reqs`); `dev/dual_log_cli/tests/test_reqs.py`, `test_turns.py`.
**Calls out:** —

---

### render_expand.py (48 LOC)

**Purpose:** `render_expand_full` — `expand`'s full-content window dump: a session/project/window
header, then each selected msg's full block content, with `── stripped by REQ n ──`/`── injected
by REQ n ──` sections for a block the proxy transformed.
**Reads:** The dict produced by `timeline.load_timeline`, plus `dumped` (already-selected msg/block rows from `commands._run_expand`).
**Writes:** Nothing — returns a string; `commands.py` does the `sys.stdout.write`.
**Called by:** `commands.py` (`_run_expand`); `dev/dual_log_cli/tests/test_project_display.py`.
**Calls out:** —

---

## State

No mutable state — every command is a single pass with no caches, no module-level state, and no
files written anywhere. Two external inputs decide the output: the dual_log directory's contents
and CC's own `~/.claude/projects/` transcript store (read by `project_map`/`usage` for project and
CR/CC resolution) — a run is reproducible only while both are unchanged, and the output tracks
whatever the proxy has appended to a live session by the time it runs.

## Gotchas

**A "sidecar" line is any non-haiku `_forwarded` entry with `counts.tools == 0`
(`timeline_boundaries._is_sidecar`).** `request_boundaries`, `discovery.build_session` and
`reader.load_last_request` each apply an equivalent exclusion independently rather than sharing one
predicate across all three — keep them in sync if the shape of a sidecar ever changes.

**`reader.load_last_request`'s haiku sniff is a cheap 512-byte window
(`_MODEL_SNIFF_BYTES`), but the zero-tool sidecar check needs the full parsed line** — `tools` can
sit arbitrarily far past that window behind a large system block, so there is no equivalently cheap
sniff for it.

**System index 0 (`_BILLING_HEADER_SYS_INDEX = 0`) is excluded unconditionally from the sys delta
comparison on every request but the first, and from the original-chars lookup on every request
including the first** — it is a hash plus the previous request id, so it differs by construction on
every single request and would otherwise swamp the real changed/new signal.

**Tool comparison in `timeline_boundaries._tool_lines` is NAME-based, not index-based** — removing
one tool renumbers every tool after it, which an index-based diff cannot distinguish from a real
edit. The name-based set-difference this uses has one blind spot: it cannot tell "tool X removed"
apart from "tool X removed AND a different, already-present-elsewhere tool added in the same
request" — both look like the same net membership change.

**`timeline_grouping._group_markers_by_turn` assigns a request to a turn via
`bisect_right(openers, marker["message_count"] - 1)`, never via the marker's own msg-index key
(`start_index`).** A request whose send bundles the previous turn's idle reply together with the
next turn's new prompt has a `start_index` that lands in the wrong turn if grouped by key instead
of by `message_count`.

**`render_reqs._rebuild_drop_qualifies`'s `--drop` boundary is strict (`<`), the opposite
convention from `--gap`'s inclusive (`>=`).** An exact `CR(n) == CR(n-1) + CC(n-1)` means the whole
prefix WAS read back, so it must NOT qualify for `--drop`.

**`--drop`'s "previous request" is always the same session's own previous REQ, even under
`--merged`.** `prev_usage` is precomputed per session (msg-index order) before `_merged_entries`
ever flattens/sorts across sessions, so a cross-session chronological neighbor never substitutes
for it.

**`usage._candidate_dirs` appends `.claude/worktrees/<name>` to a worker's sid8-resolved project
cwd; `discovery.project_for_stem` returns that same cwd UNCHANGED.** The two need different paths
for different reasons — `usage.py` needs the worker's own worktree cwd to find its transcript,
`sessions`' PROJECT column needs the project itself, not the worktree. Conflating them breaks one
or the other silently.

**`discovery.resolve_dual_log_dir` reaches the main checkout from inside a worktree via a fixed
parent-count (`here.parents[5]`).** Moving this module to a different depth in the package tree
breaks that offset.

**`render_msgs`'s columns are fixed-width** — chars is 6 wide (`_MSG_CHARS_WIDTH`), `_BLOCK_INDENT`
is exactly 8 spaces so a block sub-line never matches `^\[` (the `grep '^\['`-selects-msg-lines
contract). An index of 1000+ or a 7-digit chars value pushes its own line one column wider;
right-alignment keeps it readable but not aligned to its neighbors.

**`search.find_matches` returns `[]` for an empty term rather than matching everything** — `str.count("")` counts positions, so a blank needle would otherwise report every block as a hit.

**`reader.local_datetime` returns `None` for an empty/unparseable timestamp rather than raising.**
Every caller has its own fallback: `"?"` in a renderer, silent drop from an active date filter in
`discovery.filter_sessions`.

**`__main__.py`'s `BrokenPipeError` guard has two parts, both required.** It flushes stdout inside
the `try`, and on failure `dup2`s stdout to `os.devnull` so the interpreter's own shutdown flush has
nothing left that can fail — dropping either half can resurface `BrokenPipeError` on stderr during
shutdown.

**`timeline_markers.request_msg_range` raises `AmbiguousRequestNumberError` when a REQ number maps
to more than one msg index, rather than guessing.** This can happen even without a restart: a
trailing re-fire that adds no msg can become the sole owner of its own group (a new `start_index`
nothing after it ever fills), but the running request-number counter never advanced for it, so it
inherits the same number as the group before it.
