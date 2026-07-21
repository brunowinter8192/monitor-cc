# Proxy Pane Scroll-Up Overshoot — State/Display Clamp Mismatch, 2026-07-21

## Symptom

Scrolling UP energetically in the proxy pane (`src/proxy_display/pane.py`) overshoots far past the top edge. The display visually stops at the top (correctly clamped), but `proxy_scroll_offset` keeps accumulating a phantom value (observed up to ~1000). Scrolling back DOWN afterward requires unwinding the entire phantom offset before the display reacts — asymmetric bug, bottom-scroll (button 65) was unaffected since it already lower-clamps at 0 and the state never exceeds real content in that direction.

## Root cause

Two clamps existed, at two different layers, and only one of them wrote back to state:
- `_handle_proxy_mouse` (button 64, scroll-up): `proxy_scroll_offset = max(0, proxy_scroll_offset + 3)` — lower-bound only, no upper bound. Unlimited growth on repeated scroll-up ticks.
- `format_proxy_block` (render time): clamps the DISPLAYED slice to the actual content height, but only affects what's drawn — never writes the clamped value back to the `proxy_scroll_offset` global.

Net effect: state and display diverged. State kept growing past the real max, display stayed correctly pinned at the top, and the divergence had to be manually unwound by the user via repeated scroll-down ticks before the display would move.

## Fix

Added a state write-back clamp in `_build_proxy_output` (`src/proxy_display/pane.py`), immediately after the first `format_proxy_block(...)` call returns `total_lines`:

```python
viewport_lines_n = pane_height - 1
max_scroll = max(0, total_lines - viewport_lines_n)
proxy_scroll_offset = min(proxy_scroll_offset, max_scroll)
```

This mirrors the `max_scroll` formula already used a few lines further down inside the `_proxy_just_expanded` auto-scroll branch (unchanged, still computes its own local copy — no behavioral difference since the formula and inputs are identical). Placed at render time (not in the scroll handlers) because the handlers don't have `total_lines`/viewport context — only the renderer does. Every render now re-bounds the state to the current displayable maximum, so an over-scroll tick inflates the state for exactly one frame and the next render pulls it back to `max_scroll` — scroll-down responds immediately instead of needing the phantom offset unwound first.

Scroll handlers and the just-expanded auto-scroll branch were left untouched by design — the fix is a single write-back, not a handler rewrite.

## Verification — this session

`py_compile` clean on `pane.py`. Verified the clamp arithmetic in isolation (the full `_build_proxy_output` path needs a live terminal + live `proxy_entries` + real `format_proxy_block` rendering, not practically fakeable without mocking unrelated pane state — not attempted): reproduced the exact clamp expression with `total_lines=200, pane_height=50` → `max_scroll=151`; `proxy_scroll_offset=1000` collapsed to `151`; in-range offsets (`50`, `0`) passed through unchanged; postcondition `clamped <= max_scroll` held in every case. Live scroll-feel verification in a running terminal pane is the user's own follow-up check, not reproducible from a worker session.
