# Failed Tool Calls Analysis — 2026-04-28 20:32:04

## Source JSONLs

- `api_requests_worker_f93afc17_cc-perf-research_1777380675.jsonl` (94 events, 89 tool_use blocks)
- `api_requests_worker_f93afc17_cap-fix_1777385563.jsonl` (52 events, 49 tool_use blocks)
- `api_requests_worker_f93afc17_7xa-fix_1777387643.jsonl` (21 events, 19 tool_use blocks)
- `api_requests_worker_f93afc17_ttfb-fix_1777393095.jsonl` (127 events, 118 tool_use blocks)

Total sessions analyzed: 4. Total tool_use blocks: 275.

## Summary

**Total failures:** 3

### By Source

| Source | Failures |
|--------|----------|
| `worker:f93afc17_cap-fix` | 1 |
| `worker:f93afc17_ttfb-fix` | 2 |

### By Error Type

| Error Type | Count |
|------------|-------|
| `tool-use-error` | 2 |
| `bash-exit-nonzero` | 1 |

### By Tool

| Tool | Count |
|------|-------|
| `Bash` | 1 |
| `Edit` | 1 |
| `Write` | 1 |

## Failure Details

### [1] `bash-exit-nonzero` — Bash — worker:f93afc17_cap-fix — 16:14:08

**input_chars:** 288 &nbsp; **output_chars:** 340

**Input preview:**
```
{"command": "python3 -c \"from src.proxy.rules import apply_modification_rules\" && echo \"rules OK\" && python3 -c \"from src.proxy.addon import Prox
```

**Error content:**
```
Exit code 1 rules OK Traceback (most recent call last):   File "<string>", line 1, in <module>     from src.proxy.addon import ProxyAddon   File "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude
```

---

### [2] `tool-use-error` — Edit — worker:f93afc17_ttfb-fix — 18:25:31

**input_chars:** 1,288 &nbsp; **output_chars:** 170

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/ttfb-fix/src/proxy_display/pane.py", "old_string
```

**Error content:**
```
<tool_use_error>File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/ttfb-fix.</tool_use_error>  
```

---

### [3] `tool-use-error` — Write — worker:f93afc17_ttfb-fix — 19:14:35

**input_chars:** 2,791 &nbsp; **output_chars:** 96

**Input preview:**
```
{"file_path": "/tmp/verify_1fo.py", "content": "\"\"\"\nVerify Fix 1 (no Turn/total header rows) and Fix 2 (think:Nk from max_tokens).\n\"\"\"\nimport
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---
