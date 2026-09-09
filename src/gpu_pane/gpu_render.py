# INFRASTRUCTURE
import os
import re

from ..colors import RESET, GREEN, YELLOW, RED, DIM, ORANGE, SEARCH_MATCH_BG, SEARCH_CURRENT_BG
from ..utils import format_timestamp, compute_header_rule_len, highlight_query_in_line
from .gpu_actions import _toggle_state

IDLE_TIMEOUT = int(os.getenv("RAG_SERVER_IDLE_TIMEOUT", "3600"))
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[mKHJABCDEFGsuTXP]')

_button_regions: dict = {} # (start_col, end_col, phys_row) → (action, target_str); phys_row shifted by _GPU_SEARCH_BAR_LINES since 2026-08-18

# FUNCTIONS

# Remove ANSI escape codes to calculate visual display width
def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub('', s)


# Return colored status badge
def _badge(s: dict) -> str:
    if not s['running']:
        return f"{RED}○{RESET}"
    return f"{GREEN}●{RESET}" if s['healthy'] else f"{YELLOW}◐{RESET}"


# Return status label; shows [starting…]/[stopping…] while toggle in flight
def _status_text(s: dict) -> str:
    key = s['name'] if s['kind'] == 'preset' else f'port-{s["port"]}'
    if key in _toggle_state:
        action, _ = _toggle_state[key]
        return f"[{action}…]"
    return "running" if s['running'] else "stopped"


# Return countdown string from status dict; "" if stopped, "?" if state file missing
def _format_countdown(s: dict) -> str:
    if not s['running']:
        return ""
    if s.get('idle_state_missing'):
        return "?"
    idle_seconds = s.get('idle_seconds')
    if idle_seconds is None:
        return ""
    remaining = int(IDLE_TIMEOUT - idle_seconds)
    if remaining <= 0:
        return "stopping…"
    if remaining >= 3600:
        h = remaining // 3600
        m = (remaining % 3600) // 60
        sec = remaining % 60
        return f"stops in {h}:{m:02d}:{sec:02d}"
    m = remaining // 60
    sec = remaining % 60
    return f"stops in {m:02d}:{sec:02d}"


# Return context-dependent button label; arbitrary rows always [stop]
def _button_label(s: dict) -> str:
    if s['kind'] == 'arbitrary':
        return '[stop]'
    if not s['running']:
        return '[start]'
    return '[stop]' if s['healthy'] else '[restart]'


# Build one status row (preset or arbitrary — the only difference is prefix/name_width/button/
# action/target, all caller-supplied); registers its own _button_regions entry.
def _build_status_row(s: dict, prefix: str, name_width: int, btn: str, action: str, target: str,
                       error_counts: dict, pane_width: int, phys_row: int) -> str:
    badge      = _badge(s)
    status_txt = _status_text(s)
    countdown  = _format_countdown(s)
    port_str   = f"port {s['port']}"         if s['port']               else ""
    pid_str    = f"pid {s['pid']}"           if s['pid']                else ""
    rss_str    = f"RSS {s['rss_mb']} MB"     if s['rss_mb'] is not None else ""
    model_str  = (s.get('model_name') or '')[:20]
    err_n      = error_counts.get(s['name'], 0)
    err_col    = GREEN if err_n == 0 else ORANGE
    err_str    = f"errors today: {err_col}{err_n}{RESET}"
    content    = (f"{prefix}{s['name']:<{name_width}} {badge} {status_txt:<15} "
                  f"{countdown:<16} {port_str:<14} {pid_str:<13} "
                  f"{rss_str:<14} {model_str:<20} {err_str}")
    vis_len    = len(_strip_ansi(content))
    pad        = max(1, pane_width - vis_len - len(btn))
    _button_regions[(vis_len + pad + 1, vis_len + pad + len(btn), phys_row)] = (action, target)
    return content + ' ' * pad + btn


# Header line + optional [refresh] button; registers its own _button_regions entry when it fits.
def _render_gpu_header(pane_width: int) -> list:
    header_prefix = '  GPU Servers'
    refresh_btn = '[refresh]'
    rule_len, show_refresh = compute_header_rule_len(header_prefix, refresh_btn, 64, pane_width)
    header_text = f"{DIM}{'═' * rule_len}{RESET}{header_prefix}"
    if not show_refresh:
        return [header_text]
    header_vis_len = len(_strip_ansi(header_text))
    header_pad = pane_width - header_vis_len - len(refresh_btn)
    _button_regions[(header_vis_len + header_pad + 1, header_vis_len + header_pad + len(refresh_btn), 1)] = ('refresh', 'refresh')
    return [header_text + ' ' * header_pad + refresh_btn]


