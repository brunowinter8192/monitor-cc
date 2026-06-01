# Proxy Tool Stripping — CC Version Tool Diff

Investigation track. Captures what CC sends to the API across versions, whether the proxy
over/under-strips, and the display-semantics confusion. Status: findings captured, root mechanism
confirmed, version-vs-model question OPEN (test pending = spawn worker on CC 2.149).

## Problem / Concern (user framing)

Pipeline `CC → proxy → API`. The Monitor PROXY pane shows primarily `proxy → API` (forwarded tools)
plus yellow-bg = `CC → proxy` that the proxy does NOT forward to the API. The worry: on CC version
updates we don't know whether we LOSE tools or strip too much / too little. The CC UI changes between
versions, but the proxy reacts identically every time. Open question: are tools being lost by our
stripping, or does CC simply send less to the API now (handling more server-side)? — answerable with
the proxy logs.

## Display semantics (decoded from screenshots 2026-06-01)

| BG color | Label | Meaning |
|---|---|---|
| dark blue | `[STRIPPED]` | FORWARDED tool; its description/schema was stripped to save tokens. Name + (empty) schema still sent to the API. These are the "N defs". |
| yellow/olive | `[STRIPPED]` | Blocklist-REMOVED; not sent to API. `TOOL_BLOCKLIST` (src/constants.py:145) via `_strip_unused_tools` (src/proxy/tools.py). |
| yellow/olive | `[DEFERRED]` | CC's OWN deferral — listed in CC's deferred-tools system-reminder, loadable via ToolSearch (which the proxy ALSO strips, blocklist). |

**Ambiguity flagged by user:** `[STRIPPED]` means TWO different things depending on bg color
(schema-stripped-but-forwarded vs blocklist-removed). Display-clarity fix candidate.

## Finding: forwarded tool set differs by CC VERSION (+ model)

Evidence = api_requests logs, fields `tools_names` (forwarded post-strip) / `stripped_unused_tools_names`
(blocklist-removed) / `deferred_tools_names` (CC-deferred).

| | Opus — CC v2.149 | Worker — CC v2.1.114 (sonnet) |
|---|---|---|
| FORWARDED defs | Bash, Edit, Read, Skill, Write (5) | Bash, Edit, **Glob, Grep**, Read, Skill, Write (7) |
| STRIPPED (blocklist) | Agent, AskUserQuestion, ScheduleWakeup, ToolSearch | Agent, ScheduleWakeup, ToolSearch |
| DEFERRED (CC) | Cron{Create,Delete,List}, Enter/ExitPlanMode, Enter/ExitWorktree, LSP, Monitor, NotebookEdit, PushNotification, RemoteTrigger, Task{Create,Get,List,Output,Stop,Update}, WebFetch, WebSearch, +2 mcp Google Drive | AskUserQuestion, Cron*, Enter/ExitPlanMode, Enter/ExitWorktree, LSP, Monitor, NotebookEdit, PushNotification, RemoteTrigger, Task*, WebFetch, WebSearch |
| **Grep / Glob** | **ABSENT entirely** (not fwd, not stripped, not deferred) | **FORWARDED (active)** |
| Workflow | absent | absent |

Key diffs 114 → 149:
- **Grep/Glob:** active on 114 → vanished entirely on 149. The proxy does NOT strip them (not in blocklist) → their absence means CC 2.149 did not send them on the wire at all.
- **AskUserQuestion:** DEFERRED on 114 → active + blocklist-STRIPPED on 149. The active/deferred split shifted between versions.
- The 2 `mcp__claude_ai_Google_Drive__*` deferred entries on opus are env/account-specific, not version.

Logs cited (src/logs/):
- `api_requests_opus_monitor_cc_1780343936.jsonl` — opus, CC 2.149 (this session)
- `api_requests_opus_github_1780339047.jsonl` — opus, CC 2.149 (confirms cross-session, same 5)
- `api_requests_worker_f93afc17_rag-tab_1780345236.jsonl` — worker, CC 2.1.114 (7 incl Grep/Glob)

## Mechanics confirmed (proxy side — NOT the cause of the missing tools)

