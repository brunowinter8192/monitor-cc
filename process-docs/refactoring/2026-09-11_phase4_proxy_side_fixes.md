# Control-flow integrity fixes, proxy side (refactor phase 4)

Process record for the 9 fallback/duplication-elimination items on the proxy write side
(`src/proxy/`) and proxy read side (`src/proxy_display/`, `src/dual_log_cli/`), classified with the
user under the rule: a branch producing derived output a second way is a fallback and is
eliminated; a branch that refuses and surfaces the failure is a tripwire and stays.

## Baseline harnesses used

Before any edit, ran and recorded: `dev/proxy/pipeline_byte_identity.py` (HASH
`0d0876c7...`, 29 payloads), `dev/proxy_display/render_byte_identity.py` (HASH `5a6344a4...`, 29
entries / 236 expand-state keys), `dev/proxy/test_strip_fix.py` (255/255), `dev/proxy_dual_log/
test_composition_invariant.py` (12/12), all 13 suites under `dev/dual_log_cli/tests/` (each
individually 100% pass, counts recorded per file), `dev/constants/split_byte_identity.py` (HASH
`fa6f42c2...`, pre-deletion 70-name set), `dev/tmux_launcher/argv_byte_identity.py` (HASH
`f3cc235e...`). Also ran, as extra safety since `addon.py` is touched: `dev/proxy/
addon_hook_byte_identity.py` (HASH `ece0e640...`).

The live `src/logs/dual_log/` quartet is gitignored and absent from this worktree; froze one real
quartet (`api_requests_opus_wise2627_1789037301_*`, 29 requests, from the main checkout) to
`/tmp/p4fix_frozen_dual_log/` and pinned every harness to it via its documented env override
(`PROXY_PIPELINE_BYTE_IDENTITY_LOG`, `RENDER_BYTE_IDENTITY_LOG_DIR`,
`ADDON_HOOK_BYTE_IDENTITY_LOG`) — same before/after input for every comparison, per
`dev/panes/DOCS.md`'s and `dev/workers/DOCS.md`'s frozen-copy pattern.

After every item's edit, reran the full set; every hash matched its baseline exactly and every
pass count held. Also ran `dev/proxy/test_role_keyed_rules.py` (26/26) as an unlisted-but-relevant
baseline, since it directly exercises `rules_config.py`'s role-key resolution (item 2) end-to-end
through `apply_modification_rules` — not in Main's harness list but the only real regression
coverage for that specific module.

## Item 1 — one `_infer_model_family`

Canonical home: **`src/proxy/message_summary.py`**, not `addon.py`. `addon.py` runs
`addons = [ProxyAddon()]` at module scope — importing it anywhere just to reuse a pure classifier
function would instantiate a live `ProxyAddon` (six `_resolve_dual_log_file` calls, real
session/worker-context derivation) as an import side effect in `proxy_display` and `dual_log_cli`,
which must stay read-only. `message_summary.py` has zero side effects (imports only `json`) and
was already a shared dependency of `forwarded_parser.py`, making it the safe "writer side, owns
zero side effects" home.

`forwarded_parser.py` and `dual_log_cli/reader.py` now import the one definition instead of
redefining it; every existing caller (`pane.py`, `worker_proxy_pane.py`, `dual_log_accumulator.py`
via `from .forwarded_parser import _infer_model_family`; `discovery.py`/`timeline.py`/
`timeline_boundaries.py` via `from .reader import infer_family`) keeps working unchanged because
the name still resolves from the same module it always imported from — only the definition site
moved. `reader.py` imports it aliased (`_infer_model_family as infer_family`) to keep its own
public name.

The 3 original implementations differed on `None` input: `addon.py`/`forwarded_parser.py` did
`model.lower()` (crashes on `None`), `reader.py` did `(model or "").lower()` (safe). The unified
version uses the safe form — strictly a superset of the old behavior for every input that
previously succeeded (never changes output for a real string), only changes the outcome for an
input that previously raised `AttributeError`.

`dev/` scripts are self-contained by convention (per `dev/dual_log_cli/probe_sys_tool_original_chars.py`'s
own comment) and keep their own local `_infer_family`/`_infer_model_family` copies — not repointed,
per that convention. Repointed only the 2 dev scripts that already imported the src.-side
definition (`dev/proxy_display/render_byte_identity.py`, `dev/proxy_instrumentation/
render_recorded_request.py`, `dev/proxy_instrumentation/p6_no_flow_extra_prepend_probe.py`,
`dev/display/test_hover_map.py`) — no edit needed there, since they import
`_infer_model_family` from `forwarded_parser`, which still exports that name.

