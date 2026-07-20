#!/usr/bin/env python3
"""Replay verification for the RS-pass truncation-notice preserve-guard.

Runs every request's messages from a dual-log JSONL through
_apply_role_system_strip and asserts:
  - role=system messages starting with "[Truncated:" pass through UNCHANGED
  - other role=system messages (deferred-tools, date-changed, ...) are
    still reduced to "."

Input:  JSONL dual-log path (positional arg, optional — defaults to the
        main checkout's api_requests_opus_trading_1784579551_original.jsonl)
Output: console PASS/FAIL summary + detail file under dev/tool_use_analysis/md/
"""

# INFRASTRUCTURE

import json
import os
import sys
from pathlib import Path

_src_dir = os.path.join(
    os.environ.get('MONITOR_CC_ROOT', str(Path(__file__).parent.parent.parent)),
    'src',
)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from proxy.message_passes import _apply_role_system_strip, _TRUNCATION_NOTICE_MARKER

_WORKTREE_LOG = os.path.join(
    Path(__file__).parent.parent.parent, 'src', 'logs', 'dual_log',
    'api_requests_opus_trading_1784579551_original.jsonl',
)
_MAIN_CHECKOUT_LOG = (
    '/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log/'
    'api_requests_opus_trading_1784579551_original.jsonl'
)
_DETAIL_PATH = os.path.join(
    Path(__file__).parent, 'md', 'rs_truncation_preserve_replay_detail.md',
)

# ORCHESTRATOR

def replay_workflow(log_path: str) -> None:
    lines = _load_lines(log_path)
    truncation_preserved, noise_stripped, failures = _replay_lines(lines)
    _write_detail(failures, truncation_preserved, noise_stripped)
    _print_summary(truncation_preserved, noise_stripped, failures)

# FUNCTIONS

# Read JSONL lines from the given path.
def _load_lines(log_path: str) -> list:
    with open(log_path) as f:
        return [line for line in f if line.strip()]

# Run each request's messages through the RS pass and classify results.
def _replay_lines(lines: list) -> tuple:
    truncation_preserved = 0
    noise_stripped = 0
    failures = []
    for line_no, line in enumerate(lines, start=1):
        entry = json.loads(line)
        messages = entry.get("payload", {}).get("messages", [])
        original_by_idx = {
            idx: msg for idx, msg in enumerate(messages) if msg.get("role") == "system"
        }
        new_messages, *_ = _apply_role_system_strip(messages)
        for idx, old_msg in original_by_idx.items():
            old_content = old_msg.get("content", "")
            new_content = new_messages[idx].get("content", "")
            is_truncation = isinstance(old_content, str) and old_content.startswith(_TRUNCATION_NOTICE_MARKER)
            if is_truncation:
                if new_content == old_content:
                    truncation_preserved += 1
                else:
                    failures.append((line_no, idx, "truncation-not-preserved", old_content[:80]))
            elif old_content and old_content != ".":
                if new_content == ".":
                    noise_stripped += 1
                else:
                    failures.append((line_no, idx, "noise-not-stripped", str(old_content)[:80]))
    return truncation_preserved, noise_stripped, failures

# Write verbose per-failure detail to a markdown file (empty body when no failures).
def _write_detail(failures: list, truncation_preserved: int, noise_stripped: int) -> None:
    os.makedirs(os.path.dirname(_DETAIL_PATH), exist_ok=True)
    lines = [
        "# RS truncation-preserve replay — detail\n\n",
        f"truncation_preserved={truncation_preserved} noise_stripped={noise_stripped} failures={len(failures)}\n\n",
    ]
    if failures:
        lines.append("| line | msg_idx | kind | content_prefix |\n|---|---|---|---|\n")
        for line_no, idx, kind, prefix in failures:
            lines.append(f"| {line_no} | {idx} | {kind} | `{prefix}` |\n")
    else:
        lines.append("No failures.\n")
    with open(_DETAIL_PATH, "w") as f:
        f.writelines(lines)

# Print a tiny PASS/FAIL summary to console.
def _print_summary(truncation_preserved: int, noise_stripped: int, failures: list) -> None:
    status = "PASS" if not failures else "FAIL"
    print(f"{status}: truncation_preserved={truncation_preserved} noise_stripped={noise_stripped} failures={len(failures)}")
    print(f"Detail: {_DETAIL_PATH}")


if __name__ == "__main__":
    _log_path = sys.argv[1] if len(sys.argv) > 1 else None
    if _log_path is None:
        _log_path = _WORKTREE_LOG if os.path.exists(_WORKTREE_LOG) else _MAIN_CHECKOUT_LOG
    replay_workflow(_log_path)
