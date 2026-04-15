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
from .tool_injection import inject_mcp_tools, _load_active_plugins

ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"
DEFAULT_LOG_FILE = Path("/tmp/api_requests.jsonl")

# ORCHESTRATOR

class ProxyAddon:
    def __init__(self):
        self.log_file = _resolve_log_file()
        self.prev_messages_by_model: Dict[str, list] = {}
        self.fixated: dict = {}  # model_family → {"sys2_text": str, "msg0_pr_block": str}
        self.prev_sent_hashes_by_model: dict = {}  # model_family → hash fields from last sent_meta

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
            modified_payload, modifications, original_system2, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed = apply_modification_rules(payload, model_family, project_path)

            if model_family not in self.fixated:
                self.fixated[model_family] = _capture_fixation(modified_payload, modifications)
            else:
                modified_payload = _apply_fixation(modified_payload, modifications, self.fixated[model_family])

            modified_payload, stripped_count = _strip_unused_tools(modified_payload)
            if stripped_count > 0:
                modifications.append(f"stripped_{stripped_count}_unused_tools")

            modified_payload = inject_mcp_tools(modified_payload, project_path)
            modifications.append("injected_mcp_tools")

            modified_payload = _strip_blocked_tool_references(modified_payload)

            entry = _build_entry(flow, modified_payload, self.prev_messages_by_model.get(model_family), modifications)
            if original_system2 is not None:
                entry['original_system2_text'] = original_system2
            entry['stripped_msg_indices'] = stripped_msg_indices
            if stripped_msg_originals:
                entry['stripped_msg_originals'] = {}
                for k, v in stripped_msg_originals.items():
                    entry['stripped_msg_originals'][str(k)] = _summarize_content_for_log(v)
            if stripped_msg_removed:
                entry['stripped_msg_removed'] = {str(k): v for k, v in stripped_msg_removed.items()}
            _write_entry(self.log_file, entry)

            prev_mod_msgs = self.prev_messages_by_model.get(model_family)
            modified_payload = _strip_all_cache_control(modified_payload)
            modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)

            self.prev_messages_by_model[model_family] = [
                _summarize_message(m) for m in modified_payload.get("messages", [])
            ]

            prev_hashes = self.prev_sent_hashes_by_model.get(model_family)
            sent_meta = _build_sent_meta(modified_payload, entry.get("request_id", ""), entry.get("timestamp", ""), prev_hashes)
            self.prev_sent_hashes_by_model[model_family] = {
                "sys_block_hashes": sent_meta.get("sys_block_hashes", []),
                "tool_hashes": sent_meta.get("tool_hashes", []),
                "msg_hashes": sent_meta.get("msg_hashes", []),
                "msg0_block_hashes": sent_meta.get("msg0_block_hashes", []),
            }
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


# Capture fixation values from first modified payload — sys[2] text, msg[0] project-rules block, active_plugins
def _capture_fixation(payload: dict, modifications: list) -> dict:
    fixated = {}
    system = payload.get("system", [])
    if isinstance(system, list) and len(system) > 2:
        block2 = system[2]
        if isinstance(block2, dict) and block2.get("type") == "text":
            fixated["sys2_text"] = block2.get("text", "")
    if "injected_project_rules" in modifications:
        msgs = payload.get("messages", [])
        if msgs:
            content = msgs[0].get("content", "")
            if isinstance(content, list) and content:
                first_block = content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "text":
                    fixated["msg0_pr_block"] = first_block.get("text", "")
            elif isinstance(content, str):
                end_tag = "</system-reminder>"
                idx = content.find(end_tag)
                if idx != -1:
                    fixated["msg0_pr_block_str"] = content[:idx + len(end_tag)]
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    fixated["active_plugins"] = _load_active_plugins(project_path)
    return fixated


# Apply fixated content to payload — replaces sys[2] text, msg[0] rules block; updates active_plugins fixation if changed
def _apply_fixation(payload: dict, modifications: list, fixated: dict) -> dict:
    if not fixated:
        return payload
    result = payload
    if "sys2_text" in fixated:
        system = result.get("system", [])
        if isinstance(system, list) and len(system) > 2:
            block2 = system[2]
            if isinstance(block2, dict) and block2.get("type") == "text":
                new_system = list(system)
                new_system[2] = {**block2, "text": fixated["sys2_text"]}
                result = {**result, "system": new_system}
    if "injected_project_rules" in modifications:
        msgs = result.get("messages", [])
        if msgs:
            content = msgs[0].get("content", "")
            if isinstance(content, list) and content and "msg0_pr_block" in fixated:
                first_block = content[0]
                if isinstance(first_block, dict) and first_block.get("type") == "text":
                    new_content = [{**first_block, "text": fixated["msg0_pr_block"]}] + list(content[1:])
                    new_msgs = list(msgs)
                    new_msgs[0] = {**msgs[0], "content": new_content}
                    result = {**result, "messages": new_msgs}
            elif isinstance(content, str) and "msg0_pr_block_str" in fixated:
                end_tag = "</system-reminder>"
                idx = content.find(end_tag)
                if idx != -1:
                    old_prefix_end = idx + len(end_tag)
                    new_content_str = fixated["msg0_pr_block_str"] + content[old_prefix_end:]
                    new_msgs = list(msgs)
                    new_msgs[0] = {**msgs[0], "content": new_content_str}
                    result = {**result, "messages": new_msgs}
    if "active_plugins" in fixated:
        project_path = os.environ.get("PROXY_PROJECT_PATH", "")
        current_plugins = _load_active_plugins(project_path)
        if current_plugins != fixated["active_plugins"]:
            fixated["active_plugins"] = current_plugins
            modifications.append("active_plugins_changed")
    return result


