"""
post_restart_verification.py -- the one script a zero-context agent runs after the proxy restarts
to find out whether the three proxy-side changes on this branch (accept-encoding: identity /
answering_model, the auto-backgrounded-on-timeout strip, poread full-content injection) actually
took effect in real traffic.

Picks the newest recorded session by mtime under the dual-log directory (never a hardcoded stem),
checks all three claims against that one session's six dual-log files, and prints one of PASS,
CONTRADICTED, or MISSING DATA per claim -- a claim with no data to test against is never reported
as a pass. Reuses the real proxy predicates/constants (src/proxy/strip_bg_launch_ack.py,
src/proxy/inject_poread.py, src/proxy_display/forwarded_parser.py) wherever a claim's precision
depends on them, rather than re-typing matching logic that could silently drift from the real
implementation.

Run (from project root or this worktree):
    ./venv/bin/python dev/proxy_instrumentation/post_restart_verification.py

Exit 0: all three claims PASS.
Exit 1: at least one claim is CONTRADICTED (checked first -- the worse outcome).
Exit 2: no claim is CONTRADICTED, but at least one has no data to test (MISSING DATA).

POST_RESTART_VERIFY_LOG_DIR overrides the dual-log source directory -- used to pin a run against a
frozen snapshot (e.g. /tmp/pre_restart_logs/) instead of the live, growing main-checkout corpus.
"""

# INFRASTRUCTURE
import importlib
import json
import os
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE_ROOT))
sys.path.insert(0, str(WORKTREE_ROOT / 'src'))

from proxy.strip_bg_launch_ack import _is_bg_auto_timeout_ack, _BG_AUTO_TIMEOUT_MSG, _BG_AUTO_TIMEOUT_MSG_MAIN
from proxy.message_passes_simple import _apply_bg_launch_ack_strip, _apply_poread_expand_strip
from proxy.inject_poread import _parse_poread_marker, _POREAD_HEADER_PREFIX

_ROOT_PKG = 'src'
_forwarded_parser_mod = importlib.import_module(f'{_ROOT_PKG}.proxy_display.forwarded_parser')
_parse_forwarded_log = _forwarded_parser_mod._parse_forwarded_log

MAIN_REPO_ROOT = Path('/Users/brunowinter2000/Documents/ai/monitor-cc')
DEFAULT_LOG_DIR = MAIN_REPO_ROOT / 'src' / 'logs' / 'dual_log'

REPORT_DIR = Path(__file__).parent / 'md'

CLAIM1_NAME = 'accept-encoding: identity / answering_model'
CLAIM2_NAME = 'auto-backgrounded-on-timeout strip (wording 3)'
CLAIM3_NAME = 'poread full-content injection'

CLAIM1_ACTION = ('send at least one normal message to the main session (any ordinary chat/tool '
                  'turn) so a streamed conversation response gets logged')
CLAIM2_ACTION = ('run a Bash command that exceeds its own timeout without run_in_background, e.g. '
                  '`sleep 130` against the ~120s default, so Claude Code auto-backgrounds it')
CLAIM3_ACTION = ('run `poread <path>` via Bash, alone in its own call (nothing chained after it), '
                  'against a file well under 500,000 bytes')

_BL_FN_NAME = _apply_bg_launch_ack_strip.__name__
_PR_FN_NAME = _apply_poread_expand_strip.__name__

# ORCHESTRATOR

def run_post_restart_verification_workflow() -> int:
    log_dir = _resolve_log_dir()
    stem = _newest_session_stem(log_dir)
    paths = _log_paths(log_dir, stem)

    claims = [
        _check_claim1(paths),
        _check_claim2(paths),
        _check_claim3(paths),
    ]

    _print_report(log_dir, stem, claims)
    _write_report(log_dir, stem, claims)
    return _exit_code(claims)

# FUNCTIONS

def _resolve_log_dir() -> Path:
    override = os.environ.get('POST_RESTART_VERIFY_LOG_DIR')
    return Path(override) if override else DEFAULT_LOG_DIR

def _newest_session_stem(log_dir: Path) -> str:
    files = sorted(log_dir.glob('*_original.jsonl'), key=lambda p: p.stat().st_mtime)
    if not files:
        raise SystemExit(f'no *_original.jsonl found under {log_dir}')
    newest = files[-1]
    return newest.name[:-len('_original.jsonl')]

def _log_paths(log_dir: Path, stem: str) -> dict:
    return {suf: log_dir / f'{stem}_{suf}.jsonl' for suf in
            ('original', 'forwarded', 'stripped', 'injected', 'response', 'errors')}

def _iter_jsonl(path: Path):
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

def _load_last_jsonl_line(path: Path) -> dict:
    with open(path, encoding='utf-8') as f:
        last = deque((l for l in f if l.strip()), maxlen=1)
    return json.loads(last[0]) if last else {}

