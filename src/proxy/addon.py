# INFRASTRUCTURE
import gzip
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from mitmproxy import http

from .addon_state import DualLogPaths, DeltaState, FixationState, SessionIdentity
from .addon_dual_log import (
    _resolve_dual_log_file, _write_entry, _log_original_request,
    _write_request_dual_logs, _log_4xx_error, _write_stripped_injected,
)


class _TrailerCrashFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            exc_type, exc_val, _ = record.exc_info
            if exc_type is NotImplementedError and "trailers" in str(exc_val).lower():
                return False
        return True


logging.getLogger("mitmproxy.proxy.server").addFilter(_TrailerCrashFilter())
from .message_summary import _infer_model_family, _summarize_message
from .rules import apply_modification_rules, _strip_blocked_tool_references
from .inject_helpers import _inject_context_management, _inject_model_override
from .content_strip import _strip_tool_descriptions, _strip_sys3
from .cache import _strip_all_cache_control, _set_cache_breakpoints
from .tools import _strip_unused_tools, _extract_deferred_tool_names
from .tool_injection import inject_mcp_tools
from .fixation import _capture_fixation, _apply_fixation
from .bg_escape import _trigger_bg_escape
ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"

# ORCHESTRATOR

class ProxyAddon:
    def __init__(self):
        self.paths = DualLogPaths(
            original=_resolve_dual_log_file("original"),
            forwarded=_resolve_dual_log_file("forwarded"),
            stripped=_resolve_dual_log_file("stripped"),
            injected=_resolve_dual_log_file("injected"),
            errors=_resolve_dual_log_file("errors"),
            response=_resolve_dual_log_file("response"),
        )
        self.delta = DeltaState()
        self.fixation = FixationState()
        self.identity = SessionIdentity(
            session_id=_derive_session_id(),
            worker_context=_derive_worker_context(),
        )

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
            flow.metadata["mc_original_payload"] = payload

            model_family = _infer_model_family(payload.get("model", ""))
            project_path = os.environ.get("PROXY_PROJECT_PATH", "")

            _log_original_request(self.paths.original, flow, payload)

            modified_payload, modifications, original_system2, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, all_ops = apply_modification_rules(payload, model_family, project_path, self.identity.worker_context)
            deferred_tool_names = _extract_deferred_tool_names(payload)

            modified_payload = _apply_sys_fixation(self.fixation, model_family, modified_payload, modifications)

            modified_payload, modifications = _run_post_fixation_pipeline(
                modified_payload, modifications, model_family, project_path, self.fixation.model_params_fixated
            )

            mc_request_id, mc_timestamp = _stamp_request_metadata(flow, stripped_msg_removed, injected_msg_added, all_ops)

            try:
                _trigger_bg_escape(stripped_msg_removed, self.identity.worker_context, project_path)
            except Exception as e:
                print(f"[proxy_addon] bg_escape trigger failed: {e}", file=sys.stderr)

            modified_payload = _finalize_cache_state(self.delta, model_family, modified_payload)
            _write_request_dual_logs(flow, payload, modified_payload, model_family, mc_request_id, mc_timestamp, self.paths, self.delta, self.identity)

            flow.metadata["mc_modified_payload"] = modified_payload
            flow.metadata["mc_model_family"] = model_family
            flow.request.content = json.dumps(modified_payload).encode("utf-8")
            flow.request.headers.pop("content-encoding", None)
        except Exception as e:
            print(f"[proxy_addon] Error: {e}", file=sys.stderr)

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        try:
            if not _is_messages_request(flow):
                return
            if flow.response and 200 <= flow.response.status_code < 300:
                flow.response.stream = True
        except Exception as e:
            print(f"[proxy_addon] Error in responseheaders hook: {e}", file=sys.stderr)
        try:
            if _is_messages_request(flow) and flow.response:
                entry = {
                    "flow_id": flow.id,
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "request_id": flow.response.headers.get("request-id", ""),
                    "status_code": flow.response.status_code,
                    "headers": _filter_response_headers(flow.response.headers),
                }
                _write_entry(self.paths.response, entry)
        except Exception as e:
            print(f"[dual_log] response write failed: {e}", file=sys.stderr)

    def response(self, flow: http.HTTPFlow) -> None:
        try:
            if not _is_messages_request(flow):
                return
            if flow.response and 400 <= flow.response.status_code < 500:
                _log_4xx_error(flow, self.paths.errors)
                return
            if flow.response and flow.response.status_code < 400:
                try:
                    _write_stripped_injected(flow, self.delta, self.paths)
                except Exception as e:
                    print(f"[dual_log] stripped/injected write failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[proxy_addon] Error in response hook: {e}", file=sys.stderr)


