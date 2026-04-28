# INFRASTRUCTURE
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from mitmproxy import http

from .logging import _build_entry, _build_latency_update, _summarize_content_for_log
from .message_summary import _summarize_message
from .rules import apply_modification_rules, _strip_blocked_tool_references
from .inject_helpers import _inject_context_management, _inject_model_override, _apply_post_sleep_cap
from .content_strip import _strip_tool_descriptions, _strip_sys3
from .cache import _strip_all_cache_control, _set_cache_breakpoints
from .tools import _strip_unused_tools
from .tool_injection import inject_mcp_tools
from .fixation import _capture_fixation, _apply_fixation
from .hash_meta import _build_sent_meta
from .schema_check import _check_payload_schema

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
        self._schema_checked: Dict[str, bool] = {}  # schema check runs once per model_family (opus + sonnet)

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

            if model_family in ("opus", "sonnet") and not self._schema_checked.get(model_family, False):
                self._schema_checked[model_family] = True
                schema_warnings = _check_payload_schema(payload)
                if schema_warnings:
                    _write_entry(self.log_file, {
                        "type": "schema_warning",
                        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                        "model": payload.get("model", ""),
                        "model_family": model_family,
                        "warnings": schema_warnings,
                    })
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

            modified_payload = _apply_post_sleep_cap(modified_payload, modifications)

            entry = _build_entry(flow, modified_payload, self.prev_messages_by_model.get(model_family), modifications)
            if original_system2 is not None:
                entry['original_system2_text'] = original_system2
            if sys3_original is not None:
                entry['stripped_sys3_original'] = sys3_original
            if tool_descs_originals:
                entry['stripped_tool_descs_originals'] = tool_descs_originals
            entry['stripped_msg_indices'] = stripped_msg_indices
            entry['context_management_injected'] = cm_injected
            if stripped_msg_originals:
                entry['stripped_msg_originals'] = {}
                for k, v in stripped_msg_originals.items():
                    entry['stripped_msg_originals'][str(k)] = _summarize_content_for_log(v)
            if stripped_msg_removed:
                entry['stripped_msg_removed'] = {str(k): v for k, v in stripped_msg_removed.items()}
            _write_entry(self.log_file, entry)
            # Store timing/id for latency hooks (responseheaders + response)
            flow.metadata["mc_request_at"] = datetime.now(timezone.utc)
            flow.metadata["mc_request_id"] = entry.get("request_id", "")

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
            # Strip deprecated interleaved-thinking beta header and inject context-management beta header
            existing_beta = flow.request.headers.get("anthropic-beta", "")
            deprecated_header = "interleaved-thinking-2025-05-14"
            if deprecated_header in existing_beta:
                parts = [p.strip() for p in existing_beta.split(",") if p.strip() != deprecated_header]
                existing_beta = ",".join(parts)
            beta_value = "context-management-2025-06-27"
            if existing_beta:
                if beta_value not in existing_beta:
                    flow.request.headers["anthropic-beta"] = existing_beta + "," + beta_value
                else:
                    flow.request.headers["anthropic-beta"] = existing_beta
            else:
                flow.request.headers["anthropic-beta"] = beta_value
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

    def responseheaders(self, flow: http.HTTPFlow) -> None:
        """Capture response-headers timestamp for TTFB measurement; attach chunk-timer for stall detection."""
        try:
            if not _is_messages_request(flow):
                return
            rh_at = datetime.now(timezone.utc)
            flow.metadata["mc_responseheaders_at"] = rh_at
            # For 2xx streaming responses: collect per-chunk relative timestamps and buffer body
            # (streaming mode means flow.response.content is empty in response hook)
            if flow.response and 200 <= flow.response.status_code < 300:
                chunk_timestamps_ms = []
                body_parts = []

                def stream_chunks(chunks):
                    for chunk in chunks:
                        elapsed = (datetime.now(timezone.utc) - rh_at).total_seconds() * 1000
                        chunk_timestamps_ms.append(elapsed)
                        body_parts.append(chunk)
                        yield chunk

                flow.metadata["mc_chunk_timestamps_ms"] = chunk_timestamps_ms
                flow.metadata["mc_body_parts"] = body_parts
                flow.response.stream = stream_chunks
        except Exception as e:
            print(f"[proxy_addon] Error in responseheaders hook: {e}", file=sys.stderr)

    def response(self, flow: http.HTTPFlow) -> None:
        """Log latency metrics on success; log full payload on 4xx error."""
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
                return
            # Success path — compute and log latency metrics
            if flow.response and flow.response.status_code < 400:
                request_id = flow.metadata.get("mc_request_id", "")
                if not request_id:
                    return
                request_at = flow.metadata.get("mc_request_at")
                responseheaders_at = flow.metadata.get("mc_responseheaders_at")
                response_complete_at = datetime.now(timezone.utc)
                ttfb_ms = None
                stream_duration_ms = None
                if request_at and responseheaders_at:
                    ttfb_ms = (responseheaders_at - request_at).total_seconds() * 1000
                    stream_duration_ms = (response_complete_at - responseheaders_at).total_seconds() * 1000
                # Use body buffer from streaming handler (flow.response.content is empty when streaming)
                body_parts = flow.metadata.get("mc_body_parts")
                response_content = b''.join(body_parts) if body_parts is not None else flow.response.content
                output_tokens = _extract_output_tokens(response_content)
                output_tokens_per_sec = None
                if stream_duration_ms and stream_duration_ms > 0 and output_tokens is not None:
                    output_tokens_per_sec = output_tokens / (stream_duration_ms / 1000)
                chunk_ts = flow.metadata.get("mc_chunk_timestamps_ms", [])
                n_stalls, max_stall_ms, total_stall_ms = _compute_stall_stats(chunk_ts)
                _write_entry(self.log_file, _build_latency_update(
                    request_id, ttfb_ms, stream_duration_ms, output_tokens, output_tokens_per_sec,
                    n_stalls, max_stall_ms, total_stall_ms,
                ))
        except Exception as e:
            print(f"[proxy_addon] Error in response hook: {e}", file=sys.stderr)