def _result(name: str, status: str, detail: list, action=None) -> dict:
    return {'name': name, 'status': status, 'detail': detail, 'action': action}

def _missing(name: str, reason: str, action: str) -> dict:
    return _result(name, 'MISSING DATA', [reason], action)

def _is_compressed(content_encoding: str) -> bool:
    ce = (content_encoding or '').lower()
    return bool(ce) and ce != 'identity'

def _check_claim1(paths: dict) -> dict:
    resp_path = paths['response']
    if not resp_path.exists():
        return _missing(CLAIM1_NAME, 'no _response.jsonl found for the newest session', CLAIM1_ACTION)
    entries = list(_iter_jsonl(resp_path))
    if not entries:
        return _missing(CLAIM1_NAME, '_response.jsonl exists but has no entries', CLAIM1_ACTION)

    streaming, side_calls = [], []
    for e in entries:
        ct = e.get('headers', {}).get('content-type', '')
        if 'event-stream' in ct:
            streaming.append(e)
        elif 'json' in ct:
            side_calls.append(e)

    if not streaming:
        return _missing(
            CLAIM1_NAME,
            f'{len(entries)} _response entries observed, 0 are streamed (text/event-stream) '
            'conversation responses',
            CLAIM1_ACTION,
        )

    compressed = [e for e in streaming if _is_compressed(e.get('headers', {}).get('content-encoding', ''))]
    with_model = [e for e in streaming if e.get('answering_model')]
    side_with_model = [e for e in side_calls if e.get('answering_model')]

    ok = not compressed and len(with_model) == len(streaming)
    detail = [
        f'{len(streaming)} streamed conversation responses observed',
        f'{len(compressed)}/{len(streaming)} still carry a compressed content-encoding (expected 0)',
        f'{len(with_model)}/{len(streaming)} carry answering_model (expected {len(streaming)})',
    ]
    if side_calls:
        detail.append(
            f'{len(side_calls)} non-streaming application/json side call(s) observed, '
            f'{len(side_calls) - len(side_with_model)}/{len(side_calls)} correctly show an empty '
            'answering_model -- expected, not a gap'
        )
        if side_with_model:
            detail.append(
                f'NOTE: {len(side_with_model)} side call(s) unexpectedly carry an answering_model '
                '-- not part of this claim, flagged for awareness only'
            )
    return _result(CLAIM1_NAME, 'PASS' if ok else 'CONTRADICTED', detail)

def _iter_user_texts(messages: list):
    for idx, msg in enumerate(messages):
        if msg.get('role') != 'user':
            continue
        content = msg.get('content', '')
        if isinstance(content, str):
            yield idx, content
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'text':
                yield idx, block.get('text', '')
            elif block.get('type') == 'tool_result':
                inner = block.get('content', '')
                if isinstance(inner, str):
                    yield idx, inner
                elif isinstance(inner, list):
                    for sub in inner:
                        if isinstance(sub, dict) and sub.get('type') == 'text':
                            yield idx, sub.get('text', '')

def _newest_original_messages(orig_path: Path) -> list:
    entry = _load_last_jsonl_line(orig_path)
    return entry.get('payload', {}).get('messages', [])

def _bg_launch_ack_strip_fired(stripped_path: Path, is_genuine_removed) -> bool:
    if not stripped_path.exists():
        return False
    for entry in _iter_jsonl(stripped_path):
        fn_map = entry.get('fn_map', {})
        msgs_delta = entry.get('messages_delta', {})
        for loc, fn in fn_map.items():
            if fn != _BL_FN_NAME:
                continue
            parts = loc.split('.')
            if len(parts) != 3:
                continue
            _, midx, bidx = parts
            chunks = msgs_delta.get(midx, {}).get(bidx, [])
            if any(is_genuine_removed(c) for c in chunks):
                return True
    return False

def _forwarded_has_block_starting_with(fwd_path: Path, *prefixes) -> bool:
    if not fwd_path.exists():
        return False
    entries, _pos = _parse_forwarded_log(fwd_path, 0, {}, keep_last=None)
    if not entries:
        return False
    messages = entries[-1].get('messages', [])
    for msg in messages:
        for blk in msg.get('blocks', []):
            text = blk.get('full_text', blk.get('preview', ''))
            if any(text.startswith(p) for p in prefixes):
                return True
    return False

