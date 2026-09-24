# INFRASTRUCTURE
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_LOG_DIR = Path("/Users/brunowinter2000/Documents/ai/monitor-cc/src/logs/dual_log")
_PROJECTS_ROOT = Path("~/.claude/projects").expanduser()
_REPORT_DIR = Path(__file__).resolve().parent / "md"
_PANE_WIDTH = 62
_COLUMN_WIDTH = 62


# ORCHESTRATOR

def _turn_cache():
    from src.proxy_display.turn_cache import TurnCache
    return TurnCache()

def _token_turn_cache():
    from src.format.turn_cache import new_turn_cache
    return new_turn_cache()

def verify_workflow(stem: str, turn_number: int) -> None:
    entries, request_id_by_flow = _load_proxy_side(stem)
    turns = _load_turns(request_id_by_flow)
    proxy_lines = _proxy_plain_lines(entries, turns, request_id_by_flow)
    token_lines = _token_plain_lines(turns)
    report = _compose_report(stem, turn_number, proxy_lines, token_lines, len(entries), turns)
    _write_report(report)
    print(report)


# FUNCTIONS

def _load_proxy_side(stem: str) -> tuple:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    from src.proxy_display.proxy_pane_shared import _accumulate_request_ids
    entries, _ = _parse_forwarded_log(_LOG_DIR / f"{stem}_forwarded.jsonl", 0, {}, keep_last=None)
    request_id_by_flow = {}
    _accumulate_request_ids(_LOG_DIR / f"{stem}_response.jsonl", 0, request_id_by_flow)
    return entries, request_id_by_flow


def _load_turns(request_id_by_flow: dict) -> list:
    from src.dual_log_cli.usage import _find_transcript
    from src.panes.cache_turns import build_cache_turns
    directories = [path for path in _PROJECTS_ROOT.iterdir() if path.is_dir()]
    transcript = next(path for path in (_find_transcript(rid, directories) for rid in request_id_by_flow.values()) if path)
    turns, _ = build_cache_turns(transcript, 0, [])
    return turns


def _plain(ansi: str) -> list:
    from src.utils import _ANSI_ESCAPE_RE
    return [_ANSI_ESCAPE_RE.sub("", line).replace("\x1b[K", "").rstrip() for line in ansi.split("\n")]


def _proxy_plain_lines(entries: list, turns: list, request_id_by_flow: dict) -> list:
    from src.proxy_display.format import format_proxy_block
    ansi, _ = format_proxy_block(entries, {}, None, None, 100000, _PANE_WIDTH, 0, turns, request_id_by_flow=request_id_by_flow, turn_cache=_turn_cache())
    return _plain(ansi)


def _token_plain_lines(turns: list) -> list:
    from src.format.token_format import format_cache_tracker
    lines, _keys, _sticky, _start, _count = format_cache_tracker(turns, {}, 100000, _PANE_WIDTH, 0, turn_cache=_token_turn_cache())
    return _plain("\n".join(lines))


def _turn_slice(lines: list, turn_number: int) -> list:
    start = next(i for i, line in enumerate(lines) if line.startswith(f"Turn {turn_number} ") or line.startswith(f"Turn {turn_number}:"))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("Turn ")), len(lines))
    return [line for line in lines[start:end] if line.strip()]


def _row_time(line: str) -> str:
    match = re.search(r"(\d\d:\d\d:\d\d)$", line)
    return match.group(1) if match else ""


def _proxy_numbering(lines: list) -> list:
    rows = []
    turn = 0
    for line in lines:
        header = re.match(r"Turn (\d+)\b", line)
        if header:
            turn = int(header.group(1))
            continue
        row = re.search(r"REQ #(\d+)(\.\d+)? ", line)
        if row and not row.group(2):
            rows.append((int(row.group(1)), turn, _row_time(line)))
    return rows


def _token_numbering(lines: list) -> list:
    rows = []
    turn = 0
    for line in lines:
        header = re.match(r"Turn (\d+)\b", line)
        if header:
            turn = int(header.group(1))
            continue
        row = re.search(r"REQ #(\d+) ", line)
        if row:
            rows.append((int(row.group(1)), turn, _row_time(line)))
    return rows


def _cut_cells(text: str, width: int) -> str:
    from src.utils import _cell_width
    used = 0
    for i, ch in enumerate(text):
        used += _cell_width(ch)
        if used > width:
            return text[:i]
    return text


def _pad_cells(text: str, width: int) -> str:
    from src.utils import _cell_width
    return text + " " * (width - sum(_cell_width(ch) for ch in text))


def _side_by_side(left: list, right: list) -> list:
    rows = []
    for i in range(max(len(left), len(right))):
        l = left[i] if i < len(left) else ""
        r = right[i] if i < len(right) else ""
        rows.append(f"{_pad_cells(_cut_cells(l, _COLUMN_WIDTH), _COLUMN_WIDTH)} | {_cut_cells(r, _COLUMN_WIDTH)}")
    return rows


def _compose_report(stem: str, turn_number: int, proxy_lines: list, token_lines: list, entry_count: int, turns: list) -> str:
    proxy_rows = _proxy_numbering(proxy_lines)
    token_rows = _token_numbering(token_lines)
    unmapped = sum(1 for line in proxy_lines if "REQ #?" in line)
    out = [
        f"session: {stem}",
        f"proxy entries: {entry_count}  |  token-pane turns: {len(turns)}  |  token-pane REQ rows: {len(token_rows)}",
        f"proxy rows with a number (first occurrence): {len(proxy_rows)}  |  proxy rows 'REQ #?': {unmapped}",
        f"(number, turn, time) triples identical between panes: {proxy_rows == token_rows}  (pane width {_PANE_WIDTH})",
        "",
        f"Turn {turn_number}, proxy pane (left) | token pane (right)",
        f"{'-' * _COLUMN_WIDTH}-+-{'-' * _COLUMN_WIDTH}",
    ]
    out.extend(_side_by_side(_turn_slice(proxy_lines, turn_number), _turn_slice(token_lines, turn_number)))
    return "\n".join(out)


def _write_report(report: str) -> None:
    _REPORT_DIR.mkdir(exist_ok=True)
    name = f"verify_req_numbering_{re.sub(r'[^A-Za-z0-9]+', '_', sys.argv[1])}_turn{sys.argv[2]}.md"
    (_REPORT_DIR / name).write_text(f"```\n{report}\n```\n", encoding="utf-8")


if __name__ == "__main__":
    verify_workflow(sys.argv[1], int(sys.argv[2]))
