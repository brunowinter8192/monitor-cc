# Session Waste & Failed Calls Analysis — 2026-04-21 23:27

## Source JSONLs

- `src/logs/api_requests_opus_monitor_cc_1776797402.jsonl` (164 events, 147 tool_use blocks) — **Opus orchestrator**
- `src/logs/api_requests_worker_extract-tool-defs_1776798488.jsonl` (42 events, 47 tool_use blocks) — **Worker: extract-tool-defs**
- `src/logs/api_requests_worker_proxy-strip-plan_1776803655.jsonl` (41 events, 43 tool_use blocks) — **Worker: proxy-strip-plan**
- `src/logs/api_requests_worker_cli-consolidation_1776803661.jsonl` (74 events, 91 tool_use blocks) — **Worker: cli-consolidation**

Total sessions analyzed: 4. Total tool_use blocks: 328.

Session-JSONL token data sourced from `~/.claude/projects/` (response-side usage fields).

---

## Session Overview

### Time Range

Session start: 2026-04-21 20:50 local — end: 23:23 local (2h 33min)

### Token Totals (by source)

| Source | Input | Output | Cache Read | Cache Creation |
|--------|------:|-------:|-----------:|---------------:|
| opus (orchestrator) | 24,345 | 269,564 | 46,005,712 | 445,075 |
| worker:extract-tool-defs | 11,976 | 156,889 | 5,895,357 | 321,128 |
| worker:proxy-strip-plan | 13,551 | 50,390 | 4,435,668 | 257,844 |
| worker:cli-consolidation | 25,895 | 174,180 | 15,473,582 | 356,760 |
| **Total** | **75,767** | **651,023** | **71,810,319** | **1,380,807** |

> Cache Read dominates at **71.8M tokens** — 99.9% of all input-side token traffic is served from cache. Input tokens (75k) are the prefix-change overhead; actual new content per request is tiny.

### Proxy Request Counts

| Source | API Requests | Tool Calls |
|--------|-------------|------------|
| opus | 164 | 147 |
| worker:extract-tool-defs | 42 | 47 |
| worker:proxy-strip-plan | 41 | 43 |
| worker:cli-consolidation | 74 | 91 |
| **Total** | **321** | **328** |

### Tool Call Breakdown by Source

| Tool | opus | extract-tool-defs | proxy-strip-plan | cli-consolidation | Total |
|------|-----:|------------------:|-----------------:|------------------:|------:|
| Bash | 97 | 22 | 22 | 38 | 179 |
| Read | 15 | 19 | 9 | 24 | 67 |
| Edit | — | 3 | 5 | 16 | 24 |
| Write | 8 | 3 | — | 10 | 21 |
| worker_send | 15 | — | — | — | 15 |
| worker_spawn | 3 | — | — | — | 3 |
| Glob | — | — | 1 | 1 | 2 |
| Grep | — | — | — | 2 | 2 |
| Skill | 1 | — | — | — | 1 |
| git_check (MCP) | — | — | 1 | — | 1 |
| worker_merge | 1 | — | — | — | 1 |

Bash dominates at **179 calls (54.6% of all tool calls)**. Opus alone makes 97 Bash calls — more than any individual worker.

---

## Top-10 Waste Calls — Opus Only (ratio = input_chars / output_chars)

Excluded from ratio: Edit, Write, worker_send (content-driven, not shortenable via wrapper).

| Rank | Tool | Input chars | Output chars | Ratio | Pattern |
|-----:|------|------------:|-------------:|------:|---------|
| 1 | Bash | 123 | 3 | 41.0 | `git branch --show-current && git status --short \| head -20` |
| 2 | Bash | 142 | 4 | 35.5 | `worker-cli status cli-consolidation <project-path>` |
| 3–7 | Bash | 135 | 4 | 33.8 | `worker-cli status extract-tool-defs <project-path>` (×5) |
| 8 | Bash | 128 | 4 | 32.0 | `worker-cli status cli-consolidation <project-path>` |
| 9 | Bash | 951 | 31 | 30.7 | `bd comments add Monitor_CC-6ja "Session Progress: Phase A DONE..."` |
| 10 | Bash | 122 | 4 | 30.5 | `worker-cli status cli-consolidation <project-path>` |

All Top-10 are **Bash calls from opus**. No worker calls appear in the top 10 — workers do read-heavy (Read/Edit) work, opus is the source of all high-ratio Bash waste.

---

## Failed Calls

**Total: 5 failures** across all sources. Failure criterion: `is_error: true` at the tool_result block level.

### By Source

| Source | Failures |
|--------|----------|
| opus | 3 |
| worker:proxy-strip-plan | 1 |
| worker:cli-consolidation | 1 |

### By Error Type

| Error Type | Count | Description |
|------------|------:|-------------|
| `bash-exit-nonzero` | 2 | `is_error=true`, no `<tool_use_error>` tag — raw shell exit code |
| `parallel-cancel` | 1 | Sibling parallel call errored, this call was cancelled |
| `tool-unavailable` | 1 | Called non-existent MCP tool (`worker_merge`) |
| `edit-string-not-found` | 1 | `String to replace not found in file` |

### By Tool

| Tool | Count |
|------|------:|
| Bash | 2 |
| worker_merge (MCP) | 1 |
| Read | 1 |
| Edit | 1 |

