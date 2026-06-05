# Green Overlay Probe Report (Level 2)

Three diff variants: `diff_text_word` (current/buggy) · `diff_text_char` (char-level)
· `diff_text_char_gated` (char-level + attribution gate for phantom injected spans).

## Gating Signal Soundness Verification

Gate rule: injected span with `_fn_for_inject(text) == 'unknown'` → reclassify to `equal`.

**Scanned 44 `*_injected.jsonl` logs (msg.\* loc_keys only):**

| fn value | count | classification |
|---|---|---|
| `'_apply_bg_exit_strip'` | 79 | REAL inject — correctly non-unknown ✅ |
| `'unknown'` total | 431 | see breakdown below |
| — phantom-like (ends `\\n\\n[",}\\]]`) | 287 | word-level diff artifact ✅ correctly gated |
| — other (potentially real) | 144 | ⚠️ FLAG: real injects also map to unknown |

**Phantom attribution test:**
- `_fn_for_inject('", "is_error": f'            )` → `'unknown'` → correctly gated ✅
- `_fn_for_inject('connections?\\n\\n",'        )` → `'unknown'` → correctly gated ✅
- `_fn_for_inject('set()))\\n\\n",'             )` → `'unknown'` → correctly gated ✅

**Real inject test:**
- `_fn_for_inject('background done...')` → `'_apply_bg_exit_strip'` → kept green ✅

**⚠️ FLAG — real injects that ALSO map to 'unknown':**
- `msg.0.0` i_text='.' → fn='unknown' → would be gated (suppressed)
- `msg.0.1` i_text='.' → fn='unknown' → would be gated (suppressed)
- `msg.0.2` i_text='\n' → fn='unknown' → would be gated (suppressed)
- `msg.104.0` i_text='/Users/brunowinter2000/.claude/projects/-Users-brunowinter2000-Documents-ai-moni' → fn='unknown' → would be gated (suppressed)
- `msg.126.0` i_text='.' → fn='unknown' → would be gated (suppressed)

**Verdict:** Gate is CONDITIONALLY sound. It correctly eliminates the phantom diff
artifacts (287 cases — `\\n\\n[",}]` tail pattern from word-level bug on write-side).
But 144 real message-level injects also attribute to 'unknown'
(dot-replacements at msg.0.x for haiku/title calls, file-path injections, etc.) and
would be suppressed (shown grey instead of green). Sidecar markers `[SIDECAR_STRIPPED_X_BYTES]`
would also be suppressed. Only `_apply_bg_exit_strip` (bg-done, 78 cases) correctly avoids gating.

## Primary Bug Case — Three Variants Side By Side

**Source:** `api_requests_worker_25c51a2e_badge-recap_1780678180`
**Flow ID:** `7a12336f-7d76-476f-a3b2-4d58f9ae6f2f`
**Location:** `messages[18]` block 0 (tool_result, role=user)
**o_text len:** 762 | **f_text len:** 301 | **common prefix:** 280 chars (ends at `set()))\\n\\n`)

### Variant 1: `diff_text_word` — CURRENT PRODUCTION (buggy) — 4 spans
```
  ('equal'   , '{"tool_use_id": "toolu_013iZEuK4YDi1HqL5W9W5bMU", "type": "tool_result", "content": "80: _fid = entry.get(\'flow_id\', \'\')'...)
  ('stripped', "set()))\\n\\n<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit f"...)
  ('injected', 'set()))\\n\\n",')
  ('equal'   , '"is_error": false}')
```
**Bug:** `set()))\\n\\n<system-reminder>...` (orig) and `set()))\\n\\n",` (fwd) are ONE word each.
SequenceMatcher 'replace' → common prefix `set()))\\n\\n` appears as BOTH stripped (yellow) AND injected (green).

