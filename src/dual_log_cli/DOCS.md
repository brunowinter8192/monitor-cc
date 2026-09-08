# src/dual_log_cli/

## Role

Read-only command-line inspector for the six-stream dual-log quartet in `src/logs/dual_log/`
written by `src/proxy/addon.py`. Turns ~15 GB of unreadable JSONL — every `_original` line
re-embeds the entire conversation history, so grep and head report every content hit once per
subsequent request — into a session inventory, a deduplicated search, a msg listing grouped by
request, a full-content read of any msg window that also shows what the proxy stripped from
and injected into those msgs, a bare per-session REQ number/time listing (since 2026-09-04), and
(since 2026-09-08) a per-TURN listing splitting each turn's duration into model time and tool wall
time. The deduplicated msg timeline is the internal
data structure all six commands build on; it has no command that renders it whole, because the two
views worth having are the request-grouped classifier listing (`msgs`) and the full content of a
chosen range (`expand`). `reqs` renders neither — it is a coarser, msg-content-free index over the
SAME `timeline.request_markers` structure `msgs` already draws its separators from, for locating a
REQ number/time before diving into `msgs --req` or `expand`. `turns` renders neither either — it
groups `request_markers`' own REQs into the turns a human/orchestrator prompt opened (see
`timeline.build_turn_rows`) and joins CC's own transcript a SECOND way (alongside `usage.py`'s
existing CR/CC join) to learn each request's stream-end time and output tokens, since the dual log
itself only ever records a request's SEND time. The
user-facing unit is the msg (one API message) and its blocks, matching the proxy pane's display
grammar.
Touch this package to add read-side views over the dual logs. Do NOT add anything here that
writes, creates or locks a path under `src/logs/dual_log/`: the logs are frozen evidence and the
proxy appends to them live during a session.

## Public Interface

`__init__.py` is a package marker only — no exports. The entry path is the module runner:

```bash
./venv/bin/python -m src.dual_log_cli sessions [CONTEXT] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
./venv/bin/python -m src.dual_log_cli msgs <stem-or-substring> [FROM] [TO]
./venv/bin/python -m src.dual_log_cli msgs <stem-or-substring> --req F [T]
./venv/bin/python -m src.dual_log_cli expand <stem-or-substring> <msg> [--before N] [--after N] [--only CLASSIFIER]
./venv/bin/python -m src.dual_log_cli search <term> [SCOPE] [--since D] [--until D] [--only CLASSIFIER] [--case-sensitive]
./venv/bin/python -m src.dual_log_cli reqs [SCOPE] [--since D] [--until D] [--main | --worker] [--gap M] [--merged] [--rebuild] [--drop]
./venv/bin/python -m src.dual_log_cli turns <stem-or-substring>
./venv/bin/python -m src.dual_log_cli turns <stem-or-substring> <N>
```

Run from the project root. `bin/duallog` (repo root, mode 755) is the PATH-facing form: it cds to
the hardcoded repo root and execs the same module, so `duallog <command>` works from any cwd once
symlinked into PATH. Hardcoded on purpose — a symlink must always run the main checkout, never
whatever worktree the script was copied into.

The log directory is resolved from `MONITOR_CC_ROOT`, else the repo root, else the main checkout
when running inside `.claude/worktrees/<name>/` — the log directory is gitignored and exists only
in the main checkout.

## Flow

`__main__` parses argv → `discovery` resolves the log dir and groups `*.jsonl` by session stem →
`sessions` builds one inventory row per stem from that stem's `_forwarded` stream alone, with
`project_map` resolving each worker stem's 8-hex project id once per run.
`msgs` and `expand` resolve one stem, then `reader` reverse-seeks the last non-haiku, non-sidecar
`_original` line and parses only that line → `timeline` builds turn rows via `proxy.message_summary`
plus request boundaries from `_forwarded.counts.messages`, `system_delta` and `tools_delta` — a
zero-tool non-haiku line (`timeline._is_sidecar`) is excluded from that boundary walk the same way
`discovery.build_session` excludes it from the inventory's request count. `msgs`
prints those rows for an inclusive index range, interleaving one REQ separator per request group
(`timeline.request_markers` folds the boundaries into `{msg_index: {number, timestamp, refires,
flow_id, sys_lines, tool_lines}}`, the last carrying the system/tool blocks that request's own
delta named) and, when `usage.build_usage_by_flow`
resolves it, that group owner's prompt-cache usage, then appends each transformed msg/block's
strip/inject delta and wire size from `overlay` (which accumulates the session's
`_stripped`/`_injected` delta streams through `proxy_display.parser.accumulate_dual_log`) and,
since 2026-09-04, the same treatment for its sys/tool delta lines from
`overlay.build_sys_tool_overlay` (a sibling accumulation over the SAME two streams); `expand`
slices an anchor-centred window out of the same rows, re-summarizes each selected msg for its full
block content, and adds the proxy's own transformations of those blocks via the SAME `overlay`
call. `search` selects a
SET of sessions the same way `sessions` does (scope + date window), repeats that per-session
reconstruction for each one and streams its blocks through the matcher, skipping any session whose
timeline will not load. `reqs` (2026-09-04) selects its session set the SAME way `search` does
(scope + date window via `discovery.filter_sessions`, plus `discovery.filter_by_family` for
`--main`/`--worker`), reconstructs each one's timeline the same way (skip-on-unloadable, counted
identically), but reads only `data["boundaries"]` from it — no matcher, no msg content at all —
and folds those into `timeline.request_markers` per session, printing every request's number and
timestamp and nothing else — `--rebuild`/`--drop` additionally route each session's boundaries
through `usage.build_usage_by_flow` (the SAME join `msgs` uses), only when either flag is set.
`turns` (2026-09-08) resolves one stem exactly like `msgs`/`expand` (no scope, no date window),
then joins CC's transcript a SECOND way — `usage.build_request_times_by_flow` (the SAME
`_response`-anchor → candidate-directory → transcript-file resolution `build_usage_by_flow` uses,
factored into the shared `usage._resolve_session_transcript`, but reading each assistant record's
OWN timestamp and `output_tokens` instead of its cache figures) — to learn each request's stream-
END time, which the dual log itself never records (only the SEND time, `request_markers`' own
`timestamp`). `timeline.build_turn_rows` then does the actual work: `timeline.turn_openers` finds
every `user` msg carrying a `text` block and no `tool_result` block (a turn opener), and every
`request_markers` entry is assigned to the LATEST opener already contained in ITS OWN
`message_count` (not the msg-index key it is grouped under — see Gotchas for why the two differ),
giving one row per turn with duration/model-time/tool-time/token sums, or `?` in all four when any
one of the turn's requests fails to resolve against the join. `turns <session> N` (2026-09-09,
Milestone 2) routes the SAME loaded data and `times_by_flow` through `timeline.build_turn_requests`
instead, for one row per REQUEST of turn `N`: model/tool seconds and tokens resolve independently
per request (no aggregate to protect), and a request's tool_use names come from the msg range its
OWN reply occupies — `[this request's message_count, the NEXT request's message_count)`, the next
request GLOBALLY rather than bounded to the turn, since a reply exists regardless of which turn
later claims the following request → `render` emits plain terminal text to stdout.

## Modules

### __main__.py (546 LOC)

