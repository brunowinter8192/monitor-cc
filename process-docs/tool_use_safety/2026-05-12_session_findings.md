# Tool-Use Safety — Session 2026-05-12

## What Happened in the Session

Three observations in one session built up the "Tool-Use Safety" topic and its tracking task.

### 1. Enforcing the RAG-First Rule

Mid-session code exploration on src/menubar bypassed the RAG-First mandate from `workers-1.md` § PLAN Step 2. Reason: PLAN Step 2 is phrased as part of the formal PLAN cycle; the mid-session "scope extension during IMPLEMENT" mini-scoping didn't mention RAG. Opus jumped straight to `find` + `Read src/menubar/menubar.py` + `Read src/menubar/discover.py` (~580 LOC) instead of first reading `src/menubar/DOCS.md` via RAG (~500 tokens, a clear module overview).

→ A new rule "RAG-First on Code Exploration (NON-NEGOTIABLE)" added to `workers-1.md` § Core Rules + an anchor in `workers-2.md` § Scope Extension Mini-scoping. Live in production (`~/.claude/shared-rules/opus/workers-1.md`, workers-2.md).

### 2. Worker Kill via the grep-on-cmdline Antipattern

Three times in this session, the same worker-death mechanism:

| Worker | Time | Method |
|---|---|---|
| menubarfix | 2026-05-12 ~17:30 | `ps -A \| grep "workflow.py --mode menubar" \| awk \| xargs kill` |
| mbarfix2 | 2026-05-12 19:42 | same pattern |
| mbarlive | 2026-05-12 ~20:15 | `pkill -f "workflow.py --mode menubar"` |

Root-cause mechanics: a worker process has `claude.exe --dangerously-skip-permissions # Worker — <FULL PROMPT TEXT>` as its cmdline. The prompt text often contains strings like `workflow.py --mode menubar` (e.g. in a smoke-test block). `grep`/`pkill -f` matches against the full cmdline → the worker dies with SIGTERM (status 143 = 128+15).

Converges with that day's `extract_failed.py` output: 1 Rule-9 violation (`File has not been read yet`), 2 Rule-3 violations (broad recursive grep), 11 Rule-12 violations (sleep in worker-cli-send prompts — likely a false positive from heredoc-content matching), 3 Rule-13 violations.

**Critical:** the pattern fired directly AFTER self-explaining the antipattern. Discipline wasn't enough — structural prevention needed.

### 3. Quantification Across 67 Logs / 6 Days

```
ALL src/logs/api_requests_*.jsonl (2026-05-06 → 2026-05-12):
- 267 `pkill -f` calls total
- 246 of those concentrated in ONE session (searxng 2026-05-08)
- 18 in that day's session 2026-05-12
- 9 in Monitor_CC 2026-05-09
```

Burst-like concentration: 246/267 = 92% from one day → once the antipattern starts, it fires many times. With a hook in place, all 246 would have been avoided.

## Hook-Design Proposal (Deferred)

Planned but NOT implemented — to come in the next session:

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      { "type": "command",
        "command": "~/.claude/scripts/block-dangerous-process-kill.py",
        "timeout": 5 }
    ]
  }
]
```

Script logic: read `tool_input.command` from stdin (JSON), regex-check for `pkill -f` + `ps.*grep.*kill` pipes, on a match → stderr with alternatives (PID file, `pgrep -x` exact-comm) + exit 1 to block.

### Complication — Intentional Kill

User feedback: "sometimes we do intentionally kill workers." Meaning the design needs nuance:

- `worker-cli kill <name>` is intentional + safe → should stay allowed
- Manual process cleanup (PID known, targeted kill) → should be allowed
- `pkill -f <pattern>` → block because cmdline-substring matching is imprecise
- `ps | grep | kill` pipe → block

Likely heuristic: block when the KILL target was determined via a TEXTUAL MATCH (grep) instead of a direct PID reference or a controlled CLI wrapper. Concrete implementation in the next session.

### Cache-Cost Note

Editing `~/.claude/settings.json` to activate the hook busts the CC prompt cache (a full message rebuild on the next REQ). Same as with the RAG-First rule edit that day. The user had explicitly agreed — same logic applies to the hook edit.

## Overarching Concept

A user proposal (recorded in the tracking task): split `tool-use.md` structurally.

- "How you should proceed" → stays in tool-use.md (positive guidance)
- "How you should NOT proceed" → moves into hooks (structural prevention)

Advantages:
- Saves input tokens on every REQ (less rule text)
- Structurally reliable instead of discipline-dependent
- Antipatterns we can't discipline ourselves out of (see today's triple reproduction) become impossible this way

Migration path (next session): implement a first wave of 1-2 clear antipatterns (`pkill -f` block), remove the corresponding negative rules from tool-use.md, gather experience, then continue.

## Session Status

- A tracking task open for the migration work
- rule_compliance.py committed in Monitor_CC dev (`dev/tool_use_analysis/rule_compliance.py`)
- That day's report: `dev/tool_use_analysis/20260512_rule_compliance.md`
- Hook design discussed + deferral decided
- Menubar live-update fix in progress (separate from tool-use safety)

## Sources

- `~/.claude/shared-rules/global/tool-use.md` (the migration target)
- `~/.claude/settings.json.hooks-backup` (a working hook-format reference from the user)
- Proxy logs `src/logs/api_requests_*.jsonl` 2026-05-06 to 2026-05-12 (the quantification source)