def _check_claim2(paths: dict) -> dict:
    orig_path = paths['original']
    if not orig_path.exists():
        return _missing(CLAIM2_NAME, 'no _original.jsonl found for the newest session', CLAIM2_ACTION)

    messages = _newest_original_messages(orig_path)
    trigger = next((idx for idx, text in _iter_user_texts(messages) if _is_bg_auto_timeout_ack(text)), None)
    if trigger is None:
        return _missing(
            CLAIM2_NAME,
            'no genuine auto-backgrounded-on-timeout tool_result found (role=user, anchored '
            'prefix) in the newest session\'s _original log',
            CLAIM2_ACTION,
        )

    fix_fired = _bg_launch_ack_strip_fired(paths['stripped'], _is_bg_auto_timeout_ack)
    forwarded_ok = _forwarded_has_block_starting_with(paths['forwarded'], _BG_AUTO_TIMEOUT_MSG, _BG_AUTO_TIMEOUT_MSG_MAIN)

    ok = fix_fired and forwarded_ok
    detail = [
        f'genuine trigger found in _original (msg index {trigger}, role=user tool_result, anchored prefix match)',
        f'_stripped: a "{_BL_FN_NAME}" strip whose removed chunk is the wording-3 text was '
        + ('found' if fix_fired else 'NOT found'),
        f'_forwarded: the compact timeout-aware replacement was '
        + ('found' if forwarded_ok else 'NOT found'),
    ]
    return _result(CLAIM2_NAME, 'PASS' if ok else 'CONTRADICTED', detail)

def _poread_expand_fired(injected_path: Path) -> bool:
    if not injected_path.exists():
        return False
    for entry in _iter_jsonl(injected_path):
        fn_map = entry.get('fn_map', {})
        if any(fn == _PR_FN_NAME for fn in fn_map.values()):
            return True
    return False

def _check_claim3(paths: dict) -> dict:
    orig_path = paths['original']
    if not orig_path.exists():
        return _missing(CLAIM3_NAME, 'no _original.jsonl found for the newest session', CLAIM3_ACTION)

    messages = _newest_original_messages(orig_path)
    trigger = next(
        (idx for idx, text in _iter_user_texts(messages) if _parse_poread_marker(text) is not None),
        None,
    )
    if trigger is None:
        return _missing(
            CLAIM3_NAME,
            'no whole-block poread marker found (role=user tool_result, matching the real '
            '_parse_poread_marker fullmatch) in the newest session\'s _original log -- a marker '
            'with anything else in the same block (e.g. chained after another command) does not '
            'count, by design',
            CLAIM3_ACTION,
        )

    injected_fired = _poread_expand_fired(paths['injected'])
    forwarded_ok = _forwarded_has_block_starting_with(paths['forwarded'], _POREAD_HEADER_PREFIX)

    ok = injected_fired and forwarded_ok
    detail = [
        f'genuine whole-block poread marker found in _original (msg index {trigger})',
        f'_injected: a "{_PR_FN_NAME}" injection (rule PR) was ' + ('found' if injected_fired else 'NOT found'),
        f'_forwarded: the file\'s full content, wrapped with "{_POREAD_HEADER_PREFIX}", was '
        + ('found' if forwarded_ok else 'NOT found'),
    ]
    return _result(CLAIM3_NAME, 'PASS' if ok else 'CONTRADICTED', detail)

def _exit_code(claims: list) -> int:
    if any(c['status'] == 'CONTRADICTED' for c in claims):
        return 1
    if any(c['status'] == 'MISSING DATA' for c in claims):
        return 2
    return 0

def _print_report(log_dir: Path, stem: str, claims: list) -> None:
    print('=' * 70)
    print('post-restart verification')
    print('=' * 70)
    print(f'log dir:       {log_dir}')
    print(f'session stem:  {stem}')
    print()
    for c in claims:
        print(f"[{c['status']}] {c['name']}")
        for line in c['detail']:
            print(f'    {line}')
        if c['action']:
            print(f"    ACTION: {c['action']}")
        print()
    passed = sum(1 for c in claims if c['status'] == 'PASS')
    contradicted = sum(1 for c in claims if c['status'] == 'CONTRADICTED')
    missing = sum(1 for c in claims if c['status'] == 'MISSING DATA')
    print('=' * 70)
    print(f'{passed} passed, {contradicted} contradicted, {missing} missing data')
    print('=' * 70)

def _write_report(log_dir: Path, stem: str, claims: list) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    out_path = REPORT_DIR / f'post_restart_verification_{ts}.md'
    lines = [
        '# Post-Restart Verification',
        '',
        f'Generated: {datetime.now(timezone.utc).isoformat()}Z',
        f'Log dir: `{log_dir}`',
        f'Session stem: `{stem}`',
        '',
    ]
    for c in claims:
        lines.append(f"## [{c['status']}] {c['name']}")
        lines.append('')
        for line in c['detail']:
            lines.append(f'- {line}')
        if c['action']:
            lines.append(f"- **ACTION:** {c['action']}")
        lines.append('')
    out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Report written to: {out_path}')

if __name__ == '__main__':
    sys.exit(run_post_restart_verification_workflow())
