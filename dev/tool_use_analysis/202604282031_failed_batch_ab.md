# Failed Tool Calls Analysis — 2026-04-28 20:32:02

## Source JSONLs

- `api_requests_worker_trap-test_1777139535.jsonl` (3 events, 0 tool_use blocks)
- `api_requests_worker_pane-ram_1777139711.jsonl` (39 events, 35 tool_use blocks)
- `api_requests_worker_input-event_1777141134.jsonl` (55 events, 58 tool_use blocks)
- `api_requests_worker_assessment-strip_1777215614.jsonl` (144 events, 141 tool_use blocks)
- `api_requests_worker_gh-strip-forensik_1777220788.jsonl` (60 events, 58 tool_use blocks)
- `api_requests_worker_sidecar-leak-forensik_1777220978.jsonl` (43 events, 40 tool_use blocks)
- `api_requests_worker_abort-cascade-forensik_1777221169.jsonl` (34 events, 30 tool_use blocks)
- `api_requests_worker_waste-pane-leak-forensik_1777221359.jsonl` (47 events, 48 tool_use blocks)
- `api_requests_worker_thinking-cap_1777229846.jsonl` (35 events, 32 tool_use blocks)
- `api_requests_worker_f93afc17_cluster1-impl_1777236298.jsonl` (61 events, 59 tool_use blocks)

Total sessions analyzed: 10. Total tool_use blocks: 501.

## Summary

**Total failures:** 15

### By Source

| Source | Failures |
|--------|----------|
| `worker:f93afc17_cluster1-impl` | 4 |
| `worker:gh-strip-forensik` | 4 |
| `worker:input-event` | 2 |
| `worker:sidecar-leak-forensik` | 3 |
| `worker:thinking-cap` | 1 |
| `worker:waste-pane-leak-forensik` | 1 |

### By Error Type

| Error Type | Count |
|------------|-------|
| `bash-exit-nonzero` | 12 |
| `tool-use-error` | 2 |
| `edit-string-not-found` | 1 |

### By Tool

| Tool | Count |
|------|-------|
| `Bash` | 12 |
| `Edit` | 3 |

## Failure Details

### [1] `bash-exit-nonzero` — Bash — worker:f93afc17_cluster1-impl — 22:48:05

**input_chars:** 194 &nbsp; **output_chars:** 145

**Input preview:**
```
{"command": "python3 dev/tool_use_analysis/strip_audit.py src/logs/api_requests_opus_monitor_cc_*.jsonl > /tmp/audit_item1_check.txt 2>&1; head -40 /t
```

**Error content:**
```
Exit code 1 (eval):1: no matches found: src/logs/api_requests_opus_monitor_cc_*.jsonl head: /tmp/audit_item1_check.txt: No such file or directory
```

---

### [2] `bash-exit-nonzero` — Bash — worker:f93afc17_cluster1-impl — 22:48:20

**input_chars:** 252 &nbsp; **output_chars:** 11

**Input preview:**
```
{"command": "python3 dev/tool_use_analysis/strip_audit.py /Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_opus_monitor_cc_1777214
```

**Error content:**
```
Exit code 1
```

---

### [3] `edit-string-not-found` — Edit — worker:f93afc17_cluster1-impl — 22:49:52

