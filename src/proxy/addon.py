# INFRASTRUCTURE
import gzip
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from mitmproxy import http

from src.proxy.proxy_error_log import log_proxy_error, log_proxy_error_on_change
from src.proxy.addon_state import DualLogPaths, DeltaState, FixationState, SessionIdentity
from src.proxy.addon_dual_log import (
    _resolve_dual_log_file, _write_entry, proxy_log_id, _log_original_request,
    _write_request_dual_logs, _log_4xx_error, _write_stripped_injected,
)
from src.proxy.message_summary import _infer_model_family, _summarize_message
from src.proxy.rules import apply_modification_rules, _strip_blocked_tool_references
from src.proxy.inject_helpers import _inject_context_management, _inject_model_override, _strip_clear_thinking_edit
from src.proxy.content_strip import _strip_tool_descriptions, _strip_sys3
from src.proxy.cache import _strip_all_cache_control, _set_cache_breakpoints
from src.proxy.tools import _strip_unused_tools, _extract_deferred_tool_names
from src.proxy.tool_injection import inject_mcp_tools
from src.proxy.fixation import _capture_fixation, _apply_fixation
from src.proxy.bg_escape import _trigger_bg_escape
from src.proxy.response_model_probe import make_answering_model_probe

ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"

_RESPONSE_HEADER_EXACT = frozenset({
    "request-id", "retry-after", "anthropic-organization-id",
    "content-type", "content-encoding",
})
_RESPONSE_HEADER_PREFIXES = ("anthropic-ratelimit-", "anthropic-priority-", "anthropic-fast-")


# FUNCTIONS

class ProxyAddon:
    def __init__(self):
        self.paths = _build_dual_log_paths()
        self.delta = DeltaState()
        self.fixation = FixationState()
        self.identity = _build_identity()

    def request(self, flow: http.HTTPFlow) -> None:
        _guarded("request", _process_request, self, flow)

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        _guarded("responseheaders", _process_responseheaders, self, flow)

    def response(self, flow: http.HTTPFlow) -> None:
        _guarded("response", _process_response, self, flow)

    def error(self, flow: http.HTTPFlow) -> None:
        _guarded("error", _process_error, self, flow)


class _TrailerCrashFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            exc_type, exc_val, _ = record.exc_info
            if exc_type is NotImplementedError and "trailers" in str(exc_val).lower():
                return False
        return True


def _build_dual_log_paths() -> DualLogPaths:
    return DualLogPaths(
        original=_resolve_dual_log_file("original"),
        forwarded=_resolve_dual_log_file("forwarded"),
        stripped=_resolve_dual_log_file("stripped"),
        injected=_resolve_dual_log_file("injected"),
        errors=_resolve_dual_log_file("errors"),
        response=_resolve_dual_log_file("response"),
    )


def _build_identity() -> SessionIdentity:
    return SessionIdentity(
        session_id=_derive_session_id(),
        worker_context=_derive_worker_context(),
    )


def _derive_session_id() -> str:
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    if project_path:
        return hashlib.md5(project_path.encode()).hexdigest()[:8]
    return ""


def _derive_worker_context() -> str:
    log_id = proxy_log_id()
    if not log_id.startswith("worker_"):
        return "main"
    parts = log_id.split("_")
    if len(parts) < 4:
        raise ValueError(f"unparsable worker log id: {log_id!r}")
    return "worker:" + "_".join(parts[2:-1])


def _guarded(name: str, handler, addon: "ProxyAddon", flow: http.HTTPFlow) -> None:
    try:
        handler(addon, flow)
    except Exception as e:
        log_proxy_error(f"addon.{name} flow={flow.id}", e)


def _process_request(addon: "ProxyAddon", flow: http.HTTPFlow) -> None:
    if not _is_messages_request(flow):
        return
    payload = _read_payload(flow)
    if payload is None:
        return
    flow.metadata["mc_original_payload"] = payload
    model_family = _resolve_model_family(payload)
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    _log_original_request(addon.paths.original, flow, payload)
    modified_payload, stripped_msg_removed, injected_msg_added, all_ops, modifications = _rewrite_payload(
        addon, payload, model_family, project_path
    )
    mc_request_id, mc_timestamp = _stamp_request_metadata(flow, stripped_msg_removed, injected_msg_added, all_ops)
    _escape_background_tasks(flow, stripped_msg_removed, addon.identity.worker_context, project_path)
    modified_payload = _finalize_cache_state(addon.delta, model_family, modified_payload)
    _write_request_dual_logs(flow, payload, modified_payload, model_family, mc_request_id, mc_timestamp, addon.paths, addon.delta, addon.identity)
    _forward_modified_payload(flow, modified_payload, model_family)


