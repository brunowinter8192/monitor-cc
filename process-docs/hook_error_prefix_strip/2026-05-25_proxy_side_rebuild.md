# Hook-Error Prefix Strip — Architecture Decision (2026-05-25)

## What We Did

Previous worker (hook-cleanup-2, D4) added `_strip_hook_error_prefix()` to `src/format/formatter.py`
and called it in `format_error_output()` and `src/panes/warnings_render.py`. Display-only strip.

This task (cleanup-deploy): reverted D4 and rebuilt as a proxy-side strip module.

**Files touched:**
- Reverted: `src/format/formatter.py` (removed `_HOOK_ERROR_PREFIX`, `_strip_hook_error_prefix`, call site)
- Reverted: `src/panes/warnings_render.py` (removed import, reverted `raw_text = err['full_text']`)
- Built: `src/proxy/strip_hook_prefix.py` — `_strip_hook_prefix(content)` → `(new_content, removed_chunks)`
- Wired: `src/proxy/rules.py` — `_apply_hook_prefix_strip` pass after `_apply_bg_exit_strip`, before `_dedup_wakeup_blocks`

## What We Found

**D4 architecture flaw:**
CC wraps every hook stderr as `PreToolUse:<Tool> hook error: [python3 <path>]: <actual msg>`.
D4 stripped this prefix in the display layer only — Anthropic still received the full prefix in the
`tool_result.content`. The proxy is the correct strip point because:

1. `_build_entry(flow, modified_payload, ...)` is called with `modified_payload` (post-modification).
   So proxy strips → JSONL log records the stripped content → `err['full_text']` in warnings_render
   is already clean → display doesn't need to strip at all.

2. After proxy strip, `stripped_msg_removed[idx]` contains the stripped prefix text + the proxy
   sets `modifications = ['stripped_hook_error_prefix']`. The existing `highlight_stripped` mechanism
   then shows a yellow [STRIPPED] marker in the warnings pane — better UX than silent display strip.

3. Anthropic receives the clean error message without the CC wrapper noise.

**Content-shape analysis:**
Hook errors arrive as `tool_result` blocks with `is_error: true`. The content can be:
- `tool_result.content` as string
- `tool_result.content` as list of `{type: text, text: ...}` blocks

The strip module handles all 4 shapes (top-level str / list-of-text / tool_result-str /
tool_result-list-of-text) following the `strip_po.py` / `strip_bg_completed.py` pattern family.
Fast-path guard `_HOOK_PREFIX_MARKER = 'PreToolUse:'` skips non-matching messages cheaply.

**Regex:** `r'^PreToolUse:\w+ hook error: \[python3 [^\]]+\]:\s*'` with `re.MULTILINE`, `count=1`.

**Pass ordering in rules.py orchestrator:**
After `_apply_bg_exit_strip` (BGK plain-text path, pos 104) and before `_dedup_wakeup_blocks` (pos 124).
Hook-error content is in `tool_result` blocks — no interaction with BG notifications or wakeup dedup.
Ordering vs other passes is irrelevant; this was placed last in the message-side pass sequence.

**Worktree guard + data flow — NOT a blocker:**
`_build_entry` at `addon.py:124` uses `modified_payload` (confirmed by reading addon.py).
After D3, the logged content has the prefix stripped. The live proxy for this worker session was a
frozen snapshot (pre-D3) so live traffic verification was not possible from the worktree — unit tests
verified all 4 content shapes instead.

## dev/ Scripts

No dev/ probe built — this was a direct architectural correction with unit verification inline.
The strip logic was verified by a one-shot inline test (not committed to dev/).

## Decision / Next

- Proxy-side strip is the canonical approach for all content transformations that affect the API payload.
- Display-side strips (formatter.py) are only appropriate for rendering artifacts that live exclusively
  in the monitor display and never touch the API (e.g. ANSI color formatting, truncation markers).
- The [STRIPPED] yellow marker in warnings pane will show the stripped prefix after proxy restart.
- **Post-merge:** restart proxy with `claude_proxy_start.sh` to activate `strip_hook_prefix.py`.