- `_strip_unused_tools` (src/proxy/tools.py:17) removes `TOOL_BLOCKLIST` names → yellow `[STRIPPED]`.
- `TOOL_BLOCKLIST` (src/constants.py:145) does NOT contain Grep/Glob/Workflow → the proxy never strips them. Their absence on 149 is upstream (CC), not the proxy.
- `_extract_deferred_tool_names` (tools.py:31) parses CC's deferred-tools SR → yellow `[DEFERRED]`.
- Log entry built from MODIFIED (post-strip) payload (addon.py:122). `tools_names` = exactly what reaches the model. Confirmed: opus's own Grep tool-call fails with "No such tool available: Grep".
- Display data: parser.py `setdefault('stripped_unused_tools_names')` / `setdefault('deferred_tools_names')`; render_sections.py:168-175 renders STRIPPED/DEFERRED.

## Hypotheses

| # | Hypothesis | Status | Evidence |
|---|---|---|---|
| H1 | CC removed Grep/Glob from the wire between 114 and 149 (server-side handling or different exposure) | ACTIVE — primary | opus(149) absent vs worker(114) active; proxy demonstrably not the remover |
| H2 | Difference is model-dependent (opus vs sonnet), not version | Less likely | only known deltas are version AND model; discriminating test = spawn a SONNET worker on CC 2.149 |
| H3 | Our blocklist now over-strips tools CC newly made active (AskUserQuestion active on 149 but blocklisted) | OPEN | AskUserQuestion active+blocklisted on 149 |

## Plan (user roadmap, 2026-06-01)

1. (done/in-progress) finish underscore worker-detection fix.
2. idle MAIN discovery bug (separate — menubar drops idle main sessions of github/rag after a while).
3. **version update:** bump worker-cli default CC version → 2.149; spawn next worker; observe. If the 149-worker ALSO loses Grep/Glob → confirms H1 (version). If it retains them → H2 (model).
4. full proxy investigation: enumerate CC 2.149 wire tools vs 2.1.114, decide whether we over/under-strip, determine whether "missing" tools moved server-side. Deliver a version-robust stripping policy + display disambiguation of the two `[STRIPPED]` meanings.

## Open questions

- Does CC 2.149 handle Grep/Glob server-side, or simply not expose them at all on the wire?
- Is `TOOL_BLOCKLIST` still correct for 2.149 (AskUserQuestion is now active — do we still want it stripped)?
- Empty `#0.1` request (0msg, BP:0) — opens completely empty in the Monitor UI. What is it (haiku/aux request)? Display-edge or real.
- Display: disambiguate schema-stripped-forwarded (dark blue) vs blocklist-removed (yellow) — same word `[STRIPPED]`.

## Status (executed 2026-06-02)

- **Version bump EXECUTED.** `tmux_spawn.sh` lines 518 (spawn) + 707 (revive) → `CLAUDE_BIN` default `claude-114` → `claude-149`. Workers now spawn on CC 2.1.149. Old wrappers claude-101/109/110/114 deleted + their installs cc-cache-fix-109/110/114 (321 MB) removed; only claude-149 remains.
- **PERSISTED (both cache + source).** Edit applied in the plugin CACHE (live) AND in the plugin SOURCE repo `/Users/brunowinter2000/Documents/ai/Meta/blank/src/spawn/tmux_spawn.sh` (lines 518+707; commit 261761c, pushed to github.com:brunowinter8192/Meta). The source repo dir is named `Meta/blank` (NOT `iterative-dev` — that mismatch is why earlier name-scoped searches missed it; `.claude-plugin/plugin.json` name = iterative-dev). Cache + source both at claude-149 → a future `plugin-publish` keeps them consistent. NOT run plugin-publish (cache already synced; avoids unnecessary MCP-server restart).
- **VERIFICATION PENDING.** Next worker spawned on 2.149 → check its proxy log: (a) version 2.1.149, (b) tools lack Grep/Glob (aligning with opus → confirms H1 = version, not model), (c) is `Workflow` present anywhere (forwarded/stripped/deferred) → resolves the Workflow mystery. Folds into the first worker spawn of the logging redesign (pxn7).
