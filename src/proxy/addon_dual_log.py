# INFRASTRUCTURE
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .logging import _build_forwarded_delta, _build_errors_entries
from .strip_inject_delta import _build_stripped_injected_deltas

# FUNCTIONS


def _resolve_dual_log_file(suffix: str) -> Path:
    root = os.environ.get("MONITOR_CC_ROOT")
    log_id = os.environ.get("PROXY_LOG_ID") or os.environ.get("PROXY_SESSION_ID")
    filename = f"api_requests_{log_id}_{suffix}.jsonl" if log_id else f"api_requests_{suffix}.jsonl"
    if root:
        return Path(root) / "src" / "logs" / "dual_log" / filename
    return Path("/tmp") / "dual_log" / filename


def _write_entry(log_file: Path, entry: dict) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _log_original_request(log_file: Path, flow, payload: dict) -> None:
    try:
        _write_entry(log_file, {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "flow_id": flow.id,
            "request_id": flow.request.headers.get("x-request-id", ""),
            "model": payload.get("model", ""),
            "payload": payload,
        })
    except Exception as e:
        print(f"[dual_log] original write failed: {e}", file=sys.stderr)


def _log_forwarded_delta(log_file: Path, modified_payload: dict, flow, prev_delta) -> Optional[dict]:
    try:
        delta_entry, curr_delta = _build_forwarded_delta(
            modified_payload,
            flow.request.headers.get("x-request-id", ""),
            prev_delta,
        )
        delta_entry["flow_id"] = flow.id
        raw_beta = flow.request.headers.get("anthropic-beta", "")
        delta_entry["anthropic_beta"] = [f.strip() for f in raw_beta.split(",") if f.strip()]
        _write_entry(log_file, delta_entry)
        return curr_delta
    except Exception as e:
        print(f"[dual_log] forwarded write failed: {e}", file=sys.stderr)
        return None


def _log_errors_entries(log_file: Path, payload: dict, mc_request_id: str, mc_timestamp: str,
                        prev_seen_ids: set, worker_context: str, session_id: str, flow_id: str) -> Optional[set]:
    try:
        err_entries = _build_errors_entries(
            payload, mc_request_id, mc_timestamp, prev_seen_ids, worker_context, session_id, "",
        )
        for err_entry in err_entries:
            err_entry["flow_id"] = flow_id
            _write_entry(log_file, err_entry)
        if err_entries:
            new_seen = set(prev_seen_ids)
            new_seen.update(e["tool_use_id"] for e in err_entries)
            return new_seen
        return None
    except Exception as e:
        print(f"[dual_log] errors write failed: {e}", file=sys.stderr)
        return None


def _write_request_dual_logs(flow, payload: dict, modified_payload: dict, model_family: str,
                              mc_request_id: str, mc_timestamp: str, paths, delta_state, identity) -> None:
    curr_delta = _log_forwarded_delta(
        paths.forwarded, modified_payload, flow,
        delta_state.forwarded_hashes_by_model.get(model_family),
    )
    if curr_delta is not None:
        delta_state.forwarded_hashes_by_model[model_family] = curr_delta

    new_seen = _log_errors_entries(
        paths.errors, payload, mc_request_id, mc_timestamp,
        delta_state.error_ids_by_model.get(model_family, set()),
        identity.worker_context, identity.session_id, flow.id,
    )
    if new_seen is not None:
        delta_state.error_ids_by_model[model_family] = new_seen


def _log_4xx_error(flow, errors_log_file: Path) -> None:
    resp_body = ""
    try:
        resp_body = flow.response.content.decode("utf-8", errors="replace")[:2000]
    except Exception:
        resp_body = ""
    req_payload = None
    try:
        req_payload = json.loads(flow.request.content.decode("utf-8", errors="replace"))
    except Exception:
        req_payload = None
    error_data = {
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
        "status_code": flow.response.status_code,
        "error_response": resp_body,
        "request_url": flow.request.pretty_url,
        "request_payload": req_payload,
    }
    errors_log = errors_log_file.parent.parent / "api_errors.jsonl"
    _write_entry(errors_log, error_data)
    print(f"[proxy_addon] API {flow.response.status_code} error — logged to api_errors.jsonl", file=sys.stderr)


def _write_stripped_injected(flow, delta_state, paths) -> None:
    orig_payload = flow.metadata.get("mc_original_payload")
    mod_payload = flow.metadata.get("mc_modified_payload")
    mf = flow.metadata.get("mc_model_family")
    request_id = flow.metadata.get("mc_request_id", "")
    if orig_payload is None or mod_payload is None or mf is None:
        return
    prev_s = delta_state.stripped_hashes_by_model.get(mf)
    prev_i = delta_state.injected_hashes_by_model.get(mf)
    model_str = mod_payload.get("model", "")
    all_ops = flow.metadata.get("mc_all_ops") or {}
    s_entry, i_entry, new_s, new_i = _build_stripped_injected_deltas(
        orig_payload, mod_payload, request_id, prev_s, prev_i, model_str, all_ops,
    )
    s_entry["flow_id"] = flow.id
    i_entry["flow_id"] = flow.id
    _write_entry(paths.stripped, s_entry)
    _write_entry(paths.injected, i_entry)
    delta_state.stripped_hashes_by_model[mf] = new_s
    delta_state.injected_hashes_by_model[mf] = new_i
