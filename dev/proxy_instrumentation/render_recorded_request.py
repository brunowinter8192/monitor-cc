# INFRASTRUCTURE
import json
import sys
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'
STEM = 'api_requests_opus_posts_1785266871'
FWD_PATH = LOG_DIR / f'{STEM}_forwarded.jsonl'
STRIPPED_PATH = LOG_DIR / f'{STEM}_stripped.jsonl'
INJECTED_PATH = LOG_DIR / f'{STEM}_injected.jsonl'
TARGET_REQUEST_ID = 'b6e4f411-74b2-4b56-8940-bf5ce51e7380'

_ANSI_RE = __import__('re').compile(r'\x1b\[[0-9;]*m')
_MSG_HEADER_RE = __import__('re').compile(r'^ {4}\[(\s*\d+)\]')


# ORCHESTRATOR

def main() -> None:
    from src.proxy_display.forwarded_parser import _parse_forwarded_log
    target_line = _verify_target_line_index()
    entries, _ = _parse_forwarded_log(FWD_PATH, 0, {})

    print(f"=== Request b6e4f411 (dual-log line {target_line}) — msg 276 strip+inject spans ===")
    target, prev_same, prev_idx = _build_entries_and_spans(entries, target_line)
    print(f"message_count={target.get('message_count')} prev_same message_count={prev_same.get('message_count')} (prev_idx={prev_idx})")
    lines, keys = _render(target_line, target, prev_same)
    assert len(lines) == len(keys)
    print(f"total rendered lines: {len(lines)}")
    for i, ln in enumerate(lines):
        print(f"{i:4d}| {ln!r}")
    print("\n--- msg 276 slice ---")
    for ln in _slice_message(lines, 276):
        print(repr(ln))

    control_line = target_line - 1
    print(f"\n=== Control: message 274, introduced by request at dual-log line {control_line} ===")
    control, control_prev, control_prev_idx = _build_entries_and_spans(entries, control_line)
    print(f"message_count={control.get('message_count')} prev_same message_count={control_prev.get('message_count')} (prev_idx={control_prev_idx})")
    c_lines, c_keys = _render(control_line, control, control_prev)
    assert len(c_lines) == len(c_keys)
    print("--- msg 274 slice ---")
    for ln in _slice_message(c_lines, 274):
        print(repr(ln))


# FUNCTIONS

def _verify_target_line_index() -> int:
    with open(STRIPPED_PATH, encoding='utf-8') as f:
        for i, line in enumerate(f):
            entry = json.loads(line)
            if entry.get('request_id') == TARGET_REQUEST_ID:
                assert i == 132, f"expected line 132, found request_id at line {i}"
                return i
    raise AssertionError(f"request_id {TARGET_REQUEST_ID} not found in {STRIPPED_PATH}")


def _build_entries_and_spans(entries: list, line_idx: int):
    from src.proxy_display.forwarded_parser import _lazy_load_messages_forwarded, _infer_model_family
    from src.proxy_display.dual_log_accumulator import accumulate_dual_log
    target = entries[line_idx]
    prev_idx = _resolve_prev_same(entries, line_idx)
    assert prev_idx is not None, "no prev_same entry resolved"
    prev_same = entries[prev_idx]
    for e in (target, prev_same):
        if e.get('messages') is None:
            ok = _lazy_load_messages_forwarded(e, FWD_PATH)
            assert ok, f"lazy load failed for _fwd_req_idx={e.get('_fwd_req_idx')}"
    acc_stripped: dict = {}
    acc_injected: dict = {}
    accumulate_dual_log(STRIPPED_PATH, 0, acc_stripped)
    accumulate_dual_log(INJECTED_PATH, 0, acc_injected)
    family = _infer_model_family(target.get('model', ''))
    for e in (target, prev_same):
        e['_stripped_spans'] = acc_stripped[family]
        e['_injected_spans'] = acc_injected[family]
    return target, prev_same, prev_idx


def _resolve_prev_same(entries: list, k: int):
    from src.proxy_display.format import _is_standalone_entry
    for i in range(k - 1, -1, -1):
        if not _is_standalone_entry(entries[i]):
            return i
    return None


def _render(entry_idx: int, target: dict, prev_same: dict) -> tuple:
    from src.proxy_display.render_messages import render_messages
    return render_messages(entry_idx, target, prev_same, [], {}, pane_width=200)


def _slice_message(lines: list, msg_idx: int) -> list:
    out = []
    capturing = False
    for ln in lines:
        visible = _ANSI_RE.sub('', ln)
        m = _MSG_HEADER_RE.match(visible)
        if m:
            if int(m.group(1)) == msg_idx:
                capturing = True
            else:
                if capturing:
                    break
                capturing = False
        if capturing:
            out.append(ln)
    return out


if __name__ == '__main__':
    main()