### Variant 2: `diff_text_char` — char-level fix — 6 spans
```
  ('equal'   , '{"tool_use_id": "toolu_013iZEuK4YDi1HqL5W9W5bMU", "type": "tool_result", "content": "80:    _fid = entry.get(\'flow_id\', '...)
  ('stripped', '<system-reminder>\\nThe t')
  ('injected', '", "is_error": f')
  ('equal'   , 'a')
  ('stripped', "sk tools haven't been used recently. If you're working on tasks that would benefit from tracking progress, consider usin"...)
  ('equal'   , 'lse}')
```
**Yellow fixed:** common prefix is now span[0]=equal (280 chars) ✅
**Residual phantom green:** `['\'", "is_error": f\'']` — LCS suboptimal alignment on suffix ⚠️

### Variant 3: `diff_text_char_gated` — THE GOAL — 6 spans
```
  ('equal'   , '{"tool_use_id": "toolu_013iZEuK4YDi1HqL5W9W5bMU", "type": "tool_result", "content": "80:    _fid = entry.get(\'flow_id\', '...)
  ('stripped', '<system-reminder>\\nThe t')
  ('equal'   , '", "is_error": f')
  ('equal'   , 'a')
  ('stripped', "sk tools haven't been used recently. If you're working on tasks that would benefit from tracking progress, consider usin"...)
  ('equal'   , 'lse}')
```
**Green spans remaining:** 0 (none — phantom gone ✅)
**Stripped contains `<system-reminder>`:** True ✅
**Fidelity (char):** orig_ok=True fwd_ok=True | **Fidelity (gated):** gated_ok=False ❌

## Regression Spot-Check — All Three Variants

| Case | o_len | f_len | word | char | gated | gated_fid | gated inj remaining |
|---|---|---|---|---|---|---|---|
| R1: msg[2] blk[0] partial replace (ratio=0.76) | 429 | 322 | 4 | 6 | 6 | ❌ | 0 (all gated) |
| R2: msg[4] blk[0] tiny edit large block (ratio=0.99) | 27523 | 27137 | 3 | 3 | 3 | ✅ | 0 (all gated) |
| R3: msg[38] blk[0] system-reminder strip (ratio=0.95) | 4973 | 4512 | 4 | 3 | 3 | ✅ | 0 (all gated) |
| R4: synthetic multi-space/tab whitespace-collapse test | 42 | 50 | 4 | 3 | 3 | ❌ | 0 (all gated) |

### Details

#### R1: msg[2] blk[0] partial replace (ratio=0.76)
o_text: `'{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/badge-recap\\nbadge-recap\\n\\n<system-reminder>\\nThe'`
f_text: `'{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/badge-recap\\nbadge-recap\\n\\n<system-reminder>\\nThe'`

