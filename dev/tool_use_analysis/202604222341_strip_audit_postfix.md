# Strip Audit — 2026-04-22 23:41

Source: `api_requests_opus_monitor_cc_1776891409.jsonl`
Opus entries: 43  |  Non-opus (skipped): 2

## Rule Catalog

### SR Templates (src/proxy/strip_sr.py:_SR_TEMPLATES)
| rule (modifications name) | template_id | identifier (startswith) | mode |
|---|---|---|---|
| `stripped_task_tools_nag` | `task-tools-nag` | `The task tools haven't been used recently` | full |
| `stripped_pyright_diagnostics` | `pyright-diagnostics` | `<new-diagnostics>` | full |
| `stripped_deferred_tools_sr` | `deferred-tools` | `The following deferred tools are now available via ToolSearch` | full |
| `stripped_user_interrupt_sr` | `user-interrupt` | `The user sent a new message while you were working:` | partial |
| `stripped_all_sr_msg0` | `system-notification` | `[SYSTEM NOTIFICATION - NOT USER INPUT]` | full |
| `stripped_all_sr_msg0` | `file-modified` | `Note: ` | full |
| `stripped_claudemd_sr` | `claudemd-contents` | `Contents of ` | full |
| `stripped_all_sr_msg0` | `date-changed` | `The date has changed.` | full |
| `stripped_skills_sr` | `skills-available` | `The following skills are available` | full |
| `removed_plan_mode_sr` | `plan-mode` | `Plan mode ` | full |

### Non-SR Rules
| rule | tag / literal | notes |
|---|---|---|
| `trimmed_task_notification` | `<task-notification>` | strips full TN block; chunk starts with TN tag |
| `stripped_rejection_message` | `(rejection marker stripped by proxy)` | replaces rejection message with literal |
| *(none — rolled back)* | `<persisted-output>` | no rule; always SUSPECT |

### Attribution Note
Chunk→rule attribution inverts the proxy capture logic: `_find_system_reminder_blocks(content, MARKER)` finds SR blocks containing MARKER anywhere. Attribution checks each chunk for marker substrings in priority order. `stripped_all_sr_msg0` (Final-Pass) never writes `stripped_msg_removed` — always shows as inert or triggers Indexed-no-chunks when the index has no tracked chunks.

## Delta Log

REQ #1  [22:56:58]  msg_count=0→1  diff=[+0]
  EFFECTIVE STRIPS:
    stripped_claudemd_sr | msg[0] | 1 chunk | total 1,797 chars
      chunk[0] head="<system-reminder>↵As you answer the user's questions, you can use the following context:↵# claudeMd↵Codebase and user in"
    stripped_deferred_tools_sr | msg[0] | 1 chunk | total 768 chars
      chunk[0] head="<system-reminder>↵The following deferred tools are now available via ToolSearch. Their schemas are NOT loaded — calling "
    stripped_skills_sr | msg[0] | 1 chunk | total 4,287 chars
      chunk[0] head="<system-reminder>↵The following skills are available for use with the Skill tool:↵↵- update-config: Use this skill to co"

