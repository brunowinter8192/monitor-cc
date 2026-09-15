# 2026-09: workers window becomes two panes (worker-tokens + worker-proxy), all-workers list deleted

## Trigger

Window 2 ("workers") held two panes: the all-workers list (`worker_pane.py`, mode `workers`) on
the left, `worker-proxy` on the right. With five workers listed and two expanded inline, the list
pane scrolled with noticeable lag and the row highlight drifted against the left-edge cursor
marker (observed 2026-09-02, recorded in `process-docs/proxy_pane_scroll/`).
The user's decision, given up front rather than discovered mid-session: replace the two-pane
window's left side with a single-selected-worker cache tracker — the same tokens/proxy split the
main session already has, one worker at a time — and accept losing the simultaneous all-workers
overview to get it. The switch header becomes the only overview left, so it has to carry per-worker
liveness (status, context-%), not just a bare name. The scroll lag/drift itself was explicitly
OUT of scope for this milestone; a follow-up should check whether the split incidentally removed
it (a single-worker tracker never renders more than one cache tracker's worth of expanded content,
so the five-worker-with-two-expanded case that produced the lag can no longer occur — worth a
quick look before opening a new investigation from scratch).

## Investigation

Read every `.py` file in `src/workers/`, `src/panes/token_pane.py`+DOCS, `src/proxy_display/
worker_proxy_pane.py`+`proxy_pane_shared.py`+DOCS, `src/format/token_format.py`+DOCS,
`src/core/monitor.py`/`modes.py`+DOCS, `src/tmux_launcher.py`, `src/startup.py`, both named
process-docs entries, and all 7 named dev probes, before writing a plan — the same read-first
discipline the 2026-09 module-split entry describes, since this milestone deletes the module that
split created siblings for.

**Established the header's new home by direction, not by feel.** `proxy_display/worker_proxy_pane.py`
already imports FROM `workers` (`find_worker_jsonl`, `list_workers`,
`worker_pane.get_selection_file_path`) — a one-directional dependency. The new worker-switch
header is needed by BOTH the new worker-tokens pane (which has to live in `workers/`, since it
owns worker discovery and is the natural sibling of the deleted list pane) and the existing
worker-proxy pane (in `proxy_display/`). Putting the header in `workers/worker_switch_header.py`
and having `proxy_display` import it keeps the existing direction; the reverse (`workers`
importing from `proxy_display`) would have been new and, per the codebase's own module-boundary
convention, wrong — a function two packages need belongs where the existing dependency already
points, not where it was previously implemented.

**No live tty in this sandbox — build a pty wrapper before trusting any "no live tmux/terminal
needed" probe.** Every one of the 7 required probes' docstring makes that claim, but several call
`os.get_terminal_size()` directly (no `try/except OSError`, e.g. `proxy_pane_shared._terminal_size`),
which raises `OSError: [Errno 25] Inappropriate ioctl for device` when stdout isn't a real
terminal — true for this Bash tool. Confirmed this is pre-existing (the untouched baseline
already fails the same way) by running `p1_worker_selection_click_probe.py` before any change.
Fix: a ~25-line `/tmp/run_in_pty.py` using `pty.fork()` + `fcntl.ioctl(master_fd, termios.TIOCSWINSZ,
...)` to give the child process a real pty of a chosen size, invoked as
`PTY_COLS=<n> ./venv/bin/python /tmp/run_in_pty.py ./venv/bin/python <script>`. Plain
`script -q /dev/null` gets a pty but reports `0x0` size; exporting `COLUMNS`/`LINES` env vars does
NOT work either — `os.get_terminal_size()` (unlike `shutil.get_terminal_size()`) queries the tty
directly and does not consult those env vars. This harness is not itself part of the deliverable
and was not staged into any commit — worth recreating (or asking for) on any future task that
needs to drive a header-wrapping or viewport calculation under this tool.

## Decisions