**Purpose:** argparse dispatch for the six subcommands (`sessions`, `msgs`, `expand`, `search`, `reqs`, `turns`) plus the optional `CONTEXT` / `SCOPE` / `FROM` / `TO` positionals and the `--since` / `--until` / `--before` / `--after` / `--only` / `--case-sensitive` variants, `expand`'s window arithmetic and bound validation (`_run_expand` / `_window`), `msgs`' inclusive-range defaulting and bound validation (`_run_msgs`, which also builds the CR/CC usage map via `usage.build_usage_by_flow`, the strip/inject overlay via `overlay.build_overlay` — the same call `_run_expand` makes — and, since 2026-09-04, the sys/tool strip/inject overlay via `overlay.build_sys_tool_overlay`, `msgs`-only since it feeds `_req_delta_lines`, which `expand` never renders), the shared `_reject_bad_days` validator, the per-session search loop with its skip-on-unloadable guard, day-flag validation via `strptime` (rejects impossible dates, not just wrong shapes), the shared `_load_for` session resolution, the process exit codes, and the broken-pipe guard. **`msgs --req F [T]` (2026-09-04):** an `nargs="+"` argparse option translated in `_run_msgs` via `timeline.resolve_req_range` into the equivalent msg-index `[start, end]` pair before falling into the SAME rendering call FROM/TO already uses — no separate code path in `render.py`. Validated before that call: `--req` combined with a FROM/TO positional is a usage error (`"--req cannot be combined with FROM/TO"`, exit 2); a length outside `{1, 2}` is a usage error (`"--req takes one or two REQ numbers: --req F [T]"`, exit 2); `timeline.UnknownRequestNumberError`/`AmbiguousRequestNumberError` are caught and their own message printed verbatim (exit 2 either way) rather than an empty listing; a defensive `end < start` check (mirroring the pre-existing FROM/TO one) catches the pathological case where a restart's non-monotonic msg-index/REQ-number relationship would otherwise invert the computed range. **`reqs` (2026-09-04):** `_run_reqs` mirrors `_run_search`'s exact scoping/skip-on-unloadable shape (`filter_sessions` for scope+date, then `discovery.filter_by_family` for `--main`/`--worker`, then a per-session `load_timeline` try/except loop counting failures into `skipped`) but collects `(session, data["boundaries"])` pairs instead of hit lists — `render_reqs` does the rest. `--main`/`--worker` are an `argparse.add_mutually_exclusive_group()` (the ONLY mutually-exclusive CLI pair in this package enforced natively by argparse rather than a manual check — the positional-vs-`--req` exclusivity above cannot use this mechanism since argparse mutually-exclusive groups only support optional arguments). **`reqs --gap MINUTES` (same day):** a plain `type=int` option, `None` by default; `_run_reqs` rejects a negative value (`"--gap must be 0 or greater"`, exit 2, mirroring `expand --before/--after`'s precedent) and otherwise passes it straight through to `render_reqs` as a THIRD positional argument — no interaction with scope/date/family filtering at all, since it operates entirely on the per-session REQ list AFTER session selection, composing with every other `reqs` filter for free. **`reqs --merged` (2026-09-04, same day):** a `store_true` flag, no mutual exclusivity with anything (it changes only which render function turns `results` into text, never session SELECTION) — `_run_reqs` dispatches to `render_reqs_merged(results, skipped, args.gap)` instead of `render_reqs(...)` when set, both fed the IDENTICAL `results` list built by the SAME scope/date/family/skip-on-unloadable code above the dispatch, so `--merged` composes with every other `reqs` flag, including `--gap`, without any interaction code of its own. **`reqs --rebuild`/`--drop` (2026-09-04, same day):** two independent `store_true` flags — `_run_reqs` builds `usage_by_stem = {stem: usage.build_usage_by_flow(session, boundaries)}` (one join per LOADED session) ONLY when either is set, so a plain `reqs`/`reqs --gap`/`reqs --merged` run never touches `~/.claude/projects/` at all; both flags and that map are then passed straight through to whichever render function `--merged` already selected, as three additional positional args — `render.py`'s own `filtering = rebuild or drop` gate is what decides whether the pre-existing code paths run unchanged or the new usage-filtered ones do. **`turns` (2026-09-08):** `_run_turns` resolves one stem via the SAME `_load_for` `msgs`/`expand` already use — no scope, no date window, a single-session command by design (the milestone spec calls this out explicitly: a turn only makes sense within one session's own request/response chain). Two guards before any join runs: an empty `data["turns"]` list (`"session carries no msgs"`, exit 2, the exact message `_run_msgs` already uses for the identical condition) and, since a turn additionally needs at least one opener, `not timeline.turn_openers(data["turns"])` (`"session carries no turn-opening msgs"`, exit 2 — a distinct message, since this is a different failure: msgs exist but none of them is a user text prompt). `usage.build_request_times_by_flow(data["session"], data["boundaries"])` builds the stream-end/token map unconditionally (unlike `reqs --rebuild`/`--drop`'s opt-in join — a `turns` run has no purpose without it), then `timeline.build_turn_rows` and `render.render_turns` do the rest; no new code here for the turn grouping or duration arithmetic itself. **`turns <session> N` (2026-09-09, Milestone 2):** an optional `int` positional, `None` by default (`args.turn is None` takes the EXACT pre-existing bare-listing branch, unchanged — this is what keeps the bare output byte-identical to before this milestone). When given, `_run_turns` routes the SAME `data`/`times_by_flow` through `timeline.build_turn_requests` instead of `build_turn_rows`, catching `timeline.UnknownTurnNumberError` and printing its own message verbatim (exit 2) — mirroring `msgs --req`'s `UnknownRequestNumberError` handling above rather than a fresh range check written here, so the SAME "let the pure function own its own valid-range logic" convention holds for both.
**Reads:** `sys.argv`; the resolved dual_log directory via `discovery`.
**Writes:** stdout (rendered text), stderr (resolution, range and empty-term errors). Never touches the log directory.
**Called by:** the user, via `python -m src.dual_log_cli` or `bin/duallog`.
**Calls out:** `discovery`, `render`, `search`, `timeline`, `overlay`, `usage` (all package-local; `overlay.build_overlay` from both `_run_expand` and `_run_msgs`; `overlay.build_sys_tool_overlay` only from `_run_msgs`; `usage.build_usage_by_flow` from `_run_msgs` always and from `_run_reqs` when `--rebuild`/`--drop` is set; `usage.build_request_times_by_flow` only from `_run_turns`; `timeline.resolve_req_range` only from `_run_msgs`'s `--req` path; `timeline.build_turn_rows`/`turn_openers` only from `_run_turns`; `timeline.build_turn_requests` only from `_run_turns`'s `N`-given branch; `discovery.filter_by_family` only from `_run_reqs`).

---

### project_map.py (91 LOC, 2026-08-29, extended 2026-09-03)

**Purpose:** Resolves the proxy's `md5(project_path)[:8]` session id — the only trace of a worker's project in its stem — to a project label. Scans `~/.claude/projects/*/`, takes the first `cwd` record out of the newest transcript per directory, and hashes those real paths with the production helper. Reads CC's transcript store, never the dual logs. `build_project_index` (added 2026-09-02 for `usage.py`) does the SAME walk once and returns it in two raw shapes instead of collapsing straight to `{sid8: label}`: `cwd_to_dir` (a main stem's label match) and `sid_to_cwd` (a worker stem's sid8 lookup, keeping the real path `usage.py` needs to derive a worktree cwd from). `build_project_map` is now a one-line projection of that index, so both callers share one walk's worth of logic even though `discovery.list_sessions` and `usage.build_usage_by_flow` invoke it separately (once per run each — not memoized across the two, since they run in different commands).
**Reads:** `~/.claude/projects/<encoded>/<uuid>.jsonl` (first ~40 lines of up to 3 newest transcripts per project dir).
**Writes:** Nothing — returns `{sid8: label}` (`build_project_map`) or `{"cwd_to_dir": ..., "sid_to_cwd": ...}` (`build_project_index`); both degrade to an empty structure on any failure rather than erroring.
**Called by:** `discovery.list_sessions` (once per run, shared across all sessions), `__main__._load_for`, `usage.build_usage_by_flow` (`build_project_index` only).
**Calls out:** `src/proxy_display/forwarded_parser.py` (`_proxy_session_id_for_project` — the single source shared with `addon.py`'s `_derive_session_id`, never re-derived here); stdlib (`json`, `os`, `pathlib`).

---

### classifier.py (50 LOC, 2026-08-29)

**Purpose:** The `--only` vocabulary and its two operations, shared by `expand` and `search`. `ROLES` (3) and `TYPES` (9) are the BLOCK types a msg can carry — the real content blocks (text, thinking, tool_use, tool_result, image) plus the pseudo-types a str-content msg contributes as its single synthetic block; `parse_only` turns a spec into a `(role, type)` pair or raises `BadClassifierError`; `matches_only` applies it, matching the type side against ANY of a msg's block types. `ONLY_FORMS` is the accepted-forms sentence, interpolated into both `--help` texts so the syntax is documented where it is used.
**Reads:** Nothing — pure vocabulary and predicates.
**Writes:** Nothing.
**Called by:** `__main__.py` (validation once per run, then msg selection in `expand`), `search.py` (hit filtering).
**Calls out:** —

---

### discovery.py (233 LOC)

**Purpose:** Log-directory resolution, stem grouping, context rendering (`context_for_stem`, pure — the project map is injected, not looked up), `stem_identity` (added 2026-09-02: the same worker/main split as `context_for_stem`, returned as raw parts — `("worker", sid8, name)` or `("main", family_head, label)` — for a caller that needs the pieces rather than the rendered string; `usage.py` is the only one so far), the session inventory (`build_session`'s `requests`/`requests_main`/`messages` figures skip a zero-tool non-haiku line the same way `timeline._is_sidecar` does, since 2026-09-03 — see Gotchas), all session selection in one place (`filter_sessions` — a `context` substring for `sessions`, a broader `scope` substring matching context OR stem for `search`/`reqs`, plus an inclusive start-day window, all ANDed — the day window compares each session's LOCAL calendar day since 2026-09-04, via `reader.local_datetime`, not the raw UTC day prefix it used to slice off the ISO string), `filter_by_family` (2026-09-04: `reqs`' `--main`/`--worker` — a plain rendered-context PREFIX check, `"opus/"` or `"worker/"`, unrelated to `filter_sessions`' substring matching and deliberately not folded into it since only `reqs` has this filter class), and stem/substring resolution with explicit ambiguity and unknown errors (`AmbiguousSessionError`, `UnknownSessionError`).
**Reads:** `MONITOR_CC_ROOT`; the dual_log directory listing; each stem's `_forwarded.jsonl` in full; `stat().st_size` of all six streams.
**Writes:** Nothing — returns dicts.
**Called by:** `__main__.py`, and indirectly by `timeline.load_timeline` through the session dict it is handed; `usage.py` (`stem_identity` only).
**Calls out:** `reader` (`infer_family`, `iter_jsonl`, `local_datetime` since 2026-09-04).

---

### reader.py (137 LOC)

**Purpose:** The read-only file primitives. Reverse chunked line-offset scanner, cheap model sniff, last-conversation-request loader, small-file JSONL iterator, `infer_family` (the haiku/sonnet/else→opus rule shared with `addon.py` and `dev/proxy_dual_log/`), and (2026-09-04) `local_datetime` — the ONE place every UTC `"...Z"` dual-log timestamp gets parsed and converted to this machine's LOCAL, DST-correct time (`.astimezone()` with no explicit `tz=`, resolving via the OS's own tzdata for whichever specific date is being converted — never a fixed offset). Every renderer/filter in this package that shows or compares a time or a day calls this ONE function rather than slicing the raw ISO string itself (the pre-2026-09-04 approach, which showed UTC everywhere — verified: the same instant read 18:16:02 in `reqs`, UTC, against 20:16:02 in the proxy pane, local). Returns `None` for an empty/unparseable string rather than raising; every caller already had a `"?"`/drop-the-session fallback for that case. `load_last_request` (since 2026-09-03) also skips a zero-tool non-haiku line — the same sidecar shape `timeline._is_sidecar` excludes — after parsing it, since telling it apart from a real conversation line needs the parsed payload (see Gotchas).
**Reads:** `_original` (byte ranges only, never whole-file) and any small stream line by line.
**Writes:** Nothing.
**Called by:** `discovery.py` (`filter_sessions`' day window, since 2026-09-04, plus `infer_family`/`iter_jsonl` as before), `timeline.py`, `render.py` (`fmt_timestamp`/`_clock`/`_window_date`, since 2026-09-04), `usage.py` (`_epoch_from_iso`, since 2026-09-04, delegates to it entirely).
**Calls out:** stdlib only (`json`, `re`, `datetime`, `pathlib`).

---

### timeline.py (685 LOC)

**Purpose:** Turn-row construction for one payload, `iter_block_texts` (the block-text generator `search` builds on — since 2026-09-04 its yielded dict also carries `chars`, read off the same block field `build_turns`/`full_turn` already use, so a search hit reports the same chars value `msgs`/`expand` show for that block rather than re-measuring `text`), single-turn full extraction (`full_turn`, what `expand` dumps), request-boundary derivation from the `_forwarded` delta stream, `build_turn_times` (turn → timestamp of the request that first carried it), `request_markers` (boundaries → `{msg_index: {number, timestamp, refires, flow_id, sys_lines, tool_lines}}`, what `msgs` draws its REQ separators AND their sys/tool delta lines from — `flow_id` is what `usage.build_usage_by_flow` keys its CR/CC map by), `request_numbers_by_flow` (boundaries → `{flow_id: REQ number}`, what `overlay` uses to name the request behind a strip), and `load_timeline` as the one call that assembles everything a render needs. Both numbering consumers share `_running_request_numbers`, so the overlay can never drift from the number `msgs` prints. `request_boundaries` (since 2026-09-03) skips a `_is_sidecar` entry — `counts.tools == 0` on a `forwarded_delta` line — entirely, before touching `prev_count` or the sys/tool state, so a sidecar call multiplexed into the family bucket seeds no REQ, no restart and no sys/tool delta comparison (see Gotchas for what this fixed). `request_markers` groups boundaries by the msg index they open and takes the LAST of each group as the owner — within a group every member shares one `prev_count`, so only the last can have raised `message_count`, which makes it the request that actually added those msgs; the earlier members are re-fires and are counted, not listed — and it is also the ONLY member whose `sys_lines`/`tool_lines` a re-fire group shows. `request_boundaries` also computes, per boundary, `sys_lines`/`tool_lines` for that request's own `system_delta`/`tools_delta`, split into two purpose-built functions because the two carry different identities: `_sys_lines` stays INDEX-based (a system block has no name) — a family's first request lists every block untagged, a later request compares each index's CONTENT (`_delta_hash`, imported from `src/proxy/logging.py` — the exact normalisation the proxy itself uses, cache_control stripped) against a running `sys_hash_by_index` map, tagging `"changed"` (index seen before, hash differs), `"new"` (index never seen), or dropping the line entirely (hash unchanged — a write-side artifact, see Gotchas). `_tool_lines` (since 2026-09-03, third revision) is NAME-based instead: removing one tool from the middle of the list renumbers every tool after it, so an index-based comparison could not tell the removal from its shifted neighbours — every renumbered slot showed `changed` even though only the removed tool's content was actually gone (`skill-help_1788343931` REQ 196: `SendFeedback` removed, `Skill`/`Write` merely renumbered into its wake). `_tool_lines` tracks `name_by_index` (the FULL current index→name map) and `hash_by_name` (content hash per name), both threaded through the walk; a removal is inferred as a pure set difference — names active before this request minus names active after — and prints `"removed"` with no chars at all, while an index whose new occupant is the SAME name with the SAME hash (just shifted) prints nothing. See DOCS.md's Gotchas for the exact removal-inference rule and its one known blind spot. System index 0 — the per-request billing header, `_BILLING_HEADER_SYS_INDEX` — is dropped on every request but the first regardless of its hash (see `process-docs/cache/`: it changes by construction and never invalidates the cache). Chars are the FORWARDED wire size: `_system_block_chars` reads a system block's `text` length, `_tool_chars` is `len(json.dumps(tool))` (default separators) — the tool's actual wire serialisation. `load_timeline` returns `entry`, `family`, `line_bytes` and `haiku_lines_skipped` without readers today; `session`, `payload`, `turns`, `turn_times` and — since `msgs` grew separators — `boundaries` all have them. **`request_msg_range`/`resolve_req_range` (2026-09-04, for `msgs --req`):** invert `request_markers`' `{msg_index: marker}` into `{number: [msg_indices]}` and resolve a REQ number range into the `[start, end]` msg-index pair `render_msgs` already knows how to render — `start` is `req_from`'s own msg index, `end` is the msg index right before the next marker (by msg-index order) after `req_to`'s own, or the session's last msg index when `req_to`'s group is the last one. Raises `UnknownRequestNumberError` when a number names no marker, and `AmbiguousRequestNumberError` when it names MORE than one — proven possible even without a restart (see Gotchas): a re-fire that adds no NEW msg opens its own group (a `start_index` no earlier group used) but the running number counter does not advance for a non-adding boundary, so that group's owner is assigned the SAME number as the group before it. **`turn_openers`/`_is_turn_opener`/`_turn_preview`/`build_turn_rows` (2026-09-08, for `turns`):** a turn opener is a `user`-role turn carrying a `text`-type block and no `tool_result`-type block (`_is_turn_opener`) — a str-content pseudo-block (`system-reminder`, `task-notification`, etc., see `build_turns`) never carries the literal type `"text"`, so it is excluded for free. `_turn_preview` reads the LAST `text`-type block of the opener, not the first — a spawn prompt's leading `<system-reminder>`-wrapped block would otherwise become the preview instead of the actual prompt (verified: the only multi-text-block opener in either ground-truth session this was checked against). `build_turn_rows` and (2026-09-09) `build_turn_requests` both draw their turn assignment from a shared `_group_markers_by_turn(turns, boundaries)` — returning `(markers, openers, groups)`, `groups[i]` the sorted msg-index keys belonging to turn `i+1` — split out specifically so the two functions can never disagree about which REQ belongs to which turn. The assignment rule itself is `bisect.bisect_right(openers, marker["message_count"] - 1)` — the count of openers already contained in THAT REQUEST'S OWN sent payload — deliberately NOT the marker's own msg-index dict key (its `start_index`, the smallest index its send first reveals): see Gotchas for the exact case (a request whose send bundles the previous turn's idle text reply together with the next turn's new prompt) where the two disagree, found and corrected during this feature's own verification against real ground truth. `build_turn_rows`' turn's requests are then summed against `times_by_flow` (`usage.build_request_times_by_flow`'s `{flow_id: (stream_end_iso, output_tokens)}`) into duration (last stream-end minus first send), model time (sum of each request's own stream time), tool time (sum of the gaps between one request's stream end and the next's send — the LAST request of a turn contributes none) and summed tokens — ALL FOUR collapse to `None` together the moment any one request in the turn fails to resolve (missing flow, unparseable timestamp), never a partial sum; request count and the first request's own send timestamp print regardless, since they need no transcript join. **`build_turn_requests`/`_tool_use_names`/`_tool_use_name_from_label` (2026-09-09, Milestone 2, for `turns <session> N`):** one row per REQ of turn `N` (raises `UnknownTurnNumberError` for `N` outside `1..len(openers)`) — unlike the aggregate row, model_seconds/tool_seconds/tokens resolve INDEPENDENTLY per request (no sum to protect from a partial, so a request missing only its token count still shows model/tool seconds). `tool_seconds` is the SEND time of the request immediately AFTER this one (in the WHOLE session's msg-index order, `request_markers`' own `timestamp` — no join needed for that half) minus this request's OWN stream-end time, deliberately left unresolved for the turn's OWN LAST request even when a later turn's own first request exists and would otherwise supply a next-send time (mirrors `build_turn_rows`' "last request contributes no tool time", same `?` symbol as a genuine join failure — a reader digging into a slow turn needs "no number" more than which of the two reasons produced it). `tool_names` reads `_tool_use_names(turns, this request's own message_count, the NEXT request's message_count)` — the msg range that request's OWN reply occupies — via `_tool_use_name_from_label` (`"tool_use[Name]"` → `"Name"`, the SAME label `timeline._block_label` already produces for a tool_use block, parsed rather than re-derived). Deliberately the NEXT request GLOBALLY, not bounded to this turn: a reply is a real thing regardless of which turn the FOLLOWING request later gets assigned to (the exact M1 finding — an idle text reply can be bundled into the next turn's own opening request) — verified on `reldist-power`: REQ77 (turn 1's own idle text reply, ending the turn) correctly reads `tool_names == []`, a text-only reply, not "?".
**Reads:** The parsed last-request payload; the session's `_forwarded.jsonl`.
**Writes:** Nothing — returns row lists, a generator, and one data dict.
**Called by:** `__main__.py`, `search.py`, `render.py` (`_system_block_chars`/`_tool_chars`, since 2026-09-04 — the ORIGINAL-size lookups a sys/tool delta line's leading chars now use, see `render.py`'s Purpose).
**Calls out:** `src/proxy/message_summary.py` (`_summarize_message` — imported, not copied), `src/proxy/logging.py` (`_delta_hash`, since 2026-09-03 — the exact content-hash normalisation the proxy itself uses, reused rather than re-implemented so a read-side "changed" decision can never disagree with what the proxy considers a real change), `reader` (`local_datetime`, since 2026-09-08, for `build_turn_rows`' duration arithmetic).

---

### overlay.py (170 LOC, new 2026-08-30, sys/tool overlay added 2026-09-04)

**Purpose:** Builds the strip/inject overlay `expand` AND (since 2026-09-03) `msgs` both read: `{(msg_idx, blk_idx): {stripped, injected, req}}` for one session, by running the session's `_stripped`/`_injected` delta streams through `proxy_display.parser.accumulate_dual_log` — REUSED, not re-implemented, so duallog inherits both the per-coordinate accumulation and the write-side attribution-lag correction (`_lag_msg_idx_by_flow_id`) that credits a trailing-msg total_tokens strip to the request that performed it. `_owners_by_index` resolves each coordinate to its performing flow (lag set wins over the raw recorder), `timeline.request_numbers_by_flow` turns that into the REQ number a reader already sees in `msgs`, and `_texts` normalises the two recorded shapes (stripped = flat strings; injected = `(tag, text)` pairs of which only the `injected` ones are new content, the `equal` parts being the surviving original already on screen). `msgs` uses only the char LENGTHS of `stripped`/`injected` (its delta tail is a size, not a content dump), never the text itself. **`build_sys_tool_overlay(session, family, boundaries)` (2026-09-04)** is a sibling for `msgs`' sys/tool delta lines, returning `(sys_overlay, tools_overlay)` — `sys_overlay` keyed by system index (str), `tools_overlay` keyed by tool name, both `{stripped, injected, req, flow_id}` (tools also carry `whole: bool`, set when the stripped side recorded `{"whole": True}` — a tool the proxy removed ENTIRELY rather than trimming its description, which carries no text to measure at all). It reuses `_texts` for both system's plain span-list shape and a tool's `{"desc": [...]}` shape, and shares a new `_owners_by_flow_key` helper with a refactored `_owners_by_index` (pure refactor — `build_overlay`'s own behavior is unchanged, re-verified against `test_msgs_overlay.py`). **No lag correction for system/tools, unlike messages** — `_diff_system`/`_diff_tools` (`src/proxy/diff_engine.py`) compute a direct same-request diff of that request's own original vs. forwarded halves, never a historical ops chain the way messages' `compose_block` does, so there is no shape-ambiguity window for a strip to land one request late; verified on `opus_monitor_cc_1788464543`'s first real request, where the stripped/injected stream's own system_delta line carries the SAME flow_id `request_boundaries` marks as that request's owner. Calls `accumulate_dual_log` a SECOND time (its own independent accumulator, not shared with `build_overlay`'s) when a caller needs both — an extra ~11 ms per the wire-delta-tail measurement, negligible.
**Reads:** The session's `_stripped.jsonl` and `_injected.jsonl` (delta JSONL, 64-336 KB per session — negligible beside the `_original` stream this package deliberately never parses whole).
**Writes:** Nothing — returns one dict (`build_overlay`) or a 2-tuple of dicts (`build_sys_tool_overlay`).
**Called by:** `__main__.py` (`build_overlay` from `_run_expand` and, since 2026-09-03, `_run_msgs`; `build_sys_tool_overlay` from `_run_msgs` only, since 2026-09-04 — `sessions`/`search`/`expand` still cannot move with either).
**Calls out:** `src/proxy_display/parser.py` (`accumulate_dual_log`), `timeline` (`request_numbers_by_flow`).

---

### usage.py (253 LOC, new 2026-09-03, `_epoch_from_iso` delegated to `reader.local_datetime` 2026-09-04, second join added 2026-09-08)

**Purpose:** Builds `msgs`' `{flow_id: (cache_read_input_tokens, cache_creation_input_tokens)}` map — the CR/CC figures a REQ separator shows for the group owner — and (since 2026-09-08) `turns`' `{flow_id: (stream_end_iso, output_tokens)}` map, TWO different reads of the SAME transcript join. The dual log never carries the response body, so the join runs through THREE stores, the middle one SCOPED rather than store-wide: the session's `_response` stream gives `{flow_id: (request_id, status_code)}`; the first non-haiku boundary whose flow resolves there is the anchor — `boundaries` already excludes a sidecar call (`timeline._is_sidecar`, since 2026-09-03), so the anchor can no longer land on one and search CC's transcript store for an id that was never a conversation turn (see `timeline.py`'s Gotchas: this was the root cause of the "200 status, no transcript record" shortfall three sessions used to show). `_candidate_dirs` resolves the session's STEM alone (via `discovery.stem_identity` and `project_map.build_project_index`) to the one or few `~/.claude/projects/` directories that could possibly hold its transcript — a worker stem's sid8 gives its project's cwd, to which `/.claude/worktrees/<name>` is appended for the worker's OWN cwd; a main stem's label is matched against every known cwd's label (plural on purpose — two projects can share a basename). `_find_transcript` then reads, in Python, only the `.jsonl` files in those directories whose mtime is at or after the session's start, stopping at the first one containing the literal fragment `"requestId":"<id>"` (never a bare id — a tool_result can quote one, which would silently resolve to the wrong transcript). This whole preamble — `_response` → anchor → candidate dirs → transcript path — is `_resolve_session_transcript` (split out 2026-09-08, pure refactor re-verified against `test_msgs_usage.py`), shared by both joins below.
That transcript's `type == "assistant"` records give `{request_id: (cr, cc)}` for `build_usage_by_flow` (`_transcript_usage`, keeping only the FIRST record per id since one API request produces several identical-usage streaming chunks) or `{request_id: [stream_end_iso, output_tokens]}` for `build_request_times_by_flow` (`_transcript_stream_ends`, 2026-09-08) — the timestamp OVERWRITTEN on every sighting (ending on the LAST record's, since CC writes an assistant record at STREAM END, not first byte — verified: a trivial tool's own `tool_result` record follows by ~0.1s; contrast `_response`'s own `responseheaders`-time write, `src/proxy/addon.py` lines 141-161) while `output_tokens` is kept from the FIRST sighting only (observed identical across every record of one requestId in the corpus checked, matching the reference probe this feature was verified against). Both joins then keep only flows whose `_response` status is 200, so an errored owner degrades to no figures rather than a wrong pair; `build_request_times_by_flow` additionally drops a flow whose end timestamp or token count did not resolve, rather than including a half-`None` pair.
**Reads:** The session's `_response.jsonl`; a small, stem-derived subset of `~/.claude/projects/*/*.jsonl` — the project-index walk (delegated to `project_map`) plus, typically, one candidate transcript actually read for content.
**Writes:** Nothing — returns one `{flow_id: (cr, cc)}` dict (`build_usage_by_flow`) or one `{flow_id: (stream_end_iso, output_tokens)}` dict (`build_request_times_by_flow`); `{}` on any missing stream, unresolved anchor, a stem that resolves to no known project directory, no candidate file matching, or an unreadable transcript — the CR/CC case degrades every separator to the value-less pre-feature form, the turns case degrades the affected turn's four numeric columns to `?`.
**Called by:** `__main__.py` (`build_usage_by_flow` from `_run_msgs` always and from `_run_reqs` when `--rebuild`/`--drop` is set; `build_request_times_by_flow` from `_run_turns` only), so `sessions`/`search`/`expand` never read `~/.claude/projects/`.
**Calls out:** `discovery` (`stem_identity`), `project_map` (`build_project_index`, `project_label`), `reader` (`iter_jsonl`; `local_datetime`, since 2026-09-04, for `_epoch_from_iso`). No subprocess and no external search tool — matching is a plain Python `in` check over a handful of already-scoped files, not a store-wide scan.

`_epoch_from_iso` (the epoch used for `_find_transcript`'s mtime cutoff) now delegates entirely to `reader.local_datetime` — audited during the 2026-09-04 UTC-vs-local pass for the same bug class and found ALREADY correct: the original inline parser explicitly appended `"+00:00"` whenever the cleaned string carried no offset of its own, so the common `"...998Z"` shape was already parsed as AWARE UTC, never as a naive-assumed-local datetime. `.timestamp()` on an aware datetime is timezone-independent (the same epoch regardless of which zone the datetime is currently expressed in), so routing through `local_datetime`'s LOCAL-converted result changes nothing about the returned epoch — only removes the duplicate parsing logic.

---

### search.py (38 LOC)

**Purpose:** The literal-substring matcher over one session's deduplicated timeline. Returns one hit per matching (turn, block), each carrying that block's original-payload chars (from `timeline.iter_block_texts`, the same value `msgs`/`expand` show for the block) — since 2026-09-04, no occurrence count and no text snippet; a block with several occurrences of the term still stays exactly one hit.
**Reads:** The parsed payload, streamed block by block via `timeline.iter_block_texts`.
**Writes:** Nothing — returns the hit list.
**Called by:** `__main__.py`.
**Calls out:** `timeline`.

---

### render.py (831 LOC)

**Purpose:** All terminal output. Session table (START / CONTEXT / SESSION plus a count line), `msgs`' request-grouped classifier listing (`render_msgs` — a `── REQ n  HH:MM:SS ──` separator per request group via `_req_separator`, widened to `── REQ n  HH:MM:SS  CR c  CC c ──` when an optional `usage_by_flow` map (from `usage.build_usage_by_flow`, `{flow_id: (cr, cc)}`) resolves the group owner's flow_id — an unresolved or absent map renders the plain pre-feature separator, never a placeholder — then, since 2026-09-03, `_req_delta_lines`: one indented `sys[i]`/`tool[name]` line per entry in that request's `system_delta`/`tools_delta` (the marker's own `sys_lines`/`tool_lines` from `timeline.request_markers`), same indent/column layout as a block sub-line, tagged `  changed`/`  new` for a later request and untagged for the family's first — a marker with neither carries no such lines at all, which is what keeps a delta-free separator byte-identical to the pre-2026-09-03 output; a tool item can also carry `chars is None` (the name-based tool comparison's `"removed"` tag, third revision) — that item skips the numeric chars column entirely, printing `tool[Name]  removed` rather than a size for content that no longer exists — then one `[idx] role type chars` line per msg, a multi-block msg followed by one indented sub-line per block via `_block_sub_lines` (label + chars, chars right-aligned to the same column the parent line uses), and NOTHING else: no totals, no previews; `_governing_marker` gives a mid-group FROM its separator, and its sys/tool lines, back). Since 2026-09-03 a msg or block line the proxy transformed additionally carries `  −N +M → Wc` (chars stripped, chars injected, resulting wire size — real minus sign U+2212, digit-grouped like every other chars figure) via `_delta_tail`, fed by an optional `overlay` param (`overlay.build_overlay`'s `{(msg_idx, blk_idx): {stripped, injected, req}}`, reused from `expand`): `_block_overlay_totals` sums one coordinate's stripped/injected chars (`None` when untouched, which is what keeps an untouched line byte-identical), `_msg_delta_tail` sums those over ALL of a msg's blocks for the parent line, and both add ` by REQ n` only when the transforming request differs from the msg's OWN group (`group_req`, threaded through from `render_msgs`' marker loop) — omitted on the parent line specifically when a msg's touched blocks disagree on which request touched them, since summarizing that with one REQ number would be a guess (unobserved in the corpus: 0 of 1949 transformed msgs, measured).

Since 2026-09-04 a sys/tool line's OWN chars semantics changed to match: `_req_delta_lines` (rewritten) now takes an optional `sys_tool_overlay` (`overlay.build_sys_tool_overlay`'s `(sys_overlay, tools_overlay)`) plus `orig_system`/`orig_tools` (`data["payload"]`'s own system/tools lists, from the last request `load_timeline` already parsed). Each line's leading chars switches from the WIRE size `timeline._sys_lines`/`_tool_lines` compute to the ORIGINAL (client-sent) size, looked up by index (`_sys_index_from_label`) or name (`_tool_name_from_label`) in those lists — falling back to the item's own wire chars whenever the lookup can't resolve, which is what keeps every hand-built test fixture (none of which carries a `"payload"` key) byte-identical to the pre-2026-09-04 output. The ONE unconditional exception is system index 0, the per-request billing header (`_BILLING_HEADER_SYS_INDEX`): it changes on EVERY request by construction, so it is never looked up or overlaid at all — wire chars, no tail, exactly as before this feature, regardless of what the overlay carries for it. `_delta_line` then attaches the SAME `_delta_tail` a msg/block line uses, when `sys_overlay`/`tools_overlay` covers a (non-billing-header) coordinate — corrected same-day (a first cut derived the tail's wire figure `W` from the overlay's recorded stripped/injected TEXT lengths, which are raw description characters and not commensurable with a tool's JSON-encoded chars, printing a wrong wire size for every desc-stripped tool): `W` is now always the MEASURED wire chars (`item["chars"]`, `_tool_lines`/`_sys_lines`' own pre-existing figure — 0 for a whole-stripped tool, which has no wire item at all), and the stripped figure `S` is DERIVED as `original − W + I`, so `_delta_tail`'s own internal arithmetic reconstructs exactly that measured `W` again. A tool the proxy strips WHOLE never appears in the wire `tools_delta` at all (absent both before and after, so `_tool_lines` never lists it), so `_req_delta_lines` additionally synthesizes a standalone `tool[Name]` line for each such overlay entry — restricted to the marker whose OWN `flow_id` the overlay recorded (never guessed from a req NUMBER, which a re-fire could make ambiguous), and skipped silently when the name can't be resolved in `orig_tools`.

Search results (one term line overall, then a `session <stem>` line plus its hit lines per matching session, blank-line separated, with an optional skipped-sessions note — since 2026-09-04 a hit line is `#msg role label  chars` (the block's original-payload chars, digit-grouped like a `msgs` block sub-line, right-aligned across the whole result set the same way `label` already was), replacing the earlier `×N` occurrence count plus a whitespace-collapsed snippet — the chars value alone is enough to tell a small genuine artifact from a large prose hit without opening either), `expand`'s full-content window dump (`▶` anchor mark and an HH:MM:SS request-time column in each msg header, then one `── block i ──` header plus the raw text per block, each block optionally followed by `── stripped by REQ n ──` / `── injected by REQ n ──` sections via `_overlay_lines`), `reqs`' bare per-session REQ listing (2026-09-04, `render_reqs` — one `session <stem>` line, then one `REQ n   HH:MM:SS` line per entry of `timeline.request_markers(boundaries)` sorted by msg index, i.e. the SAME order and numbering `msgs`' own separators use, re-fires and a restart already collapsed the same way since it is the identical dict; a `REQ` number is left-justified in a fixed 4-char field — `_REQ_NUMBER_WIDTH` — directly followed by the clock via `_req_line(marker, tag="", gap_tail="")` (clock, then an optional `  <tag>` for `--merged`, then an optional `  +Nm` for `--gap` — in that order, so a combined `--merged --gap` line reads `REQ n   HH:MM:SS  <tag>  +Nm`), the same narrow-default-with-occasional-jog convention `msgs`' chars column uses; a session with zero requests still gets its `session` header, no REQ lines beneath; blank-line separated like search results, `_skipped_lines` reused verbatim for the trailing note; NO other column, no totals, no CR/CC — UNLESS `gap_minutes` is given (`--gap MINUTES`, same day): `_gap_lines` then replaces the full per-session listing with only the REQs bracketing a consecutive gap of at least that many WHOLE minutes (`total_seconds() // 60`, floored, never rounded, so a boundary case — a gap of precisely N minutes for `--gap N` — is exact), the after-REQ of each qualifying pair carrying `  +{elapsed}m` as its `_req_line` gap tail; a `printed_positions` set is what makes a REQ that is both the end of one qualifying gap and the start of the next print EXACTLY once (a second pair trying to print it "before", tail-less, finds its position already marked from the first pair's "after" role, and skips); a session with zero qualifying pairs — including one with fewer than two requests, where the pairwise walk is simply empty — prints only its `session` header line, same as the zero-requests case; `gap_minutes=None` (the default) reproduces the pre-`--gap` listing byte-for-byte, since `render_reqs` takes the OLD unconditional-loop branch whenever it is unset), `reqs --merged`'s cross-session chronological listing (2026-09-04, `render_reqs_merged` — a `merged <N> sessions` header (`N = len(results)`, the sessions that actually loaded) replaces the per-session `session <stem>` lines entirely; `_merged_entries` flattens EVERY session's markers into one `[(dt, marker, tag), …]` list, `tag` from `_session_tag` (context after the last `/`), sorted by `dt` — the whole point being that the prompt cache hangs on the shared system/tools prefix every worker of a project sends, so the gap that matters is between consecutive requests of ANY session in scope, not within one; the SAME `_bracket_gap_lines` core `_gap_lines` uses handles `--merged --gap` too, just fed the merged, tagged entries instead of one session's untagged ones — which is what makes a within-session gap that a DIFFERENT session's request happens to bridge no longer qualify, and a gap that exists only ACROSS sessions qualify correctly, with zero bridging-specific code: both are just what "pair GLOBAL chronological neighbors" already does), `reqs --rebuild`/`--drop`'s usage-filtered listing (2026-09-04, same day, corrected same day — `_rebuild_drop_qualifies(usage, prev_usage, rebuild, drop)` is the one predicate both flags share: `--rebuild` keeps CC(n) > CR(n), `--drop` keeps CR(n) < CR(n-1) + CC(n-1) — STRICT, so exactly equal does not qualify — read off `prev_usage`, which is `_entries_for_session`'s own PRECOMPUTED same-session predecessor (the 5th tuple element, set while that function is still walking ONE session's markers in msg-index order, before any cross-session merge/sort happens): ALWAYS the request's own session's immediately preceding one, `--merged` or not — `--merged` only changes ORDER and adds the `  <tag>` column, never which predecessor a `--drop` check reads, since the shared prompt-cache prefix it measures is system blocks + tools, never the conversation (see Gotchas — an initial cut instead read `entries[position - 1]` off the merged, cross-session-sorted list, which is wrong). A REQ whose own usage, or, for `--drop`, its predecessor's, never resolved returns `None` — skipped, never shown tail-less. `_rebuild_drop_lines` applies that predicate to every entry when `--gap` is absent; `_rebuild_drop_gap_lines` applies it to exactly the position set `_bracket_gap_positions` (the pure, split-out selection half of `_bracket_gap_lines`, which reads only the `dt` element — cross-session chronological neighbors are exactly what `--gap` wants) already computed for `--gap` alone — "the flags filter the lines --gap would print, before-line included" — each candidate still checked against its OWN precomputed `prev_usage`, not whichever entry the gap pairing happened to bracket it with. Both consumers append `_usage_tail` (`"  CR c  CC c"`, plus `"  −N"` for a `--drop` match) via a new `usage_tail` param on `_req_line`, ordered clock/tag/gap_tail/usage_tail so every flag combination reads as one growing tail. `_entries_for_session`/`_merged_entries` were extended from `(dt, marker, tag)` to `(dt, marker, tag, usage, prev_usage)` to carry this — `usage`/`prev_usage` are `None`, and never read, on every pre-existing code path, which is what keeps the plain and `--gap`-only outputs byte-identical to before this feature; `usage_by_stem` (`__main__.py`'s per-session `usage.build_usage_by_flow` map) is only ever non-`None` when at least one of `--rebuild`/`--drop` is set), `turns`' one-line-per-turn listing (2026-09-08, `render_turns` — `timeline.build_turn_rows`' own rows laid out, the SAME division of labor `render_reqs` already has with `request_markers`: `turn n   HH:MM:SS    DUR  model  MMM  tool   TTT   R reqs    T tok  <preview>`, self-labeled fields rather than a header row, matching `reqs`'/`msgs`' own convention; `_fmt_duration` renders a compact grep-friendly unit — `58s` under a minute, `41m24s` under an hour, `1h05m30s` at or past one, seconds always 2-digit once a coarser unit is present — and `"?"` for an unresolved row's `None`; `_fmt_tokens` digit-groups or prints `"?"`; a row whose four numeric fields are `None` (see `timeline.build_turn_rows`'s Purpose for when) prints `"?"` in all four, never a partial number, while its clock/request-count/preview print normally; no rows at all prints `"no turns found"`), `turns <session> N`'s one-line-per-request detail (2026-09-09, Milestone 2, `render_turn_detail` — `timeline.build_turn_requests`' own rows laid out: `REQ n   HH:MM:SS  model  MMM  tool   TTT   T tok  Name1 Name2`, reusing `_REQ_NUMBER_WIDTH`/`_clock`/`_fmt_duration`/`_fmt_tokens` from the bare listing/`reqs` rather than any new formatter; unlike the aggregate row, EACH of model/tool/tokens prints `"?"` INDEPENDENTLY when its own value is `None` — no all-or-nothing gate, since there is no sum here to protect from a silent partial; the turn's own last request's tool column is `"?"` by design (`build_turn_requests` never computes it, see its own Purpose), rendering identically to a genuine join failure — deliberately, a reader digging into a slow turn needs "no number here" more than which of the two produced it; `tool_names` is space-joined in reply order, empty — not `"?"` — for a text-only reply; no rows at all prints `"no requests found"`), and the char/timestamp formatters. **Every timestamp this module renders is LOCAL time, not UTC (2026-09-04):** `fmt_timestamp` (`sessions`' START column), `_clock` (every REQ separator, every `reqs` line, `expand`'s msg-header clock), and `_window_date` (`expand`'s window-header day) all delegate to `reader.local_datetime` — the ONE shared conversion point — rather than slicing the raw UTC ISO string, which is what they did before (verified regression: the SAME instant read 18:16:02 in `reqs`, UTC, against 20:16:02 in the proxy pane, local). Each still renders `"?"` for an empty/unparseable timestamp, and each keeps its pre-2026-09-04 output WIDTH (`fmt_timestamp` 19 chars, `_clock` 8) — only the VALUES changed. The overlay sections are plain text with no ANSI anywhere — this output is read by agents through pipes, so the labels carry the meaning colour carries in the proxy pane. Rendering only — selection and filtering happen before a list reaches this module.
**Reads:** The dicts produced by `discovery`, `timeline` and `search`.
**Writes:** Nothing — returns strings; `__main__.py` does the `sys.stdout.write`.
**Called by:** `__main__.py`.
**Calls out:** `timeline` (`request_markers`, for `msgs`' REQ separators AND, since 2026-09-04, `reqs`' own listing; `_system_block_chars`/`_tool_chars`, since 2026-09-04, for a sys/tool line's original-chars lookup; `_BILLING_HEADER_SYS_INDEX`, same date, to exempt system index 0 from that lookup); `reader` (`local_datetime`, since 2026-09-04, for every timestamp this module renders).

---

## State

No mutable state — every command is a single pass with no caches, no module-level state, and no
files written anywhere.

Two inputs decide the output, though, and only one of them is the log directory. Worker contexts
are resolved through `~/.claude/projects/` (see `project_map.py`), so a run is reproducible only
while BOTH are unchanged: pruning CC's transcript store flips a worker's context from
`worker/<project>/<name>` to the `worker/<sid8>/<name>` fallback without the dual logs changing at
all. On a live session the output additionally tracks whatever the proxy has appended by then.

## Gotchas

**The last line of `_original` is usually NOT the conversation.** Every session file interleaves
haiku sidecar requests (1 message, ~0.5–2 KB) with the real family. `reader.load_last_request`
walks backwards past them via a 512-byte model sniff and only parses the first non-haiku line. Since
2026-09-03 it also walks past a zero-tool non-haiku line — the OTHER sidecar shape (see below) — but
that check happens AFTER the parse, not via a cheap sniff: `tools` can sit well past the 512-byte
window behind a large system block (measured up to 110 KB ahead of it), so there is no cheap way to
sniff it the way `model` is sniffed. Measured across the whole corpus (2026-09-03): the last
non-haiku line was never a sidecar of either shape in any of the 24 sessions on disk, so this is a
guard against a case that has not happened yet, not a fix for one that has — `skipped` in
`load_last_request`'s return now counts both shapes, though only haiku ever contributes to it today.
The skipped count reaches `load_timeline`'s dict but no command prints it since the `timeline`
header was removed. Any new read path must reuse that function rather than taking the file's final
line.

**Never parse an `_original` line to decide whether you want it.** Lines reach 15 MB. The
top-level key order written by `addon.py` is `timestamp, flow_id, request_id, model, payload`, so
`model` always sits in the first few hundred bytes — that is what makes the sniff cheap and the
4.94 GB file answerable in 0.16 s.

**`_forwarded` is a line-for-line mirror of `_original`, and that is load-bearing.** Verified:
identical line count and identical per-line `(model, message_count)`. The whole 62-session
inventory therefore reads 108 MB of `_forwarded` instead of 14 GB of `_original`. If a future
proxy change breaks that 1:1 alignment, `sessions` silently reports wrong request counts and
`expand`'s time column drifts — re-verify the alignment before relying on it again.

**A message-count regression means CC restarted inside one log id.** Request boundaries before the
restart index into a message list that no longer exists, so `build_turn_times` stops trusting them
(see the `?` gotcha below). Since the `timeline` command was dropped there is no header left that
announces the regression in words — the only surviving signal is the `?` time column. Do not "fix"
the misalignment by clamping indices; it is real.

**`_summarize_message` returns `blocks == []` for string content.** CC delivers `role='system'`
messages as plain strings, so `timeline.build_turns` and `timeline.iter_block_texts` synthesize a
single pseudo-block from `content_preview`. A renderer or matcher that assumes a non-empty block
list will drop every system turn.

**A broken pipe can surface at two places, and catching only the first is not enough.** With
`| head`, EPIPE hits either the `sys.stdout.write` inside `main()` or the interpreter's shutdown
flush after `main()` returned cleanly — which output size lands where is not predictable, so both
must be handled. `__main__.py` flushes INSIDE the guard and, on failure, `dup2`s the stdout fd to
`/dev/null` so the shutdown flush has nothing left that can fail. Dropping either half brings back
`Exception ignored while flushing sys.stdout: BrokenPipeError` on stderr — measured, not
theoretical, and it only reproduces on some sessions.

**The date filter compares LOCAL calendar days, computed via `reader.local_datetime` — not the raw
UTC prefix (changed 2026-09-04).** `filter_sessions` used to slice `YYYY-MM-DD` straight off the
UTC `_forwarded` timestamp and compare lexicographically against `--since`/`--until`, which a
caller types in THEIR OWN local time — so a session started at, say, 23:30 local with a UTC
instant that had already rolled to the next calendar day was silently listed under the WRONG
(UTC) day. Fixed by converting the start timestamp to local time first (`local_datetime`, the one
shared conversion point) and comparing ITS `%Y-%m-%d`. `--since`/`--until` themselves stay plain
`YYYY-MM-DD` strings, still compared lexicographically against that local day — that part remains
"no timezone maths", only the SOURCE day now accounts for the offset. If the timestamp source ever
changes shape or width, `local_datetime` returns `None` and the session is dropped from an active
date filter rather than silently mis-parsed.

**`reqs`' worked example is the canonical before/after proof for the local-time fix.** REQ 1 of
`api_requests_worker_25c51a2e_proxy-tn-wrap_1788545761` carries the UTC instant
`2026-09-04T18:16:02Z`; the proxy pane (already local) showed `20:16:02` for the SAME instant —
`reqs` showed `18:16:02` (UTC, wrong) before this fix, `20:16:02` (matching the pane) after it.
Every one of `msgs`' REQ separators, `expand`'s msg-header clock and window-header day, and
`sessions`' START column moved by the identical offset in the same pass, since all of them
ultimately call `reader.local_datetime`.

**`reqs --gap` shows the REQS BRACKETING a gap, not the gap's own duration listed separately — a
qualifying REQ's tail carries it instead (2026-09-04).** `REQ 206 18:10:11  +89m` means REQ 206
arrived 89 whole minutes after the PREVIOUS printed REQ, not that REQ 206 itself lasted 89
minutes. The threshold is inclusive (`>=`) and computed in WHOLE minutes, floored
(`total_seconds() // 60`, never rounded) — a gap of precisely `N` minutes qualifies for `--gap N`;
one second short of it does not (verified: `dev/dual_log_cli/tests/test_reqs.py`'s
`test_gap_threshold_boundary`, 5400s vs 5399s). A REQ that ends one qualifying gap and starts the
NEXT one (two adjacent gaps both clearing the threshold) prints exactly once, carrying only the
tail from being the END of the first gap — it is never additionally listed tail-less as the START
of the second. A session where NO pair clears the threshold — including one with fewer than two
requests at all — prints only its `session <stem>` header line, with no REQ lines beneath, so a
reader scanning many sessions for gaps sees every session that was CHECKED, not just the ones that
happened to have one. `--gap` composes for free with scope/`--since`/`--until`/`--main`/`--worker`
since it only transforms the per-session REQ list AFTER session selection has already happened.

**`reqs --merged` exists because the prompt cache is shared across a project's workers, not private
to one session (2026-09-04).** The cache hangs on the shared system/tools prefix every worker of a
project sends on its first request; ANY request from ANY session of that project keeps the cache
warm for every OTHER one. Evaluating `--gap` per-session (the default) can therefore both hide a
real cache-cooling gap (session A's own last request was 10 minutes ago, but session B — same
project — sent one 30 seconds ago, so the cache never actually cooled) and manufacture a false one
(A's own two requests are 95 minutes apart, which LOOKS like a qualifying gap in isolation, but B
sent a request 30 minutes into that window — the cache was kept warm the whole time). `--merged`
fixes both by pairing GLOBAL chronological neighbors across every session in scope instead of
per-session ones — no bridging-specific code exists; it is a direct consequence of feeding
`_bracket_gap_lines` the merged, sorted, tagged entry list instead of one session's own. REQ
NUMBERS are still per-session (each session's own `request_markers` numbering restarts at 1), so a
merged listing can show the same number more than once for DIFFERENT sessions — the `  <tag>` on
every line (context after the last `/`) is what disambiguates them, not the number.

**`reqs --rebuild`/`--drop` skip a REQ under either flag whenever the usage they need does not
resolve — never fall back to a tail-less line.** `--rebuild` only needs the REQ's OWN usage;
`--drop` also needs its PREDECESSOR's, so a REQ right after one whose transcript join failed can
never qualify for `--drop` even if its own usage resolves fine — there is no way to compute the
CR(n-1)+CC(n-1) side of the comparison without it. Both flags read the exact SAME `usage_by_flow`
shape `msgs`' own CR/CC separator uses (`usage.build_usage_by_flow`), so anything that makes a
`msgs` separator go tail-less (missing `_response` stream, unresolved project directory, no
candidate transcript, non-200 status — see `usage.py`'s own Gotchas) makes the corresponding `reqs`
line disappear under `--rebuild`/`--drop` too, for the identical reason.

**`--drop`'s "previous request" is ALWAYS the SAME session's own previous REQ, even under
`--merged` (corrected 2026-09-04, second pass).** The prompt cache's shared prefix is system blocks
+ tools, never the conversation itself — comparing session A's CR against session B's CR+CC answers
no real question about either one's cache health. `--merged` changes ORDER (chronological
interleaving across sessions) and adds the `  <tag>` column; it does NOT change what "previous
request" means for `--drop`. `_entries_for_session` enforces this by PRECOMPUTING each entry's
`prev_usage` while still walking one session in isolation (msg-index order), before
`_merged_entries` ever flattens/sorts across sessions — so a session's own REQ 1 (whose precomputed
`prev_usage` is `None`) never qualifies for `--drop` regardless of where the chronological merge
places it, and every OTHER REQ is always compared against ITS OWN session's immediately preceding
request, never a different session's, even when that different session's request is chronologically
closer. An initial cut of this feature got this wrong — it read `entries[position - 1]` off the
merged, globally-sorted list, so a session's REQ 1 landing anywhere but the merge's literal first
position WAS treated as having a (wrong, cross-session) predecessor; caught by inspecting a real
`--merged --drop` run (`REQ 1 capture-crosssession  ...  −648,915`, a shortfall computed against
`duallog-search-chars`' totals, not `capture-crosssession`'s own). `--gap` is unaffected and keeps
using cross-session chronological neighbors (`_bracket_gap_positions` reads only `entries[i][0]`,
the timestamp) — gap health and drop health are different questions, one about elapsed time across
the whole project, the other about one session's own conversation continuity.

**`--drop`'s boundary is STRICT (`<`), not `<=` — deliberately the opposite convention from
`--gap`'s inclusive `>=`.** `--gap` asks "did enough time pass" (more is a stronger match, so the
threshold itself qualifies); `--drop` asks "was the previous cache NOT fully read back" (exactly
CR(n-1)+CC(n-1) means every one of those tokens WAS read again, i.e. nothing dropped) — so an exact
match is the one value that must NOT qualify. Verified in `dev/dual_log_cli/tests/test_reqs.py`'s
`test_drop_boundary_exact_equal_does_not_qualify`.

**`reqs --rebuild`/`--drop` are the only `reqs` flags that touch `~/.claude/projects/` at all.**
`_run_reqs` builds the per-session `usage_by_stem` map ONLY when `args.rebuild or args.drop` — a
plain `reqs`, `reqs --gap`, or `reqs --merged` run does zero transcript-store I/O, same as before
either flag existed. Do not move that `build_usage_by_flow` call earlier in `_run_reqs` "for
simplicity"; it would make every `reqs` invocation pay the join cost even when nothing reads it.

**The two `sessions` filters treat a missing start timestamp differently, on purpose.** A DATE
filter drops such a session — it cannot be placed on a calendar. A CONTEXT filter keeps it, because
its context is known either way. Collapsing both into one "skip incomplete sessions" rule would
silently hide sessions from a context query.

**The context filter matches the RENDERED context value, family prefix included.** That is what
makes `opus/` and `worker/` usable as selectors, and they partition the corpus exactly (measured:
31 + 30 = 61). Matching only the name part would break both.

**A worker's project label must be spelled exactly like the main sessions' label, or the whole
point is lost.** Main stems carry a sanitised label (`opus_gh_cli_…`, `opus_monitor_cc_…`), so
`project_map.project_label()` applies the same rule to the resolved path — basename with `-`
collapsed to `_`. That is what lets ONE filter term (`websearch`) return a project's main sessions
AND its workers. Change either side's spelling and they silently stop meeting.

**The proxy hashes the MAIN project path, never the worktree.** Workers of one project therefore
share a single `sid8` (measured: 9 websearch workers all on `52fce57c`). The map does contain
worktree paths too — 157 of 166 entries — but those ids never appear in a worker stem, and there
are zero hash collisions across all 166 paths. Do not "fix" the map by filtering worktrees out; it
costs nothing and would only remove a harmless superset. Related near-miss: `tmux_launcher.py`
hashes the NORMALISED path, so its `monitor_cc_<hash8>` session names are not interchangeable with
these ids.

**A search hit is one (turn, block) pair, never one occurrence.** A block containing the term N
times still stays one hit — that granularity is a contract, not a formatting detail, and it did not
change with the hit-line redesign below. Before 2026-09-04 the occurrence count was the only
visible trace of N, printed as a `×N` marker; since 2026-09-04 the hit line carries no occurrence
count at all (`find_matches` no longer even computes N, using a plain `in` test instead of
`str.count`), so N is no longer observable anywhere in `search` output — only the fact that the
block matched, and its chars.

**A search hit line is an eyeball filter for choosing what to `expand`, not a text preview
(redesigned 2026-09-04).** The line dropped its `×N` occurrence marker and its whitespace-collapsed
context snippet (`search.py`'s old `_snippet`/`SNIPPET_RADIUS`) in favor of the block's
original-payload chars — the exact value `block.get("chars", 0)` that `timeline.build_turns`/
`full_turn` already read for `msgs`/`expand`, now also threaded through `iter_block_texts`. The
motivating case: searching a literal like `undefined` across sessions returns dozens of hits, almost
all of them prose mentioning the word; a genuine artifact (the literal string used AS a value) sits
in a block whose chars are implausibly small for its label (e.g. a 9-char `assistant text` block) —
visible at a glance in the chars column, with nothing to expand or read to notice it. Reverting to a
snippet would restore a preview of arbitrary length instead of a single comparable number, which is
what makes many hits scannable in one screen.

**`expand`'s overlay names the request that PERFORMED the strip, which is not always the request whose `msgs` separator carries the msg.** CC overwrites a mid-conversation index in place, so a msg can arrive with one request and be transformed by a later one: msg 176 of the monitor_cc session sits under `── REQ 61 ──` in `msgs` (that is when it arrived) while `expand` reports `── stripped by REQ 62 ──` (that is who nuked the content CC had put there in the meantime). Both are correct and they answer different questions. The trailing total_tokens case is the opposite trap and is handled: the delta line that RECORDS such a strip belongs to the following request, so a naive reading would credit REQ 63 for what REQ 62 did — `overlay` takes the lag-corrected owner from `proxy_display.parser`'s `_lag_msg_idx_by_flow_id` instead. Verified: 746 overlay coordinates across two sessions, 0 attribution mismatches against `proxy_display`'s own ownership, 524 of them lag-corrected.

**The overlay's direction is INVERTED relative to the proxy pane, because the two read different streams.** The pane reads `_forwarded` (post-strip) and colours in what was removed; duallog reads `_original` (pre-strip), so the block body already IS the original and the `── stripped ──` section repeats the exact text above it whenever the strip was a whole-content nuke. That repetition is not redundancy to optimise away — a partial strip shows only the removed fragment there, and the reader cannot otherwise tell whole from partial.

**The recorded strip text and the displayed block can differ by whitespace, and no gate rejects that.** The accumulator is cumulative last-writer-wins per coordinate, so in principle it could describe content CC later overwrote. Measured over 741 stripped coordinates in two sessions: 670 exact matches, 19 substrings, 52 whitespace-variants (one example differs by a single `\n` in 892 chars, similarity ≥ 0.972), and **0 unrelated**. No coordinate was ever touched by more than one flow. So the overlay is shown unconditionally rather than gated on containment, which would have wrongly dropped those 52.

**`msgs` prints msg lines, their block sub-lines, REQ separators and — since 2026-09-03 — a
separator's sys/tool delta lines, and NOTHING else.** No header, no count line, no previews, no
per-msg time column — an agent pipes it into `grep`/`wc` or reads it whole, and any further
decoration would have to be filtered back out. A multi-block msg line (`3 blocks 3,862c`) is
followed by one indented sub-line per block — `        thinking                2,451c` — carrying
that block's own label and chars, so the aggregated count is legible instead of opaque; a
single-block msg still renders exactly one line. A REQ separator is, since 2026-09-03, itself
sometimes followed by indented `sys[i]`/`tool[name]` lines in the SAME layout — see the delta-line
Gotchas above — so the sub-line indent now belongs to two different things (a msg's blocks, a
separator's delta), distinguished only by which line precedes them; both still fall under
`grep -v '^\['`. Sub-lines are whitespace-indented rather than `[`-prefixed, so `grep '^\['` keeps
selecting msg lines only and both sub-lines and separators fall to `grep -v`. The separator became
part of the contract on 2026-08-30 (it was absent for the command's first hours): every msg line
sits under the `── REQ n  HH:MM:SS ──` line of the request that added it, so
`grep -v '^──' | grep -v '^ '` recovers the original separator-free, sub-line-free listing exactly
— now also delta-line-free, since those are indented the same way. Since 2026-09-03 a separator
additionally carries `CR c  CC c` (the group owner's `cache_read_input_tokens` /
`cache_creation_input_tokens`, joined from CC's own transcript via `usage.build_usage_by_flow`,
scoped to the one or few project directories the session's STEM can resolve to rather than a
store-wide search — see `usage.py`) between the clock and the closing `──` whenever that join
resolves; an unresolved owner (missing `_response` stream, no matching project directory, no
candidate file matching, or a non-200 owner status) keeps the plain pre-2026-09-03 separator rather
than showing a placeholder, so `grep -v '^──'` still recovers the exact same msg/sub-line listing
either way. `msgs <session>` is the whole
session, `msgs <session> F T` an inclusive range, and `msgs <session> F` runs from F to the last
msg. A bad bound exits 2 naming the offending side (`FROM 1417 out of range (0..1416)`,
`TO 2 is before FROM 5`). A NEGATIVE bound needs a `--` separator (`msgs <s> -- -1`), else argparse
reads it as a flag — the exit code is 2 either way.

**`msgs`' chars column is the ORIGINAL payload's size; the delta tail is what tells you the wire
size (added 2026-09-03).** A msg or block the proxy stripped from/injected into carries an extra
`  −N +M → Wc` after its chars (`−` is U+2212, not a hyphen) — `N` chars removed, `M` chars added,
`W = chars − N + M` the size that actually reached the API. Untouched lines get nothing, which is
what keeps them byte-identical to the pre-2026-09-03 output; a session whose `_stripped`/`_injected`
streams are missing degrades the same way (no tails at all), not an error. A multi-block msg's
parent line sums N/M over every block the overlay touched and measures W against the PARENT's own
chars value, not the sum of the blocks' original chars — the two coincide in every case observed,
but the parent line's own arithmetic (chars shown minus N plus M equals W shown) is what is
guaranteed, not a cross-check against the sub-lines. `by REQ n` — reusing `expand`'s attribution —
is appended only when that request differs from the msg's own group, and is dropped on the PARENT
line specifically (never the sub-lines) when a msg's touched blocks disagree on which request
touched them; measured zero such msgs across the whole corpus (0 of 1949), so the omission has
never actually fired, but the parent line still must not guess if it ever does. Measured fidelity of
the arithmetic itself against the FORWARDED (wire) payload's real block chars: 2001 of 2003
transformed coordinates matched exactly; the 2 that did not are the same known effect as the
recorded-strip-text-vs-displayed-block whitespace/staleness gap `expand`'s overlay Gotcha already
documents, not a new one.

**A FROM landing mid-group still prints that group's separator, and it is not the group's own
first line.** `_governing_marker` falls back to the nearest request opening at or before the first
printed msg, so `msgs <s> 178 178` shows `── REQ 60 ──` even though REQ 60's group starts at 176.
Only the FIRST printed msg gets that fallback; every later separator appears at its group's real
start. Without it a mid-group range would print msgs under no request at all, which is the one
thing the separator exists to prevent.

**`msgs`' REQ numbers match the proxy pane's `#N` for the same session — by construction, not by
luck.** The number counts only requests that ADDED msgs, which is exactly the pane's rule
(`format.py` numbers `#N` on `messages_added > 0` and renders a re-fire as `#N.M` without advancing
N). Measured: 971 of 971 requests across three sessions agree on number, timestamp AND message
count simultaneously. `timeline.request_boundaries`' own `request_no` does NOT match — it counts
every forwarded line MINUS sidecars, so the 3 re-fires in the gh_cli session push it out of step on
223 of 482 requests. One divergence is possible but unexercised by any recorded session: a session
mixing model families (these boundaries keep only the last request's family). Measured at zero
occurrences; if it appears, the numbers drift from there on. The sibling divergence this Gotcha used
to name — a zero-tool non-haiku sidecar landing in the SAME family bucket as the real conversation —
IS exercised (see the `_is_sidecar` Gotcha below) and was fixed 2026-09-03, not merely documented:
`request_boundaries` now excludes it, the same way it always excluded haiku.

**A zero-tool non-haiku line is a sidecar, not a conversation turn, and `_is_sidecar` excludes it
everywhere a REQ is derived (2026-09-03).** `rag-chunking_1788333660` interleaves a second,
structurally distinct sonnet call every few requests — system prompt "You are a security monitor
for autonomous AI coding agents…", `tools == 0`, always exactly 1 message — that `infer_family`
cannot tell apart from the real conversation, since both share the plain model name
`claude-sonnet-5`. Before the fix this fabricated 58 spurious restarts in that session alone (its
own `message_count == 1` regressing against the real conversation's growing count), and was the
root cause — confirmed by content hash, not merely correlated — of the "200 status, no transcript
record" `_response` join shortfall three sessions showed in the 2026-09-03 usage-join work
(`rag-chunking_1788333660`, `opus_jobscraper_1788347399`, `opus_monitor_cc_1788342698`): the
sidecar's own request id genuinely never appears in CC's transcript, because it is not a
conversation turn, so `usage.build_usage_by_flow`'s anchor search could land on it and fail to find
ANY transcript for the whole session. `request_boundaries` now skips a sidecar entry entirely,
before it can touch `prev_count` or the sys/tool hash maps — it seeds no REQ, no restart, no turn
time and no sys/tool delta comparison, in EITHER direction (it neither becomes a boundary itself nor
pollutes the one after it). `discovery.build_session` applies the identical exclusion to
`requests`/`requests_main`/`messages`, so the inventory's request count means the same thing. In the
two opus sessions above the sidecar's model (`claude-sonnet-5`) was already a DIFFERENT family from
the real conversation's (`claude-fable-5-1` → `opus`), so the family filter alone already dropped it
there — `rag-chunking` was the one session where both shared `sonnet` and the sidecar actually
reached the boundary list. `_is_sidecar` is applied regardless, in both sessions, since relying on
family divergence would silently break the moment a sidecar and its conversation ever DO share a
family — which is exactly what `rag-chunking` already does.

**Excluding the sidecar from `request_boundaries` was necessary but not sufficient — the sys/tool
delta STILL showed spurious `changed`/`new` tags for content that never moved, and the real cause
lives in `src/proxy` (2026-09-03, second pass).** `src/proxy/addon.py` keeps one
`prev_delta_hashes_by_model` state dict, keyed by `model_family` — the SAME family bucket
`infer_family` reproduces read-side — and passes the matching entry into
`src/proxy/logging.py`'s `_build_forwarded_delta` to compute `system_delta`/`tools_delta`. Keyed by
model family, not by "is this a conversation turn", so after each interleaved sidecar call, the NEXT real
conversation request gets diffed on the WRITE side against the sidecar's own system/tools, and every
real block comes back looking changed even though its content never moved (verified: hashed
`rag-chunking_1788333660`'s REQ 2 tools against REQ 1's — all 6 byte-identical, yet the raw
`tools_delta` still names all 6). Excluding the sidecar from the boundary WALK (first pass) fixed
which request a delta gets attributed to, but the delta dict itself still carried that write-side
noise. `_sys_lines`/`_tool_lines` now close the other half read-side: `sys_hash_by_index` (system) and
`hash_by_name` (tools, see the name-based Gotcha below) hold the CONTENT hash last seen across REAL
requests only, via `_delta_hash` — imported from `src/proxy/logging.py`, the exact same normalisation
the write side uses (cache_control stripped), so a hash match here is not a coincidence, it is the
same equality test the proxy itself would apply if it were diffing against the right previous
request. An index (system) or name (tools) present in the raw delta whose hash MATCHES what is
stored is dropped — no line, no tag — rather than shown as `changed`; only a genuine content
difference (or something never seen before) produces a line. This is a read-side workaround for a
write-side bug in `src/proxy` (`prev_delta_hashes_by_model` should key on conversation identity, not
bare model name); fixing it there is out of this package's scope and stays a follow-up for the
`proxy` area — do not "fix" it here a second time by touching `src/proxy`.

**Tool comparison is NAME-based, not index-based, because a removal renumbers every tool after it
(2026-09-03, third revision).** `skill-help_1788343931` REQ 196 showed why index comparison is not
enough even after the write-side fix above: `SendFeedback` left the 6-tool list (`counts.tools`
6→5), and every tool after it shifted down one INDEX with its own content completely unchanged —
`Skill` moved index 4→3, `Write` moved 5→4. The proxy's delta is computed per POSITION, so both
renumbered slots legitimately differ from what used to sit there and both land in `tools_delta`;
index-based comparison had no way to tell that apart from a real edit, and printed `tool[Skill]
changed` / `tool[Write] changed` for two tools whose definitions never moved. `_tool_lines` tracks
`name_by_index` — the FULL current index→name map, not just the indices a given request's delta
touches — and `hash_by_name` — content hash per NAME. A removal is inferred as a set difference:
the names active BEFORE this request (`name_by_index`'s values, snapshotted before the update) minus
the names active AFTER (every valid index `0..counts.tools-1`, taken from the delta where touched,
carried forward from the old map otherwise). A name in that difference prints `tool[Name]  removed`
— no chars, because there is no current content to size. An index whose new occupant is a name that
was ALREADY active with the SAME hash (only its position moved) prints nothing at all. The blind
spot: this is a set difference over NAMES, not a trace of which specific edit happened, so it cannot
distinguish "tool X removed" from "tool X removed AND a different tool of a name already present
elsewhere was added in the SAME request" — both would show only the net membership change. Not
observed in the corpus (that needs two tool-list edits landing in one API call, which never happens
in 24 sessions swept), so it is documented rather than defended against.

**A re-fire leaves its only trace on the separator.** A request that re-sent the same message list
added no msg, so it opens no group of its own; it is folded into the next separator as
`(+1 re-fire)`. Measured: 3 in 1417 msgs on the gh_cli session, 0 in the other two. Drop that
suffix and a re-fire becomes completely invisible in this view — the pane still shows it as a
`#N.M` row.

**A trailing, never-completed re-fire is the ONE exception — it DOES open its own group, carrying
a DUPLICATE REQ number (found 2026-09-04, building `msgs --req`).** The re-fire rule above holds
whenever a later boundary at the SAME `start_index` eventually adds the msgs (the normal case,
`positions[-1]` in that group is the adding one). But if a re-fire is the very LAST boundary at a
NEW `start_index` no earlier group used — nothing after it ever adds those msgs, because the
session simply ends there — it becomes the owner of ITS OWN group by definition (`positions[-1]`
with no other member), yet `_running_request_numbers`' counter never advanced for it (it never
added), so `numbers[owner]` is whatever the PREVIOUS group's number already was. Two DIFFERENT
`markers` keys (msg indices) end up carrying the SAME number. Reproduced synthetically, no restart
needed: `f0` opens msg 0, adds 2 msgs (REQ 1); `f1` opens msg 2 with `message_count` equal to its
own `start_index` (a re-fire, adds nothing) — `markers` ends up `{0: {number: 1}, 2: {number: 1}}`.
A genuine restart can produce the identical symptom when the restarted boundary itself adds
nothing. `timeline.request_msg_range` detects this and raises `AmbiguousRequestNumberError` rather
than silently resolving `--req 1` to either msg index — see that function's own Gotcha-style
comment and `dev/dual_log_cli/tests/test_msgs_req_range.py`'s `test_duplicate_req_number_raises`.

**A separator's sys/tool lines name the OWNER boundary's delta, never the group's — a re-fire's own
delta is discarded.** `request_markers` already picks the LAST boundary of a group as the owner for
timestamp/usage; since 2026-09-03 its `sys_lines`/`tool_lines` come from that same boundary. If an
earlier member of the group changed a system block or tool that the owner did not touch again,
that change never surfaces in `msgs` — only in the raw `_forwarded` stream. This mirrors the
existing re-fire trace-loss above, not a new gap.

**System block 0 — the per-request billing header — is excluded from the changed/new comparison on
every request but the first, by design (see `process-docs/cache/`).** It is a hash plus the
previous request id, so it differs on literally every request and would otherwise show `sys[0]
… changed` on every single separator, drowning the signal a prompt-cache rebuild actually needs:
a change in a REAL system block or the tool list. `timeline._sys_lines` drops it unconditionally
for a non-first request regardless of what `system_delta` says; the first request still lists it
(untagged, like every other block) because that request has nothing to compare against yet. The
SAME "changes every request" fact is why `render.py`'s original-chars lookup (2026-09-04) also
exempts index 0 unconditionally, on every request including the first: the last request's own
`system[0]` is a DIFFERENT billing header than any other request's, so looking it up as that
request's "original" would print a wrong number (corrected same-day after review: an earlier cut
looked it up like every other index, printing the LAST request's billing-header size — 174c — on
REQ 1's separator, where the wire actually carried 132c). `sys[0]` keeps its wire chars and no
tail, unconditionally, regardless of whether the overlay happens to carry data for it.

**A request with no sys/tool change prints no delta lines at all — this is the common case.** Once
system block 0 is excluded, most requests in a session carry an EMPTY `system_delta`/`tools_delta`
(the system prompt and tool list are set once, near session start, and rarely change again), so
`_req_delta_lines` returns nothing and the separator looks exactly like the pre-2026-09-03 output.
A change here is therefore worth noticing — it is the single most common cause of a prompt-cache
prefix break, which is the reason this feature exists.

**A sys/tool line's chars column is the ORIGINAL (client-sent) size, not the wire size — matching
msg lines exactly (added 2026-09-04).** Before this, `sys[i]`/`tool[Name]` showed the FORWARDED
wire size (post-strip); now the leading chars is looked up in `data["payload"]`'s own
`system`/`tools` lists by index/name (the LAST request's own copy), and the `_delta_tail` tells you
the wire size instead, exactly the same column split `msgs`' msg-line chars/tail already established
on 2026-09-03. This is safe because the ORIGINAL content is verified STABLE for the entire session:
measured across the corpus (`dev/dual_log_cli/probe_sys_tool_original_chars.py`, 2026-09-04) — tool
content by name, 0 mismatches across 45 sessions comparing any earlier request against the last;
system blocks at the only indices ever stripped (1, 2, 3), 0 length/content mismatches across 44
sessions comparing the conversation family's FIRST real request against its LAST. For an untouched
line the number does not move at all (original == wire when nothing was stripped); only a
transformed line's displayed figure actually changes. **System index 0 (the billing header) is the
one UNCONDITIONAL exception** — it changes on every request by construction (see the Gotcha below
about `sys[0]`/`_BILLING_HEADER_SYS_INDEX`), so the last request's copy is never a valid "original"
for any other request's billing header; `_req_delta_lines` skips the lookup AND the overlay for
index 0 outright, leaving it wire chars with no tail, unconditionally.

**The tail's wire figure is always the MEASURED wire chars, never derived from the overlay's
recorded stripped/injected TEXT length — a same-day correction after review caught the first cut
wrong.** The first version derived `W` as `original − (summed stripped text length) + (summed
injected text length)`, exactly mirroring how a MSG/block line's tail works. That mirroring does
not hold for tools: a tool's chars is `len(json.dumps(tool))` (JSON-encoded, including the `name`
and `input_schema` keys, quoting and escaping), while its recorded stripped/injected TEXT is the
raw description SUBSTRING the proxy removed/added — the two units are not commensurable, so the
derived `W` was wrong for every desc-stripped tool (observed on `opus_monitor_cc_1788464543` REQ 1:
`tool[Bash]` printed `→ 1,571c` where the real forwarded wire size was `517c`). Fixed by flipping
which side is measured and which is derived: `W` is now `item["chars"]` — `_tool_lines`/
`_sys_lines`' own PRE-EXISTING wire-chars figure, computed the same way it always was, never
touched by this feature at all — and 0 for a whole-stripped tool (no wire item exists to measure).
`S` is DERIVED as `original − W + I`, so `_delta_tail`'s own internal `chars − S + I` arithmetic
reconstructs exactly that measured `W` again — self-consistent by construction, and correct because
`W` was never a guess to begin with. For SYSTEM blocks the bug never actually showed a wrong number
(a system block's chars IS raw text length, `_system_block_chars` reading `block["text"]` directly,
so the two units happened to already coincide there) — but the measured-`W` rule was applied there
too, uniformly, rather than leaving the coincidence in place uncorrected.

**A tool the proxy strips WHOLE never appeared in `msgs` at all before 2026-09-04 — the wire
`tools_delta` has no trace of it, ever.** 8 tools (`Agent`, `Artifact`, `AskUserQuestion`,
`DeferredToolPlaceholder`, `ReportFindings`, `ScheduleWakeup`, `ToolSearch`, `Workflow`) are
proxy-stripped WHOLE from CC's own tool list on essentially every session (measured: present and
whole-stripped in 42 of the sessions on disk, always the same 8 names). Because a whole-stripped
tool is absent from the FORWARDED tools array both before and after, it is invisible to the
NAME-based `tool_lines` comparison, which can only tag a name PRESENT on the wire. `render.py`
synthesizes a standalone line for each instead, sourced from `overlay.build_sys_tool_overlay`'s
`whole: True` entries, full strip and wire 0 (e.g. `tool[Agent]  3,172c  −3,172 +0 → 0c`). Recorded
ONCE per session, on the conversation family's own FIRST real request in 41 of 42 sessions measured
— the write side dedupes by content hash, and a policy strip's "content" (the bare tool name) never
changes, so it is written once and suppressed forever after. The one exception
(`rag-chunking_1788333660`) is the ALREADY-documented sidecar-interleave write-side artifact (see
the `_is_sidecar` Gotcha above), not a new phenomenon — its interleaved sonnet call resets the
proxy's own hash-dedup state, causing the same whole-strip to be re-recorded on every recovery
request too.

**No lag correction exists for system/tools, unlike the messages total_tokens case — checked, not
assumed.** `_diff_system`/`_diff_tools` (`src/proxy/diff_engine.py`) compute a DIRECT diff of THIS
request's own original vs. forwarded halves every time; unlike `_process_messages_section`'s
`compose_block`, there is no historical ops-accumulation chain and therefore no shape-ambiguity
window for a strip to land on the WRONG request's delta line. Verified on
`opus_monitor_cc_1788464543`'s first real request: the `_stripped`/`_injected` stream's own
`system_delta` line carries the exact same `flow_id` `request_boundaries` marks as that request's
owner (stripped sys 1/2/3 = 57/907/1210 chars, injected 1/39307/1 chars — both streams' first line
for the family, matching the boundary's own `sys_lines` chars exactly). `overlay.build_sys_tool_overlay`
therefore has no `_lag_*` set to consult, unlike `overlay.build_overlay`'s message-level `_owners_by_index`.

**`msgs`' columns are fixed-width, and two real cases exceed them by one character.** The line is
`[{idx:3d}] {role:.4} {type:<20}{chars:>6}`. An index of 1000+ widens the whole line by one
(measured: 417 of 1417 msgs in one session), and a chars value needing 7 characters — `68,021c` —
pushes its own line out by one (12 of 1417, 2 of them overlapping the first case). Right-alignment
means both still read correctly, they just sit one column off their neighbours. Widening the
columns would trade that for permanent extra padding on every short line; the narrow default was
chosen deliberately.

**A block sub-line's chars column is anchored to the PARENT line's chars column, not to a fixed
sub-line width of its own (added 2026-08-31).** `_BLOCK_LABEL_WIDTH` is derived —
`_MSG_PREFIX_WIDTH + _MSG_LABEL_WIDTH - len(_BLOCK_INDENT)` — so that `indent + label field` always
sums to the same offset the parent's `prefix + label field` does, keeping the two chars columns
lined up under an 8-space indent even though the sub-line's own prefix is 4 columns shorter than
the parent's `[idx] role  `. A label wider than that field (a very long tool name) overflows it
exactly like the parent's 20-wide type column does — same documented one-character-or-more jog, not
a bug. `block["label"]` is read as-is from `timeline._block_label` (`tool_use[Bash]`,
`tool_result!err`, …); `render.py` does not recompute it.

**`expand` dumps full content and nothing else, and its bounds default to 0.** A bare
`expand <session> <msg>` prints exactly the anchor msg with every block in full — the old
classifier-rows overview and its 30-row hard floor are gone (2026-08-30), and so is the `--full`
flag that used to select the content dump. `--before`/`--after` are optional, may be 0, and a
negative value exits 2. The caller pays for every dumped character, so widening a window on a
tool_result-heavy stretch costs megabytes of stdout — widen deliberately.

**`expand`'s time column is the REQUEST's time, not a per-message time.** A turn shows when the
request that FIRST carried it was sent — derived by walking `_forwarded`'s `counts.messages` chain,
where turn N belongs to the earliest request whose count exceeds N. Turns that arrived in the same
request therefore share one timestamp, which is why the column typically repeats in threes
(assistant / user / system). It is a send time, not a per-turn duration, and nothing in the dual
logs offers the latter.

**A `?` in the time column means a restart discarded the chain, not that data is missing.**
`build_turn_times` walks only the chain from the LAST restart onward and leaves every turn below
that restart's message count unmapped — the requests that first carried those messages described a
different message list and cannot be walked against the final one. Measured: 766/766 turns mapped
in a restart-free session, 504/506 in the `/clear` session with exactly turns 0 and 1 unmapped.
Do not "fix" it by falling back to the pre-restart requests.

**No view prints `── REQ n ──` markers any more.** `expand`'s overview dropped them 2026-08-29
because it navigates by msg index and a second numbering system is noise there, and the `timeline`
command that owned them was removed 2026-08-30. Request boundaries survive only as data:
`timeline.request_boundaries` feeds `build_turn_times`, so a request's send time still reaches the
reader through `expand`'s HH:MM:SS column. Anything reintroducing markers should first answer which
of the two indices the reader is supposed to follow.

**`--only` matches BLOCK types, not the aggregated message type (revised 2026-08-29).** It used to
compare against the msg's single aggregated type, so a msg labelled `tool_use` was invisible to
`--only thinking` even when it carried a thinking block. That is superseded: a msg is selected when
its role matches and ANY of its blocks matches the type, and a selected msg always shows ALL of its
blocks. Measured on one window: `--only thinking` went from 5 to 11 msgs, the six additions being
assistant msgs aggregated as `tool_use` that carry reasoning; `--only user/text` picked up two msgs
aggregated as `tool_result` and `task-notification` that carry text blocks. Accepted syntax is a
role, a type, or a `role/type` pair, case-insensitive; an unknown token exits 2 naming the accepted
forms rather than silently matching nothing.

**The user-facing unit is the msg, not the turn.** One msg is one API message; its parts are
blocks. Internal identifiers still say `turns` in places (`data["turns"]`, `hit["turn"]`), but no
output string or `--help` text does — that split is intentional, and new output should say msg.

**`--only` never narrows the WINDOW, only what is printed from it.** The `expand` header keeps
stating the full examined range (`msgs 38-41 of 0-1416, anchor #40, 2026-08-29, only user`), so a
filter that hides most of the window is visible in the output rather than silent. A window in which
nothing matches prints `no msg in the window matches --only <spec>` and still exits 0 — an empty
result is a finding, not an error.

**Three commands removed so far, all of them LOUD.** `timeline --turn N [--full]` went 2026-08-29;
`timeline` itself and `expand --full` went 2026-08-30. All three break with argparse exit 2 —
`invalid choice: 'timeline'` and `unrecognized arguments: --full` — because the command and the flag
were deleted rather than reinterpreted. Replacements: `expand <s> <msg>` for a single-msg read,
`search` for finding something across a session, and — since `msgs` arrived the same day — `msgs
<s>` for the whole-session listing the old `timeline` and the old expand overview both used to
serve. `msgs` is narrower than either: no previews, and its block sub-lines (added 2026-08-31) are
label + chars only, never the block content the old `timeline` sub-rows carried. It DOES carry request
markers — since 2026-08-30 they are its default grouping — but they are the compact
`── REQ n  HH:MM:SS ──` form, not the old `timeline` marker with its running msgs total. Contrast
`search`'s argument flip below, which fails silently.

**`search` takes the TERM FIRST, and the old order fails silently.** The 2026-08-29 redesign
flipped `search <session> <term>` to `search <term> [scope]`. Both arguments stay structurally
valid under the new signature, so an old-style call is not rejected — it searches for the stem as
a literal term and scopes by the intended term, printing `no match` with exit 0. Anything that
calls this command (a script, a skill, a habit) has to be updated deliberately; there is no error
to trip over.

**`scope` and `context` are different selectors on purpose.** `sessions <CONTEXT>` matches the
rendered context only; `search <term> <SCOPE>` matches context OR stem, so one argument covers both
"the whole websearch project incl. its workers" and "this one session id". Both live in
`filter_sessions` and are ANDed with the date window.

**An unscoped `search` reconstructs every session, and that is the entire cost.** Measured: 1.42 s
over 61 sessions, unchanged between a common and a rare term — the matching is free, the per-session
last-request reconstruction is not. Scope or date flags are what make it fast, not a cheaper search.

**An empty search term matches nothing, deliberately.** `str.count("")` counts positions, so a
blank needle would report every block of the session as a hit. `find_matches` returns `[]` for it,
and `__main__` rejects a whitespace-only term with exit 2 before that ever matters.

**`reqs` lists EVERY session in scope, unlike `search`'s match-only listing (2026-09-04).**
`search` only appends a session to `results` when `find_matches` actually returned a hit — a
session with zero matches is silently absent from the output. `reqs` has no matcher to condition
on, so every session that LOADS successfully gets its own `session <stem>` line, even one with
zero requests (which still prints the header, no `REQ` lines beneath) — closer to `sessions`'
"show everything in scope" philosophy than to `search`'s. Only a session whose timeline fails to
LOAD is dropped, into the same `skipped` counter and trailing note `search` already has.

**`reqs` pays the full per-session reconstruction cost `search` does, for a much smaller output.**
It calls the same `load_timeline` (parses the last non-haiku `_original` line in full) per session
in scope — there is no cheaper way to learn a session's REQ numbers without also loading its
payload, since `load_timeline` is what resolves `family`, which `request_boundaries` needs to
filter the `_forwarded` stream. An unscoped `reqs` therefore costs the same as an unscoped
`search` (see the Gotcha above) even though it discards `data["payload"]`/`data["turns"]`
entirely and keeps only `data["boundaries"]` — scope or date flags are what make it fast, exactly
as with `search`.

**`turns`' turn assignment cannot use a `request_markers` entry's own msg-index KEY — it must use
that request's OWN `message_count` instead (found and corrected during this feature's own
verification against real ground truth, 2026-09-08).** A `request_markers` dict is keyed by
`start_index`, the SMALLEST msg index a request's send first reveals — but a request that answers
with plain text and goes idle is never itself sent anywhere; that reply only becomes visible
retroactively, bundled into whatever the NEXT api call happens to send. On a real session
(`api_requests_worker_1dda1c81_reldist-power_...`), the request ending turn 1 (a plain-text idle
reply) and the request opening turn 2 (sent after "recap") turned out to be the SAME request in
the `_forwarded` stream — CC batched the idle reply's own bookkeeping together with the "recap"
prompt into one send, whose `start_index` (230) sits BEFORE the "recap" opener's msg index (231)
even though the same request's `message_count` (233) already reaches past it. Grouping by
`start_index` membership in `[opener_N, opener_{N+1})` therefore put this request in turn 1 — one
request too many (78 instead of the verified 77) and 68 extra seconds of duration bleeding across
the idle gap. `build_turn_rows` instead assigns via `bisect_right(openers, message_count - 1)` —
the count of openers ALREADY CONTAINED in that request's own sent payload — which is why
`request_markers` now also carries `message_count`; verified against BOTH ground-truth sessions
down to the exact request count and exact summed output-token totals (see
`process-docs/dual_log_cli/` for this area's own entry on the investigation).

**`turns <session> N`'s per-request `tool_seconds` column shows "?" for TWO different reasons, and
deliberately does not distinguish them (2026-09-09, Milestone 2).** One is a genuine join
failure — this request's own stream-end time never resolved. The other is structural — this
request is the turn's OWN last one, so `build_turn_requests` never even attempts the computation,
by design (mirroring `build_turn_rows`' aggregate "the turn's last request contributes no tool
time"), even when a LATER turn's own first request exists in the session and would otherwise
supply a next-send time to subtract against. Collapsing both into the same `"?"` was a deliberate
simplification — a reader digging into a slow turn via this column needs "there is no number here"
more than which of the two reasons produced it, and introducing a second symbol for a distinction
that changes nothing about what to do next (look at the PREVIOUS request's own tool time instead)
was judged not worth the extra convention. Verified on `reldist-power`: REQ77 (turn 1's own idle
text reply, the request that ends the turn) shows `tool_seconds = "?"` and `tool_names = []` (a
genuine text-only reply, not an unresolved join) even though REQ78 (turn 2's own first request)
exists moments later and sent at `23:10:14` — the exact instant that, if used, would have printed
a bogus multi-minute "tool time" spanning the idle gap between the two turns.

**A turn's per-request tool_use names read the NEXT request's own delta range, not this request's
— easy to get backwards.** `build_turn_requests` looks up `_tool_use_names(turns,
marker["message_count"], next_marker["message_count"])` for request R: R's OWN `message_count` is
where R's REPLY starts (see the Gotcha above — a request's own msg-index range describes what its
SEND already carried, i.e. the PREVIOUS request's reply), so the range bounded by the NEXT
request's `message_count` is what actually contains R's own reply. Verified via a hand-built
fixture in `test_turns.py` where req1's reply (visible only in req2's own delta) carries a
different tool name than req2's own reply (visible in req3's) — swapping the two ranges was caught
immediately, since it would attribute req2's tool call to req1 and vice versa.
