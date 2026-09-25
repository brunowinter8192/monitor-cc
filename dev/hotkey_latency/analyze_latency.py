# INFRASTRUCTURE
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

MENUBAR_LOG = Path('~/Library/Application Support/com.brunowinter.monitor-cc-menubar/menubar.log').expanduser()
REPORT_DIR       = Path(__file__).parent / 'md'
N_SLOWEST        = 10
_LATENCY_RE      = re.compile(r'^(\S+) \[latency\] (.*)$')
_TICK_LIKE_RE    = re.compile(r'^(tick|bg_refresh) total=(\d+)ms (.*)$')
_PHASE_RE        = re.compile(r'(\w+)=(\d+)ms')
_HOTKEY_RE       = re.compile(r'^hotkey=(\S+) queue_delay_ms=([\d.]+)$')
_FOCUS_RE        = re.compile(r'^focus lookup_ms=([\d.]+) osascript_ms=([\d.]+) (.*)$')


# ORCHESTRATOR

def main() -> None:
    log_path = compute_log_path()
    ticks, bg_refreshes, hotkeys, focuses = _parse_latency_lines(log_path)
    report = _build_report(log_path, ticks, bg_refreshes, hotkeys, focuses)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_path = compute_out_path(stamp)
    out_path.write_text(report, encoding='utf-8')
    print_ticks(ticks, bg_refreshes, hotkeys, focuses)
    print_report_written_to(out_path)


# FUNCTIONS

def compute_log_path():
    return Path(sys.argv[1]) if len(sys.argv) > 1 else MENUBAR_LOG


def _parse_latency_lines(log_path: Path) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    ticks, bg_refreshes, hotkeys, focuses = [], [], [], []
    if not log_path.exists():
        return ticks, bg_refreshes, hotkeys, focuses
    with open(log_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = _LATENCY_RE.match(line.rstrip('\n'))
            if not m:
                continue
            ts, body = m.group(1), m.group(2)
            tm = _TICK_LIKE_RE.match(body)
            if tm:
                kind, total_ms_str, phase_str = tm.group(1), tm.group(2), tm.group(3)
                entry = {'ts': ts, 'total_ms': int(total_ms_str),
                          'phases': {name: int(ms) for name, ms in _PHASE_RE.findall(phase_str)}}
                (ticks if kind == 'tick' else bg_refreshes).append(entry)
                continue
            hm = _HOTKEY_RE.match(body)
            if hm:
                hotkeys.append({'ts': ts, 'name': hm.group(1), 'delay_ms': float(hm.group(2))})
                continue
            fm = _FOCUS_RE.match(body)
            if fm:
                focuses.append({'ts': ts, 'lookup_ms': float(fm.group(1)),
                                 'osascript_ms': float(fm.group(2)), 'label': fm.group(3)})
    return ticks, bg_refreshes, hotkeys, focuses


def _build_report(log_path: Path, ticks: List[dict], bg_refreshes: List[dict],
                   hotkeys: List[dict], focuses: List[dict]) -> str:
    header = (
        f'# Hotkey/Menubar Latency Report\n\n'
        f'Source: `{log_path}`\n'
        f'Generated: {datetime.now(timezone.utc).isoformat(timespec="seconds")}\n\n'
    )
    tick_section = _tick_like_section(
        ticks, 'Main-Thread Tick Latency (over-threshold ticks only)',
        'no main-thread tick exceeded TICK_LATENCY_THRESHOLD_MS in this log window.')
    bg_section = _tick_like_section(
        bg_refreshes, 'Background Discovery-Worker Cycle Latency (over-threshold cycles only)',
        'no discovery-worker cycle exceeded BG_REFRESH_LATENCY_THRESHOLD_MS in this log window.')
    return (header + tick_section + '\n' + bg_section + '\n'
            + _hotkey_section(hotkeys) + '\n' + _focus_section(focuses))


def _tick_like_section(entries: List[dict], title: str, empty_note: str) -> str:
    if not entries:
        return f'## {title}\n\nNo [latency] lines found — {empty_note}\n'
    totals = [e['total_ms'] for e in entries]
    phase_names = sorted({name for e in entries for name in e['phases']})
    phase_lines = []
    for name in phase_names:
        vals = [e['phases'][name] for e in entries if name in e['phases']]
        phase_lines.append(f'- `{name}`: {_dist_line(vals)}')
    slowest = sorted(entries, key=lambda e: -e['total_ms'])[:N_SLOWEST]
    slowest_lines = []
    for e in slowest:
        breakdown = ' '.join(f'{k}={v}ms' for k, v in sorted(e['phases'].items(), key=lambda kv: -kv[1]))
        slowest_lines.append(f'- {e["ts"]} total={e["total_ms"]}ms — {breakdown}')
    return (
        f'## {title}\n\n'
        f'Total-duration distribution: {_dist_line(totals)}\n\n'
        '### Per-Phase Distribution (ms)\n\n'
        + '\n'.join(phase_lines) + '\n\n'
        f'### Slowest {min(N_SLOWEST, len(entries))} Entries\n\n'
        + '\n'.join(slowest_lines) + '\n'
    )


def _dist_line(values: List[float]) -> str:
    if not values:
        return 'n=0'
    return (f'n={len(values)} mean={statistics.mean(values):.1f} '
            f'median={statistics.median(values):.1f} p90={_pct(values, 90):.1f} '
            f'p95={_pct(values, 95):.1f} max={max(values):.1f}')


def _pct(values: List[float], p: float) -> float:
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(p / 100 * (len(s) - 1)))))
    return s[idx]


def _hotkey_section(hotkeys: List[dict]) -> str:
    if not hotkeys:
        return '## Hotkey Queue-Delay\n\nNo [latency] hotkey lines found.\n'
    overall = [h['delay_ms'] for h in hotkeys]
    by_name: Dict[str, List[float]] = {}
    for h in hotkeys:
        by_name.setdefault(h['name'], []).append(h['delay_ms'])
    lines = [f'- `{name}`: {_dist_line(vals)}' for name, vals in sorted(by_name.items())]
    return (
        '## Hotkey Queue-Delay (queue_delay_ms = handler-entry time - Carbon event timestamp)\n\n'
        f'Overall: {_dist_line(overall)}\n\n'
        '### Per Hotkey\n\n' + '\n'.join(lines) + '\n'
    )


def _focus_section(focuses: List[dict]) -> str:
    if not focuses:
        return '## Focus-Path Timing\n\nNo [latency] focus lines found.\n'
    lookup = [f['lookup_ms'] for f in focuses]
    osa    = [f['osascript_ms'] for f in focuses]
    return (
        '## Focus-Path Timing (_focus_session)\n\n'
        f'- `lookup_ms` (get_ghostty_terminal_id): {_dist_line(lookup)}\n'
        f'- `osascript_ms` (osascript run): {_dist_line(osa)}\n'
    )


def compute_out_path(stamp):
    return REPORT_DIR / f'latency_report_{stamp}.md'


def print_ticks(ticks, bg_refreshes, hotkeys, focuses):
    print(f'ticks={len(ticks)} bg_refreshes={len(bg_refreshes)} hotkeys={len(hotkeys)} focuses={len(focuses)}')


def print_report_written_to(out_path):
    print(f'report written to {out_path}')


if __name__ == '__main__':
    main()
