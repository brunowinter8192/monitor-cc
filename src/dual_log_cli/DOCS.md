# src/dual_log_cli/

## Role

Read-only command-line inspector for the dual-log streams the proxy writes to the gitignored runtime directory. Provides session inventory, deduplicated search, request-grouped message listing, full-content expand with strip/inject overlay and a turn-grouped request listing. Add new read-side views here. Never write, create or lock anything under the log directory.

## Public Interface

`__init__.py` is empty. Entry path is the module runner `python -m src.dual_log_cli <command>` with the commands sessions, msgs, expand, search and reqs; `bin/duallog` is the PATH-facing wrapper. The log directory is resolved from the monitor root, falling back to the main checkout inside a worktree.

## Flow

`__main__.py` parses arguments (`cli_args.py`) → `commands.py` resolves sessions via `discovery.py` and loads each through `timeline.py`.
→ `timeline.py` assembles payload, turns and request boundaries from the reader, turn, boundary, marker and grouping modules.
→ `overlay.py`, `usage.py` and `numbering.py` add strip/inject overlay and cache figures → `render_*.py` produce text → `commands.py` writes stdout.

## Modules

### __main__.py (120 LOC)

**Purpose:** Dispatches arguments to the five subcommands, carries the help text and handles a broken output pipe.
**Reads:** argv; the resolved log directory via `discovery.py`.
**Writes:** stdout and stderr; never the log directory.
**Called by:** the user via `python -m src.dual_log_cli` or `bin/duallog`.
**Calls out:** none

---

### cli_args.py (174 LOC)

**Purpose:** Builds the argument parser and the subparsers for the five commands.
**Reads:** none.
**Writes:** none (returns the parsed namespace).
**Called by:** `__main__.py`.
**Calls out:** none

---

### commands.py (278 LOC)

**Purpose:** Implements the five commands with their shared validators, window and request-range routing, and skip reporting.
**Reads:** the log directory and parsed arguments passed by `__main__.py`.
**Writes:** stdout and stderr.
**Called by:** `__main__.py`.
**Calls out:** none

---

### project_map.py (70 LOC)

**Purpose:** Maps the proxy's hashed project id to the project's real directory by scanning Claude Code's transcript store.
**Reads:** the transcript store under the home folder.
**Writes:** none (returns lookup dicts); unreadable entries reported on stderr.
**Called by:** `discovery.py`, `commands.py`, `usage.py`.
**Calls out:** none

---

### classifier.py (40 LOC)

**Purpose:** The `--only` vocabulary with its parse and match operations, shared by expand and search.
**Reads:** none.
**Writes:** none.
**Called by:** `cli_args.py`, `commands.py`, `search.py`.
**Calls out:** none

---

### discovery.py (213 LOC)

**Purpose:** Log-directory resolution, stem grouping and parsing, session inventory, session selection and stem resolution with explicit errors.
**Reads:** monitor root; the log directory listing; each stem's forwarded stream; file sizes.
**Writes:** none (returns dicts).
**Called by:** `__main__.py`, `commands.py`, `usage.py`, `render_reqs.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** none

---

### reader.py (83 LOC)

**Purpose:** Read-only file primitives: reverse line scanner, model sniff, last-request loader, small-file JSONL iterator and local-time conversion.
**Reads:** the original stream (byte ranges) and small streams line by line.
**Writes:** none.
**Called by:** `discovery.py`, `timeline.py`, `timeline_boundaries.py`, `render_format.py`, `usage.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** `proxy.message_summary`

---

### diagnostics.py (14 LOC)

**Purpose:** Prints a skip or fallback cause to stderr once per identical line.
**Reads:** none.
**Writes:** stderr.
**Called by:** `commands.py`, `project_map.py`, `reader.py`, `usage.py`.
**Calls out:** none

---

### timeline.py (32 LOC)

**Purpose:** Assembles everything a render needs for one session: last payload, model family, turn rows, request boundaries and turn times.
**Reads:** the parsed last payload; the forwarded stream via submodules.
**Writes:** none (returns one data dict).
**Called by:** `commands.py`.
**Calls out:** none

---

### timeline_turns.py (109 LOC)

**Purpose:** Builds turn rows, block-text iteration and full-turn extraction for one payload.
**Reads:** the parsed last payload.
**Writes:** none (returns rows or a generator).
**Called by:** `timeline.py`, `search.py`, `commands.py`; `dev/dual_log_cli/tests/test_msgs_blocks.py`.
**Calls out:** none

---

### timeline_boundaries.py (176 LOC)

