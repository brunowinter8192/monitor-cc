# INFRASTRUCTURE
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_RETENTION = 7 * 86400


# FUNCTIONS

@dataclass(frozen=True)
class LogSpec:
    name: str
    path_pattern: str
    writer: str
    purpose: str
    fmt: str
    retention: str
    janitor_trigger: str
    sweep_eligible: bool


_LOG_REGISTRY: tuple = (
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
        name="api_requests_dual_original",
        path_pattern="dual_log/api_requests_*_original.jsonl",
        writer="proxy/addon.py:_resolve_dual_log_file",
        purpose="Dual-log: unmodified original CC request payload (pre-modification)",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_dual_forwarded",
        path_pattern="dual_log/api_requests_*_forwarded.jsonl",
        writer="proxy/addon.py:_resolve_dual_log_file",
        purpose="Dual-log: delta-log of forwarded (post-modification) request payload",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_dual_stripped",
        path_pattern="dual_log/api_requests_*_stripped.jsonl",
        writer="proxy/addon.py:_resolve_dual_log_file",
        purpose="Dual-log: delta-log of what proxy stripped (in original, not in forwarded)",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_dual_injected",
        path_pattern="dual_log/api_requests_*_injected.jsonl",
        writer="proxy/addon.py:_resolve_dual_log_file",
        purpose="Dual-log: delta-log of what proxy injected (in forwarded, not in original)",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_dual_errors",
        path_pattern="dual_log/api_requests_*_errors.jsonl",
        writer="proxy/addon.py:_build_errors_entries",
        purpose="Dual-log: derived tool-error log; is_error tool_result blocks from original payload, dedup by tool_use_id, format field-matched to tool_errors.jsonl",
        fmt="jsonl",
        retention="count-30",
        janitor_trigger="proxy-start-bash",
        sweep_eligible=False,
    ),
    LogSpec(
        name="api_requests_dual_response",
        path_pattern="dual_log/api_requests_*_response.jsonl",
        writer="proxy/addon.py:_resolve_dual_log_file",
        purpose="Dual-log: response HTTP headers (rate-limit family + request-id), joined by flow_id",
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
        name="monitor_sweep",
        path_pattern="monitor_sweep.log",
        writer="monitor_janitor.py:log_sweep_line",
        purpose="Daily tmux-session sweep decisions (session, age, KILLED/SPARED) for monitor_cc_* sessions",
        fmt="log",
        retention="unbounded-plain-text-low-volume",
        janitor_trigger="monitor-janitor-self",
        sweep_eligible=False,
    ),
)


def sweep_eligible_specs(logs_dir: Path) -> list:
    return [
        (spec, logs_dir / spec.path_pattern)
        for spec in _LOG_REGISTRY
        if spec.sweep_eligible
    ]


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
                    if ts_dt < cutoff:
                        continue
            except Exception:
                pass
            kept.append(line)
        path.write_text(''.join(kept), encoding='utf-8')
    except Exception:
        pass
