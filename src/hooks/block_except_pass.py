# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Bare exception swallow: except [OptionalType]: <newline> pass
# Covers: except: pass, except Exception: pass, except SomeError: pass
_EXCEPT_PASS = re.compile(r'except\s*(?:\w+\s*)?:\s*[\r\n]+\s*pass\b', re.MULTILINE)

_BLOCK_MESSAGE = (
    "BLOCKED: silent exception swallow (`except ...: pass`) detected in written code.\n"
    "Silently swallowing exceptions is PROHIBITED. The script must fail visibly when it\n"
    "cannot fulfill its purpose — hiding exceptions produces invisible bugs that produce\n"
    "wrong outputs without any error signal.\n"
    "\n"
    "Allowed alternatives:\n"
    "  except SomeError:                # re-raise (preserve traceback)\n"
    "      raise\n"
    "  except SomeError as e:           # log + re-raise\n"
    "      logger.error(e); raise\n"
    "  except SomeError as e:           # explicit fallback with logging\n"
    "      logger.warning(e); return default_value\n"
    "  finally:                         # resource cleanup (no pass needed)\n"
    "      resource.close()\n"
    "code-standards.md \u00a7 Error Handling.\n"
)

# ORCHESTRATOR

# Read Write or Edit tool_input; exit 2 + stderr if content contains a bare except-pass block
def block_except_pass_workflow() -> None:
    content, file_path, session_id = _parse_content()
    if content is None:
        sys.exit(0)
    if _EXCEPT_PASS.search(content):
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_except_pass", "block", "Write/Edit", file_path or "", reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (content, file_path, session_id); (None, None, None) on error
def _parse_content():
    try:
        payload = json.loads(sys.stdin.read())
        tool_name = payload.get("tool_name", "")
        inp = payload.get("tool_input", {})
        file_path = inp.get("file_path") if isinstance(inp.get("file_path"), str) else None
        sid = payload.get("session_id")
        if tool_name == "Write":
            content = inp.get("content", "")
        elif tool_name == "Edit":
            content = inp.get("new_string", "")
        else:
            return None, None, None
        return (content if isinstance(content, str) else None), file_path, sid
    except Exception:
        return None, None, None


if __name__ == "__main__":
    block_except_pass_workflow()
