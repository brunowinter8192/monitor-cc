# INFRASTRUCTURE
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from mitmproxy import http

from .logging import _build_entry, _summarize_content_for_log
from .message_summary import _summarize_message, _has_cache_control
from .rules import apply_modification_rules, _strip_blocked_tool_references
from .cache import _strip_all_cache_control, _set_cache_breakpoints
from .tools import _strip_unused_tools

ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"
DEFAULT_LOG_FILE = Path("/tmp/api_requests.jsonl")

# ORCHESTRATOR

class ProxyAddon:
    def __init__(self):
        self.log_file = _resolve_log_file()
        self.prev_messages_by_model: Dict[str, list] = {}

    def request(self, flow: http.HTTPFlow) -> None:
        try:
            if not _is_messages_request(flow):
                return

            body = _decode_body(flow.request)
            if body is None:
                return

            payload = _parse_payload(body)
            if payload is None:
                return

            model = payload.get("model", "")
            model_lower = model.lower()
            if "haiku" in model_lower:
                model_family = "haiku"
            elif "sonnet" in model_lower:
                model_family = "sonnet"
            else:
                model_family = "opus"
            project_path = os.environ.get("PROXY_PROJECT_PATH", "")
            modified_payload, modifications, original_system2, stripped_msg_indices, stripped_msg_originals = apply_modification_rules(payload, model_family, project_path)

            entry = _build_entry(flow, modified_payload, self.prev_messages_by_model.get(model_family), modifications)
            if original_system2 is not None:
                entry['original_system2_text'] = original_system2
            entry['stripped_msg_indices'] = stripped_msg_indices
            if stripped_msg_originals:
                entry['stripped_msg_originals'] = {}
                for k, v in stripped_msg_originals.items():
                    entry['stripped_msg_originals'][str(k)] = _summarize_content_for_log(v)
            _write_entry(self.log_file, entry)

            modified_payload, stripped_count = _strip_unused_tools(modified_payload)
            if stripped_count > 0:
                modifications.append(f"stripped_{stripped_count}_unused_tools")
            modified_payload = _strip_blocked_tool_references(modified_payload)

            prev_mod_msgs = self.prev_messages_by_model.get(model_family)
            modified_payload = _strip_all_cache_control(modified_payload)
            modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)

            self.prev_messages_by_model[model_family] = [
                _summarize_message(m) for m in modified_payload.get("messages", [])
            ]

            sent_meta = _build_sent_meta(modified_payload, entry.get("request_id", ""), entry.get("timestamp", ""))
            _write_entry(self.log_file, sent_meta)

            flow.request.content = json.dumps(modified_payload).encode("utf-8")
            flow.request.headers.pop("content-encoding", None)
        except Exception as e:
            print(f"[proxy_addon] Error: {e}", file=sys.stderr)
            try:
                error_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_url": flow.request.pretty_url if flow else "unknown",
                }
                _write_entry(self.log_file, error_entry)
            except Exception:
                pass

    def response(self, flow: http.HTTPFlow) -> None:
        """Log full request payload when API returns 4xx error — for debugging malformed requests."""
        try:
            if not _is_messages_request(flow):
                return
            if flow.response and 400 <= flow.response.status_code < 500:
                resp_body = ""
                try:
                    resp_body = flow.response.content.decode("utf-8", errors="replace")[:2000]
                except Exception:
                    pass
                req_payload = None
                try:
                    req_payload = json.loads(flow.request.content.decode("utf-8", errors="replace"))
                except Exception:
                    pass
                log_dir = os.path.dirname(self.log_file)
                error_file = os.path.join(log_dir, f"api_error_payload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
                error_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "status_code": flow.response.status_code,
                    "error_response": resp_body,
                    "request_url": flow.request.pretty_url,
                    "request_payload": req_payload,
                }
                with open(error_file, "w", encoding="utf-8") as f:
                    json.dump(error_data, f, indent=2, ensure_ascii=False)
                print(f"[proxy_addon] API {flow.response.status_code} error — payload saved to {error_file}", file=sys.stderr)
        except Exception as e:
            print(f"[proxy_addon] Error in response hook: {e}", file=sys.stderr)