# FUNCTIONS

def _apply_sys_fixation(fixation_state, model_family: str, modified_payload: dict, modifications: list) -> dict:
    if model_family not in fixation_state.fixated:
        fixation_state.fixated[model_family] = _capture_fixation(modified_payload, modifications)
        return modified_payload
    return _apply_fixation(modified_payload, modifications, fixation_state.fixated[model_family])


def _run_post_fixation_pipeline(modified_payload: dict, modifications: list, model_family: str, project_path: str, fixated_model_override: dict) -> tuple:
    modified_payload, stripped_count, _ = _strip_unused_tools(modified_payload)
    if stripped_count > 0:
        modifications.append(f"stripped_{stripped_count}_unused_tools")
    modified_payload = inject_mcp_tools(modified_payload, project_path)
    modifications.append("injected_mcp_tools")
    modified_payload, desc_stripped, _ = _strip_tool_descriptions(modified_payload)
    if desc_stripped > 0:
        modifications.append(f"stripped_tool_descs_{desc_stripped}")
    modified_payload, sys3_stripped, _ = _strip_sys3(modified_payload)
    if sys3_stripped:
        modifications.append("stripped_sys3")
    modified_payload = _strip_blocked_tool_references(modified_payload)
    modified_payload, cm_injected = _inject_context_management(modified_payload)
    if cm_injected:
        modifications.append("injected_context_management")
    modified_payload, model_overridden = _inject_model_override(modified_payload, model_family, fixated_model_override)
    if model_overridden:
        modifications.append("injected_model_override")
    return modified_payload, modifications


def _stamp_request_metadata(flow, stripped_msg_removed, injected_msg_added, all_ops) -> tuple:
    mc_request_id = flow.request.headers.get("x-request-id") or str(uuid.uuid4())
    now_ts = datetime.now(timezone.utc)
    mc_timestamp = f"{now_ts.strftime('%Y-%m-%dT%H:%M:%S.')}{now_ts.microsecond // 1000:03d}Z"
    flow.metadata["mc_request_id"] = mc_request_id
    flow.metadata["mc_stripped_msg_removed"] = stripped_msg_removed
    flow.metadata["mc_injected_msg_added"] = injected_msg_added
    flow.metadata["mc_all_ops"] = all_ops
    return mc_request_id, mc_timestamp


def _finalize_cache_state(delta_state, model_family: str, modified_payload: dict) -> dict:
    prev_mod_msgs = delta_state.messages_by_model.get(model_family)
    modified_payload = _strip_all_cache_control(modified_payload)
    modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)
    delta_state.messages_by_model[model_family] = [
        _summarize_message(m) for m in modified_payload.get("messages", [])
    ]
    return modified_payload


_RESPONSE_HEADER_EXACT = frozenset({"request-id", "retry-after", "anthropic-organization-id"})
_RESPONSE_HEADER_PREFIXES = ("anthropic-ratelimit-", "anthropic-priority-", "anthropic-fast-")


def _filter_response_headers(headers) -> dict:
    result = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _RESPONSE_HEADER_EXACT or kl.startswith(_RESPONSE_HEADER_PREFIXES):
            result[kl] = v
    return result


def _is_messages_request(flow: http.HTTPFlow) -> bool:
    path = flow.request.path
    return (
        flow.request.method == "POST"
        and flow.request.pretty_host == ANTHROPIC_API_HOST
        and (path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?"))
    )


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


def _parse_payload(body: bytes) -> Optional[dict]:
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _derive_session_id() -> str:
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    if project_path:
        return hashlib.md5(project_path.encode()).hexdigest()[:8]
    return ""


def _derive_worker_context() -> str:
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID") or ""
    if log_id.startswith("worker_"):
        parts = log_id.split("_")
        if len(parts) >= 4:
            return "worker:" + "_".join(parts[2:-1])
    return "main"


addons = [ProxyAddon()]
