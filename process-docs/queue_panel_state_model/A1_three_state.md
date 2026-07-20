# Queue Panel — Three-State Model (draft / queued / sent)

## Motivation

Pre-redesign: queued messages auto-deleted on successful delivery (hook_writer popped the head). User had no visibility of what was sent vs pending vs still-being-typed. No way to "stage" a message without committing it. + button replaced by one input field with binary `_pending_queue_count`-like state.

New user-facing model:

| State | Color | Cell content | Toggle button | × delete |
|---|---|---|---|---|
| draft | default gray | editable NSTextField | `↑` → queue | yes |
| queued | red bg (alpha 0.18) | read-only label | `↓` → unqueue (→ draft) | yes |
| sent | green bg (alpha 0.18) | read-only label | none (locked) | yes |

## Data model

Storage: `msg_queue.json` per session_id, list of dicts:

```json
{"text": "...", "state": "draft|queued|sent", "sent_at": null|"ISO8601"}
```

`load_queue` normalizes on read (`queue.py:_normalize_entry`):
- Bare strings (legacy) → `{text, state: queued, sent_at: null}`
- Dict missing `state` → infer from `sent_at` (non-null → sent, else queued)
- Dict with `state=queued` AND `sent_at` set (legacy inconsistency from pre-state-flip code) → `state=sent`

Save writes the canonical form always.

## State transitions

| Trigger | Handler | Action |
|---|---|---|
| `+` click | `addQueueRow_` | append `{text:"", state:draft, sent_at:null}` if last entry isn't already empty draft |
| `↑` click on draft | `toggleQueueEntry_` | capture live NSTextField text from `_pending_queue_views[(sid,idx)]`, flip state to queued |
| `↓` click on queued | `toggleQueueEntry_` | flip state to draft (text preserved) |
| Enter on draft | `commitQueueField_` | save text + flip state to queued (Enter = ↑) |
| Focus loss on draft | `controlTextDidEndEditing_` | save text only, state stays draft, no rebuild |
| × click | `removeQueueEntry_` | remove entry from queue file |
| Stop hook | `_maybe_deliver_queue` (hook_writer) | find first state=queued, deliver, on success set state=sent + sent_at |
| User queues while session already idle | `_try_deliver_now` (app.py) | read hooks.json, if status=idle deliver immediately |

## Critical: live-text capture on toggle

Bug discovered in first iteration: clicking `↑` while NSTextField has unsaved text loses the text. Root cause: borderless NSButton click does NOT make NSTextField lose focus, so `controlTextDidEndEditing_` does NOT fire. `toggleQueueEntry_` then reads queue.json (still has empty text from the initial draft entry) and flips state with empty text.

Fix: maintain `app._pending_queue_views: dict[(session_id, idx), NSTextField]` populated during rebuild. `toggleQueueEntry_` reads `tf.stringValue()` directly before flipping state:

```python
tf = app._pending_queue_views.get((session_id, idx))
live_text = str(tf.stringValue()) if tf is not None else None
entries[idx] = {**e, "state": new_state}
if live_text is not None:
    entries[idx]["text"] = live_text
```

`removeQueueEntry_` on a draft does NOT need the same — removing discards the unsaved text anyway.

## Immediate delivery on idle (`_try_deliver_now`)

Stop hook only fires on the working → idle TRANSITION. If a session is ALREADY idle when user queues a message, the hook won't fire until the next working cycle. Message sits in state=queued indefinitely.

Solution: in `commitQueueField_` and `toggleQueueEntry_`, after flipping to state=queued, call `_try_deliver_now(app, session_id, text, idx)`. That function:
1. Reads hooks.json for session's current status
2. If status != "idle" → return (Stop hook will handle later)
3. If cwd or text empty → return
4. Call `deliver_message(cwd, text)`
5. On success: load queue, set `state="sent"` + `sent_at=now_iso()`, save

Concurrency safety: hook_writer.py and menubar's _try_deliver_now both use `flock(QUEUE_LOCK)` during read-modify-write. If both fire concurrently (rare), worst case is double-delivery; mark_sent's pre-check on `entry.state == "queued"` makes the second mark_sent a no-op.

## Rendering specifics

Single-cell merged NSGridView row containing a custom NSView with `setWantsLayer_(True)`. The layer's `backgroundColor` is set via `NSColor.systemRedColor().colorWithAlphaComponent_(0.18).CGColor()`. Subviews (text/label, toggle button, × button) positioned via plain frames inside the container.

Side effect: `NSColor.CGColor()` returns a raw CGColor pointer, triggering `ObjCPointerWarning` log noise. Functional (background renders correctly), cosmetic. Deferred — not worth the NSBox refactor that would avoid it.

Read-only label text color: explicit `NSForegroundColorAttributeName: NSColor.labelColor()`. Without this, default black text becomes invisible on dark-mode panel + red/green tint. NSTextField bezeled handles dark mode automatically — only raw NSAttributedString labels need the explicit color.

## Sources

- Phase-A probe + manual osascript live test
- AppKit docs: NSView wantsLayer, CALayer backgroundColor
- See `nsgridview_migration/` for the underlying grid pattern
- See `ghostty_native_delivery/` for the delivery code path
