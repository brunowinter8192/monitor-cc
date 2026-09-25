# INFRASTRUCTURE
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_AREA_ROOT = next(p for p in Path(__file__).resolve().parents if p.name == 'proxy_dual_log')
_PROJECT_ROOT = _AREA_ROOT.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from A_render_refactor_proof_cases import _build_cases

_REPORTS = _AREA_ROOT / 'A_render_refactor_proof_reports'


# ORCHESTRATOR

def main():
    args = _parse_args()
    cases = _build_cases()
    if args.mode == 'capture':
        _run_capture(cases, args.output)
    else:
        sys.exit(_run_verify(cases, args.baseline))


# FUNCTIONS

def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['capture', 'verify'], required=True)
    today = datetime.now().strftime('%Y%m%d')
    p.add_argument('--output', default=str(_REPORTS / f'baseline_{today}.json'))
    p.add_argument('--baseline', default=None, help='Path to baseline JSON (verify mode)')
    return p.parse_args()


def _run_capture(cases, output):
    from src.proxy_display.format import format_proxy_block
    _REPORTS.mkdir(exist_ok=True)
    results = {}
    for case in cases:
        ansi, total_lines = _render_case(case, format_proxy_block)
        results[case['name']] = {'ansi': ansi, 'total_lines': total_lines}
        print(f'  captured: {case["name"]}')
    Path(output).write_text(json.dumps(results, indent=2))
    print(f'Baseline written: {output}')


def _render_case(case, format_proxy_block):
    name = case['name']
    entries = case['entries']
    expand_states = dict(case.get('expand_states', {}))
    kw = {'pane_height': 200, 'pane_width': 120}
    kw.update(case.get('kwargs', {}))
    if 'copy_rows_out' in kw:
        kw['copy_rows_out'] = set()
    if name == 'expand_fixpoint':
        return _render_fixpoint(entries, kw, format_proxy_block)
    line_map = {}
    return format_proxy_block(entries, expand_states, line_map=line_map, **kw, turn_cache=_turn_cache())


def _render_fixpoint(entries, kw, format_proxy_block):
    expand_states = {}
    known_keys = set()
    result = ('', 0)
    for _ in range(20):
        line_map = {}
        result = format_proxy_block(entries, expand_states, line_map=line_map, **kw, turn_cache=_turn_cache())
        new_keys = {v for v in line_map.values() if v is not None} - known_keys
        if not new_keys:
            break
        known_keys |= new_keys
        for key in new_keys:
            expand_states[key] = True
    return result


def _turn_cache():
    from src.proxy_display.turn_cache import TurnCache
    return TurnCache()


def _run_verify(cases, baseline_path):
    from src.proxy_display.format import format_proxy_block
    if not baseline_path:
        baselines = sorted(_REPORTS.glob('baseline_*.json'))
        if not baselines:
            print('ERROR: no baseline — run --mode capture first')
            return 1
        baseline_path = str(baselines[-1])
        print(f'Using baseline: {baseline_path}')
    baseline = json.loads(Path(baseline_path).read_text())
    failures = []
    for case in cases:
        name = case['name']
        ansi, total_lines = _render_case(case, format_proxy_block)
        exp = baseline.get(name)
        if exp is None:
            failures.append(f'{name}: missing from baseline')
            continue
        if ansi != exp['ansi'] or total_lines != exp['total_lines']:
            failures.append(f'{name}: MISMATCH  lines:{exp["total_lines"]}→{total_lines}  ansi_eq:{ansi==exp["ansi"]}')
    for f in failures:
        print(f'FAIL: {f}')
    if not failures:
        print(f'OK: {len(cases)} cases byte-identical')
        return 0
    return 1


if __name__ == '__main__':
    main()