def _is_messages_request(flow: http.HTTPFlow) -> bool:
    path = flow.request.path
    return (
        flow.request.method == "POST"
        and flow.request.pretty_host == ANTHROPIC_API_HOST
        and (path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?"))
    )


def _read_payload(flow: http.HTTPFlow) -> Optional[dict]:
    body = _decode_body(flow.request)
    if body is None:
        return None
    return _parse_payload(body)


def _decode_body(request: http.Request) -> Optional[bytes]:
    content = request.content
    if not content:
        return None
    if request.headers.get("content-encoding", "").lower() == "gzip":
        try:
            content = gzip.decompress(content)
        except OSError as e:
            log_proxy_error("addon._decode_body", e)
            return None
    return content


def _parse_payload(body: bytes) -> Optional[dict]:
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log_proxy_error("addon._parse_payload", e)
        return None


def _resolve_model_family(payload: dict) -> str:
    model_family = _infer_model_family(payload.get("model", ""))
    if model_family == "unknown":
        log_proxy_error_on_change("addon.model_family", f"unknown model family for model {payload.get('model', '')!r}")
    return model_family


def _rewrite_payload(addon: "ProxyAddon", payload: dict, model_family: str, project_path: str) -> tuple:
    modified_payload, modifications, original_system2, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added, all_ops = apply_modification_rules(payload, model_family, project_path, addon.identity.worker_context)
    deferred_tool_names = _extract_deferred_tool_names(payload)
    modified_payload = _apply_sys_fixation(addon.fixation, model_family, modified_payload, modifications)
    modified_payload, modifications = _run_post_fixation_pipeline(
        modified_payload, modifications, project_path, addon.fixation.model_params_fixated
    )
    return modified_payload, stripped_msg_removed, injected_msg_added, all_ops, modifications


def _apply_sys_fixation(fixation_state, model_family: str, modified_payload: dict, modifications: list) -> dict:
    if model_family not in fixation_state.fixated:
        fixation_state.fixated[model_family] = _capture_fixation(modified_payload, modifications)
        return modified_payload
    return _apply_fixation(modified_payload, modifications, fixation_state.fixated[model_family])


def _run_post_fixation_pipeline(modified_payload: dict, modifications: list, project_path: str, fixated_model_override: dict) -> tuple:
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
    modified_payload, model_overridden = _inject_model_override(modified_payload, fixated_model_override)
    if model_overridden:
        modifications.append("injected_model_override")
    modified_payload, clear_thinking_stripped = _strip_clear_thinking_edit(modified_payload)
    if clear_thinking_stripped:
        modifications.append("stripped_clear_thinking_edit")
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


def _escape_background_tasks(flow: http.HTTPFlow, stripped_msg_removed: dict, worker_context: str, project_path: str) -> None:
    try:
        _trigger_bg_escape(stripped_msg_removed, worker_context, project_path)
    except Exception as e:
        log_proxy_error(f"addon.request.bg_escape flow={flow.id}", e)


def _finalize_cache_state(delta_state, model_family: str, modified_payload: dict) -> dict:
    prev_mod_msgs = delta_state.messages_by_model.get(model_family)
    modified_payload = _strip_all_cache_control(modified_payload)
    modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)
    delta_state.messages_by_model[model_family] = [
        _summarize_message(m) for m in modified_payload.get("messages", [])
    ]
    return modified_payload


def _forward_modified_payload(flow: http.HTTPFlow, modified_payload: dict, model_family: str) -> None:
    flow.metadata["mc_modified_payload"] = modified_payload
    flow.metadata["mc_model_family"] = model_family
    flow.request.content = json.dumps(modified_payload).encode("utf-8")
    flow.request.headers.pop("content-encoding", None)
    _request_identity_encoding(flow)


def _request_identity_encoding(flow: http.HTTPFlow) -> None:
    flow.request.headers["accept-encoding"] = "identity"


