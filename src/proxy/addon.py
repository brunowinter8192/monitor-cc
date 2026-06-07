# INFRASTRUCTURE
import gzip
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from mitmproxy import http

from .logging import _build_forwarded_delta, _build_stripped_injected_deltas, _build_errors_entries


# Suppress noise from `NotImplementedError: HTTP trailers are not implemented yet.`
# mitmproxy 12.x hardcodes this raise in proxy/layers/http/_http1.py:118 when an HTTP/1.1
# upstream sends Transfer-Encoding chunked with trailers. Crashes the single connection
# only (other flows unaffected). Filter the LogRecord before it reaches stderr — keeps
# legitimate "mitmproxy has crashed!" messages with other exceptions visible.
class _TrailerCrashFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            exc_type, exc_val, _ = record.exc_info
            if exc_type is NotImplementedError and "trailers" in str(exc_val).lower():
                return False
        return True


logging.getLogger("mitmproxy.proxy.server").addFilter(_TrailerCrashFilter())
from .message_summary import _summarize_message
from .rules import apply_modification_rules, _strip_blocked_tool_references
from .inject_helpers import _inject_context_management, _inject_model_override
from .content_strip import _strip_tool_descriptions, _strip_sys3
from .cache import _strip_all_cache_control, _set_cache_breakpoints
from .tools import _strip_unused_tools, _extract_deferred_tool_names
from .tool_injection import inject_mcp_tools
from .fixation import _capture_fixation, _apply_fixation
ANTHROPIC_API_HOST = "api.anthropic.com"
MESSAGES_PATH = "/v1/messages"

# ORCHESTRATOR

