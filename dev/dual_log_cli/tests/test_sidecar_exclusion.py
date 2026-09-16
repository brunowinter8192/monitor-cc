# INFRASTRUCTURE

import json
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(_HERE.parents[2]))

from src.dual_log_cli.discovery import build_session
from src.dual_log_cli.reader import load_last_request
from src.dual_log_cli.timeline_boundaries import request_boundaries

PASS_LIST = []
FAIL_LIST = []

# FUNCTIONS

def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS_LIST.append(name)
    else:
        FAIL_LIST.append(name)
        print(f"  FAIL  {name}" + (f": {detail}" if detail else ""))

def _delta_entry(flow_id: str, timestamp: str, tools: int, messages: int, is_first: bool = False,
                  model: str = "claude-sonnet-5", system: int = 4) -> dict:
    return {
        "type": "forwarded_delta",
        "flow_id": flow_id,
        "timestamp": timestamp,
        "model": model,
        "is_first": is_first,
        "counts": {"system": system, "tools": tools, "messages": messages},
        "system_delta": {"0": {"type": "text", "text": "x"}, "1": {"type": "text", "text": "y"}} if is_first else {},
        "tools_delta": {"0": {"name": "Bash"}} if is_first and tools else {},
        "messages_delta": {},
    }

def _write_jsonl(entries: list) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for entry in entries:
            fh.write(json.dumps(entry) + "\n")
        return Path(fh.name)

def test_sidecar_seeds_no_boundary_and_does_not_pollute_prev_counts() -> None:
    entries = [
        _delta_entry("f0", "2026-09-03T10:00:00Z", tools=6, messages=2, is_first=True),
        _delta_entry("sidecar", "2026-09-03T10:00:02Z", tools=0, messages=1, system=3),
        _delta_entry("f1", "2026-09-03T10:00:04Z", tools=6, messages=5, system=4),
    ]
    path = _write_jsonl(entries)
    try:
        boundaries = request_boundaries(path, "sonnet")
    finally:
        path.unlink()
    check("sidecar produces no boundary of its own (2 boundaries, not 3)", len(boundaries) == 2, boundaries)
    flow_ids = [b["flow_id"] for b in boundaries]
    check("sidecar's flow_id never appears in the boundary list", "sidecar" not in flow_ids, flow_ids)
    check("no restart — the sidecar's message_count=1 never gets compared against anything",
          all(not b["restart"] for b in boundaries), boundaries)
    second = boundaries[1]
    check("second boundary's start_index continues from the FIRST real request (2), not the sidecar (1)",
          second["start_index"] == 2, second)
    check("second boundary is REQ 2 (message-adding count), the sidecar never having advanced it",
          second["message_count"] == 5, second)

def test_build_session_excludes_sidecar_from_request_count() -> None:
    entries = [
        _delta_entry("h0", "2026-09-03T09:59:00Z", tools=0, messages=1, model="claude-haiku-4-5-20251001", system=0),
        _delta_entry("f0", "2026-09-03T10:00:00Z", tools=6, messages=2, is_first=True),
        _delta_entry("sidecar", "2026-09-03T10:00:02Z", tools=0, messages=1, system=3),
        _delta_entry("f1", "2026-09-03T10:00:04Z", tools=6, messages=5, system=4),
    ]
    path = _write_jsonl(entries)
    try:
        session = build_session("test-stem", {"forwarded": path})
    finally:
        path.unlink()
    check("requests excludes the sidecar (2 real + 1 haiku = 3, not 4)", session["requests"] == 3, session)
    check("requests_main excludes the sidecar (2, not 3)", session["requests_main"] == 2, session)
    check("messages reflects the last REAL request, not the sidecar's 1", session["messages"] == 5, session)
    check("end timestamp still reflects the sidecar's own wall-clock time",
          session["end"] == "2026-09-03T10:00:04Z", session)

def _original_line(flow_id: str, model: str, tools: list, messages: list) -> dict:
    return {
        "timestamp": "2026-09-03T10:00:00.000+00:00Z",
        "flow_id": flow_id,
        "request_id": "",
        "model": model,
        "payload": {"model": model, "tools": tools, "system": [], "messages": messages},
    }

def test_load_last_request_skips_trailing_sidecar() -> None:
    lines = [
        _original_line("f0", "claude-sonnet-5", tools=[{"name": "Bash"}], messages=[{"role": "user", "content": "hi"}]),
        _original_line("sidecar", "claude-sonnet-5", tools=[], messages=[{"role": "user", "content": "review this"}]),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
        path = Path(fh.name)
    try:
        entry, _line_bytes, skipped = load_last_request(path)
    finally:
        path.unlink()
    check("returns the real conversation line, not the trailing sidecar", entry is not None and entry.get("flow_id") == "f0", entry)
    check("the sidecar line is counted as skipped", skipped == 1, skipped)

def test_load_last_request_unaffected_when_last_line_has_tools() -> None:
    lines = [
        _original_line("sidecar", "claude-sonnet-5", tools=[], messages=[{"role": "user", "content": "review"}]),
        _original_line("f1", "claude-sonnet-5", tools=[{"name": "Bash"}], messages=[{"role": "user", "content": "hi"}]),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
        path = Path(fh.name)
    try:
        entry, _line_bytes, skipped = load_last_request(path)
    finally:
        path.unlink()
    check("returns the last line when it already carries tools", entry is not None and entry.get("flow_id") == "f1", entry)
    check("nothing skipped", skipped == 0, skipped)

# ORCHESTRATOR

def test_sidecar_exclusion_workflow() -> None:
    test_sidecar_seeds_no_boundary_and_does_not_pollute_prev_counts()
    test_build_session_excludes_sidecar_from_request_count()
    test_load_last_request_skips_trailing_sidecar()
    test_load_last_request_unaffected_when_last_line_has_tools()

    total = len(PASS_LIST) + len(FAIL_LIST)
    print(f"{len(PASS_LIST)}/{total} checks passed")
    if FAIL_LIST:
        print(f"\nFAILED: {FAIL_LIST}")
        sys.exit(1)
    print("ALL PASS")

if __name__ == "__main__":
    test_sidecar_exclusion_workflow()
