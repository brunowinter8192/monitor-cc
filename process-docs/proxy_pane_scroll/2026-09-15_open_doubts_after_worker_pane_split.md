# Open doubts about scroll behavior after the worker pane split (2026-09-15)

Written by the orchestrator session that merged the worker-tokens/worker-proxy split, at the
point where issue "Workerpane" was closed without the row-drift half of it ever being reproduced.
This is a doubt record, not a finding. Nothing below was observed in the new panes — they had not
been run in production at the time of writing.

## What was closed and on what basis

The 2026-09-02 observation in this area recorded two symptoms on the old all-workers list pane:
scrolling lag, and a row highlight sitting one line off from the `>>` left-edge cursor.

The lag half is now explained and fixed, with numbers. `attach_worker_stats` read every listed
worker's whole JSONL from byte zero, twice per worker, on every 0.5s tick. Measured on real files:
70.3 ms for five typical workers, 623.6 ms for a single 196 MB one, 281.1 ms of blocking work per
second once the split had put that read in both panes. After the rewrite to an incremental
position-keyed read the same work costs 0.57 ms/s in steady state. The measurement script is
`dev/worker_pane_split/attach_worker_stats_cost_probe.py` and both before/after reports sit
beside it. The full account is in `process-docs/workers/`.

The drift half was never reproduced. The pane it was observed on — `src/workers/worker_pane.py`
plus `worker_render.py` — was deleted by the split. The user's decision was to close the issue,
run the new panes in production, and open a fresh issue with a fresh screenshot if drift shows up
again.

## Doubt 1 — the new tokens pane inherited the missing write-back clamp

This area already documents the same bug three times: 2026-07-21 (proxy pane), 2026-07-28
(worker-proxy pane, plus an off-by-one correction), 2026-08-04 (main pane). The shape is always
the same. The wheel-up handler lower-bounds the offset at 0 and never upper-bounds it; the
renderer clamps what it DRAWS but never writes the clamped value back to the state global. State
and display diverge, and scrolling back down does nothing until the phantom excess unwinds.

`src/workers/worker_tokens_pane.py` was modelled on `src/panes/token_pane.py` for its body, and it
copied that module's scroll handling as it stands. Neither module has a write-back clamp:

- `token_pane.py`: `cache_scroll_offset = max(0, cache_scroll_offset + 3)` on wheel-up, and
  `_build_tokens_output` never re-bounds `cache_scroll_offset` after `format_cache_tracker`
  returns.
- `worker_tokens_pane.py`: `worker_tokens_scroll_offset = max(0, worker_tokens_scroll_offset + 3)`,
  same absence downstream.

`worker_proxy_pane.py` is the counter-example and the reason the split did not make things worse
on that side: it renders through `proxy_pane_shared._render_and_scroll_body`, which computes
`max_scroll` and writes the clamped value back.

So by the criteria of the three prior entries in this area, two panes carry the bug today: the
main tokens pane, which has carried it all along and was never named in those entries, and the new
worker-tokens pane, which inherited it by being modelled on the first. Whether either produces a
user-visible symptom is unmeasured. The prior entries describe the symptom as a dead wheel-scroll
step and an unwind delay, not as row drift, so this doubt is about a DIFFERENT symptom than the
one the 2026-09-02 observation reported.

## Doubt 2 — the switch header wraps, and the header height is cached from the last render

The old list pane had a fixed-height header. The new worker-tokens pane does not: its switch
header carries name, status word and context percent per worker, and the pane occupies 34% of the
window next to worker-proxy at 66%. With a handful of workers that header wraps across several
physical rows, and the number of rows changes whenever a worker appears, disappears, or changes
status.

`_worker_tokens_header_lines` is a module-level cache of the last render's header height. It is
refreshed on every render and read by `_ensure_worker_tokens_match_visible` to compute a scroll
target on search-jump. That is a one-frame-stale value by construction. A jump computed against a
header height that changed in the same tick would land the viewport off by the difference. This is
exactly the class of mistake the 2026-07-28 entry in this area described as the header-offset
trap, where clamping against the wrong viewport height made the topmost line unreachable.

Nobody has seen this happen. It is named here because the ingredients are present and because a
future reader chasing an off-by-N jump in this pane should look here before anywhere else.

## Doubt 3 — the drift observation may have had nothing to do with scrolling

The 2026-09-02 screenshots showed the highlight bar spanning two request rows and sitting one line
off the left-edge marker. The deleted list pane built its rows through `worker_render.py`'s
zebra/hover loop over a nested rendering: `format_workers_block` prepended two literal spaces
before every `format_cache_tracker` line in the per-worker view, and the hover/highlight mapping
had to account for that indent. The new pane has no nesting and no indent — one worker, rendered
flat, the same way the main tokens pane renders.

If the drift came from that nested line mapping, it is gone with the code that produced it and no
fresh issue will ever appear. If it came from the scroll state, Doubt 1 is where it lives. These
two possibilities were never separated, and the data to separate them no longer exists.

## What a next session should do

Do not fix Doubt 1 speculatively. Three prior entries in this area each started from a reproduced
user report, and each fix was a single write-back line placed where the renderer's own total was
already available. The same fix is available for `token_pane.py` and `worker_tokens_pane.py` at
any time, and is cheap. What is missing is the observation that says it matters for either one.

If a drift report does come back from the new panes, the first thing to establish is which of the
two symptom classes it is: a dead wheel step with an unwind delay points at Doubt 1, a highlight
sitting next to its own cursor mark points at the row-mapping path instead, and a wrong landing
spot after a search jump points at Doubt 2.
