# INFRASTRUCTURE
import datetime
import json
import os
import sys


# FUNCTIONS

def log_fire(hook_name: str, decision: str, tool_name: str, command: str,
             reason: str = None, rewritten: str = None, session_id: str = None) -> None:
    try:
        log_path = os.environ.get(
            "MONITOR_CC_HOOK_FIRING_LOG",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'logs', 'hook_firing.jsonl',
            ),
        )
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hook": hook_name,
            "decision": decision,
            "tool": tool_name,
            "command": command or "",
            "session": session_id or "",
        }
        if decision in ("block", "feedback", "trace"):
            record["reason"] = reason or ""
        else:
            record["rewritten"] = rewritten or ""
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"log_fire failed: {type(e).__name__}: {e}", file=sys.stderr)
