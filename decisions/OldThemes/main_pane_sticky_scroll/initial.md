# Main Pane Sticky Scroll — Initial Implementation

## Problem

The main pane (`src/core/monitor.py:run_main_loop`) is a bottom-anchor TUI: `main_scroll_offset`
is "lines from bottom" (0 = newest at bottom of view). When the user scrolls up and new events
arrive via `monitor_sessions()`, the buffer grows but the offset stays fixed. The render formula:

```python
start = max(0, total - buffer_height - scroll_offset)
```

means `start` grows with `total` — the viewport drifts upward through the content. The user's
intended read position jumps away as new tool calls arrive.

## Option A vs Option B

**Option A — line-delta adjust (chosen):**
Before `monitor_sessions()` snapshot `total_lines`. After, compute `delta = total_after - total_before`.
If `scroll_offset > 0`, apply `scroll_offset += delta`. This keeps `start` constant.

**Option B — absolute-anchor switch:**
On first scroll-up, store `anchor = start` (absolute index of viewport top). On each render use
`start = anchor` directly instead of the offset formula. When user reaches bottom, drop anchor.

**Why Option A was chosen:**
- Touches only the data-refresh block in `run_main_loop` + one new helper in `monitor_display.py`
- No changes to wheel handlers, render formula, or `ensure_match_visible`
- No new module-level state
- The delta approach handles buffer cap trimming correctly: when K events are trimmed from the
  front and N added at the back, `total_after - total_before = N - K`, which is exactly the net
  shift in the viewport start index

**Why Option B was not chosen:**
- Requires changing the render formula (`start = anchor` rather than computed)
- Requires changing wheel handlers to update `anchor` rather than `scroll_offset`
- Two representations in play (`anchor` vs `scroll_offset`) creates a mode-switch with more
  edge-case surface (resize, search-jump, session-reset all need awareness of which mode)

## Implementation

New function `_count_buffer_lines(pane_width: int) -> int` in `monitor_display.py` (just above
`render_main_buffer`): iterates `main_event_buffer`, calls `_format_event_to_lines(event)` for
each, accumulates `len(lines) + 1` (the +1 is the blank separator between events).

In `run_main_loop` data-refresh block (lines ~271-289 post-commit):
1. After the session-reset guard, before `monitor_sessions()`: if `main_scroll_offset > 0`,
   snapshot `_sticky_pre = _count_buffer_lines(pane_width)`.
2. After `monitor_sessions()` + `_refresh_strip_cache()`: if `_sticky_pre is not None` and
   `main_scroll_offset > 0`, compute delta and clamp: `scroll_offset = max(0, offset + delta)`.

## Edge cases covered

| Case | Behaviour |
|---|---|
| `scroll_offset == 0` | `_sticky_pre = None` → no adjustment → bottom-anchor unchanged |
| Session reset fires | Sets `scroll_offset = 0` before snapshot → `_sticky_pre = None` → no adjustment |
| User wheels to 0 mid-tick | Second guard `scroll_offset > 0` fails → no adjustment → follow resumes |
| `ensure_match_visible` / search jump | Writes `scroll_offset` directly — unchanged, not affected |
| Buffer cap trim | `delta = lines_after - lines_before` accounts for removed lines; net shift correct |
| Buffer shrink (session reset + same cycle) | `delta < 0`, `max(0, ...)` clamps → no crash |

## Known limitation

**Buffer-cap trim shifts viewport by trimmed-line count.** When `MAIN_EVENT_BUFFER_CAP` is
exceeded and K lines are evicted from the front, those events are gone. The viewport shifts
upward by K lines relative to the remaining content. The delta adjustment compensates for the
net buffer growth (N new - K trimmed), but the K lines the user may have been near the top
of are now gone. This is accepted: the content is lost regardless (it was evicted), and the
user's view correctly anchors to whatever is now at the same index in the trimmed buffer.

## Resize behaviour

Terminal resize changes `pane_width`, which changes line wrapping for all events. The pre/post
`_count_buffer_lines` calls within a single tick both use `os.get_terminal_size().columns`, so
any resize that occurs between the two measurements produces a slightly wrong delta. In practice,
resize events between the two sequential calls within the same millisecond-range code block are
negligible. Gross resize-induced reflow shifts the viewport by an amount proportional to the
re-wrapped content — same limitation as the pre-existing code, not made worse.
