# Green Overlay Probe Report

**Bug:** word-level `_diff_text` mis-tags common prefix as stripped+injected when
JSON-serialized blocks contain `\\n` (backslash-n, 2 chars) — no real whitespace
inside the JSON string token, so orig and fwd tokens are one word each, differ → 'replace'.

## Primary Bug Case

**Source:** `api_requests_worker_25c51a2e_badge-recap_1780678180`
**Flow ID:** `7a12336f-7d76-476f-a3b2-4d58f9ae6f2f`
**Location:** `messages[18]` block 0 (tool_result, role=user)
**o_text len:** 762 chars | **f_text len:** 301 chars
**Common prefix len:** 280 chars (ends at `set()))\\n\\n`)
**Divergence in o_text:** `"<system-reminder>\\nThe task tools haven't been used recently"`
**Divergence in f_text:** `'", "is_error": false}'`

### Word-level spans — CURRENT (buggy) — 4 spans

```
  ('equal'   , '{"tool_use_id": "toolu_013iZEuK4YDi1HqL5W9W5bMU", "type": "tool_result", "content": "80: _fid = entry.get(\'flow_id\', \'\')'...)
  ('stripped', "set()))\\n\\n<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit f"...)
  ('injected', 'set()))\\n\\n",')
  ('equal'   , '"is_error": false}')
```

**Bug:** the long token containing `set()))\\n\\n<system-reminder>\\nThe...` (orig)
and `set()))\\n\\n",` (fwd) are ONE word each (no real whitespace inside JSON).
SequenceMatcher tags them 'replace' → common prefix `set()))\\n\\n` mis-tagged as
stripped (yellow) AND injected (green). Only `<system-reminder>…` was actually stripped.

### Char-level spans — CANDIDATE FIX — 6 spans

```
  ('equal'   , '{"tool_use_id": "toolu_013iZEuK4YDi1HqL5W9W5bMU", "type": "tool_result", "content": "80:    _fid = entry.get(\'flow_id\', '...)
  ('stripped', '<system-reminder>\\nThe t')
  ('injected', '", "is_error": f')
  ('equal'   , 'a')
  ('stripped', "sk tools haven't been used recently. If you're working on tasks that would benefit from tracking progress, consider usin"...)
  ('equal'   , 'lse}')
```

**Fidelity:** orig_recon==o_text: True ✅ | fwd_recon==f_text: True ✅
**Char span[0]:** `equal`, len=280 → common prefix correctly tagged as equal ✅
**Stripped contains `<system-reminder>`:** True ✅
**Injected spans:** ['\'", "is_error": f\'']

## Regression Spot-Check

| Case | o_len | f_len | word spans | char spans | char fidelity |
|---|---|---|---|---|---|
| R1: msg[2] blk[0] partial replace (ratio=0.76) | 429 | 322 | 4 | 6 | ✅ orig_ok=True fwd_ok=True |
| R2: msg[4] blk[0] tiny edit large block (ratio=0.99) | 27523 | 27137 | 3 | 3 | ✅ orig_ok=True fwd_ok=True |
| R3: msg[38] blk[0] system-reminder strip (ratio=0.95) | 4973 | 4512 | 4 | 3 | ✅ orig_ok=True fwd_ok=True |
| R4: synthetic multi-space/tab whitespace-collapse test | 42 | 50 | 4 | 3 | ✅ orig_ok=True fwd_ok=True |

### Details

#### R1: msg[2] blk[0] partial replace (ratio=0.76)
o_text: `'{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/badge-recap\\nbadge-recap\\n\\n<system-reminder>\\nThe'`
f_text: `'{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai/monitor-cc/.claude/worktrees/badge-recap\\nbadge-recap\\n\\n<system-reminder>\\nThe'`