def _process_responseheaders(addon: "ProxyAddon", flow: http.HTTPFlow) -> None:
    if not _is_messages_request(flow):
        return
    if flow.response and 200 <= flow.response.status_code < 300:
        probe, probe_state = make_answering_model_probe()
        flow.response.stream = probe
        flow.metadata["mc_answering_model_state"] = probe_state


def _process_response(addon: "ProxyAddon", flow: http.HTTPFlow) -> None:
    if not _is_messages_request(flow):
        return
    if flow.response:
        _write_response_and_mismatch(flow, addon.paths, addon.identity)
    if flow.response and 400 <= flow.response.status_code < 500:
        _log_4xx_error(flow, addon.paths.errors)
        return
    if flow.response and flow.response.status_code < 400:
        _write_stripped_injected_guarded(flow, addon)


def _write_response_and_mismatch(flow: http.HTTPFlow, paths, identity) -> None:
    response_entry = None
    try:
        response_entry = _write_response_entry(flow, paths.response)
    except Exception as e:
        log_proxy_error(f"addon.response_entry flow={flow.id}", e)
    if response_entry is not None:
        try:
            _write_model_mismatch_entry(flow, response_entry, paths.errors, identity)
        except Exception as e:
            log_proxy_error(f"addon.model_mismatch flow={flow.id}", e)


def _write_response_entry(flow: http.HTTPFlow, log_file) -> Optional[dict]:
    if flow.metadata.get("mc_response_entry_written"):
        return None
    flow.metadata["mc_response_entry_written"] = True
    original_payload = flow.metadata.get("mc_original_payload") or {}
    modified_payload = flow.metadata.get("mc_modified_payload") or {}
    probe_state = flow.metadata.get("mc_answering_model_state") or {}
    entry = {
        "flow_id": flow.id,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "request_id": flow.response.headers.get("request-id", ""),
        "status_code": flow.response.status_code,
        "headers": _filter_response_headers(flow.response.headers),
        "cc_requested_model": original_payload.get("model", ""),
        "proxy_forwarded_model": modified_payload.get("model", ""),
        "answering_model": probe_state.get("model", ""),
    }
    _write_entry(log_file, entry)
    return entry


def _filter_response_headers(headers) -> dict:
    result = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _RESPONSE_HEADER_EXACT or kl.startswith(_RESPONSE_HEADER_PREFIXES):
            result[kl] = v
    return result


def _write_model_mismatch_entry(flow: http.HTTPFlow, response_entry: dict, errors_log_file, identity) -> None:
    if flow.metadata.get("mc_model_mismatch_logged"):
        return
    forwarded_model = response_entry.get("proxy_forwarded_model", "")
    answering_model = response_entry.get("answering_model", "")
    if not answering_model or answering_model == forwarded_model:
        return
    flow.metadata["mc_model_mismatch_logged"] = True
    now_ts = datetime.now(timezone.utc)
    ts = f"{now_ts.strftime('%Y-%m-%dT%H:%M:%S.')}{now_ts.microsecond // 1000:03d}Z"
    entry = {
        "type": "model_mismatch",
        "request_id": response_entry.get("request_id", ""),
        "timestamp": ts,
        "ts": ts,
        "session_id": identity.session_id,
        "worker": identity.worker_context,
        "tool_name": "model_mismatch",
        "tool_use_id": "",
        "error_full": f"model mismatch — requested {forwarded_model}, answered {answering_model}",
        "proxy_file": "",
        "flow_id": response_entry.get("flow_id", ""),
    }
    _write_entry(errors_log_file, entry)


def _write_stripped_injected_guarded(flow: http.HTTPFlow, addon: "ProxyAddon") -> None:
    try:
        _write_stripped_injected(flow, addon.delta, addon.paths)
    except Exception as e:
        log_proxy_error(f"addon.response.stripped_injected flow={flow.id}", e)


def _process_error(addon: "ProxyAddon", flow: http.HTTPFlow) -> None:
    if not _is_messages_request(flow):
        return
    if flow.response:
        _write_response_and_mismatch(flow, addon.paths, addon.identity)


logging.getLogger("mitmproxy.proxy.server").addFilter(_TrailerCrashFilter())


addons = [ProxyAddon()]
