# Right-aligned times on turn rows and REQ rows, token and proxy panes (2026-09-24)

## Task

In the token pane and both proxy panes every time of day moves to the right edge of its row: the
turn header row (`Turn 9 [11:45:23] (1/2 🧠): "..."` had the time inline) and every REQ row (no time
before). The time must stay visible when the row is cut. The same REQ must show the same time in both
panes, next to the same-number requirement from the REQ prefix work.

## Time source decision

Measured on the sidebar worker session (122 requests) 2026-09-24:

| Source | Meaning | Offset |
|---|---|---|
| `_forwarded.timestamp` | request send time | reference |
| transcript FIRST assistant entry of a requestId | first content block | +4.6 s median, +98 s max after send |
| `_response.timestamp` | end of response (`addon.response` writes it with `datetime.now()` after mitmproxy consumed the streamed body) | +6.7 s median, +341 s max after send |
| transcript LAST assistant entry of a requestId | equals response end | +0.02 s median, +0.15 s max from the `_response` time |

A request has 1 to 4 assistant entries (2 typical, one per content block). Chosen: the transcript LAST
assistant entry, i.e. response end. Reason: both proxy panes and both token panes already run
`build_cache_turns`, and the proxy panes already join flow -> request_id -> transcript call, so no
new IO is needed; the worker token pane reads neither `_response` nor `_forwarded`. Same time in
both panes by construction (one field, `call['timestamp']`). Rejected alternative: send time from
`_forwarded` (matches `duallog reqs`, exists for in-flight requests) would need a new incremental
reader plus path plumbing in the token pane and the worker token pane. Rows without a transcript call
(`REQ #?`, `H`, `S`) show no time; no fallback to the forwarded time.

## Layout

`utils.right_align_time(line, time_str, pane_width, bg_restore='')`: content is cut with `…` to
`W - 3 - 8 - 1` cells (below that: empty), then padded, then the 8-cell time. Every time ends at
column `W - 3` on turn rows and REQ rows, so the times form one vertical column. Reserve 3, not 2:
the flash symbol `✓` is 2 cells wide (`_cell_width` treats U+2600..27BF as 2), and
`append_copy_symbol` silently drops the symbol when `pad < 0`; with the time ending at `W - 2` the
flash `✓` would vanish on every row. With the reserve of 3, `⎘` (1 cell) sits 2 cells right of the
time, `✓` 1 cell. The helper appends `SOFT_RESET` after the cut content, and re-inserts
`bg_restore` (`_BG_RESTORE_SENTINEL`) when the original line had it and the cut removed it, so a
search highlight does not flood the time. `utils` cannot import `search_bar` (the other direction
exists), hence the parameter.

Example (sidebar turn 5, width 50, plain text):

```
Turn 5 (4/9 🧠): "Merge step: pushimg… 21:21:19
 ▶ #78 273k/875/2 (127 out)            21:21:21  ⎘        token pane, narrow format
  ▶ REQ #78 sonnet 2msg eff:hig think… 21:21:21  ⎘        proxy pane, content cut, time kept
```

Wide/narrow token formats (`pane_width >= 60`) get the same treatment. The turn header keeps its
prompt truncation formula (`prompt_max`); `right_align_time` only cuts what is still too long.

## Where the pieces live

- `jsonl_cache_turns._build_api_call` stores `timestamp`; `_merge_duplicate_call` keeps the later
  one; `panes/cache_turns._merge_duplicate_turn` does the same across polls.
- `token_format`: `_format_turn_header_line` (inline `[time]` removed), `_format_cache_call`
  (`time_str`, `pane_width`), `_call_time_str`, `request_times_by_id`; the sticky-header regex is
  `Turn \d+` (it used to require the inline `[time]`).
- `token_search._call_matches_query` builds the same row text, so a REQ is searchable by its time.
- `proxy_display/format._time_by_flow`, `render_turn._build_req_header_line(time_str=...)`; the
  time is passed only for rows labelled `REQ #...`.

## Tests and verification

- `dev/proxy_display/test_req_prefix_turn_headers.py`: 46/46 (alignment at widths 50 and 120 in both
  panes, all times in column `W - 3`, REQ rows exactly `W` cells with the copy symbol, truncation
  cases token w=62 and proxy w=40, same time per REQ in both panes, time text searchable, parser keeps
  the later entry time).
- `dev/proxy_display/test_standalone_sidecar.py` 8/8; `dev/dual_log_cli/tests` 0 failures; other
  pane/proxy/display dev scripts return the same codes before and after (stash comparison).
  `click_ui/p2_copy_click_probe.py`, `thinking/render_brain_badge.py`,
  `thinking/render_thinking_expander.py` and `proxy_dual_log/.../A_render_refactor_proof.py` return
  non-zero both ways. `dev/panes/render_byte_identity.py` hash changed by design
  (`f1a8329a...` -> `b86c9f9e...`).
- Side by side at width 62, sidebar turn 5 and monitor-cc turn 11: (number, turn, time) triples
  identical between panes. Example gap: sidebar REQ #84 21:21:58 -> REQ #85 21:23:39.
- `verify_req_numbering.py` now renders at width 62 (rows would otherwise be cut in its column
  layout before the time).

## Observed, not investigated

- The last row of monitor-cc turn 11 (`REQ #54 ... 🧠`) shows its time one cell right of the column in
  the proxy pane: `truncate_visible` counts the brain emoji as 1 cell, `_cell_width` as 2.
- Not run inside a live TUI, only via log replay through the same format functions.