**input_chars:** 991 &nbsp; **output_chars:** 666

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/cluster1-impl/src/proxy/rules.py", "old_string":
```

**Error content:**
```
<tool_use_error>String to replace not found in file. String:                 modifications.append("removed_plan_mode_sr")                 if isinstance(old_content, str):                     stripped_
```

---

### [4] `bash-exit-nonzero` — Bash — worker:f93afc17_cluster1-impl — 22:51:05

**input_chars:** 45 &nbsp; **output_chars:** 637

**Input preview:**
```
{"command": "python3 /tmp/verify_b8j_imp.py"}
```

**Error content:**
```
Exit code 1 modifications: ['stripped_sidecar_content'] stripped_msg_removed: {0: ["<system-reminder>\nThe user sent a new message while you were working:\nPlease check the status of the deploy.\n\nIM
```

---

### [5] `tool-use-error` — Edit — worker:gh-strip-forensik — 20:28:12

**input_chars:** 818 &nbsp; **output_chars:** 180

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/gh-strip-forensik/src/proxy/rules.py", "old_stri
```

**Error content:**
```
<tool_use_error>File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/gh-strip-forensik.</tool_use_error>   
```

---

### [6] `bash-exit-nonzero` — Bash — worker:gh-strip-forensik — 20:29:00

**input_chars:** 61 &nbsp; **output_chars:** 797

**Input preview:**
```
{"command": "python3 /tmp/verify_finalpass_tracking.py 2>&1"}
```

**Error content:**
```
Exit code 1 [A] stripped_all_sr fired: OK [A] stripped_msg_indices contains 0: OK [A] FAIL: stripped_msg_originals['0'] missing SR [A] FAIL: stripped_msg_removed['0'] missing or empty (removed_A={0: [
```

---

### [7] `bash-exit-nonzero` — Bash — worker:gh-strip-forensik — 20:29:38

**input_chars:** 61 &nbsp; **output_chars:** 390

**Input preview:**
```
{"command": "python3 /tmp/verify_finalpass_tracking.py 2>&1"}
```

**Error content:**
```
Exit code 1 [A] stripped_all_sr fired: OK [A] stripped_msg_indices contains 0: OK [A] FAIL: stripped_msg_originals[0] missing SR (keys=[0]) [A] stripped_msg_removed[0] contains exact SR block: PASS  [
```

---

### [8] `bash-exit-nonzero` — Bash — worker:gh-strip-forensik — 20:33:00

**input_chars:** 61 &nbsp; **output_chars:** 403

**Input preview:**
```
{"command": "python3 /tmp/verify_finalpass_tracking.py 2>&1"}
```

**Error content:**
```
Exit code 1 [A] stripped_all_sr fired: OK [A] stripped_msg_indices contains 0: OK [A] FAIL: stripped_msg_originals[0] missing SR (keys=[0]) [A] stripped_msg_removed[0] contains exact SR block: PASS  [
```

---

### [9] `tool-use-error` — Edit — worker:input-event — 20:24:09

**input_chars:** 399 &nbsp; **output_chars:** 173

**Input preview:**
```
{"replace_all": false, "file_path": "/Users/brunowinter2000/Documents/ai/Monitor_CC/.claire/worktrees/input-event/src/panes/waste_pane.py", "old_strin
```

**Error content:**
```
<tool_use_error>File does not exist. Note: your current working directory is /Users/brunowinter2000/Documents/ai/Monitor_CC/.claude/worktrees/input-event.</tool_use_error>  
```

---

### [10] `bash-exit-nonzero` — Bash — worker:input-event — 20:50:24

**input_chars:** 83 &nbsp; **output_chars:** 108

**Input preview:**
```
{"command": "git checkout dev && git pull && git checkout -b streaming-parse 2>&1"}
```

**Error content:**
```
Exit code 128 fatal: 'dev' is already used by worktree at '/Users/brunowinter2000/Documents/ai/Monitor_CC'  
```

---

### [11] `bash-exit-nonzero` — Bash — worker:sidecar-leak-forensik — 18:30:05

**input_chars:** 1,108 &nbsp; **output_chars:** 139

**Input preview:**
```
{"command": "python3 << 'EOF'\nimport json\nf = \"/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_opus_monitor_cc_1777214068.json
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<stdin>", line 17, in <module> AttributeError: 'list' object has no attribute 'keys'
```

---

### [12] `bash-exit-nonzero` — Bash — worker:sidecar-leak-forensik — 18:33:56

**input_chars:** 383 &nbsp; **output_chars:** 1,231

**Input preview:**
```
{"command": "cat /Users/brunowinter2000/Documents/ai/Monitor_CC/.beads/registry.json 2>/dev/null | python3 -c \"\nimport json, sys\ndata = json.load(s
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<string>", line 3, in <module>     data = json.load(sys.stdin)   File "/opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Vers
```

---

### [13] `bash-exit-nonzero` — Bash — worker:sidecar-leak-forensik — 18:38:20

**input_chars:** 2,110 &nbsp; **output_chars:** 847

**Input preview:**
```
{"command": "python3 << 'EOF'\nimport json\nf = \"/Users/brunowinter2000/Documents/ai/Monitor_CC/src/logs/api_requests_opus_monitor_cc_1777214068.json
```

**Error content:**
```
Exit code 1 === Line 9 msg[5] (Bash call) ===   c[0] type=thinking   c[1] text: '📋 PLAN — Phase 1, Step 2: Investigation'   c[2] tool_use name=Bash input={"command": "for id in 1k8 889 8k7 9mf a4i b8j
```

---

### [14] `bash-exit-nonzero` — Bash — worker:thinking-cap — 21:18:21

**input_chars:** 95 &nbsp; **output_chars:** 515

**Input preview:**
```
{"command": "python3 -c \"from src.proxy.rules import apply_modification_rules; print('OK')\""}
```

**Error content:**
```
Exit code 1 Traceback (most recent call last):   File "<string>", line 1, in <module>     from src.proxy.rules import apply_modification_rules; print('OK')     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

---

### [15] `bash-exit-nonzero` — Bash — worker:waste-pane-leak-forensik — 21:32:22

**input_chars:** 110 &nbsp; **output_chars:** 11

**Input preview:**
```
{"command": "grep -rn \"api_requests_worker\" ~/Documents/ai/Meta/blank/iterative-dev/src/spawn/ 2>/dev/null"}
```

**Error content:**
```
Exit code 2
```

---
