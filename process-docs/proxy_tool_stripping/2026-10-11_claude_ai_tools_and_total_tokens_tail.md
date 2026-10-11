# claude.ai connector tools and the trailing total_tokens line, 2026-10-11

Two proxy changes, both observed on 2026-10-11 in the logs of Opus main `opus_monitor_cc_1791721685`, the
Sonnet worker `pdfwf` and the Haiku `pdf-kuepper-*` workers. Related areas: `proxy` (module layout), `proxy_dual_log`
(how stripped spans are recorded).

## Change 1: tools whose name starts with `mcp__claude_ai_` are removed

### Observation

The user's claude.ai account connectors deliver tool entries to every model family through the proxy.
`~/.claude.json` key `claudeAiMcpEverConnected` lists Gmail, Google Drive, Claude Code Remote and Claude Docs, but only
Claude Docs delivers tool entries directly (`mcp__claude_ai_Claude_Docs__batch`, `__guide`, `__update`). The other
connectors show up as deferred tools in a system-reminder that the proxy already strips. The entries arrive with
`description: ""` (the existing description strip empties them) and `defer_loading: true`, so the entries themselves
stay and cost tokens.

Observed Opus tool list at request index 3 (19 tools, original order):
`Agent, Artifact, AskUserQuestion, Bash, Edit, ListAgents, Read, ReportFindings, ScheduleWakeup, SendFeedback, Skill,
ToolSearch, Workflow, Write, mcp__claude_ai_Claude_Docs__batch, mcp__claude_ai_Claude_Docs__guide,
DeferredToolPlaceholder, mcp__claude_ai_Claude_Docs__update, advisor`. Forwarded before this change: 9 tools
(`Bash, Edit, Read, Skill, Write` plus the three connector tools plus `advisor`). The Haiku worker log shows request
index 2 with 5 tools and index 3 adding the three connector tools (tools_delta 5-7). After this change the same input
yields `Bash, Edit, Read, Skill, Write, advisor`.

### Decision (user)

Remove every tool whose name starts with `mcp__claude_ai_`. A prefix rule, so future connectors are covered without list
maintenance. No other `mcp__` tool is touched.

### Implementation

`src/proxy/tools.py`: `_BLOCKED_TOOL_PREFIXES` is a module-local constant (only this module uses it, so it does not go to
`constants.py`). `_is_blocked_tool(name)` is true for a `TOOL_BLOCKLIST` member or a prefix match, and
`_strip_unused_tools` uses it for both the kept list and `removed_names`. The addon calls `_strip_unused_tools` in the
post-fixation pipeline, so fixation, MCP schema injection and cache breakpoints see the already reduced list.

Not changed on purpose:
- `_strip_blocked_tool_references` (tool_reference blocks inside tool results) still matches `TOOL_BLOCKLIST` only. In the
  Opus original log, 306 lines contain `tool_reference` and none names an `mcp__claude_ai_` tool. Hypothesis: if a past
  ToolSearch result ever references such a tool, the API could reject the dangling reference; ToolSearch itself is
  blocklisted, which is why this was not observed.
- The tool strip is recorded in the stripped log as `tool_w.<name>` whole-tool removals derived from the original/forwarded
  diff, so no attribution code or `strip_vocab` entry is needed.

### `advisor` (not stripped)

The entry is `{"type": "advisor_20260301", "name": "advisor", "model": "claude-opus-5-5", "defer_loading": true}`, an
Anthropic server tool, not an MCP tool. The request carries the beta header `advisor-tool-2026-03-01`. By that name it is
the advisor feature: the executor model can consult a stronger model inside the request. It reaches the Opus main session
and is kept untouched; a test pins that the entry survives byte-identical.

## Change 2: the trailing `<total_tokens>` line is stripped from system messages that carry content

### Observation

