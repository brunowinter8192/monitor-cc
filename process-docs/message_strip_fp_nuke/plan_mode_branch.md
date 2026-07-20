# Message-Strip False Positive — File Reads Nuked to a Placeholder

Session 2026-06-22/23 (Opus). **Root cause confirmed (ground-truth), fix applied, live-verify open for the next session.**

## Problem (Symptom)

File reads via the Read tool came back as a nuked placeholder instead of content. Reproducible on the proxy-cache pipeline documentation file: reading it fully → nuked; two sibling pipeline docs read normally. Cause layer: the running Monitor proxy modifies outgoing Anthropic requests via `apply_modification_rules()` (`rules.py`); the Read tool_result travels as part of the next request through the proxy and gets replaced → the model only sees the placeholder.

## Root Cause — CONFIRMED: `_apply_first_pass` Plan-Mode Branch

NOT `_apply_role_system_strip` (that was the suspicion from the previous session, refuted — see below). The culprit is the **plan-mode branch** in `_apply_first_pass` (`message_passes.py`).

Mechanism:
1. Detection via `_content_contains(content, "Plan mode is active")` — this function **descends into `tool_result` content** (not top-level only).
2. The proxy-cache pipeline doc contains the string `"Plan mode is active"` **exactly once**, on **line 13** (documenting the strip rule `removed_plan_mode_sr`: "text-block drop on \"Plan mode is active\""). Sits within lines 1-104.
3. The branch fires on the documented string, even though there is no real `<system-reminder>` plan-mode block present. `_strip_plan_mode_blocks` finds no real block → the `else` branch **unconditionally replaces the whole message** (`"(plan-mode reminder stripped by proxy)"`), and the Read content is gone.

This explains the content-dependent bisection from the prior session (only lines 1-104 nuked, the rest survived): only lines 1-104 contain the marker (line 13).

### Ground Truth — `_stripped.jsonl` fn_map (session `opus_monitor_cc_1782163188`)

`fn_map` attributes the responsible function per strip entry AT WRITE TIME. Scan over all 41 requests:

| Request (msg idx) | Content | fn_map |
|---|---|---|
| 82a75a0b (msg 20) | pipeline-doc Read (numbered) | `_apply_first_pass` |
| d4022f94 (msg 22) | pipeline-doc head/wc | `_apply_first_pass` |
| 8dccc584 (msg 33) | pipeline-doc file-type/od | `_apply_first_pass` |
| bb3858c5 (msg 46) | pipeline-doc trigger-lines | `_apply_first_pass` |
| f996b733 (msg 64) | pipeline-doc Read | `_apply_first_pass` |

`_apply_role_system_strip` hits ONLY genuine noise in the same log: the "task tools haven't been used recently" nag and `<new-diagnostics>` blocks (CC 2.1.176 delivers these as their own `role=system` messages). No FP at role_system. role=system is consistently noise → the content-blind `.` nuke there is intentional and correct.

### Branch-Marker Check on the Pipeline Doc

`grep -c` over the pipeline doc for the `_apply_first_pass` branch markers: `Plan mode is active` = **1** (line 13), `task tools haven` = 0, `deferred tools are now available via ToolSearch` = 0, `user sent a new message while you were working` = 0. Only the plan-mode branch could match.

### Why Only Plan-Mode FP-Nukes, Not the Other Branches

The other `_apply_first_pass` branches also gate via `_content_contains` (substring, descends into tool_result), but strip via `_strip_system_reminder` (template-anchored) — if no real SR block is found, the content stays unchanged (`new_msg["content"] != old_content` is False → no change). The plan-mode branch is the only one with a destructive `else` that replaces the whole message when no real block is found. That is the defect.

## Fix — Applied (this session, direct, no worker)

- `message_passes.py`: the plan-mode branch removed entirely from `_apply_first_pass` (the first `if` removed, the following `elif` → `if`); the unused `_strip_plan_mode_blocks` import removed; the function's doc comment updated.
- `rules.py`: `_passes` = all 10 passes (incl. `_apply_role_system_strip` = #1 back on); the `_dedup_wakeup_blocks` call re-enabled; the temp-disable comment removed.
- No capability loss: real plan-mode SR blocks (if they ever occur) are still stripped by `_apply_final_sr_pass` via template-anchored matching, which does not FP-match on doc strings. The user never uses plan mode anyway.
- `py_compile` clean. Committed + pushed to `main`.

## Open — Live-Verify Next Session

The proxy only loads the new source after a restart (fresh live copy). Next session:
1. Read the full pipeline doc → no more nuke (placeholder gone, real content there).
2. role=system noise (task-tools-nag, new-diagnostics) still correctly stripped to `.`.
3. Intended strips (SR noise, BG, etc.) work, no duplicate wake-up blocks (dedup active).
4. Afterward: correct the current-state docs for the proxy-cache pipeline (the `removed_plan_mode_sr` section — rule removed), then resume the interrupted doc-drift count audit for the pipeline docs.

## Relevant Symbols / Paths

- `_apply_first_pass()` (`src/proxy/message_passes.py`) — elif chain, plan-mode branch removed
- `_content_contains()` (`src/proxy/payload_helpers.py`) — substring detection, descends into tool_result (reason for the FP gate)
- `_strip_plan_mode_blocks()` (`src/proxy/strip_sr.py`) — stays defined, no longer imported/used
- `_apply_role_system_strip()` (`src/proxy/message_passes.py`) — content-blind `.` nuke on role=system, correct, NOT the FP
- `apply_modification_rules()` / `_passes` (`src/proxy/rules.py`) — pass orchestrator, all 10 + dedup active
- Ground-truth log: `src/logs/dual_log/api_requests_opus_monitor_cc_1782163188_stripped.jsonl` (field `fn_map`)
- Commit history: `40e071d` (introduced the role=system strip — refuted as the FP suspect)
