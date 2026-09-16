# INFRASTRUCTURE
import json
import re
from collections import defaultdict

_HOOK_PREFIX_RE     = re.compile(r'^PreToolUse:\w+ hook error: \[python3 ', re.MULTILINE)
_TOOL_USE_ERROR_RE  = re.compile(r'^<tool_use_error>')
_EXIT_CODE_RE       = re.compile(r'^Exit code (\d+)')
_REJECTION_MARKER   = "doesn't want to proceed"


# FUNCTIONS

# Load all records from tool_errors.jsonl; return list of dicts
def load_entries(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# Assign each entry to exactly one bucket; return dict bucket_name → list of entries
def cluster_entries(entries: list) -> dict:
    buckets = defaultdict(list)
    for e in entries:
        t = e.get("error_full", "")
        if _HOOK_PREFIX_RE.search(t):
            buckets["hook_prefixed"].append(e)
        elif _TOOL_USE_ERROR_RE.match(t):
            buckets["tool_use_error"].append(e)
        elif _EXIT_CODE_RE.match(t):
            m = _EXIT_CODE_RE.match(t)
            if m.group(1) == "0":
                buckets["exit_code_0"].append(e)
            else:
                buckets["exit_code_nonzero"].append(e)
        elif _REJECTION_MARKER in t:
            buckets["rejection"].append(e)
        elif t:
            buckets["bare_guidance"].append(e)
        else:
            buckets["other"].append(e)
    return dict(buckets)