**`worker_pane.py`, `worker_render.py`, `worker_search.py`, `worker_clipboard.py` deleted
outright — no partial keep.** Every function in them existed to serve the all-workers list:
row-click-to-expand, per-worker nested cache-tracker rendering, three-tier
(name/turn/call)-scoped search, and the name-or-tuple-keyed clipboard serializer. None of that
has a place in a pane showing exactly one worker's own tracker — the closest existing shape for
that is `panes/token_pane.py` itself (single cache tracker, two-tier match keys, no per-item
name-wrapping), not a trimmed-down version of the deleted modules.

**The freeze feature ('f' key, `[LIVE]`/`[FROZEN]` badge) is deleted with the list, not carried
forward — a feature removed with the list it belonged to, not an oversight.** It solved "pause the
whole list's churn so I can read it" — a problem specific to N simultaneously-updating,
independently-scrolling worker blocks. A single-worker tracker doesn't reproduce that problem in
the same shape, and freezing one already-selected worker's own view was never part of the ask.
`dev/click_ui/p3_button_click_probe.py`'s `test_workers_freeze_button` is deleted, not retargeted,
with the reasoning recorded in that file's own docstring.

**`worker_tokens_pane.py` (367 LOC) is a fusion of two already-known-good shapes, not a new
design.** Its body (state, expand/scroll/copy/search mechanics, `format_cache_tracker` render
loop) mirrors `panes/token_pane.py` almost line for line, with `(turn_idx, call_idx)`/`('turn',
turn_idx)` match keys unchanged from that pane — no worker-name wrapping needed, since only one
worker's turns are ever in memory at once (unlike the deleted `worker_search.py`, which had to
wrap every key in the worker's name specifically because the list showed several workers'
independently-expanded content at the same time). Its header/switch mechanics (2-row header:
search bar row 1, worker-switch markers row 2+, IPC-file-driven selection, digit-key and
header-click switching, force-reload-on-switch) mirror `proxy_display/worker_proxy_pane.py`.

**Worker-switch now resets pane state — a deliberate behavior change from the deleted list,
not an oversight.** The old `worker_pane.py`'s own DOCS.md gotcha documented "no worker-switch
reset analog, by design" — true for a pane with no single current worker to switch away from.
This pane has exactly one current worker, same as `worker_proxy_pane.py`, so it adopts that
pane's convention instead: switching resets expand states, scroll offset, search state, and the
cache-turn incremental-read position. Verified directly (`p7_workers_pane_parity_test.py`'s
`test_worker_switch_resets_search_state_and_scroll`), including that stale turns from the
previous worker do not leak into the newly-selected worker's first render.

