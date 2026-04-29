# Failed Tool Calls Analysis — 2026-04-28 20:32:03

## Source JSONLs

- `api_requests_worker_f93afc17_meta-legend_1777302969.jsonl` (15 events, 13 tool_use blocks)
- `api_requests_worker_8e6b2517_cleanup-wave_1777304606.jsonl` (46 events, 58 tool_use blocks)
- `api_requests_worker_f93afc17_content-drift-doc_1777305742.jsonl` (27 events, 25 tool_use blocks)
- `api_requests_worker_f93afc17_docs-sync_1777307912.jsonl` (130 events, 126 tool_use blocks)
- `api_requests_worker_8e6b2517_readme-claude_1777311242.jsonl` (48 events, 41 tool_use blocks)
- `api_requests_worker_f93afc17_ctrl-r-heal_1777312001.jsonl` (78 events, 72 tool_use blocks)
- `api_requests_worker_f93afc17_tag-presence-audit_1777323525.jsonl` (48 events, 45 tool_use blocks)
- `api_requests_worker_8e6b2517_eval-extension_1777333174.jsonl` (50 events, 53 tool_use blocks)
- `api_requests_worker_f93afc17_po-preview-strip_1777334456.jsonl` (43 events, 39 tool_use blocks)
- `api_requests_worker_f93afc17_tag-3audits_1777378891.jsonl` (142 events, 136 tool_use blocks)

Total sessions analyzed: 10. Total tool_use blocks: 608.

## Summary

**Total failures:** 9

### By Source

| Source | Failures |
|--------|----------|
| `worker:8e6b2517_readme-claude` | 2 |
| `worker:f93afc17_ctrl-r-heal` | 2 |
| `worker:f93afc17_docs-sync` | 1 |
| `worker:f93afc17_meta-legend` | 1 |
| `worker:f93afc17_po-preview-strip` | 1 |
| `worker:f93afc17_tag-3audits` | 2 |

### By Error Type

| Error Type | Count |
|------------|-------|
| `bash-exit-nonzero` | 6 |
| `tool-use-error` | 2 |
| `edit-string-not-found` | 1 |

### By Tool

| Tool | Count |
|------|-------|
| `Bash` | 5 |
| `Edit` | 3 |
| `Read` | 1 |

## Failure Details

### [1] `bash-exit-nonzero` — Read — worker:8e6b2517_readme-claude — 19:34:15

**input_chars:** 118 &nbsp; **output_chars:** 153

**Input preview:**
```
{"file_path": "/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claire/worktrees/readme-claude/README.md"}
```

**Error content:**
```
File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claude/worktrees/readme-claude.
```

---

### [2] `bash-exit-nonzero` — Bash — worker:8e6b2517_readme-claude — 19:35:13

**input_chars:** 231 &nbsp; **output_chars:** 145

**Input preview:**
```
{"command": "ls /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claude/worktrees/readme-claude/commands/ /Users/brunowinter2000/Documents
```

**Error content:**
```
Exit code 1 /Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/.claude/worktrees/readme-claude/commands/: pdf-convert.md web-md-index.md
```

---

### [3] `tool-use-error` — Edit — worker:f93afc17_ctrl-r-heal — 19:56:20

**input_chars:** 1,255 &nbsp; **output_chars:** 173

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/ctrl-r-heal/src/tmux_launcher.py", "old_string":
```

**Error content:**
```
<tool_use_error>File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/ctrl-r-heal.</tool_use_error>  
```

---

### [4] `bash-exit-nonzero` — Bash — worker:f93afc17_ctrl-r-heal — 20:27:04

**input_chars:** 566 &nbsp; **output_chars:** 533

**Input preview:**
```
{"command": "./venv/bin/python3 << 'EOF'\nimport sys\nsys.path.insert(0, '.')\nfrom src.workers.worker_format import extract_worker_context_pct\n\njso
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<stdin>", line 6, in <module>   File "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/ctrl-r-heal/src/workers/worker_format.py",
```

---

### [5] `edit-string-not-found` — Edit — worker:f93afc17_docs-sync — 20:14:05

**input_chars:** 2,284 &nbsp; **output_chars:** 1,768

**Input preview:**
```
{"replace_all": false, "file_path": "decisions/pipe03_core_loop.md", "old_string": "| `active_mode` | `str` | monitor.py:36 | monitor.py | monitor.py 
```

**Error content:**
```
<tool_use_error>String to replace not found in file. String: | `active_mode` | `str` | monitor.py:36 | monitor.py | monitor.py | Aktueller Mode (all/main/subagent/rules/...) | | `ui_mode_active` | `bo
```

---

### [6] `bash-exit-nonzero` — Bash — worker:f93afc17_meta-legend — 17:16:37

**input_chars:** 222 &nbsp; **output_chars:** 764

**Input preview:**
```
{"command": "grep -n PASTEL_GREEN src/metadata/metadata_format.py; grep -n LEGEND src/metadata/metadata_format.py; ./venv/bin/python3 -c \"from src.me
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<string>", line 1, in <module>     from src.metadata.metadata_format import _format_metadata   File "/Users/brunowinter2000/Documents/ai/Monitor_
```

---

### [7] `bash-exit-nonzero` — Bash — worker:f93afc17_po-preview-strip — 02:01:42

**input_chars:** 2,382 &nbsp; **output_chars:** 197

**Input preview:**
```
{"command": "python3 << 'EOF'\nimport json, sys\n\nlog = 'src/logs/api_requests_opus_monitor_cc_1777294641.jsonl'\nreq_num = 0\nfound = 0\nwith open(l
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<stdin>", line 6, in <module> FileNotFoundError: [Errno 2] No such file or directory: 'src/logs/api_requests_opus_monitor_cc_1777294641.jsonl'
```

---

### [8] `tool-use-error` — Edit — worker:f93afc17_tag-3audits — 15:05:25

**input_chars:** 558 &nbsp; **output_chars:** 173

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/tag-3audits/dev/tool_use_analysis/tag_presence_a
```

**Error content:**
```
<tool_use_error>File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/tag-3audits.</tool_use_error>  
```

---

### [9] `bash-exit-nonzero` — Bash — worker:f93afc17_tag-3audits — 15:22:55

**input_chars:** 57 &nbsp; **output_chars:** 855

**Input preview:**
```
{"command": "./venv/bin/python3 /tmp/verify_rkk.py 2>&1"}
```

**Error content:**
```
Exit code 1 === _format_latency smoke ===   [green TTFB + green gen]: '  \x1b[38;2;166;227;161mTTFB:0.8s\x1b[39m \x1b[38;2;166;227;161mgen:3'   [yellow TTFB + yellow gen]: '  \x1b[38;2;249;226;175mTTF
```

---