### 5 Concrete Examples

**[1] parallel-cancel — Bash — opus — 20:58**
```
Input: ls /Users/.../dev/ToolsSystemPrompts/ && echo "---tool-use---" && ls ...
Error: <tool_use_error>Cancelled: parallel tool call Bash(ls /Users/...) errored</tool_use_error>
```
One of two parallel `ls` calls failed (wrong path, dir did not exist yet). The sibling was cancelled automatically. Pattern: parallel exploration of paths — one miss cancels the rest.

**[2] bash-exit-nonzero — Bash — opus — 20:58**
```
Input: ls /Users/.../Monitor_CC/src/proxy/ (incorrect path variant)
Error: Exit code 1
       __init__.py __pycache__ addon.py cache.py ...
```
Exit code 1 from `ls` — output shows the directory listing IS there but the command failed. Likely a compound command where one step returned non-zero.

**[3] tool-unavailable — worker_merge — opus — 22:14**
```
Input: {"name": "worker_merge", "worktree_name": "some-branch", ...}
Error: <tool_use_error>Error: No such tool available: mcp__plugin_iterative-dev_iterative-dev__worker_merge</tool_use_error>
```
Opus called `worker_merge` which was not registered in the plugin. This is a non-existent tool — 94 chars of input, zero useful output.

**[4] edit-string-not-found — Edit — worker:proxy-strip-plan — 21:08**
```
Input: file_path=src/proxy/addon.py, old_string="from .content_strip import (\n    _message_has_rejection,\n    _strip_rejection_message,..."
Error: <tool_use_error>String to replace not found in file. String: from .content_strip import ...
```
Import block existed in `rules.py`, not `addon.py`. Wrong target file. Caught and corrected immediately; import added to correct file on next call.

**[5] bash-exit-nonzero — Read — worker:cli-consolidation — 22:36**
```
Input: {"file_path": "/Users/.../Monitor_CC/.claude/worktrees/cli-consolidation/some_file.py"}
Error: File does not exist. Note: your current working directory is .../cli-consolidation
```
Read on a file that doesn't exist in the worktree (not yet created). Standard exploration failure.

---

## Pattern Identification

### Opus-Only Patterns (Orchestrator Waste)

| Pattern | Call Count | Avg Input chars | Avg Output chars | Avg Ratio | Total Input chars |
|---------|----------:|----------------:|-----------------:|----------:|------------------:|
| `worker-cli status <name> <path>` | 19 | 160 | 19 | ~32 | 3,040 |
| `bd comments add <id> "<text>"` | 5 | 739 | 31 | ~24 | 3,695 |
| `git branch --show-current` checks | 3 | 123 | 3 | ~41 | 369 |
| `worker-cli merge <name> <path>` | 1 | 200 | — | — | 200 |

**`worker-cli status` is the dominant opus waste pattern**: 19 calls, avg ratio 32. Output is consistently 4–19 chars (worker state: idle/running/done). The full project path `/Users/brunowinter2000/Documents/ai/Monitor_CC` (52 chars) appears in every call, adding constant overhead.

**`bd comments add`** carries large text payloads (progress notes, research findings). These are inherently content-driven — the body is the point. The command prefix itself (`bd comments add Monitor_CC-6ja "..."`) costs ~30 chars fixed overhead per call; the rest is payload.

**`git branch` checks** are the highest-ratio calls in the session (41.0) — 3-char output from a 123-char command. These are pure overhead, used by workers to verify worktree mode.

### Worker Patterns

Workers (extract-tool-defs, proxy-strip-plan, cli-consolidation) show balanced Read/Edit/Write patterns — expected investigative/implementation work. No structural waste patterns emerged. Their Bash calls are mostly one-off verification commands, not repetitive status checks.

---

## CLI-Wrapper Potential

### Pattern 1: `worker-cli status` — 19 calls, ratio ~32 → Candidate

**Current:** `worker-cli status <name> /Users/brunowinter2000/Documents/ai/Monitor_CC` = ~135–142 chars/call  
**Wrapper:** `ws <name>` = 11–25 chars/call (assumes `$PROJECT_ROOT` env or alias)  
**Saving:** ~110–120 chars/call × 19 calls = **~2,200 chars** in this session  
**Implementation:** `alias ws='worker-cli status'` + `WORKER_PROJECT=/Users/brunowinter2000/Documents/ai/Monitor_CC` in shell env

This is the highest-leverage single change. 19 repetitions in one 2.5h session.

### Pattern 2: `git branch --show-current` checks — 3 calls, ratio 41

**Current:** `git branch --show-current && git status --short | head -20` = 123 chars  
**Wrapper:** `gs` (git-status shorthand) or simply rely on the pre-edit check output  
**Saving:** ~100 chars × 3 = **~300 chars**  
**Note:** Workers issue these as the mandatory pre-edit check. Could be shortened if the check output was cached in the worker prompt context instead of re-checked each time.

### Pattern 3: `bd comments add` — 5 calls, not a wrapper candidate

The command prefix is ~30 chars, the body is payload. A shorter alias (`bdc <id>`) saves at most 8–10 chars/call. Not meaningful — the body dominates. No action recommended.

### Summary

Only `worker-cli status` is a genuine wrapper candidate in this session. The others are either content-driven (bd), too infrequent (git branch), or already minimal.
