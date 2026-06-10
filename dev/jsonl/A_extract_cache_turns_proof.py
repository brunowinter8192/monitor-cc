"""
Differential proof harness for extract_cache_turns decomposition.

Usage (from project root):
    ./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode capture
    ./venv/bin/python dev/jsonl/A_extract_cache_turns_proof.py --mode verify [--baseline PATH]

Modes:
    capture  -- parse N session JSONLs, write turns list to baseline JSON
    verify   -- parse same JSONLs, assert byte-identical against baseline, exit 0 (pass) / 1 (fail)

Entry point under test: extract_cache_turns(messages) from src/jsonl/jsonl_cache_turns.py
"""

# INFRASTRUCTURE
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

_HERE = Path(__file__).parent
_REPORTS = _HERE / 'A_extract_cache_turns_proof_reports'
_SESSIONS_DIR = Path.home() / '.claude' / 'projects' / '-Users-brunowinter2000-Documents-ai-Monitor-CC'
_MAX_SESSIONS = 10

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

def _load_messages(jsonl_path):
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
    return messages

def _run_one(session_path):
    from src.jsonl.jsonl_cache_turns import extract_cache_turns
    messages = _load_messages(session_path)
    turns = extract_cache_turns(messages)
    return json.dumps(turns, sort_keys=True, default=str)

def _run_capture(sessions, output_path):
    _REPORTS.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = Path(output_path) if output_path else _REPORTS / f'baseline_{ts}.json'
    results = {}
    for s in sessions:
        key = s.stem
        results[key] = _run_one(s)
        print(f'  captured: {key} ({len(results[key])} chars)')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'Baseline written: {out_path}')

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
        key = s.stem
        if key not in baseline:
            print(f'  SKIP (not in baseline): {key}')
            continue
        actual = _run_one(s)
        if actual == baseline[key]:
            print(f'  PASS: {key}')
            passed += 1
        else:
            print(f'  FAIL: {key}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed (baseline: {baseline_path})')
    return 0 if failed == 0 else 1

if __name__ == '__main__':
    main()