CC appends `<total_tokens>N tokens left</total_tokens>` as the last text of a `role=system` message. When that message is
only the tag, `_apply_role_system_strip` replaces it with `"."`. That pass skips three kinds of messages (str content
starting with `[Truncated:`, str content starting with `The user sent a new message while you were working:`, any content
with a top-level `<task-notification>`), and the tag survived on the task-notification ones.

Observed original (Opus log, request 111, message 318, list form with `cache_control` on the single block; request 113
carries the same message as a plain string, because CC only keeps the block form on the last message):

```
[SYSTEM NOTIFICATION - NOT USER INPUT]\nThis is an automated ... consent.\n\n<task-notification>\n<task-id>bt3i3mnoz</task-id>\n...</task-notification>\n\n<total_tokens>14985715 tokens left</total_tokens>
```

Forwarded before: `background done — check worker or other process\nOutput: <tasks dir>/bt3i3mnoz.output\nID: bt3i3mnoz\n\n<total_tokens>14985715 tokens left</total_tokens>`.
Forwarded now: the same text ending at `ID: bt3i3mnoz`.

Scan of the 40 newest forwarded logs on 2026-10-11: surviving non-bare role-system messages with the tag were all
wake-up text, 5 hits in the Opus main log (3 distinct messages, repeated in deltas) and 2 in worker `viewerbg2`. Workers
are affected too.

Request 68 is a variant: one message with three task notifications, each preceded by the notice paragraph, and the tag at
the very end. The task-notification pass leaves the notice paragraphs and three wake-up texts in place (existing
behavior, unchanged here); the end-anchored tail rule removes only the final tag, so this case needed no special handling.

### Implementation

