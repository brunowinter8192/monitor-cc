# NSGridView Migration — Architecture Pivot

## Motivation

Pre-migration: each panel row was a single NSButton with `NSAttributedString` title containing `name.ljust(_COL_NAME_W)` and string-spacers (`[*]`, `[ ]`, `[B M:SS]`). Even with Menlo monospace, NSButton title-rect internal padding made column positions drift between rows — `[*]` of a worker row and `[ ]` of a main row rendered at different x-positions despite source strings having equal column counts. Bug was user-visible.

Target: NSGridView per panel, project-separators as merged-cell rows spanning all columns, rows as cells sharing target/action/tag for click routing.

## Architecture

One NSGridView per panel:

| Panel | Cols | Layout |
|---|---|---|
| Main (panel.py) | 5 | `[slot] [*] [name flex] [dot] [badge]`, leading placement |
| Bead (bead_panel.py) | 2 (later 3 with `?` button) | `[expand-btn flex] [×]` → `[expand-btn flex] [?] [×]` |
| Queue (queue_panel.py) | 1 (collapsed) | merged single-cell container with internal-frame subviews per row |

Project-separators: `addRowWithViews_([label, empty, empty, empty, empty])` + `mergeCellsInHorizontalRange_verticalRange_(NSRange(0,N), NSRange(row,1))`.

Empty cells use `NSGridCell.emptyContentView()` (NOT Python `None` — NSNull crashes addRowWithViews_).

## Pitfalls discovered (in order of debugging)

### 1. TAMIC turned off automatically

`NSGridView.addRowWithViews_` calls `setTranslatesAutoresizingMaskIntoConstraints_(False)` on every content view. Frame-based sizing is ignored. Cells with no `intrinsicContentSize` and no explicit AutoLayout constraints get assigned `height=0` and/or `width=0`.

Probe-verified: `(x=0, y=39, w=358, h=0)` for unconstrained NSView container vs `(x=0, y=21, w=358, h=18)` with explicit `heightAnchor.constraintEqualToConstant_(18)`.

**Required pattern:** every NSView placed into a grid cell needs explicit width AND height constraints:

```python
container.widthAnchor().constraintEqualToConstant_(float(w)).setActive_(True)
container.heightAnchor().constraintEqualToConstant_(float(h)).setActive_(True)
```

For borderless NSButtons (zero intrinsic size by default): both anchors mandatory or the button gets zero hit-area inside its grid cell. Applied to `_make_queue_minus_btn`, `_make_queue_msg_label`, `_make_queue_add_btn`.

### 2. Separator-row visual bleed

`_make_separator_view` returned an NSView with internal `NSBox` at y=9 and an NSTextField label. With height=0 from missing constraint, `yPlacement=top` (NSGridView default) pinned the container origin to the row's top edge — subviews then drew UPWARD into the previous row's bounds. Visible as "searxng" label overlaying the "Monitor_CC" session row above it.

Fix: explicit `heightAnchor` on the container. Applied to `panel.py:_make_separator_view` and `bead_panel.py:_make_expand_view`. Bead-panel project headers were unaffected because `_make_header_label` returns NSTextField with non-zero intrinsicContentSize.

### 3. Re-entry guard for `_rebuild_*`

Symptom: clicking `+` on an empty draft NSTextField duplicated the entire queue panel content (two complete copies of project headers, inputs, and `+` buttons).

Trace:
1. NSTextField has focus, user clicks `+`
2. Focus leaves field → `controlTextDidEndEditing_` fires (CTRL-END-1)
3. CTRL-END-1 calls `_rebuild_queue_panel` (REBUILD-1)
4. REBUILD-1 iterates `arrangedSubviews()` and calls `removeFromSuperview()` on each, INCLUDING the focused NSTextField
5. Removing the focused NSTextField triggers a NESTED `controlTextDidEndEditing_` notification (CTRL-END-2) during REBUILD-1
6. CTRL-END-2 calls `_rebuild_queue_panel` again (REBUILD-2) — re-entrant
7. Both rebuilds add content to arrangedSubviews

Fix: module-level boolean guard at the entrance of each `_rebuild_*`:

```python
_rebuild_queue_in_progress = False

def _rebuild_queue_panel(app, sessions):
    global _rebuild_queue_in_progress
    if _rebuild_queue_in_progress:
        return
    _rebuild_queue_in_progress = True
    try:
        _rebuild_queue_panel_inner(app, sessions)
    finally:
        _rebuild_queue_in_progress = False
```

Applied defensively to all three: `panel.py`, `bead_panel.py`, `queue_panel.py`.

### 4. `_KeyablePanel(NSPanel)` for keyboard focus

NSPanel with `NSWindowStyleMaskNonactivatingPanel` overrides `canBecomeKeyWindow` to return False by default. Without key-window status, `makeFirstResponder_(textfield)` is a no-op for keyboard event routing — the NSTextField is in the responder chain but never receives keyDown.

Fix: subclass NSPanel with explicit override:

```python
class _KeyablePanel(NSPanel):
    def canBecomeKeyWindow(self):
        return True
```

Used by all three `_make_*_nspanel` builders. The nonactivating mask still prevents app activation (Ghostty stays foreground); `canBecomeKey=True` only grants key-window status to the panel itself. These are orthogonal AppKit concepts.

### 5. NSStackView removeView_ ≠ removeFromSuperview

`NSStackView.removeView_(sv)` removes the view from arranged-subviews tracking only. The view stays parented in the view hierarchy as a regular subview — still renders. Next rebuild adds a NEW grid as an additional arranged subview ON TOP of the orphaned old one. Visible as duplicate panel content.

Fix in the rebuild-loop:

```python
for sv in list(app._XXX_sv.arrangedSubviews()):
    app._XXX_sv.removeView_(sv)
    sv.removeFromSuperview()
```

Applied to all three rebuild functions.

## Sources

- `/Applications/Ghostty.app/Contents/Resources/Ghostty.sdef` — Ghostty AppleScript dictionary
- AppKit docs: NSGridView, NSGridCell.emptyContentView, mergeCellsInHorizontalRange_verticalRange_
- Probe artifact: `dev/grid_probe/probe.py` — Phase A verification of PyObjC bindings + visual alignment
