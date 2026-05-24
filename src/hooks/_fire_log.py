# INFRASTRUCTURE
import datetime
import json
import os

# log_fire decision enum — controls which optional field is included and the API-impact class:
#   "block"    — hook exited 2 + wrote stderr. Agent sees the error and may retry differently.
#                Record includes: reason (stderr text). No rewritten field.
#   "rewrite"  — hook exited 0 + emitted updatedInput JSON. Agent runs the modified input silently.
#                Record includes: rewritten (description of change). No reason field.
#   "ui-notice" — RESERVED for future hooks that only produce a UI side-effect (e.g. Monitor annotation).
#                NO API impact — agent sees neither an error nor a modified input.
#                Filter from FP analysis: jq 'select(.decision != "ui-notice")' hook_firing.jsonl


# FUNCTIONS

# Append one fire-event line to hook_firing.jsonl. Fail-silent on any exception.
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
        if decision == "block":
            record["reason"] = reason or ""
        else:
            record["rewritten"] = rewritten or ""
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return