# FUNCTIONS

# Compute stall statistics from per-chunk relative timestamps (ms) — stall threshold 30000ms — returns (n_stalls, max_stall_ms, total_stall_ms)
def _compute_stall_stats(timestamps_ms: list) -> tuple:
    if len(timestamps_ms) < 2:
        return 0, None, None
    stall_gaps = [
        timestamps_ms[i] - timestamps_ms[i - 1]
        for i in range(1, len(timestamps_ms))
        if timestamps_ms[i] - timestamps_ms[i - 1] >= 30000.0
    ]
    if not stall_gaps:
        return 0, None, None
    return len(stall_gaps), max(stall_gaps), sum(stall_gaps)


# Parse SSE stream (or plain JSON) response body to extract output_tokens count
def _extract_output_tokens(content: bytes) -> Optional[int]:
    if not content:
        return None
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return None
    # Non-streaming: plain JSON response
    stripped = text.lstrip()
    if stripped.startswith('{'):
        try:
            data = json.loads(stripped)
            tokens = data.get('usage', {}).get('output_tokens')
            return int(tokens) if tokens is not None else None
        except Exception:
            pass
    # Streaming SSE: scan lines in reverse for message_delta event
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith('data:'):
            continue
        data_str = line[5:].strip()
        if not data_str or data_str == '[DONE]':
            continue
        try:
            data = json.loads(data_str)
            if data.get('type') == 'message_delta':
                tokens = data.get('usage', {}).get('output_tokens')
                return int(tokens) if tokens is not None else None
        except (json.JSONDecodeError, ValueError):
            continue
    return None


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


# Append log entry as a single JSONL line, creating parent dirs if needed
def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


addons = [ProxyAddon()]