# Preset block — always len(presets) rows, digit-keyed [1]/[2]/[3]
def _render_preset_rows(presets: list, error_counts: dict, pane_width: int, start_row: int) -> list:
    rows = []
    for i, s in enumerate(presets):
        btn = _button_label(s)
        action = ('stop' if s['healthy'] else 'restart') if s['running'] else 'start'
        rows.append(_build_status_row(s, f"[{i+1}] ", 16, btn, action, s['name'],
                                       error_counts, pane_width, start_row + i))
    return rows


# Arbitrary block — dynamic, sorted by port, no digit keys; empty (no divider either) when there
# are no arbitrary servers.
def _render_arbitrary_rows(arbitrary: list, error_counts: dict, pane_width: int, start_row: int) -> list:
    if not arbitrary:
        return []
    rows = ["", f"{DIM}{'─' * min(pane_width, 40)}  arbitrary{RESET}"]
    for i, s in enumerate(arbitrary):
        target = f'port-{s["port"]}'
        rows.append(_build_status_row(s, "    ", 12, '[stop]', 'stop', target,
                                       error_counts, pane_width, start_row + 2 + i))
    return rows


def _render_collections_block(collections: list, pane_width: int) -> list:
    rows = ["", f"{DIM}{'═' * min(pane_width, 64)}{RESET}  RAG Collections"]
    if collections:
        for c in collections:
            rows.append(f"  {c['collection']:<32} {c['chunks']} chunks")
    else:
        rows.append(f"  {DIM}(none indexed){RESET}")
    return rows


def _render_errors_block(today_errors: list, pane_width: int) -> list:
    rows = ["", f"{DIM}{'═' * min(pane_width, 64)}{RESET}  Errors today (last 10)"]
    recent = list(reversed(today_errors))[:10]
    if recent:
        for e in recent:
            ts_str  = format_timestamp(e.get("ts", ""))
            server  = e.get("server", "?")
            code    = e.get("code", "?")
            msg     = e.get("msg", "")
            prefix_plain = f"{ts_str}  {server:<12} {code:<14} "
            max_msg = max(0, pane_width - len(prefix_plain) - 1)
            if len(msg) > max_msg:
                msg = msg[:max_msg] + "…"
            rows.append(f"{ts_str}  {server:<12} {ORANGE}{code:<14}{RESET} {msg}")
    else:
        rows.append(f"  {DIM}(no errors today){RESET}")
    return rows


def _render_anomalies_line(anomalies: list) -> list:
    if not anomalies:
        return []
    n = len(anomalies)
    return [f"  {YELLOW}⚠ {n} anomal{'y' if n == 1 else 'ies'} "
            f"(see logs/gpu_pane.log){RESET}"]


# HIGHLIGHT-ONLY, applied as a single post-loop pass right before the final join — no per-row
# background/zebra/hover loop exists in this pane, so utils.highlight_query_in_line's default
# restore_bg is directly correct (same simple case as core/monitor_display.py's main pane).
def _apply_gpu_search_highlight(lines: list, search_query: str, search_match_line_set,
                                 search_current_line) -> None:
    if search_query and search_match_line_set:
        for idx in search_match_line_set:
            if 0 <= idx < len(lines):
                marker = SEARCH_CURRENT_BG if idx == search_current_line else SEARCH_MATCH_BG
                lines[idx] = highlight_query_in_line(lines[idx], search_query, marker)


# Build full pane content; updates _button_regions as side effect. _button_regions' OWN row
# numbering stays relative to THIS function's own top (row 1 = its own first line) — callers that
# prepend a search bar shift it externally (see gpu_pane.pane.run_gpu_loop), so this function
# stays a reusable, standalone, directly-testable unit (dev/click_ui/p4_gpu_news_button_probe.py
# calls it directly and needs zero changes).
def _render_pane(pane_width: int, pane_height: int,
                 presets: list, arbitrary: list, anomalies: list,
                 today_errors: list, error_counts: dict,
                 collections: list, search_query: str = '',
                 search_match_line_set: set | None = None,
                 search_current_line: int | None = None) -> str:
    _button_regions.clear()
    lines: list[str] = _render_gpu_header(pane_width)
    lines.extend(_render_preset_rows(presets, error_counts, pane_width, len(lines) + 1))
    lines.extend(_render_arbitrary_rows(arbitrary, error_counts, pane_width, len(lines) + 1))
    lines.extend(_render_collections_block(collections, pane_width))
    lines.extend(_render_errors_block(today_errors, pane_width))
    lines.extend(_render_anomalies_line(anomalies))
    _apply_gpu_search_highlight(lines, search_query, search_match_line_set, search_current_line)
    return "\n".join(lines)