**Purpose:** Derives request boundaries and continue requests from the forwarded delta stream, with per-request system and tool change lines.
**Reads:** the session's forwarded stream.
**Writes:** none (returns boundary dicts and turn times).
**Called by:** `timeline.py`, `render_msgs.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** none

---

### timeline_markers.py (136 LOC)

**Purpose:** Builds request markers and numbering and translates request number ranges into message index ranges.
**Reads:** boundary dicts (parameters only).
**Writes:** none (returns dicts, lists or ranges; raises on ambiguous or unknown numbers).
**Called by:** `timeline_grouping.py`, `overlay.py`, `render_msgs.py`, `commands.py`; `dev/dual_log_cli/tests/test_msgs_req_range.py`.
**Calls out:** none

---

### timeline_grouping.py (38 LOC)

**Purpose:** Groups request markers into conversation turns for the request listing.
**Reads:** turn rows and boundary dicts (parameters only).
**Writes:** none (returns markers, openers and groups).
**Called by:** `render_reqs.py`; `dev/dual_log_cli/tests/test_turns.py`.
**Calls out:** none

---

### overlay.py (121 LOC)

**Purpose:** Reconstructs the proxy's strip/inject deltas as a read-side overlay by reusing the display accumulator.
**Reads:** the session's stripped and injected streams.
**Writes:** none (returns overlay dicts).
**Called by:** `commands.py`.
**Calls out:** none

---

### numbering.py (108 LOC)

**Purpose:** Resolves a session's transcript once and annotates every request with the token pane's number, turn and response time.
**Reads:** payload messages from `commands.py`; transcript data via `panes/cache_turns.py`, `format/token_format.py` and `usage.py`.
**Writes:** mutates the passed boundary dicts in place; returns usage, turns, path used and annotated requests.
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_reqs_pane_numbering.py`.
**Calls out:** `panes/cache_turns.py`, `format/token_format.py`

---

### usage.py (156 LOC)

**Purpose:** Builds the per-flow cache read and creation figures by joining the response stream with Claude Code's transcript usage records.
**Reads:** the session's response stream; a stem-scoped subset of the transcript store.
**Writes:** none (returns a mapping, empty on any missing input).
**Called by:** `commands.py`, `numbering.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** none

---

### search.py (27 LOC)

**Purpose:** Literal-substring matcher over one session's deduplicated timeline.
**Reads:** the parsed payload, block by block.
**Writes:** none (returns hits).
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_search_chars.py`.
**Calls out:** none

---

### render_format.py (47 LOC)

**Purpose:** Shared formatters for the renderers, routing every timestamp through the local-time conversion.
**Reads:** none.
**Writes:** none (returns strings).
**Called by:** `render_sessions.py`, `render_msgs.py`, `render_reqs.py`, `render_expand.py`, `render_search.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** none

---

### render_sessions.py (20 LOC)

**Purpose:** Renders the session inventory, one line per session, newest first.
**Reads:** session dicts (parameters only).
**Writes:** none (returns text).
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_project_display.py`.
**Calls out:** none

---

### render_msgs.py (171 LOC)

**Purpose:** Renders the request-grouped message listing with per-request delta lines and strip/inject tails.
**Reads:** timeline, usage and overlay data (parameters only).
**Writes:** none (returns text).
**Called by:** `commands.py`; tests under `dev/dual_log_cli/tests/`.
**Calls out:** none

---

### render_search.py (24 LOC)

**Purpose:** Renders search results across sessions.
**Reads:** session and hit pairs (parameters only).
**Writes:** none (returns text).
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_search_chars.py`.
**Calls out:** none

---

### render_reqs.py (281 LOC)

**Purpose:** Renders the turn-grouped request listing with cache figures and the turn, gap, rebuild, drop and merged filters.
**Reads:** sessions, boundaries, turns, usage, continues and pane turns (parameters only).
**Writes:** none (returns text).
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_reqs.py`, `test_turns.py`.
**Calls out:** `proxy_display.format`

---

### render_expand.py (49 LOC)

**Purpose:** Renders the full-content window dump with stripped and injected sections per block.
**Reads:** timeline data and selected rows (parameters only).
**Writes:** none (returns text).
**Called by:** `commands.py`; `dev/dual_log_cli/tests/test_project_display.py`.
**Calls out:** none

---

## State

No mutable state: every command is a single pass without caches or written files. Output depends on the dual-log directory contents and Claude Code's transcript store, and tracks whatever the proxy has appended to a live session. Gotchas and the two numbering paths are in `process-docs/refactoring/` (phase 4 proxy/panes restructure file) and `process-docs/dual_log_cli/`.