Verification: `pipeline_byte_identity.py` and `render_byte_identity.py` both byte-identical
before/after.

## Item 2 — one `is_main_session` predicate

Placed in **`src/proxy/rules_config.py`**, not `addon.py`. `addon.py` imports from `rules.py`;
putting the predicate in `addon.py` and having `rules.py` import it back would create
`addon.py` ↔ `rules.py` cycle. `rules.py` already imports `rules_config.py`
(`_load_system2_rules`), and `bg_escape.py` has no existing dependency on `rules_config.py` in
either direction — both can import from there with zero cycle risk.

**Predicate chosen: `not (worker_context or "").startswith("worker:")`**, matching what
`bg_escape.py` and `rules_config.py` already did (2 of 3 original sites), NOT `rules.py`'s
`worker_context == "main"`. The two forms are equivalent for every value `_derive_worker_context()`
in `addon.py` ever actually produces (`"main"` or `"worker:<name>"`) — they diverge only for
degenerate values (`""`, `None`, a string with no `worker:` prefix) that never occur in
production. Checked every caller that DOES exercise a degenerate value: `dev/proxy/
test_role_keyed_rules.py` explicitly asserts `_load_system2_rules('opus', '', 'main') ==
MAIN_TEXT` and 4 other degenerate-context assertions, ALL expecting the "not worker:" (main)
resolution — i.e. this test already encodes the chosen predicate as correct, not `rules.py`'s
stricter one. `dev/proxy/test_strip_fix.py`'s 255 checks call `apply_modification_rules` with a
default (`""`) `worker_context` in several places but never assert on the main-vs-worker wording
of `_apply_bg_launch_ack_strip`'s output (checked via grep for the main-only phrase "arm another
background timer" — zero matches through the full-pipeline path), so switching `rules.py`'s
predicate for degenerate inputs doesn't touch any asserted behavior there.
`pipeline_byte_identity.py` only ever calls with `'main'`/`'worker:x'`, so it's unaffected by the
edge-case choice either way — its byte-identical result doesn't distinguish between the two
candidate predicates, the `test_role_keyed_rules.py` reasoning above is what justified the choice.

Verification: `test_role_keyed_rules.py` 26/26 (unchanged), `test_strip_fix.py` 255/255
(unchanged), `pipeline_byte_identity.py` byte-identical.

## Item 3 — one log_id resolution from the marker file

Helper `_resolve_log_id(root, session_id)` added to `forwarded_parser.py` (not `parser.py`),
because `forwarded_parser.py` is documented as a leaf that `parser.py` already imports from
(`_proxy_session_id_for_project`) specifically to avoid a `parser.py` ↔ `forwarded_parser.py`
cycle — adding the new shared helper to the existing leaf preserves that direction unchanged.
`parser.py`'s `find_proxy_log_path`, `find_errors_log_path`, `find_response_log_path` and
`forwarded_parser.py`'s own `parse_proxy_log_forwarded` all now call it. The `OSError` swallow that
only `find_proxy_log_path` had (`try: lines = marker_file.read_text(...) except OSError: lines =
[]`) is gone — propagates now, same as the other 3 call sites always did. Demonstrated with a
throwaway `/tmp` probe: chmod 000 a real marker file, called `_resolve_log_id` directly, confirmed
`OSError` (`PermissionError`, a subclass) propagates instead of silently falling back to the
session id.

`src/panes/token_pane.py` (`find_response_log_path`) and `src/panes/warnings_pane.py`
(`find_errors_log_path`, `proxy_session_id_for_project`, `get_proxy_session_start_ts`) both call
these through their own `run_*_loop`'s outer `try/except Exception: log_pane_error(...)` —
confirmed by reading both loops directly, not inferred — so the newly-propagating `OSError` is
caught and logged exactly like every other in-loop exception, never crashes the pane.

Verification: `render_byte_identity.py` byte-identical; a live resolve against 3 real marker files
under the main checkout's `src/logs/` (`.proxy_session_1dda1c81` → `opus_trading_1789144373`, etc.)
matched the pre-edit inline logic's output.

## Item 4 — `get_proxy_session_start_ts`: 24h branch eliminated