# FUNCTIONS

# Resolve log file path from env vars — log_id gives per-proxy-start isolation
def _resolve_log_file() -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID")
    filename = f"api_requests_{log_id}.jsonl" if log_id else "api_requests.jsonl"
    if root:
        return Path(root) / "src" / "logs" / filename
    return Path("/tmp") / filename


# Check if flow is a POST to /v1/messages on api.anthropic.com
def _is_messages_request(flow: http.HTTPFlow) -> bool:
    return (
        flow.request.method == "POST"
        and flow.request.pretty_host == ANTHROPIC_API_HOST
        and flow.request.path.startswith(MESSAGES_PATH)
    )


# Decode request body, decompressing gzip if needed
def _decode_body(request: http.Request) -> Optional[bytes]:
    content = request.content
    if not content:
        return None
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            content = gzip.decompress(content)
        except OSError:
            return None
    return content


# Parse JSON payload from bytes
def _parse_payload(body: bytes) -> Optional[dict]:
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


# Build sent_meta entry from the final modified payload — logs what was actually sent to the API
def _build_sent_meta(payload: dict, request_id: str, timestamp: str) -> dict:
    tools = payload.get("tools", []) or []
    system = payload.get("system", []) or []
    messages = payload.get("messages", []) or []
    tool_names = sorted(t.get("name", "") for t in tools if isinstance(t, dict))

    sys_bps = [i for i, b in enumerate(system) if isinstance(b, dict) and b.get("cache_control")]
    tool_bps = [i for i, t in enumerate(tools) if isinstance(t, dict) and t.get("cache_control")]
    msg_bps = [i for i, m in enumerate(messages) if _has_cache_control(m)]

    bp1_idx = sys_bps[0] if sys_bps else None
    bp2_idx = tool_bps[0] if tool_bps else None
    bp3_idx = msg_bps[0] if msg_bps else None
    bp4_idx = msg_bps[-1] if len(msg_bps) >= 2 else None

    def _md5(data: str) -> str:
        return hashlib.md5(data.encode("utf-8")).hexdigest()[:10]

    prefix_hash_bp1 = _md5(json.dumps(system[0:bp1_idx + 1])) if bp1_idx is not None else None
    prefix_hash_bp2 = _md5(json.dumps({"system": system, "tools": tools[0:bp2_idx + 1]})) if bp2_idx is not None else None
    prefix_hash_bp3 = _md5(json.dumps({"system": system, "tools": tools, "messages": messages[0:bp3_idx + 1]})) if bp3_idx is not None else None
    prefix_hash_bp4 = _md5(json.dumps({"system": system, "tools": tools, "messages": messages[0:bp4_idx + 1]})) if bp4_idx is not None else None

    return {
        "type": "sent_meta",
        "request_id": request_id,
        "timestamp": timestamp,
        "sent_tools_count": len(tools),
        "sent_tools_hash": hashlib.md5(json.dumps(tool_names).encode()).hexdigest()[:8],
        "sent_cache_breakpoints": {
            "system": sys_bps,
            "tools": tool_bps,
            "messages": msg_bps,
        },
        "sent_system_hash": hashlib.md5(json.dumps(system).encode()).hexdigest()[:8],
        "sent_tools_bytes_hash": hashlib.md5(json.dumps(tools).encode()).hexdigest()[:8],
        "prefix_hash_bp1_sys": prefix_hash_bp1,
        "prefix_hash_bp2_tools": prefix_hash_bp2,
        "prefix_hash_bp3_msg": prefix_hash_bp3,
        "prefix_hash_bp4_msg": prefix_hash_bp4,
    }


# Append log entry as a single JSONL line, creating parent dirs if needed
def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


addons = [ProxyAddon()]