REQ #2  [22:57:05]  msg_count=1→3  diff=[+1, +2]
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #3  [22:58:06]  msg_count=3→5  diff=[+3, +4]
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #4  [22:58:28]  msg_count=5→7  diff=[+5, +6]
  ⚠ SUSPECT: <task-notification> in raw_payload — `trimmed_task_notification` did not fire
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #5  [23:02:34]  msg_count=7→9  diff=[+7, +8]
  ⚠ SUSPECT: <task-notification> in raw_payload — `trimmed_task_notification` did not fire
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #6  [23:04:11]  msg_count=9→9  diff=[~8 modified ×1]
  ⚠ SUSPECT: <task-notification> in raw_payload — `trimmed_task_notification` did not fire
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #7  [23:05:05]  msg_count=9→11  diff=[+9, +10]
  ⚠ SUSPECT: <task-notification> in raw_payload — `trimmed_task_notification` did not fire
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #8  [23:05:53]  msg_count=11→11  diff=[~10 modified ×1]
  ⚠ SUSPECT: <task-notification> in raw_payload — `trimmed_task_notification` did not fire
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #9  [23:06:02]  msg_count=11→13  diff=[+11, +12]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  EVALUATED BUT INERT:
    trimmed_task_notification | marker gated but 0 chunks captured
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #10  [23:06:14]  msg_count=13→15  diff=[+13, +14]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #11  [23:06:40]  msg_count=15→17  diff=[+15, +16]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #12  [23:09:07]  msg_count=17→19  diff=[+17, +18]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #13  [23:09:15]  msg_count=19→21  diff=[+19, +20]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[20] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #14  [23:13:23]  msg_count=21→23  diff=[+21, +22]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #15  [23:16:17]  msg_count=23→23  diff=[~22 modified ×1]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #16  [23:18:51]  msg_count=23→25  diff=[+23, +24]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #17  [23:19:07]  msg_count=25→27  diff=[+25, +26]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #18  [23:20:44]  msg_count=27→29  diff=[+27, +28]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #19  [23:20:56]  msg_count=29→31  diff=[+29, +30]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #20  [23:21:03]  msg_count=31→33  diff=[+31, +32]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #21  [23:21:06]  msg_count=33→35  diff=[+33, +34]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #22  [23:21:10]  msg_count=35→37  diff=[+35, +36]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[20] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[36] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  EVALUATED BUT INERT:
    trimmed_task_notification | marker gated but 0 chunks captured
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #23  [23:21:15]  msg_count=37→39  diff=[+37, +38]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #24  [23:22:55]  msg_count=39→41  diff=[+39, +40]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #25  [23:23:00]  msg_count=41→43  diff=[+41, +42]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #26  [23:23:02]  msg_count=43→45  diff=[+43, +44]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #27  [23:26:02]  msg_count=45→47  diff=[+45, +46]
  EFFECTIVE STRIPS:
    trimmed_task_notification | msg[46] | 1 chunk | total 406 chars
      chunk[0] head="<task-notification>↵<task-id>bfjvsrmpj</task-id>↵<tool-use-id>toolu_01EdfmMHBunn3edcTPSTjFnE</tool-use-id>↵<output-file>"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #28  [23:26:05]  msg_count=47→49  diff=[+47, +48]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #29  [23:26:08]  msg_count=49→51  diff=[+49, +50]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #30  [23:29:08]  msg_count=51→53  diff=[+51, +52]
  EFFECTIVE STRIPS:
    trimmed_task_notification | msg[46] | 1 chunk | total 406 chars
      chunk[0] head="<task-notification>↵<task-id>bfjvsrmpj</task-id>↵<tool-use-id>toolu_01EdfmMHBunn3edcTPSTjFnE</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[52] | 1 chunk | total 395 chars
      chunk[0] head="<task-notification>↵<task-id>b80sfujsp</task-id>↵<tool-use-id>toolu_015kypEtQFUNshurnksFLhik</tool-use-id>↵<output-file>"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #31  [23:29:11]  msg_count=53→55  diff=[+53, +54]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[20] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[36] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[54] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #32  [23:29:13]  msg_count=55→57  diff=[+55, +56]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #33  [23:32:13]  msg_count=57→59  diff=[+57, +58]
  EFFECTIVE STRIPS:
    trimmed_task_notification | msg[46] | 1 chunk | total 406 chars
      chunk[0] head="<task-notification>↵<task-id>bfjvsrmpj</task-id>↵<tool-use-id>toolu_01EdfmMHBunn3edcTPSTjFnE</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[52] | 1 chunk | total 395 chars
      chunk[0] head="<task-notification>↵<task-id>b80sfujsp</task-id>↵<tool-use-id>toolu_015kypEtQFUNshurnksFLhik</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[58] | 1 chunk | total 395 chars
      chunk[0] head="<task-notification>↵<task-id>bphrsnzu7</task-id>↵<tool-use-id>toolu_01AYXvGYYd9QArLZ7wbRLvXQ</tool-use-id>↵<output-file>"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #34  [23:32:17]  msg_count=59→61  diff=[+59, +60]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #35  [23:32:25]  msg_count=61→63  diff=[+61, +62]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[20] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[36] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[54] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #36  [23:32:41]  msg_count=63→65  diff=[+63, +64]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #37  [23:32:44]  msg_count=65→67  diff=[+65, +66]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #38  [23:35:15]  msg_count=67→69  diff=[+67, +68]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #39  [23:35:21]  msg_count=69→71  diff=[+69, +70]
  EFFECTIVE STRIPS:
    stripped_task_tools_nag | msg[12] [tool_result:Read] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[20] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[36] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[54] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
    stripped_task_tools_nag | msg[70] [tool_result:Bash] | 1 chunk | total 517 chars
      chunk[0] head="<system-reminder>↵The task tools haven't been used recently. If you're working on tasks that would benefit from tracking"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #40  [23:38:23]  msg_count=71→73  diff=[+71, +72]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #41  [23:40:21]  msg_count=73→73  diff=[~72 modified ×1]
  EFFECTIVE STRIPS:
    trimmed_task_notification | msg[46] | 1 chunk | total 406 chars
      chunk[0] head="<task-notification>↵<task-id>bfjvsrmpj</task-id>↵<tool-use-id>toolu_01EdfmMHBunn3edcTPSTjFnE</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[52] | 1 chunk | total 395 chars
      chunk[0] head="<task-notification>↵<task-id>b80sfujsp</task-id>↵<tool-use-id>toolu_015kypEtQFUNshurnksFLhik</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[58] | 1 chunk | total 395 chars
      chunk[0] head="<task-notification>↵<task-id>bphrsnzu7</task-id>↵<tool-use-id>toolu_01AYXvGYYd9QArLZ7wbRLvXQ</tool-use-id>↵<output-file>"
    trimmed_task_notification | msg[72] | 1 chunk | total 407 chars
      chunk[0] head="<task-notification>↵<task-id>b2pfot4wq</task-id>↵<tool-use-id>toolu_01DoMjb7UubJTz7X23VawwLE</tool-use-id>↵<output-file>"
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #42  [23:40:23]  msg_count=73→75  diff=[+73, +74]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

REQ #43  [23:40:25]  msg_count=75→77  diff=[+75, +76]
  ⚠ LEAK: <task-notification> still in raw_payload after `trimmed_task_notification` fired
  ⚠ SUSPECT: <persisted-output> in raw_payload — no strip rule (rolled back)

## Summary

- Total REQs (opus): 43
- REQs with effective strips: 11
- Inert rule firings (gated but 0 chunks): 2
- Indexed-no-chunks occurrences (Final-Pass tracking gap): 0
- Suspect tags (no rule fired): 47 occurrences
- Leaked tags (rule fired, tag survived): 35 occurrences
