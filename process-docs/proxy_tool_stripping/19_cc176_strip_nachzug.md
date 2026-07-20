# CC 2.1.176 Strip Follow-Up

## Structural Change in CC 2.1.176

CC 2.1.149 → 2.1.176 moved several content classes out of `role='user'` SR blocks into a new `role='system'` message:

| Content | until 2.1.149 | from 2.1.176 |
|---|---|---|
| Deferred-tools list (CronCreate…) | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (~9,559 chars) |
| Agent-types list | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (Opus) |
| Skills list | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (Opus) |
| Agent-types (Sonnet worker) | — | **still** as a standalone user SR (~2,353 chars) |

Additionally: a new built-in tool `Workflow` with a ~18.5k-char description, with no entry in `TOOL_BLOCKLIST`.

## Why the Drift Happened (the role==user Gate)

Every pass in the `_passes` list in `rules.py` is gated on `role == 'user'` — two patterns:

- `_apply_first_pass`: 6 `elif` branches, all with `msg.get("role") == "user"` as the first condition; the `else` appends unchanged.
- All other 7 passes: an explicit `if msg.get("role") != "user": continue` at the loop start.

A `role='system'` message hits every skip guard and passes through unchanged. The ~9,559-char message appeared in EVERY request (cached prefix, re-sent per request).

## The Four Fixes

### Fix 1 — Workflow in TOOL_BLOCKLIST

`"Workflow"` added to `TOOL_BLOCKLIST` (frozenset, `constants.py`). `_strip_unused_tools` removes it entirely. The description-strip phase (`_strip_tool_descriptions`) had already emptied the Workflow description text, but the tool dict (name + empty schema) was still forwarded.

### Fix 2 — `_apply_role_system_strip` (RS)

A new first pass in `_passes`. Condition: `role == 'system'` — no content marker, purely structural. `content → "."`. Idempotency guard: empty content and already-`"."` content are skipped.

**Attribution design (a decision made during this fix):** `_attribute_chunk` is content-marker-based and would be fragile for an unconditional role-based strip (future CC versions could deliver different content). Instead: role-based attribution directly in `_process_messages_section` (`strip_inject_delta.py`): when `om_norm.get("role") == "system"` → `code = 'RS'` (bypasses `_attribute_chunk`). `_MSG_CODE_TO_FN['RS'] = '_apply_role_system_strip'`. The strip_vocab.py `'RS'` entry has an empty marker array (no content marker planned or needed).

Both the strip condition AND the attribution condition depend on role, not content — consistent with the design intent "fire unconditional on role, regardless of content".

Log verification: a 9,559c role=system message confirmed in real worker logs.

### Fix 3 — `stripped_agent_types_sr` (AT)

Sonnet workers still get the agent-types list as a standalone `<system-reminder>` block in a `role='user'` message (~2,353 chars, `messages[0].content[1]`, starts with `<system-reminder>\nAvailable agent types for the Agent tool:`). Not affected by Fix 2 (role=user, not role=system).

Fix: a clean mirror of the skills strip in `_apply_cumulative_sr_strips`:
- A new template `'agent-types': ('Available agent types for the Agent tool', 'full')` in `strip_sr.py._SR_TEMPLATES`
- A `_MARKER_TO_TEMPLATE` entry: `'Available agent types for the Agent tool': 'agent-types'`
- The marker block in `_apply_cumulative_sr_strips` identical to the `_SKILLS_MARKER` block
- mod-name: `stripped_agent_types_sr`
- strip_vocab.py: `'AT': ('stripped_agent_types_sr', ['Available agent types for the Agent tool'])`
- strip_inject_delta.py `_MSG_CODE_TO_FN['AT'] = '_apply_cumulative_sr_strips'`

Attribution is content-marker-based (correct here: SR-wrapped and stable, unlike Fix 2).

Log verification: a 2,353c agent-types SR confirmed in real Sonnet-worker logs.

### Fix 4 — `stripped_bg_launch_ack` (BL) — Same Session, Not 176-Specific

Background-command launch acks (`"Command running in background with ID: <id>. Output is being written to: <path>. You will be notified when it completes. To check interim output, use Read on that file path."`) were not stripped. 54 occurrences in one session, pure noise (the completion injection notifies anyway).

New module `strip_bg_launch_ack.py`. A new pass `_apply_bg_launch_ack_strip` after `_apply_bg_exit_strip` (the background-strip group). Fast-path marker: `'running in background with ID'`. All 4 content shapes: str, list/text, list/tool_result-str, list/tool_result-list. Whole block content → `"."` (no substring excision, mirrors the role=system strip pattern and the rejection strip pattern). The original is captured in `pass_removed_by_idx` for dual-log attribution.

strip_vocab.py: `'BL': ('stripped_bg_launch_ack', ['running in background with ID'])`. `_MSG_CODE_TO_FN['BL'] = '_apply_bg_launch_ack_strip'`.

Not caused by CC 2.1.176 — occurrence at msg[63] confirmed in real logs.

## Files Changed

| File | Change |
|---|---|
| `src/constants.py` | `"Workflow"` added to `TOOL_BLOCKLIST` |
| `src/proxy/message_passes.py` | `_apply_role_system_strip` (new, first pass); the `_AGENT_TYPES_MARKER` block in `_apply_cumulative_sr_strips`; `_apply_bg_launch_ack_strip` (new) |
| `src/proxy/rules.py` | Import + `_passes` entries for all three new passes |
| `src/proxy/strip_sr.py` | Template `'agent-types'` + the `_MARKER_TO_TEMPLATE` entry |
| `src/proxy/strip_bg_launch_ack.py` | New module |
| `src/proxy/strip_vocab.py` | Codes RS, AT, BL |
| `src/proxy/strip_inject_delta.py` | RS/AT/BL in `_MSG_CODE_TO_FN`; role-based attribution for RS in `_process_messages_section` |

## Noise Audit (Session Scan, 2026-06-22)

After the four fixes, the session log (`api_requests_opus_monitor_cc_1782159415_original.jsonl`) was scanned for further uncovered CC-injected noise classes (distinct SR templates, role=system heads, recurring short tool_result content). Result: **no new uncovered noise type.**

| Noise class | Status |
|---|---|
| Task-tools-nag (`The task tools haven't been used recently`) | covered — in 176 as role=system → Fix 2 (RS); confirmed `.` at idx 18 in the log |
| deferred/agent-types/skills block | covered — Fix 2 (RS, Opus) + Fix 3 (AT, Sonnet worker) |
| bg-launch-ack | covered — Fix 4 (BL) |
| env-context SR (`As you answer… # userEmail`) | covered — the existing ENV rule |

What the scan otherwise shows as "recurring" (`(Bash completed with no output)` 57×, `monitor-cc` 59×, our own probe/git output, `idle X%`) is **our own tool output as conversation history** — real work, not strippable (lossy).

Deliberately NOT stripped (actionable, not pure noise): the Read-tool marker `[Truncated: PARTIAL view …]` and the `<persisted-output>` wrapper — both name the path/position of the full output.
