"""
Differential proof harness for format_cache_tracker decomposition.

Usage (from project root):
    ./venv/bin/python dev/display/A_format_cache_tracker_proof.py --mode capture
    ./venv/bin/python dev/display/A_format_cache_tracker_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- parse N session JSONLs, call format_cache_tracker on each, write 5-tuple to baseline JSON
    verify   -- call same inputs, assert byte-identical 5-tuple against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: format_cache_tracker(turns, ...) from src/format/token_format.py
Exercises all 3 extraction targets transitively: _render_expanded_call_lines, _compute_cache_viewport, _fmt_rl_reset_time.
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

_HERE = Path(__file__).parent
_REPORTS = _HERE / 'A_format_cache_tracker_proof_reports'
_SESSIONS_DIR = Path.home() / '.claude' / 'projects' / '-Users-brunowinter2000-Documents-ai-Monitor-CC'
_MAX_SESSIONS = 10
_TEST_HEIGHTS = [30, 50]
_TEST_WIDTHS = [60, 80, 100]

# ORCHESTRATOR

def main():
    args = _parse_args()
    sessions = _find_sessions()
    if not sessions:
        print('ERROR: no session JSONLs found', file=sys.stderr)
        sys.exit(1)
    if args.mode == 'capture':
        _run_capture(sessions, args.output)
    else:
        sys.exit(_run_verify(sessions, args.baseline))

# FUNCTIONS

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['capture', 'verify'], default='capture')
    p.add_argument('--output', default=None)
    p.add_argument('--baseline', default=None)
    return p.parse_args()

def _find_sessions():
    if not _SESSIONS_DIR.exists():
        return []
    files = sorted(_SESSIONS_DIR.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:_MAX_SESSIONS]

def _load_turns(jsonl_path):
    from src.jsonl.jsonl_cache_turns import extract_cache_turns
    messages = []
    with open(jsonl_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return extract_cache_turns(messages)

def _run_one_case(turns, pane_height, pane_width):
    from src.format.token_format import format_cache_tracker
    result = format_cache_tracker(turns, pane_height=pane_height, pane_width=pane_width)
    return json.dumps(result, sort_keys=True, default=str)

def _run_capture(sessions, output_path):
    _REPORTS.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = Path(output_path) if output_path else _REPORTS / f'baseline_{ts}.json'
    results = {}
    for s in sessions:
        turns = _load_turns(s)
        for h in _TEST_HEIGHTS:
            for w in _TEST_WIDTHS:
                key = f'{s.stem}_{h}x{w}'
                results[key] = _run_one_case(turns, h, w)
        print(f'  captured: {s.stem} ({len(turns)} turns)')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    total = len(_TEST_HEIGHTS) * len(_TEST_WIDTHS) * len(sessions)
    print(f'Baseline written: {out_path} ({total} cases)')

def _run_verify(sessions, baseline_path):
    if baseline_path is None:
        candidates = sorted(_REPORTS.glob('baseline_*.json'))
        if not candidates:
            print('ERROR: no baseline found', file=sys.stderr)
            return 1
        baseline_path = candidates[-1]
    with open(baseline_path) as f:
        baseline = json.load(f)
    passed = 0
    failed = 0
    for s in sessions:
        turns = _load_turns(s)
        session_ok = True
        for h in _TEST_HEIGHTS:
            for w in _TEST_WIDTHS:
                key = f'{s.stem}_{h}x{w}'
                if key not in baseline:
                    continue
                actual = _run_one_case(turns, h, w)
                if actual == baseline[key]:
                    passed += 1
                else:
                    print(f'  FAIL: {key}')
                    failed += 1
                    session_ok = False
        if session_ok:
            print(f'  PASS: {s.stem} (all {len(_TEST_HEIGHTS)*len(_TEST_WIDTHS)} cases)')
    print(f'\n{passed} passed, {failed} failed (baseline: {baseline_path})')
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    main()
