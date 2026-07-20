# Failed Tool Calls Analysis — 2026-04-28 20:32:01

## Source JSONLs

- `api_requests_opus_monitor_cc_1776949625.jsonl` (115 events, 652 tool_use blocks)
- `api_requests_opus_monitor_cc_1776956156.jsonl` (189 events, 652 tool_use blocks)
- `api_requests_opus_monitor_cc_1776966942.jsonl` (297 events, 652 tool_use blocks)
- `api_requests_worker_serializer-delta_1776976088.jsonl` (36 events, 32 tool_use blocks)
- `api_requests_opus_monitor_cc_1776977437.jsonl` (219 events, 652 tool_use blocks)
- `api_requests_worker_pm-regex-anchor_1776980864.jsonl` (101 events, 89 tool_use blocks)
- `api_requests_worker_sr-bypass-audit_1776983329.jsonl` (35 events, 32 tool_use blocks)
- `api_requests_worker_req-cascade-doc_1776989581.jsonl` (38 events, 36 tool_use blocks)
- `api_requests_worker_req-collision-bg_1776990249.jsonl` (32 events, 30 tool_use blocks)
- `api_requests_worker_log-cleanup_1777138479.jsonl` (15 events, 13 tool_use blocks)

Total sessions analyzed: 10. Total tool_use blocks: 884.

## Summary

**Total failures:** 16

### By Source

| Source | Failures |
|--------|----------|
| `opus` | 11 |
| `worker:log-cleanup` | 1 |
| `worker:pm-regex-anchor` | 3 |
| `worker:req-collision-bg` | 1 |

### By Error Type

| Error Type | Count |
|------------|-------|
| `bash-exit-nonzero` | 13 |
| `tool-use-error` | 3 |

### By Tool

| Tool | Count |
|------|-------|
| `Bash` | 12 |
| `Edit` | 2 |
| `Write` | 1 |
| `Read` | 1 |

## Failure Details

### [1] `bash-exit-nonzero` — Bash — opus — 16:44:48

**input_chars:** 423 &nbsp; **output_chars:** 221

**Input preview:**
```
{"command": "mkdir -p ~/.claude/plans && ls /tmp/opus_entries.jsonl > /dev/null 2>&1 && echo \"worker still idle:\" && worker-cli status delta-leak-su
```

**Error content:**
```
Exit code 128 worker still idle: idle --- git dev log tip 5: fatal: ambiguous argument 'dev': both revision and filename Use '--' to separate paths from revisions, like this: 'git <command> [<revision
```

---

### [2] `bash-exit-nonzero` — Bash — opus — 16:57:24

**input_chars:** 198 &nbsp; **output_chars:** 11

**Input preview:**
```
{"command": "ls dev/strip_audit/ 2>/dev/null && echo \"---\" && ls -lt src/logs/api_requests_opus_monitor_cc_*.jsonl 2>/dev/null | head -5", "descript
```

**Error content:**
```
Exit code 1
```

---

### [3] `bash-exit-nonzero` — Bash — opus — 17:04:12

**input_chars:** 579 &nbsp; **output_chars:** 225

**Input preview:**
```
{"command": "./venv/bin/python3 -c \"\nimport sys, json\nfrom pathlib import Path\nsys.path.insert(0, 'src')\nfrom proxy.strip_vocab import classify_t
```

**Error content:**
```
The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to
```

---

### [4] `bash-exit-nonzero` — Bash — opus — 17:26:04

**input_chars:** 127 &nbsp; **output_chars:** 225

**Input preview:**
```
{"command": "worker-cli spawn delta-fixes /tmp/spawn-worker-Monitor_CC-delta-fixes.md c sonnet", "description": "Spawn worker"}
```

**Error content:**
```
The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to
```

---

### [5] `bash-exit-nonzero` — Bash — opus — 17:28:42

**input_chars:** 139 &nbsp; **output_chars:** 71

**Input preview:**
```
{"command": "worker-cli spawn delta-fixes /tmp/spawn-worker-Monitor_CC-delta-fixes.md c sonnet", "description": "Spawn worker delta-fixes"}
```

**Error content:**
```
Exit code 1 ERROR: Branch 'delta-fixes' already exists. Clean up first.
```

---

### [6] `bash-exit-nonzero` — Bash — opus — 17:51:57

**input_chars:** 182 &nbsp; **output_chars:** 539

**Input preview:**
```
{"command": "git -C /Users/brunowinter2000/Documents/ai/Monitor_CC status --short && echo \"---\" && worker-cli merge delta-fixes c", "description": "
```