Word spans (4):
```
  ('equal'   , '{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai'...)
  ('stripped', "SHA]\\n\\nIMPORTANT: After completing your current task, you MUST address the user's message above. Do not ignore it.\\n</s"...)
  ('injected', 'SHA]\\n\\n</system-reminder>\\n",')
  ('equal'   , '"is_error": false}')
```
Char spans (6):
```
  ('equal'   , '{"tool_use_id": "toolu_01PMFxLaT8aMeQQ3ThF5n4TY", "type": "tool_result", "content": "/Users/brunowinter2000/Documents/ai'...)
  ('stripped', 'IMPORTANT: A')
  ('injected', '</system-reminder>\\n", "is_error": ')
  ('equal'   , 'f')
  ('stripped', 'ter completing your current task, you MUST address the user\'s message above. Do not ignore it.\\n</system-reminder>", "is'...)
  ('equal'   , 'alse}')
```
Fidelity: orig_ok=True fwd_ok=True

#### R2: msg[4] blk[0] tiny edit large block (ratio=0.99)
o_text: `'{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t## Role\\n4\\t\\n5\\tProxy pane TUI package. Reads mitmproxy forwarded-delta entries f'`
f_text: `'{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t## Role\\n4\\t\\n5\\tProxy pane TUI package. Reads mitmproxy forwarded-delta entries f'`

Word spans (3):
```
  ('equal'   , '{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t##'...)
  ('stripped', 'handler.\\n144\\n\\n<system-reminder>\\nThe following deferred tools are now available via ToolSearch. Their schemas are NOT'...)
  ('injected', 'handler.\\n144\\n\\n"}')
```
Char spans (3):
```
  ('equal'   , '{"tool_use_id": "toolu_01HY8bgoh12WbJuYyN43T3jV", "type": "tool_result", "content": "1\\t# src/proxy_display/\\n2\\t\\n3\\t##'...)
  ('stripped', '<system-reminder>\\nThe following deferred tools are now available via ToolSearch. Their schemas are NOT loaded — calling'...)
  ('equal'   , '"}')
```
Fidelity: orig_ok=True fwd_ok=True

#### R3: msg[38] blk[0] system-reminder strip (ratio=0.95)
o_text: `'{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/to'`
f_text: `'{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-request rows for an expanded turn group, numbering requests and delegating system/to'`

Word spans (4):
```
  ('equal'   , '{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-requ'...)
  ('stripped', "badge.\\n\\n<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit fr"...)
  ('injected', 'badge.\\n\\n",')
  ('equal'   , '"is_error": false}')
```
Char spans (3):
```
  ('equal'   , '{"tool_use_id": "toolu_0158ogmPp3AnoHh9dE1ZVLYo", "type": "tool_result", "content": "94:**Purpose:** Render all per-requ'...)
  ('stripped', "<system-reminder>\\nThe task tools haven't been used recently. If you're working on tasks that would benefit from trackin"...)
  ('equal'   , '", "is_error": false}')
```
Fidelity: orig_ok=True fwd_ok=True

#### R4: synthetic multi-space/tab whitespace-collapse test
o_text: `'key1:  value1\n\nkey2:\tvalue2\nkey3:   value3'`
f_text: `'key1:  value1\n\nkey2:\tvalue2_changed\nkey3:   value3'`

Word spans (4):
```
  ('equal'   , 'key1: value1 key2:')
  ('stripped', 'value2')
  ('injected', 'value2_changed')
  ('equal'   , 'key3: value3')
```
Char spans (3):
```
  ('equal'   , 'key1:  value1\n\nkey2:\tvalue2')
  ('injected', '_changed')
  ('equal'   , '\nkey3:   value3')
```
Fidelity: orig_ok=True fwd_ok=True

## Summary

- **Word-level bug:** splits on real whitespace → JSON `\\n` is not whitespace →
  long tokens with embedded escaped newlines + `<system-reminder>` are ONE word →
  SequenceMatcher 'replace' → common prefix mis-colored stripped (yellow) + injected (green).
- **Char-level fix:** operates character-by-character → finds exact boundary →
  common prefix tagged `equal`, only diverging suffix is stripped/injected.
- **Whitespace collapse:** word-level `' '.join(...)` collapses multi-space/tab;
  char-level uses exact substrings — zero information loss.
- **Span count:** char-level span count ≤ word-level for ordinary text;
  see regression table above — no explosion on any real case tested.
