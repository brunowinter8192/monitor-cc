# Failed Tool Calls Analysis — 2026-04-28 20:20:37

## Source JSONLs

- `api_requests_opus_monitor_cc_1776987151.jsonl` (150 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777132398.jsonl` (257 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777151260.jsonl` (14 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777214068.jsonl` (146 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777294641.jsonl` (289 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777320131.jsonl` (112 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777377562.jsonl` (224 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777390975.jsonl` (3 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777391349.jsonl` (72 events, 1057 tool_use blocks)
- `api_requests_opus_monitor_cc_1777394557.jsonl` (54 events, 1057 tool_use blocks)

Total sessions analyzed: 10. Total tool_use blocks: 1057.

## Summary

**Total failures:** 23

### By Source

| Source | Failures |
|--------|----------|
| `opus` | 23 |

### By Error Type

| Error Type | Count |
|------------|-------|
| `bash-exit-nonzero` | 16 |
| `tool-use-error` | 7 |

### By Tool

| Tool | Count |
|------|-------|
| `Bash` | 18 |
| `Edit` | 4 |
| `Grep` | 1 |

## Failure Details

### [1] `bash-exit-nonzero` — Bash — opus — 02:09:06

**input_chars:** 248 &nbsp; **output_chars:** 1,161

**Input preview:**
```
{"command": "cat /Users/brunowinter2000/Documents/ai/Meta/blank/skills/iterative-dev/SKILL.md | head -40; echo =====TAIL=====; tail -80 /Users/brunowi
```

**Error content:**
```
Exit code 1 --- name: iterative-dev description: (project) ---  # Iterative Development Skill  ### Session Start (MANDATORY)  → read beads. → activate the `tool-use` skill (parallel to the proxy-injec
```

---

### [2] `tool-use-error` — Bash — opus — 02:14:22

**input_chars:** 99 &nbsp; **output_chars:** 317

**Input preview:**
```
{"command": "sleep 60 && worker-cli status req-cascade-doc c", "description": "60s sleep + status"}
```

**Error content:**
```
<tool_use_error>Blocked: sleep 60 followed by: worker-cli status req-cascade-doc c. To wait for a condition, use Monitor with an until-loop (e.g. `until <check>; do sleep 2; done`). To wait for a comm
```

---

### [3] `bash-exit-nonzero` — Bash — opus — 19:40:59

**input_chars:** 144 &nbsp; **output_chars:** 174

**Input preview:**
```
{"command": "git -C /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/log-cleanup diff dev", "description": "Review worker diff"}
```

**Error content:**
```
Exit code 128 fatal: ambiguous argument 'dev': both revision and filename Use '--' to separate paths from revisions, like this: 'git <command> [<revision>...] -- [<file>...]'
```

---

### [4] `bash-exit-nonzero` — Bash — opus — 19:41:45

**input_chars:** 329 &nbsp; **output_chars:** 83

**Input preview:**
```
{"command": "find ~/Documents -maxdepth 5 -type d -name \"iterative-dev\" 2>/dev/null | head -5 && echo \"---\" && grep -l \"tmux_spawn\" ~/Documents/
```

**Error content:**
```
Exit code 2 /Users/brunowinter2000/Documents/ai/Meta/blank/skills/iterative-dev ---
```

---

### [5] `bash-exit-nonzero` — Bash — opus — 19:52:35

**input_chars:** 871 &nbsp; **output_chars:** 742

**Input preview:**
```
{"command": "echo \"=== killing worker ===\"\nworker-cli kill trap-test c 2>&1 | tail -5\nsleep 3\necho\necho \"=== state AFTER kill ===\"\necho \"Mit
```

**Error content:**
```
Exit code 1 === killing worker === Killing worker: worker-Monitor_CC-trap-test   tmux session: killed   worktree: removed Deleted branch trap-test (was aa38e96).   branch: deleted  === state AFTER kil
```

---

### [6] `bash-exit-nonzero` — Bash — opus — 19:53:02

**input_chars:** 96 &nbsp; **output_chars:** 73

**Input preview:**
```
{"command": "cat /tmp/.worker_trap-test.pLMRFh", "description": "Inspect runner script content"}
```

**Error content:**
```
Exit code 1 cat: /tmp/.worker_trap-test.pLMRFh: No such file or directory
```

---

### [7] `bash-exit-nonzero` — Bash — opus — 20:31:08

**input_chars:** 711 &nbsp; **output_chars:** 578

**Input preview:**
```
{"command": "echo \"=== process tree of active mitmproxy (PID 44496) ===\"\nps -o pid,ppid,user,command -p 44496 2>/dev/null\necho \"---\"\necho \"===
```

**Error content:**
```
Exit code 1 === process tree of active mitmproxy (PID 44496) ===   PID  PPID USER            COMMAND 44496 44472 brunowinter2000 mitmdump -p 8080 -s /Users/brunowinter2000/Documents/ai/Monitor_CC/src/
```

---

### [8] `tool-use-error` — Bash — opus — 20:32:13

**input_chars:** 737 &nbsp; **output_chars:** 886

**Input preview:**
```
{"command": "sleep 60 && echo \"=== 60s post-restart ===\" && ps aux | grep -E \"workflow\\.py.*Monitor_CC\" | grep -v grep | awk '{rss=$6/1024; cmd=\
```

**Error content:**
```
<tool_use_error>Blocked: sleep 60 followed by: echo "=== 60s post-restart ===" ps aux grep -E "workflow\.py.*Monitor_CC" grep -v grep awk '{rss=$6/1024; cmd=""; for(i=11;i<=NF;i++) if ($i ~ /--mode/) 
```

---

### [9] `tool-use-error` — Edit — opus — 21:36:02

**input_chars:** 1,289 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/sources/sources.md", "old_string": "| termshot | github.com/homepo
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [10] `bash-exit-nonzero` — Bash — opus — 21:37:25

**input_chars:** 8,510 &nbsp; **output_chars:** 1,041

**Input preview:**
```
{"command": "bd --repo /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/github create --title \"github-search SKILL evaluation: lean call / wra
```

**Error content:**
```
Exit code 1 Info: cleaned up 2 orphaned dolt sql-server process(es) Error: failed to open target store: database "github" not found on Dolt server at 127.0.0.1:50821  Backup files found in .beads/back
```

---

### [11] `tool-use-error` — Edit — opus — 21:47:23

**input_chars:** 829 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/src/input/DOCS.md", "old_string": "from src.input import read_mous
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [12] `bash-exit-nonzero` — Bash — opus — 21:25:13

**input_chars:** 412 &nbsp; **output_chars:** 707

**Input preview:**
```
{"command": "echo \"=== pre-merge status ===\" && git status --short && echo \"=== current branch ===\" && git branch --show-current && echo \"=== mer
```

**Error content:**
```
Exit code 128 === pre-merge status === === current branch === main === merge === === Commits on branch thinking-cap not in dev === fatal: ambiguous argument 'dev..thinking-cap': unknown revision or pa
```

---

### [13] `bash-exit-nonzero` — Bash — opus — 17:17:54

**input_chars:** 107 &nbsp; **output_chars:** 174

**Input preview:**
```
{"command": "git -C /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/meta-legend diff dev"}
```

**Error content:**
```
Exit code 128 fatal: ambiguous argument 'dev': both revision and filename Use '--' to separate paths from revisions, like this: 'git <command> [<revision>...] -- [<file>...]'
```

---

### [14] `tool-use-error` — Grep — opus — 17:47:34

**input_chars:** 103 &nbsp; **output_chars:** 169

**Input preview:**
```
{"pattern": "sig:|signature", "path": "src/panes/tokens_pane.py", "output_mode": "content", "-n": true}
```

**Error content:**
```
<tool_use_error>Path does not exist: src/panes/tokens_pane.py. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC.</tool_use_error>  
```

---

### [15] `bash-exit-nonzero` — Bash — opus — 18:55:47

**input_chars:** 600 &nbsp; **output_chars:** 69

**Input preview:**
```
{"command": "LOG=src/logs/api_requests_opus_monitor_cc_1777294641.jsonl\njq -c 'select(.raw_payload.model | type == \"string\" and startswith(\"claude
```

**Error content:**
```
Exit code 5 jq: error (at <stdin>:1): Cannot index object with number
```

---

### [16] `bash-exit-nonzero` — Bash — opus — 19:32:59

**input_chars:** 147 &nbsp; **output_chars:** 54

**Input preview:**
```
{"command": "find dev -name \"extract_zeros*\" -o -name \"*zero_result*\" 2>/dev/null && echo \"---\" && ls dev/zero_result_analysis/ 2>/dev/null"}
```

**Error content:**
```
Exit code 1 dev/tool_use_analysis/extract_zeros.py ---
```

---

### [17] `bash-exit-nonzero` — Bash — opus — 20:09:32

**input_chars:** 244 &nbsp; **output_chars:** 74

**Input preview:**
```
{"command": "echo \"=== subagent / MODE_SUBAGENT / 4-window refs in decisions/ ===\" && grep -ln \"subagent\\|MODE_SUBAGENT\\|--ui\\|4 windows\\|run_s
```

**Error content:**
```
Exit code 2 === subagent / MODE_SUBAGENT / 4-window refs in decisions/ ===
```

---

### [18] `bash-exit-nonzero` — Bash — opus — 21:59:34

**input_chars:** 565 &nbsp; **output_chars:** 392

**Input preview:**
```
{"command": "echo \"=== git status main ===\" && git -C /Users/brunowinter2000/Documents/ai/Monitor_CC status --short\necho \"\"\necho \"=== branch st
```

**Error content:**
```
Exit code 1 === git status main ===  === branch state === 0e554f3 merge: worker ctrl-r-heal fatal: ambiguous argument 'dev': both revision and filename Use '--' to separate paths from revisions, like 
```

---

### [19] `bash-exit-nonzero` — Bash — opus — 23:12:11

**input_chars:** 213 &nbsp; **output_chars:** 359

**Input preview:**
```
{"command": "cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tag-presence-audit && git log --oneline -3 && echo \"---\" && git dif
```

**Error content:**
```
Exit code 128 9ae2018 feat: add tag_presence_audit.py — per-REQ delta-scoped SR/TN/ND/PO audit with full content 0e554f3 merge: worker ctrl-r-heal cc36628 docs: sync DOCS post-eha/gmv/mwi merges --- f
```

---

### [20] `bash-exit-nonzero` — Bash — opus — 01:58:48

**input_chars:** 392 &nbsp; **output_chars:** 134

**Input preview:**
```
{"command": "bd close blank-27a --reason=\"Rule 8 (persisted-output \u2192 grep file, never preview) added to /Users/brunowinter2000/Documents/ai/Meta
```

**Error content:**
```
Exit code 1 Info: cleaned up 2 orphaned dolt sql-server process(es) Error: resolving ID blank-27a: no issue found matching "blank-27a"
```

---

### [21] `tool-use-error` — Edit — opus — 02:14:24

**input_chars:** 674 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/src/proxy/DOCS.md", "old_string": "- Constants: `BUCKETS` (EFF/INE
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [22] `tool-use-error` — Edit — opus — 17:08:31

**input_chars:** 183 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/src/proxy/DOCS.md", "old_string": "### addon.py (349 LOC)", "new_s
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [23] `bash-exit-nonzero` — Bash — opus — 18:18:10

**input_chars:** 368 &nbsp; **output_chars:** 51

**Input preview:**
```
{"command": "PLUGIN=~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0\nSPAWN=\"$PLUGIN/src/spawn/tmux_spawn.sh\"\nbash -c \"source \\\"$
```

**Error content:**
```
Exit code 127 bash: worker_spawn: command not found
```

---