Word (4 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai'...)
  ('stripped', "SHA]\\n\\nIMPORTANT: After completing your current task, you MUST address the user's message above. Do not ignore it.\\n</s"...)
  ('injected', 'SHA]\\n\\n</system-reminder>\\n",')
  ('equal'   , '"is_error": false}')
```
Char (6 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai'...)
  ('stripped', 'IMPORTANT: A')
  ('injected', '</system-reminder>\\n", "is_error": ')
  ('equal'   , 'f')
  ('stripped', 'ter completing your current task, you MUST address the user\'s message above. Do not ignore it.\\n</system-reminder>", "is'...)
  ('equal'   , 'alse}')
```
Gated (6 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai'...)
  ('stripped', 'IMPORTANT: A')
  ('equal'   , '</system-reminder>\\n", "is_error": ')
  ('equal'   , 'f')
  ('stripped', 'ter completing your current task, you MUST address the user\'s message above. Do not ignore it.\\n</system-reminder>", "is'...)
  ('equal'   , 'alse}')
```
  → no injected spans remaining (all phantom-gated or no real injects in this case)
Fidelity: char=orig_ok=True fwd_ok=True | gated=False

#### R2: msg[4] blk[0] tiny edit large block (ratio=0.99)
o_text: `'{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t## Role\\n4\\t\\n5\\tProxy pane TUI package. Reads mitmproxy forwarded-delta entries f'`
f_text: `'{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t## Role\\n4\\t\\n5\\tProxy pane TUI package. Reads mitmproxy forwarded-delta entries f'`

Word (3 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t##'...)
  ('stripped', 'handler.\\n144\\n\\n<system-reminder>\\nThe following deferred tools are now available via ToolSearch. Their schemas are NOT'...)
  ('injected', 'handler.\\n144\\n\\n"}')
```
Char (3 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t##'...)
  ('stripped', '<system-reminder>\\nThe following deferred tools are now available via ToolSearch. Their schemas are NOT loaded — calling'...)
  ('equal'   , '"}')
```
Gated (3 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t##'...)
  ('stripped', '<system-reminder>\\nThe following deferred tools are now available via ToolSearch. Their schemas are NOT loaded — calling'...)
  ('equal'   , '"}')
```
  → no injected spans remaining (all phantom-gated or no real injects in this case)
Fidelity: char=orig_ok=True fwd_ok=True | gated=True

#### R3: msg[38] blk[0] system-reminder strip (ratio=0.95)
o_text: `'{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/to'`
f_text: `'{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/to'`

Word (4 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-requ'...)
  ('stripped', "badge.\\n\\n<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit fr"...)
  ('injected', 'badge.\\n\\n",')
  ('equal'   , '"is_error": false}')
```
Char (3 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-requ'...)
  ('stripped', "<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit from trackin"...)
  ('equal'   , '", "is_error": false}')
```
Gated (3 spans):
```
  ('equal'   , '{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-requ'...)
  ('stripped', "<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit from trackin"...)
  ('equal'   , '", "is_error": false}')
```
  → no injected spans remaining (all phantom-gated or no real injects in this case)
Fidelity: char=orig_ok=True fwd_ok=True | gated=True

#### R4: synthetic multi-space/tab whitespace-collapse test
o_text: `'key1:  value1\n\nkey2:\tvalue2\nkey3:   value3'`
f_text: `'key1:  value1\n\nkey2:\tvalue2_changed\nkey3:   value3'`

Word (4 spans):
```
  ('equal'   , 'key1: value1 key2:')
  ('stripped', 'value2')
  ('injected', 'value2_changed')
  ('equal'   , 'key3: value3')
```
Char (3 spans):
```
  ('equal'   , 'key1:  value1\n\nkey2:\tvalue2')
  ('injected', '_changed')
  ('equal'   , '\nkey3:   value3')
```
Gated (3 spans):
```
  ('equal'   , 'key1:  value1\n\nkey2:\tvalue2')
  ('equal'   , '_changed')
  ('equal'   , '\nkey3:   value3')
```
  → no injected spans remaining (all phantom-gated or no real injects in this case)
Fidelity: char=orig_ok=True fwd_ok=True | gated=False

## Summary

### Level 1 (char-level): fixes YELLOW boundary
- Word-level splits on whitespace → JSON `\\n` is not whitespace → single-word tokens →
  SequenceMatcher 'replace' → common prefix in both stripped (yellow) AND injected (green).
- Char-level finds exact boundary → common prefix = equal, only changed suffix colored.
- Residual: char-level has LCS suboptimal alignment → phantom green on `\"\\, is_error: f\"` suffix.

### Level 2 (char-level + gating): fixes residual phantom GREEN
- Gate: injected span with fn=unknown (no strip/inject marker) → reclassify equal (grey).
- Correctly removes `\"\\, is_error: f\"` phantom from the bug case.
- ⚠️ Known limitation: 144 real 'unknown' msg-injects in live logs would also be suppressed
  (dot-replacements for haiku calls, file-path injects, sidecar markers).
  Only `_apply_bg_exit_strip` (bg-done) reliably avoids gating.

### Whitespace fidelity
- Word-level `' '.join(...)` collapses multi-space/tab; char-level/gated preserve exactly.