- `src/proxy/strip_total_tokens_tail.py`: `_strip_total_tokens_tail(content)`. For a string, or the last block of a list
  when that block is a text block, it matches `<total_tokens>\d+ tokens left</total_tokens>\s*\Z`. The text before the
  match is stripped of trailing newlines and must contain non-whitespace, otherwise nothing changes (a bare marker is the
  role-system nuke's job). Exactly one tail is removed; the removed text includes the separating newlines, e.g.
  `"\n\n<total_tokens>14985715 tokens left</total_tokens>"`.
- `src/proxy/message_passes_simple.py`: `_TOTAL_TOKENS_TAIL_SPEC` (roles `{"system"}`, marker guard on the closing tag at top
  level, mod name `stripped_total_tokens_tail`) and `_apply_total_tokens_tail_strip`.
- `src/proxy/rules.py`: the pass runs directly after `_apply_first_pass`, so the task notification is already rewritten
  to the wake-up text when the tail is cut. Position does not matter for span composition: every pass records ops
  relative to its own input and `compose_block` applies them in order.
- Roles: `system` only. User text, assistant text and tool results that quote the tag are never touched (test TL07).
- No `strip_vocab.RULES` or `_MSG_CODE_TO_FN` entry was added. A tail chunk would attribute to `TT` only by the marker
  `</total_tokens>`, and the same marker is inside every bare-marker nuke chunk that currently counts as unattributed in
  the audit tooling, so a `TT` rule would silently move those into an effective bucket. In the dual log a stripped tail
  inside a task-notification message is attributed through the joined chunk, which starts with the task notification or
  the notice paragraph (code `TN` or `SNP`; read from `attribute_chunk` and `_record_stripped_msg_block`, not covered by a test); a tail on any other surviving system message would be labelled `RS` by
  `_record_stripped_msg_block`, which labels every non-task-notification system message `RS`. That label is cosmetic.

### Scope correction found during implementation

The user chose the broader rule (all surviving system messages, motivated by the observed `[Truncated:` messages that end
with the tag). The `[Truncated:` messages in the logs are all list-shaped (`system`, `list`, 2000 in the kuepper-101 log
alone), while the role-system skip only protects string content, so they are nuked to `"."` as a whole. In the forwarded
log of that worker 0 such messages survive. The tail rule therefore changes nothing for them; test TL04 pins that
list-shaped `[Truncated:` messages are still nuked whole. The broader role gate still costs nothing and covers a
string-shaped `[Truncated:` or mid-turn-user message if one ever appears (hypothesis, not observed). Effective scope in
production today: wake-up messages built from task notifications.

### Connector instructions inside `[Truncated:` messages (out of scope, noted)

The original `[Truncated:` messages of the pdf workers do not only hold the Read truncation notice and the tag. Between
them sits text from the claude.ai Claude Docs connector, e.g. `... answer ONLY with a doc comment under that root
(`create` an utterance, parent `<root id>`) — no artifact/platform comment tool: that relay thread is resolved and never
reaches the doc; an edit asked there → `update` with `answering: "<root id>"`.` Because those messages are nuked whole
by the role-system strip, the text does not reach the API today. If the `[Truncated:` skip is ever extended to list
content, this connector text would be forwarded with it. Not handled here.

## Tests

`dev/proxy/test_strip_fix.py` (strand runner), two new case modules, 14 new strands, suite 130/130 on 2026-10-11:
- `test_strip_fix_cases_claude_ai_tools.py` (CA01-CA05): observed 19-tool Opus list; kept exactly
  `Bash, Edit, Read, Skill, Write, advisor`, 13 removed; `advisor` identical; an unrelated `mcp__` tool kept (name is
  synthetic, no other `mcp__` tool exists in the observed logs); a not-yet-seen connector name removed through the prefix;
  a clean list returns the same payload object.
- `test_strip_fix_cases_total_tokens_tail.py` (TL01-TL09), run through the real `apply_modification_rules` where the
  pipeline matters: request 111 list shape with `cache_control`, request 113 string shape, request 68 three-notification
  shape, `[Truncated:` list shape still `"."`, bare marker and nudge-plus-tag shapes still `"."`, non-system roles
  untouched, pass bookkeeping plus idempotence, span composition (stripped span equals the tail, equal span equals the
  kept text, no injected span).
- Fidelity check: with the `src` changes stashed, CA01, TL01 and TL03 fail, and TL01's actual output is byte-identical to
  the forwarded text observed in the log.
- Replay: the real pipeline over original requests 68, 111, 113, 167, 169, 250 and 302 of the Opus log leaves 0 system
  messages ending in the tag (62 to 284 per request before).
- Regression: `dev/proxy_dual_log/proxy_176_strip_tests.py` 9/9, `dev/proxy/test_role_keyed_rules.py` 6/6,
  `dev/proxy/test_sidecar_delta_chain.py` 3/3, `dev/proxy_dual_log/test_composition_invariant` 12/12.

## How a change goes live

Proxies run from frozen copies. `claude_proxy_start.sh` (main session) and the iterative-dev plugin's `worker_proxy.sh`
(each worker spawn) run `copy_proxy_live.sh`, which copies `src/{__init__,constants,monitor_root}.py` and `src/proxy/`
into `src/logs/.proxy_live_<uid>` and starts `mitmdump -s` from that copy. Workers copy from the `MONITOR_CC_ROOT` that
line 3 of `/tmp/.monitor_cc_proxy_<session id>` holds, which is the main checkout (branch `integration` on 2026-10-11),
not a worktree. So:
- The change must be merged into the main checkout before any new proxy can pick it up.
- Every proxy already running, including the main session's, keeps the old code until it is restarted.
- A freshly spawned worker gets the new code. The main Opus session needs a restart through `claude_proxy_start.sh`.

Live check (not run by this session): after the merge, spawn a fresh Haiku worker with a task that runs a few requests.
In `api_requests_worker_<id>_<name>_<ts>_forwarded.jsonl` no `tools_delta` entry and no `counts.tools` entry may contain
an `mcp__claude_ai_` tool (the old log shows them arriving at request index 3). The matching `_stripped.jsonl` shows the
three tools as whole-tool removals. For the tail, a worker that waits on a background Bash task must show the wake-up
text without `<total_tokens>` in the forwarded log and the tail as a stripped span in `_stripped.jsonl`.
