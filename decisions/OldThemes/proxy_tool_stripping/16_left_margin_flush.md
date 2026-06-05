# Left-Margin Flush — Green/Yellow Row Background Asymmetry (2026-06-05)

## Symptom

In the proxy pane, expanding a request (e.g. the `fields: N changed` section) showed an
alignment asymmetry: yellow stripped rows had their `DIM_YELLOW_BG` background starting at
column 0 (full-width), while green injected rows had their `DIM_GREEN_BG` background starting
only at the first non-space character (~column 6). The left margin of green rows stayed dark
(zebra-coloured), making the left edge of the two overlay colours non-flush.

Observed concretely in the fields section (`max_tokens`, `model`, `output_config`, `thinking`:
yellow old value line vs green new value line). Same asymmetry present in all other green-emitting
paths: system-block headers, tool headers/desc-spans, and message inline spans.

## Root Cause

`format.py` builds the final render output in a per-line loop (~line 186–212). For each output
line it selects `chosen_bg` and prepends it, painting from column 0:

```python
result_lines.append(f"{chosen_bg}{trunc}\033[K{RESET}")
```

The priority chain was:

```python
if is_hovered:
    chosen_bg = HOVER_BG
elif DIM_YELLOW_BG in line:      # yellow lines → hoisted to column 0 ✓
    chosen_bg = DIM_YELLOW_BG
elif is_collision:
    chosen_bg = COLLISION_BG
else:
    chosen_bg = zebra_bg          # green lines fell here → no hoist ✗
```

There was **no `DIM_GREEN_BG in line` branch**. Green rows emitted by the renderers have the
form `"<indent>" + DIM_GREEN_BG + DIM + text + SOFT_RESET` — the `DIM_GREEN_BG` escape code
appears AFTER the leading spaces. Without a hoist, `chosen_bg = zebra_bg` prepended the dark
zebra background to the whole line, and the green only started where the inline escape code
appeared.

Two contributing factors:
- `DIM_GREEN_BG` was not imported in `format.py` at all (only `DIM_YELLOW_BG` was imported),
  so even a manual fix attempt would have failed with a `NameError`.
- `SOFT_RESET = '\033[39m'` resets only the foreground colour, not the background. This means
  the inline `DIM_GREEN_BG` set inside the text remained active after `SOFT_RESET`, so `\033[K`
  already filled the **right-hand** margin correctly with green. The bug was exclusively the
  **left** margin (columns 0–5), which received the prepended `chosen_bg = zebra_bg` (empty or
  dark). The fix does not touch `SOFT_RESET`.

## Fix

`src/proxy_display/format.py` — two changes:

1. **Import:** added `DIM_GREEN_BG` to the `constants` import alongside `DIM_YELLOW_BG`.
2. **elif branch:** added `elif DIM_GREEN_BG in line: chosen_bg = DIM_GREEN_BG` between the
   yellow and collision checks:

```python
elif DIM_YELLOW_BG in line:
    chosen_bg = DIM_YELLOW_BG
elif DIM_GREEN_BG in line:          # ← added
    chosen_bg = DIM_GREEN_BG
elif is_collision:
    chosen_bg = COLLISION_BG
```

Result: `f"{DIM_GREEN_BG}{indent}{DIM_GREEN_BG}{DIM}text{SOFT_RESET}\033[K{RESET}"` — the
leading `DIM_GREEN_BG` fills from column 0; the inline escape is redundant but harmless;
`\033[K` fills to end-of-line with green. Full-width green, flush with yellow.

Hover priority (`HOVER_BG` first) is preserved unchanged.

## Affected Paths

All green-emitting render paths were affected identically; all are fixed by the single hoist:
- `render_sections.render_fields_delta` — old/new value pairs per field key
- `render_sections.render_system_blocks` — block headers + inline injected spans
- `render_sections.render_tools` — whole-injected tool name lines + desc span rows
- `render_messages.py` — new-format inline injected span rows (both msg-count branches)

No render-side changes were needed — all emit sites already placed `DIM_GREEN_BG` inline;
the fix makes format.py also use it as the row-level background.

## Verification

- Code-review convergent: root cause confirmed by reading `format.py` priority chain + constants.
- Live render verification: by user after monitor restart (pure read-side change, no proxy restart needed).