# Compute MD5[:10] hashes for each system block
def _compute_sys_block_hashes(system) -> list:
    if not isinstance(system, list):
        return []
    return [hashlib.md5(json.dumps(b).encode("utf-8")).hexdigest()[:10] for b in system]


# Compute MD5[:10] hashes for each tool
def _compute_tool_hashes(tools: list) -> list:
    return [hashlib.md5(json.dumps(t).encode("utf-8")).hexdigest()[:10] for t in tools]


# Compute per-message hashes: first 10 individually, middle as rolling summary, last 5 individually
def _compute_msg_hashes(messages: list) -> list:
    def _mhash(msg: dict) -> str:
        return hashlib.md5(json.dumps(msg).encode("utf-8")).hexdigest()[:10]

    n = len(messages)
    if n == 0:
        return []
    first_count = min(10, n)
    last_count = min(5, n)
    middle_start = first_count
    middle_end = max(first_count, n - last_count)
    last_start = middle_end

    result = []
    for i in range(first_count):
        result.append({"idx": i, "role": messages[i].get("role", ""), "hash": _mhash(messages[i])})

    chunk_size = 5
    for chunk_start in range(middle_start, middle_end, chunk_size):
        chunk_end = min(chunk_start + chunk_size, middle_end)
        chunk_hashes = [_mhash(messages[i]) for i in range(chunk_start, chunk_end)]
        rolling = hashlib.md5("".join(chunk_hashes).encode("utf-8")).hexdigest()[:10]
        count = chunk_end - chunk_start
        result.append({
            "idx": f"{chunk_start}-{chunk_end - 1}",
            "role": "middle_chunk",
            "hash": f"count={count},rolling={rolling}",
        })

    for i in range(last_start, n):
        result.append({"idx": i, "role": messages[i].get("role", ""), "hash": _mhash(messages[i])})

    return result


# Compute per-block hashes for messages[0].content
def _compute_msg0_block_hashes(messages: list) -> list:
    if not messages:
        return []
    content = messages[0].get("content", "")
    if isinstance(content, str):
        return [hashlib.md5(content.encode("utf-8")).hexdigest()[:10]]
    if isinstance(content, list):
        return [hashlib.md5(json.dumps(b).encode("utf-8")).hexdigest()[:10] for b in content]
    return []


# Compare current hash fields against previous — detect unexpected drift in stable prefix fields
def _compute_drift_report(curr: dict, prev: Optional[dict]) -> dict:
    if prev is None:
        return {"initial": True}

    report: dict = {"sys": [], "tools": [], "msgs": [], "msg0_blocks": []}

    curr_sys = curr.get("sys_block_hashes", [])
    prev_sys = prev.get("sys_block_hashes", [])
    for i in range(min(len(curr_sys), len(prev_sys))):
        if curr_sys[i] != prev_sys[i]:
            report["sys"].append(i)

    curr_tools = curr.get("tool_hashes", [])
    prev_tools = prev.get("tool_hashes", [])
    for i in range(min(len(curr_tools), len(prev_tools))):
        if curr_tools[i] != prev_tools[i]:
            report["tools"].append(i)

    curr_msgs = curr.get("msg_hashes", [])
    prev_msgs = prev.get("msg_hashes", [])
    total_curr = 0
    for e in curr_msgs:
        idx = e.get("idx")
        if isinstance(idx, str) and "-" in idx:
            parts = idx.split("-")
            try:
                total_curr += int(parts[1]) - int(parts[0]) + 1
            except (ValueError, IndexError):
                total_curr += 1
        else:
            total_curr += 1
    stable_threshold = max(0, total_curr - 2)
    for ec, ep in zip(curr_msgs, prev_msgs):
        c_idx = ec.get("idx")
        p_idx = ep.get("idx")
        if c_idx != p_idx:
            break
        if isinstance(c_idx, str) and "-" in c_idx:
            if ec.get("hash") != ep.get("hash"):
                report["msgs"].append(c_idx)
            continue
        if isinstance(c_idx, int) and c_idx >= stable_threshold:
            continue
        if ec.get("hash") != ep.get("hash"):
            report["msgs"].append(c_idx)

    curr_m0 = curr.get("msg0_block_hashes", [])
    prev_m0 = prev.get("msg0_block_hashes", [])
    for i in range(min(len(curr_m0), len(prev_m0))):
        if curr_m0[i] != prev_m0[i]:
            report["msg0_blocks"].append(i)

    return report


# Build sent_meta entry from the final modified payload — logs what was actually sent to the API
def _build_sent_meta(payload: dict, request_id: str, timestamp: str, prev_hashes: Optional[dict] = None) -> dict:
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

    sys_block_hashes = _compute_sys_block_hashes(system)
    tool_hashes = _compute_tool_hashes(tools)
    msg_hashes = _compute_msg_hashes(messages)
    msg0_block_hashes = _compute_msg0_block_hashes(messages)

    curr_hashes = {
        "sys_block_hashes": sys_block_hashes,
        "tool_hashes": tool_hashes,
        "msg_hashes": msg_hashes,
        "msg0_block_hashes": msg0_block_hashes,
    }
    drift_report = _compute_drift_report(curr_hashes, prev_hashes)

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
        "sys_block_hashes": sys_block_hashes,
        "tool_hashes": tool_hashes,
        "msg_hashes": msg_hashes,
        "msg0_block_hashes": msg0_block_hashes,
        "drift_report": drift_report,
    }


# Append log entry as a single JSONL line, creating parent dirs if needed
def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


addons = [ProxyAddon()]