class ProxyAddon:
    def __init__(self):
        self.original_log_file = _resolve_dual_log_file("original")
        self.forwarded_log_file = _resolve_dual_log_file("forwarded")
        self.stripped_log_file = _resolve_dual_log_file("stripped")
        self.injected_log_file = _resolve_dual_log_file("injected")
        self.errors_log_file = _resolve_dual_log_file("errors")
        self.response_log_file = _resolve_dual_log_file("response")
        self.prev_messages_by_model: Dict[str, list] = {}
        self.fixated: dict = {}  # model_family → {"sys2_text": str, "msg0_pr_block": str}
        self.prev_delta_hashes_by_model: dict = {}  # model_family → {"system": [...], "tools": [...], "messages": [...]} for forwarded delta
        self.prev_stripped_hashes_by_model: dict = {}  # model_family → flat loc_key → hash dict for stripped delta
        self.prev_injected_hashes_by_model: dict = {}  # model_family → flat loc_key → hash dict for injected delta
        self.prev_error_ids_by_model: Dict[str, set] = {}  # model_family → set of tool_use_ids already written to _errors
        self._session_id = _derive_session_id()
        self._worker_context = _derive_worker_context()

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

            model = payload.get("model", "")
            model_lower = model.lower()
            if "haiku" in model_lower:
                model_family = "haiku"
            elif "sonnet" in model_lower:
                model_family = "sonnet"
            else:
                model_family = "opus"
            project_path = os.environ.get("PROXY_PROJECT_PATH", "")

            try:
                _write_entry(self.original_log_file, {
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "flow_id": flow.id,
                    "request_id": flow.request.headers.get("x-request-id", ""),
                    "model": payload.get("model", ""),
                    "payload": payload,
                })
            except Exception as e:
                print(f"[dual_log] original write failed: {e}", file=sys.stderr)

            modified_payload, modifications, original_system2, stripped_msg_indices, stripped_msg_originals, stripped_msg_removed, injected_msg_added = apply_modification_rules(payload, model_family, project_path)
            deferred_tool_names = _extract_deferred_tool_names(payload)

            if model_family not in self.fixated:
                self.fixated[model_family] = _capture_fixation(modified_payload, modifications)
            else:
                modified_payload = _apply_fixation(modified_payload, modifications, self.fixated[model_family])

            modified_payload, stripped_count, stripped_tool_names = _strip_unused_tools(modified_payload)
            if stripped_count > 0:
                modifications.append(f"stripped_{stripped_count}_unused_tools")

            modified_payload = inject_mcp_tools(modified_payload, project_path)
            modifications.append("injected_mcp_tools")

            modified_payload, desc_stripped, tool_descs_originals = _strip_tool_descriptions(modified_payload)
            if desc_stripped > 0:
                modifications.append(f"stripped_tool_descs_{desc_stripped}")

            modified_payload, sys3_stripped, sys3_original = _strip_sys3(modified_payload)
            if sys3_stripped:
                modifications.append("stripped_sys3")

            modified_payload = _strip_blocked_tool_references(modified_payload)

            modified_payload, cm_injected = _inject_context_management(modified_payload)
            if cm_injected:
                modifications.append("injected_context_management")

            modified_payload, model_overridden = _inject_model_override(modified_payload, model_family)
            if model_overridden:
                modifications.append("injected_model_override")

            # Derive request_id and timestamp for downstream dual-log writes (replaces _build_entry)
            mc_request_id = flow.request.headers.get("x-request-id") or str(uuid.uuid4())
            now_ts = datetime.now(timezone.utc)
            mc_timestamp = f"{now_ts.strftime('%Y-%m-%dT%H:%M:%S.')}{now_ts.microsecond // 1000:03d}Z"
            flow.metadata["mc_request_id"] = mc_request_id
            flow.metadata["mc_stripped_msg_removed"] = stripped_msg_removed
            flow.metadata["mc_injected_msg_added"] = injected_msg_added

            prev_mod_msgs = self.prev_messages_by_model.get(model_family)
            modified_payload = _strip_all_cache_control(modified_payload)
            modified_payload = _set_cache_breakpoints(modified_payload, prev_mod_msgs)

            self.prev_messages_by_model[model_family] = [
                _summarize_message(m) for m in modified_payload.get("messages", [])
            ]

            try:
                prev_delta = self.prev_delta_hashes_by_model.get(model_family)
                delta_entry, curr_delta = _build_forwarded_delta(
                    modified_payload,
                    flow.request.headers.get("x-request-id", ""),
                    prev_delta,
                )
                delta_entry["flow_id"] = flow.id
                raw_beta = flow.request.headers.get("anthropic-beta", "")
                delta_entry["anthropic_beta"] = [f.strip() for f in raw_beta.split(",") if f.strip()]
                _write_entry(self.forwarded_log_file, delta_entry)
                self.prev_delta_hashes_by_model[model_family] = curr_delta
            except Exception as e:
                print(f"[dual_log] forwarded write failed: {e}", file=sys.stderr)

            try:
                seen_ids = self.prev_error_ids_by_model.get(model_family, set())
                err_entries = _build_errors_entries(
                    payload,
                    mc_request_id,
                    mc_timestamp,
                    seen_ids,
                    self._worker_context,
                    self._session_id,
                    "",
                )
                for err_entry in err_entries:
                    err_entry["flow_id"] = flow.id
                    _write_entry(self.errors_log_file, err_entry)
                if err_entries:
                    new_seen = set(seen_ids)
                    new_seen.update(e["tool_use_id"] for e in err_entries)
                    self.prev_error_ids_by_model[model_family] = new_seen
            except Exception as e:
                print(f"[dual_log] errors write failed: {e}", file=sys.stderr)

            flow.metadata["mc_modified_payload"] = modified_payload
            flow.metadata["mc_model_family"] = model_family
            flow.request.content = json.dumps(modified_payload).encode("utf-8")
            flow.request.headers.pop("content-encoding", None)
        except Exception as e:
            print(f"[proxy_addon] Error: {e}", file=sys.stderr)

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        """Pass streaming responses through without buffering — preserves CC token streaming."""
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
                _write_entry(self.response_log_file, entry)
        except Exception as e:
            print(f"[dual_log] response write failed: {e}", file=sys.stderr)

    def response(self, flow: http.HTTPFlow) -> None:
        """Log 4xx errors; write stripped/injected dual-log entries on success."""
        try:
            if not _is_messages_request(flow):
                return
            if flow.response and 400 <= flow.response.status_code < 500:
                resp_body = ""
                try:
                    resp_body = flow.response.content.decode("utf-8", errors="replace")[:2000]
                except Exception:  # decode failure — log empty string, never crash
                    resp_body = ""
                req_payload = None
                try:
                    req_payload = json.loads(flow.request.content.decode("utf-8", errors="replace"))
                except Exception:  # body not valid JSON — log None, never crash
                    req_payload = None
                error_data = {
                    "ts": datetime.now(timezone.utc).isoformat() + "Z",
                    "status_code": flow.response.status_code,
                    "error_response": resp_body,
                    "request_url": flow.request.pretty_url,
                    "request_payload": req_payload,
                }
                errors_log = self.errors_log_file.parent.parent / "api_errors.jsonl"
                _write_entry(errors_log, error_data)
                print(f"[proxy_addon] API {flow.response.status_code} error — logged to api_errors.jsonl", file=sys.stderr)
                return
            if flow.response and flow.response.status_code < 400:
                try:
                    orig_payload = flow.metadata.get("mc_original_payload")
                    mod_payload = flow.metadata.get("mc_modified_payload")
                    mf = flow.metadata.get("mc_model_family")
                    request_id = flow.metadata.get("mc_request_id", "")
                    if orig_payload is not None and mod_payload is not None and mf is not None:
                        prev_s = self.prev_stripped_hashes_by_model.get(mf)
                        prev_i = self.prev_injected_hashes_by_model.get(mf)
                        model_str = mod_payload.get("model", "")
                        smr = flow.metadata.get("mc_stripped_msg_removed") or {}
                        ima = flow.metadata.get("mc_injected_msg_added") or {}
                        s_entry, i_entry, new_s, new_i = _build_stripped_injected_deltas(
                            orig_payload, mod_payload, request_id, prev_s, prev_i, model_str, smr, ima,
                        )
                        s_entry["flow_id"] = flow.id
                        i_entry["flow_id"] = flow.id
                        _write_entry(self.stripped_log_file, s_entry)
                        _write_entry(self.injected_log_file, i_entry)
                        self.prev_stripped_hashes_by_model[mf] = new_s
                        self.prev_injected_hashes_by_model[mf] = new_i
                except Exception as e:
                    print(f"[dual_log] stripped/injected write failed: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[proxy_addon] Error in response hook: {e}", file=sys.stderr)


