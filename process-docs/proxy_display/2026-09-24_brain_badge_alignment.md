# Brain-badge time misalignment in the verify report (2026-09-24)

## Task

Issue text: on REQ rows ending in the brain badge the right-aligned time sits one cell further right than on other rows. The suspected cause was that `truncate_visible` counts the brain emoji as 1 cell.

## Findings

- The suspected cause is false. `utils._cell_width` returns 2 for U+1F9E0 (range 0x1F000..0x1FAFF, East Asian Width W). `truncate_visible` and `right_align_time` use the same function.
- Measured: the turn-11 REQ #54 header (brain badge) through `right_align_time` at width 62 is 59 cells (W - 3) by `_cell_width`, the same as rows without a badge. In characters it is 58, because the emoji is one character but two cells.
- The misalignment was seen only in `dev/proxy_display/md/verify_req_numbering_*_turn11.md`, never in the real pane (confirmed by the user). Cause: `verify_req_numbering._side_by_side` padded and cut with `f"{l[:62]:<62}"`, which counts characters. A row with the emoji is one character shorter than its cell width, so the `|` separator and the right column shifted one column right on that row, and in a character view the time looked one column left.

Before (2026-09-24 report, character padding; the `|` of the badge row is one column further right):

```
  ▶ REQ #53 opus 152msg eff:med think:64k          12:02:05    |
  ▶ REQ #54 opus 155msg eff:med think:64k 🧠       12:02:12     |
```

After (cell padding, same session, turn 11, width 62):

```
  ▶ REQ #53 opus 152msg eff:med think:64k          12:02:05    |   ▶ REQ #53  CR: ...
  ▶ REQ #54 opus 155msg eff:med think:64k 🧠       12:02:12    |   ▶ REQ #54  CR: ...
```

## Change

Only `dev/proxy_display/verify_req_numbering.py`: `_cut_cells` and `_pad_cells` (both via `src.utils._cell_width`) replace the character slicing and `:<` padding in `_side_by_side`. No `src/` code changed; `_cell_width` is deliberately untouched.

## Hypothesis, not observed: over-count of some symbols

`_cell_width` treats all of U+2600..27BF as 2 cells. `⚠` (U+26A0, used in the `⚠T` REQ-row warning) and `✓` (U+2713, the copy flash symbol) have East Asian Width N and are drawn as 1 cell by typical terminals without VS16. If a terminal draws them as 1 cell, rows with `⚠T` would have their time one cell left of the column, and the `W - 3` reserve in `right_align_time` (justified in the right-aligned-times work by `✓` being 2 cells) would be 1 cell larger than needed. Zero-width characters (VS16, ZWJ, combining marks) are also counted as 1. None of this was seen on screen, so nothing was changed. If a real misalignment on `⚠T` rows shows up, start with `_cell_width`; `wcwidth` is not installed, only `unicodedata` is available.
