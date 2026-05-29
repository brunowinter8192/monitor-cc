# INFRASTRUCTURE
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_RETENTION = 7 * 86400


# FUNCTIONS

@dataclass(frozen=True)
class LogSpec:
    name: str            # identifier
    path_pattern: str    # relative to src/logs/ (gpu_pane + ccwrap use explicit subdir paths)
    writer: str          # "module.py:symbol"
    purpose: str         # one-liner
    fmt: str             # "jsonl" | "log" | "bin+ansi"
    retention: str       # "7d-ts-records" | "count-30" | "7d-timed-rotation" | "count-10-pairs"
    janitor_trigger: str # "monitor-24h" | "proxy-start-bash" | "live-handler" | "ccwrap-caller"
    sweep_eligible: bool # True = cleanup_old_jsonl applies via monitor-24h tick


# Authoritative log inventory — single source for all Monitor_CC log policies
_LOG_REGISTRY: tuple = (
    LogSpec(
        name="tool_errors",
        path_pattern="tool_errors.jsonl",
        writer="panes/warnings_persist.py:append_tool_errors",
        purpose="Tool-use errors from CC hooks, displayed in warnings pane",
        fmt="jsonl",
        retention="7d-ts-records",
        janitor_trigger="monitor-24h",
        sweep_eligible=True,
    ),
    LogSpec(
        name="hook_firing",
        path_pattern="hook_firing.jsonl",
        writer="hooks/*:log_fire",
        purpose="Hook execution events (pre/post tool-use hook firings)",
        fmt="jsonl",
        retention="7d-ts-records",
        janitor_trigger="monitor-24h",
        sweep_eligible=True,
    ),
    LogSpec(
        name="api_errors",
        path_pattern="api_errors.jsonl",
        writer="proxy/addon.py:ProxyAddon.response",
        purpose="4xx API error payloads from mitmproxy (rollend)",
        fmt="jsonl",
        retention="7d-ts-records",
        janitor_trigger="monitor-24h",
        sweep_eligible=True,
    ),
    LogSpec(
        name="api_requests_opus",
        path_pattern="api_requests_opus_*.jsonl",
        writer="proxy/addon.py:_write_entry",
        purpose="Full proxy log: modified request + response metadata for Opus sessions",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_worker",
        path_pattern="api_requests_worker_*.jsonl",
        writer="proxy/addon.py:_write_entry",
        purpose="Full proxy log: modified request + response metadata for Worker sessions",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="gpu_pane",
        path_pattern="../gpu_pane/logs/gpu_pane.log",
        writer="gpu_pane/status.py:TimedRotatingFileHandler",
        purpose="GPU monitoring status messages",
        fmt="log",
        retention="7d-timed-rotation",
        janitor_trigger="live-handler",
        sweep_eligible=False,
    ),
    LogSpec(
        name="ccwrap_session",
        path_pattern="../ccwrap/logs/*.bin + *.ansi.log",
        writer="ccwrap/ansi_log.py:open_log_pair",
        purpose="Raw ANSI terminal capture of CC sessions",
        fmt="bin+ansi",
        retention="count-10-pairs",
        janitor_trigger="ccwrap-caller",
        sweep_eligible=False,
    ),
    LogSpec(
        name="polling_state",
        path_pattern="polling_state.jsonl",
        writer="hooks/block_polling_loop.py:_record_and_count",
        purpose="Polling-frequency state for block_polling_loop hook (session×target counters, self-pruned at 30 s window)",
        fmt="jsonl",
        retention="1d-ts-records",
        janitor_trigger="monitor-24h",
        sweep_eligible=True,
    ),
)


# Return (spec, resolved_path) pairs for logs the monitor-24h sweep handles via cleanup_old_jsonl
def sweep_eligible_specs(logs_dir: Path) -> list:
    return [
        (spec, logs_dir / spec.path_pattern)
        for spec in _LOG_REGISTRY
        if spec.sweep_eligible
    ]


# Drop records older than 7 days from a JSONL file by 'ts' field; exception-safe; rewrites atomically
def cleanup_old_jsonl(path: Path) -> None:
    try:
        if not path.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=_RETENTION)
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        kept = []
        for line in lines:
            if not line.strip():
                continue
            try:
                ts_raw = json.loads(line).get('ts', '')
                if ts_raw:
                    ts_dt = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                    if ts_dt < cutoff:   # TypeError if naive ts → caught below → keep
                        continue
            except Exception:  # unparseable ts or naive/aware mismatch → keep (fail-safe)
                pass
            kept.append(line)
        path.write_text(''.join(kept), encoding='utf-8')
    except Exception:  # janitor must never raise into the monitor event loop
        pass
