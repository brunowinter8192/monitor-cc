# INFRASTRUCTURE
import importlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

AREA_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = AREA_DIR.parents[1]
REPORT_DIR = AREA_DIR / 'md'
OLD_REF = '0ce370df'
HOVER_RENDERS = 21
PROJECTS = Path.home() / '.claude' / 'projects'
SESSIONS = {
    'many_calls (35 turns, 869 calls)': PROJECTS / '-Users-brunowinter2000-Documents-ai-Meta-ClaudeCode-cli-rag-cli--claude-worktrees-builder' / 'b390fcfd-d2ca-41a6-8dff-d35174c717d1.jsonl',
    'many_turns (104 turns, 460 calls)': PROJECTS / '-Users-brunowinter2000-Documents-wise2627' / 'ae01f367-f15e-4c85-97ea-bc68d91d3446.jsonl',
}
SCALES = [1, 10]
PANES = ['tokens', 'worker_tokens']

# ORCHESTRATOR

def timing_workflow() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        return child_measure(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    work_dir = Path(tempfile.mkdtemp(prefix='flicker_m2_timing_'))
    old_root = extract_old_tree(work_dir)
    rows = collect_rows(old_root)
    write_report(rows)
    return 0

# FUNCTIONS

def extract_old_tree(work_dir: Path) -> Path:
    old_root = work_dir / 'old_tree'
    old_root.mkdir()
    archive = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'archive', OLD_REF], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(old_root)], input=archive, check=True)
    return old_root

def collect_rows(old_root: Path) -> list:
    rows = []
    for pane in PANES:
        for label, path in SESSIONS.items():
            for scale in SCALES:
                result = {'pane': pane, 'session': label, 'scale': scale}
                for tree, root in (('old', old_root), ('new', WORKTREE_ROOT)):
                    proc = subprocess.run([sys.executable, str(Path(__file__)), '--child', str(root), pane, str(path), str(scale)], capture_output=True, text=True)
                    result[tree] = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else {'error': proc.stderr[-300:]}
                rows.append(result)
    return rows

def child_measure(root: str, pane: str, jsonl_path: str, scale: int) -> int:
    sys.path.insert(0, root)
    os.chdir(root)
    os.environ.setdefault('MONITOR_CC_ROOT', root)
    os.get_terminal_size = lambda *a: os.terminal_size((120, 45))
    cache_turns = importlib.import_module('src.panes.cache_turns')
    turns, _ = cache_turns.build_cache_turns(Path(jsonl_path), 0, [])
    turns = turns * scale
    handle = make_handle(pane, turns)
    cold_start = time.process_time()
    handle.build()
    cold_ms = (time.process_time() - cold_start) * 1000
    samples = []
    for i in range(HOVER_RENDERS):
        handle.hover(3 + i % 12)
        start = time.process_time()
        handle.build()
        samples.append((time.process_time() - start) * 1000)
    calls = sum(len(t.get('api_calls', [])) for t in turns)
    print(json.dumps({'turns': len(turns), 'calls': calls, 'cold_ms': cold_ms, 'median_ms': statistics.median(samples), 'min_ms': min(samples), 'max_ms': max(samples)}))
    return 0

def make_handle(pane: str, turns: list) -> SimpleNamespace:
    if pane == 'tokens':
        mod = importlib.import_module('src.panes.token_pane')
        mod._cache_turns = turns
        return SimpleNamespace(build=mod._build_tokens_output, hover=lambda row: mod._handle_tokens_mouse(35, 10, row))
    mod = importlib.import_module('src.workers.worker_tokens_pane')
    mod._read_selected_worker_name = lambda monitor: 'w1'
    mod._worker_tokens_workers = [{'name': 'w1', 'status': 'working', 'session': 's1'}]
    mod._worker_tokens_turns = turns
    monitor = SimpleNamespace(active_project_filter='/tmp/flk_m2_timing_proj')
    return SimpleNamespace(build=lambda: mod._build_worker_tokens_output(monitor), hover=lambda row: mod._handle_worker_tokens_mouse(35, 10, row, monitor))

def write_report(rows: list) -> None:
    REPORT_DIR.mkdir(exist_ok=True)
    ref = subprocess.run(['git', '-C', str(WORKTREE_ROOT), 'rev-parse', '--short', OLD_REF], capture_output=True, text=True).stdout.strip()
    lines = ['# m2_hover_timing report', '', f'Run: {datetime.now().isoformat(timespec="seconds")}',
             f'Old: git archive {OLD_REF} ({ref}); new: worktree. Terminal patched to 120x45.',
             f'Each cell: median of {HOVER_RENDERS} hover-triggered builds (one mouse-motion event then one full build of the pane output), ms of process CPU time (the machine is shared and heavily loaded, wall time varies up to 10x); cold = first build.',
             'scale 10 = the real turn list repeated 10 times (synthetic, hypothesis for larger sessions).', '',
             '| pane | session | scale | turns | calls | old cold | old hover median | new cold | new hover median | speedup |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        o, n = r['old'], r['new']
        if 'error' in o or 'error' in n:
            lines.append(f"| {r['pane']} | {r['session']} | {r['scale']} | error | | | | | | {o.get('error', '')[:80]}{n.get('error', '')[:80]} |")
            continue
        lines.append(f"| {r['pane']} | {r['session']} | {r['scale']} | {o['turns']} | {o['calls']} | {o['cold_ms']:.1f} | {o['median_ms']:.2f} | {n['cold_ms']:.1f} | {n['median_ms']:.2f} | {o['median_ms'] / n['median_ms']:.1f}x |")
    (REPORT_DIR / 'm2_hover_timing.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[7:]))

if __name__ == '__main__':
    sys.exit(timing_workflow())