# FUNCTIONS

_RESPONSE_HEADER_EXACT = frozenset({"request-id", "retry-after", "anthropic-organization-id"})
_RESPONSE_HEADER_PREFIXES = ("anthropic-ratelimit-", "anthropic-priority-", "anthropic-fast-")


# Filter Anthropic rate-limit + identity response headers; normalize keys to lowercase
def _filter_response_headers(headers) -> dict:
    result = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _RESPONSE_HEADER_EXACT or kl.startswith(_RESPONSE_HEADER_PREFIXES):
            result[kl] = v
    return result


# Check if flow is a POST to exactly /v1/messages (with optional query string) on api.anthropic.com — excludes /v1/messages/count_tokens and other sub-paths
def _is_messages_request(flow: http.HTTPFlow) -> bool:
    path = flow.request.path
    return (
        flow.request.method == "POST"
        and flow.request.pretty_host == ANTHROPIC_API_HOST
        and (path == MESSAGES_PATH or path.startswith(MESSAGES_PATH + "?"))
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


# Resolve dual-log file path in src/logs/dual_log/ subfolder with given suffix (e.g. "original", "forwarded")
def _resolve_dual_log_file(suffix: str) -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID")
    filename = f"api_requests_{log_id}_{suffix}.jsonl" if log_id else f"api_requests_{suffix}.jsonl"
    if root:
        return Path(root) / "src" / "logs" / "dual_log" / filename
    return Path("/tmp") / "dual_log" / filename


# Append log entry as a single JSONL line, creating parent dirs if needed
def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# Derive proxy session_id from PROXY_PROJECT_PATH env — md5(project_path)[:8], empty string if absent
def _derive_session_id() -> str:
    project_path = os.environ.get("PROXY_PROJECT_PATH", "")
    if project_path:
        return hashlib.md5(project_path.encode()).hexdigest()[:8]
    return ""


# Derive worker context string from PROXY_LOG_ID env — "worker:<name>" or "main"
# Worker log_ids follow the pattern worker_<hash>_<name>_<ts>; main log_ids do not start with worker_
def _derive_worker_context() -> str:
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID") or ""
    if log_id.startswith("worker_"):
        parts = log_id.split("_")
        if len(parts) >= 4:
            return "worker:" + "_".join(parts[2:-1])
    return "main"


addons = [ProxyAddon()]