**`format_worker_switch_header` (in the new `workers/worker_switch_header.py`) keeps the
worker-proxy pane's call site working via an import alias.** `worker_proxy_pane.py` does
`from ..workers.worker_switch_header import format_worker_switch_header as _format_worker_proxy_header`
— the pre-move name stays a valid attribute of that module, so `dev/click_ui/
p1_worker_selection_click_probe.py`'s pre-existing direct calls (`wp._format_worker_proxy_header(...)`)
needed zero changes. The function gained a `label` parameter (default `'WORKER-PROXY'`, so the
worker-proxy call site — which never passes it — is unaffected) and per-marker liveness text
(status word + context-%, both `.get()`-defaulted so a bare `{'name': ...}` fixture dict, which
several probes still pass, never crashes it). `workers/worker_tmux.py` gained
`attach_worker_stats(workers)` to compute that liveness (guarded on `if not session: continue`,
so a probe's `session=''` fixture never triggers a real tmux subprocess call) — called by both
panes' own refresh functions before building their header.

**Narrow-width wrap was verified directly against the pane's real window share, not just at
widths chosen to force a straddle.** worker-tokens is the 34% pane in a 34/66 split with
worker-proxy; five workers' own name+status+context-% marker text wraps across up to 5 physical
rows at that width. Verified with a throwaway script (not staged) that every marker segment stays
independently clickable at width 34, and folded that sweep into
`p1_worker_selection_click_probe.py`'s `test_worker_tokens_header_wrap_at_narrow_pane_width` as a
permanent regression guard (widths 200/60/40/34, asserting `straddle_found` is true and that
pane_width=34 specifically was swept, not just some width that happens to trigger a straddle).

**Mode renamed `workers` → `worker-tokens`** (`core/modes.py`'s `MODE_WORKERS` →
`MODE_WORKER_TOKENS`), threaded through `core/monitor.py`'s dispatch, `startup.py`'s argparse
choices, `workflow.py`'s startup-message suppression list, and `tmux_launcher.py`'s
`_WINDOW_LAYOUT`/`_build_mode_commands`/pane-title map/`M-k` capture message. The tmux WINDOW
label itself stays `workers` (window 2's own `-n` name) — it's a group label for the pane pair,
not a mode string, and renaming it bought nothing.

## Verification

All 7 named dev probes plus 3 more touched incidentally
(`dev/click_ui/p4_gpu_news_button_probe.py`, `p5_proxy_message_copy_click_probe.py`,
`dev/pane_search/p8_warnings_gpu_news_parity_test.py`) run green after the change, via the pty
wrapper at `PTY_COLS=200` (and additionally at 34/40/60 for the two header-wrap tests):

| Probe | Before | After | What changed |
|---|---|---|---|
| `p1_worker_selection_click_probe.py` | 35/35 | 75/75 | `test_workers_pane_row_click` replaced with `test_worker_tokens_header_click` + a new narrow-width wrap sweep |
| `p2_copy_click_probe.py` | 25/25 | 21/21 | `test_workers_pane_copy_click` retargeted at `worker_tokens_pane.py`, same shape as the tokens-pane case (fewer checks — no more separate header-row-copy case) |
| `p3_button_click_probe.py` | 32/32 | 22/22 | `test_workers_freeze_button` deleted (feature retired with the list) |
| `p1_pane_loop_survives_exception_probe.py` | 47/47 | 47/47 | `mod_workers`/`test_workers_pane` retargeted at `worker_tokens_pane.run_worker_tokens_loop`, pane id `workers`→`worker_tokens` |
| `dev/display/test_hover_map.py` | 45 passed | 33 passed | 4 dead tests removed (`format_workers_block`-dependent); proxy-side tests untouched |
| `p5_worker_proxy_pane_parity_test.py` | 77/77 | 77/77 | unchanged file, unaffected by the header move (alias import + `.get()`-defaulted liveness) |
| `p6_tokens_pane_parity_test.py` | 78/78 | 78/78 | unchanged file, unaffected |
| `p7_workers_pane_parity_test.py` | 76/76 (old subject) | 83/83 (new subject) | fully rewritten: same mechanics suite as `p6_`, plus the 2-row header/worker-switch suite of `p5_`, plus a new worker-switch-reset test |

`dev/workers/format_byte_identity.py` (+ its `DOCS.md`) deleted outright — its entire subject,
`format_workers_block`, no longer exists; there is no successor byte-identity harness to write,
since the new pane's rendering IS `format_cache_tracker`, already covered by the parity suites
above. `dev/constants/split_byte_identity.py` updated (`MODE_WORKERS`→`MODE_WORKER_TOKENS` in its
frozen name list) since it would otherwise `AttributeError` on import — confirmed it still
produces a hash (not compared against a prior run; this harness's own before/after pair was for a
different, already-completed split).

Scroll lag/drift (2026-09-02 observation) itself — the row-highlight-vs-cursor drift specifically
— was NOT independently investigated per the task's own scope boundary. The LAG half of that same
observation, however, turned out to have a measured cause; see the next section, which corrects
this entry's own first pass at that boundary.

## Follow-up (same session): the lag was the header-liveness read pattern, not render cost — and this split had doubled it

**The assumption everyone had been making, including this entry's own first pass above, was
wrong.** `process-docs/proxy_pane_scroll/`'s 2026-09-02 observation recorded the lag without
attributing a cause beyond speculating it might be "render cost with five expanded request
tables." This entry's own Trigger section, written earlier in this same session, repeated that
framing and reasoned that a single-worker view "structurally cannot reproduce" the lag because it
never renders more than one expanded tracker — true, but beside the point, because rendering was
never the cost. A post-implementation review caught that `attach_worker_stats` — introduced by
this exact milestone to give the switch header its liveness text (status, context-%) — called
`extract_worker_tokens`/`extract_worker_context_pct` for every worker, and both of those called
`jsonl.read_new_lines(jsonl_path, 0)`: a full read of the ENTIRE worker JSONL from byte zero, on
every `POLL_INTERVAL` (0.5s) tick, in BOTH worker panes now instead of the one pane
(`worker_pane.py`) that used to do the equivalent work.

**Measured on this machine, real files, before touching the fix** (`dev/worker_pane_split/md/
attach_worker_stats_cost_probe_20260915_213048.md`): 5 real worker-worktree JSONLs at their
median real size (~1.6 MB each, 8.02 MB total) cost **70.3 ms** for one `attach_worker_stats`
call. Extrapolated to the actual call pattern (both panes, each gated by its own 0.5s tick):
**281.1 ms of blocking, single-threaded I/O per second — 28.1% of one CPU core — spent solely on
header liveness**, before either pane can poll its own input again. The single largest real
worker JSONL found on this machine (a 196 MB long-running session) cost **623.6 ms** alone — more
than the entire 500ms tick budget, meaning a pane with that worker in its list could not keep its
own refresh tick on schedule at all. This is a directly measured, sufficient explanation for
"noticeable delay" scrolling lag that has nothing to do with render cost, and the panesplit
milestone had made it roughly twice as expensive system-wide by duplicating the same read pattern
into a second pane.

**The fix, same session:** `worker_format.py`'s two full-reparse extractors were replaced by one
`parse_worker_stats_delta(jsonl_path, last_position, running_output, running_context_pct) ->
(total_output, context_pct, new_position)` — reads only `read_new_lines(jsonl_path,
last_position)`, folding new assistant messages into the running totals it was handed instead of
resumming from scratch. `worker_tmux.attach_worker_stats(workers, cache)` gained a required
`cache: dict` parameter (keyed by session name), self-healing (resets a session's entry to
position 0) when that session's resolved `jsonl_path` changes — a worker restarting under a fresh
session file must not keep summing into the old file's totals. Each pane owns its own cache
(`_worker_tokens_stats_cache` / `_worker_proxy_stats_cache`) since they are separate OS processes
with no shared memory — mirrors the exact shape `panes/cache_turns.build_cache_turns` already
uses elsewhere in this codebase for the same "append-only file, incremental position" problem.
Context-% is a LAST-VALUE, not a sum — verified directly (a throwaway smoke script, not staged)
that a tick bringing zero new assistant messages leaves the previous percent standing rather than
dropping it to `None`, and that a new message with no `cache_read_input_tokens` field does the
same; a worker that goes quiet must not blank out in the header, and does not.

**Measured again after the fix** (`dev/worker_pane_split/md/
attach_worker_stats_cost_probe_20260915_213651.md`, same 5 files, same machine): COLD (fresh
cache — what the first tick after a pane starts, or after a worker's session changes, still
pays) dropped to **31.1 ms** — already about half the old 70.3ms, because the fix also merged two
separate full-file passes into one. WARM (steady state — every tick after the first) dropped to
**0.14 ms**, a **220x** speedup over COLD on the same data. Extrapolated the same way: both panes
combined now cost **0.57 ms/s** in steady state, down from the 281.1 ms/s the pre-fix code cost
doing the exact same job. The worst-case 196MB file's COLD cost roughly halved to 320.5 ms (still
one-time, same merge effect); its WARM cost is 0.08 ms — the pathological single-worker case that
used to blow the entire tick budget every 0.5 seconds now does so only once, on first sight of
that worker, never again.

`dev/worker_pane_split/attach_worker_stats_cost_probe.py` is rerunnable and kept in the repo
specifically so a future change to this read path can reproduce this same before/after pair on
whatever machine it runs on, rather than trusting these numbers unverified.