**Error content:**
```
Exit code 2 A  dev/tool_use_analysis/202604231704_strip_audit.md A  dev/tool_use_analysis/archive/202604231657_strip_audit.md --- === Commits on branch delta-fixes not in dev === 0a6c0bc fix: delta-sc
```

---

### [7] `bash-exit-nonzero` — Bash — opus — 19:13:05

**input_chars:** 98 &nbsp; **output_chars:** 318

**Input preview:**
```
{"command": "./venv/bin/python3 /tmp/prefix_diff_req30.py 2>&1", "description": "Run prefix diff"}
```

**Error content:**
```
Exit code 1   File "/tmp/prefix_diff_req30.py", line 106     print(f'  {req_label}: sent_tools_bytes_hash={d.get(\"sent_tools_bytes_hash\")} sent_system_hash={d.get(\"sent_system_hash\")}')           
```

---

### [8] `tool-use-error` — Edit — opus — 21:01:39

**input_chars:** 136 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "src/proxy/DOCS.md", "old_string": "### rules.py (264 LOC)", "new_string": "### rules.py (270 LOC)"}
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [9] `tool-use-error` — Edit — opus — 22:44:24

**input_chars:** 189 &nbsp; **output_chars:** 96

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/src/proxy_display/DOCS.md", "old_string": "### pane.py (172 LOC)",
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [10] `tool-use-error` — Write — opus — 23:21:17

**input_chars:** 2,229 &nbsp; **output_chars:** 96

**Input preview:**
```
{"file_path": "/tmp/sidecar_scan.py", "content": "import json, sys\npath = \"src/logs/api_requests_opus_monitor_cc_1776977437.jsonl\"\nentries = []\nw
```

**Error content:**
```
<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>
```

---

### [11] `bash-exit-nonzero` — Bash — opus — 01:31:28

**input_chars:** 221 &nbsp; **output_chars:** 73

**Input preview:**
```
{"command": "git -C /Users/brunowinter2000/Documents/ai/Meta/blank checkout main && git -C /Users/brunowinter2000/Documents/ai/Meta/blank merge dev --
```

**Error content:**
```
Exit code 1 error: pathspec 'main' did not match any file(s) known to git
```

---

### [12] `bash-exit-nonzero` — Bash — worker:log-cleanup — 19:39:05

**input_chars:** 1,635 &nbsp; **output_chars:** 461

**Input preview:**
```
{"command": "cd /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/log-cleanup\n\n# Create fake orphan shim + dir in src/logs/\nLOG_DIR=
```

**Error content:**
```
Exit code 1 === Before janitor === -rw-r--r--@ 1 brunowinter2000  staff  0 Apr 25 19:39 src/logs/.proxy_addon_live_worker_test_orphan.py  src/logs/.proxy_live_worker_test_orphan/: total 0 drwxr-xr-x@ 
```

---

### [13] `bash-exit-nonzero` — Bash — worker:pm-regex-anchor — 23:49:36

**input_chars:** 100 &nbsp; **output_chars:** 358

**Input preview:**
```
{"command": "./venv/bin/python3 -c \"from src.proxy.rules import _pm_pat; print(_pm_pat.pattern)\""}
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<string>", line 1, in <module>     from src.proxy.rules import _pm_pat; print(_pm_pat.pattern)     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ImportErro
```

---

### [14] `bash-exit-nonzero` — Read — worker:pm-regex-anchor — 00:18:29

**input_chars:** 149 &nbsp; **output_chars:** 142

**Input preview:**
```
{"file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/pm-regex-anchor/src/proxy/strip_vocab.py", "offset": 28, "limit": 35}
```

**Error content:**
```
File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/pm-regex-anchor.
```

---

### [15] `bash-exit-nonzero` — Bash — worker:pm-regex-anchor — 00:34:10

**input_chars:** 359 &nbsp; **output_chars:** 1,654

**Input preview:**
```
{"command": "./venv/bin/python3 dev/tool_use_analysis/cc_injection_audit.py \\\n  src/logs/api_requests_opus_monitor_cc_1776977437.jsonl \\\n  --cc-se
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/pm-regex-anchor/dev/tool_use_analysis/cc_injection_audit.py", line 287, in <modu
```

---

### [16] `bash-exit-nonzero` — Bash — worker:req-collision-bg — 02:34:04

**input_chars:** 4,069 &nbsp; **output_chars:** 346

**Input preview:**
```
{"command": "./venv/bin/python3 << 'EOF'\nimport sys, os, json\nsys.path.insert(0, '.')\nfrom src.proxy_display.parser import _parse_log_file\nfrom sr
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<stdin>", line 11, in <module>   File "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/req-collision-bg/src/proxy_display/parser
```

---