Removed only the `time.time() - mtime < 86400` condition; the pre-existing `try/except OSError`
around `marker_file.stat()` (unrelated to the 24h branch, not in Main's item list) stays untouched.
Function now returns the marker mtime whenever the marker file exists and its mtime is readable,
however old; no-marker path (`return time.time()`) unchanged.

`src/panes/warnings_pane.py`'s only consumer: `_monitor_start_ts = get_proxy_session_start_ts(...)
if project_filter else time.time()`, used to filter which historical warnings show. As of
2026-09-11, a stale (>24h) marker now surfaces its real (old) mtime instead of masking it as "now"
— this is the intended behavior change per the item (eliminates the fallback), not a defect.

Verification demonstrated with a throwaway `/tmp` probe: wrote a marker with mtime backdated 25h,
confirmed `get_proxy_session_start_ts` returns that old mtime (not `time.time()`).

## Item 5 — render_sections.py legacy tool path: producer search, verdict DELETED

Grepped every `_stripped_spans` reference in `src/`. It is assigned in exactly one place:
`proxy_pane_shared._attach_overlay_references`, line `entry['_stripped_spans'] =
acc_stripped[family]`. Both `pane.py` (`_refresh_proxy_data`) and `worker_proxy_pane.py` (its
refresh function) call `_attach_overlay_references` — via `_accumulate_dual_logs_and_attach` —
unconditionally on every entry added to `proxy_entries`/`worker_proxy_entries`, immediately after
`extend()`, before any render function ever sees the entry. Traced every path that constructs an
entry dict reaching `format_proxy_block`/`render_tools`: `parse_proxy_log_forwarded` →
`_accumulate_dual_logs_and_attach` (pane.py) and `_parse_forwarded_log` →
`_accumulate_dual_logs_and_attach` (worker_proxy_pane.py) are the only two producers, both attach
unconditionally. `dev/proxy_display/render_byte_identity.py`'s own harness independently calls
`_attach_overlay_references` too. No code path in `src/` builds a `format_proxy_block`-bound entry
without it.

**Verdict: no producer found — deleted.** Removed `_render_tool_legacy`, `_render_legacy_tool_params`,
the `use_dual` parameter from `_render_tool_defs_list`, and the `use_dual`/`else` branches in
`_render_tools_body` (the `entry.get('stripped_unused_tools_names', [])` legacy fallback list).
Scope stayed to exactly the tool-rendering branch named in the item — `render_sections_system.py`'s
own `_stripped_spans` check and `render_sections.py`'s `render_fields_delta`'s own check are
untouched (not named in the item, and not "produces derived output a second way" — they're
early-return guards, not alternate renderers).

Verification: `render_byte_identity.py` byte-identical; `dev/proxy_tool_stripping/tests/
test_whole_stripped_tool_expand.py` (imports `render_tools`, `_render_whole_stripped_tool`
directly per its own DOCS.md-recorded caller relationship) 37/37 unchanged.

## Item 6 — terminal-size defaults eliminated

`proxy_pane_shared._terminal_size` and `ccwrap/wrapper._get_winsize`: removed the `except OSError`
fallback tuple in both; `os.get_terminal_size()`/`fcntl.ioctl(...)` now propagate. Left the unused
`default_lines`/`default_cols` parameters on `_terminal_size` in place rather than also changing
its signature — out of this item's scope, and both call sites (`pane.py`, `worker_proxy_pane.py`)
call it with no arguments regardless. Demonstrated propagation with a `/tmp` probe monkeypatching
`os.get_terminal_size` to raise; confirmed `OSError` reaches the caller.

## Item 7 — log-read OSError handlers become visible

Added `pane_error_log.log_pane_error(<tag>)` as the first statement in each handler, before the
existing `return <unchanged position>` (retry-next-poll semantics unchanged): `dual_log_accumulator.py`'s
`accumulate_original_tools` and `accumulate_dual_log` (tag `'dual_log_accumulator'`),
`forwarded_parser.py`'s `_parse_forwarded_log` and `_lazy_load_messages_forwarded` (tag
`'forwarded_parser'`), `side_logs.py`'s `read_response_log` (tag `'side_logs'`) —
`scan_worker_errors_logs` in the same file was NOT touched, it isn't in the item list. Chose
module-name tags rather than a calling-pane name because these functions are shared by both
`pane.py` and `worker_proxy_pane.py` (plus `dual_log_cli/overlay.py` for `dual_log_accumulator.py`,
explicitly noted as harmless there) and have no way to know which pane is calling — a
module-identity tag distinguishes the log line's origin without threading a new parameter through
every caller, which the item didn't ask for.

Demonstrated all 5 handlers with one throwaway `/tmp` probe: chmod 000 a real file, called each
function directly, confirmed each wrote a traceback to `/tmp/monitor_cc_error.log` tagged with its
module name AND still returned the unchanged position (`0`/`{}`/`[]`/`False` as appropriate) —
retry-next-poll semantics intact.

## Item 8 — dead code removal

`src/utils.py:_iso_to_float` — grepped `src/`, `dev/`, and root `.py` files: zero callers besides
its own definition. Deleted; `datetime` import stays (still used by `format_timestamp`).

`src/constants.py`'s `HOOK_*` cluster (25 names) + `HOOK_EVENT_CATEGORIES` — grepped every one of
the 26 names across `src/` and `dev/`: zero real importers (the only `HOOK_`-prefixed hits
elsewhere, e.g. `hooks/hook_setup.py`'s `_HOOK_TIMEOUT`/`_HOOK_SCRIPTS`, are unrelated local
constants in a different module, confirmed by reading both files). Earlier work recorded under
`process-docs/refactoring/` had investigated moving this cluster to a dedicated `hook_events.py`
and reversed that plan because a module with zero importers would be dead code on arrival — but
that investigation still kept the cluster (as of that date) rather than deleting it. This task's
classifying rule treats a cluster with zero importers and zero live purpose as dead code outright,
so it was deleted rather than kept a second time.
Updated `dev/constants/split_byte_identity.py`'s frozen `_NAMES` list (70 → 44 entries) and its
docstring/comments to match, and got a fresh baseline hash for the new frozen set (this hash is
intentionally NOT equal to the pre-deletion hash — the set of hashed names itself changed, so
byte-identity doesn't apply to this particular harness for this particular item; LOC-drift and
symbol-drift both show 0 findings post-edit, confirming internal consistency).

`src/metadata/` and `src/subagents/` — do not exist in this worktree (sparse checkout; git tracks
no files under either path, and `__pycache__` is gitignored so a fresh worktree never accumulates
it independently). They DO exist as `__pycache__`-only leftovers in the main checkout, outside this
worktree's writable area per the worker isolation rule — no action taken here; this is a filesystem
hygiene item outside git's purview, not something a commit from this worktree can address.

## Item 9 — claude_proxy_start.sh

**(a)** Removed the "old format (no PID line): mtime-only" `else` branch from both liveness checks
(the per-project `MARKER_FILE` guard and the cross-repo `TMP_MARKER` guard) — collapsed
`if -n "$existing_pid"; then ... else ...; fi` to a single combined `if [ -n "$existing_log_id" ] &&
[ -n "$existing_pid" ]; then ... fi` with no else; absent PID now falls through to the
already-initialized `MARKER_IS_STALE=true`/`TMP_IS_STALE=true` default. `dev/proxy/
marker_race_repro.sh` (12/12 passed after the edit) only sources `_proxy_pid_is_live` from the
script via `awk` extraction and keeps its own mirror `_is_stale`, so it doesn't exercise the edited
inline block directly, but confirms the untouched primary-liveness function this block calls is
unaffected.

**(b)** `SESSION_ID` now hashes `NORMALIZED_PROJECT="$(python3 -c 'import os, sys;
print(os.path.normpath(os.path.expanduser(sys.argv[1])))' "$PROJECT")"` instead of `$PROJECT`
directly — byte-for-byte the same normalization `src/tmux_launcher.py:generate_session_name` does
via `os.path.normpath(os.path.expanduser(project_path))`, computed through `python3` rather than
re-implemented in bash, so the two sides can never diverge on a path-normalization edge case again.

Proof (canonical absolute path, no trailing slash, no `~`):
```
canonical: /Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/p4fix-a
BEFORE (unnormalized) md5[:8]: 394da8fb
AFTER  (normalized)   md5[:8]: 394da8fb   -- byte-identical
```
Proof the fix actually closes the gap (trailing-slash path):
```
tmux_launcher.generate_session_name(path)        -> monitor_cc_394da8fb
tmux_launcher.generate_session_name(path + '/')  -> monitor_cc_394da8fb   (same, normpath collapses it)
bash SESSION_ID before this fix, path + '/'      -> 92a32869              (diverged from tmux side)
bash SESSION_ID after this fix,  path + '/'      -> 394da8fb              (now matches tmux side)
```
Existing markers on disk (written under the old, unnormalized hash) keep resolving for any project
whose path was already in normalized form when the marker was created — which is every marker
observed under the main checkout's `src/logs/` (absolute paths, no trailing slash) — since
normalization is a no-op on an already-normalized path.

## Import smoke + full harness re-run (after all 9 items)

All touched modules plus every direct importer named in their DOCS.md `Called by` lines imported
cleanly in one process: `src.proxy.message_summary`, `.addon`, `.rules`, `.rules_config`,
`.bg_escape`, `src.proxy_display.forwarded_parser`, `.parser`, `.dual_log_accumulator`,
`.side_logs`, `.proxy_pane_shared`, `.render_sections`, `.pane`, `.worker_proxy_pane`, `.format`,
`.render_turn`, `.search`, `.__init__`, `src.dual_log_cli.reader`, `.discovery`, `.timeline`,
`.timeline_boundaries`, `.overlay`, `.project_map`, `src.ccwrap.wrapper`, `src.constants`,
`src.utils`, `src.panes.token_pane`, `src.panes.warnings_pane`.

Final full re-run, all green: `pipeline_byte_identity.py` and `render_byte_identity.py`
byte-identical to their pre-edit hashes; `addon_hook_byte_identity.py` byte-identical;
`test_strip_fix.py` 255/255; `test_composition_invariant.py` 12/12; all 13 `dev/dual_log_cli/
tests/` files at their original pass counts; `test_role_keyed_rules.py` 26/26;
`test_whole_stripped_tool_expand.py` 37/37; `argv_byte_identity.py` byte-identical (tmux_launcher.py
itself untouched); `marker_race_repro.sh` 12/12; `docs-drift-check` from the worktree root: 0
LOC-drift, 0 symbol-drift, 16 path-drift findings — identical set (same paths, same line numbers ±1
from an unrelated Gotcha-bullet removal) to a `git stash`-verified pre-edit run, all pointing at
`src/logs/...` or `.claude/worktrees` paths absent from every fresh worktree regardless of this
task's changes.

## 2026-09-11 recap — review follow-ups: 9(b) was incomplete, dead `_terminal_size` params

Main's review of the first commit caught two gaps.

**9(b) was only half-fixed.** The initial pass normalized `SESSION_ID` in
`claude_proxy_start.sh` and confirmed it already matched `tmux_launcher.generate_session_name`,
but missed that `src/proxy_display/forwarded_parser.py:_proxy_session_id_for_project` — the
READ side's own hash of the project path, used by every `parser.py` `find_*_log_path` function and
by `dual_log_cli/project_map.py` — still hashed the raw, unnormalized string. A trailing slash on
`project_filter` (e.g. from a caller that appends `/` before passing it through) would produce a
session id on the read side that never matches the write side's (shell) or the tmux side's
(`generate_session_name`) session id for the same project, even after the first commit's fix —
exactly the 3-way divergence class item 9(b) was meant to close, just on the one call site that
got missed. Fixed by applying the same `os.path.normpath(os.path.expanduser(project_path))`
normalization inside `_proxy_session_id_for_project` itself, matching
`src/workers/worker_selection.py:get_selection_file_path`'s existing identical pattern for the
same reason (worker selection file naming) — this is the third module doing this exact
normalization now, all three byte-for-byte identical in method.

Proof, canonical path (unchanged from the first commit's proof, confirming no regression):
`hashlib.md5(canon).hexdigest()[:8]` before this fix == `_proxy_session_id_for_project(canon)`
after == `394da8fb`. Proof the actual gap is closed: `_proxy_session_id_for_project(canon + '/')`
now also returns `394da8fb` (was `92a32869` before this fix, diverging from
`generate_session_name`'s `394da8fb` for the same trailing-slash input). Reran
`dev/proxy_display/render_byte_identity.py` against the same frozen quartet used throughout this
task — HASH `5a6344a4...`, unchanged from every prior run, since the harness never varies its
project-path input format. `dev/dual_log_cli/tests/test_msgs_usage.py` (13/13) and
`test_project_display.py` (23/23) — the two dev suites that call `_proxy_session_id_for_project`
directly — both still pass; both already pass an absolute, already-normalized path, so the
function's new normalization step is a no-op for their inputs and doesn't need new test coverage.

**Dead `_terminal_size` parameters.** `proxy_pane_shared._terminal_size`'s `default_lines`/
`default_cols` parameters became unused once the first commit removed the `except OSError:
return default_lines, default_cols` branch, but were left in place at the time out of a
minimize-the-diff instinct. Main's review pointed out `p4fix-b` (the sibling worker on the
worker-pane side of this same phase-4 scan) removed the equivalent dead parameters on its own
terminal-size helper, so this was left inconsistent. Dropped both parameters — `_terminal_size()`
now takes no arguments; both call sites (`pane.py:293`, `worker_proxy_pane.py:320`) already called
it with zero arguments, so this is a pure signature cleanup with no caller change needed.
`render_byte_identity.py` and `pipeline_byte_identity.py` rerun, both still byte-identical.

Both fixes committed as `7117049`. `docs-drift-check` after: same 0 LOC-drift / 0 symbol-drift /
16 path-drift (identical pre-existing set) as every prior run in this task.
